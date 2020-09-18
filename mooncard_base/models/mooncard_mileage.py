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
        string='Unique Identifier', readonly=True, copy=False, required=True)
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

    @api.model
    def _prepare_mileage(self, line, speeddict):
        bdio = self.env['business.document.import']
        account_analytic_id = False
        if line['currency'] != speeddict['company_currency']:
            raise UserError(_(
                "The currency of the mileage is %s whereas "
                "the company currency is %s.") % (
                    line['currency'], speeddict['company_currency']))
        account_analytic_id = account_id = trip_type = False
        if line.get('expense_category_id'):
            if line['expense_category_id'] not in speeddict['api_exp_categ']:
                raise UserError(
                    "The expense category '%s' is unknown. This should "
                    "never happen." % line['expense_category_id'])
            account_code = speeddict['api_exp_categ'][line['expense_category_id']]['code']
            account = bdio._match_account(
                {'code': account_code}, [],
                speed_dict=speeddict['accounts'])
            account_id = account.id

        # convert to float/int
        # line['price_unit'] = float(line[u'Barême kilométrique'])
        # if line.get('Codes analytiques'):
        #    account_analytic_id = speeddict['analytic'].get(
        #        line['Codes analytiques'].lower())
        typedict = {
            'single': 'oneway',
            'return': 'roundtrip',
            }
        if line['source']['distance_type'] not in typedict:
            raise UserError(_(
                "Wrong value '%s' for distance type. This should never happen.")
                % line['source']['distance_type'])

        trip_type = typedict[line['source']['distance_type']]
        date = self.env['res.company'].convert_datetime_to_utc(
            line['at'])

        if line['user_profile_id'] not in speeddict['api_users']:
            raise UserError(
                "The user profile UUID %s is unkown. This should never happen."
                % line['user_profile_id'])
        email = speeddict['api_users'][line['user_profile_id']]
        if not email:
            raise UserError(_('Missing email'))
        email = email.strip().lower()
        if email not in speeddict['partner_mail']:
            # for test
            # partner = self.env['res.partner'].create({'name': 'tutu', 'email': email})
            # speeddict['partner_mail'][email] = partner.id
            raise UserError(_(
                "No partner with email '%s' found") % email)
        partner_id = speeddict['partner_mail'][email]
        vals = {
            'unique_import_id': line['id'],
            'partner_id': partner_id,
            'km': line['source']['distance'],
            # 'price_unit': line['price_unit'],
            'price_unit': 0.58,  # TODO update
            'date': date,
            'description': line['title'],
            # 'car_name': line[u'Véhicule'],
            # 'car_plate': line.get(u"Immatriculation"),
            # 'car_fiscal_power': line.get(u'Puissance fiscale'),
            'departure': line['source']['start_point'],
            'arrival': line['source']['end_point'],
            'trip_type': trip_type,
            'account_analytic_id': account_analytic_id,
            'expense_account_id': account_id,
            }
        return vals
