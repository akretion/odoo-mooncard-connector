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
    payment_move_only = fields.Boolean(
        string="Generate Payment Move Only",
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
    payment_move_line_id = fields.Many2one(
        'account.move.line', string='Payment Move Line', readonly=True)
    payment_move_id = fields.Many2one(
        'account.move', string="Payment Move",
        related='payment_move_line_id.move_id', readonly=True)
    reconcile_id = fields.Many2one(
        'account.full.reconcile', string="Reconcile",
        related='payment_move_line_id.full_reconcile_id', readonly=True)
    load_move_id = fields.Many2one(
        'account.move', string="Load Move", readonly=True)
    # Note for future versions : was it really a good idea to have 2 fields
    # payment_move_id and load_move_id -> 1 field bank_move_id ?

    @api.onchange('invoice_id')
    def invoice_id_change(self):
        if self.invoice_id:
            self.partner_id = self.invoice_id.commercial_partner_id

    @api.multi
    def process_line(self):
        # TODO: in the future, we may have to support the case where
        # both mooncard_invoice and mooncard_expense are installed
        for line in self:
            if line.state != 'draft':
                logger.warning(
                    'Skipping mooncard transaction %s which is not draft',
                    line.name)
                continue
            if line.transaction_type == 'presentment':
                if not line.description:
                    raise UserError(_(
                        "The description field is empty on "
                        "mooncard transaction %s.") % line.name)
                line.generate_bank_journal_move()
                if not line.payment_move_only:
                    line.generate_invoice()
                    line.reconcile()
                line.state = 'done'
            elif line.transaction_type == 'load':
                line.generate_load_move()
                line.state = 'done'
            elif line.transaction_type == 'authorization':
                raise UserError(_(
                    'Cannot process mooncard transaction %s because it is '
                    'still in authorization state at the bank.') % line.name)

    @api.multi
    def _prepare_load_move(self):
        self.ensure_one()
        date = self.date[:10]
        precision = self.company_currency_id.rounding
        load_amount = self.total_company_currency
        if float_compare(load_amount, 0, precision_rounding=precision) > 0:
            credit = 0
            debit = load_amount
        else:
            credit = load_amount
            debit = 0
        journal = self.card_id.journal_id
        mvals = {
            'journal_id': journal.id,
            'date': date,
            'ref': self.name,
            'line_ids': [
                (0, 0, {
                    'account_id': journal.default_debit_account_id.id,
                    'debit': debit,
                    'credit': credit,
                    'name': _('Load Mooncard prepaid-account'),
                    }),
                (0, 0, {
                    'account_id':
                    self.company_id.transfer_account_id.id,
                    'debit': credit,
                    'credit': debit,
                    'name': _('Load Mooncard prepaid-account'),
                    }),
                ],
            }
        return mvals

    @api.one
    def generate_load_move(self):
        assert not self.load_move_id, 'already has a load move !'
        if not self.company_id.transfer_account_id:
            raise UserError(_(
                "Missing 'Internal Bank Transfer Account' on company %s.")
                % self.company_id.name)
        if not self.card_id.journal_id:
            raise UserError(_(
                "Bank Journal not configured on Moon Card '%s'")
                % self.card_id.name)
        move = self.env['account.move'].create(self._prepare_load_move())
        move.post()
        self.load_move_id = move.id
        return True

    @api.one
    def generate_bank_journal_move(self):
        assert not self.payment_move_line_id, 'Payment line already created'
        if not self.card_id.journal_id:
            raise UserError(_(
                "Bank Journal not configured on Moon Card '%s'")
                % self.card_id.name)
        journal = self.card_id.journal_id
        amlo = self.env['account.move.line']
        date = self.date[:10]
        partner = self.partner_id.commercial_partner_id
        expense_amount = self.total_company_currency * -1
        precision = self.company_currency_id.rounding
        if float_compare(
                expense_amount, 0, precision_rounding=precision) > 0:
            credit = 0
            debit = expense_amount
        else:
            credit = expense_amount
            debit = 0
        mlvals1 = {
            'name': self.description,
            'partner_id': partner.id,
            'account_id': partner.property_account_payable_id.id,
            'credit': credit,
            'debit': debit,
            }
        mlvals2 = {
            'name': self.description,
            'partner_id': partner.id,
            'account_id': journal.default_credit_account_id.id,
            'credit': debit,
            'debit': credit,
            }
        mvals = {
            'journal_id': journal.id,
            'date': date,
            'ref': self.name,
            'line_ids': [(0, 0, mlvals1), (0, 0, mlvals2)],
            }
        bank_move = self.env['account.move'].create(mvals)
        bank_move.post()
        self.payment_move_line_id = amlo.search([
            ('move_id', '=', bank_move.id),
            ('account_id', '=', partner.property_account_payable_id.id),
            ])[0].id

    @api.model
    def _countries_vat_refund(self):
        return self.env.user.company_id.country_id

    @api.multi
    def _prepare_invoice_import(self):
        self.ensure_one()
        precision = self.company_currency_id.rounding
        if self.force_invoice_date:
            date = self.force_invoice_date
        elif self.payment_date:
            date = self.payment_date[:10]
        else:
            date = self.date[:10]
        vat_compare = float_compare(
            self.vat_company_currency, 0, precision_rounding=precision)
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
            total_compare = float_compare(
                self.total_company_currency, 0, precision_rounding=precision)
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
                'price_unit': amount_untaxed,
                'name': self.description,
                'qty': 1,
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

    @api.one
    def generate_invoice(self):
        if self.invoice_id:
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
            return
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
        self.invoice_id = invoice.id

    @api.one
    def reconcile(self):
        assert self.payment_move_line_id
        assert self.invoice_id
        assert self.invoice_id.move_id
        assert not self.reconcile_id, 'already has a reconcile mark'
        movelines_to_rec = self.payment_move_line_id
        for line in self.invoice_id.move_id.line_ids:
            if line.account_id == self.payment_move_line_id.account_id:
                movelines_to_rec += line
                break
        movelines_to_rec.reconcile()
        self.reconcile_id = self.payment_move_line_id.full_reconcile_id.id
