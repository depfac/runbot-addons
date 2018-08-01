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
from odoo import http

from odoo.http import request

from odoo.addons.runbot.common import uniq_list, flatten
from odoo.addons.runbot.controllers.frontend import Runbot
from odoo.addons.http_routing.models.ir_http import slug
from odoo.addons.website_sale.controllers.main import QueryURL


class InheritRunbotController(Runbot):

    @http.route(['/runbot', '/runbot/repo/<model("runbot.repo"):repo>'], website=True, auth='public', type='http')
    def repo(self, repo=None, search='', limit='100', refresh='', **kwargs):
        branch_obj = request.env['runbot.branch']
        build_obj = request.env['runbot.build']
        repo_obj = request.env['runbot.repo']

        repo_ids = repo_obj.search([('visible', '=', True)])
        repos = repo_obj.browse(repo_ids)
        if not repo and repos:
            repo = repos[0].id

        pending = self._pending()
        context = {
            'repos': repos.ids,
            'repo': repo,
            'host_stats': [],
            'pending_total': pending[0],
            'pending_level': pending[1],
            'limit': limit,
            'search': search,
            'refresh': refresh,
        }

        build_ids = []
        if repo:
            filters = {key: kwargs.get(key, '1') for key in ['pending', 'testing', 'running', 'done', 'deathrow']}
            domain = [('repo_id', '=', repo.id)]
            domain += [('state', '!=', key) for key, value in iter(filters.items()) if value == '0']
            if search:
                domain += ['|', '|', ('dest', 'ilike', search), ('subject', 'ilike', search),
                           ('branch_id.branch_name', 'ilike', search)]

            build_ids = build_obj.search(domain, limit=int(limit))
            branch_ids, build_by_branch_ids = [], {}

            if build_ids:
                branch_query = """
                    SELECT br.id FROM runbot_branch br INNER JOIN runbot_build bu ON br.id=bu.branch_id WHERE bu.id in %s
                    ORDER BY bu.sequence DESC
                    """
                sticky_dom = [('repo_id', '=', repo.id), ('sticky', '=', True)]
                sticky_branch_ids = [] if search else branch_obj.search(sticky_dom).ids
                request._cr.execute(branch_query, (tuple(build_ids.ids),))
                branch_ids = uniq_list(sticky_branch_ids + [br[0] for br in request._cr.fetchall()])

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
                request._cr.execute(build_query, (tuple(branch_ids),))
                build_by_branch_ids = {
                    rec[0]: [r for r in rec[1:] if r is not None] for rec in request._cr.fetchall()
                }

            branches = branch_obj.browse(branch_ids)
            build_ids = flatten(build_by_branch_ids.values())
            build_dict = {build.id: build for build in build_obj.browse(build_ids)}

            def branch_info(branch):
                return {
                    'branch': branch,
                    'builds': [self.build_info(build_dict[build_id]) for build_id in
                               build_by_branch_ids.get(branch.id) or []]
                }

            context.update({
                'branches': [branch_info(b) for b in branches],
                'testing': build_obj.search_count([('repo_id', '=', repo.id), ('state', '=', 'testing')]),
                'running': build_obj.search_count([('repo_id', '=', repo.id), ('state', '=', 'running')]),
                'pending': build_obj.search_count([('repo_id', '=', repo.id), ('state', '=', 'pending')]),
                'qu': QueryURL('/runbot/repo/' + slug(repo), search=search, limit=limit, refresh=refresh, **filters),
                'filters': filters,
            })

        # consider host gone if no build in last 100
        build_threshold = max(build_ids or [0]) - 100

        for result in build_obj.read_group([('id', '>', build_threshold)], ['host'], ['host']):
            if result['host']:
                context['host_stats'].append({
                    'host': result['host'],
                    'testing': build_obj.search_count([('state', '=', 'testing'), ('host', '=', result['host'])]),
                    'running': build_obj.search_count([('state', '=', 'running'), ('host', '=', result['host'])]),
                })
        return http.request.render('runbot.repo', context)
