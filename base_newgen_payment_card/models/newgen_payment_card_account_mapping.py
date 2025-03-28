# Copyright 2016-2025 Akretion France (https://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class NewgenPaymentCardAccountMapping(models.Model):
    _name = 'newgen.payment.card.account.mapping'
    _description = 'Account mapping for new generation payment cards'
    _check_company_auto = True

    card_id = fields.Many2one(
        'newgen.payment.card', string='Payment Card', ondelete='cascade', required=True)
    company_id = fields.Many2one(related='card_id.company_id', store=True)
    expense_account_id = fields.Many2one(
        'account.account', string='Expense Account', ondelete='restrict',
        domain="[('deprecated', '=', False), ('company_ids', 'in', company_id), ('account_type', '!=', 'off_balance')]",
        required=True, check_company=True)
    force_expense_account_id = fields.Many2one(
        'account.account', string='Override Expense Account', ondelete='restrict',
        domain="[('deprecated', '=', False), ('company_ids', 'in', company_id), ('account_type', '!=', 'off_balance')]",
        required=True, check_company=True)
