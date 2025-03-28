# Copyright 2020-2025 Akretion France (https://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.misc import format_date


class NewgenPaymentCardTransaction(models.Model):
    _inherit = 'newgen.payment.card.transaction'

    start_date = fields.Date()
    end_date = fields.Date()

    @api.constrains('start_date', 'end_date')
    def _check_start_end_dates(self):
        for trans in self:
            if trans.start_date and not trans.end_date:
                raise ValidationError(_(
                    "Missing End Date for transaction '%s'.")
                    % trans.display_name)
            if trans.end_date and not trans.start_date:
                raise ValidationError(_(
                    "Missing Start Date for transaction '%s'.")
                    % trans.display_name)
            if trans.end_date and trans.start_date and \
                    trans.start_date > trans.end_date:
                raise ValidationError(_(
                    "Start Date (%(start)s) should be before or be the same as "
                    "End Date (%(end)s) for transaction '%(trans)s'.",
                    trans=trans.display_name,
                    start=format_date(self.env, trans.start_date),
                    end=format_date(self.env, trans.end_date)))

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        if self.start_date and self.end_date:
            vals['invoice_line_ids'][0][2].update({
                'start_date': self.start_date,
                'end_date': self.end_date,
                })
        return vals
