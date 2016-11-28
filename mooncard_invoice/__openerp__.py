# -*- coding: utf-8 -*-
# © 2016 Akretion (Alexis de Lattre <alexis.delattre@akretion.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Mooncard Invoice',
    'version': '8.0.1.0.0',
    'category': 'Accounting & Finance',
    'license': 'AGPL-3',
    'summary': 'Create supplier invoices from mooncard transactions',
    'author': 'Akretion',
    'website': 'http://www.akretion.com',
    'depends': ['mooncard_base', 'account_invoice_import'],
    'data': [
        'data/partner.xml',
        'views/mooncard_transaction.xml',
        'views/mooncard_card.xml',
        'views/account_config_settings.xml',
        'views/company.xml',
    ],
    'images': [
        'static/description/banner_odoo_mooncard.jpg',
        'static/description/diagram_odoo_mooncard.jpg',
        ],
    'installable': True,
}
