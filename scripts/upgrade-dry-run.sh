#!/usr/bin/env bash
# Preview what Odoo's own upgrade_code scripts would rewrite when porting a module to 19.
# Uses the odoo:19.0 image (upgrade_code exists from 19.0). Never writes: --dry-run.
set -euo pipefail
export MSYS_NO_PATHCONV=1
MODULE="${1:-aero_material_outtime}"
cd "$(dirname "$0")/.."
HOST_ADDONS="$(pwd -W 2>/dev/null || pwd)/addons"
docker run --rm -v "${HOST_ADDONS}:/mnt/extra-addons" odoo:19.0 \
  odoo upgrade_code --from 17.0 --addons-path=/mnt/extra-addons --glob "$MODULE/**/*" --dry-run || true
