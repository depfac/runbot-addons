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
import os

import polib
from slumber import API, exceptions


parser = argparse.ArgumentParser(
    description='Pull Transifex updated translations to the file system',
    add_help=True)
parser.add_argument('tx_login', help='Transifex Login')
parser.add_argument('tx_password', help='Transifex Password')
parser.add_argument('tx_slug', help='Transifex Slug')
parser.add_argument('-p', '--project_path', dest='path_out', help='Project Path', default=os.getcwd())
parser.add_argument('-r', '--tx_num_retries', help='Max Retrieves', dest='tx_num_retries', default=3)

TX_URL = "https://www.transifex.com/api/2/"

class TransifexPuller(object):
    def __init__(self):
        result = parser.parse_args()
        arguments = dict(result._get_kwargs())

        tx_login = arguments['tx_login']
        tx_password = arguments['tx_password']
        self.transifex_project_slug = arguments['tx_slug']
        self.tx_num_retries = arguments['tx_num_retries']

        self.path_out = arguments['path_out']
        self._check_path(self.path_out)

        # Connect to Transifex
        self.tx_api = API(TX_URL, auth=(tx_login, tx_password))

    def _check_path(self, path):
        if not os.path.isdir(path):
            raise Exception('The folder %s doesn\'t exist' % path)
        if not os.path.isdir(os.path.join(path, '.git')):
            raise Exception('This folder exists but it is not a git folder (no .git folder found)')
        if not os.access(path, os.W_OK):
            raise Exception('You cannot write on this folder')

    def pull_translation(self):
        print "Retrieve project %s" % (self.transifex_project_slug)
        try:
            tx_project = self.tx_api.project(self.transifex_project_slug).get()
        except:
            raise  Exception('Cannot retrieve the project %s' % self.transifex_project_slug)

        print "Processing project '%s'..." % tx_project['name']
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
                        gl_i18n_path = os.path.join(self.path_out, resource['slug'], "i18n")
                        if not os.path.isdir(gl_i18n_path):
                            os.makedirs(gl_i18n_path)

                        gl_file_path = os.path.join(gl_i18n_path, lang['code'] + '.po')
                        tx_po_file.save(gl_file_path)

                    except (KeyboardInterrupt, SystemExit):
                        raise
                    except:
                        raise
                        print "ERROR: processing lang '%s'" % lang['code']
                else:
                    print "ERROR: fetching lang '%s'" % lang['code']


def main():
    tp = TransifexPuller()
    tp.pull_translation()


if __name__ == '__main__':
    main()
