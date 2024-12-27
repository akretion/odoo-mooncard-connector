# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import base64

from odoo.modules.module import get_resource_path
from odoo.tests.common import SavepointCase


class TestMooncardMultiVatImport(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["account.account"].create(
            {
                "user_type_id": cls.env.ref("account.data_account_type_expenses").id,
                "name": "test expense 1",
                "code": "62510030",
            }
        )
        cls.env["account.account"].create(
            {
                "user_type_id": cls.env.ref("account.data_account_type_expenses").id,
                "name": "test expense 2",
                "code": "62510000",
            }
        )
        cls.env["account.account"].create(
            {
                "user_type_id": cls.env.ref("account.data_account_type_expenses").id,
                "name": "test expense 2",
                "code": "62510020",
            }
        )

    def test_import_multi_vat(self):
        old_transactions = self.env["newgen.payment.card.transaction"].search([])
        file_path = get_resource_path(
            "mooncard_payment_card_multi_vat", "tests/", "statement_sample.csv"
        )
        data = open(file_path, "rb").read()
        data = base64.b64encode(data)
        wizard = self.env["mooncard.csv.import"].create(
            {
                "mooncard_file": data,
            }
        )
        wizard.mooncard_import()
        transactions = self.env["newgen.payment.card.transaction"].search([])
        new_transactions = transactions - old_transactions
        self.assertEqual(len(new_transactions), 4)
        transaction = new_transactions.filtered(
            lambda t: t.description == "Déplacement1"
        )
        self.assertEqual(len(transaction.vat_line_ids), 2)
        vat_20 = transaction.vat_line_ids.filtered(
            lambda li: li.expense_account_id.code == "62510000"
        )
        vat_10 = transaction.vat_line_ids.filtered(
            lambda li: li.expense_account_id.code == "62510020"
        )
        self.assertEqual(vat_20.vat_company_currency, -2.17)
        self.assertEqual(vat_20.subtotal_company_currency, -8.68)
        self.assertEqual(vat_20.vat_rate, 20.0)
        self.assertEqual(vat_10.vat_company_currency, -3.95)
        self.assertEqual(vat_10.subtotal_company_currency, -35.55)
        self.assertEqual(vat_10.vat_rate, 10.0)
