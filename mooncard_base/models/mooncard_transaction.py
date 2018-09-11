# -*- coding: utf-8 -*-
# © 2016 Akretion (Alexis de Lattre <alexis.delattre@akretion.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import models, fields, api, _
from openerp.exceptions import Warning as UserError
import openerp.addons.decimal_precision as dp


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
        string="Company Currency")
    description = fields.Char(
        string='Description', states={'done': [('readonly', True)]})
    unique_import_id = fields.Char(
        string='Unique Identifier', readonly=True, copy=False)
    date = fields.Datetime(
        string='Date', required=True, readonly=True,
        help="This is the date of the bank transaction. It may be a few "
        "days after the payment date.")
    payment_date = fields.Datetime(string='Payment Date', readonly=True)
    card_id = fields.Many2one(
        'mooncard.card', string='Moon Card', readonly=True,
        ondelete='restrict')
    expense_categ_name = fields.Char(
        string='Expense Category Name', readonly=True)
    product_id = fields.Many2one(
        'product.product', string='[OLD] Expense Product', ondelete='restrict',
        states={'done': [('readonly', True)]})
    expense_account_id = fields.Many2one(
        'account.account', states={'done': [('readonly', True)]},
        domain=[('type', 'not in', ('view', 'closed', 'consolidation'))],
        string='Expense Account')
    account_analytic_id = fields.Many2one(
        'account.analytic.account', string='Analytic Account',
        domain=[('type', '!=', 'view')],
        states={'done': [('readonly', True)]}, ondelete='restrict')
    country_id = fields.Many2one(
        'res.country', string='Country', readonly=True)
    merchant = fields.Char(string='Merchant', readonly=True)
    transaction_type = fields.Selection([
        ('load', 'Load'),
        ('presentment', 'Expense'),
        ('authorization', 'Authorization'),  # not needed as we now
                                             # use bank statements
        ], string='Transaction Type', readonly=True)
    vat_company_currency = fields.Float(
        string='VAT Amount',
        # not readonly, because accountant may have to change the value
        digits=dp.get_precision('Account'),
        states={'done': [('readonly', True)]},
        help='VAT Amount in Company Currency')
    fr_vat_20_amount = fields.Float(
        string='VAT Amount 20.0 %', states={'done': [('readonly', True)]},
        help='20.0 % French VAT Amount in Company Currency')
    fr_vat_10_amount = fields.Float(
        string='VAT Amount 10.0 %', states={'done': [('readonly', True)]},
        help='10.0 % French VAT Amount in Company Currency')
    fr_vat_5_5_amount = fields.Float(
        string='VAT Amount 5.5 %', states={'done': [('readonly', True)]},
        help='5.5 % French VAT Amount in Company Currency')
    fr_vat_2_1_amount = fields.Float(
        string='VAT Amount 2.1 %', states={'done': [('readonly', True)]},
        help='2.1 % French VAT Amount in Company Currency')
    total_company_currency = fields.Float(
        string='Total Amount in Company Currency',
        digits=dp.get_precision('Account'), readonly=True)
    currency_id = fields.Many2one(
        'res.currency', string='Expense Currency', readonly=True)
    total_currency = fields.Float(
        string='Total Amount in Expense Currency', readonly=True)
    image_url = fields.Char(string='Image URL', readonly=True)
    receipt_lost = fields.Boolean(
        string='Receipt Lost', states={'done': [('readonly', True)]})
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ], string='State', default='draft', readonly=True)
    receipt_number = fields.Char(string='Receipt Number', readonly=True)

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

    @api.multi
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

    @api.multi
    def unlink(self):
        for line in self:
            if line.state == 'done':
                raise UserError(_(
                    "Cannot delete Mooncard transaction '%s' which is in "
                    "done state.") % line.name)
        return super(MooncardTransaction, self).unlink()

    @api.multi
    def process_line(self):
        raise UserError(_(
            "You must install the module mooncard_invoice or "
            "mooncard_expense"))
