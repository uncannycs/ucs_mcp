# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

from odoo.exceptions import UserError

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import TOOL_PERM_WRITE

_logger = logging.getLogger(__name__)


@register
class ConfirmSaleOrderTool(BaseMcpTool):
    """Confirm a draft sale order."""

    name = "confirm_sale_order"
    description = "Confirm a draft sale order (action_confirm). Moves it from draft to sale state."
    required_permission = TOOL_PERM_WRITE
    input_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "default": "sale.order"},
            "id": {"type": "integer", "description": "Sale order ID to confirm"},
        },
        "required": ["id"],
    }

    def execute(self, params: dict) -> dict:
        """Execute confirm_sale_order."""
        self._require(params, "id")
        order_id = self._require_int(params, "id")
        order = self.env["sale.order"].browse(order_id)
        if not order.exists():
            raise UserError("Sale order %d not found." % order_id)
        if order.state != "draft":
            raise UserError("Sale order %d is not in draft state (current: %s)." % (order_id, order.state))
        order.action_confirm()
        _logger.info("MCP confirm_sale_order: id=%d", order_id)
        return self._serialize({"id": order_id, "name": order.name, "state": order.state})
