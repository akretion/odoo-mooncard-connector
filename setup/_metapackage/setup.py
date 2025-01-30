import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo10-addons-akretion-odoo-mooncard-connector",
    description="Meta package for akretion-odoo-mooncard-connector Odoo addons",
    version=version,
    install_requires=[
        'odoo10-addon-mooncard_base',
        'odoo10-addon-mooncard_invoice',
        'odoo10-addon-mooncard_invoice_start_end_dates',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 10.0',
    ]
)
