# -*- coding: utf-8 -*-
# © 2016 Akretion (Alexis de Lattre <alexis.delattre@akretion.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    # This field is fully generic, so it should be in a module
    # independant from mooncard... but there is no such module
    # for the moment AFAIK
    internal_bank_transfer_account_id = fields.Many2one(
        'account.account', string='Internal Bank Transfer Account',
        domain=[('type', 'not in', ('closed', 'consolidation', 'view'))])
