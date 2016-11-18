# -*- coding: utf-8 -*-
# © 2016 Akretion (Alexis de Lattre <alexis.delattre@akretion.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import api, SUPERUSER_ID

MAPPING = {
    'FR': {
        # 'MOON-1000': {},
        'MOON-1010': {'account': '6278', 'tax': 'ACH-20.0'},
        'MOON-1020': {'account': '6227', 'tax': 'ACH-20.0'},
        'MOON-1030': {'account': '626', 'tax': False},
        'MOON-1040': {'account': '6241', 'tax': 'ACH-20.0'},
        'MOON-1100': {'account': '6064', 'tax': 'ACH-20.0'},
        'MOON-1200': {'account': '6181', 'tax': 'ACH-5.5'},
        'MOON-2000': {'account': '6233', 'tax': 'ACH-20.0'},
        'MOON-2500': {'account': '6234', 'tax': 'ACH-20.0'},
        'MOON-3000': {'account': '6063', 'tax': 'ACH-20.0'},
        'MOON-3100': {'account': '2183', 'tax': 'ACH-20.0'},
        'MOON-3500': {'account': '626', 'tax': 'ACH-20.0'},
        'MOON-4000': {'account': '604', 'tax': 'ACH-20.0'},
        'MOON-6000': {'account': '626', 'tax': 'ACH-20.0'},
        'MOON-6010': {'account': '6231', 'tax': 'ACH-20.0'},
        'MOON-6020': {'account': '6284', 'tax': 'ACH-20.0'},
        'MOON-6030': {'account': '626', 'tax': 'ACH-20.0'},  # Better account ?
        'MOON-6040': {},  # Internet ventes; which account ?
        'MOON-6050': {'account': '6237', 'tax': 'ACH-20.0'},
        'MOON-6900': {'account': '651', 'tax': 'ACH-20.0'},
        'MOON-7000': {'account': '6251', 'tax': False},
        'MOON-7200': {'account': '6257', 'tax': 'ACH-10.0'},
        'MOON-7300': {'account': '6251', 'tax': 'ACH-10.0'},
        'MOON-8000': {'account': '6251', 'tax': 'ACH-20.0'},
        'MOON-8010': {'account': '6251', 'tax': 'ACH-20.0'},
        'MOON-8020': {'account': '6251', 'tax': 'ACH-20.0'},
        'MOON-8030': {'account': '6251', 'tax': 'ACH-20.0'},
        'MOON-8040': {'account': '6251', 'tax': 'ACH-20.0'},
        'MOON-8050': {'account': '6251', 'tax': 'ACH-20.0'},
        'MOON-8060': {'account': '6251', 'tax': False},
        'MOON-8070': {'account': '6251', 'tax': False},
        'MOON-8099': {'account': '6251', 'tax': False},
        # 'MOON-9000': {},  # Autre
        }
    }


def set_accounts_on_products(cr, registry):
    with api.Environment.manage():
        env = api.Environment(cr, SUPERUSER_ID, {})
        supplier = env.ref('mooncard_base.mooncard_supplier')
        companies = env['res.company'].search([])
        for company in companies:
            company_country_code = company.country_id.code and\
                company.country_id.code.upper()
            if company_country_code not in MAPPING:
                continue
            for default_code, val_dict in\
                    MAPPING[company_country_code].iteritems():
                products = env['product.product'].search([
                    ('seller_id', '=', supplier.id),
                    ('default_code', '=', default_code),
                    ])
                if not products:
                    continue
                product = products[0]
                if val_dict.get('account'):
                    accounts = env['account.account'].search([
                        ('code', '=like', val_dict['account'] + '%'),
                        ('type', 'not in', ('view', 'closed'))])
                    if accounts:
                        product.with_context(force_company=company.id).\
                            property_account_expense = accounts[0].id
                if 'tax' in val_dict:
                    if val_dict['tax']:
                        taxes = env['account.tax'].search([
                            ('type_tax_use', 'in', ('all', 'purchase')),
                            ('description', '=', val_dict['tax'])])
                        if taxes:
                            product.with_context(force_company=company.id).\
                                supplier_taxes_id = [(6, 0, [taxes[0].id])]
                    else:
                        product.with_context(force_company=company.id).\
                            supplier_taxes_id = False
    return
