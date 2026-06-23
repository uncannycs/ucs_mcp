# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

from odoo.exceptions import AccessError, UserError

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import TOOL_PERM_DELETE

_logger = logging.getLogger(__name__)


@register
class DeleteRecordTool(BaseMcpTool):
    """Delete or archive a record."""

    name = "delete_record"
    description = "Delete or archive a record. If the model has an 'active' field, the record is archived (soft delete) instead of permanently deleted."
    required_permission = TOOL_PERM_DELETE
    input_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "Odoo model technical name"},
            "id": {"type": "integer", "description": "Record database ID"},
            "force_delete": {"type": "boolean", "description": "If true, permanently delete even if 'active' field exists. Default false.", "default": False},
        },
        "required": ["model", "id"],
    }

    def execute(self, params: dict) -> dict:
        """Execute delete_record. Requires delete permission on the API key."""
        self._require(params, "model", "id")

        # Explicit delete permission check — belt-and-suspenders beyond BaseMcpTool.run()
        if not self.api_key.perm_delete:
            raise AccessError("API key does not have delete permission.")

        model_name = params["model"]
        record_id = self._require_int(params, "id")
        force_delete = bool(params.get("force_delete", False))

        Model = self.env[model_name]
        record = Model.browse(record_id)
        if not record.exists():
            raise UserError("Record %d not found in '%s'." % (record_id, model_name))

        model_fields = Model.fields_get(["active"], attributes=["type"])
        has_active = "active" in model_fields

        if has_active and not force_delete:
            self._post_chatter(
                model_name, record_id,
                "&#129302; <b>AI Assistant</b> archived this record via MCP key <i>%s</i>." % self.api_key.name,
            )
            record.write({"active": False})
            action = "archived"
        else:
            record.unlink()
            action = "deleted"

        _logger.info("MCP delete_record: model=%s id=%d action=%s", model_name, record_id, action)
        return self._serialize({"id": record_id, "action": action})
