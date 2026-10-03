#!/usr/bin/env bash
# Fresh database -> install module -> run its tests. Exit code != 0 on any failure.
# Usage: scripts/test.sh [module]   (default: aero_material_outtime)
set -euo pipefail
export MSYS_NO_PATHCONV=1   # Git Bash on Windows: do not rewrite /module into C:/...
MODULE="${1:-aero_material_outtime}"
DB="test_${MODULE}"
LOG="${TMPDIR:-/tmp}/odoo-test-${MODULE}.log"
cd "$(dirname "$0")/.."

docker compose up -d --wait db   # --wait: block until the healthcheck passes
docker compose exec -T db dropdb -U odoo --if-exists "$DB"
docker compose run --rm -T odoo \
  -d "$DB" -i "$MODULE" \
  --test-tags "/$MODULE" \
  --stop-after-init --log-level=test 2>&1 | tee "$LOG"

# Belt and braces: fail on any ERROR/CRITICAL line even if the exit code was 0.
if grep -Eq " (ERROR|CRITICAL) " "$LOG"; then
  echo "ERROR lines found in test log: $LOG" >&2
  exit 1
fi
echo "OK: ${MODULE} tests passed on a fresh database"
