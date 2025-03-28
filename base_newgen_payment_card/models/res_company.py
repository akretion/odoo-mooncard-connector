# Copyright 2016-2025 Akretion France (https://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare
from unidecode import unidecode

MEANINGFUL_PARTNER_NAME_MIN_SIZE = 3


class ResCompany(models.Model):
    _inherit = 'res.company'

    def _default_partner(self, raise_if_not_found=False):
        return self.env.ref(
            'base_newgen_payment_card.misc_supplier',
            raise_if_not_found=raise_if_not_found)

    def _prepare_account_import_speeddict(self):
        res = {}
        account_res = self.env["account.account"].with_company(self.id).search_read(
            [("company_ids", "in", self.id), ("deprecated", "=", False), ('code', '!=', False)], ["code"]
        )
        for account in account_res:
            res[account['code'].upper()] = account['id']
        return res

    def _prepare_import_speeddict(self):
        """Used in provider-specific modules"""
        self.ensure_one()
        speeddict = {
            'tokens': {}, 'accounts': {}, 'analytic': {},
            'countries': {}, 'currencies': {}, 'mapping': {}}

        speeddict['accounts'] = self._prepare_account_import_speeddict()

        token_res = self.env['newgen.payment.card'].search_read(
            [('company_id', '=', self.id)], ['name'])
        for token in token_res:
            speeddict['tokens'][token['name']] = token['id']

        analytic_res = self.env['account.analytic.account'].search_read(
            [('company_id', '=', self.id), ('code', '!=', False)], ['code'])
        for analytic in analytic_res:
            analytic_code = analytic['code'].strip().lower()
            speeddict['analytic'][analytic_code] = analytic['id']

        countries = self.env['res.country'].search_read(
            [('code', '!=', False)], ['code'])
        for country in countries:
            speeddict['countries'][country['code'].strip()] = country['id']
        speeddict['eu_country_ids'] = self.env.ref('base.europe').country_ids.ids
        if not self.country_id.id:
            raise UserError(_(
                "Country is not set on company '%s'.") % self.display_name)
        speeddict['my_country_id'] = self.country_id.id

        currencies = self.env['res.currency'].with_context(
            active_test=False).search_read([], ['name'])
        for curr in currencies:
            speeddict['currencies'][curr['name']] = curr['id']
        npcto = self.env['newgen.payment.card.transaction']
        map_res = self.env['newgen.payment.card.account.mapping'].search_read(
            [('company_id', '=', self.id)])
        for map_entry in map_res:
            speeddict['mapping'][
                (map_entry['card_id'][0],
                 map_entry['expense_account_id'][0])] =\
                map_entry['force_expense_account_id'][0]
        if not self.transfer_account_id:
            raise UserError(_(
                "Missing 'Internal Bank Transfer Account' on company '%s'.")
                % self.display_name)
        speeddict['transfer_account_id'] = self.transfer_account_id.id
        default_partner = self._default_partner(raise_if_not_found=True)
        if default_partner.parent_id:
            raise UserError(_(
                "The default partner (%s) should be a parent partner.")
                % default_partner.display_name)
        speeddict['default_partner_id'] = default_partner.id
        speeddict['partner_labels'] = {}
        specific_partner_existing_transactions = npcto.search_read([
            ('state', '=', 'done'),
            ('transaction_type', '=', 'expense'),
            ('vendor', '!=', False),
            ('partner_id', '!=', False),
            ('partner_id', '!=', speeddict['default_partner_id'])],
            ['vendor', 'partner_id'], order='id')
        # order by id to have the latest value for a particular label
        for trans in specific_partner_existing_transactions:
            label = unidecode(trans['vendor']).strip().upper()
            speeddict['partner_labels'][label] = trans['partner_id'][0]
        speeddict['partner_vat'] = {}
        speeddict['partner_names'] = {}
        partners = self.env['res.partner'].search_read(
            [('parent_id', '=', False), ('id', '!=', self.partner_id.id)],
            ['name', 'vat'])
        for partner in partners:
            partner_name = unidecode(partner['name'].strip().upper())
            if len(partner_name) >= MEANINGFUL_PARTNER_NAME_MIN_SIZE:
                speeddict['partner_names'][partner_name] = partner['id']
            if partner['vat']:
                # 'vat' field is already sanitized
                speeddict['partner_vat'][partner['vat']] = partner['id']
        speeddict['default_vat_rate'] = 0
        if (
                self.account_purchase_tax_id and
                self.account_purchase_tax_id.amount_type == 'percent' and
                float_compare(
                    self.account_purchase_tax_id.amount, 0,
                    precision_digits=4) > 0):
            speeddict['default_vat_rate'] =\
                self.account_purchase_tax_id.amount
        return speeddict
