# -*- coding: utf-8 -*-
# © 2016 Akretion (Alexis de Lattre <alexis.delattre@akretion.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import models, fields, api, _
from openerp.exceptions import ValidationError


class MooncardToken(models.Model):
    _name = 'mooncard.token'
    _description = 'Mooncard Tokens'
    _rec_name = 'display_name'

    code = fields.Char(string='Short Name')
    user_id = fields.Many2one(
        'res.users', string='User',
        help="Link to user ; only for information purpose.")
    name = fields.Char(
        string='Token Number', required=True, size=9, copy=False)
    display_name = fields.Char(
        compute='_compute_display_name_field', readonly=True, store=True)
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env['res.company']._company_default_get(
            'mooncard.token'))

    @api.one
    @api.depends('code', 'name')
    def _compute_display_name_field(self):
        dname = self.name
        if self.code:
            dname = '%s (%s)' % (dname, self.code)
        self.display_name = dname

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
