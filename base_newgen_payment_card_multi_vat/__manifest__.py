# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "New-generation payment card Multi vat",
    "version": "14.0.1.0.0",
    "category": "Accounting",
    "license": "AGPL-3",
    "summary": "New-generation payment card with multi vat rate",
    "author": "Akretion",
    "website": "https://github.com/OCA/sale-workflow",
    "depends": ["base_newgen_payment_card"],
    "data": [
        "views/newgen_payment_card_transaction.xml",
        "security/ir.model.access.csv",
    ],
    "installable": True,
}
