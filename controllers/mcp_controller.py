# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import json
import logging
from datetime import timedelta

from odoo import fields, http
from odoo.exceptions import AccessError, UserError
from odoo import _
from odoo.http import request, Response

from ..tools.mcp_tool_registry import all_tools, get_tool, get_tools_schema

_logger = logging.getLogger(__name__)

_MCP_VERSION = "2024-11-05"
_SERVER_NAME = "ucs-mcp-odoo"
_SERVER_VERSION = "19.0.1.0.0"


def _json_response(data, status=200):
    """Return a JSON HTTP response."""
    return Response(
        json.dumps(data, default=str, ensure_ascii=False),
        status=status,
        mimetype="application/json",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )


def _mcp_error(code: int, message: str, req_id=None) -> dict:
    """Build a JSON-RPC 2.0 error envelope."""
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": code, "message": message},
    }


def _mcp_result(result, req_id=None) -> dict:
    """Build a JSON-RPC 2.0 result envelope."""
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _authenticate(req):
    """Extract and validate API key from Authorization header or ?key= query param."""
    auth_header = req.httprequest.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        plain_key = auth_header[7:].strip()
    else:
        # Fallback: ?key=<plain_key> in URL (workaround for clients that don't send headers)
        plain_key = req.httprequest.args.get("key", "").strip()
        if not plain_key:
            raise AccessError("Missing or invalid Authorization header. Use 'Bearer <key>'.")
    return req.env["mcp.api.key"].authenticate(plain_key)


def _server_url():
    return request.httprequest.host_url.rstrip("/")


class McpController(http.Controller):

    @http.route("/mcp/health", auth="public", methods=["GET"], csrf=False, type="http")
    def health(self, **kwargs):
        """Return server health and version info."""
        return _json_response({
            "status": "ok",
            "server": _SERVER_NAME,
            "version": _SERVER_VERSION,
            "mcp_version": _MCP_VERSION,
            "tool_count": len(all_tools()),
        })

    # ── Portal routes ────────────────────────────────────────────────

    @http.route("/mcp/connect", auth="public", methods=["GET"], csrf=False, type="http")
    def portal(self, error=None, **kwargs):
        """Smart portal: shows login CTA for guests, key management for authenticated users."""
        is_public = request.env.user._is_public()
        ctx = {
            "server_name": _SERVER_NAME,
            "server_version": _SERVER_VERSION,
            "is_public": is_public,
            "error": error,
            "csrf_token": request.csrf_token(),
            "server_url": _server_url(),
        }
        if not is_public:
            ctx["current_user"] = request.env.user
            ctx["api_keys"] = request.env["mcp.api.key"].search([])
        return request.render("ucs_mcp.portal_mcp_connect", ctx)

    @http.route("/mcp/connect/create", auth="public", methods=["POST"], csrf=False, type="http")
    def portal_create_key(self, key_name="", mcp_server_name="", expiry_days="", perm_write=None,
                          perm_create=None, perm_delete=None, perm_execute=None, **kwargs):
        """Create a new API key from the portal form. Redirects to /mcp/connect if not logged in."""
        if request.env.user._is_public():
            return request.redirect("/web/login?redirect=/mcp/connect")

        key_name = (key_name or "").strip()
        if not key_name:
            return request.redirect("/mcp/connect?error=Key+name+is+required.")

        expiry_date = None
        if expiry_days and str(expiry_days).isdigit():
            expiry_date = fields.Date.today() + timedelta(days=int(expiry_days))

        try:
            rec, plain_key = request.env["mcp.api.key"].sudo().generate_key(
                key_name,
                user_id=request.env.uid,
                expiry_date=expiry_date,
                perm_write=bool(perm_write),
                perm_create=bool(perm_create),
                perm_delete=bool(perm_delete),
                perm_execute=bool(perm_execute),
            )
        except (UserError, AccessError) as exc:
            return request.redirect("/mcp/connect?error=" + str(exc).replace(" ", "+"))

        request.session["mcp_plain_key"] = plain_key
        request.session["mcp_key_name"] = rec.name
        request.session["mcp_server_name"] = (mcp_server_name or "odoo").strip().replace(" ", "-")
        return request.redirect("/mcp/connect/created")

    @http.route("/mcp/connect/created", auth="public", methods=["GET"], csrf=False, type="http")
    def portal_key_created(self, **kwargs):
        """Show the newly created key and ready-to-copy configs for all clients."""
        if request.env.user._is_public():
            return request.redirect("/web/login?redirect=/mcp/connect")

        plain_key = request.session.pop("mcp_plain_key", None)
        key_name = request.session.pop("mcp_key_name", "New Key")
        mcp_server_name = request.session.pop("mcp_server_name", "odoo")
        if not plain_key:
            return request.redirect("/mcp/connect")

        base = _server_url()
        return request.render("ucs_mcp.portal_mcp_key_created", {
            "plain_key": plain_key,
            "key_name": key_name,
            "mcp_server_name": mcp_server_name,
            "mcp_endpoint": base + "/mcp/v1",
        })

    @http.route("/mcp/connect/revoke", auth="public", methods=["POST"], csrf=False, type="http")
    def portal_revoke_key(self, key_id=None, **kwargs):
        """Deactivate an API key from the portal."""
        if request.env.user._is_public():
            return request.redirect("/web/login?redirect=/mcp/connect")
        if key_id:
            key = request.env["mcp.api.key"].browse(int(key_id))
            if key.exists() and key.user_id.id == request.env.uid:
                key.sudo().write({"active": False})
        return request.redirect("/mcp/connect")

    @http.route("/mcp/connect/rotate", auth="public", methods=["POST"], csrf=False, type="http")
    def portal_rotate_key(self, key_id=None, **kwargs):
        """Regenerate (rotate) an API key — old hash replaced, new plain key shown once."""
        if request.env.user._is_public():
            return request.redirect("/web/login?redirect=/mcp/connect")
        if not key_id:
            return request.redirect("/mcp/connect")

        key = request.env["mcp.api.key"].sudo().browse(int(key_id))
        if not key.exists() or key.user_id.id != request.env.uid:
            return request.redirect("/mcp/connect")

        import secrets
        import hashlib
        plain_key = "ucs_mcp_" + secrets.token_urlsafe(32)
        new_hash = hashlib.sha256(plain_key.encode()).hexdigest()
        key.write({
            "key_hash": new_hash,
            "key_prefix": plain_key[:12],
            "use_count": 0,
            "request_count": 0,
            "last_used": False,
            "rate_window_start": False,
        })

        request.session["mcp_plain_key"] = plain_key
        request.session["mcp_key_name"] = key.name + " (regenerated)"
        return request.redirect("/mcp/connect/created")

    @http.route("/mcp/wizard/<int:wizard_id>/download", auth="user", methods=["GET"], csrf=False, type="http")
    def wizard_download_config(self, wizard_id, **kwargs):
        """Download wizard step-2 configs as a plain-text file."""
        wizard = request.env["mcp.api.key.wizard"].browse(wizard_id)
        if not wizard.exists() or not wizard.plain_key:
            return Response("Not found or key already gone.", status=404, mimetype="text/plain")
        lines = [
            "# Odoo MCP Server — Connection Config",
            "# KEEP THIS FILE SECURE — treat like a password",
            "",
            "== YOUR API KEY ==",
            wizard.plain_key or "",
            "",
            "== MCP Endpoint ==",
            wizard.mcp_endpoint or "",
            "",
            "== Claude Code (run in terminal) ==",
            wizard.config_claude or "",
            "",
            "== Cursor IDE (.cursor/mcp.json) ==",
            wizard.config_cursor or "",
            "",
            "== Continue.dev (~/.continue/config.json) ==",
            wizard.config_continue or "",
            "",
            "== Claude Desktop (claude_desktop_config.json) ==",
            wizard.config_desktop or "",
        ]
        content = "\n".join(lines)
        return Response(
            content,
            status=200,
            mimetype="text/plain",
            headers={
                "Content-Disposition": "attachment; filename=odoo-mcp-config.txt",
                "Content-Type": "text/plain; charset=utf-8",
            },
        )

    @http.route("/mcp/v1", auth="public", methods=["GET"], csrf=False, type="http")
    def mcp_endpoint_get(self, **kwargs):
        """SSE endpoint stub — Claude Code probes GET before falling back to POST."""
        return Response(
            "data: {}\n\n",
            status=200,
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Access-Control-Allow-Origin": "*",
            },
        )

    @http.route("/mcp/v1", auth="public", methods=["POST", "OPTIONS"], csrf=False, type="http")
    def mcp_endpoint(self, **kwargs):
        if request.httprequest.method == "OPTIONS":
            return Response("", status=200, headers={
                "Allow": "POST, OPTIONS",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Authorization, Content-Type",
            })
        """Main MCP JSON-RPC 2.0 endpoint."""
        try:
            body = request.httprequest.get_data(as_text=True)
            payload = json.loads(body)
        except Exception:
            return _json_response(_mcp_error(-32700, "Parse error"), status=400)

        req_id = payload.get("id")
        method = payload.get("method", "")
        params = payload.get("params", {})

        # Notifications have no id — return 202 Accepted, do not process further
        if "id" not in payload:
            return Response("", status=202)

        # Authenticate for all methods except initialize
        api_key = None
        if method != "initialize":
            try:
                api_key = _authenticate(request)
            except AccessError as exc:
                return _json_response(
                    _mcp_error(-32001, str(exc), req_id=req_id),
                    status=401,
                )
            except UserError as exc:
                # UserError from _check_rate_limit (AccessError is a subclass, caught above)
                return _json_response(
                    _mcp_error(-32029, str(exc), req_id=req_id),
                    status=429,
                )

        # Route MCP methods
        if method == "initialize":
            return _json_response(_mcp_result({
                "protocolVersion": _MCP_VERSION,
                "serverInfo": {"name": _SERVER_NAME, "version": _SERVER_VERSION},
                "capabilities": {"tools": {}},
            }, req_id=req_id))

        if method == "ping":
            return _json_response(_mcp_result({}, req_id=req_id))

        if method == "tools/list":
            return _json_response(_mcp_result({"tools": get_tools_schema()}, req_id=req_id))

        if method == "tools/call":
            tool_name = params.get("name")
            tool_params = params.get("arguments") or {}
            if not tool_name:
                return _json_response(_mcp_error(-32602, "Missing 'name' in params", req_id=req_id), status=400)

            ToolClass = get_tool(tool_name)
            if ToolClass is None:
                return _json_response(
                    _mcp_error(-32601, "Tool '%s' not found." % tool_name, req_id=req_id),
                    status=404,
                )

            # Run as key owner — ensures record rules + ACLs apply correctly
            user_env = request.env(user=api_key.user_id.id)
            tool = ToolClass(env=user_env, api_key=api_key)
            result = tool.run(tool_params)
            return _json_response(_mcp_result({
                "content": [{"type": "text", "text": json.dumps(result, default=str, ensure_ascii=False)}]
            }, req_id=req_id))

        return _json_response(_mcp_error(-32601, "Method not found: %s" % method, req_id=req_id), status=404)
