# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from openupgradelib import openupgrade


@openupgrade.migrate()
def migrate(env, version):
    openupgrade.logged_query(
        env.cr,
        """
            UPDATE newgen_payment_card_transaction
            SET
                invoice_id = am.id
            FROM account_invoice ai
            JOIN account_move am ON am.old_invoice_id = ai.id
            WHERE newgen_payment_card_transaction.old_invoice_id = ai.id AND newgen_payment_card_transaction.old_invoice_id IS NOT NULL
        """,
    )
