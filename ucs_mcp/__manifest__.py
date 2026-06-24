# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
{
    "name": "UCS MCP Server",
    "version": "19.0.1.7.0",
    "summary": "Connect Claude Code, ChatGPT, Cursor, Gemini and any AI client to Odoo via MCP",
    "description": """
        MCP (Model Context Protocol) server for Odoo 19.
        Exposes 25 tools covering generic CRUD, sales, accounting, inventory, HR, GST, and WhatsApp
        to Claude Code, Claude Desktop, ChatGPT, Cursor, Continue.dev, Gemini CLI, and more.
    """,
    "author": "Uncanny CS",
    "website": "https://github.com/uncannycs/ucs-mcp",
    "license": "LGPL-3",
    "category": "Technical",
    "depends": [
        "base",
        "mail",
        "web",
    ],
    "data": [
        "security/mcp_security.xml",
        "security/ir.model.access.csv",
        "data/mcp_cron.xml",
        "views/mcp_api_key_wizard_views.xml",
        "views/mcp_api_key_views.xml",
        "views/mcp_audit_log_views.xml",
        "views/mcp_portal_templates.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
