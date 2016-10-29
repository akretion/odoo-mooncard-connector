# -*- coding: utf-8 -*-
# © 2016 Akretion (Alexis de Lattre <alexis.delattre@akretion.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import models, fields, api, _
from openerp.exceptions import ValidationError


class MooncardToken(models.Model):
    _name = 'mooncard.token'
    _description = 'Mooncard Tokens'

    name = fields.Char(
        string='Token Number', required=True, size=9, copy=False)
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env['res.company']._company_default_get(
            'mooncard.token'))

    @api.one
    @api.constrains('name')
    def name_check(self):
        if self.name and not self.name.isdigit():
            raise ValidationError(_(
                "'%s' is not a valid Mooncard token. "
                "It should only have digits") % self.name)

    _sql_constrains = [(
        'token_uniq',
        'unique(name)',
        'This Mooncard token already exists in the database!'
        )]
