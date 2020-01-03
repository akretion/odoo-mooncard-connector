# Copyright 2016-2019 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero
from datetime import datetime
import unicodecsv
from unidecode import unidecode
from tempfile import TemporaryFile
import logging
import pycountry
import base64

logger = logging.getLogger(__name__)


class MooncardCsvImport(models.TransientModel):
    _name = 'mooncard.csv.import'
    _description = 'Import Mooncard Transactions'

    mooncard_file = fields.Binary(string='CSV File', required=True)
    filename = fields.Char(string='Filename')

    @api.model
    def partner_match(self, merchant, speed_entry):
        if speed_entry[0] in merchant:
            return speed_entry[1]
        else:
            return False

    @api.model
    def _prepare_transaction(self, line, speeddict, action='create'):
        bdio = self.env['business.document.import']
        account_analytic_id = expense_account_id = card_id = partner_id = False
        # convert to float
        float_fields = [
            'vat_eur', 'amount_eur', 'amount_currency',
            'vat_20_id', 'vat_10_id', 'vat_55_id', 'vat_21_id']
        for float_field in float_fields:
            if line.get(float_field):
                try:
                    line[float_field] = float(line[float_field])
                except Exception:
                    raise UserError(_(
                        "Cannot convert float field '%s' with value '%s'.")
                        % (float_field, line.get(float_field)))
            else:
                line[float_field] = 0.0
        total_vat_rates = line['vat_20_id'] + line['vat_10_id'] +\
            line['vat_55_id'] + line['vat_21_id']
        if float_compare(line['vat_eur'], total_vat_rates, precision_digits=2):
            logger.warning(
                "In the Mooncard CSV file: for transaction ID '%s' "
                "the column 'vat_eur' (%.2f) doesn't have the same value "
                "as the sum of the 4 columns per VAT rate (%.2f). Check "
                "that it is foreign VAT.",
                line['id'], line['vat_eur'], total_vat_rates)

        # Transaction Type
        ttype2odoo = {
            'P': 'expense',
            'L': 'load',
            }
        if line.get('transaction_type') not in ttype2odoo:
            raise UserError(_(
                "Wrong transaction type '%s'. The only possible values are "
                "'P' (expense) or 'L' (load).")
                % line.get('transaction_type'))
        transaction_type = ttype2odoo[line['transaction_type']]

        # Card
        if line.get('card_token'):
            card_id = speeddict['tokens'].get(line['card_token'])
            if not card_id:
                raise UserError(_(
                    "The CSV file contains the Moon Card '%s'. This "
                    "card is not registered in Odoo, cf menu "
                    "Accounting > Configuration > Miscellaneous > "
                    "Moon Cards)") % line.get('card_token'))

        # Accounts
        if transaction_type == 'expense':
            if line.get('charge_account'):
                expense_account = bdio._match_account(
                    {'code': line['charge_account']}, [],
                    speed_dict=speeddict['accounts'])
                expense_account_id = expense_account.id

            if card_id and expense_account_id:
                tuple_match = (card_id, expense_account_id)
                if tuple_match in speeddict['mapping']:
                    expense_account_id = speeddict['mapping'][tuple_match]

            if line.get('analytic_code_1'):
                account_analytic_id = speeddict['analytic'].get(
                    line['analytic_code_1'].lower())

        # Partner and bank_counterpart_account_id
        if transaction_type == 'load':
            bank_counterpart_account_id = speeddict['transfer_account_id']
        elif transaction_type == 'expense':
            merchant = line.get('supplier') and line['supplier'].strip()
            partner_id = speeddict['default_partner_id']
            if merchant:
                merchant_match = unidecode(merchant.upper())
                for speed_entry in speeddict['partner']:
                    partner_match = self.partner_match(
                        merchant_match, speed_entry)
                    if partner_match:
                        partner_id = partner_match
                        break
            partner = self.env['res.partner'].browse(partner_id)
            bank_counterpart_account_id =\
                partner.property_account_payable_id.id

        # VAT rate
        vat_rate = 0
        if not float_is_zero(line['vat_eur'], precision_digits=2):
            rates_amount = [
                ('20.0', abs(line['vat_20_id'])),
                ('10.0', abs(line['vat_10_id'])),
                ('5.5', abs(line['vat_55_id'])),
                ('2.1', abs(line['vat_21_id'])),
                ]
            rates_amount_sorted = sorted(
                rates_amount, key=lambda to_sort: to_sort[1])
            vat_rate = rates_amount_sorted[-1][0]

        vals = {
            'transaction_type': transaction_type,
            'description': line.get('title'),
            'expense_categ_name': line.get('expense_category_name'),
            'expense_account_id': expense_account_id,
            'account_analytic_id': account_analytic_id,
            'vat_company_currency': line['vat_eur'],
            'vat_rate': vat_rate,
            'image_url': line.get('attachment'),
            'receipt_number': line.get('receipt_code'),
            'partner_id': partner_id,
            'bank_counterpart_account_id': bank_counterpart_account_id,
            }

        if action == 'update':
            return vals

        # Continue with fields required for create
        country_id = payment_date = False
        if line.get('country_code') and len(line['country_code']) == 3:
            logger.debug(
                'search country with code %s with pycountry',
                line['country_code'])
            pcountry = pycountry.countries.get(alpha_3=line['country_code'])
            if pcountry and pcountry.alpha_2:
                country_id = speeddict['countries'].get(pcountry.alpha_2)
        currency_id = speeddict['currencies'].get(
            line.get('original_currency'))
        if (
                transaction_type == 'expense' and
                line.get('date_authorization')):
            # Mooncard now always gives us datetime in UTC
            # example : 2019-04-18 13:35:06 UTC
            payment_date = datetime.strptime(
                line['date_authorization'], '%Y-%m-%d %H:%M:%S %Z')

        vals.update({
            'unique_import_id': line.get('id'),
            'date': line['date_transaction'] and line['date_transaction'][:10],
            'payment_date': payment_date,
            'card_id': card_id,
            'country_id': country_id,
            'merchant': line.get('supplier') and line['supplier'].strip(),
            'total_company_currency': line['amount_eur'],
            'total_currency': line['amount_currency'],
            'currency_id': currency_id,
        })
        return vals

    @api.model
    def _prepare_mileage(self, line, speeddict, action='create'):
        bdio = self.env['business.document.import']
        account_analytic_id = False
        # convert to float/int
        line['price_unit'] = float(line[u'Barême kilométrique'])
        line['km'] = int(line[u'Distance (km)'])
        account_analytic_id = account_id = trip_type = False
        if line.get('Codes analytiques'):
            account_analytic_id = speeddict['analytic'].get(
                line['Codes analytiques'].lower())
        if line.get('Compte de charge'):
            account = bdio._match_account(
                {'code': line['Compte de charge']}, [],
                speed_dict=speeddict['accounts'])
            account_id = account.id
        typedict = {
            'Aller Simple': 'oneway',
            'Aller / Retour': 'roundtrip',
            }
        if line.get('Type de trajet') and line['Type de trajet'] in typedict:
            trip_type = typedict[line['Type de trajet']]

        vals = {
            'km': line['km'],
            'price_unit': line['price_unit'],
            'date': line['Date'],
            'description': line['Description'],
            'car_name': line[u'Véhicule'],
            'car_plate': line.get(u"Immatriculation"),
            'car_fiscal_power': line.get(u'Puissance fiscale'),
            'departure': line.get(u'Départ'),
            'arrival': line.get(u'Arrivée'),
            'trip_type': trip_type,
            'account_analytic_id': account_analytic_id,
            'expense_account_id': account_id,
            }

        if action == 'update':
            return vals

        # Continue with fields required for create
        email = line.get('Email')
        if not email:
            raise UserError(_('Missing email'))
        email = email.strip().lower()
        if email not in speeddict['partner']:
            raise UserError(_(
                "No partner with email '%s' found") % email)
        partner_id = speeddict['partner'][email]
        vals.update({
            'unique_import_id': line.get('Identifiant unique'),
            'partner_id': partner_id,
        })
        return vals

    @api.model
    def _prepare_mileage_speeddict(self):
        bdio = self.env['business.document.import']
        company = self.env.user.company_id
        speeddict = {'partner': {}, 'analytic': {}, 'accounts': {}}

        partner_res = self.env['res.partner'].search_read(
            [('email', '!=', False)], ['email'])
        for partner in partner_res:
            email = partner['email'].strip().lower()
            speeddict['partner'][email] = partner['id']

        analytic_res = self.env['account.analytic.account'].search_read(
            [('company_id', '=', company.id), ('code', '!=', False)], ['code'])
        for analytic in analytic_res:
            analytic_code = analytic['code'].strip().lower()
            speeddict['analytic'][analytic_code] = analytic['id']
        speeddict['accounts'] = bdio._prepare_account_speed_dict()
        return speeddict

    def mooncard_import_mileage(self, fileobj):
        mmo = self.env['mooncard.mileage']
        speeddict = self._prepare_mileage_speeddict()
        fileobj.seek(0)
        reader = unicodecsv.DictReader(
            fileobj, delimiter=';',
            quoting=unicodecsv.QUOTE_MINIMAL, encoding='latin1')
        i = 0
        exiting_mileage = {}
        existings = mmo.search([])
        for l in existings:
            exiting_mileage[l.unique_import_id] = l
        mm_ids = []
        for line in reader:
            i += 1
            # replace '' by False, so as to make the domains such as
            # ('image_url', '!=', False) work
            # and strip regular strings
            for key, value in line.items():
                if value:
                    line[key] = value.strip()
                else:
                    line[key] = False
            logger.debug("line=%s", line)
            if not line.get('Identifiant unique'):
                raise UserError(_(
                    "Missing ID in CSV file line %d.") % i)
            existing_import_id = False
            if line['Identifiant unique'] in exiting_mileage:
                existing_import_id = line['Identifiant unique']

                mileage = exiting_mileage[existing_import_id]
                logger.debug(
                    'Existing line with unique ID %s (odoo ID %s, state %s)',
                    existing_import_id, mileage.id, mileage.state)
                if mileage.state == 'draft':
                    # update existing lines
                    wvals = self._prepare_mileage(
                        line, speeddict, action='update')
                    mileage.write(wvals)
                    mm_ids.append(mileage.id)
                continue
            vals = self._prepare_mileage(line, speeddict)
            mileage = mmo.create(vals)
            mm_ids.append(mileage.id)
        fileobj.close()
        if not mm_ids:
            raise UserError(_("No Mooncard mileage created nor updated."))
        action = self.env['ir.actions.act_window'].for_xml_id(
            'mooncard_base', 'mooncard_mileage_action')
        action.update({
            'domain': "[('id', 'in', %s)]" % mm_ids,
            'views': False,
            'nodestroy': False,
            })
        return action

    def mooncard_import(self):
        self.ensure_one()
        npcto = self.env['newgen.payment.card.transaction']
        speeddict = npcto._prepare_import_speeddict()
        logger.info('Importing Mooncard transactions.csv')
        fileobj = TemporaryFile('wb+')
        fileobj.write(base64.b64decode(self.mooncard_file))
        fileobj.seek(0)
        # TODO port mileage
        # file_content = fileobj.read()
        # if file_content.startswith('Identifiant unique;Collaborateur;Email'):
        #    return self.mooncard_import_mileage(fileobj)
        fileobj.seek(0)
        reader = unicodecsv.DictReader(
            fileobj, delimiter=',',
            quoting=unicodecsv.QUOTE_MINIMAL, encoding='utf8')
        i = 0
        exiting_transactions = {}
        existings = npcto.search([])
        for l in existings:
            exiting_transactions[l.unique_import_id] = l
        mt_ids = []
        for line in reader:
            i += 1
            # replace '' by False, so as to make the domains such as
            # ('image_url', '!=', False) work
            # and strip regular strings
            for key, value in line.items():
                if value:
                    line[key] = value.strip()
                else:
                    line[key] = False
            logger.debug("line=%s", line)
            if not line.get('id'):
                raise UserError(_(
                    "Missing ID in CSV file line %d.") % i)
            # line['transaction_id'] used for the transition
            # from transactions.csv to Mooncard bank statements
            existing_import_id = False
            if line['id'] in exiting_transactions:
                existing_import_id = line['id']
            # only for the transition to CSV bank statements on July 2017
            # To be removed
            elif (
                    line['transaction_id'] and
                    line['transaction_id'] in exiting_transactions):
                existing_import_id = line['transaction_id']
            if existing_import_id:
                transaction = exiting_transactions[existing_import_id]
                logger.debug(
                    'Existing line with unique ID %s (odoo ID %s, state %s)',
                    existing_import_id, transaction.id, transaction.state)
                if transaction.state == 'draft':
                    # update existing lines
                    wvals = self._prepare_transaction(
                        line, speeddict, action='update')
                    transaction.write(wvals)
                    mt_ids.append(transaction.id)
                continue
            vals = self._prepare_transaction(line, speeddict)
            transaction = npcto.create(vals)
            mt_ids.append(transaction.id)
        fileobj.close()
        if not mt_ids:
            raise UserError(_(
                "No payment card transaction created nor updated."))
        action = self.env.ref(
            'base_newgen_payment_card.newgen_payment_card_transaction_action'
            ).read()[0]
        action.update({
            'domain': "[('id', 'in', %s)]" % mt_ids,
            'views': False,
            'nodestroy': False,
            })
        return action
