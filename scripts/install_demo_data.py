#!/usr/bin/env python3
# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
"""
UCS MCP Demo Data Installer
============================
Creates realistic demo records across several Odoo models so you can
test every MCP tool against real data on a fresh odoo.sh instance.

Usage (run from the Odoo workspace root):

    python3 19.0/odoo-bin shell -c <conf> -d <db> \
        < ucs-erp/ucs_mcp/scripts/install_demo_data.py

Or interactively in Odoo shell:

    exec(open('ucs-erp/ucs_mcp/scripts/install_demo_data.py').read())
"""
import logging

_logger = logging.getLogger("ucs_mcp.demo")


def _section(title):
    _logger.info("=" * 60)
    _logger.info("  %s", title)
    _logger.info("=" * 60)


# ── 1. Partners ──────────────────────────────────────────────────────────────

_section("Partners")

countries = env["res.country"].search([("name", "in", ["India", "United States", "United Arab Emirates"])])
country_map = {c.name: c.id for c in countries}

PARTNERS = [
    {"name": "Acme Corp",         "email": "contact@acme.example",    "phone": "+1-555-0100", "is_company": True,  "country_id": country_map.get("United States")},
    {"name": "Gulf Traders LLC",  "email": "info@gulftraders.example", "phone": "+971-4-0000001", "is_company": True,  "country_id": country_map.get("United Arab Emirates")},
    {"name": "Sigma Solutions",   "email": "sigma@sigma.example",      "phone": "+91-98765-43210", "is_company": True,  "country_id": country_map.get("India")},
    {"name": "John Doe",          "email": "john.doe@example.com",     "phone": "+1-555-0200", "is_company": False},
    {"name": "Priya Sharma",      "email": "priya@example.in",         "phone": "+91-99000-11111", "is_company": False},
    {"name": "Mohammed Al Farsi", "email": "mfarsi@example.ae",        "phone": "+971-50-1234567", "is_company": False},
    {"name": "TechStart Inc",     "email": "hello@techstart.example",  "phone": "+1-555-0300", "is_company": True},
    {"name": "Retail World",      "email": "buy@retailworld.example",  "phone": "+91-80-12345678", "is_company": True,  "country_id": country_map.get("India")},
]

created_partners = []
for vals in PARTNERS:
    existing = env["res.partner"].search([("email", "=", vals["email"])], limit=1)
    if existing:
        created_partners.append(existing)
        _logger.info("  skip (exists): %s", vals["name"])
    else:
        p = env["res.partner"].create(vals)
        created_partners.append(p)
        _logger.info("  created: %s (id=%d)", p.name, p.id)

env.cr.commit()
_logger.info("Partners done: %d total", len(created_partners))


# ── 2. Products ───────────────────────────────────────────────────────────────

_section("Products")

uom_unit = env.ref("uom.product_uom_unit", raise_if_not_found=False)
uom_id = uom_unit.id if uom_unit else None

PRODUCTS = [
    {"name": "MCP Demo Widget",       "list_price": 150.00,   "standard_price": 80.00,   "type": "consu"},
    {"name": "MCP Demo Service Pack", "list_price": 500.00,   "standard_price": 200.00,  "type": "service"},
    {"name": "MCP Demo Laptop",       "list_price": 1200.00,  "standard_price": 900.00,  "type": "consu"},
    {"name": "MCP Demo Keyboard",     "list_price": 75.00,    "standard_price": 40.00,   "type": "consu"},
    {"name": "MCP Demo Consulting",   "list_price": 200.00,   "standard_price": 100.00,  "type": "service"},
]

created_products = []
for vals in PRODUCTS:
    if uom_id:
        vals["uom_id"] = uom_id
        vals["uom_po_id"] = uom_id
    existing = env["product.template"].search([("name", "=", vals["name"])], limit=1)
    if existing:
        created_products.append(existing.product_variant_ids[:1])
        _logger.info("  skip (exists): %s", vals["name"])
    else:
        tmpl = env["product.template"].create(vals)
        created_products.append(tmpl.product_variant_ids[:1])
        _logger.info("  created: %s (id=%d)", tmpl.name, tmpl.id)

env.cr.commit()
_logger.info("Products done: %d total", len(created_products))


# ── 3. Sales Orders (if sale module installed) ────────────────────────────────

_section("Sales Orders")

if "sale.order" in env:
    company = env.company
    company_partners = [p for p in created_partners if p.is_company]
    ORDERS = [
        {"partner": company_partners[0] if len(company_partners) > 0 else created_partners[0], "lines": [(created_products[0], 3, 150.00), (created_products[3], 2, 75.00)]},
        {"partner": company_partners[1] if len(company_partners) > 1 else created_partners[1], "lines": [(created_products[1], 1, 500.00), (created_products[4], 5, 200.00)]},
        {"partner": company_partners[2] if len(company_partners) > 2 else created_partners[2], "lines": [(created_products[2], 1, 1200.00)]},
    ]
    created_orders = []
    for order_data in ORDERS:
        partner = order_data["partner"]
        order_lines = []
        for product, qty, price in order_data["lines"]:
            if product:
                order_lines.append((0, 0, {
                    "product_id": product.id,
                    "product_uom_qty": qty,
                    "price_unit": price,
                }))
        if not order_lines:
            continue
        so = env["sale.order"].create({
            "partner_id": partner.id,
            "order_line": order_lines,
        })
        created_orders.append(so)
        _logger.info("  created SO: %s (id=%d, partner=%s)", so.name, so.id, partner.name)

    # Confirm first two orders so we have invoiceable orders
    for so in created_orders[:2]:
        try:
            so.action_confirm()
            _logger.info("  confirmed: %s", so.name)
        except Exception as exc:
            _logger.warning("  could not confirm %s: %s", so.name, exc)

    env.cr.commit()
    _logger.info("Sales Orders done: %d created", len(created_orders))
else:
    _logger.info("  sale module not installed — skipping")
    created_orders = []


# ── 4. Invoices (if account module installed) ─────────────────────────────────

_section("Invoices")

if "account.move" in env:
    invoice_partners = [p for p in created_partners if p.is_company][:3]
    created_invoices = []
    for i, partner in enumerate(invoice_partners):
        inv_lines = []
        if created_products:
            product = created_products[i % len(created_products)]
            if product:
                inv_lines.append((0, 0, {
                    "product_id": product.id,
                    "quantity": (i + 1) * 2,
                    "price_unit": [150.00, 500.00, 1200.00][i % 3],
                    "name": product.name or "Demo Invoice Line",
                }))
        if not inv_lines:
            inv_lines.append((0, 0, {
                "name": "Demo Service Line %d" % (i + 1),
                "quantity": 1,
                "price_unit": 250.00 * (i + 1),
            }))
        try:
            inv = env["account.move"].create({
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_line_ids": inv_lines,
            })
            created_invoices.append(inv)
            _logger.info("  created invoice: %s (id=%d, partner=%s)", inv.name, inv.id, partner.name)
        except Exception as exc:
            _logger.warning("  could not create invoice for %s: %s", partner.name, exc)

    # Post first invoice so there's at least one confirmed invoice to report on
    if created_invoices:
        try:
            created_invoices[0].action_post()
            _logger.info("  posted: %s", created_invoices[0].name)
        except Exception as exc:
            _logger.warning("  could not post invoice: %s", exc)

    env.cr.commit()
    _logger.info("Invoices done: %d created", len(created_invoices))
else:
    _logger.info("  account module not installed — skipping")
    created_invoices = []


# ── 5. MCP API Keys ───────────────────────────────────────────────────────────

_section("MCP API Keys")

KEY_CONFIGS = [
    {
        "name": "Demo Full Access Key",
        "perm_read": True, "perm_write": True, "perm_create": True,
        "perm_delete": True, "perm_execute": True, "rate_limit": 500,
    },
    {
        "name": "Demo Read-Only Key",
        "perm_read": True, "perm_write": False, "perm_create": False,
        "perm_delete": False, "perm_execute": False, "rate_limit": 200,
    },
    {
        "name": "Demo Sales Key",
        "perm_read": True, "perm_write": True, "perm_create": True,
        "perm_delete": False, "perm_execute": False,
        "allowed_models": "sale.order,res.partner,product.product,product.template",
        "rate_limit": 300,
    },
]

created_keys = []
for cfg in KEY_CONFIGS:
    existing = env["mcp.api.key"].search([("name", "=", cfg["name"])], limit=1)
    if existing:
        _logger.info("  skip (exists): %s", cfg["name"])
        created_keys.append((existing, None))
        continue
    rec, plain_key = env["mcp.api.key"].generate_key(**cfg)
    created_keys.append((rec, plain_key))
    _logger.info("  created key: %s (id=%d)", rec.name, rec.id)
    _logger.info("    PLAIN KEY (save this!): %s", plain_key)

env.cr.commit()
_logger.info("MCP Keys done: %d total", len(created_keys))


# ── Summary ───────────────────────────────────────────────────────────────────

_section("SUMMARY")

base_url = env["ir.config_parameter"].sudo().get_param("web.base.url", "http://localhost:8069")

_logger.info("")
_logger.info("Partners created:       %d", len(created_partners))
_logger.info("Products created:       %d", len([p for p in created_products if p]))
_logger.info("Sales Orders created:   %d", len(created_orders) if "sale.order" in env else 0)
_logger.info("Invoices created:       %d", len(created_invoices) if "account.move" in env else 0)
_logger.info("MCP Keys created:       %d", len(created_keys))
_logger.info("")
_logger.info("MCP Endpoint:  %s/mcp/v1", base_url)
_logger.info("Portal:        %s/mcp/connect", base_url)
_logger.info("Health check:  %s/mcp/health", base_url)
_logger.info("")
_logger.info("API Keys (copy plain keys from above — stored as hash only):")
for rec, plain_key in created_keys:
    if plain_key:
        _logger.info("  %-30s  %s", rec.name, plain_key)
    else:
        _logger.info("  %-30s  (already existed — plain key unavailable)", rec.name)
_logger.info("")
_logger.info("Quick test (replace KEY with plain key from above):")
_logger.info("  curl -s '%s/mcp/health'", base_url)
_logger.info("  curl -s -X POST '%s/mcp/v1?key=KEY' \\", base_url)
_logger.info("    -H 'Content-Type: application/json' \\")
_logger.info("    -d '{\"jsonrpc\":\"2.0\",\"method\":\"tools/list\",\"id\":1}'")
_logger.info("")
_logger.info("Demo data installation complete.")
