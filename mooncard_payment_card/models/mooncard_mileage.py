# Copyright 2018-2021 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from babel.dates import format_date
from odoo.tools.misc import formatLang
from odoo.exceptions import UserError
import logging
logger = logging.getLogger(__name__)


class MooncardMileage(models.Model):
    _name = 'mooncard.mileage'
    _inherit = "analytic.mixin"
    _description = 'Mooncard Kilometer Expense'
    _order = 'date desc'
    _check_company_auto = True

    name = fields.Char(string='Number', readonly=True, default=lambda self: _("New"))
    company_id = fields.Many2one(
        'res.company', required=True, readonly=True,
        default=lambda self: self.env.company)
    company_currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id',
        string="Company Currency", store=True)
    partner_id = fields.Many2one(
        'res.partner',
        ondelete='restrict', states={'done': [('readonly', True)]})
    description = fields.Char(states={'done': [('readonly', True)]})
    unique_import_id = fields.Char(
        string='Unique Identifier', readonly=True, copy=False)
    date = fields.Date(required=True, states={'done': [('readonly', True)]})
    departure = fields.Char(states={'done': [('readonly', True)]})
    arrival = fields.Char(states={'done': [('readonly', True)]})
    trip_type = fields.Selection([
        ('oneway', 'One-Way'),
        ('roundtrip', 'Round Trip'),
        ], states={'done': [('readonly', True)]})
    expense_account_id = fields.Many2one(
        'account.account', states={'done': [('readonly', True)]},
        domain="[('deprecated', '=', False), ('company_id', '=', company_id)]",
        string='Expense Account', check_company=True)

    km = fields.Integer(states={'done': [('readonly', True)]})
    price_unit = fields.Float(
        string='Unit Price', required=True,
        digits='Mileage Price', states={'done': [('readonly', True)]})
    car_name = fields.Char(
        string='Car', states={'done': [('readonly', True)]})
    car_plate = fields.Char(states={'done': [('readonly', True)]})
    car_fiscal_power = fields.Char(states={'done': [('readonly', True)]})
    amount = fields.Monetary(
        string='Total Amount', compute='_compute_amount', store=True,
        currency_field='company_currency_id', readonly=True,
        help="Total amount in company currency")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ], compute='_compute_state', store=True)
    invoice_id = fields.Many2one(
        'account.move', string='Vendor Bill', check_company=True,
        states={'done': [('readonly', True)]})
    invoice_payment_state = fields.Selection(
        related='invoice_id.payment_state', readonly=True,
        string="Vendor Bill Payment State")

    _sql_constraints = [(
        'unique_import_id',
        'unique(unique_import_id)',
        'A mooncard mileage can be imported only once!')]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'company_id' in vals:
                self = self.with_company(vals['company_id'])
            if vals.get('name', _("New")) == _("New"):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'mooncard.mileage', sequence_date=vals.get('date')) or _("New")
        return super().create(vals_list)

    def unlink(self):
        for line in self:
            if line.state == 'done':
                raise UserError(_(
                    "Cannot delete Mooncard mileage expense '%s' which is in "
                    "done state.") % line.name)
        return super().unlink()

    @api.depends('price_unit', 'km')
    def _compute_amount(self):
        for mileage in self:
            mileage.amount = mileage.price_unit * mileage.km

    @api.depends("expense_account_id", "partner_id")
    def _compute_analytic_distribution(self):
        for mileage in self:
            distrib = self.env[
                "account.analytic.distribution.model"
            ]._get_distribution(
                {
                    "partner_id": mileage.partner_id.id,
                    "partner_category_id": mileage.partner_id.category_id.ids,
                    "account_prefix": mileage.expense_account_id.code,
                    "company_id": mileage.company_id.id,
                }
            )
            mileage.analytic_distribution = distrib or mileage.analytic_distribution

    # If I only write @api.depends('invoice_id'), then it is not invalidated
    # upon invoice deletion. That's why I use invoice_id.name
    @api.depends('invoice_id.name')
    def _compute_state(self):
        for line in self:
            line.state = line.invoice_id and 'done' or 'draft'

    def process_line(self):
        lines_by_partner = {}  # key = partner, value = lines
        for line in self:
            if line.state != 'draft':
                logger.warning(
                    'Skipping mooncard mileage %s which is not draft',
                    line.name)
                continue
            if line.partner_id in lines_by_partner:
                lines_by_partner[line.partner_id] += line
            else:
                lines_by_partner[line.partner_id] = line
        if not lines_by_partner:
            raise UserError(_("Selected mileages are already processed."))
        invoice_ids = []
        for lines in lines_by_partner.values():
            invoice = lines.generate_invoice_same_partner()
            invoice_ids.append(invoice.id)
        action = self.env['ir.actions.actions']._for_xml_id(
            'account.action_move_in_invoice_type')
        action['views'] = False
        action['view_id'] = False
        if len(invoice_ids) > 1:
            action['domain'] = "[('id', 'in', %s)]" % invoice_ids
        else:
            action['view_mode'] = 'form,tree,kanban'
            action['res_id'] = invoice_ids[0]
        return action

    def prepare_invoice_line_name(self):
        self.ensure_one()
        triptype_key2label = dict(self.fields_get(
            'trip_type', 'selection')['trip_type']['selection'])
        date_formatted = self.date
        if self.date:
            date_dt = fields.Date.from_string(self.date)
            date_formatted = format_date(
                date_dt, format='short', locale=self.env.user.lang or 'fr_FR')
        price_unit_formatted = formatLang(
            self.env, self.price_unit, dp='Mileage Price',
            monetary=True, currency_obj=self.company_id.currency_id)
        name = _('%s %s: %s %s %s %s %d km\n%s %s, %s CV, %s/km\nRef: %s') % (
            date_formatted,
            self.description,
            self.trip_type and triptype_key2label[self.trip_type] or False,
            self.departure,
            self.trip_type == 'roundtrip' and '<->' or '->',
            self.arrival,
            self.km,
            self.car_name,
            self.car_plate,
            self.car_fiscal_power,
            price_unit_formatted,
            self.name)
        return name

    def prepare_invoice(self):
        date = False
        vals = {
            'partner_id': self[0].partner_id.id,
            'currency_id': self[0].company_id.currency_id.id,
            'move_type': 'in_invoice',
            'company_id': self[0].company_id.id,
            'invoice_origin': _('Mooncard Mileage'),
            'invoice_line_ids': [],
        }
        for line in self:
            if not date or date < line.date:
                date = line.date
            assert line.company_id.id == vals["company_id"]
            name = line.prepare_invoice_line_name()
            vals['invoice_line_ids'].append((0, 0, {
                'price_unit': line.amount,
                'name': name,
                'quantity': 1,
                'account_id': line.expense_account_id.id,
                'analytic_distribution': line.analytic_distribution or False,
                'tax_ids': False,
                }))
        vals['invoice_date'] = date
        return vals

    def generate_invoice_same_partner(self):
        amo = self.env['account.move']
        vals = self.prepare_invoice()
        invoice = amo.create(vals)
        invoice.with_context(validate_analytic=True)._post(soft=False)
        invoice.message_post(body=_(
            "Invoice created from Mooncard mileage."))
        self.write({
            'invoice_id': invoice.id,
            })
        return invoice
