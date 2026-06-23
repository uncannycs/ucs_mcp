# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

from odoo.exceptions import UserError

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import TOOL_PERM_CREATE

_logger = logging.getLogger(__name__)


@register
class RegisterPaymentTool(BaseMcpTool):
    """Register payment against an invoice."""

    name = "register_payment"
    description = "Register and reconcile a payment against a posted invoice. Returns the payment ID."
    required_permission = TOOL_PERM_CREATE
    input_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "default": "account.move"},
            "invoice_id": {"type": "integer", "description": "Posted invoice ID"},
            "amount": {"type": "number", "description": "Payment amount. Default = full amount residual."},
            "payment_date": {"type": "string", "description": "YYYY-MM-DD. Default today."},
            "journal_id": {"type": "integer", "description": "Payment journal ID. Default = company's bank journal."},
        },
        "required": ["invoice_id"],
    }

    def execute(self, params: dict) -> dict:
        """Execute register_payment."""
        self._require(params, "invoice_id")
        invoice_id = self._require_int(params, "invoice_id")
        invoice = self.env["account.move"].browse(invoice_id)
        if not invoice.exists():
            raise UserError("Invoice %d not found." % invoice_id)
        if invoice.state != "posted":
            raise UserError("Invoice %d must be posted before registering payment (state: %s)." % (invoice_id, invoice.state))

        from odoo import fields

        ctx = {"active_ids": [invoice_id], "active_model": "account.move"}
        wizard = self.env["account.payment.register"].with_context(**ctx).create({})
        if params.get("amount"):
            wizard.amount = float(params["amount"])
        if params.get("payment_date"):
            wizard.payment_date = fields.Date.to_date(params["payment_date"])
        if params.get("journal_id"):
            wizard.journal_id = int(params["journal_id"])

        action = wizard.action_create_payments()
        payment_ids = action.get("domain", [["id", "in", []]])[0][2] if isinstance(action, dict) else []
        _logger.info("MCP register_payment: invoice=%d payment_ids=%s", invoice_id, payment_ids)
        return self._serialize({
            "invoice_id": invoice_id,
            "payment_ids": payment_ids,
            "payment_state": invoice.payment_state,
        })
