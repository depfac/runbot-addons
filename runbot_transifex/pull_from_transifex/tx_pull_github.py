#!/usr/bin/env python
#  -*- coding: utf-8 -*-
"""
This script is meant to pull the translations from Transifex .
Technically, it will pull the translations from Transifex,
compare it with the po files in the repository and replace it if needed

Installation
============

For using this utility, you need to install these dependencies:

* github3.py library for handling Github calls. To install it, use:
  `sudo pip install github3.py`.
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
* Reverse the name of the project slug to get GitHub branch
* Compare with the existing GitHub files
* If changed, a commit is pushed to GitHub with the updated files

Known issues / Roadmap
======================

* This script is only valid for OCA projects pushed to Transifex with default
  naming scheme. This is because there's a reversal operation in the name to
  get the GitHub repo. It can be easily adapted to get pairs of Transifex slugs
  with the corresponding GitHub branch.
* The scan is made downloading each translation file, so it's an slow process.
  Maybe we can improve this using Transifex statistics (see
  http://docs.transifex.com/api/statistics/) to check if there is no update
  in the resource, and comparing with the date of the last commit made by
  this script (but forces also to check for this commit on GitHub). Another
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
import github3

import polib
from slumber import API, exceptions


parser = argparse.ArgumentParser(
    description='Pull Transifex updated translations to GitHub',
    add_help=True)
parser.add_argument('tx_login', help='Transifex Login')
parser.add_argument('tx_password', help='Transifex Password')
parser.add_argument('tx_organization', help='Transifex Organization')
parser.add_argument('tx_project_shortcut', help='Transifex Project Shortcut')
parser.add_argument('github_token', help='GitHub Token')
parser.add_argument('github_email', help='GihHub Email')
parser.add_argument('github_url', help='Github URL')
parser.add_argument('-b', '--git_branch', dest='github_branch', help='Git Branch', default='develop')
parser.add_argument('-v', '--odoo_version', dest='odoo_version', action='store', help='Odoo Version', default='8.0')
parser.add_argument('-r', '--tx_num_retries', help='', dest='tx_num_retries', default=3)

TX_URL = "https://www.transifex.com/api/2/"


class TransifexPuller(object):
    def __init__(self):
        result = parser.parse_args()
        arguments = dict(result._get_kwargs())

        tx_login = arguments['tx_login']
        tx_password = arguments['tx_password']
        tx_organization = arguments['tx_organization']
        github_token = arguments['github_token']
        github_email = arguments['github_email']

        self.tx_project_shortcut = arguments['tx_project_shortcut']
        self.github_url = arguments['github_url']
        self.github_branch = arguments['github_branch']
        self.odoo_version = arguments['odoo_version']
        self.tx_num_retries = arguments['tx_num_retries']

        self.transifex_project_slug = "%s-%s" % (self.tx_project_shortcut,
                                      self.odoo_version.replace('.', '-'))

        self.tx_org = tx_organization
        self.gh_token = github_token
        self.gh_org = self.tx_org
        # Connect to GitHub
        self.github = github3.login(token=github_token)
        gh_user = self.github.user()

        if not gh_user.email and not github_email:
            raise Exception(
                'Email required to commit to github. Please provide one on '
                'the command line or make the one of your github profile '
                'public.')
        self.gh_credentials = {'name': gh_user.name or str(gh_user),
                               'email': gh_user.email or github_email}

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
    def _get_owner_repository(cls, github_url):
        if github_url.startswith('https://'):
            regex = r'^https:\/\/github.com\/(?P<owner>.*)\/(?P<repo>.*).git$'
        elif github_url.startswith('git@'):
            regex = r'^git@github.com:(?P<owner>.*)\/(?P<repo>.*).git$'
        else:
            raise Warning('The GitHub URL %s is not valid (SSH or HTTPS only)')

        match_object = re.search(regex, github_url)
        owner = match_object.group('owner')
        repository = match_object.group('repo')
        return owner, repository


    def pull_translation(self):
        print "Retrieve project %s (%s)" % (self.tx_project_shortcut, self.transifex_project_slug)
        try:
            tx_project = self.tx_api.project(self.transifex_project_slug).get()
        except:
            raise  Exception('Cannot retrieve the project %s' % self.transifex_project_slug)

        print "Processing project '%s'..." % tx_project['name']
        owner, repo = self._get_owner_repository(self.github_url)
        # get a reference to the github repo and branch where to push the
        # the translations
        gh_repo = self.github.repository(owner, repo)
        gh_branch = gh_repo.branch(self.github_branch)
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
                        gh_i18n_path = os.path.join(
                            '/', resource['slug'], "i18n")
                        gh_file_path = os.path.join(
                            gh_i18n_path, lang['code'] + '.po')
                        gh_file = gh_repo.contents(
                            gh_file_path, gh_branch.name)
                        if gh_file:
                            gh_po_file = polib.pofile(
                                gh_file.decoded.decode('utf-8'))
                            gh_po_dict = self._load_po_dict(gh_po_file)
                            unmatched_items = (set(gh_po_dict.items()) ^
                                               set(tx_po_dict.items()))
                            if not unmatched_items:
                                print "...no change in %s" % gh_file_path
                                continue
                        print '..replacing %s' % gh_file_path
                        new_file_blob = gh_repo.create_blob(
                            tx_lang['content'], encoding='utf-8')
                        tree_data.append({
                            'path': gh_file_path[1:],
                            'mode': '100644',
                            'type': 'blob',
                            'sha': new_file_blob})
                    except (KeyboardInterrupt, SystemExit):
                        raise
                    except:
                        print "ERROR: processing lang '%s'" % lang['code']
                else:
                    print "ERROR: fetching lang '%s'" % lang['code']
            # Wait a minute before the next file to avoid reaching Transifex
            # API limitations
            # TODO: Request the API to get the date for the next request
            # http://docs.rackspace.com/loadbalancers/api/v1.0/clb-devguide/\
            # content/Determining_Limits_Programmatically-d1e1039.html
            print "Sleeping a minute..."
            time.sleep(60)

        if tree_data:
            tree_sha = gh_branch.commit.commit.tree.sha
            tree = gh_repo.create_tree(tree_data, tree_sha)
            message = 'Transbot updated translations from Transifex'
            print "message", message
            commit = gh_repo.create_commit(
                message=message, tree=tree.sha, parents=[gh_branch.commit.sha],
                author=self.gh_credentials, committer=self.gh_credentials)
            print "git pushing"
            gh_repo.ref('heads/{}'.format(gh_branch.name)).update(commit.sha)
        # Wait 5 minutes before the next project to avoid reaching Transifex
        # API limitations
        # TODO: Request the API to get the date for the next request
        # http://docs.rackspace.com/loadbalancers/api/v1.0/clb-devguide/\
        # content/Determining_Limits_Programmatically-d1e1039.html
        print "Sleeping 5 minutes..."
        time.sleep(300)


def main():
    tp = TransifexPuller()
    tp.pull_translation()


if __name__ == '__main__':
    main()
