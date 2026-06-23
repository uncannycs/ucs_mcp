#!/usr/bin/env python3
# License LGPL-3 or later (https://www.gnu.org/licenses/lgpl).
"""
UCS MCP Remote Demo Data Seeder
================================
Populates a remote Odoo instance with demo data for testing all MCP tools.
Uses Odoo JSON-RPC 2.0 API — no server shell access required.

Usage:
    python3 seed_remote.py

Defaults to https://ucs-mcp.odoo.com/ (admin / jKTY8Kc8a53v8Be).
Override via env vars:
    ODOO_URL=https://myinstance.odoo.com
    ODOO_DB=mydb
    ODOO_USER=admin
    ODOO_PASSWORD=secret
    python3 seed_remote.py
"""

import json
import logging
import os
import sys

try:
    import requests
except ImportError:
    sys.exit("pip install requests")

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
_log = logging.getLogger("seed_remote")

# ── Config ────────────────────────────────────────────────────────────────────

ODOO_URL = os.environ.get("ODOO_URL", "https://ucs-mcp.odoo.com").rstrip("/")
ODOO_DB = os.environ.get("ODOO_DB", "")  # auto-detected if empty
ODOO_USER = os.environ.get("ODOO_USER", "admin")
ODOO_PASSWORD = os.environ.get("ODOO_PASSWORD", "jKTY8Kc8a53v8Be")

SESSION = requests.Session()
SESSION.headers.update({"Content-Type": "application/json"})

_uid = None
_db = None


# ── JSON-RPC helpers ──────────────────────────────────────────────────────────

def _rpc(endpoint, method, *args, **kwargs):
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "id": 1,
        "params": {"method": method, "args": list(args), "kwargs": kwargs},
    }
    r = SESSION.post(f"{ODOO_URL}{endpoint}", json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError("RPC error: %s" % data["error"])
    return data["result"]


def _call(model, method, *args, **kwargs):
    return _rpc(
        "/web/dataset/call_kw",
        method,
        *args,
        model=model,
        method=method,
        args=list(args),
        kwargs=kwargs,
    )


def call_kw(model, method, args, kwargs=None):
    """Direct call_kw for create/search/write."""
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "id": 1,
        "params": {
            "model": model,
            "method": method,
            "args": args,
            "kwargs": kwargs or {},
        },
    }
    r = SESSION.post(f"{ODOO_URL}/web/dataset/call_kw", json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError("RPC error on %s.%s: %s" % (model, method, data["error"].get("data", {}).get("message", data["error"])))
    return data["result"]


def section(title):
    _log.info("")
    _log.info("=" * 60)
    _log.info("  %s", title)
    _log.info("=" * 60)


# ── Auth ──────────────────────────────────────────────────────────────────────

def authenticate():
    global _uid, _db

    # Auto-detect DB if not provided
    if not ODOO_DB:
        r = SESSION.post(f"{ODOO_URL}/web/database/list", json={
            "jsonrpc": "2.0", "method": "call", "id": 1, "params": {}
        }, timeout=15)
        dbs = r.json().get("result", [])
        if not dbs:
            sys.exit("No databases found. Set ODOO_DB env var.")
        _db = dbs[0]
        _log.info("Auto-detected DB: %s", _db)
    else:
        _db = ODOO_DB

    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "id": 1,
        "params": {
            "db": _db,
            "login": ODOO_USER,
            "password": ODOO_PASSWORD,
        },
    }
    r = SESSION.post(f"{ODOO_URL}/web/session/authenticate", json=payload, timeout=15)
    r.raise_for_status()
    result = r.json().get("result", {})
    _uid = result.get("uid")
    if not _uid:
        sys.exit("Authentication failed. Check URL / credentials.")
    _log.info("Authenticated as uid=%d on %s (db=%s)", _uid, ODOO_URL, _db)


# ── Partners ──────────────────────────────────────────────────────────────────

def seed_partners():
    section("Partners")

    countries = call_kw(
        "res.country", "search_read",
        [[["name", "in", ["India", "United States", "United Arab Emirates"]]]],
        {"fields": ["id", "name"], "limit": 10},
    )
    country_map = {c["name"]: c["id"] for c in countries}

    PARTNERS = [
        {"name": "Acme Corp",         "email": "contact@acme.example",    "phone": "+1-555-0100",      "is_company": True,  "country_id": country_map.get("United States")},
        {"name": "Gulf Traders LLC",  "email": "info@gulftraders.example", "phone": "+971-4-0000001",   "is_company": True,  "country_id": country_map.get("United Arab Emirates")},
        {"name": "Sigma Solutions",   "email": "sigma@sigma.example",      "phone": "+91-98765-43210",  "is_company": True,  "country_id": country_map.get("India")},
        {"name": "John Doe",          "email": "john.doe@example.com",     "phone": "+1-555-0200",      "is_company": False},
        {"name": "Priya Sharma",      "email": "priya@example.in",         "phone": "+91-99000-11111",  "is_company": False},
        {"name": "Mohammed Al Farsi", "email": "mfarsi@example.ae",        "phone": "+971-50-1234567",  "is_company": False},
        {"name": "TechStart Inc",     "email": "hello@techstart.example",  "phone": "+1-555-0300",      "is_company": True},
        {"name": "Retail World",      "email": "buy@retailworld.example",  "phone": "+91-80-12345678",  "is_company": True,  "country_id": country_map.get("India")},
    ]

    partner_ids = []
    for vals in PARTNERS:
        # Remove None country_id
        if "country_id" in vals and vals["country_id"] is None:
            del vals["country_id"]

        existing = call_kw("res.partner", "search", [[["email", "=", vals["email"]]]], {"limit": 1})
        if existing:
            partner_ids.append(existing[0])
            _log.info("  skip (exists): %s [id=%d]", vals["name"], existing[0])
        else:
            pid = call_kw("res.partner", "create", [vals])
            partner_ids.append(pid)
            _log.info("  created: %s [id=%d]", vals["name"], pid)

    _log.info("Partners done: %d", len(partner_ids))
    return partner_ids


# ── Products ──────────────────────────────────────────────────────────────────

def seed_products():
    section("Products")

    PRODUCTS = [
        {"name": "MCP Demo Widget",       "list_price": 150.00,  "standard_price": 80.00,  "type": "consu"},
        {"name": "MCP Demo Service Pack", "list_price": 500.00,  "standard_price": 200.00, "type": "service"},
        {"name": "MCP Demo Laptop",       "list_price": 1200.00, "standard_price": 900.00, "type": "consu"},
        {"name": "MCP Demo Keyboard",     "list_price": 75.00,   "standard_price": 40.00,  "type": "consu"},
        {"name": "MCP Demo Consulting",   "list_price": 200.00,  "standard_price": 100.00, "type": "service"},
    ]

    variant_ids = []
    for vals in PRODUCTS:
        existing = call_kw("product.template", "search", [[["name", "=", vals["name"]]]], {"limit": 1})
        if existing:
            # Get variant id
            variants = call_kw(
                "product.product", "search",
                [[["product_tmpl_id", "=", existing[0]]]],
                {"limit": 1},
            )
            variant_ids.append(variants[0] if variants else None)
            _log.info("  skip (exists): %s [tmpl_id=%d]", vals["name"], existing[0])
        else:
            tmpl_id = call_kw("product.template", "create", [vals])
            variants = call_kw(
                "product.product", "search",
                [[["product_tmpl_id", "=", tmpl_id]]],
                {"limit": 1},
            )
            vid = variants[0] if variants else None
            variant_ids.append(vid)
            _log.info("  created: %s [tmpl_id=%d, variant_id=%s]", vals["name"], tmpl_id, vid)

    _log.info("Products done: %d", len(variant_ids))
    return variant_ids


# ── Sales Orders ──────────────────────────────────────────────────────────────

def seed_sales_orders(partner_ids, variant_ids):
    section("Sales Orders")

    # Check if sale module installed
    installed = call_kw(
        "ir.module.module", "search_read",
        [[["name", "=", "sale"], ["state", "=", "installed"]]],
        {"fields": ["id"], "limit": 1},
    )
    if not installed:
        _log.info("  sale module not installed — skipping")
        return []

    # Company partners are first 3
    company_partner_ids = partner_ids[:3]
    prices = [150.00, 500.00, 1200.00, 75.00, 200.00]

    ORDERS = [
        {"partner_id": company_partner_ids[0], "lines": [(variant_ids[0], 3, prices[0]), (variant_ids[3], 2, prices[3])]},
        {"partner_id": company_partner_ids[1], "lines": [(variant_ids[1], 1, prices[1]), (variant_ids[4], 5, prices[4])]},
        {"partner_id": company_partner_ids[2], "lines": [(variant_ids[2], 1, prices[2])]},
    ]

    order_ids = []
    for order_data in ORDERS:
        lines = []
        for vid, qty, price in order_data["lines"]:
            if vid:
                lines.append((0, 0, {"product_id": vid, "product_uom_qty": qty, "price_unit": price}))
        if not lines:
            continue
        try:
            so_id = call_kw("sale.order", "create", [{"partner_id": order_data["partner_id"], "order_line": lines}])
            order_ids.append(so_id)
            _log.info("  created SO id=%d", so_id)
        except RuntimeError as e:
            _log.warning("  could not create SO: %s", e)

    # Confirm first two
    for so_id in order_ids[:2]:
        try:
            call_kw("sale.order", "action_confirm", [[so_id]])
            _log.info("  confirmed SO id=%d", so_id)
        except RuntimeError as e:
            _log.warning("  could not confirm SO id=%d: %s", so_id, e)

    _log.info("Sales Orders done: %d", len(order_ids))
    return order_ids


# ── Invoices ──────────────────────────────────────────────────────────────────

def seed_invoices(partner_ids, variant_ids):
    section("Invoices")

    installed = call_kw(
        "ir.module.module", "search_read",
        [[["name", "=", "account"], ["state", "=", "installed"]]],
        {"fields": ["id"], "limit": 1},
    )
    if not installed:
        _log.info("  account module not installed — skipping")
        return []

    invoice_partner_ids = partner_ids[:3]
    prices = [150.00, 500.00, 1200.00]
    invoice_ids = []

    for i, partner_id in enumerate(invoice_partner_ids):
        vid = variant_ids[i % len(variant_ids)] if variant_ids else None
        if vid:
            lines = [(0, 0, {
                "product_id": vid,
                "quantity": (i + 1) * 2,
                "price_unit": prices[i % 3],
            })]
        else:
            lines = [(0, 0, {
                "name": "Demo Service Line %d" % (i + 1),
                "quantity": 1,
                "price_unit": 250.00 * (i + 1),
            })]
        try:
            inv_id = call_kw("account.move", "create", [{
                "move_type": "out_invoice",
                "partner_id": partner_id,
                "invoice_line_ids": lines,
            }])
            invoice_ids.append(inv_id)
            _log.info("  created invoice id=%d for partner_id=%d", inv_id, partner_id)
        except RuntimeError as e:
            _log.warning("  could not create invoice for partner_id=%d: %s", partner_id, e)

    # Post first invoice
    if invoice_ids:
        try:
            call_kw("account.move", "action_post", [[invoice_ids[0]]])
            _log.info("  posted invoice id=%d", invoice_ids[0])
        except RuntimeError as e:
            _log.warning("  could not post invoice id=%d: %s", invoice_ids[0], e)

    _log.info("Invoices done: %d", len(invoice_ids))
    return invoice_ids


# ── MCP API Keys ──────────────────────────────────────────────────────────────

def seed_mcp_keys():
    """Create MCP API keys via the portal endpoint — uses sudo() internally so no group needed."""
    section("MCP API Keys")

    KEY_CONFIGS = [
        {
            "key_name": "Demo Full Access Key",
            "mcp_server_name": "odoo-full",
            "expiry_days": "",
            "perm_write": "1",
            "perm_create": "1",
            "perm_delete": "1",
            "perm_execute": "1",
        },
        {
            "key_name": "Demo Read-Only Key",
            "mcp_server_name": "odoo-readonly",
            "expiry_days": "",
        },
        {
            "key_name": "Demo Sales Key",
            "mcp_server_name": "odoo-sales",
            "expiry_days": "",
            "perm_write": "1",
            "perm_create": "1",
        },
    ]

    results = []
    for cfg in KEY_CONFIGS:
        # POST to portal create endpoint — session cookie is already set from authenticate()
        # Must NOT send application/json here — portal expects form-encoded data
        r = SESSION.post(
            f"{ODOO_URL}/mcp/connect/create",
            data=cfg,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            allow_redirects=False,
            timeout=30,
        )
        location = r.headers.get("Location", "")

        if "created" in location:
            # Fetch the created page to get the plain key from session
            created_r = SESSION.get(f"{ODOO_URL}/mcp/connect/created", timeout=15)
            # Parse plain key from page HTML (it's in a <code> or visible text block)
            import re
            match = re.search(r"ucs_mcp_[A-Za-z0-9_\-]{40,}", created_r.text)
            plain_key = match.group(0) if match else None
            results.append((cfg["key_name"], None, plain_key))
            _log.info("  created: %s", cfg["key_name"])
            if plain_key:
                _log.info("    PLAIN KEY: %s", plain_key)
            else:
                _log.warning("    could not extract plain key from page (save from portal manually)")
        elif "error" in location:
            import urllib.parse
            err = urllib.parse.unquote_plus(location.split("error=")[-1]) if "error=" in location else location
            _log.warning("  failed to create %s: %s", cfg["key_name"], err)
        else:
            _log.warning("  unexpected redirect for %s: %s", cfg["key_name"], location)

    _log.info("MCP Keys done: %d", len(results))
    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    _log.info("UCS MCP Remote Data Seeder")
    _log.info("Target: %s", ODOO_URL)

    authenticate()

    partner_ids = seed_partners()
    variant_ids = seed_products()
    order_ids = seed_sales_orders(partner_ids, variant_ids)
    invoice_ids = seed_invoices(partner_ids, variant_ids)
    key_results = seed_mcp_keys()

    section("SUMMARY")
    _log.info("Partners:      %d", len(partner_ids))
    _log.info("Products:      %d", len([v for v in variant_ids if v]))
    _log.info("Sales Orders:  %d", len(order_ids))
    _log.info("Invoices:      %d", len(invoice_ids))
    _log.info("MCP Keys:      %d", len(key_results))
    _log.info("")
    _log.info("MCP Endpoint:  %s/mcp/v1", ODOO_URL)
    _log.info("Portal:        %s/mcp/connect", ODOO_URL)
    _log.info("Health check:  %s/mcp/health", ODOO_URL)
    _log.info("")
    _log.info("API Keys:")
    for name, rec_id, plain_key in key_results:
        if plain_key:
            _log.info("  %-30s  %s", name, plain_key)
        else:
            _log.info("  %-30s  (existed — plain key unavailable)", name)
    _log.info("")
    _log.info("Quick test:")
    _log.info("  curl -s '%s/mcp/health'", ODOO_URL)


if __name__ == "__main__":
    main()
