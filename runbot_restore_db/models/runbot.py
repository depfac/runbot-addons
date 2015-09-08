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
import os
import time

import openerp
from openerp import models, fields, api
from openerp.exceptions import Warning

from openerp.addons.runbot import runbot
from openerp.addons.runbot.runbot import log, dashes, mkdirs, grep, rfind, \
    lock, locked, nowait, run, now, dt2time, s2human, flatten, \
    decode_utf, uniq_list, fqdn
from openerp.addons.runbot.runbot import _re_error, _re_warning, \
    _re_job, _logger

loglevels = (('none', 'None'),
             ('warning', 'Warning'),
             ('error', 'Error'))


class RunbotBuild(models.Model):
    _inherit = "runbot.build"

    @api.model
    def job_25_restore(self, build, lock_path, log_path):
        if not build.repo_id.db_name:
            return 0
        cmd = "createdb -T %s %s-all" % (build.repo_id.db_name, build.dest)
        return self.spawn(cmd, lock_path, log_path, cpu_limit=None, shell=True)

    @api.model
    def job_26_upgrade(self, build, lock_path, log_path):
        if not build.repo_id.db_name:
            return 0
        to_test = build.repo_id.modules if build.repo_id.modules else 'all'
        cmd, mods = build.cmd()
        cmd += ['-d', '%s-all' % build.dest, '-u', to_test, '--stop-after-init',
                '--log-level=debug', '--test-enable']
        return self.spawn(cmd, lock_path, log_path, cpu_limit=None)

    @api.model
    def job_30_run(self, build, lock_path, log_path):
        if build.repo_id.db_name and build.state == 'running' \
                and build.result == "ko":
            return 0
        runbot._re_error = self._get_regexeforlog(build=build, errlevel='error')
        runbot._re_warning = self._get_regexeforlog(build=build,
                                                    errlevel='warning')

        build._log('run', 'Start running build %s' % build.dest)

        v = {}
        result = "ok"
        log_names = [elmt.name for elmt in build.repo_id.parse_job_ids]
        for log_name in log_names:
            log_all = build.path('logs', log_name + '.txt')
            if grep(log_all, ".modules.loading: Modules loaded."):
                if rfind(log_all, _re_error):
                    result = "ko"
                    break;
                elif rfind(log_all, _re_warning):
                    result = "warn"
                elif not grep(build.server("test/common.py"),
                              "post_install") or grep(log_all,
                                                      "Initiating shutdown."):
                    if result != "warn":
                        result = "ok"
            else:
                result = "ko"
                break;
            log_time = time.localtime(os.path.getmtime(log_all))
            v['job_end'] = time.strftime(
                openerp.tools.DEFAULT_SERVER_DATETIME_FORMAT, log_time)
        v['result'] = result
        build.write(v)
        build.github_status()

        # run server
        cmd, mods = build.cmd()
        if os.path.exists(build.server('addons/im_livechat')):
            cmd += ["--workers", "2"]
            cmd += ["--longpolling-port", "%d" % (build.port + 1)]
            cmd += ["--max-cron-threads", "1"]
        else:
            # not sure, to avoid old server to check other dbs
            cmd += ["--max-cron-threads", "0"]

        cmd += ['-d', "%s-all" % build.dest]

        if grep(build.server("tools/config.py"), "db-filter"):
            if build.repo_id.nginx:
                cmd += ['--db-filter', '%d.*$']
            else:
                cmd += ['--db-filter', '%s.*$' % build.dest]

        return self.spawn(cmd, lock_path, log_path, cpu_limit=None)

    def _get_regexeforlog(self, build, errlevel):
        addederror = False
        regex = r'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3} \d+ '
        if build.repo_id.error == errlevel:
            if addederror:
                regex += "|"
            else:
                addederror = True
            regex += "(ERROR)"
        if build.repo_id.critical == errlevel:
            if addederror:
                regex += "|"
            else:
                addederror = True
            regex += "(CRITICAL)"
        if build.repo_id.warning == errlevel:
            if addederror:
                regex += "|"
            else:
                addederror = True
            regex += "(WARNING)"
        if build.repo_id.failed == errlevel:
            if addederror:
                regex += "|"
            else:
                addederror = True
            regex += "(TEST.*FAIL)"
        if build.repo_id.traceback == errlevel:
            if addederror:
                regex = '(Traceback \(most recent call last\))|(%s)' % regex
            else:
                regex = '(Traceback \(most recent call last\))'
        # regex = '^' + regex + '$'
        return regex

    @api.multi
    def schedule(self):
        """
        /!\ must rewrite the all method because for each build we need
            to remove jobs that were specified as skipped in the repo.
        """
        all_jobs = self.list_jobs()
        icp = self.env['ir.config_parameter']
        default_timeout = int(
            icp.get_param('runbot.timeout', default=1800)) / 60

        for build in self:
            # remove skipped jobs
            jobs = all_jobs[:]
            for job_to_skip in build.repo_id.skip_job_ids:
                jobs.remove(job_to_skip.name)
            if build.state == 'pending':
                # allocate port and schedule first job
                port = self.find_port()
                values = {
                    'host': fqdn(),
                    'port': port,
                    'state': 'testing',
                    'job': jobs[0],
                    'job_start': now(),
                    'job_end': False,
                }
                build.write(values)
                self.env.cr.commit()
            else:
                # check if current job is finished
                lock_path = build.path('logs', '%s.lock' % build.job)
                if locked(lock_path):
                    # kill if overpassed
                    timeout = (
                              build.branch_id.job_timeout
                              or default_timeout) * 60
                    if build.job != jobs[-1] and build.job_time > timeout:
                        build.logger('%s time exceded (%ss)', build.job,
                                     build.job_time)
                        build.kill(result='killed')
                    continue
                build.logger('%s finished', build.job)
                # schedule
                v = {}
                # testing -> running
                if build.job == jobs[-2]:
                    v['state'] = 'running'
                    v['job'] = jobs[-1]
                    v['job_end'] = now(),
                # running -> done
                elif build.job == jobs[-1]:
                    v['state'] = 'done'
                    v['job'] = ''
                # testing
                else:
                    v['job'] = jobs[jobs.index(build.job) + 1]
                build.write(v)
            build.refresh()

            # run job
            pid = None
            if build.state != 'done':
                build.logger('running %s', build.job)
                job_method = getattr(self, build.job)
                mkdirs([build.path('logs')])
                lock_path = build.path('logs', '%s.lock' % build.job)
                log_path = build.path('logs', '%s.txt' % build.job)
                pid = job_method(build, lock_path, log_path)
                build.write({'pid': pid})
            # needed to prevent losing pids if multiple jobs are started
            # and one them raise an exception
            self.env.cr.commit()

            if pid == -2:
                # no process to wait, directly call next job
                # FIXME find a better way that this recursive call
                build.schedule()

            # cleanup only needed if it was not killed
            if build.state == 'done':
                build.cleanup()


class RunbotJob(models.Model):
    _name = "runbot.job"

    name = fields.Char("Job name")


class RunbotRepo(models.Model):
    _inherit = "runbot.repo"

    @api.model
    def cron_update_job(self):
        build_obj = self.env['runbot.build']
        jobs = build_obj.list_jobs()
        job_obj = self.env['runbot.job']
        for job_name in jobs:
            job = job_obj.search([('name', '=', job_name)])
            if not job:
                job_obj.create({'name': job_name})
        job_to_rm = job_obj.sudo().search([('name', 'not in', jobs)])
        job_to_rm.unlink()
        return True

    db_name = fields.Char("Database name to replicate")
    sequence = fields.Integer('Sequence of display', select=True)
    error = fields.Selection(loglevels, 'Error messages', default='error')
    critical = fields.Selection(loglevels, 'Critical messages', default='error')
    traceback = fields.Selection(loglevels, 'Traceback messages',
                                 default='error')
    warning = fields.Selection(loglevels, 'Warning messages', default='warning')
    failed = fields.Selection(loglevels, 'Failed messages', default='none')
    skip_job_ids = fields.Many2many('runbot.job', string='Jobs to skip')
    parse_job_ids = fields.Many2many('runbot.job', "repo_parse_job_rel",
                                     string='Jobs to parse')

    @api.onchange('db_name')
    @api.constrains('db_name')
    @api.one
    def onchange_db_name(self):
        if not self.db_name:
            return
        try:
            db = openerp.sql_db.db_connect(self.db_name)
            db_cursor = db.cursor()
        except:
            raise Warning('The database "%s" doesn\'t exist' % self.db_name)
        db_cursor.close()

    _order = 'sequence'


class RunbotControllerPS(runbot.RunbotController):
    def build_info(self, build):
        res = super(RunbotControllerPS, self).build_info(build)
        res['parse_job_ids'] = [elmt.name for elmt in
                                build.repo_id.parse_job_ids]
        return res
