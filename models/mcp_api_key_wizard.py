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
    "  this.textContent='✓ Copied!';this.style.background='#059669';"
    "  var b=this;"
    "  setTimeout(function(){{b.textContent='Copy';b.style.background='rgba(255,255,255,.12)';}},2200);"
    "}}.bind(this)).catch(function(){{"
    "  var ta=document.createElement('textarea');ta.value=t;"
    "  document.body.appendChild(ta);ta.select();document.execCommand('copy');"
    "  document.body.removeChild(ta);"
    "  this.textContent='✓ Copied!';var b=this;"
    "  setTimeout(function(){{b.textContent='Copy';}},2200);"
    "}}.bind(this));"
)

_CARD_STYLE = (
    "border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;"
    "background:#fff;display:flex;flex-direction:column;"
)
_HEADER_STYLE = (
    "background:linear-gradient(135deg,#6c47ff 0%,#9370db 100%);"
    "padding:10px 14px;display:flex;align-items:center;gap:8px;"
)
_CODE_WRAP = "position:relative;margin:0;"
_PRE_STYLE = (
    "background:#0d1117;color:#e6edf3;border-radius:0;padding:12px 14px;"
    "font-size:11.5px;line-height:1.55;overflow-x:auto;white-space:pre;"
    "margin:0;font-family:'Fira Code',monospace,monospace;"
)
_COPY_BTN = (
    "position:absolute;top:6px;right:6px;background:rgba(255,255,255,.12);"
    "border:1px solid rgba(255,255,255,.2);color:#e6edf3;padding:3px 9px;"
    "border-radius:5px;font-size:11px;cursor:pointer;transition:background .15s;"
)
_STEPS_STYLE = (
    "padding:10px 14px 12px 14px;background:#f9fafb;"
    "border-top:1px solid #f0f0f0;flex:1;"
)
_STEPS_TITLE = (
    "font-size:10.5px;font-weight:700;color:#6c47ff;"
    "text-transform:uppercase;letter-spacing:.05em;margin-bottom:5px;"
)
_OL_STYLE = "margin:0;padding-left:16px;"
_LI_STYLE = "font-size:11.5px;color:#374151;line-height:1.6;margin-bottom:1px;"
_CODE_INLINE = "background:#ede9fe;color:#4c1d95;padding:1px 4px;border-radius:3px;font-size:11px;"


def _e(s):
    """Minimal HTML escape."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _card(rec_id, slot, emoji, name, desc, code, steps):
    """Render one client config card."""
    cid = "wzcfg-%d-%s" % (rec_id, slot)
    code_esc = _e(code)
    copy_onclick = _COPY_JS.format(cid=cid)
    steps_html = "".join(
        "<li style='%s'>%s</li>" % (_LI_STYLE, s) for s in steps
    )
    return (
        "<div style='%s'>"
        "  <div style='%s'>"
        "    <span style='font-size:18px'>%s</span>"
        "    <div>"
        "      <div style='font-weight:700;font-size:13px;color:#fff'>%s</div>"
        "      <div style='font-size:11px;color:rgba(255,255,255,.8);margin-top:1px'>%s</div>"
        "    </div>"
        "  </div>"
        "  <div style='%s'>"
        "    <pre id='%s' style='%s'>%s</pre>"
        "    <button onclick=\"%s\" style='%s'>Copy</button>"
        "  </div>"
        "  <div style='%s'>"
        "    <div style='%s'>&#128196; Setup</div>"
        "    <ol style='%s'>%s</ol>"
        "  </div>"
        "</div>"
    ) % (
        _CARD_STYLE, _HEADER_STYLE,
        emoji, _e(name), _e(desc),
        _CODE_WRAP, cid, _PRE_STYLE, code_esc, copy_onclick, _COPY_BTN,
        _STEPS_STYLE, _STEPS_TITLE, _OL_STYLE, steps_html,
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

            cards = [
                _card(rid, "claude", "🤖", "Claude Code",
                      "Anthropic's AI coding CLI — run once in terminal, done.",
                      r.config_claude or "",
                      [
                          "Install: <code style='%s'>npm install -g @anthropic-ai/claude-code</code>" % _CODE_INLINE,
                          "Run the command above in your terminal.",
                          "Open Claude Code: <code style='%s'>claude</code>" % _CODE_INLINE,
                          "Test: <em>\"List my top 5 customers in Odoo\"</em>",
                      ]),
                _card(rid, "cursor", "▶", "Cursor IDE",
                      "AI-first code editor with native MCP support.",
                      r.config_cursor or "",
                      [
                          "Install Cursor from <strong>cursor.com</strong>.",
                          "Create or open <code style='%s'>.cursor/mcp.json</code> in your project root." % _CODE_INLINE,
                          "Paste the JSON above (merge into <code style='%s'>mcpServers</code> if it exists)." % _CODE_INLINE,
                          "Save and restart Cursor. Type <code style='%s'>@%s</code> in Cursor Chat." % (_CODE_INLINE, srv),
                      ]),
                _card(rid, "continue", "🔧", "Continue.dev",
                      "Open-source AI assistant for VS Code &amp; JetBrains.",
                      r.config_continue or "",
                      [
                          "Install <strong>Continue</strong> extension in VS Code / JetBrains Marketplace.",
                          "Open <code style='%s'>~/.continue/config.json</code> (gear icon in Continue sidebar)." % _CODE_INLINE,
                          "Merge the JSON above into the <code style='%s'>mcpServers</code> array." % _CODE_INLINE,
                          "Reload VS Code: <code style='%s'>Ctrl+Shift+P → Developer: Reload Window</code>." % _CODE_INLINE,
                      ]),
                _card(rid, "zed", "⚡", "Zed Editor",
                      "High-performance multiplayer editor with native MCP support.",
                      json.dumps({"context_servers": {srv: {
                          "command": {"path": "npx", "args": ["-y", "mcp-remote", f"{endpoint}?key={k}"]},
                          "settings": {},
                      }}}, indent=2),
                      [
                          "Install Zed from <strong>zed.dev</strong> (free, Mac/Linux/Windows).",
                          "Open <code style='%s'>~/.config/zed/settings.json</code> (Zed → Settings)." % _CODE_INLINE,
                          "Merge the JSON above into the <code style='%s'>context_servers</code> key." % _CODE_INLINE,
                          "Install bridge: <code style='%s'>npm install -g mcp-remote</code>" % _CODE_INLINE,
                          "Restart Zed. Open Agent Panel → ask about your Odoo data.",
                      ]),
                _card(rid, "desktop", "🖥", "Claude Desktop",
                      "Anthropic's desktop app for Mac &amp; Windows with MCP built-in.",
                      r.config_desktop or "",
                      [
                          "Download from <strong>claude.ai/download</strong>. Log in.",
                          "Open Settings → Developer → <strong>Edit Config</strong>.",
                          "Merge the JSON into <code style='%s'>claude_desktop_config.json</code>." % _CODE_INLINE,
                          "Restart Claude Desktop. A 🔨 icon shows available Odoo tools.",
                      ]),
                _card(rid, "gemini", "✨", "Gemini CLI",
                      "Google's open-source AI agent for the terminal.",
                      r.config_gemini or "",
                      [
                          "Install: <code style='%s'>npm install -g @google/gemini-cli</code>" % _CODE_INLINE,
                          "Authenticate: run <code style='%s'>gemini</code> → follow Google login." % _CODE_INLINE,
                          "Open or create <code style='%s'>~/.gemini/settings.json</code>." % _CODE_INLINE,
                          "Paste the JSON above (merge into <code style='%s'>mcpServers</code>)." % _CODE_INLINE,
                      ]),
                _card(rid, "codex", "💻", "Codex CLI (OpenAI)",
                      "OpenAI's terminal AI agent — uses your OpenAI API key.",
                      r.config_codex or "",
                      [
                          "Install: <code style='%s'>npm install -g @openai/codex</code>" % _CODE_INLINE,
                          "Set key: <code style='%s'>export OPENAI_API_KEY=sk-...</code>" % _CODE_INLINE,
                          "Create or open <code style='%s'>~/.codex/config.yaml</code> and paste YAML above." % _CODE_INLINE,
                          "Run <code style='%s'>codex</code>." % _CODE_INLINE,
                      ]),
                _card(rid, "opencode", "⚙", "OpenCode",
                      "Open-source terminal AI agent supporting multiple AI providers.",
                      r.config_opencode or "",
                      [
                          "Install: <code style='%s'>npm install -g opencode-ai</code>" % _CODE_INLINE,
                          "Create <code style='%s'>opencode.json</code> in project root (or <code style='%s'>~/.config/opencode/opencode.json</code>)." % (_CODE_INLINE, _CODE_INLINE),
                          "Paste the JSON above and save.",
                          "Run <code style='%s'>opencode</code>." % _CODE_INLINE,
                      ]),
                _card(rid, "chatgpt", "💬", "ChatGPT (Native MCP)",
                      "ChatGPT.com supports MCP connectors — paste the URL directly, no file config needed.",
                      f"{endpoint}?key={k}",
                      [
                          "Go to <strong>chatgpt.com</strong> → left sidebar → <strong>Apps</strong> (or Codex icon).",
                          "Click <strong>New App</strong> → give it a name (e.g. <em>Odoo</em>).",
                          "Under <strong>Connection</strong> → select <strong>Server URL</strong> tab.",
                          "Paste the URL above into the Server URL field.",
                          "Authentication: set to <strong>No Auth</strong> (key is already in the URL).",
                          "Check <em>\"I understand and want to continue\"</em> → click <strong>Create</strong>.",
                          "Now ask ChatGPT: <em>\"Show my overdue invoices\"</em>",
                      ]),
                _card(rid, "openai", "🐍", "OpenAI / ChatGPT (Python)",
                      "Python bridge — loads Odoo MCP tools into any OpenAI-compatible model.",
                      r.config_openai or "",
                      [
                          "Install deps: <code style='%s'>pip install openai mcp</code>" % _CODE_INLINE,
                          "Set key: <code style='%s'>export OPENAI_API_KEY=sk-...</code>" % _CODE_INLINE,
                          "Copy the script above into <code style='%s'>odoo_ai.py</code> and run it." % _CODE_INLINE,
                          "Change the <code style='%s'>content</code> string to your actual question." % _CODE_INLINE,
                      ]),
            ]

            grid = (
                "<div style='display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px'>"
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
