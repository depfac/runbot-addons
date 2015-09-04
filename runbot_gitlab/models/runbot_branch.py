# -*- encoding: utf-8 -*-
##############################################################################
#
#    Odoo, Open Source Management Solution
#    This module copyright (C) 2010 Savoir-faire Linux
#    (<http://www.savoirfairelinux.com>).
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
from openerp import models, fields, api

def gitlab_api(func):
    """Decorator for functions which should be overwritten only if
    uses_gitlab is enabled in repo.
    """
    def gitlab_func(self, *args, **kwargs):
        if self.repo_id.hosting == 'gitlab':
            return func(self, *args, **kwargs)
        else:
            regular_func = getattr(super(RunbotBranch, self), func.func_name)
            return regular_func(*args, **kwargs)
    return gitlab_func


class RunbotBranch(models.Model):
    _inherit = "runbot.branch"
    project_id = fields.Integer('VCS Project', select=1)
    merge_request_id = fields.Integer('Merge Request', select=1)

    @api.multi
    @gitlab_api
    def is_pull_request(self):
        self.ensure_one()

        if self.merge_request_id:
            return True
        return False

    @api.multi
    @gitlab_api
    def get_pull_request_url(self, owner, repository, branch):
        self.ensure_one()

        return "https://%s/merge_requests/%s" % (self.repo_id.base, self.merge_request_id)

    @api.multi
    @gitlab_api
    def get_branch_url(self, owner, repository, pull_number):
        self.ensure_one()

        return "https://%s/tree/%s" % (self.repo_id.base, self.branch_name)

    @api.multi
    @gitlab_api
    def _get_pull_info(self):
        self.ensure_one()
        repo = self.repo_id
        if repo.token and repo.name.startswith('refs/pull/'):
            pull_number = repo.name[len('refs/pull/'):]
            return repo.github('/repos/:owner/:repo/pulls/%s' % pull_number, ignore_errors=True) or {}

        return {}