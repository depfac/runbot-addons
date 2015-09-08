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
from openerp import http

from openerp.http import request

from openerp.addons.runbot.runbot import RunbotController, uniq_list, flatten
from openerp.addons.website.models.website import slug
from openerp.addons.website_sale.controllers.main import QueryURL


class InheritRunbotController(RunbotController):

    @http.route()
    def repo(self, repo=None, search='', limit='100', refresh='', **post):
        registry, cr, uid = request.registry, request.cr, request.uid

        branch_obj = registry['runbot.branch']
        build_obj = registry['runbot.build']
        icp = registry['ir.config_parameter']
        repo_obj = registry['runbot.repo']
        count = lambda dom: build_obj.search_count(cr, uid, dom)

        repo_ids = repo_obj.search(cr, uid, [('visible', '=', True)])
        repos = repo_obj.browse(cr, uid, repo_ids)
        if not repo and repos:
            repo = repos[0]

        context = {
            'repos': repos,
            'repo': repo,
            'host_stats': [],
            'pending_total': count([('state','=','pending')]),
            'limit': limit,
            'search': search,
            'refresh': refresh,
        }

        if repo:
            filters = {key: post.get(key, '1') for key in ['pending', 'testing', 'running', 'done']}
            domain = [('repo_id','=',repo.id)]
            domain += [('state', '!=', key) for key, value in filters.iteritems() if value == '0']
            if search:
                domain += ['|', '|', ('dest', 'ilike', search), ('subject', 'ilike', search), ('branch_id.branch_name', 'ilike', search)]

            build_ids = build_obj.search(cr, uid, domain, limit=int(limit))
            branch_ids, build_by_branch_ids = [], {}

            if build_ids:
                branch_query = """
                SELECT br.id FROM runbot_branch br INNER JOIN runbot_build bu ON br.id=bu.branch_id WHERE bu.id in %s
                ORDER BY bu.sequence DESC
                """
                sticky_dom = [('repo_id','=',repo.id), ('sticky', '=', True)]
                sticky_branch_ids = [] if search else branch_obj.search(cr, uid, sticky_dom)
                cr.execute(branch_query, (tuple(build_ids),))
                branch_ids = uniq_list(sticky_branch_ids + [br[0] for br in cr.fetchall()])

                build_query = """
                    SELECT
                        branch_id,
                        max(case when br_bu.row = 1 then br_bu.build_id end),
                        max(case when br_bu.row = 2 then br_bu.build_id end),
                        max(case when br_bu.row = 3 then br_bu.build_id end),
                        max(case when br_bu.row = 4 then br_bu.build_id end)
                    FROM (
                        SELECT
                            br.id AS branch_id,
                            bu.id AS build_id,
                            row_number() OVER (PARTITION BY branch_id) AS row
                        FROM
                            runbot_branch br INNER JOIN runbot_build bu ON br.id=bu.branch_id
                        WHERE
                            br.id in %s
                        GROUP BY br.id, bu.id
                        ORDER BY br.id, bu.id DESC
                    ) AS br_bu
                    WHERE
                        row <= 4
                    GROUP BY br_bu.branch_id;
                """
                cr.execute(build_query, (tuple(branch_ids),))
                build_by_branch_ids = {
                    rec[0]: [r for r in rec[1:] if r is not None] for rec in cr.fetchall()
                }

            branches = branch_obj.browse(cr, uid, branch_ids, context=request.context)
            build_ids = flatten(build_by_branch_ids.values())
            build_dict = {build.id: build for build in build_obj.browse(cr, uid, build_ids, context=request.context) }

            def branch_info(branch):
                return {
                    'branch': branch,
                    'builds': [self.build_info(build_dict[build_id]) for build_id in build_by_branch_ids[branch.id]]
                }

            context.update({
                'branches': [branch_info(b) for b in branches],
                'testing': count([('repo_id','=',repo.id), ('state','=','testing')]),
                'running': count([('repo_id','=',repo.id), ('state','=','running')]),
                'pending': count([('repo_id','=',repo.id), ('state','=','pending')]),
                'qu': QueryURL('/runbot/repo/'+slug(repo), search=search, limit=limit, refresh=refresh, **filters),
                'filters': filters,
            })

        for result in build_obj.read_group(cr, uid, [], ['host'], ['host']):
            if result['host']:
                context['host_stats'].append({
                    'host': result['host'],
                    'testing': count([('state', '=', 'testing'), ('host', '=', result['host'])]),
                    'running': count([('state', '=', 'running'), ('host', '=', result['host'])]),
                })

        return request.render("runbot.repo", context)