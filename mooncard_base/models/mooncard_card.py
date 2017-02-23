# -*- coding: utf-8 -*-
# © 2016-2017 Akretion (Alexis de Lattre <alexis.delattre@akretion.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MooncardCard(models.Model):
    _name = 'mooncard.card'
    _description = 'Moon Card'
    _rec_name = 'display_name'

    code = fields.Char(string='Short Name')
    user_id = fields.Many2one(
        'res.users', string='User',
        help="Link to user ; only for information purpose.")
    name = fields.Char(
        string='Token Number', required=True, size=9, copy=False,
        help="Enter the 9 digits number written at the bottom of the "
        "front side of your Moon Card")
    display_name = fields.Char(
        compute='_compute_display_name_field', readonly=True, store=True)
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env['res.company']._company_default_get(
            'mooncard.card'))

    @api.depends('code', 'name')
    def _compute_display_name_field(self):
        for card in self:
            dname = card.name
            if card.code:
                dname = '%s (%s)' % (dname, card.code)
            card.display_name = dname

    @api.constrains('name')
    def name_check(self):
        for card in self:
            if card.name and not card.name.isdigit():
                raise ValidationError(_(
                    "'%s' is not a valid Mooncard token. "
                    "It should only have digits") % card.name)

    _sql_constrains = [(
        'token_uniq',
        'unique(name)',
        'This Moon Card already exists in the database!'
        )]
