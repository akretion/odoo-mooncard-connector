import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo14-addons-akretion-odoo-mooncard-connector",
    description="Meta package for akretion-odoo-mooncard-connector Odoo addons",
    version=version,
    install_requires=[
        'odoo14-addon-base_newgen_payment_card',
        'odoo14-addon-base_newgen_payment_card_start_end_dates',
        'odoo14-addon-l10n_fr_base_newgen_payment_card',
        'odoo14-addon-mooncard_payment_card',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 14.0',
    ]
)
