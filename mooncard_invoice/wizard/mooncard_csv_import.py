# -*- coding: utf-8 -*-
# © 2017 Akretion (Alexis de Lattre <alexis.delattre@akretion.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import models, api


class MooncardCsvImport(models.TransientModel):
    _inherit = 'mooncard.csv.import'

    @api.model
    def _prepare_speeddict(self):
        speeddict = super(MooncardCsvImport, self)._prepare_speeddict()
        speeddict['mapping'] = {}
        map_res = self.env['mooncard.account.mapping'].search_read(
            [('company_id', '=', self.env.user.company_id.id)])
        for map_entry in map_res:
            speeddict['mapping'][
                (map_entry['card_id'][0], map_entry['product_id'][0])] =\
                map_entry['force_expense_account_id'][0]
        return speeddict

    @api.model
    def _prepare_transaction(self, line, speeddict, action='create'):
        vals = super(MooncardCsvImport, self)._prepare_transaction(
            line, speeddict, action=action)
        # Used in created and update
        if line.get('card_token'):
            card_id = speeddict['tokens'].get(line['card_token'])
            if (card_id, vals.get('product_id')) in speeddict['mapping']:
                vals['force_expense_account_id'] =\
                    speeddict['mapping'][(card_id, vals.get('product_id'))]
        return vals
