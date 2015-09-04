# -*- encoding: utf-8 -*-
##############################################################################
#
#    Author: Sylvain VanHoof
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

from openerp.addons.runbot.runbot import RunbotController


class InheritRunbotController(RunbotController):

    @http.route()
    def repo(self, repo=None, search='', limit='100', refresh='', **post):
        result = super(InheritRunbotController, self).repo(repo=repo, search=search, limit=limit, refresh=refresh, **post)

        registry, cr, uid = request.registry, request.cr, request.uid
        repo_obj = registry['runbot.repo']
        repo_ids = repo_obj.search(cr, uid, [('visible', '=', True)])
        repos = repo_obj.browse(cr, uid, repo_ids)

        result.qcontext['repos'] = repos

        return result