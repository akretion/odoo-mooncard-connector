import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo-addons-akretion-odoo-mooncard-connector",
    description="Meta package for akretion-odoo-mooncard-connector Odoo addons",
    version=version,
    install_requires=[
        'odoo-addon-base_newgen_payment_card>=15.0dev,<15.1dev',
        'odoo-addon-base_newgen_payment_card_start_end_dates>=15.0dev,<15.1dev',
        'odoo-addon-l10n_fr_base_newgen_payment_card>=15.0dev,<15.1dev',
        'odoo-addon-mooncard_payment_card>=15.0dev,<15.1dev',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 15.0',
    ]
)
