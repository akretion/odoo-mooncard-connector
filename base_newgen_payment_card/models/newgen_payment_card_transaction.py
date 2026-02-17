# Copyright 2016-2025 Akretion France (https://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare
from odoo.tools.misc import format_amount
import requests
import logging
from urllib.parse import urlparse
from markupsafe import Markup
import os
import io

TIMEOUT = 30

logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageOps
except ImportError:
    logger.debug('Cannot import Pillow version >= 6.0.0')


class NewgenPaymentCardTransaction(models.Model):
    _name = 'newgen.payment.card.transaction'
    _description = 'New-generation payment card transaction'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'analytic.mixin']
    _order = 'date desc'
    _check_company_auto = True

    name = fields.Char(string='Number', readonly=True, default=lambda self: _("New"))
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, readonly=True,
        default=lambda self: self.env.company)
    company_currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id',
        string="Company Currency", store=True)
    description = fields.Char(string='Description')
    unique_import_id = fields.Char(
        string='Unique Identifier', readonly=True, copy=False)
    date = fields.Date(
        string='Bank Transaction Date', required=True, readonly=True,
        help="This is the date of the bank transaction written on the "
        "bank statement. It may be a few days after the payment date. "
        "It is used for the bank journal entry.")
    payment_date = fields.Datetime(
        string='Payment Date', readonly=True,
        help="This is the real date of the payment. It may be a few days "
        "before the date of the bank transaction written on the bank "
        "statement. It is used for the supplier invoice.")
    force_invoice_date = fields.Date(string='Force Invoice Date')
    card_id = fields.Many2one(
        'newgen.payment.card', string='Card', readonly=True,
        ondelete='restrict', check_company=True)
    expense_categ_name = fields.Char(
        string='Expense Category', readonly=True)
    expense_account_id = fields.Many2one(
        'account.account',
        domain="[('deprecated', '=', False), ('company_ids', 'in', company_id), ('account_type', '!=', 'off_balance')]",
        string='Expense Account', check_company=True)
    analytic_distribution = fields.Json()
    country_id = fields.Many2one('res.country', string='Country')
    vendor = fields.Char(string='Vendor', readonly=True)
    vendor_vat = fields.Char(string='Vendor VAT Number', readonly=True)
    partner_id = fields.Many2one(
        'res.partner', string='Vendor Partner',
        domain=[('parent_id', '=', False)], ondelete='restrict',
        compute="_compute_partner_id", store=True, precompute=True, readonly=False,
        help="By default, all transactions are linked to the generic "
        "supplier 'Misc Suppliers'. You can change the partner "
        "to the real partner of the transaction if you want, but it may not "
        "be worth the additionnal work.")
    transaction_type = fields.Selection([
        ('load', 'Load'),
        ('expense', 'Expense'),
        ], string='Transaction Type', readonly=True)
    autoliquidation = fields.Selection([
        ('intracom', 'Intra-EU'),
        ('extracom', 'Extra-EU'),
        ('none', 'None'),
        ], default='none', string='Auto-Liquidation')
    vat_company_currency = fields.Monetary(
        string='VAT Amount',
        # not readonly, because accountant may have to change the value
        currency_field='company_currency_id',
        help='VAT Amount in Company Currency')
    vat_rate = fields.Float(
        string='VAT Rate (%)', digits=(16, 4),
        help='Main VAT rate of the transaction in percent.')
    total_company_currency = fields.Monetary(
        string='Total Amount in Company Currency',
        currency_field='company_currency_id', readonly=True)
    currency_id = fields.Many2one(
        'res.currency', string='Expense Currency', readonly=True)
    total_currency = fields.Monetary(
        string='Total Amount in Expense Currency', readonly=True,
        currency_field='currency_id')
    image_url = fields.Char(string='Image URL')
    receipt_lost = fields.Boolean(string='Receipt Lost')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ], string='State', default='draft', readonly=True)
    receipt_number = fields.Char(string='Receipt Number', readonly=True)
    bank_move_only = fields.Boolean(
        string="Generate Bank Journal Entry Only",
        help="When you process a transaction on which this option is enabled, "
        "Odoo will only generate the journal entry in the bank journal, it will not "
        "generate a supplier invoice/refund. This option is useful when you "
        "make a payment in advance and you haven't received the invoice yet.")
    invoice_id = fields.Many2one(
        'account.move', string='Invoice', check_company=True)
    invoice_payment_state = fields.Selection(
        related='invoice_id.payment_state', string="Invoice Payment Status")
    bank_counterpart_account_id = fields.Many2one(
        'account.account',
        compute='_compute_bank_counterpart_account_id', store=True, precompute=True,
        readonly=False,
        domain="[('deprecated', '=', False), ('company_ids', 'in', company_id), ('account_type', '!=', 'off_balance')]",
        string="Counter-part of Bank Journal Item", check_company=True)
    bank_move_id = fields.Many2one(
        'account.move', string="Bank Journal Entry", readonly=True, check_company=True)

    _sql_constraints = [(
        'unique_import_id',
        'unique(unique_import_id)',
        'A payment card transaction can be imported only once!')]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'company_id' in vals:
                self = self.with_company(vals['company_id'])
            if vals.get('name', _("New")) == _("New"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'newgen.payment.card.transaction',
                    sequence_date=vals.get('date')) or _("New")
        return super().create(vals_list)

    @api.depends("partner_id", "expense_account_id")
    def _compute_analytic_distribution(self):
        for trans in self:
            distribution = self.env[
                "account.analytic.distribution.model"
            ]._get_distribution(
                {
                    "partner_id": trans.partner_id.id,
                    "partner_category_id": trans.partner_id.category_id.ids,
                    "account_prefix": trans.expense_account_id.code,
                    "company_id": trans.company_id.id,
                }
            )
            trans.analytic_distribution = distribution or trans.analytic_distribution

    # We could write the partner matching here
    # advantage: generic code, not mooncard-specific
    # drawback: no speeddict that allows to speed-up matching
    @api.depends('invoice_id', 'company_id')
    def _compute_partner_id(self):
        for trans in self:
            if trans.invoice_id:
                partner = trans.invoice_id.commercial_partner_id
            else:
                partner = trans.company_id._default_partner()
            trans.partner_id = partner and partner.id or False

    @api.constrains('transaction_type', 'partner_id')
    def _check_transaction(self):
        for trans in self:
            if trans.transaction_type == 'expense' and not trans.partner_id:
                raise ValidationError(_(
                    "Partner missing on expense transaction '%s'.")
                    % trans.display_name)

    def open_image_url(self):
        if not self.image_url:
            raise UserError(_(
                "Missing image URL for transaction %s.") % self.display_name)
        action = {
            'type': 'ir.actions.act_url',
            'url': self.image_url,
            'target': 'new',
            }
        return action

    def unlink(self):
        for trans in self:
            if trans.state == 'done':
                raise UserError(_(
                    "Cannot delete transaction '%s' which is in "
                    "done state.") % trans.display_name)
        return super().unlink()

    @api.depends('partner_id', 'transaction_type', 'company_id')
    def _compute_bank_counterpart_account_id(self):
        for trans in self:
            account_id = False
            if trans.transaction_type == 'load':
                account_id = trans.company_id.transfer_account_id.id or False
            elif trans.transaction_type == 'expense':
                if trans.partner_id:
                    account_id = trans.with_company(trans.company_id.id).partner_id.property_account_payable_id.id
                else:
                    account_id = self.env['ir.property'].with_company(
                        trans.company_id.id)._get(
                            'property_account_payable_id', 'res.partner')
            trans.bank_counterpart_account_id = account_id

    def process_line(self):
        for line in self:
            if line.state != 'draft':
                logger.warning(
                    'Skipping transaction %s which is not draft',
                    line.display_name)
                continue
            vals = {'state': 'done'}
            bank_move = line.generate_bank_journal_move()
            vals['bank_move_id'] = bank_move.id
            if line.transaction_type == 'expense':
                if not line.bank_move_only:
                    if line.invoice_id:
                        self.check_existing_invoice()
                        invoice = line.invoice_id
                    else:
                        invoice = line.generate_invoice()
                        vals['invoice_id'] = invoice.id
                    line.reconcile(bank_move, invoice)
            line.write(vals)
        return True

    def _prepare_bank_journal_move(self):
        self.ensure_one()
        amount = self.total_company_currency
        if self.company_currency_id.compare_amounts(amount, 0) > 0:
            credit = 0
            debit = amount
        else:
            credit = amount * -1
            debit = 0
        if not self.card_id.journal_id:
            raise UserError(_(
                "Bank Journal not configured on payment card '%s'")
                % self.card_id.name)
        journal = self.card_id.journal_id
        if not self.bank_counterpart_account_id:
            raise UserError(_(
                "Counter-part of Bank Journal Item is empty "
                "on transaction %s.") % self.name)
        transaction_type = dict(
            self.fields_get(
                'transaction_type',
                'selection')['transaction_type']['selection'])[self.transaction_type]
        ref = f'{self.name} ({transaction_type})'
        if self.transaction_type == 'expense':
            partner_id = self.partner_id.id
        elif self.transaction_type == 'load':
            partner_id = False
        mvals = {
            'journal_id': journal.id,
            'date': self.date,
            'ref': ref,
            'line_ids': [
                Command.create({
                    'account_id': journal.default_account_id.id,
                    'debit': debit,
                    'credit': credit,
                    'partner_id': partner_id,
                    }),
                Command.create({
                    'account_id': self.bank_counterpart_account_id.id,
                    'debit': credit,
                    'credit': debit,
                    'partner_id': partner_id,
                    }),
                ],
            }
        return mvals

    def generate_bank_journal_move(self):
        self.ensure_one()
        vals = self._prepare_bank_journal_move()
        bank_move = self.env['account.move'].create(vals)
        bank_move._post(soft=False)
        return bank_move

    def _countries_vat_refund(self):
        return self.company_id.country_id

    def _prepare_autoliquidation_taxes(self):
        self.ensure_one()
        assert self.autoliquidation in ('intracom', 'extracom')
        ato = self.env["account.tax"]
        autoliq2categ = {
            'intracom': 'K',
            'extracom': 'G',
            }
        domain = [
            ('company_id', '=', self.company_id.id),
            ('type_tax_use', '=', 'purchase'),
            ('unece_type_code', '=', 'VAT'),
            ('amount_type', '=', 'percent'),
            ('amount', '>', 0),
            ('unece_categ_code', '=', autoliq2categ[self.autoliquidation]),
            ]
        if hasattr(ato, 'fr_vat_autoliquidation'):
            domain.append(('fr_vat_autoliquidation', '=', True))
        tax = ato.search(domain, order='amount desc', limit=1)
        if not tax:
            raise UserError(_(
                "Odoo could not find any %s auto-liquidation tax properly configured "
                "in company '%s'.") % (
                    self._fields['autoliquidation'].convert_to_export(
                        self.autoliquidation, self),
                    self.company_id.display_name))
        tax_ids = [tax.id]
        return tax_ids

    def _prepare_regular_taxes(self):
        # This method is inherited in l10n_fr_base_newgen_payment_card
        self.ensure_one()
        domain = [
            ('company_id', '=', self.company_id.id),
            ('type_tax_use', '=', 'purchase'),
            ('price_include', '=', False),
            ('amount_type', '=', 'percent'),
            ('amount', '>', 0),
            ('unece_type_code', '=', 'VAT'),
            ('unece_categ_code', '=', 'S'),
            ]
        taxes = self.env['account.tax'].search(domain)
        for tax in taxes:
            # self.vat_rate = 20.0
            if not float_compare(tax.amount, self.vat_rate, precision_digits=4):
                return [tax.id]
        raise UserError(_(
            "Failed to match regular purchase VAT tax %.2f %%.") % self.vat_rate)

    def _prepare_invoice(self):
        self.ensure_one()
        if self.force_invoice_date:
            date = self.force_invoice_date
        elif self.payment_date:
            date = self.payment_date
        else:
            date = self.date
        vat_compare = self.company_currency_id.compare_amounts(
            self.vat_company_currency, 0)
        total_compare = self.company_currency_id.compare_amounts(
            self.total_company_currency, 0)
        if vat_compare:
            if (
                    self.country_id and
                    self.company_id.country_id and
                    self.country_id not in self._countries_vat_refund()):
                raise UserError(_(
                    "The transaction '%s' is associated with country "
                    "'%s'. As we cannot refund VAT from this country, "
                    "the VAT amount of that transaction should be updated "
                    "to 0.")
                    % (self.name, self.country_id.name))
            if vat_compare != total_compare:
                raise UserError(_(
                    "The sign of the VAT amount (%s) should be the same as "
                    "the sign of the total amount (%s).")
                    % (self.vat_company_currency, self.total_company_currency))

            tax_ids = self._prepare_regular_taxes()
        elif self.autoliquidation in ('intracom', 'extracom'):
            tax_ids = self._prepare_autoliquidation_taxes()
        else:
            tax_ids = []
        if not self.description:
            raise UserError(_("Description is missing on transaction '%s'.") % self.display_name)
        if not self.expense_account_id:
            raise UserError(_(
                "Missing expense account on transaction '%s'.") % self.display_name)
        if not self.partner_id:
            raise UserError(_(
                "Missing partner on transaction '%s'.") % self.display_name)

        origin = self.name
        if self.receipt_number:
            origin = '%s (%s)' % (origin, self.receipt_number)
        amount_untaxed = self.total_company_currency * -1\
            - self.vat_company_currency * -1
        if total_compare > 0:  # refund
            move_type = 'in_refund'
            price_unit = amount_untaxed * -1
        else:  # invoice
            move_type = 'in_invoice'
            price_unit = amount_untaxed
        vals = {
            'partner_id': self.partner_id.id,
            'invoice_date': date,
            'invoice_date_due': date,
            'currency_id': self.company_id.currency_id.id,
            'move_type': move_type,
            'ref': self.name,
            'invoice_origin': origin,
            'invoice_line_ids': [Command.create({
                'display_type': 'product',
                'tax_ids': tax_ids,
                'account_id': self.expense_account_id.id,
                'analytic_distribution': self.analytic_distribution or False,
                'price_unit': price_unit,
                'name': self.description,
                'quantity': 1,
                })],
            }
        vals["attachment_ids"] = self._get_attachment_vals_list()
        return vals

    def _get_attachment_vals_list(self):
        self.ensure_one()
        attachment_vals_list = []
        url = self.image_url
        attachments = self.env['ir.attachment'].search([
            ('res_model', '=', self._name),
            ('res_id', '=',  self.id),
            ])
        if not url and not attachments and not self.receipt_lost:
            raise UserError(_(
                "Missing image URL and/or attachments on transaction %s. "
                "If you lost that receipt, you can mark this transaction "
                "as 'Receipt Lost'.")
                % self.name)

        if url:
            try:
                rimage = requests.get(url, timeout=TIMEOUT)
            except Exception as e:
                raise UserError(_(
                    "Failed to download the image of the receipt. "
                    "Error message: %s.") % e)
            if rimage.status_code != 200:
                raise UserError(_(
                    "Could not download the image of transaction %s "
                    "from URL %s (HTTP error code %s).")
                    % (self.name, url, rimage.status_code))
            image_binary = rimage.content
            file_extension = os.path.splitext(urlparse(url).path)[1]
            logger.debug('file_extension=%s', file_extension)
            if file_extension in ('.JPG', '.JPEG', '.jpg', '.jpeg'):
                logger.debug('Trying to rotate the JPG image %s', url)
                try:
                    image_binary = self._rotate_image(image_binary)
                    logger.info('JPEG file successfully rotated')
                except Exception as e:
                    logger.info('Failed to rotate the image. Error: %s', e)
                    pass
            filename = 'Receipt-%s%s' % (self.name, file_extension)
            attachment_vals_list.append(Command.create({
                'name': filename,
                'res_model': 'account.move',
                'raw': image_binary,
                }))
        for att in attachments:
            attachment_vals_list.append(Command.create({
                'name': att.name,
                'res_model': 'account.move',
                'raw': att.raw,
                }))
        return attachment_vals_list

    @api.model
    def _rotate_image(self, image_binary):
        image_original_file = io.BytesIO()
        image_original_file.write(image_binary)
        original_image = Image.open(image_original_file)
        rotated_image = ImageOps.exif_transpose(original_image)
        rotated_image_file = io.BytesIO()
        rotated_image.save(rotated_image_file, format='JPEG')
        rotated_image_binary = rotated_image_file.getvalue()
        return rotated_image_binary

    def check_existing_invoice(self):
        assert self.invoice_id
        # should not happen because domain blocks that
        if self.invoice_id.currency_id != self.company_currency_id:
            raise UserError(_(
                "For the moment, we don't support linking to an invoice "
                "in another currency than the company currency."))
        # should not happen because domain blocks that
        if self.invoice_id.payment_state != 'not_paid':
            raise UserError(_(
                "The transaction %s is linked to invoice %s "
                "which is not in unpaid state.")
                % (self.name, self.invoice_id.number))
        # should not happen because domain blocks that
        if self.invoice_id.move_type not in ('in_invoice', 'in_refund'):
            raise UserError(_(
                "The transaction %s is linked to invoice %s "
                "which is not a supplier invoice/refund!")
                % (self.name, self.invoice_id.name))
        # handled by onchange
        if self.partner_id != self.invoice_id.commercial_partner_id:
            raise UserError(_(
                "The transaction %s is linked to partner '%s' "
                "whereas the related invoice %s is linked to "
                "partner '%s'.") % (
                self.name, self.partner_id.display_name,
                self.invoice_id.display_name,
                self.invoice_id.commercial_partner_id.display_name))
        # TODO handle partial payments ?
        if self.company_currency_id.compare_amounts(
                self.invoice_id.amount_total_signed,
                self.total_company_currency):
            raise UserError(_(
                "The transaction %s is linked to the "
                "invoice/refund %s whose total amount is %s, "
                "but the amount of the transaction is %s.") % (
                self.name, self.invoice_id.name,
                format_amount(
                    self.env,
                    self.invoice_id.amount_total_signed * -1,
                    self.invoice_id.currency_id),
                format_amount(
                    self.env, self.total_company_currency, self.company_currency_id),
                ))

    def generate_invoice(self):
        self.ensure_one()
        assert self.transaction_type == 'expense', 'wrong transaction type'
        inv_vals = self._prepare_invoice()
        logger.debug('Payment card invoice inv_vals=%s', inv_vals)
        invoice = self.env['account.move'].create(inv_vals)
        trans_link = f"<a href='#' data-oe-model='{self._name}' data-oe-id='{self.id}'>{self.display_name}</a>"
        invoice.message_post(body=Markup(_("Invoice created from payment card transaction %s.") % trans_link))
        invoice.with_context(validate_analytic=True)._post(soft=False)
        self._post_process_invoice(invoice)
        return invoice

    def _post_process_invoice(self, invoice):
        cur = self.company_currency_id
        total_compare = cur.compare_amounts(
            self.total_company_currency, 0)
        amount_total = self.total_company_currency
        amount_tax = self.vat_company_currency
        if total_compare < 0:
            amount_total *= -1
            amount_tax *= -1
        # force total tax amount to match total amount
        invoice._check_total_amount(amount_total)
        if self.company_currency_id.compare_amounts(invoice.amount_total, amount_total):
            raise UserError(_(
                "Wrong total amount. Transaction total amount: %(trans_total)s. "
                "Vendor bill/refund total amount: %(invoice_total)s. This should never happen.",
                trans_total=format_amount(self.env, amount_total, cur),
                invoice_total=format_amount(self.env, invoice.amount_total, cur),
                )
                )
        if self.company_currency_id.compare_amounts(invoice.amount_tax, amount_tax):
            raise UserError(_(
                "Wrong tax amount. Maybe the code to force the tax amount didn't work. "
                "This should never happen."))

    def reconcile(self, bank_move, invoice):
        self.ensure_one()
        assert self.bank_counterpart_account_id
        assert bank_move
        assert invoice
        movelines_to_rec = self.env['account.move.line'].search([
            ('move_id', '=', bank_move.id),
            ('account_id', '=', self.bank_counterpart_account_id.id),
            ], limit=1)
        for line in invoice.line_ids:
            if line.account_id == self.bank_counterpart_account_id:
                movelines_to_rec += line
        movelines_to_rec.reconcile()
