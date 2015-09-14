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
from openerp import models, api
from openerp.addons.runbot import runbot


class RunbotBuild(models.Model):
    _inherit = "runbot.build"

    @api.model
    def job_30_run(self, build, lock_path, log_path):
        """
        Redefine this job to avoid ERROR on empty logs like db restore
        :param build:
        :param lock_path:
        :param log_path:
        :return:
        """
        # if build.repo_id.db_name and build.state == 'running' \
        #         and build.result == "ko":
        #     return 0

        # parse logs (only ones that have been chosen)
        runbot._re_error = r'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3} \d+ (ERROR)'
        runbot._re_warning = r'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3} \d+ (WARNING)'

        v = {}
        result = "ok"
        log_names = [elmt.name for elmt in build.repo_id.parse_job_ids]
        for log_name in log_names:
            log_all = build.path('logs', log_name + '.txt')
            if runbot.grep(log_all, ".modules.loading: Modules loaded."):
                if runbot.rfind(log_all, runbot._re_error):
                    result = "ko"
                    break;
                elif runbot.rfind(log_all, runbot._re_warning):
                    result = "warn"
                elif not runbot.grep(build.server("test/common.py"),
                              "post_install") or runbot.grep(log_all,
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
        build._log('run', 'Start running build %s' % build.dest)
        cmd, mods = build.cmd()
        if os.path.exists(build.server('addons/im_livechat')):
            cmd += ["--workers", "2"]
            cmd += ["--longpolling-port", "%d" % (build.port + 1)]
            cmd += ["--max-cron-threads", "1"]
        else:
            # not sure, to avoid old server to check other dbs
            cmd += ["--max-cron-threads", "0"]

        cmd += ['-d', "%s-all" % build.dest]

        if runbot.grep(build.server("tools/config.py"), "db-filter"):
            if build.repo_id.nginx:
                cmd += ['--db-filter', '%d.*$']
            else:
                cmd += ['--db-filter', '%s.*$' % build.dest]

        return self.spawn(cmd, lock_path, log_path, cpu_limit=None)

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
                    'host': runbot.fqdn(),
                    'port': port,
                    'state': 'testing',
                    'job': jobs[0],
                    'job_start': runbot.now(),
                    'job_end': False,
                }
                build.write(values)
                self.env.cr.commit()
            else:
                # check if current job is finished
                lock_path = build.path('logs', '%s.lock' % build.job)
                if runbot.locked(lock_path):
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
                    v['job_end'] = runbot.now(),
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
                runbot.mkdirs([build.path('logs')])
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
