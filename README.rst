.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

=======================
Odoo-Mooncard connector
=======================

This project is a connector between `Odoo <https://www.odoo.com/>`_, the leading OpenSource ERP solution, and `Mooncard <http://www.mooncard.co/>`_, a new-generation corporate card solution.

Mooncard propose:

* instant notification of each card payment on your smartphone,
* easy and fast recording of your card expenses from your smartphone,
* management of your mileage expenses.

The diagram below illustrate the full process from the payment with Mooncard to the accounting entries in Odoo:

.. figure:: http://public.akretion.com/diagram_odoo_mooncard.jpg
   :alt: Diagram to illustrate the full process from a payment with Mooncard to the accounting entries in Odoo

Mooncard has been launched in France in October 2016 ; it will be extended to other countries in the future.

Recording card expenses in accounting
=====================================

To record a corporate card transaction in the books of the company, you need:

1. the **date** of the expense,
2. the **total amount**,
3. the **VAT amount**, to be able to refund VAT,
4. the **description** of the expense,
5. the **kind of expense** (train ticket, hotel, book, gift, etc.), to be able to choose the right expense account in the chart of accounts,
6. a **receipt**, to have a proof of the expense for the fiscal administration.

Then, the accountant will have to:

* create an account move to record the expense,
* create an account move to record the payment,
* reconcile the expense and the payment.

How Mooncard works
==================

A Mooncard is a special `MasterCard <http://www.mastercard.com/>`_ card linked to a dedicated bank account. To make a payment, you can use the Mooncard like any MasterCard card. When you make a payment with your Mooncard:

1. Mooncard instantly receives the raw bank transaction, which contains all the details about the payment (date, time, amount in local currency, amount in EUR) and about the vendor (vendor name, country, activity, etc.). Among the 6 information needed to record the transaction in the accounting:

  - the **date** is known,
  - the **total amount** is known,
  - the **kind of expense** can be guessed from the activity of the vendor,
  - the **VAT amount** can be guessed from the kind of expense and the country of the vendor.

2. The user is instantly notified of the payment on his smartphone. With his smartphone, he can:

  - modify the **kind of expense** if needed,
  - modify the **VAT amount** if needed,
  - write a **description** of the expense. If he has granted Mooncard read access to his agenda, he can select any entry of his agenda as a description of the expense (e.g. *Lunch with Mr Chic*)
  - take a **picture of the receipt** with the camera of his smartphone.

3. Once the user has validated the information on his smartphone, the information is sent to Mooncard.

4. The accountant can import the transaction from Mooncard to the accounting software; with the Odoo-Mooncard connector, it is very easy!

Competing enterprise expense management solutions also take advantage of the smartphone of the user to take a picture of the receipt and then use OCR (Optical Character Recognition) to try to extract the relevant information. But real-life experience shows that it regularly fails to extract all the required information. The solution proposed by Mooncard, with the use of a special corporate card, is better and more reliable than the competing solutions.

How the Odoo-Mooncard connector works
=====================================

The accountant will download the Mooncard bank statement (CSV file) and upload it in Odoo.

Then, in Odoo, the accountant can:

1. check the information of each expense by comparing them with the image of the receipt. He can modify the description of the expense, the VAT amount, the expense category and the expense account if needed.

2. process the transactions in just one click! For each transaction, Odoo will create a supplier invoice, attach the image of the receipt to that invoice and create the corresponding payment.

Please refer to the README of each module for a detailed instructions to configure and use the Odoo-Mooncard connector.

Author
======

This connector has been developped by Alexis de Lattre from `Akretion <http://www.akretion.com/>`_, who is a happy Mooncard user since July 2016!
