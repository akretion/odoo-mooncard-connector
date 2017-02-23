# -*- coding: utf-8 -*-
# © 2016-2017 Akretion (Alexis de Lattre <alexis.delattre@akretion.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields


class MooncardCard(models.Model):
    _inherit = 'mooncard.card'

    journal_id = fields.Many2one(
        'account.journal', string='Mooncard Bank Journal',
        domain=[('type', '=', 'bank')])
