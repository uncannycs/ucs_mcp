# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("ucs_mcp")
class TestMcpApiKey(TransactionCase):

    def setUp(self):
        super().setUp()
        self.key_model = self.env["mcp.api.key"]

    def _make_key(self, **kwargs):
        """Helper: create a key and return (record, plain_key)."""
        defaults = {"name": "Test Key"}
        defaults.update(kwargs)
        return self.key_model.generate_key(**defaults)

    def test_key_generation_returns_plain_key(self):
        """generate_key returns a non-empty plain key string."""
        record, plain_key = self._make_key()
        self.assertTrue(plain_key)
        self.assertTrue(plain_key.startswith("ucs_mcp_"))
        self.assertIsNotNone(record.id)

    def test_key_hash_stored_not_plain(self):
        """key_hash field stores the SHA-256 hash, not the plain key."""
        record, plain_key = self._make_key()
        self.assertNotEqual(record.key_hash, plain_key)
        self.assertEqual(len(record.key_hash), 64)  # SHA-256 hex

    def test_authenticate_valid_key(self):
        """authenticate() with a valid plain key returns the key record."""
        record, plain_key = self._make_key()
        auth_record = self.key_model.authenticate(plain_key)
        self.assertEqual(auth_record.id, record.id)

    def test_authenticate_invalid_key_raises(self):
        """authenticate() with a wrong key raises AccessError."""
        with self.assertRaises(AccessError):
            self.key_model.authenticate("ucs_mcp_notavalidkey")

    def test_expired_key_raises(self):
        """authenticate() with an expired key raises AccessError."""
        yesterday = fields.Date.today() - timedelta(days=1)
        record, plain_key = self._make_key(expiry_date=yesterday)
        with self.assertRaises(AccessError):
            self.key_model.authenticate(plain_key)

    def test_inactive_key_raises(self):
        """authenticate() with an inactive key raises AccessError."""
        record, plain_key = self._make_key()
        record.active = False
        with self.assertRaises(AccessError):
            self.key_model.authenticate(plain_key)

    def test_rate_limit_enforcement(self):
        """Key exceeding rate_limit raises UserError on next auth."""
        from odoo.exceptions import UserError
        record, plain_key = self._make_key(rate_limit=2)
        # Exhaust the limit
        record.sudo().write({
            "request_count": 2,
            "rate_window_start": fields.Datetime.now(),
        })
        with self.assertRaises(UserError):
            self.key_model.authenticate(plain_key)

    def test_system_blocked_model_denied(self):
        """check_model_access raises AccessError for SYSTEM_BLOCKED_MODELS entries."""
        record, _ = self._make_key()
        with self.assertRaises(AccessError):
            record.check_model_access("ir.config_parameter")

    def test_custom_blocked_model_denied(self):
        """check_model_access raises AccessError for custom blocked models."""
        record, _ = self._make_key()
        record.custom_blocked_models = "sale.order"
        with self.assertRaises(AccessError):
            record.check_model_access("sale.order")

    def test_whitelist_restricts_access(self):
        """check_model_access raises AccessError for models not in allowed_models."""
        record, _ = self._make_key()
        record.allowed_models = "res.partner"
        with self.assertRaises(AccessError):
            record.check_model_access("sale.order")
        # Should NOT raise for allowed model
        record.check_model_access("res.partner")
