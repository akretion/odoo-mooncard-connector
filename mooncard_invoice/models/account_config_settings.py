# -*- coding: utf-8 -*-
# © 2016 Akretion (Alexis de Lattre <alexis.delattre@akretion.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import models, fields


class AccountConfigSettings(models.TransientModel):
    _inherit = 'account.config.settings'

    internal_bank_transfer_account_id = fields.Many2one(
        'account.account',
        related='company_id.internal_bank_transfer_account_id')
