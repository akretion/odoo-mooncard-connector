# -*- coding: utf-8 -*-
# Copyright 2018 Akretion (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if not version:
        return

    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})
        mto = env['mooncard.transaction']
        for company in env['res.company'].search([]):
            transs = mto.search([
                ('company_id', '=', company.id),
                ('product_id', '!=', False)])
            for trans in transs:
                transc = trans.with_context(force_company=company.id)
                account = transc.product_id.product_tmpl_id.\
                    _get_product_accounts()['expense']
                if account:
                    cr.execute('''
                    UPDATE mooncard_transaction SET expense_account_id=%s
                    WHERE id=%s''', (account.id, trans.id))
