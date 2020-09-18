# -*- coding: utf-8 -*-
# © 2016-2017 Akretion (Alexis de Lattre <alexis.delattre@akretion.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class MooncardCard(models.Model):
    _inherit = 'mooncard.card'

    journal_id = fields.Many2one(
        'account.journal', string='Mooncard Bank Journal',
        domain=[('type', '=', 'bank')],
        default=lambda self: self._default_journal())
    mapping_ids = fields.One2many(
        'mooncard.account.mapping', 'card_id', string='Mapping')

    @api.model
    def _default_journal(self):
        company_id = self._context.get('force_company') or self.env.user.company_id.id
        journal = self.env['account.journal'].search([
            ('company_id', '=', company_id),
            ('type', '=', 'bank'),
            ('name', 'ilike', 'moon')], limit=1)
        return journal


class MooncardAccountMapping(models.Model):
    _name = 'mooncard.account.mapping'

    card_id = fields.Many2one('mooncard.card', string='Moon Card')
    company_id = fields.Many2one(
        related='card_id.company_id', readonly=True, store=True)
    expense_account_id = fields.Many2one(
        'account.account', domain=[('deprecated', '=', False)],
        string='Expense Account', required=True)
    force_expense_account_id = fields.Many2one(
        'account.account', 'Override Expense Account', ondelete='restrict',
        domain=[('deprecated', '=', False)], required=True)
