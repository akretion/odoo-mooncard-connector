# Copyright 2022-2025 Akretion France (https://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models
from odoo.tools import float_compare


class NewgenPaymentCardTransaction(models.Model):
    _inherit = 'newgen.payment.card.transaction'

    def _prepare_regular_taxes(self):
        # Set tax "TVA déd./immobilisation (achat)" on expenses with an asset account
        self.ensure_one()
        tax_ids = super()._prepare_regular_taxes()
        if (
                self.company_id.is_france_country
                and self.expense_account_id
                and self.expense_account_id.code.startswith(('20', '21'))):
            possible_taxes = self.env['account.tax'].search([
                ('company_id', '=', self.company_id.id),
                ('type_tax_use', '=', 'purchase'),
                ('unece_type_code', '=', 'VAT'),
                ('amount_type', '=', 'percent'),
                ('amount', '>', 0),
                ])
            accounts = self.env['account.account'].search([
                ('company_ids', 'in', self.company_id.id),
                ('code', '=ilike', '44562%'),
                ])
            if not accounts:
                return tax_ids
            lines = self.env['account.tax.repartition.line'].search([
                ('repartition_type', '=', 'tax'),
                ('company_id', '=', self.company_id.id),
                ('tax_id', 'in', possible_taxes.ids),
                ('document_type', '=', 'invoice'),
                ('account_id', 'in', accounts.ids),
                ('factor_percent', '>', 99.99),
                ('factor_percent', '<', 100.01),
                ])
            if not lines:
                return tax_ids
            for line in lines:
                if not float_compare(
                        line.tax_id.amount, self.vat_rate, precision_digits=4):
                    return [line.tax_id.id]
        return tax_ids
