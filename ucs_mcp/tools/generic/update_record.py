# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

from odoo.exceptions import UserError

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import TOOL_PERM_WRITE

_logger = logging.getLogger(__name__)


@register
class UpdateRecordTool(BaseMcpTool):
    """Update fields on an existing record."""

    name = "update_record"
    description = "Update one or more fields on an existing record identified by model and ID."
    required_permission = TOOL_PERM_WRITE
    input_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "Odoo model technical name"},
            "id": {"type": "integer", "description": "Record database ID"},
            "values": {"type": "object", "description": "Fields to update and their new values"},
        },
        "required": ["model", "id", "values"],
    }

    def execute(self, params: dict) -> dict:
        """Execute update_record."""
        self._require(params, "model", "id", "values")
        model_name = params["model"]
        record_id = self._require_int(params, "id")
        values = params["values"]
        if not isinstance(values, dict):
            raise UserError("Parameter 'values' must be an object.")

        record = self.env[model_name].browse(record_id)
        if not record.exists():
            raise UserError("Record %d not found in '%s'." % (record_id, model_name))

        record.write(values)
        _logger.info("MCP update_record: model=%s id=%d fields=%s", model_name, record_id, list(values.keys()))
        fields_str = ", ".join("<code>%s</code>" % f for f in values.keys())
        self._post_chatter(
            model_name, record_id,
            "&#129302; <b>AI Assistant</b> updated %s via MCP key <i>%s</i>." % (fields_str, self.api_key.name),
        )
        return self._serialize({"id": record_id, "updated_fields": list(values.keys())})
