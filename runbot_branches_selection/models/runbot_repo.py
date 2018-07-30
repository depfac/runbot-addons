# -*- encoding: utf-8 -*-
##############################################################################
#
#    Odoo, Open Source Management Solution
#    Copyright (C) 2017 dFakto
#    http://www.dfakto.com
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
from odoo import models, fields


class RunbotRepo(models.Model):
    _inherit = "runbot.repo"
    _rec_name = 'label'

    branch_filters = fields.Char(name='Branches to build',
                                 help='Regular expressions of names of branches to build, separated by semi-colons')
    label = fields.Char(string='Repo name')
    name = fields.Char(string='URL')
