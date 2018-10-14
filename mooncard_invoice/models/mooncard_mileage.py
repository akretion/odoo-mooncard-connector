# -*- coding: utf-8 -*-
# Copyright 2016-2018 Akretion France
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields, api, _
from odoo.tools.misc import formatLang
from babel.dates import format_date
import logging

logger = logging.getLogger(__name__)


class MooncardMileage(models.Model):
    _inherit = 'mooncard.mileage'

    invoice_id = fields.Many2one(
        'account.invoice', string='Invoice',
        states={'done': [('readonly', True)]})
    invoice_state = fields.Selection(
        related='invoice_id.state', readonly=True,
        string="Invoice State")
    state = fields.Selection(
        compute='_compute_state', store=True)

    # If I only write @api.depends('invoice_id'), then it is not invalidated
    # upon invoice deletion. That's why I use invoice_id.move_name
    @api.depends('invoice_id.move_name')
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
            if line.invoice_id:
                logger.warning(
                    'Skipping mooncard mileage %s which is already invoiced',
                    line.name)
                continue
            if line.partner_id in lines_by_partner:
                lines_by_partner[line.partner_id] += line
            else:
                lines_by_partner[line.partner_id] = line
        invoice_ids = []
        for lines in lines_by_partner.values():
            invoice = lines.generate_invoice_same_partner()
            invoice_ids.append(invoice.id)
        action = self.env['ir.actions.act_window'].for_xml_id(
            'account', 'action_invoice_tree2')
        action['views'] = False
        if len(invoice_ids) > 1:
            action['domain'] = "[('id', 'in', %s)]" % invoice_ids
        else:
            action['view_mode'] = 'form,tree,kanban,calendar,pivot,graph'
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
        name = _('%s %s: %s %s %s %s %d km (%s %s, %s CV, %s/km)') % (
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
            price_unit_formatted)
        return name

    def prepare_invoice(self):
        aio = self.env['account.invoice']
        date = False
        vals = {
            'partner_id': self[0].partner_id.id,
            'currency_id': self[0].company_id.currency_id.id,
            'type': 'in_invoice',
            'company_id': self[0].company_id.id,
            'origin': _('Mooncard Mileage'),
            'invoice_line_ids': [],
        }
        vals = aio.play_onchanges(vals, ['partner_id'])
        for line in self:
            if not date or date < line.date:
                date = line.date
            name = line.prepare_invoice_line_name()
            vals['invoice_line_ids'].append((0, 0, {
                'price_unit': line.amount,
                'name': name,
                'quantity': 1,
                'account_id': line.expense_account_id.id,
                'account_analytic_id': line.account_analytic_id.id or False,
                'origin': line.name,
                }))
        vals['date'] = date
        return vals

    def generate_invoice_same_partner(self):
        aio = self.env['account.invoice']
        vals = self.prepare_invoice()
        invoice = aio.with_context(type='in_invoice').create(vals)
        invoice.message_post(_(
            "Invoice created from Mooncard mileage."))
        self.write({
            'invoice_id': invoice.id,
            })
        return invoice
