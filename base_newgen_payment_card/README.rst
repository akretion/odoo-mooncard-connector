.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

=====================================
New-generation payment card framework
=====================================

This is the base module of the new-generation payment card framework. This framework is designed to support new-generation payment cards that support features such as:

* instant notification on your smartphone upon payment,
* ability to take a picture of the receipt/invoice from your smartphone,
* ability to set expense description, expense category and VAT amount from your smartphone or PC,
* ability to export all payment information to a structured file or via an API.

This module is not useful by itself. You need to add a module specific to your new-generation payment card provider. For example, the module *mooncard_payment_card* adds support for Mooncard `Mooncard <http://www.mooncard.co/>`_.

Installation
============

Some Python libs are required:

.. code::

  pip3 install --upgrade unidecode
  pip3 install --upgrade Pillow

Configuration
=============

Refer to the configuration instructions written in the provider-specific module.

Usage
=====

Once the transactions have been imported in Odoo, you can still change/update some information on the transactions (description, expense account, analytic account, etc.).

Then, you can process the transaction, either one-by-one or multiple transactions at the same time.

For each expense transaction, Odoo will:

* generate a supplier invoice (or refund), put the receipt as attachment and validate the invoice, which will auto-generate an entry in the purchase journal,
* create an entry in the bank journal linked to the payment card,
* reconcile these 2 entries.

For each load transaction (the transaction to load money on the special bank account linked to the payment card), Odoo will generate an entry in the bank journal linked to the payment card. The counter-part will be the *Inter-bank transfer account* (unfortunately, this field is not display in the Invoicing configuration page ; the *account_usability* module of Akretion fixes this).

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
