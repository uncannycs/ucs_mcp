# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

from odoo.exceptions import UserError

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import TOOL_PERM_READ

_logger = logging.getLogger(__name__)


@register
class GetCustomerStatementTool(BaseMcpTool):
    """Get a customer's account statement summary."""

    name = "get_customer_statement"
    description = "Return a customer's outstanding invoices, total due, and credit balance."
    required_permission = TOOL_PERM_READ
    input_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "default": "res.partner"},
            "partner_id": {"type": "integer", "description": "Customer partner ID"},
        },
        "required": ["partner_id"],
    }

    def execute(self, params: dict) -> dict:
        """Execute get_customer_statement."""
        self._require(params, "partner_id")
        partner_id = self._require_int(params, "partner_id")
        partner = self.env["res.partner"].browse(partner_id)
        if not partner.exists():
            raise UserError("Partner %d not found." % partner_id)

        invoices = self.env["account.move"].search([
            ("partner_id", "=", partner_id),
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("state", "=", "posted"),
        ])
        unpaid = invoices.filtered(lambda i: i.payment_state not in ("paid", "reversed"))
        total_due = sum(unpaid.mapped("amount_residual"))
        currency = self.env.company.currency_id.name

        statement = {
            "partner_id": partner_id,
            "partner_name": partner.name,
            "currency": currency,
            "total_due": total_due,
            "unpaid_invoices": [
                {
                    "id": inv.id,
                    "name": inv.name,
                    "date": str(inv.invoice_date),
                    "due_date": str(inv.invoice_date_due),
                    "amount_total": inv.amount_total,
                    "amount_residual": inv.amount_residual,
                    "payment_state": inv.payment_state,
                }
                for inv in unpaid
            ],
        }
        return self._serialize(statement)
