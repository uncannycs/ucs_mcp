# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
{
    "name": "UCS MCP Server",
    "version": "19.0.1.1.0",
    "summary": "Expose Odoo to Claude Code / Claude Desktop via the Model Context Protocol",
    "description": """
        MCP (Model Context Protocol) server for Odoo 19.
        Allows Claude Code and Claude Desktop to query and update Odoo via 23 tools
        covering generic CRUD, sales, accounting, inventory, HR, GST, and WhatsApp.
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
