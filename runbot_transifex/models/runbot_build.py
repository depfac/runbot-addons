# -*- encoding: utf-8 -*-
##############################################################################
#
#    Author: Sylvain Van Hoof, Samuel Lefever
#    Odoo, Open Source Management Solution
#    Copyright (C) 2010-2015 Eezee-It (<http://www.eezee-it.com>).
#    Copyright 2015 Niboo (<http://www.niboo.be>).
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
import logging
import re

import openerp
from openerp import models, api

from ..push_to_transifex import runbot_transifex

_logger = logging.getLogger(__name__)


class RunbotBuild(models.Model):
    _inherit = 'runbot.build'

    @api.model
    def job_22_pull_translation_from_transifex(self, build, lock_path, log_path):
        return 0

    @api.model
    def job_99_push_translation_to_transifex(self, build, lock_path, log_path):
        repo = build.repo_id
        branch = build.branch_id

        if not repo.is_transifex_project or branch not in repo.branch_triggered_ids:
            return 0

        _logger.info('Start pushing translations for project %s' % repo.project_name)

        cmd, mods = build.cmd()
        transifex_login = self.env['ir.config_parameter'].get_param('runbot_transifex.transifex_login')
        transifex_password = self.env['ir.config_parameter'].get_param('runbot_transifex.transifex_password')
        addons = openerp.tools.ustr(mods)
        db_name = "%s-all" % build.dest
        server_path = build.path("openerp-server")
        addons_path = build.server('addons')

        _logger.info('Login: %s - Password: %s - Addons: %s, DB Name: %s - Server path: %s - Addons path: %s' %
                     (transifex_login, re.sub(r'.', '*', transifex_password), addons, db_name, server_path, addons_path))
        return runbot_transifex(transifex_login, transifex_password, addons, db_name, server_path, addons_path)
