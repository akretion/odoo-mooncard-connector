# -*- coding: utf-8 -*-
# Copyright 2020 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    'name': 'Mooncard Invoice Start End Dates',
    'version': '10.0.1.0.0',
    'category': 'Accounting & Finance',
    'license': 'AGPL-3',
    'summary': 'Add start/end dates on Mooncard Transactions',
    'author': 'Akretion',
    'website': 'http://www.akretion.com',
    'depends': ['mooncard_invoice', 'account_invoice_start_end_dates'],
    'data': [
        'views/mooncard_transaction.xml',
    ],
    'installable': True,
}
