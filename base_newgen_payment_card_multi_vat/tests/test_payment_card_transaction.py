# Copyright 2016-2019 Akretion France (http://www.akretion.com/)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import time

from odoo.tests.common import SavepointCase


class TestNewgenPaymentCardMultiVat(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.account0 = cls.env["account.account"].create(
            {
                "user_type_id": cls.env.ref("account.data_account_type_expenses").id,
                "name": "test expense 1",
                "code": "62510030",
            }
        )
        cls.account20 = cls.env["account.account"].create(
            {
                "user_type_id": cls.env.ref("account.data_account_type_expenses").id,
                "name": "test expense 2",
                "code": "62510000",
            }
        )
        cls.account10 = cls.env["account.account"].create(
            {
                "user_type_id": cls.env.ref("account.data_account_type_expenses").id,
                "name": "test expense 2",
                "code": "62510020",
            }
        )
        bank_acc_type = cls.env.ref("account.data_account_type_liquidity")
        cls.card_bank_account = cls.env["account.account"].create(
            {
                "code": "512199",
                "name": "Card prepaid account",
                "user_type_id": bank_acc_type.id,
            }
        )
        cls.card_bank_journal = cls.env["account.journal"].create(
            {
                "type": "bank",
                "name": "Card Test",
                "code": "CARD",
                "default_account_id": cls.card_bank_account.id,
            }
        )
        cls.card1 = cls.env.ref("base_newgen_payment_card.card1")
        cls.card1.write({"journal_id": cls.card_bank_journal.id})
        # create 20% and 10% taxes
        cls.tax_account = cls.env["account.account"].create(
            {
                "code": "445661",
                "name": "TVA déductible sur autres biens et services",
                "user_type_id": cls.env.ref(
                    "account.data_account_type_current_assets"
                ).id,
            }
        )
        cls.tax_20 = cls.env["account.tax"].create(
            {
                "name": "20%",
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "amount": 20.0,
                "unece_type_id": cls.env.ref("account_tax_unece.tax_type_vat").id,
                "unece_categ_id": cls.env.ref("account_tax_unece.tax_categ_s").id,
                "invoice_repartition_line_ids": [
                    (
                        0,
                        0,
                        {
                            "factor_percent": 100,
                            "repartition_type": "base",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "factor_percent": 100,
                            "repartition_type": "tax",
                            "account_id": cls.tax_account.id,
                        },
                    ),
                ],
            }
        )
        cls.tax_10 = cls.env["account.tax"].create(
            {
                "name": "10%",
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "amount": 10.0,
                "unece_type_id": cls.env.ref("account_tax_unece.tax_type_vat").id,
                "unece_categ_id": cls.env.ref("account_tax_unece.tax_categ_s").id,
                "invoice_repartition_line_ids": [
                    (
                        0,
                        0,
                        {
                            "factor_percent": 100,
                            "repartition_type": "base",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "factor_percent": 100,
                            "repartition_type": "tax",
                            "account_id": cls.tax_account.id,
                        },
                    ),
                ],
            }
        )
        cls.company = cls.env.ref("base.main_company")
        cls.euro = cls.env.ref("base.EUR")
        cls.company.write(
            {
                "currency_id": cls.euro.id,
            }
        )
        cls.prec = cls.company.currency_id.rounding

    def test_expense_line_multi_vat(self):
        transaction = self.env["newgen.payment.card.transaction"].create(
            {
                "transaction_type": "expense",
                "description": "Dinner with customer",
                "date": time.strftime("%Y-01-02 %H:%M:10"),
                "card_id": self.env.ref("base_newgen_payment_card.card1").id,
                "expense_categ_name": "customer meal",
                "vendor": "Test",
                "country_id": self.env.ref("base.fr").id,
                "vat_company_currency": -6.12,
                "vat_rate": 10.0,
                "total_company_currency": -50.35,
                "total_currency": -50.35,
                "currency_id": self.env.ref("base.EUR").id,
                "image_url": "https://linuxfr.org/images/sections/10.png",
                "vat_line_ids": [
                    (
                        0,
                        0,
                        {
                            "vat_company_currency": -2.17,
                            "vat_rate": 20.0,
                            "subtotal_company_currency": -8.68,
                            "total_company_currency": -10.85,
                            "expense_account_id": self.account20.id,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "vat_company_currency": -3.95,
                            "vat_rate": 10.0,
                            "subtotal_company_currency": -35.55,
                            "total_company_currency": -39.5,
                            "expense_account_id": self.account10.id,
                        },
                    ),
                ],
            }
        )
        transaction.process_line()
        self.assertEqual(transaction.state, "done")
        inv = transaction.invoice_id
        self.assertEqual(inv.state, "posted")
        self.assertEqual(inv.payment_state, "paid")
        self.assertEqual(inv.move_type, "in_invoice")
        # 2 inv line / 5 lines because of 2 different VAT
        self.assertEqual(len(inv.invoice_line_ids), 2)
        self.assertEqual(len(inv.line_ids), 5)
        self.assertAlmostEqual(-transaction.total_company_currency, inv.amount_total)
        self.assertAlmostEqual(-transaction.vat_company_currency, inv.amount_tax)
        self.assertEqual(inv.invoice_date, transaction.date)
        self.assertTrue(transaction.bank_move_id)
        self.assertEqual(transaction.bank_move_id.date, transaction.date)
        self.assertEqual(transaction.bank_move_id.journal_id, self.card1.journal_id)
        self.assertTrue(transaction.reconcile_id)

    def test_refund_line_multi_vat_with_tva_diff(self):
        transaction = self.env["newgen.payment.card.transaction"].create(
            {
                "transaction_type": "expense",
                "description": "Dinner with customer",
                "date": time.strftime("%Y-01-02 %H:%M:10"),
                "card_id": self.env.ref("base_newgen_payment_card.card1").id,
                "expense_categ_name": "customer meal",
                "vendor": "Test",
                "country_id": self.env.ref("base.fr").id,
                "vat_company_currency": 6.12,
                "vat_rate": 10.0,
                "total_company_currency": 50.35,
                "total_currency": 50.35,
                "currency_id": self.env.ref("base.EUR").id,
                "image_url": "https://linuxfr.org/images/sections/10.png",
                "vat_line_ids": [
                    (
                        0,
                        0,
                        {
                            # missing 1 cent
                            "vat_company_currency": 2.16,
                            "vat_rate": 20.0,
                            "subtotal_company_currency": 8.68,
                            "total_company_currency": 10.84,
                            "expense_account_id": self.account20.id,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            # 1 more cent
                            "vat_company_currency": 3.96,
                            "vat_rate": 10.0,
                            "subtotal_company_currency": 35.55,
                            "total_company_currency": 39.51,
                            "expense_account_id": self.account10.id,
                        },
                    ),
                ],
            }
        )
        transaction.process_line()
        self.assertEqual(transaction.state, "done")
        inv = transaction.invoice_id
        self.assertEqual(inv.state, "posted")
        self.assertEqual(inv.payment_state, "paid")
        self.assertEqual(inv.move_type, "in_refund")
        # 2 inv line / 5 lines because of 2 different VAT
        self.assertEqual(len(inv.invoice_line_ids), 2)
        self.assertEqual(len(inv.line_ids), 5)
        self.assertAlmostEqual(transaction.total_company_currency, inv.amount_total)
        self.assertAlmostEqual(transaction.vat_company_currency, inv.amount_tax)
        tax_line_20 = inv.line_ids.filtered(lambda li: li.tax_line_id == self.tax_20)
        tax_line_10 = inv.line_ids.filtered(lambda li: li.tax_line_id == self.tax_10)
        self.assertEqual(tax_line_20.credit, 2.16)
        self.assertEqual(tax_line_10.credit, 3.96)
