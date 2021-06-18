from openupgradelib import openupgrade


@openupgrade.migrate(use_env=True)
def migrate(env, version):
    # A bit hard to migrate fr_vat_20_amount and other 5.5, 2.1 and 10 fields to vat_rate
    # so we just delete all draft transaction, we will import it again
    env['newgen.payment.card.transaction'].search([('state', '=', 'draft')]).unlink()
