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
import os
import time
import logging

from openerp import SUPERUSER_ID
from openerp import models, api, fields, tools

from openerp.addons.runbot.runbot import RunbotController

_logger = logging.getLogger(__name__)


def grep(filename, string):
    if os.path.isfile(filename):
        return open(filename).read().find(string) != -1
    return False


def now():
    return time.strftime(tools.DEFAULT_SERVER_DATETIME_FORMAT)


class RunbotRepo(models.Model):
    _inherit = 'runbot.repo'

    install_chart_account = fields.Boolean('Install the chart account', default=True,
                                    help="Install the chart account according the country of the company")

a
class RunbotBuild(models.Model):
    _inherit = "runbot.build"

    disable_base_log = fields.Boolean('Disable Base Log')

    def job_10_test_base(self, cr, uid, build, lock_path, log_path):
        """
        According to the Runbot Settings, this method will disable or not the job 10
        """
        disable_job = self.pool.get('ir.config_parameter').get_param(cr, uid, 'runbot.disable_job_10', default='True')
        if disable_job == 'True':
            _logger.info('Job 10 disable')
            self.write(cr, SUPERUSER_ID, build.id, {'disable_base_log': True})
            build.checkout()
            return
        _logger.info('Job 10 enable')
        super(RunbotBuild, self).job_10_test_base(cr, uid, build, lock_path, log_path)

    def job_15_install_all(self, cr, uid, build, lock_path, log_path):
        """
        This job will create the database "full" and install modules WITHOUT demo data.
        Any tests wil be executed
        """
        build._log('install_all', 'Start install all modules')
        self.pg_createdb(cr, uid, "%s-all" % build.dest)
        cmd, mods = build.cmd()
        if grep(build.server("tools/config.py"), "test-enable"):
            cmd.append("--test-enable")
        cmd += ['-d', '%s-all' % build.dest, '-i', mods, '--without-demo=all', '--stop-after-init', '--log-level=test', '--max-cron-threads=0']
        # reset job_start to an accurate job_20 job_time
        build.write({'job_start': now()})
        return self.spawn(cmd, lock_path, log_path, cpu_limit=2100)

    def job_20_test_all(self, cr, uid, build, lock_path, log_path):
        """
        This job will install all demo data of specified modules.
        Moreover, this job will execute tests from specified modules.
        """
        build._log('test_all', 'Start test all modules')
        cmd, mods = build.cmd()
        if grep(build.server("tools/config.py"), "test-enable"):
            cmd.append("--test-enable")
        cmd += ['-d', '%s-all' % build.dest, '-i', mods, '--stop-after-init', '--log-level=test', '--max-cron-threads=0']
        # reset job_start to an accurate job_20 job_time
        build.write({'job_start': now()})
        return self.spawn(cmd, lock_path, log_path, cpu_limit=2100)


class Controller(RunbotController):
    def build_info(self, build):
        """
        Add the value 'disable_base_log' in result. Use in the view build to show or hide the "Base Log" menu entry
        """
        real_build = build.duplicate_id if build.state == 'duplicate' else build

        result = super(Controller, self).build_info(build)
        result['disable_base_log'] = real_build.disable_base_log

        return result
