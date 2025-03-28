# Copyright 2016-2025 Akretion France (https://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'New-generation payment card - Base module',
    'version': '18.0.1.0.0',
    'category': 'Accounting',
    'license': 'AGPL-3',
    'summary': 'New-generation payment card',
    'author': 'Akretion',
    'website': 'https://github.com/akretion/odoo-mooncard-connector',
    'depends': ['account_tax_unece'],
    'external_dependencies': {'python': ['unidecode', 'PIL']},
    'data': [
        'data/res_partner.xml',
        'data/ir_sequence.xml',
        'data/decimal_precision.xml',
        'views/newgen_payment_card_transaction.xml',
        'views/newgen_payment_card.xml',
        'security/ir.model.access.csv',
        'security/newgen_payment_card_security.xml',
    ],
    'demo': ['demo/demo.xml'],
    'installable': True,
}
