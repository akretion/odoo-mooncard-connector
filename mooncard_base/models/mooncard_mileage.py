# -*- coding: utf-8 -*-
# Copyright 2018 Akretion France
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields, api, _
import odoo.addons.decimal_precision as dp
from odoo.exceptions import UserError


class MooncardMileage(models.Model):
    _name = 'mooncard.mileage'
    _description = 'Mooncard Kilometer Expense'
    _order = 'date desc'

    name = fields.Char(string='Number', readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, readonly=True,
        default=lambda self: self.env['res.company']._company_default_get(
            'mooncard.transaction'))
    company_currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True,
        string="Company Currency", store=True)
    partner_id = fields.Many2one(
        'res.partner', string='Partner',
        ondelete='restrict', states={'done': [('readonly', True)]})
    description = fields.Char(
        string='Description', states={'done': [('readonly', True)]})
    unique_import_id = fields.Char(
        string='Unique Identifier', readonly=True, copy=False)
    date = fields.Date(
        string='Date', required=True, readonly=True)
    departure = fields.Char(
        string='Departure', states={'done': [('readonly', True)]})
    arrival = fields.Char(
        string='Arrival', states={'done': [('readonly', True)]})
    trip_type = fields.Selection([
        ('oneway', 'One-Way'),
        ('roundtrip', 'Round Trip'),
        ], string='Trip Type', states={'done': [('readonly', True)]})
    expense_account_id = fields.Many2one(
        'account.account', states={'done': [('readonly', True)]},
        domain=[('deprecated', '=', False)],
        string='Expense Account')
    account_analytic_id = fields.Many2one(
        'account.analytic.account', string='Analytic Account',
        states={'done': [('readonly', True)]}, ondelete='restrict')
    km = fields.Integer(states={'done': [('readonly', True)]})
    price_unit = fields.Float(
        string='Unit Price', required=True,
        digits=dp.get_precision('Mileage Price'),
        states={'done': [('readonly', True)]})
    car_name = fields.Char(
        string='Car', states={'done': [('readonly', True)]})
    car_plate = fields.Char(
        string='Car Plate', states={'done': [('readonly', True)]})
    car_fiscal_power = fields.Char(
        string='Car Fiscal Power', states={'done': [('readonly', True)]})
    amount = fields.Monetary(
        string='Total Amount', compute='_compute_amount', store=True,
        currency_field='company_currency_id', readonly=True,
        help="Total amount in company currency")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ], string='State', default='draft', readonly=True)

    _sql_constraints = [(
        'unique_import_id',
        'unique(unique_import_id)',
        'A mooncard mileage can be imported only once!')]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'mooncard.mileage')
        return super(MooncardMileage, self).create(vals)

    def unlink(self):
        for line in self:
            if line.state == 'done':
                raise UserError(_(
                    "Cannot delete Mooncard mileage expense '%s' which is in "
                    "done state.") % line.name)
        return super(MooncardMileage, self).unlink()

    @api.depends('price_unit', 'km')
    def _compute_amount(self):
        for mileage in self:
            mileage.amount = mileage.price_unit * mileage.km

    def process_line(self):
        raise UserError(_(
            "You must install the module mooncard_invoice or "
            "mooncard_expense"))
