# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

from odoo.exceptions import UserError

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import TOOL_PERM_WRITE

_logger = logging.getLogger(__name__)


@register
class PostInvoiceTool(BaseMcpTool):
    """Post (validate) a draft invoice."""

    name = "post_invoice"
    description = "Post (validate) a draft invoice or bill. Moves it from draft to posted state."
    required_permission = TOOL_PERM_WRITE
    input_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "default": "account.move"},
            "id": {"type": "integer", "description": "Invoice ID to post"},
        },
        "required": ["id"],
    }

    def execute(self, params: dict) -> dict:
        """Execute post_invoice."""
        self._require(params, "id")
        invoice_id = self._require_int(params, "id")
        invoice = self.env["account.move"].browse(invoice_id)
        if not invoice.exists():
            raise UserError("Invoice %d not found." % invoice_id)
        if invoice.state != "draft":
            raise UserError("Invoice %d is not in draft state (current: %s)." % (invoice_id, invoice.state))
        invoice.action_post()
        _logger.info("MCP post_invoice: id=%d", invoice_id)
        return self._serialize({"id": invoice_id, "name": invoice.name, "state": invoice.state, "amount_total": invoice.amount_total})
