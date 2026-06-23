# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

from odoo.exceptions import UserError

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import TOOL_PERM_READ

_logger = logging.getLogger(__name__)


@register
class GetRecordTool(BaseMcpTool):
    """Get a single record by ID."""

    name = "get_record"
    description = "Fetch a single record by its database ID and return specified fields."
    required_permission = TOOL_PERM_READ
    input_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "Odoo model technical name"},
            "id": {"type": "integer", "description": "Record database ID"},
            "fields": {"type": "array", "items": {"type": "string"}, "description": "Field names to return."},
        },
        "required": ["model", "id"],
    }

    def execute(self, params: dict) -> dict:
        """Execute get_record."""
        self._require(params, "model", "id")
        model_name = params["model"]
        record_id = self._require_int(params, "id")
        requested_fields = params.get("fields") or []

        Model = self.env[model_name]
        record = Model.browse(record_id)
        if not record.exists():
            raise UserError("Record %d not found in model '%s'." % (record_id, model_name))

        model_fields = Model.fields_get(attributes=["type"])
        if requested_fields:
            valid_fields = [f for f in requested_fields if f in model_fields or f == "id"]
        else:
            valid_fields = list(model_fields.keys())[:50]  # cap to avoid huge payloads

        row = record.read(valid_fields)[0] if valid_fields else {"id": record_id}
        return self._serialize({"record": row})
