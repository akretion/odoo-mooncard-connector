# Copyright 2016-2025 Akretion France (https://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class NewgenPaymentCard(models.Model):
    _name = 'newgen.payment.card'
    _description = 'New generation payment card'
    _check_company_auto = True

    code = fields.Char(string='Short Name')
    user_id = fields.Many2one(
        'res.users', string='User',
        help="Link to user ; only for information purpose.")
    name = fields.Char(
        string='Card/Account Number', required=True, copy=False)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True)
    journal_id = fields.Many2one(
        'account.journal', string='Bank Journal', check_company=True,
        domain="[('type', '=', 'bank'), ('company_id', '=', company_id)]",
        ondelete='restrict')
    mapping_ids = fields.One2many(
        'newgen.payment.card.account.mapping', 'card_id', string='Mapping')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        res['company_id'] = self.env.company.id
        existing_card_same_company = self.search([
            ('company_id', '=', res['company_id']),
            ('journal_id', '!=', False),
            ], limit=1)
        if existing_card_same_company:
            res['journal_id'] = existing_card_same_company.journal_id.id
        return res

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for card in self:
            dname = card.name
            if card.code:
                dname = f'{dname} ({card.code})'
            card.display_name = dname

    _sql_constrains = [(
        'token_uniq',
        'unique(name)',
        'This card already exists in the database!'
        )]

    @api.model
    def _match_account(self, code, speeddict):
        # exact match
        if code in speeddict:
            return speeddict[code]
        # match when code has more trailing 0 that odoo's code
        code_tmp = code
        while code_tmp and code_tmp[-1] == "0":
            code_tmp = code_tmp[:-1]
            if code_tmp and code_tmp in speeddict:
                return speeddict[code_tmp]
        # match when code is shorter than odoo's code
        for odoo_code, account_id in speeddict.items():
            if odoo_code.startswith(code):
                return account_id
        raise UserError(_(
            "Could not find any account in Odoo that matches '%s'.") % code)
