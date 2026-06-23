# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import json
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# ── HTML helpers ──────────────────────────────────────────────────────────────

_COPY_JS = (
    "var el=document.getElementById('{cid}');"
    "var t=el.textContent;"
    "navigator.clipboard.writeText(t).then(function(){{"
    "  this.textContent='✓ Copied';"
    "  this.style.borderColor='#198754';this.style.color='#198754';"
    "  var b=this;"
    "  setTimeout(function(){{"
    "    b.textContent='Copy';"
    "    b.style.borderColor='rgba(255,255,255,.25)';b.style.color='#adb5bd';"
    "  }},2000);"
    "}}.bind(this)).catch(function(){{"
    "  var ta=document.createElement('textarea');ta.value=t;"
    "  document.body.appendChild(ta);ta.select();document.execCommand('copy');"
    "  document.body.removeChild(ta);"
    "  this.textContent='✓ Copied';var b=this;"
    "  setTimeout(function(){{b.textContent='Copy';}},2000);"
    "}}.bind(this));"
)

# Inline code style — neutral, readable, no brand color
_CI = (
    "background:#f1f5f9;color:#0f172a;padding:1px 5px;"
    "border-radius:3px;font-family:monospace;font-size:10.5px;"
    "border:1px solid #e2e8f0;"
)


def _e(s):
    """Minimal HTML escape."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _card(rec_id, slot, accent, badge, emoji, name, desc, code, steps):
    """Render one client config card — Bootstrap 5 / Odoo-native styling."""
    cid = "wzcfg-%d-%s" % (rec_id, slot)
    code_esc = _e(code)
    copy_js = _COPY_JS.format(cid=cid)
    steps_html = "".join(
        "<li style='font-size:12px;color:#495057;line-height:1.6;margin-bottom:2px'>%s</li>" % s
        for s in steps
    )
    # badge background is accent at 12% opacity
    badge_bg = accent + "1f"
    return (
        # Card wrapper
        "<div style='"
        "border:1px solid #dee2e6;border-radius:6px;overflow:hidden;"
        "background:#fff;display:flex;flex-direction:column;"
        "box-shadow:0 1px 2px rgba(0,0,0,.04)'>"

        # Header — white bg, left accent border, name + badge
        "  <div style='"
        "border-left:3px solid {accent};padding:9px 13px;"
        "display:flex;align-items:center;gap:9px;"
        "border-bottom:1px solid #f1f3f5'>"
        "    <span style='font-size:18px;line-height:1;flex-shrink:0'>{emoji}</span>"
        "    <div style='flex:1;min-width:0'>"
        "      <div style='display:flex;align-items:center;gap:6px;flex-wrap:wrap'>"
        "        <span style='font-weight:700;font-size:13px;color:#212529'>{name}</span>"
        "        <span style='"
        "font-size:9.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;"
        "padding:1px 7px;border-radius:20px;"
        "background:{badge_bg};color:{accent}"
        "'>{badge}</span>"
        "      </div>"
        "      <div style='font-size:11.5px;color:#6c757d;margin-top:1px'>{desc}</div>"
        "    </div>"
        "  </div>"

        # Code block
        "  <div style='position:relative'>"
        "    <pre id='{cid}' style='"
        "background:#212529;color:#adb5bd;margin:0;"
        "padding:10px 13px;font-size:10.5px;line-height:1.55;"
        "overflow-x:auto;white-space:pre;"
        "font-family:SFMono-Regular,Menlo,Monaco,Consolas,monospace;"
        "border-radius:0'>{code_esc}</pre>"
        "    <button onclick=\"{copy_js}\" style='"
        "position:absolute;top:6px;right:6px;"
        "padding:2px 9px;font-size:10.5px;font-weight:500;"
        "cursor:pointer;border-radius:4px;"
        "border:1px solid rgba(255,255,255,.25);"
        "background:transparent;color:#adb5bd;transition:all .15s;"
        "'>Copy</button>"
        "  </div>"

        # Setup steps
        "  <div style='padding:9px 13px 11px;background:#f8f9fa;border-top:1px solid #f1f3f5;flex:1'>"
        "    <div style='"
        "font-size:9.5px;font-weight:700;color:#adb5bd;"
        "text-transform:uppercase;letter-spacing:.08em;margin-bottom:5px"
        "'>Setup</div>"
        "    <ol style='margin:0;padding-left:16px'>{steps_html}</ol>"
        "  </div>"
        "</div>"
    ).format(
        accent=accent, badge_bg=badge_bg, badge=badge,
        emoji=emoji, name=_e(name), desc=_e(desc),
        cid=cid, code_esc=code_esc, copy_js=copy_js,
        steps_html=steps_html,
    )


class McpApiKeyWizard(models.TransientModel):
    _name = "mcp.api.key.wizard"
    _description = "MCP API Key Setup Wizard"

    # ── Step 1 — Input ────────────────────────────────────────────────
    name = fields.Char(string="Key Name", required=True, default="My MCP Key")
    mcp_server_name = fields.Char(
        string="MCP Server Name",
        required=True,
        default="odoo",
        help="Short slug used to register this server in your AI client (e.g. 'odoo-acme'). No spaces.",
    )
    user_id = fields.Many2one(
        "res.users", string="Owner",
        default=lambda self: self.env.user, required=True,
    )
    expiry_date = fields.Date(string="Expiry Date")
    rate_limit = fields.Integer(string="Rate Limit (req/hr)", default=100)
    perm_write = fields.Boolean(string="Write Permission", default=False)
    perm_create = fields.Boolean(string="Create Permission", default=False)
    perm_delete = fields.Boolean(string="Delete Permission", default=False)
    perm_execute = fields.Boolean(string="Execute Permission", default=False)
    allowed_models = fields.Text(
        string="Allowed Models",
        help="Comma-separated model names. Empty = all allowed.",
    )

    # ── Step 2 — Result ───────────────────────────────────────────────
    plain_key = fields.Char(string="API Key (copy now — shown once)", readonly=True, copy=False)
    key_id = fields.Many2one("mcp.api.key", string="Key Record", readonly=True)
    mcp_endpoint = fields.Char(string="MCP Endpoint", compute="_compute_configs")

    # Raw config fields (used by download route)
    config_claude = fields.Char(compute="_compute_configs")
    config_cursor = fields.Text(compute="_compute_configs")
    config_continue = fields.Text(compute="_compute_configs")
    config_antigravity = fields.Text(compute="_compute_configs")
    config_desktop = fields.Text(compute="_compute_configs")
    config_gemini = fields.Text(compute="_compute_configs")
    config_codex = fields.Text(compute="_compute_configs")
    config_opencode = fields.Text(compute="_compute_configs")
    config_openai = fields.Text(compute="_compute_configs")

    # Beautiful HTML rendered panel (replaces individual fields in view)
    step2_html = fields.Html(
        string="Client Setup",
        compute="_compute_step2_html",
        sanitize=False,
    )

    def _base_url(self):
        return self.env["ir.config_parameter"].sudo().get_param(
            "web.base.url", "http://localhost:8069"
        )

    @api.depends("plain_key", "mcp_server_name")
    def _compute_configs(self):
        base = self._base_url()
        endpoint = base + "/mcp/v1"
        for r in self:
            r.mcp_endpoint = endpoint
            k = r.plain_key or "[YOUR_KEY]"
            srv = r.mcp_server_name or "odoo"
            r.config_claude = f'claude mcp add --transport http {srv} "{endpoint}?key={k}"'
            r.config_cursor = json.dumps(
                {"mcpServers": {srv: {"url": endpoint, "headers": {"Authorization": f"Bearer {k}"}}}},
                indent=2,
            )
            r.config_continue = json.dumps(
                {"mcpServers": [{"name": srv, "transport": {"type": "streamable-http", "url": f"{endpoint}?key={k}"}}]},
                indent=2,
            )
            r.config_antigravity = json.dumps(
                {"mcp": {"servers": [{"name": srv, "endpoint": endpoint, "auth": {"type": "bearer", "token": k}}]}},
                indent=2,
            )
            r.config_desktop = json.dumps(
                {"mcpServers": {srv: {
                    "command": "curl",
                    "args": ["-s", "-X", "POST", endpoint,
                             "-H", f"Authorization: Bearer {k}",
                             "-H", "Content-Type: application/json", "-d", "@-"],
                }}},
                indent=2,
            )
            r.config_gemini = json.dumps(
                {"mcpServers": {srv: {"httpUrl": endpoint, "headers": {"Authorization": f"Bearer {k}"}}}},
                indent=2,
            )
            r.config_codex = (
                f"# Add to ~/.codex/config.yaml\n"
                f"mcp_servers:\n"
                f"  - name: {srv}\n"
                f"    url: {endpoint}?key={k}\n"
            )
            r.config_opencode = json.dumps(
                {"mcp": {srv: {"type": "remote", "url": f"{endpoint}?key={k}"}}},
                indent=2,
            )
            r.config_openai = (
                "# pip install openai mcp\n"
                "import asyncio\n"
                "from mcp import ClientSession\n"
                "from mcp.client.streamable_http import streamablehttp_client\n"
                "from openai import OpenAI\n\n"
                f'MCP_URL = "{endpoint}?key={k}"\n\n'
                "async def get_tools():\n"
                "    async with streamablehttp_client(MCP_URL) as (r, w, _):\n"
                "        async with ClientSession(r, w) as s:\n"
                "            await s.initialize()\n"
                "            return (await s.list_tools()).tools\n\n"
                "tools = asyncio.run(get_tools())\n"
                "oai_tools = [{'type': 'function', 'function': {\n"
                "    'name': t.name, 'description': t.description,\n"
                "    'parameters': t.inputSchema}} for t in tools]\n\n"
                "client = OpenAI()  # set OPENAI_API_KEY env var\n"
                "response = client.chat.completions.create(\n"
                "    model='gpt-4o', tools=oai_tools,\n"
                "    messages=[{'role': 'user', 'content': 'Search for top 5 customers'}]\n"
                ")"
            )

    @api.depends("mcp_endpoint", "plain_key", "mcp_server_name",
                 "config_claude", "config_cursor", "config_continue",
                 "config_desktop", "config_gemini", "config_codex",
                 "config_opencode", "config_openai")
    def _compute_step2_html(self):
        for r in self:
            if not r.plain_key:
                r.step2_html = False
                continue
            rid = r.id or 0
            srv = r.mcp_server_name or "odoo"
            endpoint = r.mcp_endpoint or ""
            k = r.plain_key or "[YOUR_KEY]"

            ci = _CI  # inline code style shorthand
            cards = [
                _card(rid, "claude", "#5b4fcf", "CLI", "🤖", "Claude Code",
                      "Anthropic's AI coding CLI — run once in terminal, done.",
                      r.config_claude or "",
                      [
                          "Install: <code style='%s'>npm install -g @anthropic-ai/claude-code</code>" % ci,
                          "Run the command above in your terminal.",
                          "Open Claude Code: <code style='%s'>claude</code>" % ci,
                          "Test: <em>\"List my top 5 customers in Odoo\"</em>",
                      ]),
                _card(rid, "cursor", "#0d6efd", "IDE", "▶", "Cursor IDE",
                      "AI-first code editor with native MCP support.",
                      r.config_cursor or "",
                      [
                          "Install Cursor from <strong>cursor.com</strong>.",
                          "Create or open <code style='%s'>.cursor/mcp.json</code> in project root." % ci,
                          "Paste JSON above (merge into <code style='%s'>mcpServers</code>)." % ci,
                          "Restart Cursor. Type <code style='%s'>@%s</code> in Cursor Chat." % (ci, srv),
                      ]),
                _card(rid, "continue", "#198754", "EXTENSION", "🔧", "Continue.dev",
                      "Open-source AI assistant for VS Code and JetBrains.",
                      r.config_continue or "",
                      [
                          "Install <strong>Continue</strong> in VS Code / JetBrains Marketplace.",
                          "Open <code style='%s'>~/.continue/config.json</code> (gear icon)." % ci,
                          "Merge JSON into <code style='%s'>mcpServers</code> array." % ci,
                          "Reload: <code style='%s'>Ctrl+Shift+P → Reload Window</code>." % ci,
                      ]),
                _card(rid, "zed", "#fd7e14", "EDITOR", "⚡", "Zed Editor",
                      "High-performance editor with native MCP support.",
                      json.dumps({"context_servers": {srv: {
                          "command": {"path": "npx", "args": ["-y", "mcp-remote", f"{endpoint}?key={k}"]},
                          "settings": {},
                      }}}, indent=2),
                      [
                          "Install Zed from <strong>zed.dev</strong>.",
                          "Open <code style='%s'>~/.config/zed/settings.json</code>." % ci,
                          "Merge JSON into <code style='%s'>context_servers</code> key." % ci,
                          "Bridge: <code style='%s'>npm install -g mcp-remote</code>" % ci,
                          "Restart Zed → Agent Panel → ask about Odoo data.",
                      ]),
                _card(rid, "desktop", "#5b4fcf", "DESKTOP", "🖥", "Claude Desktop",
                      "Anthropic's desktop app for Mac and Windows with MCP built-in.",
                      r.config_desktop or "",
                      [
                          "Download from <strong>claude.ai/download</strong>. Log in.",
                          "Open Settings → Developer → <strong>Edit Config</strong>.",
                          "Merge JSON into <code style='%s'>claude_desktop_config.json</code>." % ci,
                          "Restart. A 🔨 icon confirms Odoo tools are connected.",
                      ]),
                _card(rid, "gemini", "#0dcaf0", "CLI", "✨", "Gemini CLI",
                      "Google's open-source AI agent for the terminal.",
                      r.config_gemini or "",
                      [
                          "Install: <code style='%s'>npm install -g @google/gemini-cli</code>" % ci,
                          "Authenticate: run <code style='%s'>gemini</code> → Google login." % ci,
                          "Open <code style='%s'>~/.gemini/settings.json</code>." % ci,
                          "Merge JSON into <code style='%s'>mcpServers</code>." % ci,
                      ]),
                _card(rid, "codex", "#198754", "CLI", "💻", "Codex CLI",
                      "OpenAI's terminal AI agent — uses your OpenAI API key.",
                      r.config_codex or "",
                      [
                          "Install: <code style='%s'>npm install -g @openai/codex</code>" % ci,
                          "Set key: <code style='%s'>export OPENAI_API_KEY=sk-...</code>" % ci,
                          "Open <code style='%s'>~/.codex/config.yaml</code> and paste YAML above." % ci,
                          "Run: <code style='%s'>codex</code>" % ci,
                      ]),
                _card(rid, "opencode", "#6c757d", "CLI", "⚙", "OpenCode",
                      "Open-source terminal AI agent — works with multiple AI providers.",
                      r.config_opencode or "",
                      [
                          "Install: <code style='%s'>npm install -g opencode-ai</code>" % ci,
                          "Create <code style='%s'>opencode.json</code> in project root." % ci,
                          "Paste JSON above and save.",
                          "Run: <code style='%s'>opencode</code>" % ci,
                      ]),
                _card(rid, "chatgpt", "#10a37f", "WEB", "💬", "ChatGPT",
                      "ChatGPT.com native MCP — paste URL directly, no file config needed.",
                      f"{endpoint}?key={k}",
                      [
                          "Go to <strong>chatgpt.com</strong> → sidebar → <strong>Apps</strong>.",
                          "Click <strong>New App</strong> → name it (e.g. <em>Odoo</em>).",
                          "Connection → <strong>Server URL</strong> tab → paste URL above.",
                          "Auth: <strong>No Auth</strong> (key is in the URL). Click <strong>Create</strong>.",
                          "Ask: <em>\"Show my overdue invoices\"</em>",
                      ]),
                _card(rid, "openai", "#343a40", "PYTHON", "🐍", "OpenAI SDK",
                      "Python bridge — loads Odoo MCP tools into any OpenAI-compatible model.",
                      r.config_openai or "",
                      [
                          "Install: <code style='%s'>pip install openai mcp</code>" % ci,
                          "Set key: <code style='%s'>export OPENAI_API_KEY=sk-...</code>" % ci,
                          "Copy script above into <code style='%s'>odoo_ai.py</code> and run." % ci,
                          "Edit the <code style='%s'>content</code> string with your question." % ci,
                      ]),
            ]

            grid = (
                "<div style='display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px'>"
                + "".join(cards)
                + "</div>"
            )

            r.step2_html = grid

    def action_generate(self):
        """Generate the key and reload this wizard record to show result."""
        self.ensure_one()
        rec, plain_key = self.env["mcp.api.key"].generate_key(
            self.name,
            user_id=self.user_id.id,
            expiry_date=self.expiry_date,
            rate_limit=self.rate_limit,
            perm_write=self.perm_write,
            perm_create=self.perm_create,
            perm_delete=self.perm_delete,
            perm_execute=self.perm_execute,
            allowed_models=self.allowed_models or False,
        )
        self.write({"plain_key": plain_key, "key_id": rec.id})
        return {
            "type": "ir.actions.act_window",
            "name": _("Key Created — Save Your Config"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": dict(self.env.context, dialog_size="extra-large"),
        }

    def action_open_key(self):
        """Navigate to the created key record."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("MCP API Key"),
            "res_model": "mcp.api.key",
            "res_id": self.key_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_download_config(self):
        """Download all configs as a text file."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": "/mcp/wizard/%d/download" % self.id,
            "target": "new",
        }
