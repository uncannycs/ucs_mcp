# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("ucs_mcp")
class TestGenericTools(TransactionCase):

    def setUp(self):
        super().setUp()
        record, self.plain_key = self.env["mcp.api.key"].generate_key(
            "Test Key",
            perm_read=True,
            perm_write=True,
            perm_create=True,
            perm_delete=True,
            perm_execute=True,
        )
        self.api_key = record

    def _tool(self, tool_name):
        from odoo.addons.ucs_mcp.tools.mcp_tool_registry import get_tool
        ToolClass = get_tool(tool_name)
        self.assertIsNotNone(ToolClass, "Tool '%s' not registered." % tool_name)
        return ToolClass(env=self.env, api_key=self.api_key)

    def _readonly_key(self):
        record, _ = self.env["mcp.api.key"].generate_key(
            "Read-only Key",
            perm_read=True,
            perm_write=False,
            perm_create=False,
            perm_delete=False,
            perm_execute=False,
        )
        return record

    # ── search_records ────────────────────────────────────────────────────────

    def test_search_records_basic(self):
        tool = self._tool("search_records")
        result = tool.run({"model": "res.partner", "domain": [], "limit": 5})
        self.assertTrue(result.get("success"))
        self.assertIn("records", result["data"])

    def test_search_records_respects_limit(self):
        tool = self._tool("search_records")
        result = tool.run({"model": "res.partner", "domain": [], "limit": 2})
        self.assertTrue(result.get("success"))
        self.assertLessEqual(len(result["data"]["records"]), 2)

    def test_search_records_blocked_model_raises(self):
        tool = self._tool("search_records")
        result = tool.run({"model": "ir.config_parameter", "domain": []})
        self.assertFalse(result.get("success"))

    def test_search_records_with_domain_filter(self):
        self.env["res.partner"].create({"name": "MCP Filter Test Partner"})
        tool = self._tool("search_records")
        result = tool.run({
            "model": "res.partner",
            "domain": [["name", "=", "MCP Filter Test Partner"]],
            "limit": 5,
        })
        self.assertTrue(result.get("success"))
        names = [r["name"] for r in result["data"]["records"]]
        self.assertIn("MCP Filter Test Partner", names)

    def test_search_records_with_fields_subset(self):
        tool = self._tool("search_records")
        result = tool.run({
            "model": "res.partner",
            "domain": [],
            "fields": ["name", "email"],
            "limit": 3,
        })
        self.assertTrue(result.get("success"))
        for rec in result["data"]["records"]:
            self.assertIn("name", rec)
            self.assertNotIn("phone", rec)

    # ── search_count ──────────────────────────────────────────────────────────

    def test_search_count_returns_integer(self):
        tool = self._tool("search_count")
        result = tool.run({"model": "res.partner", "domain": []})
        self.assertTrue(result.get("success"))
        self.assertIsInstance(result["data"]["count"], int)
        self.assertGreater(result["data"]["count"], 0)

    # ── get_record ────────────────────────────────────────────────────────────

    def test_get_record_returns_fields(self):
        partner = self.env["res.partner"].create({"name": "Get Record Test"})
        tool = self._tool("get_record")
        result = tool.run({"model": "res.partner", "id": partner.id})
        self.assertTrue(result.get("success"))
        self.assertEqual(result["data"]["record"]["name"], "Get Record Test")

    def test_get_record_nonexistent_returns_error(self):
        tool = self._tool("get_record")
        result = tool.run({"model": "res.partner", "id": 9999999})
        self.assertFalse(result.get("success"))

    # ── create_record ─────────────────────────────────────────────────────────

    def test_create_record_success(self):
        tool = self._tool("create_record")
        result = tool.run({
            "model": "res.partner",
            "values": {"name": "MCP Test Partner %d" % self.env.uid},
        })
        self.assertTrue(result.get("success"))
        self.assertIsInstance(result["data"]["id"], int)

    def test_create_record_without_permission_raises(self):
        from odoo.addons.ucs_mcp.tools.mcp_tool_registry import get_tool
        ro_key = self._readonly_key()
        ToolClass = get_tool("create_record")
        tool = ToolClass(env=self.env, api_key=ro_key)
        result = tool.run({"model": "res.partner", "values": {"name": "Should Fail"}})
        self.assertFalse(result.get("success"))

    def test_create_record_posts_chatter_note(self):
        """create_record posts robot chatter note on mail.thread models."""
        partner = None
        tool = self._tool("create_record")
        result = tool.run({
            "model": "res.partner",
            "values": {"name": "Chatter Test Partner"},
        })
        self.assertTrue(result.get("success"))
        partner = self.env["res.partner"].browse(result["data"]["id"])
        messages = partner.message_ids.filtered(lambda m: "AI Assistant" in (m.body or ""))
        self.assertTrue(messages, "Expected chatter note from AI Assistant on created partner.")

    def test_create_record_chatter_silent_on_non_mail_model(self):
        """create_record must not crash on models without mail.thread."""
        tool = self._tool("create_record")
        result = tool.run({
            "model": "res.lang",
            "values": {"name": "Test Lang XX", "code": "xx_XX", "iso_code": "xx"},
        })
        # May succeed or fail depending on model constraints — must NOT raise
        self.assertIn("success", result)

    # ── update_record ─────────────────────────────────────────────────────────

    def test_update_record_success(self):
        partner = self.env["res.partner"].create({"name": "Update Test"})
        tool = self._tool("update_record")
        result = tool.run({
            "model": "res.partner",
            "id": partner.id,
            "values": {"name": "Updated"},
        })
        self.assertTrue(result.get("success"))
        self.assertIn("name", result["data"]["updated_fields"])
        self.assertEqual(partner.name, "Updated")

    def test_update_record_posts_chatter_note(self):
        partner = self.env["res.partner"].create({"name": "Update Chatter Test"})
        tool = self._tool("update_record")
        tool.run({"model": "res.partner", "id": partner.id, "values": {"phone": "1234567890"}})
        messages = partner.message_ids.filtered(lambda m: "AI Assistant" in (m.body or ""))
        self.assertTrue(messages, "Expected chatter note from AI Assistant on update.")

    def test_update_record_nonexistent_returns_error(self):
        tool = self._tool("update_record")
        result = tool.run({"model": "res.partner", "id": 9999999, "values": {"name": "X"}})
        self.assertFalse(result.get("success"))

    # ── delete_record ─────────────────────────────────────────────────────────

    def test_delete_record_soft_delete_if_active_field(self):
        partner = self.env["res.partner"].create({"name": "Archive Me"})
        tool = self._tool("delete_record")
        result = tool.run({"model": "res.partner", "id": partner.id})
        self.assertTrue(result.get("success"))
        self.assertEqual(result["data"]["action"], "archived")
        self.assertFalse(partner.active)

    def test_delete_record_requires_delete_permission(self):
        from odoo.addons.ucs_mcp.tools.mcp_tool_registry import get_tool
        ro_key = self._readonly_key()
        partner = self.env["res.partner"].create({"name": "No Delete"})
        ToolClass = get_tool("delete_record")
        tool = ToolClass(env=self.env, api_key=ro_key)
        result = tool.run({"model": "res.partner", "id": partner.id})
        self.assertFalse(result.get("success"))

    def test_delete_record_posts_chatter_before_archive(self):
        partner = self.env["res.partner"].create({"name": "Delete Chatter Test"})
        tool = self._tool("delete_record")
        tool.run({"model": "res.partner", "id": partner.id})
        # After archive, fetch messages with active_test=False
        partner_all = self.env["res.partner"].with_context(active_test=False).browse(partner.id)
        messages = partner_all.message_ids.filtered(lambda m: "AI Assistant" in (m.body or ""))
        self.assertTrue(messages, "Expected chatter note before archive.")

    # ── execute_method ────────────────────────────────────────────────────────

    def test_execute_method_blocked_method_raises(self):
        tool = self._tool("execute_method")
        result = tool.run({"model": "res.partner", "method": "unlink", "ids": []})
        self.assertFalse(result.get("success"))

    # ── get_fields ────────────────────────────────────────────────────────────

    def test_get_fields_returns_field_definitions(self):
        tool = self._tool("get_fields")
        result = tool.run({"model": "res.partner"})
        self.assertTrue(result.get("success"))
        fields_data = result["data"]["fields"]
        self.assertIn("name", fields_data)
        self.assertIn("email", fields_data)

    # ── smart_context ─────────────────────────────────────────────────────────

    def test_smart_context_returns_required_keys(self):
        tool = self._tool("smart_context")
        result = tool.run({})
        self.assertTrue(result.get("success"))
        data = result["data"]
        for key in ("company", "user", "date", "currency"):
            self.assertIn(key, data, "smart_context missing key: %s" % key)

    # ── read_group ────────────────────────────────────────────────────────────

    def test_read_group_count_by_partner_country(self):
        """read_group groups partners by country_id and counts them."""
        tool = self._tool("read_group")
        result = tool.run({
            "model": "res.partner",
            "domain": [],
            "groupby": ["country_id"],
            "aggregates": ["id:count"],
        })
        self.assertTrue(result.get("success"), result)
        rows = result["data"]["rows"]
        self.assertIsInstance(rows, list)
        # Each row must contain the groupby field
        for row in rows:
            self.assertIn("country_id", row)

    def test_read_group_backward_compat_fields_param(self):
        """read_group accepts legacy 'fields' param as alias for 'aggregates'."""
        tool = self._tool("read_group")
        result = tool.run({
            "model": "res.partner",
            "domain": [],
            "groupby": ["country_id"],
            "fields": ["id:count"],
        })
        self.assertTrue(result.get("success"), result)

    def test_read_group_requires_groupby(self):
        """read_group with empty groupby returns error."""
        tool = self._tool("read_group")
        result = tool.run({"model": "res.partner", "domain": [], "groupby": []})
        self.assertFalse(result.get("success"))

    def test_read_group_respects_limit(self):
        """read_group limit caps number of rows returned."""
        tool = self._tool("read_group")
        result = tool.run({
            "model": "res.partner",
            "domain": [],
            "groupby": ["country_id"],
            "limit": 2,
        })
        self.assertTrue(result.get("success"))
        self.assertLessEqual(len(result["data"]["rows"]), 2)

    def test_read_group_blocked_model_denied(self):
        """read_group on blocked model returns success=False."""
        tool = self._tool("read_group")
        result = tool.run({
            "model": "ir.config_parameter",
            "domain": [],
            "groupby": ["key"],
        })
        self.assertFalse(result.get("success"))

    def test_read_group_read_only_key_allowed(self):
        """read_group works with read-only key (it's a read operation)."""
        from odoo.addons.ucs_mcp.tools.mcp_tool_registry import get_tool
        ro_key = self._readonly_key()
        ToolClass = get_tool("read_group")
        tool = ToolClass(env=self.env, api_key=ro_key)
        result = tool.run({
            "model": "res.partner",
            "domain": [],
            "groupby": ["country_id"],
        })
        self.assertTrue(result.get("success"))

    # ── get_report_pdf ────────────────────────────────────────────────────────

    def test_get_report_pdf_invalid_xmlid_returns_error(self):
        """get_report_pdf with non-existent XML ID returns success=False."""
        tool = self._tool("get_report_pdf")
        result = tool.run({
            "report_xmlid": "nonexistent.report_does_not_exist",
            "record_ids": [1],
        })
        self.assertFalse(result.get("success"))

    def test_get_report_pdf_empty_record_ids_returns_error(self):
        """get_report_pdf with empty record_ids returns success=False."""
        tool = self._tool("get_report_pdf")
        result = tool.run({
            "report_xmlid": "base.action_res_partner_tree",
            "record_ids": [],
        })
        self.assertFalse(result.get("success"))

    def test_get_report_pdf_read_only_key_allowed(self):
        """get_report_pdf is a read tool — works with read-only key (fails on report lookup, not perms)."""
        from odoo.addons.ucs_mcp.tools.mcp_tool_registry import get_tool
        ro_key = self._readonly_key()
        ToolClass = get_tool("get_report_pdf")
        tool = ToolClass(env=self.env, api_key=ro_key)
        # Will fail because xmlid is fake — but must NOT fail with permission denied
        result = tool.run({
            "report_xmlid": "nonexistent.fake_report",
            "record_ids": [1],
        })
        # success=False is expected (bad xmlid), but error must NOT say "permission"
        self.assertFalse(result.get("success"))
        self.assertNotIn("permission", (result.get("error") or "").lower())

    # ── audit log IP capture ──────────────────────────────────────────────────

    def test_audit_log_created_on_tool_run(self):
        """Every tool.run() creates an audit log entry."""
        before_count = self.env["mcp.audit.log"].search_count([
            ("api_key_id", "=", self.api_key.id),
        ])
        tool = self._tool("search_records")
        tool.run({"model": "res.partner", "domain": [], "limit": 1})
        after_count = self.env["mcp.audit.log"].search_count([
            ("api_key_id", "=", self.api_key.id),
        ])
        self.assertEqual(after_count, before_count + 1)

    def test_audit_log_has_ip_address_field(self):
        """mcp.audit.log model has ip_address field."""
        log_model = self.env["mcp.audit.log"]
        self.assertIn("ip_address", log_model._fields)

    def test_audit_log_status_error_on_failed_tool(self):
        """Blocked tool run logs status=denied in audit log."""
        tool = self._tool("search_records")
        tool.run({"model": "ir.config_parameter", "domain": []})
        log = self.env["mcp.audit.log"].search([
            ("api_key_id", "=", self.api_key.id),
            ("model_name", "=", "ir.config_parameter"),
        ], limit=1, order="id desc")
        self.assertTrue(log)
        self.assertEqual(log.status, "denied")

    # ── wizard step2_html and mcp_server_name ─────────────────────────────────

    def test_wizard_step2_html_empty_without_plain_key(self):
        """step2_html is falsy before key is generated."""
        wizard = self.env["mcp.api.key.wizard"].create({"name": "Test", "mcp_server_name": "odoo"})
        self.assertFalse(wizard.step2_html)

    def test_wizard_step2_html_populated_after_generate(self):
        """step2_html contains HTML cards after action_generate."""
        wizard = self.env["mcp.api.key.wizard"].create({
            "name": "Wizard Test",
            "mcp_server_name": "test-erp",
        })
        wizard.action_generate()
        self.assertTrue(wizard.step2_html)
        self.assertIn("Claude Code", wizard.step2_html)
        self.assertIn("ChatGPT", wizard.step2_html)
        self.assertIn("Zed", wizard.step2_html)
        self.assertIn("Continue.dev", wizard.step2_html)

    def test_wizard_mcp_server_name_in_configs(self):
        """Custom mcp_server_name appears in all generated configs."""
        wizard = self.env["mcp.api.key.wizard"].create({
            "name": "Custom Name Test",
            "mcp_server_name": "my-custom-erp",
        })
        wizard.action_generate()
        self.assertIn("my-custom-erp", wizard.config_claude or "")
        self.assertIn("my-custom-erp", wizard.config_cursor or "")
        self.assertIn("my-custom-erp", wizard.config_desktop or "")
        self.assertIn("my-custom-erp", wizard.step2_html or "")

    def test_wizard_zed_config_in_step2_html(self):
        """Zed card in step2_html contains mcp-remote and mcp_server_name."""
        wizard = self.env["mcp.api.key.wizard"].create({
            "name": "Zed Test",
            "mcp_server_name": "zed-test",
        })
        wizard.action_generate()
        html = wizard.step2_html or ""
        self.assertIn("mcp-remote", html)
        self.assertIn("zed-test", html)

    def test_wizard_chatgpt_card_contains_endpoint_url(self):
        """ChatGPT card in step2_html shows endpoint URL with key embedded."""
        wizard = self.env["mcp.api.key.wizard"].create({
            "name": "ChatGPT Test",
            "mcp_server_name": "odoo",
        })
        wizard.action_generate()
        html = wizard.step2_html or ""
        self.assertIn("mcp/v1", html)
        self.assertIn("?key=", html)

    def test_wizard_endpoint_uses_mcp_endpoint_field(self):
        """mcp_endpoint is set after generate and matches base URL pattern."""
        wizard = self.env["mcp.api.key.wizard"].create({
            "name": "Endpoint Test",
            "mcp_server_name": "odoo",
        })
        wizard.action_generate()
        self.assertTrue(wizard.mcp_endpoint)
        self.assertIn("/mcp/v1", wizard.mcp_endpoint)
