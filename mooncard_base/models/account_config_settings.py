# -*- coding: utf-8 -*-
# Copyright 2020 Akretion France (http://www.akretion.com)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class AccountConfigSettings(models.TransientModel):
    _inherit = 'account.config.settings'

    mooncard_api_login = fields.Char(
        related='company_id.mooncard_api_login', readonly=False)
    mooncard_api_password = fields.Char(
        related='company_id.mooncard_api_password', readonly=False)
    mooncard_api_company_uuid = fields.Char(
        related='company_id.mooncard_api_company_uuid', readonly=False)
