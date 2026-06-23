# ucs_mcp — Module Memory for Claude

**Module:** `ucs_mcp` in `/home/sanjay/odoo/workspace/ucs-erp/`
**Odoo version:** 19 Community / Enterprise (addons path via `ucs_mcp_test.conf` on port 8072)
**Purpose:** Expose Odoo 19 to Claude Code, Claude Desktop, Cursor, Gemini CLI, OpenAI, ChatGPT etc via MCP (Model Context Protocol) JSON-RPC 2.0 over HTTP.

---

## Instances

### odoo.sh (live)
- **URL:** https://ucs-mcp.odoo.com/
- **User:** admin
- **Password:** jKTY8Kc8a53v8Be
- Module `ucs_mcp` already installed on this instance.
- MCP endpoint: `https://ucs-mcp.odoo.com/mcp/v1`
- Health: `curl https://ucs-mcp.odoo.com/mcp/health` → `{"status":"ok","tool_count":25}`
- DB: `uncannycs-ucs-mcp-main-33913980`

**Demo API Keys (seeded):**
| Key | Plain token |
|-----|-------------|
| Demo Full Access Key | `ucs_mcp_0zjZ5r5kWaBsBnH7qg3cv4laUarM33tjX-SlbMtAh0o` |
| Demo Read-Only Key | `ucs_mcp_r9aeeT68VwusATXtawbSoSXunTpm-CPRjFiIDNjx9dA` |
| Demo Sales Key | `ucs_mcp_RMWH8kN3bZs4MJlqrzg611Rx71rqdYIw4BGb9hmNFGM` |

**Demo Data seeded:**
- 8 partners (Acme Corp, Gulf Traders, Sigma Solutions, etc.) — ids 8–15
- 5 products (MCP Demo Widget/Laptop/Keyboard/Service Pack/Consulting) — tmpl ids 1–5
- Sales orders, invoices created via `scripts/seed_remote.py`

### Local Test Config
```
conf: /home/sanjay/odoo/workspace/ucs_mcp_test.conf
port: 8072
addons_path includes: ucs-erp (so ucs_mcp is loaded)
```
Health check: `curl http://localhost:8072/mcp/health`

---

## Module Structure

```
ucs_mcp/
├── __manifest__.py          version 19.0.1.0.0, depends: base, mail, web
├── __init__.py
├── const.py                 constants: SYSTEM_BLOCKED_MODELS, DANGEROUS_METHODS, perm names, limits
├── controllers/
│   └── mcp_controller.py    all HTTP routes (health, portal, /mcp/v1 JSON-RPC endpoint)
├── models/
│   ├── mcp_api_key.py       mcp.api.key — auth, rate limiting, model access control
│   ├── mcp_api_key_wizard.py mcp.api.key.wizard — step1/step2 setup wizard, 10-client config cards
│   └── mcp_audit_log.py     mcp.audit.log — every tool call logged, cron purges old entries
├── tools/
│   ├── base.py              BaseMcpTool ABC — run(), execute(), _log(), _format_error()
│   ├── mcp_tool_registry.py  _REGISTRY dict, register() decorator, get_tool(), get_tools_schema()
│   ├── generic/             9 tools: search_records, search_count, get_record, get_fields,
│   │                        smart_context, create_record, update_record, delete_record,
│   │                        execute_method, get_report_pdf, read_group
│   ├── sales/               3 tools: create_sale_order, confirm_sale_order, get_customer_statement
│   ├── accounting/          4 tools: create_invoice, post_invoice, register_payment, get_account_balance
│   ├── inventory/           2 tools: get_stock_level, create_stock_move
│   ├── hr/                  2 tools: get_employee_list, create_leave_request
│   ├── gst/                 2 tools: get_gst_summary, validate_gstin (requires l10n_in)
│   └── whatsapp/            1 tool: send_whatsapp_message (requires meta_cloud_whatsapp)
├── views/                   mcp_api_key_views.xml, mcp_api_key_wizard_views.xml,
│                            mcp_audit_log_views.xml, mcp_portal_templates.xml
├── security/
│   ├── mcp_security.xml     groups: ucs_mcp.group_mcp_admin, ucs_mcp.group_mcp_user
│   └── ir.model.access.csv  ACLs for mcp.api.key, mcp.audit.log, mcp.api.key.wizard
├── data/
│   └── mcp_cron.xml         daily purge cron for old audit log entries
└── scripts/
    └── install_demo_data.py
```

---

## Architecture Decisions

### Thin models, fat tools
- `mcp.api.key` only handles auth, rate limiting, model access. No business logic.
- `mcp.audit.log` only logs. Class method `_log()` so it can be called with any env.
- All business logic lives in `tools/` — each tool is a class with `execute(params)`.

### Tool registration pattern
```python
# Decorator self-registers at import time — no manual registry updates needed
@register
class SearchRecords(BaseMcpTool):
    name = "search_records"
    description = "..."
    required_permission = "read"
    input_schema = {...}

    def execute(self, params):
        ...
```

### BaseMcpTool.run() flow
1. `api_key.check_permission(self.required_permission)`
2. `api_key.check_model_access(model_name)` if model in params
3. `self.execute(params)` — runs as key owner's env (record rules apply, no sudo bypass)
4. `McpAuditLog._log(...)` always — even on error
5. Returns JSON-serialisable dict

### Auth flow in controller
- Bearer token from `Authorization: Bearer ucs_mcp_...` header
- Fallback: `?key=` query param (for clients that can't set headers)
- SHA-256 hash comparison — plain key never stored
- Key prefix (first 12 chars) stored for identification
- `initialize` method skips auth (MCP protocol spec)

### sudo() usage — documented inline in models
- `mcp.api.key.authenticate()` → sudo() to bypass owner record rule during lookup
- `_check_rate_limit()` / `_record_usage()` → sudo() to write counters regardless of caller perms
- `McpAuditLog._log()` → sudo() so any tool can write logs
- Never sudo() for actual business operations in tools

---

## MCP Endpoint

**URL:** `POST /mcp/v1`
**Protocol:** JSON-RPC 2.0
**Auth:** `Authorization: Bearer ucs_mcp_<token>` or `?key=<token>`

**Methods supported:**
- `initialize` — returns protocol version + capabilities (no auth required)
- `ping` → `{}`
- `tools/list` → array of tool schemas
- `tools/call` → `{name, arguments}` → runs tool, returns `{content: [{type:"text", text:...}]}`

**Other routes:**
- `GET /mcp/health` — public, returns `{status:"ok", tool_count:23}`
- `GET /mcp/connect` — portal: guest sees login CTA, logged-in user sees key management
- `POST /mcp/connect/create` — create key from portal form
- `GET /mcp/connect/created` — shows plain key + 10 client configs (one-time)
- `POST /mcp/connect/revoke` — deactivate key
- `POST /mcp/connect/rotate` — regenerate key hash, shows new plain key once
- `GET /mcp/wizard/<id>/download` — download all configs as text file

---

## Security Model

| Layer | Mechanism |
|-------|-----------|
| Transport | HTTPS at reverse proxy |
| Auth | SHA-256 Bearer token |
| Permissions | Per-key: read/write/create/delete/execute |
| Model access | System blocklist + per-key whitelist + per-key custom blocklist |
| Rate limiting | Sliding 1-hour window per key (default 100 req/hr, 0=unlimited) |
| Audit | Every call → mcp.audit.log |
| Record rules | Users see only own keys (group_mcp_admin bypasses) |

**System blocked models (const.py `SYSTEM_BLOCKED_MODELS`):**
`ir.config_parameter`, `ir.rule`, `ir.model.access`, `res.users`, `res.groups`,
`ir.module.module`, `ir.model`, `ir.model.fields`, `base.automation`,
`mail.template`, `ir.actions.server`, `ir.cron`

**Dangerous methods blocked in execute_method tool (const.py `DANGEROUS_METHODS`):**
`unlink, write, create, _write, _create, sudo, execute, execute_kw, shell, exec, eval, load, import_data, base_import, _sql_constraints`

---

## All 23 Tools

| # | Tool name | Category | Permission |
|---|-----------|----------|-----------|
| 1 | search_records | generic | read |
| 2 | search_count | generic | read |
| 3 | get_record | generic | read |
| 4 | get_fields | generic | read |
| 5 | smart_context | generic | read |
| 6 | create_record | generic | create |
| 7 | update_record | generic | write |
| 8 | delete_record | generic | delete |
| 9 | execute_method | generic | execute |
| 10 | get_report_pdf | generic | read |
| 11 | read_group | generic | read |
| 12 | create_sale_order | sales | create |
| 13 | confirm_sale_order | sales | write |
| 14 | get_customer_statement | sales | read |
| 15 | create_invoice | accounting | create |
| 16 | post_invoice | accounting | write |
| 17 | register_payment | accounting | create |
| 18 | get_account_balance | accounting | read |
| 19 | get_stock_level | inventory | read |
| 20 | create_stock_move | inventory | create |
| 21 | get_employee_list | hr | read |
| 22 | create_leave_request | hr | create |
| 23 | get_gst_summary | gst | read |
| 24 | validate_gstin | gst | read |
| 25 | send_whatsapp_message | whatsapp | write |

> README says 23 but manifest count may differ — tool count from health endpoint is authoritative.

---

## Wizard — 10 Client Config Cards

`mcp.api.key.wizard` step2 renders a 2-column HTML grid of cards for:
Claude Code, Cursor IDE, Continue.dev, Zed Editor, Claude Desktop, Gemini CLI,
Codex CLI (OpenAI), OpenCode, ChatGPT (native MCP URL paste), OpenAI Python bridge.

Config fields: `config_claude`, `config_cursor`, `config_continue`, `config_antigravity`,
`config_desktop`, `config_gemini`, `config_codex`, `config_opencode`, `config_openai`

Download route: `GET /mcp/wizard/<wizard_id>/download` → plain text file with all configs.

---

## mcp.api.key Fields Reference

```
name, key_hash (SHA-256), key_prefix (first 12 chars), user_id, company_id,
expiry_date, active, rate_limit (req/hr, 0=unlimited),
request_count, rate_window_start (sliding 1hr window),
perm_read (default True), perm_write, perm_create, perm_delete, perm_execute,
allowed_models (comma-sep, empty=all), custom_blocked_models (comma-sep),
last_used, use_count
```

Key generation: `env["mcp.api.key"].generate_key(name, user_id=uid, perm_read=True, ...)`
Returns `(record, plain_key)` — plain key shown/returned ONCE, never stored.

---

## mcp.audit.log Fields Reference

```
api_key_id, user_id, tool_name, model_name, method,
request_data (text, capped 4096), response_summary (text, capped 2048),
status (success/error/denied), error_message, duration_ms, ip_address, create_date
```

Purge cron: daily, reads `ucs_mcp.audit_log_retention_days` system param (default 90).

---

## Adding a New Tool (pattern)

1. Create `tools/<category>/<tool_name>.py`
2. Import and use `@register` from `mcp_tool_registry`
3. Subclass `BaseMcpTool`, set `name`, `description`, `required_permission`, `input_schema`
4. Implement `execute(self, params) -> dict`
5. Add import in `tools/<category>/__init__.py`
6. Tool auto-appears in `tools/list` — no registry changes needed

---

## Known State / Work Done

- Module fully built: models, controller, 25 tools, wizard with 10 client cards, portal, audit log
- `ucs_mcp_blueprint.pdf` and `ucs_mcp_test_report.html` exist in module root (reference docs)
- STDIO bridge script exists: `mcp_stdio_bridge.sh` (for clients needing stdio transport)
- Last session goal: "super module" — **clarify with user what this means before starting**
  - Possibly: making ucs_mcp a standalone PyPI/GitHub repo (not inside ucs-erp)
  - Possibly: adding more tool categories (project, CRM, purchase, manufacturing)
  - Possibly: multi-database support or SaaS mode

---

## What to Check at Session Start

```bash
# Is the server running?
curl http://localhost:8072/mcp/health

# Any syntax errors?
python3 -m py_compile /home/sanjay/odoo/workspace/ucs-erp/ucs_mcp/controllers/mcp_controller.py

# Git status
cd /home/sanjay/odoo/workspace/ucs-erp && git log --oneline -10
```

---

## Standards (from workspace CLAUDE.md — apply always)

- License header on every `.py`: `# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).`
- `_logger = logging.getLogger(__name__)` — never print()
- No bare `except Exception` — catch specific types
- `self.ensure_one()` on single-record methods
- No `attrs=`, no `states=` in XML (Odoo 19)
- `<odoo>` root, never `<openerp>`
- Black 88 chars, isort profile=black
- `_name` + `_description` on every model
- `_check_company_auto = True` on company-scoped models
- `tracking=True` on business-critical fields
