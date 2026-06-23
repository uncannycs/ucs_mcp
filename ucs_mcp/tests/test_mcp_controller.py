# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import json
import logging

from odoo.tests.common import HttpCase, tagged

_logger = logging.getLogger(__name__)


@tagged("ucs_mcp", "post_install")
class TestMcpController(HttpCase):

    def setUp(self):
        super().setUp()
        record, self.plain_key = self.env["mcp.api.key"].generate_key(
            "HTTP Test Key",
            perm_read=True,
            perm_write=True,
            perm_create=True,
            perm_delete=True,
            perm_execute=True,
        )
        self.api_key = record

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": "Bearer %s" % self.plain_key,
        }

    def _post(self, payload, headers=None):
        resp = self.url_open(
            "/mcp/v1",
            data=json.dumps(payload).encode(),
            headers=headers or self._headers(),
        )
        return resp, json.loads(resp.content)

    def _post_key_param(self, payload):
        """POST using ?key= query param instead of Authorization header."""
        resp = self.url_open(
            "/mcp/v1?key=%s" % self.plain_key,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        return resp, json.loads(resp.content)

    # ── health ────────────────────────────────────────────────────────────────

    def test_health_endpoint_returns_ok(self):
        """GET /mcp/health returns status=ok and 200."""
        resp = self.url_open("/mcp/health")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data["status"], "ok")
        self.assertIn("tool_count", data)

    def test_health_tool_count_at_least_25(self):
        """tool_count in /mcp/health reflects all 25 registered tools."""
        resp = self.url_open("/mcp/health")
        data = json.loads(resp.content)
        self.assertGreaterEqual(data["tool_count"], 25)

    # ── authentication ────────────────────────────────────────────────────────

    def test_mcp_endpoint_without_auth_returns_401(self):
        """POST /mcp/v1 without auth returns JSON-RPC error -32001."""
        resp, data = self._post(
            {"jsonrpc": "2.0", "method": "tools/list", "id": 1},
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(data["error"]["code"], -32001)

    def test_mcp_endpoint_with_bearer_header_works(self):
        """Bearer token auth in Authorization header works."""
        _, data = self._post({"jsonrpc": "2.0", "method": "tools/list", "id": 2})
        self.assertIn("result", data)
        self.assertNotIn("error", data)

    def test_mcp_endpoint_with_key_query_param_works(self):
        """?key= query param auth works (used by ChatGPT / Claude Code shorthand)."""
        _, data = self._post_key_param({"jsonrpc": "2.0", "method": "tools/list", "id": 10})
        self.assertIn("result", data)
        self.assertNotIn("error", data)

    def test_mcp_endpoint_with_invalid_key_query_param_returns_401(self):
        """?key= with wrong key returns -32001."""
        resp = self.url_open(
            "/mcp/v1?key=ucs_mcp_totallywrong",
            data=json.dumps({"jsonrpc": "2.0", "method": "tools/list", "id": 11}).encode(),
            headers={"Content-Type": "application/json"},
        )
        data = json.loads(resp.content)
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(data["error"]["code"], -32001)

    def test_mcp_endpoint_with_invalid_bearer_returns_401(self):
        """Wrong bearer token returns -32001."""
        resp, data = self._post(
            {"jsonrpc": "2.0", "method": "tools/list", "id": 12},
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer ucs_mcp_invalidkey",
            },
        )
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(data["error"]["code"], -32001)

    # ── tools/list ────────────────────────────────────────────────────────────

    def test_tools_list_returns_all_tools(self):
        """tools/list returns at least 25 tools."""
        _, data = self._post({"jsonrpc": "2.0", "method": "tools/list", "id": 3})
        tools = data["result"]["tools"]
        self.assertGreaterEqual(len(tools), 25)
        names = [t["name"] for t in tools]
        for expected in ("search_records", "smart_context", "read_group", "get_report_pdf"):
            self.assertIn(expected, names, "Missing tool: %s" % expected)

    def test_tools_list_each_tool_has_schema(self):
        """Every tool in tools/list has name, description, and inputSchema."""
        _, data = self._post({"jsonrpc": "2.0", "method": "tools/list", "id": 13})
        for tool in data["result"]["tools"]:
            self.assertIn("name", tool)
            self.assertIn("description", tool)
            self.assertIn("inputSchema", tool)

    # ── tools/call ────────────────────────────────────────────────────────────

    def test_tools_call_search_records(self):
        """tools/call search_records returns success result."""
        _, data = self._post({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 4,
            "params": {
                "name": "search_records",
                "arguments": {"model": "res.partner", "domain": [], "limit": 3},
            },
        })
        self.assertIn("result", data)
        content = json.loads(data["result"]["content"][0]["text"])
        self.assertTrue(content.get("success"))

    def test_tools_call_read_group_via_http(self):
        """tools/call read_group via HTTP returns grouped rows."""
        _, data = self._post({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 20,
            "params": {
                "name": "read_group",
                "arguments": {
                    "model": "res.partner",
                    "domain": [],
                    "groupby": ["country_id"],
                    "aggregates": ["id:count"],
                    "limit": 5,
                },
            },
        })
        self.assertIn("result", data)
        content = json.loads(data["result"]["content"][0]["text"])
        self.assertTrue(content.get("success"), content)
        self.assertIn("rows", content["data"])

    def test_tools_call_read_group_key_param_auth(self):
        """tools/call read_group works via ?key= auth."""
        _, data = self._post_key_param({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 21,
            "params": {
                "name": "read_group",
                "arguments": {"model": "res.partner", "domain": [], "groupby": ["country_id"]},
            },
        })
        content = json.loads(data["result"]["content"][0]["text"])
        self.assertTrue(content.get("success"))

    def test_tools_call_get_report_pdf_bad_xmlid_returns_error(self):
        """tools/call get_report_pdf with invalid XML ID returns tool-level error, not 500."""
        _, data = self._post({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 22,
            "params": {
                "name": "get_report_pdf",
                "arguments": {
                    "report_xmlid": "nonexistent.bad_report",
                    "record_ids": [1],
                },
            },
        })
        self.assertIn("result", data)
        content = json.loads(data["result"]["content"][0]["text"])
        self.assertFalse(content.get("success"))

    def test_tools_call_create_record_via_http(self):
        """tools/call create_record via HTTP creates a partner and returns its ID."""
        _, data = self._post({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 30,
            "params": {
                "name": "create_record",
                "arguments": {
                    "model": "res.partner",
                    "values": {"name": "HTTP Create Test Partner"},
                },
            },
        })
        self.assertIn("result", data)
        content = json.loads(data["result"]["content"][0]["text"])
        self.assertTrue(content.get("success"))
        self.assertIsInstance(content["data"]["id"], int)

    def test_tools_call_update_record_via_http(self):
        """tools/call update_record via HTTP updates a partner."""
        partner = self.env["res.partner"].create({"name": "HTTP Update Test"})
        _, data = self._post({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 31,
            "params": {
                "name": "update_record",
                "arguments": {
                    "model": "res.partner",
                    "id": partner.id,
                    "values": {"name": "HTTP Updated"},
                },
            },
        })
        content = json.loads(data["result"]["content"][0]["text"])
        self.assertTrue(content.get("success"))
        self.assertEqual(partner.name, "HTTP Updated")

    def test_tools_call_blocked_model_denied_via_http(self):
        """tools/call on blocked model returns success=False in content (not HTTP 500)."""
        _, data = self._post({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 32,
            "params": {
                "name": "search_records",
                "arguments": {"model": "ir.config_parameter", "domain": []},
            },
        })
        content = json.loads(data["result"]["content"][0]["text"])
        self.assertFalse(content.get("success"))

    # ── protocol ─────────────────────────────────────────────────────────────

    def test_ping_returns_empty_result(self):
        """ping method returns empty result object per MCP spec."""
        _, data = self._post({"jsonrpc": "2.0", "method": "ping", "id": 6})
        self.assertIn("result", data)
        self.assertEqual(data["result"], {})

    def test_unknown_method_returns_method_not_found(self):
        """Unknown JSON-RPC method returns -32601."""
        _, data = self._post({"jsonrpc": "2.0", "method": "unknown/method", "id": 7})
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], -32601)

    def test_tools_call_unknown_tool_returns_error(self):
        """tools/call with unknown tool name returns JSON-RPC -32601 error."""
        resp, data = self._post({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "id": 5,
            "params": {"name": "nonexistent_tool", "arguments": {}},
        })
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(data["error"]["code"], -32601)

    def test_malformed_json_returns_parse_error(self):
        """Malformed JSON body returns -32700 parse error."""
        resp = self.url_open(
            "/mcp/v1",
            data=b"{not valid json",
            headers=self._headers(),
        )
        data = json.loads(resp.content)
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], -32700)
