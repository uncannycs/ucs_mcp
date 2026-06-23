#!/usr/bin/env bash
# MCP stdio bridge — reads JSON-RPC lines from stdin, POSTs to Odoo MCP endpoint.
# Usage: MCP_API_KEY=ucs_mcp_xxx MCP_URL=http://localhost:8072/mcp/v1 ./mcp_stdio_bridge.sh
set -euo pipefail

URL="${MCP_URL:-http://localhost:8069/mcp/v1}"
KEY="${MCP_API_KEY:-}"

while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    curl -s -X POST "$URL" \
        -H "Authorization: Bearer $KEY" \
        -H "Content-Type: application/json" \
        --data-raw "$line"
    printf '\n'
done
