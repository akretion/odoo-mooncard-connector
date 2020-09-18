# -*- coding: utf-8 -*-
# © 2016-2017 Akretion (Alexis de Lattre <alexis.delattre@akretion.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_compare
from unidecode import unidecode
import logging
import pycountry
from odoo.addons.mooncard_base.models.company import MEANINGFUL_PARTNER_NAME_MIN_SIZE

logger = logging.getLogger(__name__)


class MooncardTransaction(models.Model):
    _name = 'mooncard.transaction'
    _description = 'Mooncard Transaction'
    _order = 'date desc'

    name = fields.Char(string='Number', readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, readonly=True,
        default=lambda self: self.env['res.company']._company_default_get(
            'mooncard.transaction'))
    company_currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True,
        string="Company Currency", store=True)
    description = fields.Char(
        string='Description', states={'done': [('readonly', True)]})
    attendees = fields.Char(
        string='Attendees', states={'done': [('readonly', True)]})
    unique_import_id = fields.Char(
        string='Unique Identifier', readonly=True, copy=False,
        required=True)
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
    card_id = fields.Many2one(
        'mooncard.card', string='Moon Card', readonly=True,
        ondelete='restrict')
    expense_categ_name = fields.Char(
        string='Expense Category Name', readonly=True)
    product_id = fields.Many2one(  # Field to remove in v12
        'product.product', string='[OLD] Expense Product', ondelete='restrict',
        states={'done': [('readonly', True)]})
    expense_account_id = fields.Many2one(
        'account.account', states={'done': [('readonly', True)]},
        domain=[('deprecated', '=', False)],
        string='Expense Account')
    account_analytic_id = fields.Many2one(
        'account.analytic.account', string='Analytic Account',
        states={'done': [('readonly', True)]}, ondelete='restrict')
    country_id = fields.Many2one(
        'res.country', string='Country', readonly=True)
    merchant = fields.Char(string='Merchant', readonly=True)
    partner_id = fields.Many2one(
        'res.partner', string='Vendor', required=True,
        domain=[('supplier', '=', True), ('parent_id', '=', False)],
        states={'done': [('readonly', True)]}, ondelete='restrict',
        default=lambda self: self._default_partner(),
        help="By default, all transactions are linked to the generic "
        "supplier 'Mooncard Misc Suppliers'. You can change the partner "
        "to the real partner of the transaction if you want, but it may not "
        "be worth the additionnal work.")
    # partner_id and bank_counterpart_account_id were initially in
    # mooncard_invoice, but I decided to move all the fields that are
    # needed for import in mooncard_base.
    # The definition in the view may still be in mooncard_invoice
    # This "split" issue has been solved in v12
    transaction_type = fields.Selection([
        ('load', 'Load'),
        ('presentment', 'Expense'),
        ('authorization', 'Authorization'),  # not needed as we now
                                             # use bank statements
        ], string='Transaction Type', readonly=True)
    vat_company_currency = fields.Monetary(
        string='VAT Amount',
        # not readonly, because accountant may have to change the value
        currency_field='company_currency_id',
        states={'done': [('readonly', True)]},
        help='VAT Amount in Company Currency')
    fr_vat_20_amount = fields.Monetary(
        string='VAT Amount 20.0 %', currency_field='company_currency_id',
        states={'done': [('readonly', True)]},
        help='20.0 % French VAT Amount in Company Currency')
    fr_vat_10_amount = fields.Monetary(
        string='VAT Amount 10.0 %', currency_field='company_currency_id',
        states={'done': [('readonly', True)]},
        help='10.0 % French VAT Amount in Company Currency')
    fr_vat_5_5_amount = fields.Monetary(
        string='VAT Amount 5.5 %', currency_field='company_currency_id',
        states={'done': [('readonly', True)]},
        help='5.5 % French VAT Amount in Company Currency')
    fr_vat_2_1_amount = fields.Monetary(
        string='VAT Amount 2.1 %', currency_field='company_currency_id',
        states={'done': [('readonly', True)]},
        help='2.1 % French VAT Amount in Company Currency')
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
    bank_counterpart_account_id = fields.Many2one(
        'account.account', domain=[('deprecated', '=', False)],
        states={'done': [('readonly', True)]}, required=True,
        string="Counter-part of Bank Move")

    _sql_constraints = [(
        'unique_import_id',
        'unique(unique_import_id)',
        'A mooncard transaction can be imported only once!')]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'mooncard.transaction')
        return super(MooncardTransaction, self).create(vals)

    def open_image_url(self):
        if not self.image_url:
            raise UserError(_(
                "Missing image URL for mooncard transaction %s.") % self.name)
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
                    "Cannot delete Mooncard transaction '%s' which is in "
                    "done state.") % line.name)
        return super(MooncardTransaction, self).unlink()

    def process_line(self):
        raise UserError(_(
            "You must install the module mooncard_invoice or "
            "mooncard_expense"))

    @api.model
    def _default_partner(self):
        return self.env.ref('mooncard_base.mooncard_supplier')

    # IMPORT CODE
    @api.model
    def _prepare_transaction(self, line, speeddict, action='create'):
        bdio = self.env['business.document.import']
        account_analytic_id = account_id = False
        # convert to float
        float_fields = [
            'vat_eur', 'amount_eur', 'amount_currency',
            'vat_20_id', 'vat_10_id', 'vat_55_id', 'vat_21_id']
        for float_field in float_fields:
            if line.get(float_field):
                try:
                    line[float_field] = float(line[float_field])
                except Exception:
                    raise UserError(_(
                        "Cannot convert float field '%s' with value '%s'.")
                        % (float_field, line.get(float_field)))
            else:
                line[float_field] = 0.0
        total_vat_rates = line['vat_20_id'] + line['vat_10_id'] +\
            line['vat_55_id'] + line['vat_21_id']
        if float_compare(line['vat_eur'], total_vat_rates, precision_digits=2):
            logger.warning(
                "In the Mooncard CSV file: for transaction ID '%s' "
                "the column 'vat_eur' (%.2f) doesn't have the same value "
                "as the sum of the 4 columns per VAT rate (%.2f). Check "
                "that it is foreign VAT.",
                line['id'], line['vat_eur'], total_vat_rates)
        if line.get('charge_account'):
            account = bdio._match_account(
                {'code': line['charge_account']}, [],
                speed_dict=speeddict['accounts'])
            account_id = account.id
        if line.get('analytic_code_1'):
            account_analytic_id = speeddict['analytic'].get(
                line['analytic_code_1'].lower())
        ttype2odoo = {
            'P': 'presentment',
            'L': 'load',
            }
        if line.get('transaction_type') not in ttype2odoo:
            raise UserError(_(
                "Wrong transaction type '%s'. The only possible values are "
                "'P' (presentment) or 'L' (load).")
                % line.get('transaction_type'))
        transaction_type = ttype2odoo[line['transaction_type']]
        vals = {
            'transaction_type': transaction_type,
            'description': line.get('title'),
            'attendees': line.get('attendees'),
            'expense_categ_name': line.get('expense_category_name'),
            'expense_account_id': account_id,
            'account_analytic_id': account_analytic_id,
            'vat_company_currency': line['vat_eur'],
            'fr_vat_20_amount': line['vat_20_id'],
            'fr_vat_10_amount': line['vat_10_id'],
            'fr_vat_5_5_amount': line['vat_55_id'],
            'fr_vat_2_1_amount': line['vat_21_id'],
            'image_url': line.get('attachment'),
            'receipt_number': line.get('receipt_code'),
            'company_id': speeddict['company_id'],
            }

        card_id = False
        if line.get('card_token'):
            token = line['card_token']
            card_id = speeddict['tokens'].get(token)
            if not card_id:
                card = self.env['mooncard.card'].sudo().create({
                    'name': token,
                    'company_id': speeddict['company_id'],
                    })
                speeddict['tokens'][token] = card.id
                logger.info(
                    'New mooncard.card created token %s ID %s',
                    token, card.id)
            tuple_match = (card_id, vals.get('expense_account_id'))
            if tuple_match in speeddict['mapping']:
                vals['expense_account_id'] = speeddict['mapping'][tuple_match]

        if transaction_type == 'load':
            vals['bank_counterpart_account_id'] =\
                speeddict['transfer_account_id']
        elif transaction_type == 'presentment':
            merchant = line.get('supplier') and line['supplier'].strip()
            partner_id = speeddict['default_partner_id']
            if merchant and len(merchant) >= MEANINGFUL_PARTNER_NAME_MIN_SIZE:
                merchant_match = unidecode(merchant.upper())
                for speed_entry in speeddict['partner']:
                    partner_match = self.partner_match(
                        merchant_match, speed_entry)
                    if partner_match:
                        partner_id = partner_match
            partner = self.env['res.partner'].browse(partner_id)
            vals.update({
                'partner_id': partner_id,
                'bank_counterpart_account_id':
                partner.property_account_payable_id.id,
                })

        if action == 'update':
            return vals
        # Continue with fields required for create
        country_id = False
        if line.get('country_code') and len(line['country_code']) == 3:
            logger.debug(
                'search country with code %s with pycountry',
                line['country_code'])
            pcountry = pycountry.countries.get(alpha_3=line['country_code'])
            if pcountry and pcountry.alpha_2:
                country_id = speeddict['countries'].get(pcountry.alpha_2)
        currency_id = speeddict['currencies'].get(
            line.get('original_currency'))
        payment_date = False
        if (
                transaction_type == 'presentment' and
                line.get('date_authorization')):
            payment_date = self.env['res.company'].convert_datetime_to_utc(
                line['date_authorization'])

        vals.update({
            'unique_import_id': line.get('id'),
            'date': line['date_transaction'] and line['date_transaction'][:10],
            'payment_date': payment_date,
            'card_id': card_id,
            'country_id': country_id,
            'merchant': line.get('supplier') and line['supplier'].strip(),
            'total_company_currency': line['amount_eur'],
            'total_currency': line['amount_currency'],
            'currency_id': currency_id,
        })
        return vals

    @api.model
    def partner_match(self, merchant, speed_entry):
        if speed_entry[0] in merchant:
            return speed_entry[1]
        else:
            return False
