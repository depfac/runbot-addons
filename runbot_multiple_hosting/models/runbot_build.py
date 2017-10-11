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
import os
import glob
import shutil
from openerp import models, api
from openerp.addons.runbot import runbot

import logging

_logger = logging.getLogger(__name__)


class RunbotBuild(models.Model):
    _inherit = "runbot.build"

    @api.multi
    def _server(self, *l, **kw):
        for build in self:
            return build._path(build.repo_id.server_dir, *l)

    @api.multi
    def _checkout(self):
        result = super(RunbotBuild, self)._checkout()
        for build in self:
            for extra_repo in build.repo_id.dependency_nested_ids:
                extra_repo.repo_dst_id._git_export(
                    extra_repo.reference, build._path())

            modules_to_move = [
                os.path.dirname(module)
                for module in (glob.glob(build._path('*/__openerp__.py')) +
                               glob.glob(build._path('*/__manifest__.py')))
            ]

            for module in runbot.uniq_list(modules_to_move):
                basename = os.path.basename(module)
                if os.path.exists(build._server('addons', basename)):
                    build._log(
                        'Building environment',
                        'You have duplicate modules in your branches "%s"' %
                        basename
                    )
                    shutil.rmtree(build._server('addons', basename))
                shutil.move(module, build._server('addons'))

        return result

    @api.multi
    def github_status(self):
        """
        By default, we disable this feature.
        This method should be call only for github repo
        :return:
        """
        return
