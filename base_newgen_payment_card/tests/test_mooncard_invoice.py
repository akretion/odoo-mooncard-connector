# Copyright 2016-2025 Akretion France (https://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import Command, fields
from odoo.tests.common import TransactionCase
from odoo.tools import float_compare
import random


class TestNewgenPaymentCard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.account_model = cls.env['account.account']
        cls.move_model = cls.env['account.move']
        cls.journal_model = cls.env['account.journal']
        cls.card_model = cls.env['newgen.payment.card']
        cls.card_bank_account = cls.account_model.create({
            'code': '512199',
            'name': 'Card prepaid account',
            'account_type': "asset_cash",
            })
        cls.expense_account = cls.account_model.create({
            'code': '6TESTXXX',
            'name': 'Test Expense Account',
            'account_type': "expense",
            })
        cls.card_bank_journal = cls.journal_model.create({
            'type': 'bank',
            'name': 'Card Test',
            'code': 'CARD',
            'default_account_id': cls.card_bank_account.id,
            })
        cls.card1 = cls.env.ref('base_newgen_payment_card.card1')
        cls.card1.write({
            'journal_id': cls.card_bank_journal.id})
        cls.company = cls.env.ref('base.main_company')
        cls.euro = cls.env.ref('base.EUR')
        cls.country = cls.env.ref('base.fr')
        cls.company.write({
            'currency_id': cls.euro.id,
            })
        cls.prec = cls.company.currency_id.rounding

    def test_load_line(self):
        # Set company country to France
        load1 = self.env.ref('base_newgen_payment_card.load1')
        load1.process_line()
        self.assertEqual(load1.state, 'done')
        self.assertTrue(load1.bank_move_id)
        self.assertEqual(load1.bank_move_id.journal_id, self.card1.journal_id)
        self.assertEqual(load1.bank_move_id.date, load1.date)

    def test_expense_line(self):
        for expense_xmlid in ['expense1', 'expense2', 'expense3']:
            expense = self.env.ref(
                'base_newgen_payment_card.%s' % expense_xmlid)
            expense.write({'image_url': False, 'receipt_lost': True})
            expense.process_line()
            self.assertEqual(expense.state, 'done')
            inv = expense.invoice_id
            self.assertEqual(inv.state, 'posted')
            self.assertEqual(inv.payment_state, 'paid')
            if float_compare(
                    expense.total_company_currency, 0,
                    precision_rounding=self.prec) == -1:
                self.assertEqual(inv.move_type, 'in_invoice')
            else:
                self.assertEqual(inv.move_type, 'in_refund')
            self.assertFalse(float_compare(
                abs(expense.total_company_currency),
                inv.amount_total,
                precision_rounding=self.prec))
            self.assertFalse(float_compare(
                abs(expense.vat_company_currency),
                inv.amount_tax,
                precision_rounding=self.prec))
            self.assertEqual(inv.invoice_date, expense.date)
            self.assertTrue(expense.bank_move_id)
            self.assertEqual(expense.bank_move_id.date, expense.date)
            self.assertEqual(
                expense.bank_move_id.journal_id, self.card1.journal_id)

    def test_match_account(self):
        company = self.env['res.company'].create({'name': 'test match account'})
        codes_to_create = ['601000', '625100', '626100']
        code2id = {}
        for code in codes_to_create:
            account = self.env['account.account'].create({
                'account_type': 'expense',
                'company_ids': [Command.set([company.id])],
                'code': code,
                'name': 'test label',
                })
            code2id[code] = account.id
        speeddict = company._prepare_account_import_speeddict()
        self.assertEqual(
            self.card_model._match_account('626100', speeddict), code2id['626100'])
        self.assertEqual(
            self.card_model._match_account('6251', speeddict), code2id['625100'])
        self.assertEqual(
            self.card_model._match_account('625', speeddict), code2id['625100'])

    def test_process_line_force_vat1(self):
        trans = self.env['newgen.payment.card.transaction'].create({
            'transaction_type': 'expense',
            'company_id': self.company.id,
            'expense_account_id': self.expense_account.id,
            'unique_import_id': 'RANDOM%s' % random.randrange(100000000),
            'description': 'test description',
            'date': fields.Datetime.now(),
            'card_id': self.card1.id,
            'receipt_lost': True,
            'vendor': 'Test vendor',
            'country_id': self.country.id,
            'vat_company_currency': -20.5,
            'vat_rate': 20.0,
            'total_company_currency': -120,
            'currency_id': self.euro.id,
            })
        trans.process_line()
        self.assertEqual(trans.invoice_id.move_type, 'in_invoice')
        self.assertFalse(trans.currency_id.compare_amounts(trans.invoice_id.amount_total, 120))
        self.assertFalse(trans.currency_id.compare_amounts(trans.invoice_id.amount_untaxed, 99.5))

    def test_process_line_force_vat2(self):
        trans = self.env['newgen.payment.card.transaction'].create({
            'transaction_type': 'expense',
            'company_id': self.company.id,
            'expense_account_id': self.expense_account.id,
            'unique_import_id': 'RANDOM%s' % random.randrange(100000000),
            'description': 'test description',
            'date': fields.Datetime.now(),
            'card_id': self.card1.id,
            'receipt_lost': True,
            'vendor': 'Test vendor',
            'country_id': self.country.id,
            'vat_company_currency': -19.98,
            'vat_rate': 20.0,
            'total_company_currency': -119.98,
            'currency_id': self.euro.id,
            })
        trans.process_line()
        self.assertEqual(trans.invoice_id.move_type, 'in_invoice')
        self.assertFalse(trans.currency_id.compare_amounts(trans.invoice_id.amount_total, 119.98))
        self.assertFalse(trans.currency_id.compare_amounts(trans.invoice_id.amount_untaxed, 100.0))

    def test_process_line_force_refund(self):
        trans = self.env['newgen.payment.card.transaction'].create({
            'transaction_type': 'expense',
            'company_id': self.company.id,
            'expense_account_id': self.expense_account.id,
            'unique_import_id': 'RANDOM%s' % random.randrange(100000000),
            'description': 'test refund',
            'date': fields.Datetime.now(),
            'card_id': self.card1.id,
            'receipt_lost': True,
            'vendor': 'Test vendor',
            'country_id': self.country.id,
            'vat_company_currency': 19.98,
            'vat_rate': 20.0,
            'total_company_currency': 119.98,
            'currency_id': self.euro.id,
            })
        trans.process_line()
        self.assertEqual(trans.invoice_id.move_type, 'in_refund')
        self.assertFalse(trans.currency_id.compare_amounts(trans.invoice_id.amount_total, 119.98))
        self.assertFalse(trans.currency_id.compare_amounts(trans.invoice_id.amount_untaxed, 100.0))
