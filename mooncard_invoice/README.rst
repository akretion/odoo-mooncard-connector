.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

================
Mooncard Invoice
================

This module is part of the Odoo-Mooncard connector. `Mooncard <https://www.mooncard.co/>`_ is a new-generation corporate card that propose:

* instant notification of each card payment on your mobile phone,
* easy and fast recording of your card expenses from your mobile phone.

Mooncard is only available in France for the moment, but it will be extended to other countries in the future.

You should use this module if your Mooncards are attached to the bank account of the company. If the Mooncards are attached to the private bank account of the employees, you should use the module *mooncard_expense* (to be developped) instead.

Installation
============

This module depend on the module *account_invoice_import* which is available in the `EDI OCA project <https://github.com/OCA/edi>`_ on Github.

Configuration
=============

First, read the configuration instructions of the *mooncard_base* module.

As Mooncard is attached to a pre-paid account, you must create a dedicated bank journal and accounting account that will correspond to the Mooncard pre-paid account. On this journal, the *Default Debit Account* and the *Default Credit Account* must be set to the Mooncard accounting account.

Then, in the menu *Accounting > Configuration > Miscellaneous > Moon Cards*, for each Moon Card, you must configure the related *Mooncard Bank Journal*. If all the Mooncards are attached to the same Mooncard account, you will just create one Mooncard journal and attach all your Moon Cards to this journal.

In the menu *Settings > Configuration > Accounting*, in the *Mooncard* section, you must select the *Internal Bank Transfer Account* (580000 in the French chart of accounts).

Usage
=====

First, you must import the Mooncard transactions CSV file, cf the README of the *mooncard_base* module.

Then, go to the menu *Accounting > Mooncard > Mooncard Transactions* and check if the parameters of the draft Mooncard expenses are correct. For that, you can click on the magnifier to visualize the image of the receipt and:

* check that the *VAT amount* is correct and update it if it's wrong,
* update the *Description* of the expense if needed,
* check that the selected *Expense Product* is correct and change it if it's wrong.

Eventually, you can process the transactions that are complete and correct:

* you can process them one by one: click on the *Process Line* button on each line,
* you can process several at once: in the list view, select several draft mooncard transactions and click on *More > Process Lines*.

When you process a Mooncard transaction:

* for a *load* transaction, Odoo will generate an account move in the Mooncard Bank Journal between the *Internal Bank Transfer Account* and the *Mooncard Bank Account*,

* for an *expense* transaction, Odoo will:

  - create and validate a supplier invoice and put the image of the receipt as attachment,
  - create a payment in the Mooncard Bank Journal,
  - reconcile the supplier invoice and the payment.

Roadmap
=======

Please send us feedback on this module so that we can feed the roadmap !

Bug Tracker
===========

Bugs are tracked on `GitHub Issues
<https://github.com/akretion/odoo-mooncard-connector/issues>`_. In case of trouble, please
check there if your issue has already been reported. If you spotted it first,
help us smashing it by providing a detailed and welcomed feedback.

Credits
=======

Contributors
------------

* Alexis de Lattre <alexis.delattre@akretion.com>
