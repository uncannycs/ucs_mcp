# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import json
import logging
import time
from abc import ABC, abstractmethod

from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)


class BaseMcpTool(ABC):
    """Abstract base for all MCP tools."""

    name: str = ""
    description: str = ""
    required_permission: str = "read"
    input_schema: dict = {}

    def __init__(self, env, api_key):
        self.env = env
        self.api_key = api_key

    @abstractmethod
    def execute(self, params: dict) -> dict:
        """Execute the tool with validated params. Return JSON-serialisable dict."""

    def run(self, params: dict) -> dict:
        """Validate access, execute, log, and return result."""
        from ..models.mcp_audit_log import McpAuditLog

        start = time.monotonic()
        model_name = params.get("model")
        status = "success"
        error_msg = None
        result = None

        try:
            self.api_key.check_permission(self.required_permission)
            if model_name:
                self.api_key.check_model_access(model_name)
            result = self.execute(params)
        except (AccessError, UserError, ValidationError) as exc:
            status = "denied" if isinstance(exc, AccessError) else "error"
            error_msg = str(exc)
            result = self._format_error(error_msg)
            if status == "error":
                _logger.warning("MCP tool %s error: %s", self.name, error_msg)
        except Exception as exc:
            status = "error"
            error_msg = str(exc)
            result = self._format_error("Internal error — see server log.")
            _logger.exception("MCP tool %s unhandled exception", self.name)

        duration_ms = int((time.monotonic() - start) * 1000)
        ip_address = None
        try:
            from odoo.http import request as _req
            ip_address = _req.httprequest.remote_addr
        except Exception:
            pass
        McpAuditLog._log(
            self.env,
            self.api_key,
            tool_name=self.name,
            status=status,
            model_name=model_name,
            request_data=json.dumps(params, default=str, ensure_ascii=False)[:4096],
            response_summary=json.dumps(result, default=str, ensure_ascii=False)[:2048],
            error_message=error_msg,
            duration_ms=duration_ms,
            ip_address=ip_address,
        )
        return result

    def _post_chatter(self, model_name: str, record_id: int, body: str):
        """Post a chatter note on the record if it supports mail.thread. Never raises."""
        try:
            record = self.env[model_name].sudo().browse(record_id)
            if record.exists() and hasattr(record, "message_post"):
                record.message_post(
                    body=body,
                    message_type="comment",
                    subtype_xmlid="mail.mt_note",
                )
        except Exception:
            _logger.debug("MCP chatter note failed for %s #%d", model_name, record_id)

    @staticmethod
    def _format_error(message: str) -> dict:
        """Wrap an error message in the standard error envelope."""
        return {"success": False, "error": message}

    @staticmethod
    def _require(params: dict, *keys):
        """Raise UserError if any required key is missing from params."""
        missing = [k for k in keys if k not in params or params[k] is None]
        if missing:
            raise UserError("Missing required parameter(s): %s" % ", ".join(missing))

    @staticmethod
    def _require_int(params: dict, key: str):
        """Raise UserError if params[key] is not an integer."""
        val = params.get(key)
        if not isinstance(val, int):
            raise UserError("Parameter '%s' must be an integer, got %r." % (key, val))
        return val

    @staticmethod
    def _serialize(data) -> dict:
        """Wrap data in success envelope, JSON-safe via default=str."""
        return {"success": True, "data": json.loads(json.dumps(data, default=str, ensure_ascii=False))}
