# -*- encoding: utf-8 -*-
##############################################################################
#
#    Odoo, Open Source Management Solution
#    Copyright (C) 2010-2015 Eezee-It (<http://www.eezee-it.com>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from openerp.addons.runbot_multiple_hosting.models import hosting
import requests


class BitBucketHosting(hosting.Hosting):
    API_URL = 'https://bitbucket.org/api/2.0'
    URL = 'https://bitbucket.org'
    token = (())

    def __init__(self, credentials):
        response = requests.post(self.URL + '/site/oauth2/access_token',
                                 auth=credentials,
                                 data={'grant_type': 'client_credentials'})
        self.token = response.json().get('access_token')
        super(BitBucketHosting, self).__init__()

    @classmethod
    def get_branch_url(cls, owner, repository, branch):
        return cls.get_url('/%s/%s/branch/%s', owner, repository, branch)

    @classmethod
    def get_pull_request_url(cls, owner, repository, pull_number):
        return cls.get_url('/%s/%s/pull-request/%s', owner, repository,
                           pull_number)

    def get_pull_request(self, owner, repository, pull_number):
        url = self.get_api_url('/repositories/%s/%s/pullrequests/%s' % (
        owner, repository, pull_number))
        reponse = self.session.get('%s?access_token=%s' % (url, self.token))
        return reponse.json()
