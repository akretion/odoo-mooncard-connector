# Copyright 2016-2021 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'New-generation payment card - Base module',
    'version': '16.0.1.0.0',
    'category': 'Accounting',
    'license': 'AGPL-3',
    'summary': 'New-generation payment card',
    'author': 'Akretion',
    'website': 'http://www.akretion.com',
    'depends': ['account_invoice_import'],
    'external_dependencies': {'python': ['unidecode', 'PIL']},
    'data': [
        'data/partner.xml',
        'data/sequence.xml',
        'views/newgen_payment_card_transaction.xml',
        'views/newgen_payment_card.xml',
        'security/ir.model.access.csv',
        'security/newgen_payment_card_security.xml',
    ],
    'demo': ['demo/demo.xml'],
    'installable': True,
}
