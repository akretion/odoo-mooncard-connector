from openupgradelib import openupgrade

@openupgrade.migrate(use_env=True)
def migrate(env, version):
    openupgrade.rename_models(env.cr, [
        ('mooncard.transaction', 'newgen.payment.card.transaction'),
        ('mooncard.account.mapping', 'newgen.payment.card.account.mapping'),
        ('mooncard.card', 'newgen.payment.card'),
    ])
    openupgrade.rename_tables(env.cr, [
        ('mooncard_transaction', 'newgen_payment_card_transaction'),
        ('mooncard_account_mapping', 'newgen_payment_card_account_mapping'),
        ('mooncard_card', 'newgen_payment_card'),
    ])
    openupgrade.rename_fields(env, [
        ('newgen.payment.card.transaction', 'newgen_payment_card_transaction', 'merchant', 'vendor'),
    ])
    env.cr.execute("""
        UPDATE newgen_payment_card_transaction SET transaction_type = 'expense' WHERE transaction_type = 'presentment'
    """)
