# -*- coding: utf-8 -*-
# Copyright 2020 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MooncardTransaction(models.Model):
    _inherit = 'mooncard.transaction'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')

    @api.constrains('start_date', 'end_date')
    def _check_start_end_dates(self):
        for trans in self:
            if trans.start_date and not trans.end_date:
                raise ValidationError(_(
                    "Missing End Date for Mooncard transaction '%s'.")
                    % trans.display_name)
            if trans.end_date and not trans.start_date:
                raise ValidationError(_(
                    "Missing Start Date for Mooncard transaction '%s'.")
                    % trans.display_name)
            if trans.end_date and trans.start_date and \
                    trans.start_date > trans.end_date:
                raise ValidationError(_(
                    "Start Date should be before or be the same as "
                    "End Date for Mooncard transaction '%s'.")
                    % trans.display_name)

    def _prepare_invoice_import(self):
        parsed_inv = super(MooncardTransaction, self)._prepare_invoice_import()
        if self.start_date and self.end_date:
            parsed_inv['lines'][0].update({
                'date_start': self.start_date,
                'date_end': self.end_date,
                })
        return parsed_inv
