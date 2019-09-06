# -*- coding: utf-8 -*-
# © 2016-2017 Akretion (Alexis de Lattre <alexis.delattre@akretion.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero
import requests
import base64
import logging
from urlparse import urlparse
import os

logger = logging.getLogger(__name__)


class MooncardTransaction(models.Model):
    _inherit = 'mooncard.transaction'

    partner_id = fields.Many2one(
        'res.partner', string='Vendor', required=True,
        domain=[('supplier', '=', True), ('parent_id', '=', False)],
        states={'done': [('readonly', True)]}, ondelete='restrict',
        default=lambda self:
            self.env.ref('mooncard_base.mooncard_supplier'),
        help="By default, all transactions are linked to the generic "
        "supplier 'Mooncard Misc Suppliers'. You can change the partner "
        "to the real partner of the transaction if you want, but it may not "
        "be worth the additionnal work.")
    force_invoice_date = fields.Date(
        string='Force Invoice Date', states={'done': [('readonly', True)]})
    bank_move_only = fields.Boolean(
        string="Generate Bank Move Only", oldname='payment_move_only',
        states={'done': [('readonly', True)]},
        help="When you process a transaction on which this option is enabled, "
        "Odoo will only generate the move in the bank journal, it will not "
        "generate a supplier invoice/refund. This option is useful when you "
        "make a payment in advance and you haven't received the invoice yet.")
    invoice_id = fields.Many2one(
        'account.invoice', string='Invoice',
        states={'done': [('readonly', True)]})
    invoice_state = fields.Selection(
        related='invoice_id.state', readonly=True,
        string="Invoice State")
    payment_move_line_id = fields.Many2one(  # remove field in v12
        'account.move.line', string='[OLD] Payment Move Line', readonly=True)
    payment_move_id = fields.Many2one(  # remove field in v12
        'account.move', string="[OLD] Payment Move",
        related='payment_move_line_id.move_id', readonly=True)
    reconcile_id = fields.Many2one(
        'account.full.reconcile', string="Reconcile",
        related='payment_move_line_id.full_reconcile_id', readonly=True)
    load_move_id = fields.Many2one(  # remove field in v12
        'account.move', string="[OLD] Load Move", readonly=True)
    bank_counterpart_account_id = fields.Many2one(
        'account.account', domain=[('deprecated', '=', False)],
        states={'done': [('readonly', True)]}, required=True,
        string="Counter-part of Bank Move")
    bank_move_id = fields.Many2one(
        # replaces load_move_id and payment_move_id
        'account.move', string="Bank Move", readonly=True)

    @api.onchange('invoice_id')
    def invoice_id_change(self):
        if self.invoice_id:
            self.partner_id = self.invoice_id.commercial_partner_id

    @api.onchange('partner_id')
    def partner_id_change(self):
        if self.transaction_type == 'presentment' and self.partner_id:
            self.bank_counterpart_account_id =\
                self.partner_id.property_account_payable_id.id

    def process_line(self):
        # TODO: in the future, we may have to support the case where
        # both mooncard_invoice and mooncard_expense are installed
        for line in self:
            if line.state != 'draft':
                logger.warning(
                    'Skipping mooncard transaction %s which is not draft',
                    line.name)
                continue
            if line.transaction_type == 'authorization':
                raise UserError(_(
                    'Cannot process mooncard transaction %s because it is '
                    'still in authorization state at the bank.') % line.name)
            vals = {'state': 'done'}
            bank_move = line.generate_bank_journal_move()
            vals['bank_move_id'] = bank_move.id
            if line.transaction_type == 'presentment':
                if not line.bank_move_only:
                    if line.invoice_id:
                        self.check_existing_invoice()
                        invoice = line.invoice_id
                    else:
                        invoice = line.generate_invoice()
                        vals['invoice_id'] = invoice.id
                    rec = line.reconcile(bank_move, invoice)
                    vals['reconcile_id'] = rec.id
            line.write(vals)
        return True

    def _prepare_bank_journal_move(self):
        self.ensure_one()
        precision = self.company_currency_id.rounding
        amount = self.total_company_currency
        if float_compare(amount, 0, precision_rounding=precision) > 0:
            credit = 0
            debit = amount
        else:
            credit = amount * -1
            debit = 0
        if not self.card_id.journal_id:
            raise UserError(_(
                "Bank Journal not configured on Moon Card '%s'")
                % self.card_id.name)
        journal = self.card_id.journal_id
        if not self.bank_counterpart_account_id:
            raise UserError(_(
                "Counter-part of Bank Move is empty "
                "on mooncard transaction %s.") % self.name)
        if self.transaction_type == 'presentment':
            if not self.description:
                raise UserError(_(
                    "The description field is empty on "
                    "mooncard transaction %s.") % self.name)
            name = self.description
            partner_id = self.partner_id.id
        elif self.transaction_type == 'load':
            name = _('Load Mooncard prepaid-account')
            partner_id = False
        mvals = {
            'journal_id': journal.id,
            'date': self.date,
            'ref': self.name,
            'line_ids': [
                (0, 0, {
                    'account_id': journal.default_debit_account_id.id,
                    'debit': debit,
                    'credit': credit,
                    'name': name,
                    'partner_id': partner_id,
                    }),
                (0, 0, {
                    'account_id': self.bank_counterpart_account_id.id,
                    'debit': credit,
                    'credit': debit,
                    'name': name,
                    'partner_id': partner_id,
                    }),
                ],
            }
        return mvals

    def generate_bank_journal_move(self):
        self.ensure_one()
        vals = self._prepare_bank_journal_move()
        bank_move = self.env['account.move'].create(vals)
        bank_move.post()
        return bank_move

    @api.model
    def _countries_vat_refund(self):
        return self.env.user.company_id.country_id

    def _prepare_invoice_import(self):
        self.ensure_one()
        precision = self.company_currency_id.rounding
        if self.force_invoice_date:
            date = self.force_invoice_date
        elif self.payment_date:
            date = self.payment_date[:10]
        else:
            date = self.date
        vat_compare = float_compare(
            self.vat_company_currency, 0, precision_rounding=precision)
        total_compare = float_compare(
            self.total_company_currency, 0, precision_rounding=precision)
        taxes = []
        if vat_compare:
            if (
                    self.country_id and
                    self.company_id.country_id and
                    self.country_id not in self._countries_vat_refund()):
                raise UserError(_(
                    "The mooncard transaction '%s' is associated with country "
                    "'%s'. As we cannot refund VAT from this country, "
                    "the VAT amount of that transaction should be updated "
                    "to 0.")
                    % (self.name, self.country_id.name))
            if vat_compare != total_compare:
                raise UserError(_(
                    "The sign of the VAT amount (%s) should be the same as "
                    "the sign of the total amount (%s).")
                    % (self.vat_company_currency, self.total_company_currency))
            # get rate
            if not float_is_zero(
                    self.fr_vat_20_amount, precision_rounding=precision):
                rate = 20.0
            elif not float_is_zero(
                    self.fr_vat_10_amount, precision_rounding=precision):
                rate = 10.0
            elif not float_is_zero(
                    self.fr_vat_5_5_amount, precision_rounding=precision):
                rate = 5.5
            elif not float_is_zero(
                    self.fr_vat_2_1_amount, precision_rounding=precision):
                rate = 2.1
            else:
                raise UserError(_("Houston, we have a problem!"))
            taxes.append({
                'amount_type': 'percent',
                'amount': rate,
                'unece_type_code': 'VAT',
                'unece_categ_code': 'S',
                })
        if not self.description:
            raise UserError(_(
                "Missing label on Mooncard transaction %s")
                % self.name)
        origin = self.name
        if self.receipt_number:
            origin = u'%s (%s)' % (origin, self.receipt_number)
        amount_untaxed = self.total_company_currency * -1\
            - self.vat_company_currency * -1
        price_unit = amount_untaxed
        qty = 1
        if total_compare > 0:  # refund
            qty *= -1
            price_unit *= -1
        parsed_inv = {
            'partner': {'recordset': self.partner_id},
            'date': date,
            'date_due': date,
            'currency': {'recordset': self.company_id.currency_id},
            'amount_total': self.total_company_currency * -1,
            'amount_untaxed': amount_untaxed,
            'invoice_number': self.name,
            'lines': [{
                'taxes': taxes,
                'price_unit': price_unit,
                'name': self.description,
                'qty': qty,
                'uom': {'recordset': self.env.ref('product.product_uom_unit')},
                }],
            'origin': origin,
            }
        url = self.image_url
        if not url and not self.receipt_lost:
            raise UserError(_(
                "Missing image URL on Mooncard transaction %s. If you lost "
                "that receipt, you can mark this mooncard transaction "
                "as 'Receipt Lost'.")
                % self.name)
        if url:
            try:
                rimage = requests.get(url)
            except Exception, e:
                raise UserError(_(
                    "Failed to download the image of the receipt. "
                    "Error message: %s.") % e)
            if rimage.status_code != 200:
                raise UserError(_(
                    "Could not download the image of Mooncard transaction %s "
                    "from URL %s (HTTP error code %s).")
                    % (self.name, url, rimage.status_code))
            image_b64 = base64.encodestring(rimage.content)
            file_extension = os.path.splitext(urlparse(url).path)[1]
            filename = 'Receipt-%s%s' % (self.name, file_extension)
            parsed_inv['attachments'] = {filename: image_b64}
        return parsed_inv

    def check_existing_invoice(self):
        assert self.invoice_id
        # should not happen because domain blocks that
        if self.invoice_id.currency_id != self.company_currency_id:
            raise UserError(_(
                "For the moment, we don't support linking to an invoice "
                "in another currency than the company currency."))
        # should not happen because domain blocks that
        if self.invoice_id.state != 'open':
            raise UserError(_(
                "The mooncard transaction %s is linked to invoice %s "
                "which is not in open state.")
                % (self.name, self.invoice_id.number))
        # should not happen because domain blocks that
        if self.invoice_id.type not in ('in_invoice', 'in_refund'):
            raise UserError(_(
                "The mooncard transaction %s is linked to invoice %s "
                "which is not a supplier invoice/refund!")
                % (self.name, self.invoice_id.number))
        # handled by onchange
        if self.partner_id != self.invoice_id.commercial_partner_id:
            raise UserError(_(
                "The mooncard transaction %s is linked to partner '%s' "
                "whereas the related invoice %s is linked to "
                "partner '%s'.") % (
                self.name, self.partner_id.display_name,
                self.invoice_id.commercial_partner_id.display_name))
        # TODO handle partial payments ?
        if float_compare(
                self.invoice_id.amount_total_signed,
                self.total_company_currency * -1,
                precision_rounding=self.company_currency_id.rounding):
            raise UserError(_(
                "The mooncard transaction %s is linked to the "
                "invoice/refund %s whose total amount is %s %s, "
                "but the amount of the transaction is %s %s.") % (
                self.name, self.invoice_id.number,
                self.invoice_id.amount_total_signed,
                self.invoice_id.currency_id.name,
                self.total_company_currency,
                self.company_currency_id.name))

    def generate_invoice(self):
        self.ensure_one()
        assert self.transaction_type == 'presentment', 'wrong transaction type'
        aiio = self.env['account.invoice.import']
        precision = self.company_currency_id.rounding
        parsed_inv = self._prepare_invoice_import()
        logger.debug('Mooncard invoice import parsed_inv=%s', parsed_inv)
        parsed_inv = aiio.pre_process_parsed_inv(parsed_inv)
        if not self.expense_account_id:
            raise UserError(_(
                "Missing expense account on transaction %s") % self.name)
        import_config = {
            'invoice_line_method': 'nline_no_product',
            'account': self.expense_account_id,
            'account_analytic': self.account_analytic_id or False,
            }
        invoice = aiio.create_invoice(parsed_inv, import_config=import_config)
        invoice.message_post(_(
            "Invoice created from Mooncard transaction %s.") % self.name)
        invoice.action_invoice_open()
        assert float_compare(
            invoice.amount_tax, abs(self.vat_company_currency),
            precision_rounding=precision) == 0, 'bug on VAT'
        return invoice

    def reconcile(self, bank_move, invoice):
        self.ensure_one()
        assert self.bank_counterpart_account_id
        assert bank_move
        assert invoice
        assert invoice.move_id
        assert not self.reconcile_id, 'already has a reconcile mark'
        movelines_to_rec = self.env['account.move.line'].search([
            ('move_id', '=', bank_move.id),
            ('account_id', '=', self.bank_counterpart_account_id.id),
            ], limit=1)
        for line in invoice.move_id.line_ids:
            if line.account_id == self.bank_counterpart_account_id:
                movelines_to_rec += line
        movelines_to_rec.reconcile()
        return movelines_to_rec[0].full_reconcile_id
