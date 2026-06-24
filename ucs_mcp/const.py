# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).

SYSTEM_BLOCKED_MODELS = frozenset([
    "ir.config_parameter",
    "ir.rule",
    "ir.model.access",
    "res.users",
    "res.groups",
    "ir.module.module",
    "ir.model",
    "ir.model.fields",
    "base.automation",
    "mail.template",
    "ir.actions.server",
    "ir.cron",
    "mcp.api.key",
    "mcp.audit.log",
])

DANGEROUS_METHODS = frozenset([
    "unlink",
    "write",
    "create",
    "_write",
    "_create",
    "sudo",
    "execute",
    "execute_kw",
    "shell",
    "exec",
    "eval",
    "load",
    "import_data",
    "base_import",
    "_sql_constraints",
])

MCP_ADMIN_GROUP = "ucs_mcp.group_mcp_admin"
MCP_USER_GROUP = "ucs_mcp.group_mcp_user"

DEFAULT_SEARCH_LIMIT = 80
MAX_SEARCH_LIMIT = 500

TOOL_PERM_READ = "read"
TOOL_PERM_WRITE = "write"
TOOL_PERM_CREATE = "create"
TOOL_PERM_DELETE = "delete"
TOOL_PERM_EXECUTE = "execute"
