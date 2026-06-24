# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

from odoo.exceptions import UserError

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import TOOL_PERM_CREATE

_logger = logging.getLogger(__name__)


@register
class CreateLeaveRequestTool(BaseMcpTool):
    """Create an employee leave request."""

    name = "create_leave_request"
    description = "Create a leave (time-off) request for an employee. Returns the allocation ID."
    required_permission = TOOL_PERM_CREATE
    input_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "default": "hr.leave"},
            "employee_id": {"type": "integer", "description": "Employee ID"},
            "holiday_status_id": {"type": "integer", "description": "Leave type ID"},
            "date_from": {"type": "string", "description": "Start date YYYY-MM-DD"},
            "date_to": {"type": "string", "description": "End date YYYY-MM-DD"},
            "name": {"type": "string", "description": "Reason / description"},
        },
        "required": ["employee_id", "holiday_status_id", "date_from", "date_to"],
    }

    def execute(self, params: dict) -> dict:
        """Execute create_leave_request."""
        self._require(params, "employee_id", "holiday_status_id", "date_from", "date_to")
        from odoo import fields

        vals = {
            "employee_id": self._require_int(params, "employee_id"),
            "holiday_status_id": self._require_int(params, "holiday_status_id"),
            "date_from": fields.Date.to_date(params["date_from"]),
            "date_to": fields.Date.to_date(params["date_to"]),
        }
        if params.get("name"):
            vals["name"] = params["name"]

        leave = self.env["hr.leave"].create(vals)
        _logger.info("MCP create_leave_request: id=%d employee=%d", leave.id, vals["employee_id"])
        self._post_chatter(
            "hr.leave", leave.id,
            "&#129302; <b>AI Assistant</b> submitted this leave request via MCP key <i>%s</i>." % self.api_key.name,
        )
        return self._serialize({"id": leave.id, "state": leave.state})
