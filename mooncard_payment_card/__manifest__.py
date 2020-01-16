# Copyright 2016-2020 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Mooncard Payment Card',
    'version': '12.0.1.0.0',
    'category': 'Accounting',
    'license': 'AGPL-3',
    'summary': 'Odoo-Mooncard connector',
    'author': 'Akretion',
    'website': 'http://www.akretion.com',
    'depends': ['base_newgen_payment_card'],
    'external_dependencies': {'python': ['unicodecsv', 'pycountry']},
    'data': [
        'security/mooncard_security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'wizard/mooncard_csv_import_view.xml',
        'views/mooncard_mileage.xml',
    ],
    'installable': True,
}
