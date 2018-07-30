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

from odoo import models, fields, api
from odoo.sql_db import db_connect
from odoo.exceptions import Warning

class RunbotRepo(models.Model):
    _inherit = "runbot.repo"

    db_name = fields.Char("Database name to replicate")

    @api.onchange('db_name')
    @api.constrains('db_name')
    def onchange_db_name(self):
        self.ensure_one()
        if not self.db_name:
            return
        try:
            db = db_connect(self.db_name)
            db_cursor = db.cursor()
        except:
            raise Warning('The database "%s" doesn\'t exist' % self.db_name)
        db_cursor.close()