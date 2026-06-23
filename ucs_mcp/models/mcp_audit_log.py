# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import json
import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class McpAuditLog(models.Model):
    _name = "mcp.audit.log"
    _description = "MCP Audit Log"
    _rec_name = "tool_name"
    _order = "create_date desc"
    _log_access = False

    api_key_id = fields.Many2one(
        "mcp.api.key",
        string="API Key",
        ondelete="set null",
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="User",
        ondelete="set null",
        index=True,
    )
    tool_name = fields.Char(string="Tool Name", required=True, index=True)
    model_name = fields.Char(string="Model Name")
    method = fields.Char(string="Method")
    request_data = fields.Text(string="Request Data")
    response_summary = fields.Text(string="Response Summary")
    status = fields.Selection(
        [("success", "Success"), ("error", "Error"), ("denied", "Access Denied")],
        string="Status",
        required=True,
        default="success",
        index=True,
    )
    error_message = fields.Text(string="Error Message")
    duration_ms = fields.Integer(string="Duration (ms)")
    ip_address = fields.Char(string="IP Address", readonly=True)
    create_date = fields.Datetime(string="Timestamp", readonly=True, index=True)

    @api.model
    def _cron_purge_old_logs(self):
        """Delete audit log entries older than ucs_mcp.audit_log_retention_days (default 90)."""
        retention_days = int(
            self.env["ir.config_parameter"].sudo().get_param(
                "ucs_mcp.audit_log_retention_days", 90
            )
        )
        if retention_days <= 0:
            _logger.info("MCP audit log retention disabled (retention_days=0). Skipping purge.")
            return
        cutoff = fields.Datetime.now() - timedelta(days=retention_days)
        old_logs = self.sudo().search([("create_date", "<", cutoff)])
        count = len(old_logs)
        old_logs.unlink()
        _logger.info("MCP audit log purged %d entries older than %d days.", count, retention_days)

    @classmethod
    def _log(cls, env, api_key, tool_name, status, **kwargs):
        """Create an audit log entry. Call with sudo() — never blocks the request."""
        try:
            vals = {
                "api_key_id": api_key.id if api_key else False,
                "user_id": api_key.user_id.id if api_key else False,
                "tool_name": tool_name,
                "status": status,
            }
            vals.update(kwargs)
            # sudo() needed: callers may not have create access to this model
            env["mcp.audit.log"].sudo().create(vals)
        except Exception:
            _logger.exception("Failed to write MCP audit log for tool=%s", tool_name)
