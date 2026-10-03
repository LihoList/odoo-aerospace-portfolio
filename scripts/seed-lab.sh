#!/usr/bin/env bash
# Recreate the clean training database `lab`: no Odoo demo data, only the apps
# and the handful of records the exercises need. The demo database `dev` is untouched.
set -euo pipefail
export MSYS_NO_PATHCONV=1
cd "$(dirname "$0")/.."

docker compose up -d --wait db
docker compose exec -T db dropdb -U odoo --if-exists lab
docker compose run --rm -T odoo \
  -d lab -i stock,mrp,purchase,aero_material_outtime,aero_ncr_mrb \
  --without-demo=all --stop-after-init
docker compose run --rm -T odoo odoo shell -d lab --no-http < scripts/seed-lab.py
docker compose up -d
echo "lab ready: http://localhost:8069 (database 'lab', admin / admin)"
