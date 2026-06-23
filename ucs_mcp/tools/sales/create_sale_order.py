# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

from odoo.exceptions import UserError

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import TOOL_PERM_CREATE

_logger = logging.getLogger(__name__)


@register
class CreateSaleOrderTool(BaseMcpTool):
    """Create a sale order with order lines."""

    name = "create_sale_order"
    description = "Create a new sale order with order lines. Returns the new SO ID and name."
    required_permission = TOOL_PERM_CREATE
    input_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "default": "sale.order"},
            "partner_id": {"type": "integer", "description": "Customer (res.partner) ID"},
            "lines": {
                "type": "array",
                "description": "Order lines",
                "items": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "integer"},
                        "product_uom_qty": {"type": "number"},
                        "price_unit": {"type": "number"},
                    },
                    "required": ["product_id", "product_uom_qty"],
                },
            },
            "date_order": {"type": "string", "description": "Order date YYYY-MM-DD. Default today."},
            "note": {"type": "string"},
        },
        "required": ["partner_id", "lines"],
    }

    def execute(self, params: dict) -> dict:
        """Execute create_sale_order."""
        self._require(params, "partner_id", "lines")
        partner_id = self._require_int(params, "partner_id")
        lines = params["lines"]
        if not isinstance(lines, list) or not lines:
            raise UserError("Parameter 'lines' must be a non-empty list.")

        order_lines = []
        for line in lines:
            if not isinstance(line.get("product_id"), int):
                raise UserError("Each line must have an integer 'product_id'.")
            order_lines.append((0, 0, {
                "product_id": line["product_id"],
                "product_uom_qty": float(line.get("product_uom_qty", 1)),
                "price_unit": float(line["price_unit"]) if "price_unit" in line else 0.0,
            }))

        vals = {
            "partner_id": partner_id,
            "order_line": order_lines,
        }
        if params.get("date_order"):
            from odoo import fields
            vals["date_order"] = fields.Date.to_date(params["date_order"])
        if params.get("note"):
            vals["note"] = params["note"]

        order = self.env["sale.order"].create(vals)
        _logger.info("MCP create_sale_order: id=%d name=%s", order.id, order.name)
        return self._serialize({"id": order.id, "name": order.name, "state": order.state})
