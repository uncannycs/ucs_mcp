# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import TOOL_PERM_READ

_logger = logging.getLogger(__name__)


@register
class GetFieldsTool(BaseMcpTool):
    """Get field definitions for an Odoo model."""

    name = "get_fields"
    description = "Return field definitions (type, string, required, relation) for any Odoo model."
    required_permission = TOOL_PERM_READ
    input_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "Odoo model technical name"},
            "attributes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Field attributes to include. Default: type, string, required, relation.",
                "default": ["type", "string", "required", "relation"],
            },
        },
        "required": ["model"],
    }

    def execute(self, params: dict) -> dict:
        """Execute get_fields."""
        self._require(params, "model")
        model_name = params["model"]
        attributes = params.get("attributes") or ["type", "string", "required", "relation"]
        fields_info = self.env[model_name].fields_get(attributes=attributes)
        return self._serialize({"model": model_name, "fields": fields_info})
