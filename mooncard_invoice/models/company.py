# -*- coding: utf-8 -*-
# © 2016 Akretion (Alexis de Lattre <alexis.delattre@akretion.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    # This field exists in Odoo v9+, but not in Odoo 8
    # That's why we create it here
    transfer_account_id = fields.Many2one(
        'account.account', string='Inter-Banks Transfer Account',
        domain=[
            ('type', 'not in', ('closed', 'consolidation', 'view')),
            ('reconcile', '=', True)],
        help="Intermediary account used when moving money from a "
        "liquidity account to another")
