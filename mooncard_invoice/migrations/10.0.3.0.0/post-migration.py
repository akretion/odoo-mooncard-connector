# -*- coding: utf-8 -*-
# Copyright 2019 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if not version:
        return

    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})
        # Set new field 'bank_move_id'
        cr.execute('''
            UPDATE mooncard_transaction SET bank_move_id=load_move_id
            WHERE load_move_id is not null AND transaction_type='load'
            ''')
        cr.execute('''
            UPDATE mooncard_transaction
            SET bank_move_id=account_move_line.move_id
            FROM account_move_line WHERE
            account_move_line.id=mooncard_transaction.payment_move_line_id
            AND mooncard_transaction.transaction_type='presentment'
            AND mooncard_transaction.payment_move_line_id is not null
            ''')
        # Set new field 'bank_counterpart_account_id'
        cr.execute('''
            UPDATE mooncard_transaction
            SET bank_counterpart_account_id=res_company.transfer_account_id
            FROM res_company
            WHERE res_company.id=mooncard_transaction.company_id
            AND mooncard_transaction.transaction_type='load'
            ''')
        mto = env['mooncard.transaction']
        for company in env['res.company'].search([]):
            transs = mto.search([
                ('company_id', '=', company.id),
                ('transaction_type', '!=', 'load')])
            for trans in transs:
                transc = trans.with_context(force_company=company.id)
                trans.bank_counterpart_account_id =\
                    transc.partner_id.property_account_payable_id.id
