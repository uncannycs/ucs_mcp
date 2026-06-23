# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import logging
import re

from odoo.exceptions import UserError

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import TOOL_PERM_READ

_logger = logging.getLogger(__name__)

_GSTIN_PATTERN = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
)


@register
class ValidateGstinTool(BaseMcpTool):
    """Validate a GSTIN number format. Requires l10n_in."""

    name = "validate_gstin"
    description = "Validate the format of a GSTIN (GST Identification Number) and decode its state code and PAN. Requires l10n_in module."
    required_permission = TOOL_PERM_READ
    input_schema = {
        "type": "object",
        "properties": {
            "model": {"type": "string", "default": "res.partner"},
            "gstin": {"type": "string", "description": "15-character GSTIN to validate"},
        },
        "required": ["gstin"],
    }

    def execute(self, params: dict) -> dict:
        """Execute validate_gstin. Checks l10n_in is installed before proceeding."""
        l10n_in = self.env["ir.module.module"].sudo().search(
            [("name", "=", "l10n_in"), ("state", "=", "installed")], limit=1
        )
        if not l10n_in:
            raise UserError("Module l10n_in is not installed. GST tools require the India localisation.")

        self._require(params, "gstin")
        gstin = str(params["gstin"]).strip().upper()
        valid = bool(_GSTIN_PATTERN.match(gstin))

        result = {
            "gstin": gstin,
            "valid": valid,
        }
        if valid:
            result["state_code"] = gstin[:2]
            result["pan"] = gstin[2:12]
            result["entity_code"] = gstin[12]

        return self._serialize(result)
