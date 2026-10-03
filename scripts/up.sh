#!/usr/bin/env bash
# Start the sandbox and wait until Odoo answers.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose up -d
for i in $(seq 1 60); do
  if curl -fsS -o /dev/null "http://localhost:8069/web/login" 2>/dev/null; then
    echo "Odoo:    http://localhost:8069  (db: dev, login admin / admin)"
    echo "Mailpit: http://localhost:8025"
    exit 0
  fi
  sleep 2
done
echo "Odoo did not answer in time; see: docker compose logs -f odoo" >&2
exit 1
