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
from odoo import models, api, fields
from odoo.addons.runbot.common import dt2time, fqdn, now, locked, grep, time2str, rfind, uniq_list, local_pgadmin_cursor, lock, get_py_version
import logging
import re

_re_error = r'^(?:\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3} \d+ (?:ERROR|CRITICAL) )|(?:Traceback \(most recent call last\):)$'
_re_warning = r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d{3} \d+ WARNING '
re_job = re.compile('_job_\d')

_logger = logging.getLogger(__name__)

class RunbotBuild(models.Model):
    _inherit = "runbot.build"

    def _get_closest_branch_name(self, target_repo_id):
        """Return (repo, branch name) of the closest common branch between build's branch and
           any branch of target_repo or its duplicated repos.

        Rules priority for choosing the branch from the other repo is:
        1. Same branch name
        2. A PR whose head name match
        3. Match a branch which is the dashed-prefix of current branch name
        4. Common ancestors (git merge-base)
        Note that PR numbers are replaced by the branch name of the PR target
        to prevent the above rules to mistakenly link PR of different repos together.
        """
        self.ensure_one()
        return target_repo_id, '10.0', 'default'

    def _job_30_run(self, build, lock_path, log_path):
        v = {
        }
        result = "ok"
        build._log('run', 'Start running build %s' % build.dest)
        log_names = [elmt.name for elmt in build.repo_id.parse_job_ids]
        for log_name in log_names:
            log_all = build._path('logs', log_name + '.txt')
            log_time = time.localtime(os.path.getmtime(log_all))
            v['job_end'] = time2str(log_time)

            if grep(log_all, ".modules.loading: Modules loaded."):
                if rfind(log_all, _re_error):
                    result = "ko"
                elif rfind(log_all, _re_warning):
                    result = "warn"
                elif not grep(build._server("test/common.py"), "post_install") or grep(log_all, "Initiating shutdown."):
                    result = "ok"
            else:
                result = "ko"

        v['result'] = result
        build.write(v)
        # post statuses on duplicate too
        for b in self.search([('name', '=', build.name)]):
            b._github_status()
        # run server
        cmd, mods = build._cmd()
        if os.path.exists(build._server('addons/im_livechat')):
            cmd += ["--workers", "2"]
            cmd += ["--longpolling-port", "%d" % (build.port + 1)]
            cmd += ["--max-cron-threads", "1"]
        else:
            # not sure, to avoid old server to check other dbs
            cmd += ["--max-cron-threads", "0"]

        cmd += ['-d', "%s-all" % build.dest]

        if grep(build._server("tools/config.py"), "db-filter"):
            if build.repo_id.nginx:
                cmd += ['--db-filter', '%d.*$' % build.dest]
            else:
                cmd += ['--db-filter', '%s.*$' % build.dest]
        return self._spawn(cmd, lock_path, log_path, cpu_limit=None)

    def _schedule(self):
        """schedule the build"""
        all_jobs = self._list_jobs()

        icp = self.env['ir.config_parameter']
        # For retro-compatibility, keep this parameter in seconds
        default_timeout = int(icp.get_param('runbot.runbot_timeout', default=1800)) / 60

        for build in self:
            jobs = all_jobs[:]
            for job_to_skip in build.repo_id.skip_job_ids:
                jobs.remove(job_to_skip.name)
            if build.state == 'deathrow':
                build._kill(result='manually_killed')
                continue
            elif build.state == 'pending':
                # allocate port and schedule first job
                port = self._find_port()
                values = {
                    'host': fqdn(),
                    'port': port,
                    'state': 'testing',
                    'job': jobs[0],
                    'job_start': now(),
                    'job_end': False,
                }
                build.write(values)
            else:
                # check if current job is finished
                lock_path = build._path('logs', '%s.lock' % build.job)
                if locked(lock_path):
                    # kill if overpassed
                    timeout = (build.branch_id.job_timeout or default_timeout) * 60 * ( build.coverage and 1.5 or 1)
                    if build.job != jobs[-1] and build.job_time > timeout:
                        build._logger('%s time exceded (%ss)', build.job, build.job_time)
                        build.write({'job_end': now()})
                        build._kill(result='killed')
                    continue
                build._logger('%s finished', build.job)
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

            # run job
            pid = None
            if build.state != 'done':
                build._logger('running %s', build.job)
                job_method = getattr(self, '_' + build.job)  # compute the job method to run
                os.makedirs(build._path('logs'), exist_ok=True)
                lock_path = build._path('logs', '%s.lock' % build.job)
                log_path = build._path('logs', '%s.txt' % build.job)
                try:
                    pid = job_method(build, lock_path, log_path)
                    build.write({'pid': pid})
                except Exception:
                    _logger.exception('%s failed running method %s', build.dest, build.job)
                    build._log(build.job, "failed running job method, see runbot log")
                    build._kill(result='ko')
                    continue
            # needed to prevent losing pids if multiple jobs are started and one them raise an exception
            self.env.cr.commit()

            if pid == -2:
                # no process to wait, directly call next job
                # FIXME find a better way that this recursive call
                build._schedule()

            # cleanup only needed if it was not killed
            if build.state == 'done':
                build._local_cleanup()
