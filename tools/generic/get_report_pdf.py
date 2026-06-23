# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
import base64
import logging

from odoo.exceptions import UserError

from ..base import BaseMcpTool
from ..mcp_tool_registry import register
from ...const import TOOL_PERM_READ

_logger = logging.getLogger(__name__)


@register
class GetReportPdfTool(BaseMcpTool):
    """Generate a PDF report for one or more records and return it as base64."""

    name = "get_report_pdf"
    description = (
        "Generate a PDF report (e.g. invoice, sale order, delivery slip) for given record IDs. "
        "Returns the PDF as a base64-encoded string. "
        "Use get_fields or smart_context to discover available report XML IDs."
    )
    required_permission = TOOL_PERM_READ
    input_schema = {
        "type": "object",
        "properties": {
            "report_xmlid": {
                "type": "string",
                "description": (
                    "XML ID of the report action, e.g. 'account.account_invoices', "
                    "'sale.action_report_saleorder', 'stock.action_report_delivery'."
                ),
            },
            "record_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "List of record IDs to include in the PDF.",
            },
        },
        "required": ["report_xmlid", "record_ids"],
    }

    def execute(self, params: dict) -> dict:
        self._require(params, "report_xmlid", "record_ids")
        report_xmlid = params["report_xmlid"]
        record_ids = params["record_ids"]

        if not isinstance(record_ids, list) or not record_ids:
            raise UserError("'record_ids' must be a non-empty list of integers.")

        report = self.env.ref(report_xmlid, raise_if_not_found=False)
        if not report:
            raise UserError("Report '%s' not found. Check the XML ID." % report_xmlid)

        # sudo() needed: report rendering may require elevated access for certain models
        pdf_content, _mime = report.sudo()._render_qweb_pdf(record_ids)
        pdf_b64 = base64.b64encode(pdf_content).decode("ascii")
        size_kb = len(pdf_content) // 1024

        _logger.info(
            "MCP get_report_pdf: report=%s ids=%s size=%dkB",
            report_xmlid, record_ids, size_kb,
        )
        return self._serialize({
            "report_xmlid": report_xmlid,
            "record_ids": record_ids,
            "pdf_base64": pdf_b64,
            "size_kb": size_kb,
            "filename": "%s_%s.pdf" % (report_xmlid.split(".")[-1], "_".join(str(i) for i in record_ids)),
        })
