# Copyright 2016-2019 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class NewgenPaymentCard(models.Model):
    _name = 'newgen.payment.card'
    _description = 'New generation payment card'

    code = fields.Char(string='Short Name')
    user_id = fields.Many2one(
        'res.users', string='User',
        help="Link to user ; only for information purpose.")
    name = fields.Char(
        string='Card/Account Number', required=True, copy=False)
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env['res.company']._company_default_get())
    journal_id = fields.Many2one(
        'account.journal', string='Bank Journal',
        domain=[('type', '=', 'bank')], ondelete='restrict')
    mapping_ids = fields.One2many(
        'newgen.payment.card.account.mapping', 'card_id', string='Mapping')

    @api.depends('code', 'name')
    def name_get(self):
        res = []
        for card in self:
            dname = card.name
            if card.code:
                dname = '%s (%s)' % (dname, card.code)
            res.append((card.id, dname))
        return res

    _sql_constrains = [(
        'token_uniq',
        'unique(name)',
        'This card already exists in the database!'
        )]
