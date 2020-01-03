# Copyright 2016-2019 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class NewgenPaymentCardProcessLines(models.TransientModel):
    _name = 'newgen.payment.card.process.lines'
    _description = 'Process new-generation payment card transactions'

    def process_lines(self):
        self.ensure_one()
        action = True
        if (
                self._context.get('active_model') in
                ('newgen.payment.card.transaction', 'mooncard.mileage')):
            lines = self.env[self._context['active_model']].browse(
                self._context['active_ids'])
            action = lines.process_line()
        return action
