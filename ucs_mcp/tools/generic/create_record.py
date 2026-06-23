# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

from odoo.exceptions import UserError

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import TOOL_PERM_CREATE

_logger = logging.getLogger(__name__)


@register
class CreateRecordTool(BaseMcpTool):
    """Create a new record in any model."""

    name = "create_record"
    description = "Create a new record in any Odoo model. Returns the new record's ID."
    required_permission = TOOL_PERM_CREATE
    input_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "Odoo model technical name"},
            "values": {"type": "object", "description": "Field values for the new record"},
        },
        "required": ["model", "values"],
    }

    def execute(self, params: dict) -> dict:
        """Execute create_record."""
        self._require(params, "model", "values")
        model_name = params["model"]
        values = params["values"]
        if not isinstance(values, dict):
            raise UserError("Parameter 'values' must be an object.")
        record = self.env[model_name].create(values)
        _logger.info("MCP create_record: model=%s id=%d", model_name, record.id)
        self._post_chatter(
            model_name, record.id,
            "&#129302; <b>AI Assistant</b> created this record via MCP key <i>%s</i>." % self.api_key.name,
        )
        return self._serialize({"id": record.id, "model": model_name})
