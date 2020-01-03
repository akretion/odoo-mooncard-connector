.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

=====================
Mooncard Payment Card
=====================

This is the Mooncard-specific module of the new-generation payment card framework. `Mooncard <http://www.mooncard.co/>`_ is a new-generation corporate card that propose:

* instant notification of each card payment on your mobile phone,
* easy and fast recording of your card expenses from your mobile phone.

Installation
============

To install this module, you need some additional Python librairies:

.. code::

  sudo pip install pycountry
  sudo pip install unicodecsv

Note: you should not use the Debian/Ubuntu package *python-pycountry* because, as of Ubuntu 16.04, the version is too old and has a slightly different API than the latest version of `pycountry on Pypi <https://pypi.python.org/pypi/pycountry/>`_ (and we are using the latest version of the API of pycountry in this module).

Configuration
=============

In the menu *Invoicing > Configuration > Payment Cards > Payment Cards*, you must create your Moon Cards.

In the Mooncard Web interface `app.mooncard.co <https://app.mooncard.co/>`_, go to *Paramètres > Natures de dépense* and update the column *Compte de charge* so that it matches exactly the account codes that you have in Odoo.

Usage
=====

Go to the menu *Invoicing > Payment Card > Mooncard Import* and upload the CSV file that you downloaded from your `Mooncard account <https://app.mooncard.co/>`_ under *Espace client > Relevés de compte > Exporter > Odoo*:

* Odoo will create the new Mooncard transactions,
* Odoo will update the existing Mooncard transactions that are still in draft.

[Still not ported to v12] For mileage expenses, use the same Odoo menu and upload the CSV file that you downloaded from your Mooncard account under *Dépenses > Frais kilométriques > Exporter*.

Roadmap
=======

* When the Mooncard webservices will be available, the module will be updated: the mooncard transactions will be automatically downloaded.

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
