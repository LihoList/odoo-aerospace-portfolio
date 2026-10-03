#!/usr/bin/env bash
# Preview what Odoo's own upgrade_code scripts would rewrite when porting a module to 19.
# Uses the odoo:19.0 image (upgrade_code exists from 19.0). Never writes: --dry-run.
# Usage: scripts/upgrade-dry-run.sh <module> [--apply]
#   --apply  really rewrite the files (addons mounted read-write); review the git diff afterwards.
set -euo pipefail
export MSYS_NO_PATHCONV=1
MODULE="${1:-aero_material_outtime}"
MODE="--dry-run"
[ "${2:-}" = "--apply" ] && MODE=""
cd "$(dirname "$0")/.."
HOST_ADDONS="$(pwd -W 2>/dev/null || pwd)/addons"
# --entrypoint odoo: the image entrypoint otherwise waits for a PostgreSQL host "db" that
# does not exist for a plain `docker run`, and upgrade_code needs no database at all.
# upgrade_code exits 1 when files are (or would be) rewritten, so do not treat that as failure.
docker run --rm --entrypoint odoo -v "${HOST_ADDONS}:/mnt/extra-addons" odoo:19.0 \
  upgrade_code --from 17.0 --addons-path=/mnt/extra-addons --glob "$MODULE/**/*" $MODE || true
