#!/usr/bin/env bash
# Odoo 19 port check: fresh DB with demo data -> install module -> run its tests.
# Runs in the separate compose project "aero19" (docker-compose.19.yml), so the 17 sandbox keeps running.
# Usage: scripts/test19.sh [module]   (default: aero_material_outtime)
set -euo pipefail
export MSYS_NO_PATHCONV=1   # Git Bash on Windows: do not rewrite /module into C:/...
MODULE="${1:-aero_material_outtime}"
DB="test19_${MODULE}"
LOG="${TMPDIR:-/tmp}/odoo19-test-${MODULE}.log"
cd "$(dirname "$0")/.."
DC=(docker compose -f docker-compose.19.yml)

"${DC[@]}" up -d --wait db
"${DC[@]}" exec -T db dropdb -U odoo --if-exists "$DB"
set +e
"${DC[@]}" run --rm -T odoo \
  -d "$DB" -i "$MODULE" --with-demo \
  --test-tags "/$MODULE" \
  --stop-after-init --log-level=test 2>&1 | tee "$LOG"
RC=${PIPESTATUS[0]}
set -e

if [ "$RC" -ne 0 ] || grep -Eq " (ERROR|CRITICAL) " "$LOG"; then
  echo "FAILED (exit $RC or ERROR lines): $LOG" >&2
  exit 1
fi
# A module Odoo refuses to load (e.g. manifest version still 17.0.x -> "incompatible version,
# setting installable=False") is skipped silently and the run ends green with "of 0 tests";
# broken demo data is only a WARNING ("demo data failed to install, installed without demo data").
if grep -Eq "incompatible version|demo data failed to install" "$LOG" || ! grep -Eq "of [1-9][0-9]* tests" "$LOG"; then
  echo "FAILED: module not installed or no tests ran: $LOG" >&2
  exit 1
fi
echo "OK: ${MODULE} tests passed on a fresh Odoo 19 database"
