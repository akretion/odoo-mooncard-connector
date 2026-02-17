# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, exceptions, fields, models
from odoo.tools import float_compare
from odoo.tools.misc import format_amount
from markupsafe import Markup


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

#    def _prepare_invoice(self):
#        if not self.has_multiple_vat_line:
#            return super()._prepare_invoice()
#        else:
#            return self._prepare_multiple_line_invoice()

    def _create_multiple_line_invoice(self):
        self.ensure_one()
        if self.force_invoice_date:
            date_dt = self.force_invoice_date
        elif self.payment_date:
            date_dt = self.payment_date
        else:
            date_dt = self.date

        if not self.description:
            raise UserError(_("Description is missing on transaction '%s'.") % self.display_name)
        if not self.partner_id:
            raise UserError(_(
                "Missing partner on transaction '%s'.") % self.display_name)

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
        tax2amounts = {}
        for vat_line in self.vat_line_ids:
            if not vat_line.expense_account_id:
                raise exceptions.UserError(
                    _("The expense account is missing on vat line %s for transaction %s" % (vat_line.vat_rate, self.description))
                )
            if vat_line.vat_rate:
                tax = self.env["account.tax"].browse(vat_line._prepare_regular_taxes())
                assert len(tax) == 1
            else:
                tax = self.env["account.tax"]
            line_vals = {
                "name": self.description,
                "quantity": 1,
                "tax_ids": [(6, 0, tax.ids)],
                "price_unit": abs(vat_line.subtotal_company_currency),
                "account_id": vat_line.expense_account_id.id,
                # let's consider the analytic does not depend on the line.
                "analytic_distribution": self.analytic_distribution or False,
            }
            vals["invoice_line_ids"].append((0, 0, line_vals))
            if tax:
                tax2amounts[tax.id] = vat_line.vat_company_currency
        vals["attachment_ids"] = self._get_attachment_vals_list()
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

                    line.with_context().write(vals)
#            invoice.with_context(check_move_validity=False)._recompute_dynamic_lines()
#            invoice._check_balanced()
        return invoice

    def generate_invoice(self):
        self.ensure_one()
        # standard mooncard import
        if not self.has_multiple_vat_line:
            return super().generate_invoice()
        assert self.transaction_type == "expense", "wrong transaction type"
        # manage multiple line invoice creation
        invoice = self._create_multiple_line_invoice()
        trans_link = f"<a href='#' data-oe-model='{self._name}' data-oe-id='{self.id}'>{self.display_name}</a>"
        invoice.message_post(body=Markup(_("Invoice created from payment card transaction %s.") % trans_link))
        invoice.with_context(validate_analytic=True)._post(soft=False)
        self._post_process_invoice(invoice)
        return invoice
