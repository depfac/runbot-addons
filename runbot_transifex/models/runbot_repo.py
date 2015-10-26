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
from openerp import models, api, fields


class RunbotRepo(models.Model):
    _inherit = 'runbot.repo'

    is_transifex_project = fields.Boolean('Use Transifex to manage translations', default=False)
    branch_triggered_ids = fields.Many2many('runbot.branch', string='Branches to trigger',
                                           help="For each builds of following branches, the system will update translations")
    project_name = fields.Char('Project Name')
    project_shortcut = fields.Char('Project Shorcut')
    project_organization = fields.Char('Project Organization')
