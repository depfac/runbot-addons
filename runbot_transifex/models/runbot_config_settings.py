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
from openerp import models, fields, api


class RunbotConfigSettings(models.Model):
    _inherit = 'runbot.config.settings'

    transifex_login = fields.Char('Transifex Login', required=True,
                      default=lambda self: self.env['ir.config_parameter'].get_param('runbot_transifex.transifex_login'))
    transifex_password = fields.Char('Transifex Password', required=True,
                      default=lambda self: self.env['ir.config_parameter'].get_param('runbot_transifex.transifex_password'))

    @api.multi
    def set_transifex_login(self):
        self.env['ir.config_parameter'].set_param('runbot_transifex.transifex_login', self.transifex_login)

    @api.multi
    def set_transifex_password(self):
        self.env['ir.config_parameter'].set_param('runbot_transifex.transifex_password', self.transifex_password)
