# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

from odoo.exceptions import UserError

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import TOOL_PERM_READ

_logger = logging.getLogger(__name__)


@register
class GetAccountBalanceTool(BaseMcpTool):
    """Get the current balance of an account."""

    name = "get_account_balance"
    description = "Return the current debit, credit, and net balance for a GL account."
    required_permission = TOOL_PERM_READ
    input_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "default": "account.account"},
            "account_id": {"type": "integer", "description": "Account ID"},
            "date_from": {"type": "string", "description": "Start date YYYY-MM-DD (optional)"},
            "date_to": {"type": "string", "description": "End date YYYY-MM-DD (optional)"},
        },
        "required": ["account_id"],
    }

    def execute(self, params: dict) -> dict:
        """Execute get_account_balance."""
        self._require(params, "account_id")
        account_id = self._require_int(params, "account_id")
        account = self.env["account.account"].browse(account_id)
        if not account.exists():
            raise UserError("Account %d not found." % account_id)

        domain = [
            ("account_id", "=", account_id),
            ("parent_state", "=", "posted"),
        ]
        from odoo import fields
        if params.get("date_from"):
            domain.append(("date", ">=", fields.Date.to_date(params["date_from"])))
        if params.get("date_to"):
            domain.append(("date", "<=", fields.Date.to_date(params["date_to"])))

        lines = self.env["account.move.line"].search(domain)
        debit = sum(lines.mapped("debit"))
        credit = sum(lines.mapped("credit"))
        balance = debit - credit

        return self._serialize({
            "account_id": account_id,
            "account_code": account.code,
            "account_name": account.name,
            "currency": self.env.company.currency_id.name,
            "debit": debit,
            "credit": credit,
            "balance": balance,
        })
