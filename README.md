# odoo-aerospace-portfolio

Production-style Odoo 17 modules for an aerospace manufacturer, built for a
fictional company (**Borealis Launch Ltd**) on synthetic data. Every module is
installable on a fresh database in one command, has tests, and follows OCA
conventions so it is cheap to carry across major Odoo versions.

| Module | Business problem | Status |
|---|---|---|
| [`aero_material_outtime`](addons/aero_material_outtime/) | Freezer-controlled composites (prepregs, film adhesives): cumulative out-time per lot, blocks MO completion on expired material | tests passing |
| [`aero_ncr_mrb`](addons/aero_ncr_mrb/) | Nonconformance reports with automatic quarantine, MRB dispositions (use-as-is / rework / repair / scrap / return) that drive real stock moves, engineering-approval and CAPA gates, PDF | tests passing |
| Migration case 17 -> 19 | Port a module with Odoo's `upgrade_code`, document what breaks and why | planned |

## Run it in 5 minutes

Requirements: Docker Desktop (or Docker Engine) and Git Bash / any POSIX shell.

```bash
scripts/up.sh            # Odoo 17 + PostgreSQL 15 + Mailpit  ->  http://localhost:8069
scripts/init-dev-db.sh   # 'dev' database with demo data, apps and our modules (admin / admin)
scripts/test.sh aero_material_outtime   # fresh DB -> install -> tests, exit != 0 on failure
```

`make up`, `make test MODULE=...` wrap the same scripts on Linux/macOS.

## Engineering rules

Everything an AI coding agent or a human contributor must respect lives in
[AGENTS.md](AGENTS.md): Odoo 17 API conventions (no 18/19-isms), security
defaults (no `sudo()` shortcuts), upgrade-safety (inheritance only, `@name`
xpath anchors), tests as the definition of done. CI installs every module on a
clean database and runs its tests on each push.

## Layout

```
addons/            our modules, one directory each
scripts/           up / init-dev-db / test / shell / upgrade-dry-run
docker-compose.yml odoo:17.0, postgres:15, mailpit
.github/workflows  CI: tests on fresh DB + pre-commit (ruff, xml, yaml)
AGENTS.md          project rules for agents and humans
```
