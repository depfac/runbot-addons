# -*- encoding: utf-8 -*-
##############################################################################
#
#    Odoo, Open Source Management Solution
#    Copyright (C) 2017 dFakto
#    http://www.dfakto.com
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
from openerp import models, api

import re


class RunbotBuild(models.Model):
    _inherit = "runbot.build"

    @api.model
    def create(self, vals):
        if self._should_build_branch(vals):
            return super(RunbotBuild, self).create(vals)
        else:
            return self.browse()

    def _should_build_branch(self, vals):
        branch = self.env['runbot.branch'].browse(vals['branch_id'])
        repo = branch.repo_id
        if repo.branch_filters:
            patterns = repo.branch_filters.split(';')
            if not any(re.match('^%s$' % pattern, branch.name.split('/')[-1]) for pattern in patterns):
                return False
        return True
