# UCS MCP Server

![Odoo 19](https://img.shields.io/badge/Odoo-19-blueviolet)
![License LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue)
![Author Uncanny CS](https://img.shields.io/badge/Author-Uncanny%20CS-orange)

Expose your Odoo 19 instance to **Claude Code** and **Claude Desktop** via the [Model Context Protocol (MCP)](https://modelcontextprotocol.io). Ask Claude to search records, create invoices, check stock, and more — all through a secure, audited API.

---

## Features

- **23 MCP tools** covering generic CRUD, sales, accounting, inventory, HR, GST, and WhatsApp
- **API key authentication** — SHA-256 hashed, never stored in plain text
- **Per-key permissions** — read / write / create / delete / execute independently toggled
- **Per-key rate limiting** — configurable requests/hour per key
- **Model access control** — whitelist or blocklist models per key
- **System-level blocked models** — `ir.config_parameter`, `ir.rule`, `res.users`, and 9 others always blocked
- **Full audit log** — every tool call recorded with tool, model, status, duration
- **Portal page** — `/mcp/connect` with quick-start config snippets
- **Odoo 19 compatible** — no `attrs=`, no `states=`, uses `fields.Date.to_date()`

---

## Tool Reference (all 23)

| # | Tool | Description | Required Permission |
|---|------|-------------|---------------------|
| 1 | `search_records` | Search any model with domain/limit/fields | read |
| 2 | `search_count` | Count records matching a domain | read |
| 3 | `get_record` | Fetch a single record by ID | read |
| 4 | `get_fields` | Return field definitions for a model | read |
| 5 | `smart_context` | Business context: company, user, date, metrics | read |
| 6 | `create_record` | Create a new record in any model | create |
| 7 | `update_record` | Update fields on an existing record | write |
| 8 | `delete_record` | Archive or permanently delete a record | delete |
| 9 | `execute_method` | Call a method on a model (blocked: unlink/write/create/sudo) | execute |
| 10 | `create_sale_order` | Create a sale order with order lines | create |
| 11 | `confirm_sale_order` | Confirm a draft sale order | write |
| 12 | `get_customer_statement` | Unpaid invoices and total due for a customer | read |
| 13 | `create_invoice` | Create a customer invoice with lines | create |
| 14 | `post_invoice` | Post (validate) a draft invoice | write |
| 15 | `register_payment` | Register and reconcile payment on an invoice | create |
| 16 | `get_account_balance` | Debit/credit/balance for a GL account | read |
| 17 | `get_stock_level` | On-hand, reserved, available qty for a product | read |
| 18 | `create_stock_move` | Create an internal stock transfer | create |
| 19 | `get_employee_list` | List active employees with department/manager | read |
| 20 | `create_leave_request` | Create an employee time-off request | create |
| 21 | `get_gst_summary` | GST output/ITC/net payable for a period *(requires l10n_in)* | read |
| 22 | `validate_gstin` | Validate GSTIN format and decode state/PAN *(requires l10n_in)* | read |
| 23 | `send_whatsapp_message` | Send a WhatsApp message to a partner *(requires meta_cloud_whatsapp)* | write |

---

## Installation

```bash
# From your Odoo addons path
git clone https://github.com/uncannycs/ucs-mcp ucs_mcp
# Add ucs_mcp to your addons path, then:
# Apps → Update App List → Install "UCS MCP Server"
```

**Python dependencies:** none beyond Odoo 19 standard library.

**Optional module dependencies:**
- `l10n_in` — required for GST tools (`get_gst_summary`, `validate_gstin`)
- `meta_cloud_whatsapp` — required for `send_whatsapp_message`

---

## Quick Start

### 1. Generate an API key

Go to **MCP → API Keys → New**, fill in the name, set permissions, save. The plain key is shown **once** — copy it now.

Or via shell/RPC:
```python
record, plain_key = env["mcp.api.key"].generate_key(
    "My Claude Key",
    perm_read=True,
    perm_write=True,
    perm_create=True,
)
print(plain_key)  # save this
```

### 2. Configure Claude Code

Add to `~/.claude/settings.json` (or project `.claude/settings.json`):

```json
{
  "mcpServers": {
    "odoo": {
      "type": "http",
      "url": "http://localhost:8069/mcp/v1",
      "headers": {
        "Authorization": "Bearer ucs_mcp_YOUR_KEY_HERE"
      }
    }
  }
}
```

Verify: `claude mcp list` should show `odoo` as connected.

### 3. Configure Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "odoo": {
      "type": "http",
      "url": "http://localhost:8069/mcp/v1",
      "headers": {
        "Authorization": "Bearer ucs_mcp_YOUR_KEY_HERE"
      }
    }
  }
}
```

Restart Claude Desktop after saving.

### 4. Claude Web (Remote MCP)

1. Open Claude.ai → Settings → Integrations → Add MCP Server
2. URL: `https://your-odoo-domain.com/mcp/v1`
3. Auth header: `Authorization: Bearer ucs_mcp_YOUR_KEY_HERE`
4. Save and reload.

---

## Health Check

```bash
curl http://localhost:8069/mcp/health
# {"status": "ok", "tool_count": 23, ...}
```

---

## Security Model

| Layer | Mechanism |
|-------|-----------|
| Transport | HTTPS (enforce at reverse proxy) |
| Authentication | Bearer token → SHA-256 hash comparison |
| Authorisation | Per-key permission flags (read/write/create/delete/execute) |
| Model access | System blocklist + per-key whitelist/blocklist |
| Rate limiting | Sliding 1-hour window per key |
| Audit | Every call logged to `mcp.audit.log` |
| Record rules | Users see only their own keys (admins bypass) |

**System-blocked models** (always denied, regardless of key permissions):
`ir.config_parameter`, `ir.rule`, `ir.model.access`, `res.users`, `res.groups`,
`ir.module.module`, `ir.model`, `ir.model.fields`, `base.automation`,
`mail.template`, `ir.actions.server`, `ir.cron`

---

## Multi-Tenant

Each key is scoped to a company (`company_id`). The Odoo request runs as the key's `user_id`, so all ORM record rules and company filters apply normally. No `sudo()` is used for actual business operations — only for the authentication lookup and audit logging.

---

## GST Tools Requirements

Install `l10n_in` (India localisation). Both `get_gst_summary` and `validate_gstin` check at runtime and return a clear error if the module is absent.

---

## WhatsApp Tools Requirements

Install `meta_cloud_whatsapp` (Odoo's official Meta Cloud WhatsApp integration). `send_whatsapp_message` checks at runtime.

---

## Support

**Uncanny Consulting Services LLP**
📧 sanjay@uncannycs.com
🌐 https://github.com/uncannycs/ucs-mcp

---

## License

[LGPL-3](https://www.gnu.org/licenses/lgpl-3.0.html) © Uncanny CS
