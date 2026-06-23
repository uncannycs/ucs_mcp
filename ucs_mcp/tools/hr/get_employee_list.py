# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import TOOL_PERM_READ

_logger = logging.getLogger(__name__)


@register
class GetEmployeeListTool(BaseMcpTool):
    """List employees with basic info."""

    name = "get_employee_list"
    description = "Return active employees with their department, job position, and manager."
    required_permission = TOOL_PERM_READ
    input_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "default": "hr.employee"},
            "department_id": {"type": "integer", "description": "Filter by department ID (optional)"},
            "active": {"type": "boolean", "description": "Include only active employees. Default true.", "default": True},
        },
    }

    def execute(self, params: dict) -> dict:
        """Execute get_employee_list."""
        domain = [("active", "=", params.get("active", True))]
        if params.get("department_id"):
            domain.append(("department_id", "=", int(params["department_id"])))

        employees = self.env["hr.employee"].search(domain)
        rows = employees.read(["id", "name", "job_id", "department_id", "parent_id", "work_email"])
        return self._serialize({"count": len(rows), "employees": rows})
