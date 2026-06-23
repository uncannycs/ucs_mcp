# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

from odoo.exceptions import UserError

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import TOOL_PERM_CREATE

_logger = logging.getLogger(__name__)


@register
class CreateStockMoveTool(BaseMcpTool):
    """Create an internal stock transfer."""

    name = "create_stock_move"
    description = "Create an internal stock transfer (picking) to move product between two locations."
    required_permission = TOOL_PERM_CREATE
    input_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "default": "stock.picking"},
            "product_id": {"type": "integer", "description": "Product ID to move"},
            "qty": {"type": "number", "description": "Quantity to transfer"},
            "location_src_id": {"type": "integer", "description": "Source location ID"},
            "location_dest_id": {"type": "integer", "description": "Destination location ID"},
            "scheduled_date": {"type": "string", "description": "YYYY-MM-DD"},
        },
        "required": ["product_id", "qty", "location_src_id", "location_dest_id"],
    }

    def execute(self, params: dict) -> dict:
        """Execute create_stock_move."""
        self._require(params, "product_id", "qty", "location_src_id", "location_dest_id")
        product_id = self._require_int(params, "product_id")
        qty = float(params["qty"])
        if qty <= 0:
            raise UserError("Quantity must be positive.")
        src_id = self._require_int(params, "location_src_id")
        dest_id = self._require_int(params, "location_dest_id")

        # Find internal transfer picking type
        picking_type = self.env["stock.picking.type"].search([
            ("code", "=", "internal"),
            ("warehouse_id.company_id", "=", self.env.company.id),
        ], limit=1)
        if not picking_type:
            raise UserError("No internal transfer picking type found for company.")

        from odoo import fields
        vals = {
            "picking_type_id": picking_type.id,
            "location_id": src_id,
            "location_dest_id": dest_id,
            "move_ids": [(0, 0, {
                "name": self.env["product.product"].browse(product_id).display_name,
                "product_id": product_id,
                "product_uom_qty": qty,
                "product_uom": self.env["product.product"].browse(product_id).uom_id.id,
                "location_id": src_id,
                "location_dest_id": dest_id,
            })],
        }
        if params.get("scheduled_date"):
            vals["scheduled_date"] = fields.Date.to_date(params["scheduled_date"])

        picking = self.env["stock.picking"].create(vals)
        _logger.info("MCP create_stock_move: picking=%d product=%d qty=%s", picking.id, product_id, qty)
        return self._serialize({"id": picking.id, "name": picking.name, "state": picking.state})
