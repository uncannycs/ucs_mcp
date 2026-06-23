# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

from odoo.exceptions import UserError

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import TOOL_PERM_READ

_logger = logging.getLogger(__name__)

_REQUIRED_KEYS = {"company", "user", "date", "currency"}


@register
class SmartContextTool(BaseMcpTool):
    """Return key business context to help Claude give relevant answers."""

    name = "smart_context"
    description = "Return current business context: company info, active user, today's date, currency, recent activity summary. Use this as the first call to orient Claude."
    required_permission = TOOL_PERM_READ
    input_schema = {
        "type": "object",
        "properties": {
            "include": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional subset of context keys to return: company, user, date, currency, sales, invoices, stock.",
            }
        },
    }

    def execute(self, params: dict) -> dict:
        """Execute smart_context. Always returns company/user/date/currency keys."""
        include = params.get("include") or []
        env = self.env

        company = env.company
        user = env.user

        ctx = {
            "company": {
                "id": company.id,
                "name": company.name,
                "currency": company.currency_id.name,
                "country": company.country_id.name if company.country_id else None,
            },
            "user": {
                "id": user.id,
                "name": user.name,
                "login": user.login,
                "lang": user.lang,
                "tz": user.tz,
            },
            "date": str(fields_today()),
            "currency": company.currency_id.name,
        }

        if not include or "sales" in include:
            try:
                draft_so = env["sale.order"].search_count([("state", "=", "draft")])
                confirmed_so = env["sale.order"].search_count([("state", "=", "sale")])
                ctx["sales"] = {"draft": draft_so, "confirmed": confirmed_so}
            except Exception:
                ctx["sales"] = {"error": "sale module not installed"}

        if not include or "invoices" in include:
            try:
                unpaid = env["account.move"].search_count([
                    ("move_type", "=", "out_invoice"),
                    ("payment_state", "!=", "paid"),
                    ("state", "=", "posted"),
                ])
                ctx["invoices"] = {"unpaid_customer_invoices": unpaid}
            except Exception:
                ctx["invoices"] = {"error": "account module not installed"}

        if not include or "stock" in include:
            try:
                low_stock = env["stock.quant"].search_count([
                    ("location_id.usage", "=", "internal"),
                    ("quantity", "<", 1),
                ])
                ctx["stock"] = {"zero_stock_locations": low_stock}
            except Exception:
                ctx["stock"] = {"error": "stock module not installed"}

        missing = _REQUIRED_KEYS - set(ctx.keys())
        if missing:
            raise UserError("smart_context missing required keys: %s" % missing)

        return self._serialize(ctx)


def fields_today():
    """Return today's date using Odoo-safe method."""
    from odoo import fields
    return fields.Date.today()
