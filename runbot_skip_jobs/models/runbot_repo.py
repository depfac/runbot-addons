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
from openerp import models, fields, api


class RunbotJob(models.Model):
    _name = "runbot.job"

    name = fields.Char("Job name")


class RunbotRepo(models.Model):
    _inherit = "runbot.repo"

    @api.model
    def cron_update_job(self):
        build_obj = self.env['runbot.build']
        jobs = build_obj._list_jobs()
        job_obj = self.env['runbot.job']
        for job_name in jobs:
            job = job_obj.search([('name', '=', job_name)])
            if not job:
                job_obj.create({'name': job_name})
        job_to_rm = job_obj.sudo().search([('name', 'not in', jobs)])
        job_to_rm.unlink()
        return True

    skip_job_ids = fields.Many2many('runbot.job', string='Jobs to skip')
    parse_job_ids = fields.Many2many('runbot.job', "repo_parse_job_rel",
                                     string='Jobs to parse')