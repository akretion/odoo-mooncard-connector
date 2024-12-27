# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, exceptions, fields, models
from odoo.tools import float_compare
from odoo.tools.misc import format_amount


class NewgenPaymentCardTransaction(models.Model):
    _inherit = "newgen.payment.card.transaction"

    vat_line_ids = fields.One2many(
        "newgen.payment.card.transaction.vat.line", "transaction_id"
    )
    has_multiple_vat_line = fields.Boolean(compute="_compute_has_multiple_vat_line")

    @api.depends("vat_line_ids")
    def _compute_has_multiple_vat_line(self):
        for rec in self:
            rec.has_multiple_vat_line = len(rec.vat_line_ids) > 1

    def _create_multiple_line_invoice(self):
        self.ensure_one()
        if self.force_invoice_date:
            date_dt = self.force_invoice_date
        elif self.payment_date:
            date_dt = self.payment_date
        else:
            date_dt = self.date

        origin = self.name
        if self.receipt_number:
            origin = "%s (%s)" % (origin, self.receipt_number)
        move_type = "in_invoice" if self.total_company_currency <= 0.0 else "in_refund"
        vals = {
            "move_type": move_type,
            "partner_id": self.partner_id.id,
            "invoice_date": date_dt,
            "date": date_dt,
            "invoice_date_due": date_dt,
            "currency_id": self.company_id.currency_id.id,
            "ref": self.name,
            "invoice_origin": origin,
            "company_id": self.company_id.id,
            "invoice_line_ids": [],
        }
        if self.card_id.purchase_journal_id:
            vals["journal_id"] = self.card_id.purchase_journal_id.id
        vals = self.env["account.move"].play_onchanges(vals, ["partner_id"])
        tax2amounts = {}
        for vat_line in self.vat_line_ids:
            if not vat_line.expense_account_id:
                raise exceptions.UserError(
                    _("The expense account is missing on vat line %s for transaction %s" % (vat_line.vat_rate, self.description))
                )
            # we depend on base_business_document_import just for finding the tax.
            # we may choose to get rid of this in the future if base mooncard module
            # does not use it anymore either.
            if vat_line.vat_rate:
                taxes_info = self._prepare_regular_taxes_multi_rate(vat_line.vat_rate)
                tax = self.env["business.document.import"]._match_taxes(taxes_info, [])
                assert len(tax) == 1
            else:
                tax = self.env["account.tax"]
            line_vals = {
                "name": self.description,
                "quantity": 1,
                "product_uom_id": self.env.ref("uom.product_uom_unit").id,
                "tax_ids": [(6, 0, tax.ids)],
                "price_unit": abs(vat_line.subtotal_company_currency),
                "analytic_account_id": self.account_analytic_id.id,
                "account_id": vat_line.expense_account_id.id,
            }
            vals["invoice_line_ids"].append((0, 0, line_vals))
            if tax:
                tax2amounts[tax.id] = vat_line.vat_company_currency
        invoice = self.env["account.move"].create(vals)

        # all invoices are in company currency
        company_cur = invoice.company_id.currency_id
        prec = invoice.currency_id.rounding
        # TODO float compare
        if float_compare(
            invoice.amount_untaxed,
            abs(self.total_company_currency - self.vat_company_currency),
            precision_rounding=prec,
        ):
            # or should it be managed as a possible case ?
            raise exceptions.UserError(
                _(
                    "The untaxed amount of the invoice does not match the one of the "
                    "transaction"
                )
            )
        # Force tax amount if necessary
        if float_compare(
            invoice.amount_total,
            abs(self.total_company_currency),
            precision_rounding=prec,
        ):
            for tax_id, tax_amount in tax2amounts.items():
                line = invoice.line_ids.filtered(lambda li: li.tax_line_id.id == tax_id)
                assert len(line) == 1
                if float_compare(
                    -line.amount_currency, tax_amount, precision_rounding=prec
                ):
                    diff_tax_amount = abs(tax_amount) - abs(line.amount_currency)
                    if line.currency_id.compare_amounts(line.amount_currency, 0) >= 0:
                        new_amount_currency = company_cur.round(
                            line.amount_currency + diff_tax_amount
                        )
                    else:
                        new_amount_currency = company_cur.round(
                            line.amount_currency - diff_tax_amount
                        )
                    invoice.message_post(
                        body=_(
                            "The <b>tax amount</b> for tax %s has been <b>forced</b> "
                            "to %s (amount computed by Odoo was: %s)."
                        )
                        % (
                            line.tax_line_id.display_name,
                            format_amount(
                                self.env, new_amount_currency, invoice.currency_id
                            ),
                            format_amount(
                                self.env, line.amount_currency, invoice.currency_id
                            ),
                        )
                    )
                    vals = {"amount_currency": new_amount_currency}
                    if (
                        float_compare(new_amount_currency, 0, precision_rounding=prec)
                        > 0
                    ):
                        vals["debit"] = new_amount_currency
                        vals["credit"] = 0
                    else:
                        vals["debit"] = 0
                        vals["credit"] = new_amount_currency * -1

                    line.with_context(check_move_validity=False).write(vals)
            invoice.with_context(check_move_validity=False)._recompute_dynamic_lines()
            invoice._check_balanced()
        return invoice

    # similar to base_newgen_payment_card but manage different rate
    def _prepare_regular_taxes_multi_rate(self, rate):
        self.ensure_one()
        taxes = [
            {
                "amount_type": "percent",
                "amount": rate,
                "unece_type_code": "VAT",
                "unece_categ_code": "S",
            }
        ]
        return taxes

    def _generate_multiple_line_invoice_attachment(self, invoice):
        self.ensure_one()
        attachment_vals = self._get_attachment_vals()
        vals_list = []
        for name, data in attachment_vals.items():
            vals_list.append(
                {
                    "name": name,
                    "datas": data,
                    "res_id": invoice.id,
                    "res_model": "account.move",
                }
            )
        return self.env["ir.attachment"].create(vals_list)

    def generate_invoice(self):
        self.ensure_one()
        # standard mooncard import
        if not self.has_multiple_vat_line:
            return super().generate_invoice()
        assert self.transaction_type == "expense", "wrong transaction type"
        # manage multiple line invoice creation
        invoice = self._create_multiple_line_invoice()
        #        invoice = self.env["account.move"].create(invoice_vals)
        self._generate_multiple_line_invoice_attachment(invoice)
        invoice.message_post(
            body=_("Invoice created from payment card transaction %s.") % self.name
        )
        invoice.action_post()
        assert (
            self.company_currency_id.compare_amounts(
                invoice.amount_tax, abs(self.vat_company_currency)
            )
            == 0
        ), "bug on VAT"
        return invoice
