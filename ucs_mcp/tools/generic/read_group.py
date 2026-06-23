# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

from odoo.exceptions import UserError

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import TOOL_PERM_READ

_logger = logging.getLogger(__name__)


@register
class ReadGroupTool(BaseMcpTool):
    """Aggregate records — SUM, COUNT, AVG grouped by one or more fields."""

    name = "read_group"
    description = (
        "Group and aggregate Odoo records. Equivalent to SQL GROUP BY with aggregate functions. "
        "Use for totals, counts, averages. E.g. total invoiced per customer, order count by state."
    )
    required_permission = TOOL_PERM_READ
    input_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "Odoo model technical name"},
            "domain": {
                "type": "array",
                "description": "Domain filter (list of tuples). Use [] for all records.",
                "default": [],
            },
            "groupby": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Field names to group by (e.g. ['partner_id', 'state'])",
            },
            "aggregates": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Aggregate expressions, e.g. "
                    "['amount_total:sum', 'id:count', 'price_unit:avg']. "
                    "Use field:sum, field:count, field:avg, field:min, field:max."
                ),
                "default": [],
            },
            "limit": {"type": "integer", "description": "Max groups to return. Default 80.", "default": 80},
            "orderby": {"type": "string", "description": "Order string e.g. 'amount_total desc'"},
        },
        "required": ["model", "groupby"],
    }

    def execute(self, params: dict) -> dict:
        self._require(params, "model", "groupby")
        model_name = params["model"]
        domain = params.get("domain", [])
        groupby = params["groupby"]
        # Accept both "aggregates" (new) and "fields" (backward compat alias)
        aggregates = params.get("aggregates") or params.get("fields") or []
        limit = params.get("limit", 80)
        orderby = params.get("orderby") or None

        if not isinstance(groupby, list) or not groupby:
            raise UserError("'groupby' must be a non-empty list of field names.")
        if not isinstance(domain, list):
            raise UserError("'domain' must be a list.")

        # _read_group returns list[tuple]: (groupby_values..., aggregate_values...)
        raw_rows = self.env[model_name]._read_group(
            domain,
            groupby=groupby,
            aggregates=aggregates,
            limit=limit,
            order=orderby,
        )

        # Convert tuples to dicts using groupby + aggregates as keys
        all_specs = list(groupby) + list(aggregates)
        rows = []
        for tup in raw_rows:
            row = {}
            for i, spec in enumerate(all_specs):
                val = tup[i] if i < len(tup) else None
                # Recordsets come back for Many2one groupby — serialise as [id, display_name]
                if hasattr(val, "_name"):
                    val = [val.id, val.display_name] if val else False
                row[spec] = val
            rows.append(row)

        _logger.info("MCP read_group: model=%s groupby=%s rows=%d", model_name, groupby, len(rows))
        return self._serialize({"rows": rows, "count": len(rows)})
