# -*- coding: utf-8 -*-
# Copyright 2020 Akretion France (http://www.akretion.com)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError
from odoo.tools import float_compare
from datetime import datetime, timedelta
import dateutil.parser
from datetime import datetime, timedelta
from unidecode import unidecode
import requests
import logging
MEANINGFUL_PARTNER_NAME_MIN_SIZE = 3


logger = logging.getLogger(__name__)


try:
    from requests_oauthlib import OAuth2Session
except ImportError:
    logger.debug('Cannot import requests-oauthlib')

API_URL = ""
SANDBOX_API_URL = "https://sandbox.mooncard.co/api/v3"
TOKEN_URL = ''
SANDBOX_TOKEN_URL = 'https://sandbox.mooncard.co/oauth/token'
MARGIN_TOKEN_EXPIRY_SECONDS = 240
MAX_PAGE = 1000
PER_PAGE = 50


class ResCompany(models.Model):
    _inherit = 'res.company'

    mooncard_api_login = fields.Char(
        string='Mooncard API Login')
    mooncard_api_password = fields.Char(
        string='Mooncard API Password')
    mooncard_api_company_uuid = fields.Char(
        string='Mooncard API Company UUID')

    def mooncard_get_api_oauth_identifiers(self, raise_if_ko=False):
        self.ensure_one()
        oauth_id = tools.config.get('mooncard_api_oauth_id')
        oauth_secret = tools.config.get('mooncard_api_oauth_secret')
        if not oauth_id:
            msg = _(
                "Missing key 'mooncard_api_oauth_id' in Odoo server "
                "configuration file")
            if raise_if_ko:
                raise UserError(msg)
            else:
                logger.warning(msg)
                return False
        if not oauth_secret:
            msg = _(
                "Missing key 'mooncard_api_oauth_secret' in Odoo server "
                "configuration file")
            if raise_if_ko:
                raise UserError(msg)
            else:
                logger.warning(msg)
                return False
        sandbox = tools.config.get('mooncard_api_sandbox')
        if not sandbox:
            sandbox = False
        return (oauth_id, oauth_secret, sandbox)

    def mooncard_get_api_params(self, raise_if_ko=False):
        self.ensure_one()
        api_params = {}
        oauth_identifiers = self.mooncard_get_api_oauth_identifiers(
            raise_if_ko=raise_if_ko)
        if (
                self.mooncard_api_login and
                self.mooncard_api_password and
                self.mooncard_api_company_uuid and
                oauth_identifiers):
            api_params = {
                'login': self.mooncard_api_login.strip(),
                'password': self.mooncard_api_password.strip(),
                'company_uuid': self.mooncard_api_company_uuid.strip(),
                'oauth_id': oauth_identifiers[0],
                'oauth_secret': oauth_identifiers[1],
                'sandbox': oauth_identifiers[2],
            }
        elif raise_if_ko:
            raise UserError(_(
                "Missing Mooncard API parameters on the company %s")
                % self.display_name)
        else:
            logger.warning(
                'Some Mooncard API parameters are missing on company %s',
                self.display_name)
        return api_params

    @api.model
    @tools.ormcache(
            "oauth_id", "oauth_secret",
            "login", "password", "company_uuid", "sandbox")
    def _mooncard_get_new_token(
            self, oauth_id, oauth_secret,
            login, password, company_uuid, sandbox):
        url = sandbox and SANDBOX_TOKEN_URL or TOKEN_URL
        logger.info('Requesting new token from mooncard via %s', url)
        try:
            r = requests.post(
                url,
                data={
                    "grant_type": "password",
                    "client_id": oauth_id,
                    "client_secret": oauth_secret,
                    "company_id": company_uuid,
                    "username": login,
                    "password": password,
                    })
            logger.debug('_mooncard_get_new_token HTTP answer code=%s', r.status_code)
        except requests.exceptions.ConnectionError as e:
            logger.error("Connection to %s failed. Error: %s", url, e)
            raise UserError(_(
                "Connection to Mooncard API (URL %s) failed. "
                "Check the internet connection of the Odoo server.\n\n"
                "Error details: %s") % (url, e))
        except requests.exceptions.RequestException as e:
            logger.error("Request for new mooncard API token failed. Error: %s", e)
            raise UserError(_(
                "Technical failure when trying to get a new token "
                "for Mooncard API.\n\nError details: %s") % e)
        token = r.json()
        if r.status_code != 200:
            logger.error(
                'Error %s in the request to get a new token. '
                'Error type: %s. Error description: %s',
                r.status_code, token.get('error'),
                token.get('error_description'))
            raise UserError(_(
                "Error in the request to get a new token for Mooncard API.\n\n"
                "HTTP error code: %s. Error type: %s. "
                "Error description: %s.") % (
                    r.status_code, token.get('error'),
                    token.get('error_description')))
        # {'access_token': 'xxxxxxxxxxxxxxxxx',
        # 'token_type': 'Bearer', 'expires_in': 7200, 'scope': 'public'}
        logger.info(
            'New Mooncard token retreived with a validity of '
            '%d seconds', token.get('expires_in'))
        seconds = int(token.get('expires_in')) - MARGIN_TOKEN_EXPIRY_SECONDS
        expiry_date_gmt = datetime.utcnow() + timedelta(seconds=seconds)
        return (token, expiry_date_gmt)

    def _mooncard_get_token(self, api_params):
        token, expiry_date_gmt = self._mooncard_get_new_token(
            api_params['oauth_id'], api_params['oauth_secret'],
            api_params['login'], api_params['password'],
            api_params['company_uuid'], api_params['sandbox'])
        now = datetime.utcnow()
        logger.debug('_get_token expiry_date_gmt=%s now=%s', expiry_date_gmt, now)
        if now > expiry_date_gmt:
            # force clear cache
            self._mooncard_get_new_token.clear_cache(self.env[self._name])
            logger.info('Mooncard token cleared from cache.')
            token, expiry_date_gmt = self._get_new_token(
                api_params['oauth_id'], api_params['oauth_secret'],
                api_params['login'], api_params['password'],
                api_params['company_uuid'], api_params['qualif'])
        else:
            logger.info(
                'Mooncard token expires on %s GMT (includes margin)',
                expiry_date_gmt)
        return token

    @api.model
    def mooncard_get(self, api_params, url_path, params=None, session=None):
        url_base = api_params['sandbox'] and SANDBOX_API_URL or API_URL
        url = '%s/%s' % (url_base, url_path)
        if session is None:
            token = self._mooncard_get_token(api_params)
            session = OAuth2Session(api_params['oauth_id'], token=token)
        logger.info(
            'Mooncard API GET request to %s params=%s', url, params)
        try:
            r = session.get(
                url, verify=True, params=params)
        except requests.exceptions.ConnectionError as e:
            logger.error("Connection to %s failed. Error: %s", url, e)
            raise UserError(_(
                "Connection to Mooncard API (URL %s) failed. "
                "Check the Internet connection of the Odoo server.\n\n"
                "Error details: %s") % (url, e))
        except requests.exceptions.RequestException as e:
            logger.error("Mooncard GET request failed. Error: %s", e)
            raise UserError(_(
                "Technical failure when trying to connect to Mooncard API.\n\n"
                "Error details: %s") % e)
        if r.status_code != 200:
            logger.error(
                "Mooncard API webservice answered with HTTP status code=%s and "
                "content=%s" % (r.status_code, r.text))
            raise UserError(_(
                "Wrong request on %s. HTTP error code received from "
                "Mooncard: %s") % (url, r.status_code))

        answer = r.json()
        logger.info('Mooncard WS answer payload: %s', answer)
        return (answer, session)

    def _prepare_speeddict(self):
        self.ensure_one()
        bdio = self.env['business.document.import']
        mto = self.env['mooncard.transaction']
        speeddict = {
            'tokens': {}, 'accounts': {}, 'analytic': {},
            'countries': {}, 'currencies': {}, 'mapping': {},
            'company_id': self.id, 'company_currency': self.currency_id.name,
            'partner': [], 'partner_mail': {},
            }

        token_res = self.env['mooncard.card'].search_read(
            [('company_id', '=', self.id)], ['name'])
        for token in token_res:
            speeddict['tokens'][token['name']] = token['id']

        speeddict['accounts'] = bdio._prepare_account_speed_dict()

        analytic_res = self.env['account.analytic.account'].search_read(
            [('company_id', '=', self.id), ('code', '!=', False)], ['code'])
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
        # if mooncard_invoice is installed
        if 'mooncard.account.mapping' in self.env:
            map_res = self.env['mooncard.account.mapping'].search_read(
                [('company_id', '=', self.id)])
            for map_entry in map_res:
                speeddict['mapping'][
                    (map_entry['card_id'][0],
                     map_entry['expense_account_id'][0])] =\
                    map_entry['force_expense_account_id'][0]
        if not self.transfer_account_id:
            raise UserError(_(
                "Missing 'Internal Bank Transfer Account' on company '%s'.")
                % self.display_name)
        speeddict['transfer_account_id'] = self.transfer_account_id.id
        default_partner = mto._default_partner()
        if default_partner.parent_id:
            raise UserError(_(
                "The default partner (%s) should be a parent partner.")
                % default_partner.display_name)
        speeddict['default_partner_id'] = default_partner.id
        specific_partner_existing_transactions = mto.search_read([
            ('state', '=', 'done'),
            ('transaction_type', '=', 'presentment'),
            ('merchant', '!=', False),
            ('partner_id', '!=', False),
            ('partner_id', '!=', speeddict['default_partner_id'])],
            ['merchant', 'partner_id'])
        for trans in specific_partner_existing_transactions:
            speeddict['partner'].append((
                unidecode(trans['merchant']).strip().upper(),
                trans['partner_id'][0]))
        partners = self.env['res.partner'].search_read(
                [('parent_id', '=', False)], ['name'])
        for partner in partners:
            partner_name = unidecode(partner['name'].strip().upper())
            if len(partner_name) >= MEANINGFUL_PARTNER_NAME_MIN_SIZE:
                speeddict['partner'].append((partner_name, partner['id']))
        # for mileage
        partner_res = self.env['res.partner'].search_read(
            [('email', '!=', False)], ['email'])
        for partner in partner_res:
            email = partner['email'].strip().lower()
            speeddict['partner_mail'][email] = partner['id']
        return speeddict

    def mooncard_api_import(self):
        self.ensure_one()
        speeddict = self._prepare_speeddict()
        logger.info('Importing Mooncard transactions via API')
        api_params = self.mooncard_get_api_params()
        page = 1
        speeddict['api_exp_categ'] = {}  # key = UUID, value = {'name': , 'code': }
        session = None
        while page < MAX_PAGE:
            res_categ, session = self.mooncard_get(
                api_params, 'expense_categories',
                params={'page': page, 'per_page': PER_PAGE}, session=session)
            for categ in res_categ:
                if categ.get('charge_account'):
                    speeddict['api_exp_categ'][categ['id']] = {
                        'code': categ['charge_account'],
                        'name': categ.get('name'),
                        }
            if not res_categ:
                break
            page += 1

        mt_ids = self.mooncard_api_transaction_import(
            api_params, session, speeddict)
        self.mooncard_api_mileage_import(api_params, session, speeddict)
        return mt_ids

    def mooncard_api_transaction_import(self, api_params, session, speeddict):
        self.ensure_one()
        mto = self.env['mooncard.transaction']
        # Get MC "bank" accounts
        res_accounts, session = self.mooncard_get(
            api_params, 'accounts', session=session)
        if len(res_accounts) != 1:
            raise UserError(
                "The /accounts webservice reported %d accounts. "
                "The module currently only support 1 account."
                % len(res_accounts))
        res_account = res_accounts[0]
        mc_account_id = res_account['id']
        mc_currency_code = res_account['currency']
        if mc_currency_code != speeddict['company_currency']:
            raise UserError(
                "The currency of the Mooncard account is %s where as the "
                "currency of company '%s' is %s." % (
                    mc_currency_code,
                    self.display_name,
                    speeddict['company_currency']))
        logger.debug('mc_account_id=%s', mc_account_id)
        exiting_transactions = {}
        existings = mto.search_read(
            [('company_id', '=', self.id)],
            ['state', 'unique_import_id'])
        for l in existings:
            exiting_transactions[l['unique_import_id']] = {
                'state': l['state'],
                'id': l['id'],
                }

        mt_ids = []
        expense_needed = {}
        page = 1
        # Get MC bank statement lines
        while page < MAX_PAGE:
            movements, session = self.mooncard_get(
                api_params, 'account_movements', session=session,
                params={
                    'account_id': mc_account_id,
                    'page': page,
                    'per_page': PER_PAGE})
            existing_done = 0
            for st_line in movements:
                st_line_uuid = st_line['id']
                transaction_type = st_line['transaction_type']
                line = {
                    'transaction_type': transaction_type,
                    'card_token': str(st_line['token']),
                    'amount_eur': float(st_line['change_real']),
                    'date_transaction': st_line['transaction_date'],
                    'transaction_link': st_line.get('transaction_link', False),
                    'id': st_line['id'],
                    }
                if st_line_uuid in exiting_transactions:
                    odoo_state = exiting_transactions[st_line_uuid]['state']
                    if odoo_state == 'draft':  # need update
                        existing_transaction_id = exiting_transactions[st_line_uuid]['id']
                        if transaction_type == 'P':
                            line['existing_transaction_id'] = existing_transaction_id
                            expense_needed[line['transaction_link']] = line
                        elif transaction_type == 'L':
                            wvals = mto._prepare_transaction(
                                line, speeddict, action='update')
                            transaction = mto.browse(existing_transaction_id)
                            transaction.write(wvals)
                            mt_ids.append(transaction.id)
                    elif odoo_state == 'done':
                        existing_done += 1
                        logger.info(
                            'Transaction %s is already in done state in Odoo. '
                            'Do nothing.', st_line_uuid)
                        continue
                else:
                    if transaction_type == 'P':
                        expense_needed[line['transaction_link']] = line
                    elif transaction_type == 'L':
                        wvals = mto._prepare_transaction(
                            line, speeddict, action='create')
                        transaction = mto.create(wvals)
                        mt_ids.append(transaction.id)

            if not movements:
                break
            if existing_done == len(movements):
                logger.info(
                    'No need to go further in account_movements, '
                    'we had a page full of existing done transactions')
                break
            page += 1

        if expense_needed:
            page = 1
            while page < MAX_PAGE:
                expenses, session = self.mooncard_get(
                    api_params, 'expenses', session=session,
                    params={
                        'page': page,
                        'per_page': PER_PAGE,
                        'expense_search[source_type_eq]': 'CardExpense'})
                for expense in expenses:
                    if expense.get('source') and expense['source'].get('transaction_link'):
                        transaction_link = expense['source']['transaction_link']
                        if transaction_link in expense_needed:
                            line = expense_needed.pop(transaction_link)
                            amount = float(expense['amount'])
                            if float_compare(amount, line['amount_eur'], precision_digits=2):
                                raise UserError(_(
                                    "There is a difference between the amount "
                                    "of the statement line (%s) and the "
                                    "amount of the expense (%s). This "
                                    "should never happen.")
                                    % (line['amount_eur'], amount))
                            expense_categ_name = charge_account = False
                            if expense.get('expense_category_id'):
                                if expense['expense_category_id'] not in speeddict['api_exp_categ']:
                                    raise UserError(_(
                                        "The expense category UUID %s is unknown. "
                                        "This should never happen.")
                                        % expense['expense_category_id'])
                                expense_categ_name = speeddict['api_exp_categ'][expense['expense_category_id']]['name']
                                charge_account = speeddict['api_exp_categ'][expense['expense_category_id']]['code']
                            vat_eur = 0.0
                            vat_20_id = vat_10_id = vat_55_id = vat_21_id = 0.0
                            for vat_line in expense.get('vats', []):
                                if vat_line.get('country') == 'FRA':
                                    vat_amount = float(vat_line['amount'])
                                    vat_eur += vat_amount
                                    if vat_line.get('rate') == '20.0':
                                        vat_20_id += vat_amount
                                    elif vat_line.get('rate') == '10.0':
                                        vat_10_id += vat_amount
                                    elif vat_line.get('rate') == '5.5':
                                        vat_55_id += vat_amount
                                    elif vat_line.get('rate') == '2.1':
                                        vat_21_id += vat_amount
                            attachment = ''
                            if expense.get('receipt_id'):
                                res_receipts, session = self.mooncard_get(
                                    api_params,
                                    'receipts/%s' % expense['receipt_id'],
                                    session=session)
                                attachment = res_receipts.get('url')
                            attendees = False
                            if expense.get('attendees'):
                                attendees = u', '.join([x for x in expense['attendees']])
                            supplier = False
                            if expense.get('supplier_id'):
                                res_supplier, session = self.mooncard_get(
                                    api_params,
                                    'suppliers/%s' % expense['supplier_id'],
                                    session=session)
                                supplier = res_supplier.get('name')
                            line.update({
                                'title': expense.get('title'),
                                'country_code': expense.get('invoice_country'),
                                'expense_category_name': expense_categ_name,
                                'charge_account': charge_account,
                                'date_authorization': expense.get('at'),
                                'supplier': supplier,
                                'receipt_code': expense.get('receipt_code'),
                                'attachment': attachment,
                                'original_currency': expense.get('currency'),
                                'amount_currency': float(expense['amount_currency']),
                                'vat_eur': vat_eur,
                                'vat_20_id': vat_20_id,
                                'vat_10_id': vat_10_id,
                                'vat_55_id': vat_55_id,
                                'vat_21_id': vat_21_id,
                                'attendees': attendees,
                                })
                            if line.get('existing_transaction_id'):
                                transaction = mto.browse(line['existing_transaction_id'])
                                wvals = mto._prepare_transaction(
                                    line, speeddict, action='update')
                                transaction.write(wvals)
                                mt_ids.append(transaction.id)
                            else:
                                vals = mto._prepare_transaction(line, speeddict)
                                transaction = mto.create(vals)
                                mt_ids.append(transaction.id)

                if not expenses:
                    break
                if not expense_needed:
                    logger.debug(
                        'Stop queries on /expenses because '
                        'expense_needed is empty')
                    break
                page += 1
        return mt_ids

    def mooncard_api_mileage_import(self, api_params, session, speeddict):
        self.ensure_one()
        mmo = self.env['mooncard.mileage']
        mm_ids = []
        exiting_mileage = {}
        existings = mmo.search_read(
            [('company_id', '=', self.id)],
            ['state', 'unique_import_id'])
        for l in existings:
            exiting_mileage[l['unique_import_id']] = {
                'state': l['state'],
                'id': l['id'],
                }
        speeddict['api_users'] = {}
        page = 1
        while page < MAX_PAGE:
            res_users, session = self.mooncard_get(
                api_params, 'user_profiles',
                params={'page': page, 'per_page': PER_PAGE}, session=session)
            for user in res_users:
                if user.get('email'):
                    speeddict['api_users'][user['id']] = user['email']
            if not res_users:
                break
            page += 1

        page = 1
        while page < MAX_PAGE:
            expenses, session = self.mooncard_get(
                api_params, 'expenses', session=session,
                params={
                    'page': page,
                    'per_page': PER_PAGE,
                    'expense_search[source_type_eq]': 'KmExpense'})
            done_count = 0
            for expense in expenses:
                if expense['id'] in exiting_mileage:
                    odoo_state = exiting_mileage[expense['id']]['state']
                    if odoo_state == 'done':
                        done_count += 1
                        continue
                    elif odoo_state == 'draft':
                        wvals = mmo._prepare_mileage(expense, speeddict)
                        mileage = mmo.browse(exiting_mileage[expense['id']]['id'])
                        mileage.write(wvals)
                        mm_ids.append(mileage.id)
                else:
                    vals = mmo._prepare_mileage(expense, speeddict)
                    mileage = mmo.create(vals)
                    mm_ids.append(mileage.id)
            if not expenses:
                break
            if done_count == len(expenses):
                logger.info(
                    'Reached one mileage page fully done in Odoo. '
                    'Stop queries.')
                break
            page += 1
        return mm_ids

    @api.model
    def convert_datetime_to_utc(self, date_time_str):
        # %z can only be used in strptime() starting from python 3.2
        # API : 2019-10-07T07:56:52.000Z
        # CSV : 2019-10-08 13:06:10 UTC ou-
        if date_time_str[10] == 'T':
            date_time_dt = dateutil.parser.isoparse(date_time_str)
        elif date_time_str[-2:].isdigit():
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
    def _cron_mooncard_api_import(self):
        logger.info('Start Mooncard API import via cron')
        companies = self.search([
            ('mooncard_api_login', '!=', False),
            ('mooncard_api_password', '!=', False),
            ('mooncard_api_company_uuid', '!=', False),
            ])
        for company in companies:
            logger.info('Import Mooncard in company %s', company.display_name)
            company.with_context(force_company=company.id).mooncard_api_import()
        logger.info('End of Mooncard API import via cron')
