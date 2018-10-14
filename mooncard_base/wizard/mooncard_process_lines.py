# -*- coding: utf-8 -*-
# Copyright 2016-2018 Akretion France
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class MooncardProcessLines(models.TransientModel):
    _name = 'mooncard.process.lines'
    _description = 'Process Mooncard Transactions'

    def process_lines(self):
        self.ensure_one()
        action = True
        if (
                self._context.get('active_model') in
                ('mooncard.transaction', 'mooncard.mileage')):
            lines = self.env[self._context['active_model']].browse(
                self._context['active_ids'])
            action = lines.process_line()
        return action
