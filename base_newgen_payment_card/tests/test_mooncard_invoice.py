# Copyright 2016-2019 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.tests.common import TransactionCase
from odoo.tools import float_compare


class TestNewgenPaymentCard(TransactionCase):

    def setUp(self):
        super().setUp()
        self.account_model = self.env['account.account']
        self.move_model = self.env['account.move']
        self.journal_model = self.env['account.journal']
        bank_acc_type = self.env.ref('account.data_account_type_liquidity')
        expense_acc_type = self.env.ref('account.data_account_type_expenses')
        self.card_bank_account = self.account_model.create({
            'code': '512199',
            'name': 'Card prepaid account',
            'user_type_id': bank_acc_type.id,
            })
        self.expense_account = self.account_model.create({
            'code': '6TESTXXX',
            'name': 'Test Expense Account',
            'user_type_id': expense_acc_type.id,
            })
        self.card_bank_journal = self.journal_model.create({
            'type': 'bank',
            'name': 'Card Test',
            'code': 'CARD',
            'default_account_id': self.card_bank_account.id,
            })
        self.card1 = self.env.ref('base_newgen_payment_card.card1')
        self.card1.write({
            'journal_id': self.card_bank_journal.id})
        self.company = self.env.ref('base.main_company')
        self.euro = self.env.ref('base.EUR')
        self.company.write({
            'currency_id': self.euro.id,
            })
        self.prec = self.company.currency_id.rounding

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
            expense.expense_account_id = self.expense_account.id
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
            self.assertTrue(expense.reconcile_id)
