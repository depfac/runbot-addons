#!/usr/bin/env python
#  -*- coding: utf-8 -*-
"""
This script is meant to pull the translations from Transifex .
Technically, it will pull the translations from Transifex,
compare it with the po files in the repository and replace it if needed

Installation
============

For using this utility, you need to install these dependencies:

* gitlab3.py library for handling GitLab calls. To install it, use:
  `sudo pip install gitlab3.py`.
* slumber library for handling Transifex calls (REST calls). To install it,
  use `sudo pip install slumber`.
* polib library for po handling. To install it, use `sudo pip install polib`.

Configuration
=============

You must have a file called oca.cfg on the same folder of the script for
storing credentials parameters. You can generate an skeleton config running
this script for a first time.

Usage
=====

tx_pull.py [-h] [-p PROJECTS [PROJECTS ...]]

optional arguments:
  -h, --help            show this help message and exit
  -p PROJECTS [PROJECTS ...], --projects PROJECTS [PROJECTS ...]
                        List of slugs of Transifex projects to pull

You have to set correctly the configuration file (oca.cfg), and then you'll
see the progress in the screen. The script will:

* Scan all accesible projects for the user (or only the passed ones with
  -p/--projects argument).
* Check which ones contain 'OCA-' string.
* Retrieve the available translation strings
* Reverse the name of the project slug to get GitLab branch
* Compare with the existing GitLab files
* If changed, a commit is pushed to GitLab with the updated files

Known issues / Roadmap
======================

* This script is only valid for OCA projects pushed to Transifex with default
  naming scheme. This is because there's a reversal operation in the name to
  get the GitLab repo. It can be easily adapted to get pairs of Transifex slugs
  with the corresponding GitLab branch.
* The scan is made downloading each translation file, so it's an slow process.
  Maybe we can improve this using Transifex statistics (see
  http://docs.transifex.com/api/statistics/) to check if there is no update
  in the resource, and comparing with the date of the last commit made by
  this script (but forces also to check for this commit on GitLab). Another
  option is to add an argument to provide a date, and check if there is an
  update for the resource translation beyond that date. As this also needs a
  call, it has to be tested if we improve or not the speed.

Credits
=======

Contributors
------------

* Samuel Lefever
* Pedro M. Baeza <pedro.baeza@serviciosbaeza.com>

Maintainer
----------

.. image:: https://odoo-community.org/logo.png
   :alt: Odoo Community Association
   :target: https://odoo-community.org

This module is maintained by the OCA.

OCA, or the Odoo Community Association, is a nonprofit organization whose
mission is to support the collaborative development of Odoo features and
promote its widespread use.

To contribute to this module, please visit http://odoo-community.org.
"""

import argparse
import os.path
import re
import time
import gitlab3

import polib
from slumber import API, exceptions
from pygit2 import Repository, Signature
from pygit2 import GIT_FILEMODE_TREE, GIT_FILEMODE_BLOB


parser = argparse.ArgumentParser(
    description='Pull Transifex updated translations to GitLab',
    add_help=True)
parser.add_argument('tx_login', help='Transifex Login')
parser.add_argument('tx_password', help='Transifex Password')
parser.add_argument('tx_organization', help='Transifex Organization')
parser.add_argument('tx_project_shortcut', help='Transifex Project Shortcut')
parser.add_argument('gitlab_url', help='GitLab URL')
parser.add_argument('gitlab_token', help='GitLab Token')
parser.add_argument('gitlab_repo_url', help='GitLab Rpo URL')
parser.add_argument('bare_repo_path', help='Bare Repo Path')
parser.add_argument('-b', '--git_branch', dest='git_branch', help='Git Branch', default='develop')
parser.add_argument('-v', '--odoo_version', dest='odoo_version', action='store', help='Odoo Version', default='8.0')
parser.add_argument('-r', '--tx_num_retries', help='Max Retrieves', dest='tx_num_retries', default=3)

TX_URL = "https://www.transifex.com/api/2/"

class TransifexPuller(object):
    def __init__(self):
        result = parser.parse_args()
        arguments = dict(result._get_kwargs())

        tx_login = arguments['tx_login']
        tx_password = arguments['tx_password']
        tx_organization = arguments['tx_organization']
        gitlab_token = arguments['gitlab_token']

        self.tx_project_shortcut = arguments['tx_project_shortcut']
        self.gitlab_url = arguments['gitlab_url']
        self.gitlab_repo_url = arguments['gitlab_repo_url']
        self.bare_repo_path = arguments['bare_repo_path']
        self.git_branch = arguments['git_branch']
        self.odoo_version = arguments['odoo_version']
        self.tx_num_retries = arguments['tx_num_retries']

        self.transifex_project_slug = "%s-%s" % (self.tx_project_shortcut,
                                      self.odoo_version.replace('.', '-'))

        self.tx_org = tx_organization
        self.gl_token = gitlab_token
        self.gl_org = self.tx_org
        self.gl_credentials = Signature('Worldline Runbot', 'runbot@depfac.com')
        
        # Connect to GitLab
        self.gitlab = gitlab3.GitLab(self.gitlab_url, gitlab_token)

        # Connect to Transifex
        self.tx_api = API(TX_URL, auth=(tx_login, tx_password))

    @classmethod
    def _load_po_dict(cls, po_file):
        po_dict = {}
        for po_entry in po_file:
            if po_entry.msgstr:
                key = u'\n'.join(x[0] for x in po_entry.occurrences)
                key += u'\nmsgid "%s"' % po_entry.msgid
                po_dict[key] = po_entry.msgstr
        return po_dict

    @classmethod
    def _get_owner_repository(cls, gitlab_repo_url):
        if gitlab_repo_url.startswith('https://'):
            regex = r'^https:\/\/.*\/(?P<owner>.*)\/(?P<repo>.*).git$'
        elif gitlab_repo_url.startswith('git@'):
            regex = r'^git@.*:(?P<owner>.*)\/(?P<repo>.*).git$'
        else:
            raise Warning('The GitLab URL %s is not valid (SSH or HTTPS only)')

        match_object = re.search(regex, gitlab_repo_url)
        owner = match_object.group('owner')
        repository = match_object.group('repo')
        return owner, repository


    def pull_translation(self):
        print "Retrieve project %s (%s)" % (self.tx_project_shortcut, self.transifex_project_slug)
        try:
            tx_project = self.tx_api.project(self.transifex_project_slug).get()
        except:
            raise  Exception('Cannot retrieve the project %s' % self.transifex_project_slug)

        print "Init Repo GitLab"
        repo = Repository(self.bare_repo_path)
        root = repo.TreeBuilder()

        print "Processing project '%s'..." % tx_project['name']
        owner, repo_name = self._get_owner_repository(self.gitlab_repo_url)
        # get a reference to the gitlab repo and branch where to push the
        # the translations
        project = [project for project in self.gitlab.projects() if '%s/%s.git' % (owner, repo_name) in project.http_url_to_repo]
        if not project:
            raise Exception('Project %s not found in the repo gitlab' % tx_project['name'])
        project = project[0]
        tree_data = []

        tx_project_api = self.tx_api.project(tx_project['slug'])
        resources = tx_project_api.resources().get()
        for resource in resources:
            print "Checking resource %s..." % resource['name']
            tx_resource_api = tx_project_api.resource(resource['slug'])
            resource = tx_resource_api.get(details=True)
            for lang in resource['available_languages']:
                cont = 0
                tx_lang = False
                while cont < self.tx_num_retries and not tx_lang:
                    # for some weird reason, sometimes Transifex fails to
                    # some requests, so this retry mechanism handles this
                    # problem
                    try:
                        tx_lang = tx_resource_api.translation(
                            lang['code']).get()
                    except exceptions.HttpClientError:
                        tx_lang = False
                        cont += 1
                if tx_lang:
                    try:
                        tx_po_file = polib.pofile(tx_lang['content'])
                        tx_po_dict = self._load_po_dict(tx_po_file)
                        # Discard empty languages
                        if not tx_po_dict:
                            continue
                        gl_i18n_path = os.path.join(
                            '/', resource['slug'], "i18n")
                        gl_file_path = os.path.join(
                            gl_i18n_path, lang['code'] + '.po')[1:]
                        try:
                            gl_file = project.get_blob(self.git_branch, gl_file_path)
                        except:
                            print "ERROR: Cannot retrieve the file %s on branch %s" % (gl_file_path, self.git_branch)
                        if gl_file:
                            gl_po_file = polib.pofile(
                                gl_file.decode('utf-8'))
                            gl_po_dict = self._load_po_dict(gl_po_file)
                            unmatched_items = (set(gl_po_dict.items()) ^
                                               set(tx_po_dict.items()))
                            if not unmatched_items:
                                print "...no change in %s" % gl_file_path
                                continue
                        print '..replacing %s' % gl_file_path
                        new_file_blob = repo.create_blob(tx_lang['content'].encode('utf-8'))
                        auto_insert(repo, root, gl_file_path, new_file_blob, GIT_FILEMODE_BLOB)
                    except (KeyboardInterrupt, SystemExit):
                        raise
                    except:
                        raise
                        print "ERROR: processing lang '%s'" % lang['code']
                else:
                    print "ERROR: fetching lang '%s'" % lang['code']
            # Wait a minute before the next file to avoid reaching Transifex
            # API limitations
            # TODO: Request the API to get the date for the next request
            # http://docs.rackspace.com/loadbalancers/api/v1.0/clb-devguide/\
            # content/Determining_Limits_Programmatically-d1e1039.html

        tree_oid = repo.index.write_tree()
        message = 'Transbot updated translations from Transifex'
        branch = repo.lookup_branch(self.git_branch)

        print "message", message
        commit = repo.create_commit(branch.name, self.gl_credentials, self.gl_credentials, message, tree_oid, [branch.target])

        print "git pushing"
        # TODO To implement
        #repo.ref('heads/{}'.format(gl_branch.name)).update(commit.sha)
        # Wait 5 minutes before the next project to avoid reaching Transifex
        # API limitations
        # TODO: Request the API to get the date for the next request
        # http://docs.rackspace.com/loadbalancers/api/v1.0/clb-devguide/\
        # content/Determining_Limits_Programmatically-d1e1039.html
        print "Sleeping 5 minutes..."
        time.sleep(300)



def auto_insert(repo, treebuilder, path, thing, mode):
    """figure out and deal with the necessary subtree structure"""
    path_parts = path.split('/', 1)
    if len(path_parts) == 1:  # base case
        treebuilder.insert(path, thing, mode)
        return treebuilder.write()

    subtree_name, sub_path = path_parts
    tree_oid = treebuilder.write()
    tree = repo.get(tree_oid)
    try:
        entry = tree[subtree_name]
        assert entry.filemode == GIT_FILEMODE_TREE,\
            '{} already exists as a blob, not a tree'.format(entry.name)
        existing_subtree = repo.get(entry.hex)
        sub_treebuilder = repo.TreeBuilder(existing_subtree)
    except KeyError:
        sub_treebuilder = repo.TreeBuilder()

    subtree_oid = auto_insert(repo, sub_treebuilder, sub_path, thing, mode)
    treebuilder.insert(subtree_name, subtree_oid, GIT_FILEMODE_TREE)
    return treebuilder.write()

def main():
    tp = TransifexPuller()
    tp.pull_translation()


if __name__ == '__main__':
    main()
