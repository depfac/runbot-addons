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
from odoo import models, api, fields, _
from odoo.exceptions import Warning

from psycopg2 import ProgrammingError
from ..tabulate import tabulate


class SQLQuery(models.Model):
    _name = 'runbot.sql.query'
    _order = 'when_applied desc'

    database = fields.Char(string='Database', required=True, states={'applied': [('readonly', True)]})
    query = fields.Text(string='Query', required=True, states={'applied': [('readonly', True)]})
    state = fields.Selection(selection=[('draft', 'Draft'), ('failed', 'Failed'), ('applied', 'Applied')],
                             default='draft', readonly=True)
    test_state = fields.Selection(selection=[('untested', 'Untested'), ('failed', '✘'), ('ok', '✓')],
                                  default='untested', readonly=True)
    pg_result = fields.Text(string='Result returned by Postgres', readonly=True)
    when_applied = fields.Datetime(string='Time of application', readonly=True)
    who_applied = fields.Many2one('res.users', string='User who applied', readonly=True)

    @api.multi
    def write(self, vals):
        if 'query' in vals:
            vals['test_state'] = 'untested'
        return super(SQLQuery, self).write(vals)

    @api.multi
    def test(self):
        for query in self:
            query.validate()
            cr = None
            try:
                cr = openerp.sql_db.db_connect(query.database).cursor()
                cr.execute('BEGIN')
                cr.execute(query.query)
                result = u'Status: %s\n\n\n' % cr.statusmessage
                if cr.rowcount > 0:
                    try:
                        data = cr.fetchall()
                        result += tabulate(data, headers=[c.name for c in cr.description])
                    except ProgrammingError as e:
                        if e.message != 'no results to fetch':
                            raise
                else:
                    result += '(0 rows)'
                cr.execute('ROLLBACK')
                query.write({
                    'pg_result': result,
                    'test_state': 'ok',
                })
            except StandardError as e:
                query.write({
                    'pg_result': repr(e).replace('\\n', '\n'),
                    'test_state': 'failed',
                })
            finally:
                if cr:
                    cr.close()

    @api.multi
    def apply(self):
        for query in self:
            query.validate()
            cr = None
            try:
                cr = openerp.sql_db.db_connect(query.database).cursor()
                cr.execute('BEGIN')
                cr.execute(query.query)
                status = cr.statusmessage
                cr.execute('COMMIT')
                query.write({
                    'pg_result': u'Status: %s\n' % status,
                    'state': 'applied',
                    'when_applied': fields.Datetime.now(),
                    'who_applied': self.env.user.id,
                })
            except StandardError as e:
                query.write({
                    'pg_result': repr(e).replace('\\n', '\n'),
                    'state': 'failed',
                })
            finally:
                if cr:
                    cr.close()

    @api.multi
    def validate(self):
        def is_transaction_control(p):
            return any(p.startswith(x) for x in ('BEGIN', 'COMMIT', 'ROLLBACK'))

        for query in self:
            query_str = query.query
            query_str = query_str.upper().replace("''", "")
            strings_removed = []
            in_string = False
            for char in query_str:
                if char == "'":
                    in_string = not in_string
                elif not in_string:
                    strings_removed.append(char)
            query_str = ''.join(strings_removed)
            parts = [part.strip() for part in query_str.split(';')]
            if any(is_transaction_control(part) for part in parts):
                raise Warning(_('The transaction is managed by the editor, please don\'t use '
                                'BEGIN, COMMIT or ROLLBACK in the query'))

