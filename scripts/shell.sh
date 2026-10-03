#!/usr/bin/env bash
# Interactive Odoo shell on the dev database:  env["stock.lot"].search([]) etc.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose run --rm odoo odoo shell -d "${1:-dev}"
