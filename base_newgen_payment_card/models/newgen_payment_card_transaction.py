# Copyright 2016-2021 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare
from odoo.tools.misc import format_amount
import requests
import base64
import logging
from urllib.parse import urlparse
import os
import io
import logging
from unidecode import unidecode

MEANINGFUL_PARTNER_NAME_MIN_SIZE = 3

logger = logging.getLogger(__name__)

try:
    from PIL import Image, ImageOps
except ImportError:
    logger.debug('Cannot import Pillow version >= 6.0.0')


class NewgenPaymentCardTransaction(models.Model):
    _name = 'newgen.payment.card.transaction'
    _description = 'New-generation payment card transaction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'
    _check_company_auto = True

    name = fields.Char(string='Number', readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, readonly=True,
        default=lambda self: self.env.company)
    company_currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id',
        string="Company Currency", store=True)
    description = fields.Char(
        string='Description', states={'done': [('readonly', True)]})
    unique_import_id = fields.Char(
        string='Unique Identifier', readonly=True, copy=False)
    date = fields.Date(
        string='Bank Transaction Date', required=True, readonly=True,
        help="This is the date of the bank transaction written on the "
        "bank statement. It may be a few days after the payment date. "
        "It is used for the payment move.")
    payment_date = fields.Datetime(
        string='Payment Date', readonly=True,
        help="This is the real date of the payment. It may be a few days "
        "before the date of the bank transaction written on the bank "
        "statement. It is used for the supplier invoice.")
    force_invoice_date = fields.Date(
        string='Force Invoice Date', states={'done': [('readonly', True)]})
    card_id = fields.Many2one(
        'newgen.payment.card', string='Card', readonly=True,
        ondelete='restrict', check_company=True)
    expense_categ_name = fields.Char(
        string='Expense Category Name', readonly=True)
    expense_account_id = fields.Many2one(
        'account.account', states={'done': [('readonly', True)]},
        domain="[('deprecated', '=', False), ('company_id', '=', company_id), ('is_off_balance', '=', False)]",
        string='Expense Account', check_company=True)
    account_analytic_id = fields.Many2one(
        'account.analytic.account', string='Analytic Account',
        states={'done': [('readonly', True)]}, ondelete='restrict',
        check_company=True)
    country_id = fields.Many2one(
        'res.country', string='Country', readonly=True)
    vendor = fields.Char(string='Vendor', readonly=True)
    partner_id = fields.Many2one(
        'res.partner', string='Vendor Partner',
        domain=[('parent_id', '=', False)],
        states={'done': [('readonly', True)]}, ondelete='restrict',
        default=lambda self: self._default_partner(),
        help="By default, all transactions are linked to the generic "
        "supplier 'Misc Suppliers'. You can change the partner "
        "to the real partner of the transaction if you want, but it may not "
        "be worth the additionnal work.")
    transaction_type = fields.Selection([
        ('load', 'Load'),
        ('expense', 'Expense'),
        ], string='Transaction Type', readonly=True)
    vat_company_currency = fields.Monetary(
        string='VAT Amount',
        # not readonly, because accountant may have to change the value
        currency_field='company_currency_id',
        states={'done': [('readonly', True)]},
        help='VAT Amount in Company Currency')
    vat_rate = fields.Float(
        string='VAT Rate (%)', states={'done': [('readonly', True)]},
        digits=(16, 4),
        help='Main VAT rate of the transaction in percent.')
    total_company_currency = fields.Monetary(
        string='Total Amount in Company Currency',
        currency_field='company_currency_id', readonly=True)
    currency_id = fields.Many2one(
        'res.currency', string='Expense Currency', readonly=True)
    total_currency = fields.Monetary(
        string='Total Amount in Expense Currency', readonly=True,
        currency_field='currency_id')
    image_url = fields.Char(string='Image URL', readonly=True)
    receipt_lost = fields.Boolean(
        string='Receipt Lost', states={'done': [('readonly', True)]})
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ], string='State', default='draft', readonly=True)
    receipt_number = fields.Char(string='Receipt Number', readonly=True)
    bank_move_only = fields.Boolean(
        string="Generate Bank Move Only",
        states={'done': [('readonly', True)]},
        help="When you process a transaction on which this option is enabled, "
        "Odoo will only generate the move in the bank journal, it will not "
        "generate a supplier invoice/refund. This option is useful when you "
        "make a payment in advance and you haven't received the invoice yet.")
    invoice_id = fields.Many2one(
        'account.move', string='Invoice', check_company=True,
        states={'done': [('readonly', True)]})
    invoice_payment_state = fields.Selection(
        related='invoice_id.payment_state', string="Invoice Payment Status")
    reconcile_id = fields.Many2one(
        'account.full.reconcile', string="Reconcile",
        compute='_compute_reconcile_id', readonly=True)
    bank_counterpart_account_id = fields.Many2one(
        'account.account',
        domain="[('deprecated', '=', False), ('company_id', '=', company_id), ('is_off_balance', '=', False)]",
        states={'done': [('readonly', True)]}, required=True,
        # default value mostly used to load demo data
        default=lambda self: self.env['ir.property']._get(
            'property_account_payable_id', 'res.partner'),
        string="Counter-part of Bank Move", check_company=True)
    bank_move_id = fields.Many2one(
        'account.move', string="Bank Move", readonly=True, check_company=True)

    _sql_constraints = [(
        'unique_import_id',
        'unique(unique_import_id)',
        'A payment card transaction can be imported only once!')]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'newgen.payment.card.transaction')
        return super().create(vals)

    @api.depends('bank_move_id')
    def _compute_reconcile_id(self):
        for trans in self:
            reconcile_id = False
            if trans.bank_move_id:
                for line in trans.bank_move_id.line_ids:
                    if (
                            line.account_id ==
                            trans.bank_counterpart_account_id and
                            line.full_reconcile_id):
                        reconcile_id = line.full_reconcile_id.id
            trans.reconcile_id = reconcile_id

    @api.constrains('transaction_type', 'partner_id')
    def _check_transaction(self):
        for trans in self:
            if trans.transaction_type == 'expense' and not trans.partner_id:
                raise ValidationError(_(
                    "Partner missing on expense transaction '%s'.")
                    % trans.display_name)

    @api.model
    def _default_partner(self):
        return self.env.ref('base_newgen_payment_card.misc_supplier')

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
        for line in self:
            if line.state == 'done':
                raise UserError(_(
                    "Cannot delete transaction '%s' which is in "
                    "done state.") % line.name)
        return super().unlink()

    @api.onchange('invoice_id')
    def invoice_id_change(self):
        if self.invoice_id:
            self.partner_id = self.invoice_id.commercial_partner_id

    @api.onchange('partner_id')
    def partner_id_change(self):
        if self.transaction_type == 'expense' and self.partner_id:
            self.bank_counterpart_account_id =\
                self.partner_id.property_account_payable_id.id

    def process_line(self):
        for line in self:
            if line.state != 'draft':
                logger.warning(
                    'Skipping transaction %s which is not draft',
                    line.name)
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
                "Bank Journal not configured on payment card '%s'")
                % self.card_id.name)
        journal = self.card_id.journal_id
        if not self.bank_counterpart_account_id:
            raise UserError(_(
                "Counter-part of Bank Move is empty "
                "on transaction %s.") % self.name)
        transaction_type = dict(self.fields_get('transaction_type', 'selection')['transaction_type']['selection'])[self.transaction_type]
        ref = '%s (%s)' % (self.name, transaction_type)
        if self.transaction_type == 'expense':
            partner_id = self.partner_id.id
        elif self.transaction_type == 'load':
            partner_id = False
        mvals = {
            'journal_id': journal.id,
            'date': self.date,
            'ref': ref,
            'line_ids': [
                (0, 0, {
                    'account_id': journal.default_account_id.id,
                    'debit': debit,
                    'credit': credit,
                    'partner_id': partner_id,
                    }),
                (0, 0, {
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
        bank_move.action_post()
        return bank_move

    @api.model
    def _countries_vat_refund(self):
        return self.env.user.company_id.country_id

    def _prepare_invoice_import(self):
        self.ensure_one()
        precision = self.company_currency_id.rounding
        if self.force_invoice_date:
            date_dt = self.force_invoice_date
        elif self.payment_date:
            date_dt = self.payment_date
        else:
            date_dt = self.date
        date = fields.Date.to_string(date_dt)
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
            taxes.append({
                'amount_type': 'percent',
                'amount': self.vat_rate,
                'unece_type_code': 'VAT',
                'unece_categ_code': 'S',
                })
        if not self.description:
            raise UserError(_("Description is missing on transaction %s.")
                % self.name)
        origin = self.name
        if self.receipt_number:
            origin = '%s (%s)' % (origin, self.receipt_number)
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
                'uom': {'recordset': self.env.ref('uom.product_uom_unit')},
                }],
            'origin': origin,
            }
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

        parsed_inv['attachments'] = {}
        if url:
            try:
                rimage = requests.get(url)
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
            image_b64 = base64.encodebytes(image_binary)
            parsed_inv['attachments'] = {filename: image_b64}
        if attachments:
            for att in attachments:
                parsed_inv['attachments'][att.name] = att.datas
        # TODO: delete attachments on transaction once invoice is created ?
        return parsed_inv

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
        if float_compare(
                self.invoice_id.amount_total_signed,
                self.total_company_currency,
                precision_rounding=self.company_currency_id.rounding):
            raise UserError(_(
                "The transaction %s is linked to the "
                "invoice/refund %s whose total amount is %s, "
                "but the amount of the transaction is %s.") % (
                self.name, self.invoice_id.name,
                format_amount(
                    self.env, self.invoice_id.amount_total_signed * -1, self.invoice_id.currency_id),
                format_amount(
                    self.env, self.total_company_currency, self.company_currency_id),
                ))

    def generate_invoice(self):
        self.ensure_one()
        assert self.transaction_type == 'expense', 'wrong transaction type'
        aiio = self.env['account.invoice.import']
        precision = self.company_currency_id.rounding
        parsed_inv = self._prepare_invoice_import()
        logger.debug('Payment card invoice import parsed_inv=%s', parsed_inv)
        parsed_inv = aiio.pre_process_parsed_inv(parsed_inv)
        if not self.expense_account_id:
            raise UserError(_(
                "Missing expense account on transaction %s") % self.name)
        import_config = {
            'invoice_line_method': 'nline_no_product',
            'account': self.expense_account_id,
            'account_analytic': self.account_analytic_id or False,
            }
        invoice = aiio.create_invoice(
            parsed_inv, import_config=import_config, origin='Mooncard connector')
        invoice.message_post(
            body=_("Invoice created from payment card transaction %s.")
            % self.name)
        invoice.action_post()
        assert float_compare(
            invoice.amount_tax, abs(self.vat_company_currency),
            precision_rounding=precision) == 0, 'bug on VAT'
        return invoice

    def reconcile(self, bank_move, invoice):
        self.ensure_one()
        assert self.bank_counterpart_account_id
        assert bank_move
        assert invoice
        assert not self.reconcile_id, 'already has a reconcile mark'
        movelines_to_rec = self.env['account.move.line'].search([
            ('move_id', '=', bank_move.id),
            ('account_id', '=', self.bank_counterpart_account_id.id),
            ], limit=1)
        for line in invoice.line_ids:
            if line.account_id == self.bank_counterpart_account_id:
                movelines_to_rec += line
        movelines_to_rec.reconcile()
        return movelines_to_rec[0].full_reconcile_id

    @api.model
    def _prepare_import_speeddict(self):
        """Used in provided-specific modules"""
        company = self.env.user.company_id
        bdio = self.env['business.document.import']
        speeddict = {
            'tokens': {}, 'accounts': {}, 'analytic': {},
            'countries': {}, 'currencies': {}, 'mapping': {}}

        token_res = self.env['newgen.payment.card'].search_read(
            [('company_id', '=', company.id)], ['name'])
        for token in token_res:
            speeddict['tokens'][token['name']] = token['id']

        speeddict['accounts'] = bdio._prepare_account_speed_dict()

        analytic_res = self.env['account.analytic.account'].search_read(
            [('company_id', '=', company.id), ('code', '!=', False)], ['code'])
        for analytic in analytic_res:
            analytic_code = analytic['code'].strip().lower()
            speeddict['analytic'][analytic_code] = analytic['id']

        countries = self.env['res.country'].search_read(
            [('code', '!=', False)], ['code'])
        for country in countries:
            speeddict['countries'][country['code'].strip()] = country['id']

        currencies = self.env['res.currency'].with_context(
            active_test=False).search_read([], ['name'])
        for curr in currencies:
            speeddict['currencies'][curr['name']] = curr['id']
        npcto = self.env['newgen.payment.card.transaction']
        map_res = self.env['newgen.payment.card.account.mapping'].search_read(
            [('company_id', '=', company.id)])
        for map_entry in map_res:
            speeddict['mapping'][
                (map_entry['card_id'][0],
                 map_entry['expense_account_id'][0])] =\
                map_entry['force_expense_account_id'][0]
        if not company.transfer_account_id:
            raise UserError(_(
                "Missing 'Internal Bank Transfer Account' on company '%s'.")
                % company.display_name)
        speeddict['transfer_account_id'] = company.transfer_account_id.id
        default_partner = self._default_partner()
        if default_partner.parent_id:
            raise UserError(_(
                "The default partner (%s) should be a parent partner.")
                % default_partner.display_name)
        speeddict['default_partner_id'] = default_partner.id
        speeddict['partner'] = []
        specific_partner_existing_transactions = npcto.search_read([
            ('state', '=', 'done'),
            ('transaction_type', '=', 'expense'),
            ('vendor', '!=', False),
            ('partner_id', '!=', False),
            ('partner_id', '!=', speeddict['default_partner_id'])],
            ['vendor', 'partner_id'])
        for trans in specific_partner_existing_transactions:
            speeddict['partner'].append((
                unidecode(trans['vendor']).strip().upper(),
                trans['partner_id'][0]))
        partners = self.env['res.partner'].search_read(
            [('parent_id', '=', False)], ['name'])
        for partner in partners:
            partner_name = unidecode(partner['name'].strip().upper())
            if len(partner_name) >= MEANINGFUL_PARTNER_NAME_MIN_SIZE:
                speeddict['partner'].append((partner_name, partner['id']))
        speeddict['default_vat_rate'] = 0
        if (
                company.account_purchase_tax_id and
                company.account_purchase_tax_id.amount_type == 'percent' and
                float_compare(
                    company.account_purchase_tax_id.amount, 0,
                    precision_digits=4) > 0):
            speeddict['default_vat_rate'] =\
                company.account_purchase_tax_id.amount
        return speeddict
