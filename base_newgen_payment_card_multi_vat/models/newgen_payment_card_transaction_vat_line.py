# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import exceptions, fields, models
from odoo.tools import float_compare


class NewgenPaymentCardTransactionVatLine(models.Model):
    _name = "newgen.payment.card.transaction.vat.line"
    _description = "Transaction amounts by vat rate"

    transaction_id = fields.Many2one(
        "newgen.payment.card.transaction", required=True, readonly=True,
        ondelete='cascade'
    )
    state = fields.Selection(related="transaction_id.state", store=True)
    company_currency_id = fields.Many2one(
        "res.currency", related="transaction_id.company_currency_id", store=True
    )
    currency_id = fields.Many2one(
        "res.currency", related="transaction_id.currency_id", store=True
    )
    company_id = fields.Many2one(
        "res.company", related="transaction_id.company_id", store=True
    )
    vat_company_currency = fields.Monetary(
        string="VAT Amount",
        # not readonly, because accountant may have to change the value
        currency_field="company_currency_id",
        states={"done": [("readonly", True)]},
        help="VAT Amount in Company Currency",
    )
    vat_rate = fields.Float(
        string="VAT Rate (%)",
        states={"done": [("readonly", True)]},
        digits=(16, 4),
        help="VAT rate of the transaction (or part of it) in percent.",
    )
    subtotal_company_currency = fields.Monetary(
        string="Total Amount in Company Currency",
        currency_field="company_currency_id",
        readonly=True,
    )
    total_company_currency = fields.Monetary(
        string="Total Amount in Company Currency",
        currency_field="company_currency_id",
        readonly=True,
    )
    expense_account_id = fields.Many2one(
        "account.account",
        states={"done": [("readonly", True)]},
        domain="[('deprecated', '=', False), ('company_ids', 'in', company_id), ('account_type', '!=', 'off_balance')]",
        string="Expense Account",
        check_company=True,
    )

    def _prepare_regular_taxes(self):
        self.ensure_one()
        domain = [
            ('company_id', '=', self.transaction_id.company_id.id),
            ('type_tax_use', '=', 'purchase'),
            ('price_include', '=', False),
            ('amount_type', '=', 'percent'),
            ('amount', '>', 0),
            ('unece_type_code', '=', 'VAT'),
            ('unece_categ_code', '=', 'S'),
            ]
        taxes = self.env['account.tax'].search(domain)
        for tax in taxes:
            if not float_compare(tax.amount, self.vat_rate, precision_digits=4):
                return [tax.id]
        raise exceptions.UserError(self.env._(
            "Failed to match regular purchase VAT tax %.2f %%.") % self.vat_rate)

