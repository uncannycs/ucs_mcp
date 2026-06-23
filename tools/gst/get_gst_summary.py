# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

from odoo.exceptions import UserError

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import TOOL_PERM_READ

_logger = logging.getLogger(__name__)


@register
class GetGstSummaryTool(BaseMcpTool):
    """Get GST summary for a period. Requires l10n_in."""

    name = "get_gst_summary"
    description = "Return GST output tax, input tax credit, and net payable for a period. Requires l10n_in module."
    required_permission = TOOL_PERM_READ
    input_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "default": "account.move"},
            "date_from": {"type": "string", "description": "Period start YYYY-MM-DD"},
            "date_to": {"type": "string", "description": "Period end YYYY-MM-DD"},
        },
        "required": ["date_from", "date_to"],
    }

    def execute(self, params: dict) -> dict:
        """Execute get_gst_summary. Checks l10n_in is installed before proceeding."""
        l10n_in = self.env["ir.module.module"].sudo().search(
            [("name", "=", "l10n_in"), ("state", "=", "installed")], limit=1
        )
        if not l10n_in:
            raise UserError("Module l10n_in is not installed. GST tools require the India localisation.")

        self._require(params, "date_from", "date_to")
        from odoo import fields

        date_from = fields.Date.to_date(params["date_from"])
        date_to = fields.Date.to_date(params["date_to"])

        output_domain = [
            ("move_id.move_type", "in", ["out_invoice", "out_refund"]),
            ("move_id.state", "=", "posted"),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
            ("tax_line_id", "!=", False),
        ]
        input_domain = [
            ("move_id.move_type", "in", ["in_invoice", "in_refund"]),
            ("move_id.state", "=", "posted"),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
            ("tax_line_id", "!=", False),
        ]

        output_lines = self.env["account.move.line"].search(output_domain)
        input_lines = self.env["account.move.line"].search(input_domain)
        output_gst = sum(output_lines.mapped("balance"))
        input_itc = sum(input_lines.mapped("balance"))
        net_payable = abs(output_gst) - abs(input_itc)

        return self._serialize({
            "date_from": str(date_from),
            "date_to": str(date_to),
            "output_gst": abs(output_gst),
            "input_itc": abs(input_itc),
            "net_payable": max(net_payable, 0),
            "currency": self.env.company.currency_id.name,
        })
