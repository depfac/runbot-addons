#!/usr/bin/env python
# coding: utf-8
import os
import argparse
from odoo_connection import context_mapping
from slumber import API, exceptions
from txclib import utils, commands

parser = argparse.ArgumentParser(description='Push translation from Odoo to Transiflex')
parser.add_argument('tx_login', action='store', help='Transifex Login')
parser.add_argument('tx_passwd', action='store', help='Transifex Password')
parser.add_argument('addons', action='store', help='Odoo Addons')
parser.add_argument('db_name', action='store', help='Odoo DB name')
parser.add_argument('server_path', action='store', help='Odoo Server Path')
parser.add_argument('addons_path', action='store', help='Odoo Addons Path')
parser.add_argument('project_name', action='store', help='Transifex Project Name')
parser.add_argument('project_shortcut', action='store', help='Transifex Project Shortcut')
parser.add_argument('project_organization', action='store', help='Transifex Project Organization')
parser.add_argument('--odoo_version', action='store', help='Odoo Version', default='8.0')
parser.add_argument('--fillup-resources', action='store_true', default=False, dest='fillup-resources', help='If the system should fill up resources automatically with 100% similar matches from the Translation Memory')
parser.add_argument('--version', action='version', version='%(prog)s 1.0')


def main(argv=None):
    result = parser.parse_args()
    arguments = dict(result._get_kwargs())

    transifex_user = arguments['tx_login']
    transifex_password = arguments['tx_passwd']
    addons_str = arguments['addons']
    db_name = arguments['db_name']
    server_path = arguments['server_path']
    addons_path = arguments['addons_path']
    project_name = arguments['project_name']
    project_shortcut = arguments['project_shortcut']
    project_organization = arguments['project_organization']
    odoo_version = arguments.get('odoo_version')
    transifex_fill_up_resources = arguments.get('fillup-resources', False)

    addons = addons_str.split(',')

    transifex_project_name = "%s (%s)" % (project_name, odoo_version)
    transifex_organization = project_organization

    # Create Transifex project if it doesn't exist
    print
    print "Creating Transifex project if it doesn't exist"
    auth = (transifex_user, transifex_password)
    api_url = "https://www.transifex.com/api/2/"
    api = API(api_url, auth=auth)
    project_data = {"slug": project_shortcut,
                    "name": transifex_project_name,
                    "description": transifex_project_name,
                    "source_language_code": 'en_US',
                    "organization": project_organization,
                    "private": True,
                    "fill_up_resources": transifex_fill_up_resources,
                    }
    try:
        api.project(project_shortcut).get()
        print 'This Transifex project already exists.'
    except exceptions.HttpClientError:
        try:
            api.projects.post(project_data)
            print 'Transifex project has been successfully created.'
        except exceptions.HttpClientError:
            print 'Transifex organization: %s' % transifex_organization
            print 'Transifex username: %s' % transifex_user
            print 'Transifex project slug: %s' % project_shortcut
            print 'Error: Authentication failed. Please verify that '\
                      'Transifex organization, user and password are '\
                      'correct. You can change these variables in your '\
                      '.travis.yml file.'
            raise

    print "\nModules to translate: %s" % addons_str

    # Initialize Transifex project
    print
    print 'Initializing Transifex project'
    init_args = ['--host=https://www.transifex.com',
                 '--user=%s' % transifex_user,
                 '--pass=%s' % transifex_password]
    commands.cmd_init(init_args, path_to_tx=None)
    path_to_tx = utils.find_dot_tx()

    # Initialize Odoo Socket
    connection_context = context_mapping[odoo_version]
    with connection_context(server_path, addons_path, db_name) \
            as odoo_context:
        for module in addons:
            print
            print "Downloading PO file for %s" % module
            source_filename = os.path.join(addons_path, module, 'i18n',
                                           module + ".pot")
            # Create i18n/ directory if doesn't exist
            if not os.path.exists(os.path.dirname(source_filename)):
                os.makedirs(os.path.dirname(source_filename))
            with open(source_filename, 'w') as f:
                f.write(odoo_context.get_pot_contents(module))

            print
            print "Linking PO file and Transifex resource"
            set_args = ['-t', 'PO',
                        '--auto-local',
                        '-r', '%s.%s' % (project_shortcut, module),
                        '%s/i18n/<lang>.po' % module,
                        '--source-lang', 'en',
                        '--source-file', source_filename,
                        '--execute']
            commands.cmd_set(set_args, path_to_tx)

    print
    print 'Pushing translation files to Transifex'
    push_args = ['-s', '-t', '--skip']
    commands.cmd_push(push_args, path_to_tx)

    return 0


if __name__ == "__main__":
    exit(main())
