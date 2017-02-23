# -*- coding: utf-8 -*-
# © 2016-2017 Akretion (Alexis de Lattre <alexis.delattre@akretion.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, api


class MooncardProcessLines(models.TransientModel):
    _name = 'mooncard.process.lines'
    _description = 'Process Mooncard Transactions'

    @api.multi
    def process_lines(self):
        self.ensure_one()
        assert self._context.get('active_model') == 'mooncard.transaction',\
            'wrong underlying model'
        lines = self.env['mooncard.transaction'].browse(
            self._context['active_ids'])
        lines.process_line()
        return True
