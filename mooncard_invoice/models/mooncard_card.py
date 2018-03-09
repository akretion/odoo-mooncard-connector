# © 2016-2017 Akretion (Alexis de Lattre <alexis.delattre@akretion.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields


class MooncardCard(models.Model):
    _inherit = 'mooncard.card'

    journal_id = fields.Many2one(
        'account.journal', string='Mooncard Bank Journal',
        domain=[('type', '=', 'bank')])
    mapping_ids = fields.One2many(
        'mooncard.account.mapping', 'card_id', string='Mapping')


class MooncardAccountMapping(models.Model):
    _name = 'mooncard.account.mapping'

    card_id = fields.Many2one('mooncard.card', string='Moon Card')
    company_id = fields.Many2one(
        related='card_id.company_id', readonly=True, store=True)
    product_id = fields.Many2one(
        'product.product', 'Expense Product', ondelete='restrict',
        required=True)
    expense_account_id = fields.Many2one(
        related='product_id.property_account_expense_id', readonly=True,
        string='Expense Account of the Product')
    force_expense_account_id = fields.Many2one(
        'account.account', 'Override Expense Account', ondelete='restrict',
        domain=[('deprecated', '=', False)], required=True)
