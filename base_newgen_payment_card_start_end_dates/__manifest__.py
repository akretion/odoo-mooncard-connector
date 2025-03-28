# Copyright 2020-2025 Akretion France (https://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Base Newgen Payment Card Start End Dates',
    'version': '18.0.1.0.0',
    'category': 'Accounting & Finance',
    'license': 'AGPL-3',
    'summary': 'Add start/end dates on payment card transactions',
    'author': 'Akretion',
    'website': 'https://github.com/akretion/odoo-mooncard-connector',
    'depends': ['base_newgen_payment_card', 'account_invoice_start_end_dates'],
    'data': [
        'views/newgen_payment_card_transaction.xml',
    ],
    'installable': True,
}
