# © 2016-2017 Akretion (Alexis de Lattre <alexis.delattre@akretion.com>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_compare
from datetime import datetime, timedelta
from tempfile import TemporaryFile
import logging

logger = logging.getLogger(__name__)

try:
    import unicodecsv
except ImportError:
    logger.debug('Cannot `import unicodecsv`.')
try:
    import pycountry
except ImportError:
    logger.debug('Cannot `import pycountry`.')


class MooncardCsvImport(models.TransientModel):
    _name = 'mooncard.csv.import'
    _description = 'Import Mooncard Transactions'

    mooncard_file = fields.Binary(
        string='Bank Statement File', required=True)
    filename = fields.Char(string='Filename')

    @api.model
    def convert_datetime_to_utc(self, date_time_str):
        # %z can only be used in strptime() starting from python 3.2
        if date_time_str[-2:].isdigit():
            date_time_dt = datetime.strptime(
                date_time_str[:19], '%Y-%m-%d %H:%M:%S')
            if date_time_str[20] == '+':
                date_time_dt -= timedelta(
                    hours=int(date_time_str[21:23]),
                    minutes=int(date_time_str[23:]))
            elif date_time_str[20] == '-':
                date_time_dt += timedelta(
                    hours=int(date_time_str[21:23]),
                    minutes=int(date_time_str[23:]))
        else:
            date_time_dt = datetime.strptime(
                date_time_str, '%Y-%m-%d %H:%M:%S %Z')
        return date_time_dt

    @api.model
    def _prepare_transaction(self, line, speeddict, action='create'):
        bdio = self.env['business.document.import']
        account_analytic_id = account_id = False
        # convert to float
        float_fields = [
            'vat_eur', 'amount_eur', 'amount_currency',
            'vat_20_id', 'vat_10_id', 'vat_55_id', 'vat_21_id']
        for float_field in float_fields:
            if line.get(float_field):
                try:
                    line[float_field] = float(line[float_field])
                except Exception as e:
                    raise UserError(_(
                        "Cannot convert float field '%s' with value '%s'.")
                        % (float_field, line.get(float_field)))
            else:
                line[float_field] = 0.0
        total_vat_rates = line['vat_20_id'] + line['vat_10_id'] +\
            line['vat_55_id'] + line['vat_21_id']
        if float_compare(line['vat_eur'], total_vat_rates, precision_digits=2):
            raise UserError(_(
                "Error in the Mooncard CSV file: for transaction ID '%s' "
                "the column 'vat_eur' (%.2f) doesn't have the same value "
                "as the sum of the 4 columns per VAT rate (%.2f)")
                % (line['id'], line['vat_eur'], total_vat_rates))
        if line.get('charge_account'):
            account = bdio._match_account(
                {'code': line['charge_account']}, [],
                speed_dict=speeddict['accounts'])
            account_id = account.id
        if line.get('analytic_code_1'):
            account_analytic_id = speeddict['analytic'].get(
                line['analytic_code_1'].lower())
        ttype2odoo = {
            'P': 'presentment',
            'L': 'load',
        }
        if line.get('transaction_type') not in ttype2odoo:
            raise UserError(_(
                "Wrong transaction type '%s'. The only possible values are "
                "'P' (presentment) or 'L' (load).")
                % line.get('transaction_type'))
        transaction_type = ttype2odoo[line['transaction_type']]
        vals = {
            'transaction_type': transaction_type,
            'description': line.get('title'),
            'expense_categ_name': line.get('expense_category_name'),
            'expense_account_id': account_id,
            'account_analytic_id': account_analytic_id,
            'vat_company_currency': line['vat_eur'],
            'fr_vat_20_amount': line['vat_20_id'],
            'fr_vat_10_amount': line['vat_10_id'],
            'fr_vat_5_5_amount': line['vat_55_id'],
            'fr_vat_2_1_amount': line['vat_21_id'],
            'image_url': line.get('attachment'),
            'receipt_number': line.get('receipt_code'),
        }

        if action == 'update':
            return vals

        # Continue with fields required for create
        country_id = False
        if line.get('country_code') and len(line['country_code']) == 3:
            logger.debug(
                'search country with code %s with pycountry',
                line['country_code'])
            pcountry = pycountry.countries.get(alpha_3=line['country_code'])
            if pcountry and pcountry.alpha_2:
                country_id = speeddict['countries'].get(pcountry.alpha_2)
        currency_id = speeddict['currencies'].get(
            line.get('original_currency'))
        card_id = False
        if line.get('card_token'):
            card_id = speeddict['tokens'].get(line['card_token'])
            if not card_id:
                raise UserError(_(
                    "The CSV file contains the Moon Card '%s'. This "
                    "card is not registered in Odoo, cf menu "
                    "Accounting > Configuration > Miscellaneous > "
                    "Moon Cards)") % line.get('card_token'))
        payment_date = False
        if (
                transaction_type == 'presentment' and
                line.get('date_authorization')):
            payment_date = self.convert_datetime_to_utc(
                line['date_authorization'])

        vals.update({
            'unique_import_id': line.get('id'),
            'date': self.convert_datetime_to_utc(line['date_transaction']),
            'payment_date': payment_date,
            'card_id': card_id,
            'country_id': country_id,
            'merchant': line.get('supplier'),
            'total_company_currency': line['amount_eur'],
            'total_currency': line['amount_currency'],
            'currency_id': currency_id,
        })
        return vals

    @api.model
    def _prepare_speeddict(self):
        company = self.env.user.company_id
        bdio = self.env['business.document.import']
        speeddict = {
            'tokens': {}, 'accounts': {}, 'analytic': {},
            'countries': {}, 'currencies': {}}

        token_res = self.env['mooncard.card'].search_read(
            [('company_id', '=', company.id)], ['name'])
        for token in token_res:
            speeddict['tokens'][token['name']] = token['id']

        speeddict['accounts'] = bdio._prepare_account_speed_dict()

        analytic_res = self.env['account.analytic.account'].search_read(
            [('company_id', '=', company.id), ('code', '!=', False)], ['code'])
        for analytic in analytic_res:
            analytic_code = analytic['code'].strip().lower()
            speeddict['analytic'][analytic_code] = analytic['id']

        countries = self.env['res.country'].search_read(
            [('code', '!=', False)], ['code'])
        for country in countries:
            speeddict['countries'][country['code'].strip()] = country['id']

        currencies = self.env['res.currency'].search_read(
            ['|', ('active', '=', True), ('active', '=', False)], ['name'])
        for curr in currencies:
            speeddict['currencies'][curr['name']] = curr['id']
        return speeddict

    @api.multi
    def mooncard_import(self):
        self.ensure_one()
        mto = self.env['mooncard.transaction']
        speeddict = self._prepare_speeddict()
        logger.info('Importing Mooncard transactions.csv')
        fileobj = TemporaryFile('w+')
        fileobj.write(self.mooncard_file.decode('base64'))
        fileobj.seek(0)
        reader = unicodecsv.DictReader(
            fileobj, delimiter=',',
            quoting=unicodecsv.QUOTE_MINIMAL, encoding='utf8')
        i = 0
        exiting_transactions = {}
        existings = mto.search([])
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
            transaction = mto.create(vals)
            mt_ids.append(transaction.id)
        fileobj.close()
        if not mt_ids:
            raise UserError(_("No Mooncard transaction created nor updated."))
        action = self.env['ir.actions.act_window'].for_xml_id(
            'mooncard_base', 'mooncard_transaction_action')
        action.update({
            'domain': "[('id', 'in', %s)]" % mt_ids,
            'views': False,
            'nodestroy': False,
        })
        return action
