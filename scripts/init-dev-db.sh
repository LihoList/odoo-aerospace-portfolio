#!/usr/bin/env bash
# Create the dev database with demo data and the apps we need, then install our modules.
# Safe to re-run: drops and recreates the database.
set -euo pipefail
export MSYS_NO_PATHCONV=1
cd "$(dirname "$0")/.."
MODULES="${1:-stock,mrp,purchase,maintenance,aero_material_outtime,aero_ncr_mrb}"

docker compose up -d --wait db
docker compose stop odoo >/dev/null 2>&1 || true
docker compose exec -T db dropdb -U odoo --if-exists dev
docker compose run --rm -T odoo -d dev -i "$MODULES" --stop-after-init
docker compose up -d
echo "dev database ready: http://localhost:8069 (admin / admin)"
