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

{
    'name': 'Runbot Hide Repositories',
    'category': 'Runbot',
    'summary': 'Allows to hide some repositories',
    'version': '1.0',
    'description': """
Runbot Hide Repositories
=======================

Allows to hide some repositories

Contributors
------------
* Sylvain Van Hoof (sylvain.vanhoof@eezee-it.com)
""",
    'author': "Eezee-It,Odoo Community Association (OCA)",
    'depends': ['runbot'],
    'data': [
        "views/runbot_repo.xml",
    ],
    'installable': True,
}
