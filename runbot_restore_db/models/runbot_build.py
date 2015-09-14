# -*- encoding: utf-8 -*-
##############################################################################
#
#    Author: Sylvain Van Hoof
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
import traceback
import logging
import openerp
from openerp import models, api

_logger = logging.getLogger(__name__)


class RunbotBuild(models.Model):
    _inherit = "runbot.build"

    @api.model
    def job_16_restore(self, build, lock_path, log_path):
        if not build.repo_id.db_name:
            return 0
        cmd = "createdb -T %s %s-all" % (build.repo_id.db_name, build.dest)
        return self.spawn(cmd, lock_path, log_path, cpu_limit=None, shell=True)

    @api.model
    def job_25_upgrade(self, build, lock_path, log_path):
        if not build.repo_id.db_name:
            return 0
        old_password = build._set_admin_password()
        to_test = build.repo_id.modules if build.repo_id.modules else 'all'
        cmd, mods = build.cmd()
        cmd += ['-d', '%s-all' % build.dest, '-u', to_test, '--stop-after-init',
                '--test-enable']
        return self.spawn(cmd, lock_path, log_path, cpu_limit=None)

    @api.model
    def job_26_reset_password(self, build, lock_path, log_path):
        if not build.repo_id.db_name:
            return 0
        build._set_admin_password('')
        return 1

    @api.model
    def _set_admin_password(self, password='admin'):
        db = openerp.sql_db.db_connect('%s-all' % self.dest)
        # threading.current_thread().dbname = '%s-all' % build.dest
        build_cr = db.cursor()
        old_password = False

        try:
            build_cr.execute("SELECT password FROM res_users WHERE id = 1")
            old_password = build_cr.fetchone()
            build_cr.execute("UPDATE res_users SET password = '%s' \
WHERE id = 1" % password)
            build_cr.commit()
        except:
           _logger.error("Error during password set:\n %s" % traceback.format_exc())
           self.write({'result': 'ko', 'state': 'done'})
           pass

        # Close and restore the new cursor
        build_cr.close()
        return old_password
