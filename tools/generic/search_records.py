# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

from odoo.exceptions import UserError

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import DEFAULT_SEARCH_LIMIT, MAX_SEARCH_LIMIT, TOOL_PERM_READ

_logger = logging.getLogger(__name__)


@register
class SearchRecordsTool(BaseMcpTool):
    """Search records in any Odoo model."""

    name = "search_records"
    description = "Search records in any Odoo model using a domain filter. Returns matching records with requested fields."
    required_permission = TOOL_PERM_READ
    input_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "Odoo model technical name (e.g. 'sale.order')"},
            "domain": {"type": "array", "description": "Odoo domain filter list. Default [].", "default": []},
            "fields": {"type": "array", "items": {"type": "string"}, "description": "Field names to return. Default: name + id."},
            "limit": {"type": "integer", "description": "Max records to return. Default 80, max 500.", "default": 80},
            "offset": {"type": "integer", "description": "Skip N records for pagination.", "default": 0},
            "order": {"type": "string", "description": "Sort order, e.g. 'name asc'"},
        },
        "required": ["model"],
    }

    def execute(self, params: dict) -> dict:
        """Execute search_records."""
        self._require(params, "model")
        model_name = params["model"]
        domain = params.get("domain") or []
        requested_fields = params.get("fields") or ["id", "name"]
        limit = min(int(params.get("limit") or DEFAULT_SEARCH_LIMIT), MAX_SEARCH_LIMIT)
        offset = int(params.get("offset") or 0)
        order = params.get("order")

        if not isinstance(domain, list):
            raise UserError("Parameter 'domain' must be a list.")

        Model = self.env[model_name]
        search_kwargs = {"limit": limit, "offset": offset}
        if order:
            search_kwargs["order"] = order

        records = Model.search(domain, **search_kwargs)

        # Only request fields that exist on the model
        model_fields = Model.fields_get(attributes=["type"])
        valid_fields = [f for f in requested_fields if f in model_fields or f == "id"]
        if not valid_fields:
            valid_fields = ["id", "name"] if "name" in model_fields else ["id"]

        rows = records.read(valid_fields)
        return self._serialize({"count": len(rows), "records": rows})
