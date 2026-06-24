# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import hashlib
import logging
import secrets

from odoo import _, api, fields, models
from odoo.addons.base.models.res_users import check_identity
from odoo.exceptions import AccessError, UserError

from ..const import (
    DEFAULT_SEARCH_LIMIT,
    SYSTEM_BLOCKED_MODELS,
    TOOL_PERM_CREATE,
    TOOL_PERM_DELETE,
    TOOL_PERM_EXECUTE,
    TOOL_PERM_READ,
    TOOL_PERM_WRITE,
)

_logger = logging.getLogger(__name__)

_PLAIN_KEY_PREFIX = "ucs_mcp_"
_KEY_BYTES = 32


class McpApiKey(models.Model):
    _name = "mcp.api.key"
    _description = "MCP API Key"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _check_company_auto = True
    _order = "create_date desc"

    name = fields.Char(string="Key Name", required=True, tracking=True)
    key_hash = fields.Char(
        string="Key Hash",
        required=True,
        readonly=True,
        copy=False,
        index=True,
    )
    key_prefix = fields.Char(
        string="Key Prefix",
        readonly=True,
        copy=False,
        help="First 8 chars of plain key for identification",
    )
    user_id = fields.Many2one(
        "res.users",
        string="Owner",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    expiry_date = fields.Date(string="Expiry Date", tracking=True)
    active = fields.Boolean(string="Active", default=True, tracking=True)
    rate_limit = fields.Integer(
        string="Rate Limit (requests/hour)",
        default=100,
        tracking=True,
        help="Max requests per hour. 0 = unlimited.",
    )
    request_count = fields.Integer(
        string="Requests This Hour",
        default=0,
        readonly=True,
    )
    rate_window_start = fields.Datetime(
        string="Rate Window Start",
        readonly=True,
    )

    # Permissions
    perm_read = fields.Boolean(string="Read Permission", default=True)
    perm_write = fields.Boolean(string="Write Permission", default=False, tracking=True)
    perm_create = fields.Boolean(string="Create Permission", default=False, tracking=True)
    perm_delete = fields.Boolean(string="Delete Permission", default=False, tracking=True)
    perm_execute = fields.Boolean(string="Execute Permission", default=False, tracking=True)

    # Model access control
    allowed_models = fields.Text(
        string="Allowed Models",
        help="Comma-separated model names. Empty = all allowed (subject to blocked list).",
    )
    custom_blocked_models = fields.Text(
        string="Custom Blocked Models",
        help="Comma-separated model names to block in addition to system defaults.",
    )

    last_used = fields.Datetime(string="Last Used", readonly=True)
    use_count = fields.Integer(string="Total Uses", default=0, readonly=True)

    # Shown once after key creation from backend form, cleared by user action
    plain_key_once = fields.Char(
        string="API Key — copy now, shown once",
        readonly=True,
        copy=False,
        help="Plain key generated on save. Click 'I've saved the key' to clear it.",
    )

    _key_hash_unique = models.Constraint("UNIQUE(key_hash)", "API key hash must be unique.")

    def _compute_hash(self, plain_key):
        """Return SHA-256 hex digest of a plain key."""
        return hashlib.sha256(plain_key.encode()).hexdigest()

    @api.model_create_multi
    def create(self, vals_list):
        # Auto-generate key_hash when creating from the backend form (no hash provided)
        for vals in vals_list:
            if not vals.get("key_hash"):
                plain_key = _PLAIN_KEY_PREFIX + secrets.token_urlsafe(_KEY_BYTES)
                vals["key_hash"] = self._compute_hash(plain_key)
                vals["key_prefix"] = plain_key[:12]
                vals["plain_key_once"] = plain_key
        return super().create(vals_list)

    def action_clear_plain_key(self):
        """User confirms they've saved the key — clear plain_key_once from DB."""
        self.ensure_one()
        # sudo() needed: user may not have write permission on this field directly
        self.sudo().write({"plain_key_once": False})

    @api.model
    def generate_key(self, name, user_id=None, **kwargs):
        """Create a new API key. Returns (record, plain_key) — plain_key shown once."""
        plain_key = _PLAIN_KEY_PREFIX + secrets.token_urlsafe(_KEY_BYTES)
        key_hash = self._compute_hash(plain_key)
        vals = {
            "name": name,
            "key_hash": key_hash,
            "key_prefix": plain_key[:12],
            "user_id": user_id or self.env.uid,
        }
        vals.update(kwargs)
        record = self.create(vals)
        _logger.info("MCP API key created: id=%d name=%s user=%d", record.id, name, record.user_id.id)
        return record, plain_key

    @api.model
    def authenticate(self, plain_key):
        """Authenticate a plain key. Returns the key record or raises AccessError."""
        key_hash = self._compute_hash(plain_key)
        # sudo() needed: record rules restrict to owner, but auth must work for any caller
        record = self.sudo().search([("key_hash", "=", key_hash)], limit=1)
        if not record:
            raise AccessError(_("Invalid API key."))
        if not record.active:
            raise AccessError(_("API key is inactive."))
        if record.expiry_date and record.expiry_date < fields.Date.today():
            raise AccessError(_("API key has expired."))
        record._check_rate_limit()
        record._record_usage()
        return record

    def _check_rate_limit(self):
        """Raise UserError if key is over its rate limit."""
        self.ensure_one()
        if not self.rate_limit:
            return
        now = fields.Datetime.now()
        window_start = self.rate_window_start
        if not window_start or (now - window_start).total_seconds() >= 3600:
            # sudo() needed: resetting rate counters requires write on the key record
            self.sudo().write({"request_count": 0, "rate_window_start": now})
            return
        if self.request_count >= self.rate_limit:
            raise UserError(
                _("Rate limit exceeded. Max %d requests/hour.") % self.rate_limit
            )

    def _record_usage(self):
        """Increment usage counters."""
        self.ensure_one()
        # sudo() needed: caller may not have write access to this key record
        self.sudo().write({
            "request_count": self.request_count + 1,
            "last_used": fields.Datetime.now(),
            "use_count": self.use_count + 1,
        })

    def check_model_access(self, model_name):
        """Raise AccessError if this key is not allowed to access model_name."""
        self.ensure_one()
        if model_name in SYSTEM_BLOCKED_MODELS:
            raise AccessError(
                _("Access to model '%s' is blocked by system policy.") % model_name
            )
        custom_blocked = self._get_custom_blocked()
        if model_name in custom_blocked:
            raise AccessError(
                _("Access to model '%s' is blocked for this key.") % model_name
            )
        allowed = self._get_allowed_models()
        if allowed and model_name not in allowed:
            raise AccessError(
                _("Model '%s' is not in the allowed list for this key.") % model_name
            )

    def check_permission(self, perm):
        """Raise AccessError if key lacks the required permission."""
        self.ensure_one()
        perm_map = {
            TOOL_PERM_READ: self.perm_read,
            TOOL_PERM_WRITE: self.perm_write,
            TOOL_PERM_CREATE: self.perm_create,
            TOOL_PERM_DELETE: self.perm_delete,
            TOOL_PERM_EXECUTE: self.perm_execute,
        }
        if not perm_map.get(perm, False):
            raise AccessError(_("API key lacks '%s' permission.") % perm)

    def _get_allowed_models(self):
        """Return set of allowed model names, or empty set if unrestricted."""
        if not self.allowed_models:
            return set()
        return {m.strip() for m in self.allowed_models.split(",") if m.strip()}

    def _get_custom_blocked(self):
        """Return set of custom blocked model names for this key."""
        if not self.custom_blocked_models:
            return set()
        return {m.strip() for m in self.custom_blocked_models.split(",") if m.strip()}

    # ── Setup Guide (backend form view) ──────────────────────────────

    setup_guide_html = fields.Html(
        string="Setup Guide",
        compute="_compute_setup_guide_html",
        sanitize=False,
    )

    def _compute_setup_guide_html(self):
        base = self.env["ir.config_parameter"].sudo().get_param(
            "web.base.url", "http://localhost:8069"
        )
        endpoint = base + "/mcp/v1"
        for r in self:
            k = r.key_prefix + "..." if r.key_prefix else "[YOUR_KEY]"
            note = (
                "<div style='background:#fffbeb;border:1px solid #fcd34d;border-radius:6px;"
                "padding:10px 14px;font-size:13px;color:#92400e;margin-bottom:14px'>"
                f"&#9888; Plain key not stored — prefix shown for identification: "
                f"<code style='background:#fef3c7;padding:1px 6px;border-radius:3px'>{k}</code>. "
                "Use <b>Regenerate Key</b> to get a new plain key."
                "</div>"
            )

            def block(label, code):
                esc = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                return (
                    f"<div style='margin-bottom:14px'>"
                    f"<div style='font-size:12px;font-weight:600;color:#374151;margin-bottom:4px'>{label}</div>"
                    f"<div style='position:relative'>"
                    f"<pre style='background:#1e1e2e;color:#cdd6f4;border-radius:7px;padding:10px 80px 10px 12px;"
                    f"font-size:12px;line-height:1.5;overflow-x:auto;white-space:pre;margin:0'>{esc}</pre>"
                    f"<button onclick=\"var t=this.previousSibling.textContent;"
                    f"navigator.clipboard.writeText(t).then(()=>{{this.textContent='✓ Copied!';"
                    f"setTimeout(()=>this.textContent='Copy',2000)}})\" "
                    f"style='position:absolute;top:6px;right:6px;background:rgba(255,255,255,.1);"
                    f"border:1px solid rgba(255,255,255,.2);color:#cdd6f4;padding:3px 8px;"
                    f"border-radius:4px;font-size:11px;cursor:pointer'>Copy</button>"
                    f"</div></div>"
                )

            import json as _json
            claude_cmd = f"claude mcp add --transport http odoo \"{endpoint}?key=[YOUR_KEY]\""
            cursor_cfg = _json.dumps(
                {"mcpServers": {"odoo": {"url": endpoint, "headers": {"Authorization": "Bearer [YOUR_KEY]"}}}},
                indent=2,
            )
            continue_cfg = _json.dumps(
                {"mcpServers": [{"name": "odoo", "transport": {
                    "type": "streamable-http", "url": f"{endpoint}?key=[YOUR_KEY]"
                }}]},
                indent=2,
            )
            desktop_cfg = _json.dumps(
                {"mcpServers": {"odoo": {
                    "command": "curl",
                    "args": ["-s", "-X", "POST", endpoint,
                             "-H", "Authorization: Bearer [YOUR_KEY]",
                             "-H", "Content-Type: application/json", "-d", "@-"],
                }}},
                indent=2,
            )
            r.setup_guide_html = (
                note
                + block("Claude Code — run in terminal:", claude_cmd)
                + block("Cursor IDE — .cursor/mcp.json:", cursor_cfg)
                + block("Continue.dev — ~/.continue/config.json:", continue_cfg)
                + block("Claude Desktop — claude_desktop_config.json:", desktop_cfg)
            )

    @check_identity
    def action_regenerate_key(self):
        """Open the wizard pre-filled with this key's settings for regeneration."""
        self.ensure_one()
        wizard = self.env["mcp.api.key.wizard"].create({
            "name": self.name + " (regenerated)",
            "user_id": self.user_id.id,
            "expiry_date": self.expiry_date,
            "rate_limit": self.rate_limit,
            "perm_write": self.perm_write,
            "perm_create": self.perm_create,
            "perm_delete": self.perm_delete,
            "perm_execute": self.perm_execute,
            "allowed_models": self.allowed_models or False,
        })
        # Deactivate old key so it no longer authenticates
        self.sudo().write({"active": False})
        return wizard.action_generate()
