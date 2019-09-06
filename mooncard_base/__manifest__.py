# -*- coding: utf-8 -*-
# Copyright 2016-2019 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Mooncard Base',
    'version': '10.0.3.0.0',
    'category': 'Accounting',
    'license': 'AGPL-3',
    'summary': 'Mooncard base module',
    'author': 'Akretion',
    'website': 'http://www.akretion.com',
    'depends': ['base_business_document_import'],
    'external_dependencies': {'python': ['unicodecsv', 'pycountry']},
    'data': [
        'data/partner.xml',
        'data/sequence.xml',
        'data/decimal_precision.xml',
        'views/mooncard_transaction.xml',
        'views/mooncard_mileage.xml',
        'views/mooncard_card.xml',
        'wizard/mooncard_csv_import_view.xml',
        'wizard/mooncard_process_lines_view.xml',
        'security/ir.model.access.csv',
        'security/mooncard_security.xml',
    ],
    'demo': ['demo/demo.xml'],
    'installable': True,
}
