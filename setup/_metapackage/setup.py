import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo12-addons-akretion-odoo-mooncard-connector",
    description="Meta package for akretion-odoo-mooncard-connector Odoo addons",
    version=version,
    install_requires=[
        'odoo12-addon-base_newgen_payment_card',
        'odoo12-addon-mooncard_payment_card',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 12.0',
    ]
)
