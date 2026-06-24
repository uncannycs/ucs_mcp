# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

from odoo.exceptions import UserError

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import TOOL_PERM_CREATE

_logger = logging.getLogger(__name__)


@register
class CreateInvoiceTool(BaseMcpTool):
    """Create a customer invoice."""

    name = "create_invoice"
    description = "Create a customer invoice (account.move, move_type=out_invoice) with invoice lines."
    required_permission = TOOL_PERM_CREATE
    input_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "default": "account.move"},
            "partner_id": {"type": "integer", "description": "Customer partner ID"},
            "lines": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "quantity": {"type": "number"},
                        "price_unit": {"type": "number"},
                        "account_id": {"type": "integer"},
                        "tax_ids": {"type": "array", "items": {"type": "integer"}},
                    },
                    "required": ["name", "price_unit"],
                },
            },
            "invoice_date": {"type": "string", "description": "YYYY-MM-DD. Default today."},
            "ref": {"type": "string", "description": "Customer reference/PO number"},
        },
        "required": ["partner_id", "lines"],
    }

    def execute(self, params: dict) -> dict:
        """Execute create_invoice."""
        self._require(params, "partner_id", "lines")
        partner_id = self._require_int(params, "partner_id")
        lines = params["lines"]
        if not isinstance(lines, list) or not lines:
            raise UserError("Parameter 'lines' must be a non-empty list.")

        invoice_lines = []
        for line in lines:
            line_vals = {
                "name": line.get("name", "/"),
                "quantity": float(line.get("quantity", 1)),
                "price_unit": float(line["price_unit"]),
            }
            if line.get("account_id"):
                line_vals["account_id"] = int(line["account_id"])
            if line.get("tax_ids"):
                line_vals["tax_ids"] = [(6, 0, [int(t) for t in line["tax_ids"]])]
            invoice_lines.append((0, 0, line_vals))

        vals = {
            "move_type": "out_invoice",
            "partner_id": partner_id,
            "invoice_line_ids": invoice_lines,
        }
        if params.get("invoice_date"):
            from odoo import fields
            vals["invoice_date"] = fields.Date.to_date(params["invoice_date"])
        if params.get("ref"):
            vals["ref"] = params["ref"]

        invoice = self.env["account.move"].create(vals)
        _logger.info("MCP create_invoice: id=%d name=%s", invoice.id, invoice.name)
        self._post_chatter(
            "account.move", invoice.id,
            "&#129302; <b>AI Assistant</b> created this invoice via MCP key <i>%s</i>." % self.api_key.name,
        )
        return self._serialize({"id": invoice.id, "name": invoice.name, "state": invoice.state})
