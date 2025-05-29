# Copyright 2016-2021 Akretion France (http://www.akretion.com/)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import _, api, exceptions, models
from odoo.exceptions import UserError
from odoo.tools import float_compare


logger = logging.getLogger(__name__)

VAT_DETAIL = [
    ("vat_20_id", "20_ht", "20_ttc", "charge_account_20_id", 20.0),
    ("vat_10_id", "10_ht", "10_ttc", "charge_account_10_id", 10.0),
    ("vat_55_id", "55_ht", "55_ttc", "charge_account_55_id", 5.5),
    ("vat_21_id", "21_ht", "21_ttc", "charge_account_21_id", 2.1),
    ("exempt_id", "exempt_ht", "exempt_ttc", "exempt_account", 0.0),
]


class MooncardCsvImport(models.TransientModel):
    _inherit = "mooncard.csv.import"

    def _prepare_transaction(self, line, speeddict, action="create"):
        vals = super()._prepare_transaction(line, speeddict, action=action)
        new_float_fields = [
            "20_ht",
            "20_ttc",
            "10_ht",
            "10_ttc",
            "55_ht",
            "55_ttc",
            "21_ht",
            "21_ttc",
            "exempt_ht",
            "exempt_ttc",
            "exempt_id",
        ]
        for float_field in new_float_fields:
            if line.get(float_field):
                try:
                    line[float_field] = float(line[float_field])
                except Exception:
                    raise UserError(
                        _("Cannot convert float field '%s' with value '%s'.")
                        % (float_field, line.get(float_field))
                    )
            else:
                line[float_field] = 0.0
        vals["vat_line_ids"] = []
        total_ttc = 0.0
        total_vat = 0.0
        for vat_col, ht_col, ttc_col, expense_col, rate in VAT_DETAIL:
            if line[ht_col]:
                if not line.get(expense_col):
                    raise exceptions.ValidationError(
                        _("Problem in the file, not expense account for line %(line_id)s - %(title)s", line_id=line["id"], title=line["title"])
                    )
                expense_account_id = self.env["newgen.payment.card"]._match_account(line.get(expense_col), speeddict['accounts'])
                if not expense_account_id:
                    raise exceptions.ValidationError(
                        _("No account found in Odoo fo code %(code)s", code=line[expense_col])
                    )
                vals["vat_line_ids"].append(
                    (
                        0,
                        0,
                        {
                            "vat_rate": rate,
                            "vat_company_currency": line[vat_col],
                            "subtotal_company_currency": line[ht_col],
                            "total_company_currency": line[ttc_col],
                            "expense_account_id": expense_account_id,
                        },
                    )
                )
                total_ttc += line[ttc_col]
                total_vat += line[vat_col]
        precision = self.env.company.currency_id.rounding
        # check consistency between detailed and global amounts
        if float_compare(
            total_ttc,
            line["amount_eur"],
            precision_rounding=precision,
        ):
            raise UserError(
                _("Problem in the file, the line %(line_id)s - %(title)s is not  consistent about the "
                  "amounts with taxes.", line_id=line["id"], title=line["title"])
            )
        if float_compare(
            total_vat,
            line["vat_eur"],
            precision_rounding=precision,
        ):
            raise UserError(
                _("Problem in the file, the line %(title)s is not  consistent about the "
                  "tax amounts.", title=line["title"] )
            )
        # Force account in transaction in case there is only 1 vat line because
        # I am not sure this main account will be consistent with this multiple
        # expense account file...
        if len(vals["vat_line_ids"]) == 1:
            expense_account_id = vals["vat_line_ids"][0][2]["expense_account_id"]
            vals["expense_account_id"] = expense_account_id

#        # Add a line for 0.0 if we have both taxed and untaxed expenses
#        # Not  sure it is a possible case though
#        if total_ttc and abs(total_ttc) < abs(line["amount_eur"]):
#            diff = line["amount_eur"] - total_ttc
#            vals["vat_line_ids"].append(
#                (
#                    0,
#                    0,
#                    {
#                        "vat_rate": 0.0,
#                        "vat_company_currency": 0.0,
#                        "subtotal_company_currency": diff,
#                        "total_company_currency": diff,
#                        "expense_account_id": self._get_account(
#                            line["charge_account"], speeddict
#                        ).id,
#                    },
#                )
#            )
#        # ensure global expense_account_id is consistent with the one in vat line if
#        # only one because in that case the native processing will hapen, using the
#        # global expense account
#        if len(vals["vat_line_ids"]) == 1:
#            vat_expense_id = vals["vat_line_ids"][0][2]["expense_account_id"]
#            if vat_expense_id and vat_expense_id != vals.get("expense_account_id"):
#                vals["expense_account_id"] = vat_expense_id

        if action == "update":
            # delete existing vat line first
            transaction = self.env["newgen.payment.card.transaction"].search([("unique_import_id", "=", line['id'])])
            if len(transaction) != 1:
                raise exceptions.ValidatonError(_("Problem with the file updating %(line_id)s", line_id=line["id"]))
            for vat_line in transaction.vat_line_ids:
                vals["vat_line_ids"].append((2, vat_line.id, 0))
        return vals
