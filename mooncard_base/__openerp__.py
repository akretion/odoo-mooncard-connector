# -*- coding: utf-8 -*-
# © 2016 Akretion (Alexis de Lattre <alexis.delattre@akretion.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Mooncard Base',
    'version': '8.0.1.0.0',
    'category': 'Accounting & Finance',
    'license': 'AGPL-3',
    'summary': 'Mooncard base module',
    'author': 'Akretion',
    'website': 'http://www.akretion.com',
    'depends': ['account'],
    'external_dependencies': {'python': ['unicodecsv', 'pycountry']},
    'data': [
        'data/partner.xml',
        'data/product.xml',
        'data/sequence.xml',
        'views/mooncard_transaction.xml',
        'views/mooncard_token.xml',
        'views/company.xml',
        'views/account_config_settings.xml',
        'wizard/mooncard_csv_import_view.xml',
        'wizard/mooncard_process_lines_view.xml',
        'security/ir.model.access.csv',
        'security/mooncard_security.xml',
    ],
    'installable': True,
}
