# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

from odoo.exceptions import UserError

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import DANGEROUS_METHODS, TOOL_PERM_EXECUTE

_logger = logging.getLogger(__name__)


@register
class ExecuteMethodTool(BaseMcpTool):
    """Call an Odoo method on a model or record set."""

    name = "execute_method"
    description = "Call a specific method on an Odoo model. Blocked methods: unlink, write, create, sudo, execute, shell, eval, load."
    required_permission = TOOL_PERM_EXECUTE
    input_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "Odoo model technical name"},
            "method": {"type": "string", "description": "Method name to call"},
            "ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Record IDs to call method on. Empty list = model-level call.",
                "default": [],
            },
            "args": {"type": "array", "description": "Positional arguments for the method.", "default": []},
            "kwargs": {"type": "object", "description": "Keyword arguments for the method.", "default": {}},
        },
        "required": ["model", "method"],
    }

    def execute(self, params: dict) -> dict:
        """Execute execute_method. Blocks all methods in DANGEROUS_METHODS."""
        self._require(params, "model", "method")
        model_name = params["model"]
        method_name = params["method"]

        if method_name in DANGEROUS_METHODS:
            raise UserError(
                "Method '%s' is blocked. Use dedicated tools for write/create/delete operations." % method_name
            )
        if method_name.startswith("_"):
            raise UserError("Private methods (starting with '_') cannot be called via MCP.")

        args = params.get("args") or []
        kwargs = params.get("kwargs") or {}
        ids = params.get("ids") or []

        if not isinstance(args, list):
            raise UserError("Parameter 'args' must be a list.")
        if not isinstance(kwargs, dict):
            raise UserError("Parameter 'kwargs' must be an object.")

        Model = self.env[model_name]
        target = Model.browse(ids) if ids else Model

        method = getattr(target, method_name, None)
        if method is None:
            raise UserError("Method '%s' not found on model '%s'." % (method_name, model_name))

        result = method(*args, **kwargs)

        # Recordsets are not JSON-serialisable — convert to IDs
        if hasattr(result, "_ids"):
            result = {"ids": list(result._ids), "model": result._name}

        _logger.info("MCP execute_method: model=%s method=%s ids=%s", model_name, method_name, ids)
        return self._serialize({"result": result})
