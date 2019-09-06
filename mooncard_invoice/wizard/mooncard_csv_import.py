# -*- coding: utf-8 -*-
# Copyright 2017-2019 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models, _
from unidecode import unidecode
from odoo.exceptions import UserError
MEANINGFUL_PARTNER_NAME_MIN_SIZE = 3


class MooncardCsvImport(models.TransientModel):
    _inherit = 'mooncard.csv.import'

    @api.model
    def _default_partner(self):
        return self.env.ref('mooncard_base.mooncard_supplier')

    @api.model
    def _prepare_speeddict(self):
        speeddict = super(MooncardCsvImport, self)._prepare_speeddict()
        mto = self.env['mooncard.transaction']
        company = self.env.user.company_id
        speeddict['mapping'] = {}
        map_res = self.env['mooncard.account.mapping'].search_read(
            [('company_id', '=', company.id)])
        for map_entry in map_res:
            speeddict['mapping'][
                (map_entry['card_id'][0],
                 map_entry['expense_account_id'][0])] =\
                map_entry['force_expense_account_id'][0]
        if not company.transfer_account_id:
            raise UserError(_(
                "Missing 'Internal Bank Transfer Account' on company '%s'.")
                % company.display_name)
        speeddict['transfer_account_id'] = company.transfer_account_id.id
        default_partner = self._default_partner()
        if default_partner.parent_id:
            raise UserError(_(
                "The default partner (%s) should be a parent partner.")
                % default_partner.display_name)
        speeddict['default_partner_id'] = default_partner.id
        speeddict['partner'] = []
        specific_partner_existing_transactions = mto.search_read([
            ('state', '=', 'done'),
            ('transaction_type', '=', 'presentment'),
            ('merchant', '!=', False),
            ('partner_id', '!=', False),
            ('partner_id', '!=', speeddict['default_partner_id'])],
            ['merchant', 'partner_id'])
        for trans in specific_partner_existing_transactions:
            speeddict['partner'].append((
                unidecode(trans['merchant']).strip().upper(),
                trans['partner_id'][0]))
        partners = self.env['res.partner'].search_read(
                [('parent_id', '=', False)], ['name'])
        for partner in partners:
            partner_name = unidecode(partner['name'].strip().upper())
            if len(partner_name) >= MEANINGFUL_PARTNER_NAME_MIN_SIZE:
                speeddict['partner'].append((partner_name, partner['id']))
        return speeddict

    @api.model
    def partner_match(self, merchant, speed_entry):
        if speed_entry[0] in merchant:
            return speed_entry[1]
        else:
            return False

    @api.model
    def _prepare_transaction(self, line, speeddict, action='create'):
        vals = super(MooncardCsvImport, self)._prepare_transaction(
            line, speeddict, action=action)
        # Used in create and update
        if line.get('card_token'):
            card_id = speeddict['tokens'].get(line['card_token'])
            tuple_match = (card_id, vals.get('expense_account_id'))
            if tuple_match in speeddict['mapping']:
                vals['expense_account_id'] = speeddict['mapping'][tuple_match]
        if line.get('transaction_type') == 'L':  # presentment
            vals['bank_counterpart_account_id'] =\
                speeddict['transfer_account_id']
        elif line.get('transaction_type') == 'P':
            merchant = line.get('supplier') and line['supplier'].strip()
            partner_id = speeddict['default_partner_id']
            if merchant and len(merchant) >= MEANINGFUL_PARTNER_NAME_MIN_SIZE:
                merchant_match = unidecode(merchant.upper())
                for speed_entry in speeddict['partner']:
                    partner_match = self.partner_match(
                        merchant_match, speed_entry)
                    if partner_match:
                        partner_id = partner_match
            partner = self.env['res.partner'].browse(partner_id)
            vals.update({
                'partner_id': partner_id,
                'bank_counterpart_account_id':
                partner.property_account_payable_id.id,
                })
        return vals
