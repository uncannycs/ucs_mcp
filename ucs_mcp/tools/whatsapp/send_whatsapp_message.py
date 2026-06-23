# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging

from odoo.exceptions import UserError

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import TOOL_PERM_WRITE

_logger = logging.getLogger(__name__)


@register
class SendWhatsappMessageTool(BaseMcpTool):
    """Send a WhatsApp message via Odoo's Meta Cloud integration. Requires meta_cloud_whatsapp."""

    name = "send_whatsapp_message"
    description = "Send a WhatsApp message to a partner using Odoo's Meta Cloud WhatsApp integration. Requires meta_cloud_whatsapp module."
    required_permission = TOOL_PERM_WRITE
    input_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "default": "whatsapp.message"},
            "partner_id": {"type": "integer", "description": "Recipient partner ID"},
            "body": {"type": "string", "description": "Message text"},
            "template_id": {"type": "integer", "description": "WhatsApp template ID (optional, uses template instead of free-text body)"},
        },
        "required": ["partner_id", "body"],
    }

    def execute(self, params: dict) -> dict:
        """Execute send_whatsapp_message. Checks meta_cloud_whatsapp is installed."""
        wa_mod = self.env["ir.module.module"].sudo().search(
            [("name", "=", "meta_cloud_whatsapp"), ("state", "=", "installed")], limit=1
        )
        if not wa_mod:
            raise UserError("Module meta_cloud_whatsapp is not installed. WhatsApp tools require it.")

        self._require(params, "partner_id", "body")
        partner_id = self._require_int(params, "partner_id")
        partner = self.env["res.partner"].browse(partner_id)
        if not partner.exists():
            raise UserError("Partner %d not found." % partner_id)
        if not partner.mobile and not partner.phone:
            raise UserError("Partner %d has no mobile or phone number." % partner_id)

        vals = {
            "partner_id": partner_id,
            "body": params["body"],
        }
        if params.get("template_id"):
            vals["wa_template_id"] = int(params["template_id"])

        msg = self.env["whatsapp.message"].create(vals)
        msg.button_send()
        _logger.info("MCP send_whatsapp_message: partner=%d msg=%d", partner_id, msg.id)
        return self._serialize({"id": msg.id, "state": msg.state, "partner": partner.name})
