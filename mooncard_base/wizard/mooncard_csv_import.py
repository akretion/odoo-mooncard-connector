# -*- coding: utf-8 -*-
# Copyright 2016-2020 Akretion
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models, fields, _
from odoo.exceptions import UserError
import unicodecsv
from tempfile import TemporaryFile
import logging
MEANINGFUL_PARTNER_NAME_MIN_SIZE = 3


logger = logging.getLogger(__name__)


class MooncardCsvImport(models.TransientModel):
    _name = 'mooncard.csv.import'
    _description = 'Import Mooncard Transactions'

    mooncard_file = fields.Binary(string='CSV File', required=False)
    filename = fields.Char(string='Filename')

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
            for key, value in line.iteritems():
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

    def mooncard_csv_import(self):
        self.ensure_one()
        mto = self.env['mooncard.transaction']
        if not self.mooncard_file:
            raise UserError(_(
                "You must upload the Mooncard CSV file."))
        company = self.env.user.company_id
        speeddict = company._prepare_speeddict()
        logger.info('Importing Mooncard CSV file.')
        fileobj = TemporaryFile('w+')
        fileobj.write(self.mooncard_file.decode('base64'))
        fileobj.seek(0)
        file_content = fileobj.read()
        if file_content.startswith('Identifiant unique;Collaborateur;Email'):
            return self.mooncard_import_mileage(fileobj)
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
            for key, value in line.iteritems():
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
                    wvals = mto._prepare_transaction(
                        line, speeddict, action='update')
                    transaction.write(wvals)
                    mt_ids.append(transaction.id)
            else:
                vals = mto._prepare_transaction(line, speeddict)
                transaction = mto.create(vals)
                mt_ids.append(transaction.id)
        fileobj.close()
        return self._prepare_action(mt_ids, raise_if_empty=True)

    def mooncard_api_import(self):
        self.ensure_one()
        company = self.env.user.company_id
        mt_ids = company.mooncard_api_import()
        return self._prepare_action(mt_ids)

    def _prepare_action(self, mt_ids, raise_if_empty=False):
        if not mt_ids and raise_if_empty:
            raise UserError(_("No Mooncard transaction created nor updated."))
        action = self.env['ir.actions.act_window'].for_xml_id(
            'mooncard_base', 'mooncard_transaction_action')
        action.update({
            'domain': "[('id', 'in', %s)]" % mt_ids,
            'views': False,
            'nodestroy': False,
            })
        return action
