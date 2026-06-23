# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

from odoo.exceptions import UserError

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import TOOL_PERM_READ

_logger = logging.getLogger(__name__)


@register
class GetStockLevelTool(BaseMcpTool):
    """Get stock level for a product."""

    name = "get_stock_level"
    description = "Return current on-hand, forecasted, and reserved stock for a product, optionally filtered by warehouse or location."
    required_permission = TOOL_PERM_READ
    input_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "default": "stock.quant"},
            "product_id": {"type": "integer", "description": "Product ID"},
            "location_id": {"type": "integer", "description": "Stock location ID (optional, defaults to all internal locations)"},
            "warehouse_id": {"type": "integer", "description": "Warehouse ID (optional)"},
        },
        "required": ["product_id"],
    }

    def execute(self, params: dict) -> dict:
        """Execute get_stock_level."""
        self._require(params, "product_id")
        product_id = self._require_int(params, "product_id")
        product = self.env["product.product"].browse(product_id)
        if not product.exists():
            raise UserError("Product %d not found." % product_id)

        domain = [
            ("product_id", "=", product_id),
            ("location_id.usage", "=", "internal"),
        ]
        if params.get("location_id"):
            domain.append(("location_id", "=", int(params["location_id"])))
        if params.get("warehouse_id"):
            wh = self.env["stock.warehouse"].browse(int(params["warehouse_id"]))
            if wh.exists():
                domain.append(("location_id", "child_of", wh.lot_stock_id.id))

        quants = self.env["stock.quant"].search(domain)
        qty_on_hand = sum(quants.mapped("quantity"))
        qty_reserved = sum(quants.mapped("reserved_quantity"))

        return self._serialize({
            "product_id": product_id,
            "product_name": product.display_name,
            "qty_on_hand": qty_on_hand,
            "qty_reserved": qty_reserved,
            "qty_available": qty_on_hand - qty_reserved,
        })
