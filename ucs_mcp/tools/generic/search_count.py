# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

from odoo.exceptions import UserError

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import TOOL_PERM_READ

_logger = logging.getLogger(__name__)


@register
class SearchCountTool(BaseMcpTool):
    """Count records matching a domain."""

    name = "search_count"
    description = "Count how many records in a model match a given domain filter."
    required_permission = TOOL_PERM_READ
    input_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "Odoo model technical name"},
            "domain": {"type": "array", "description": "Odoo domain filter list. Default [].", "default": []},
        },
        "required": ["model"],
    }

    def execute(self, params: dict) -> dict:
        """Execute search_count."""
        self._require(params, "model")
        model_name = params["model"]
        domain = params.get("domain") or []
        if not isinstance(domain, list):
            raise UserError("Parameter 'domain' must be a list.")
        count = self.env[model_name].search_count(domain)
        return self._serialize({"model": model_name, "count": count})
