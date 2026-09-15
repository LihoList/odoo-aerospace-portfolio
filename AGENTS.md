# AGENTS.md - Odoo 17 aerospace portfolio: rules for AI coding agents and humans

## Context
- Odoo 17.0 Community, official `odoo:17.0` Docker image, PostgreSQL 15.
- Odoo source for reading: `../odoo` (branch 17.0). Before overriding a method, read its implementation there.
- Fictional company "Borealis Launch Ltd". Synthetic data only. Never paste real part numbers,
  drawings, supplier names, customer data or export-controlled data.

## Commands (run from repo root, Git Bash / Linux)
- Tests:   `scripts/test.sh <module>`   # fresh DB, installs the module, runs its tests, exit != 0 on failure
- Sandbox: `scripts/up.sh` then `scripts/init-dev-db.sh` (dev DB with demo data, admin/admin)
- Shell:   `scripts/shell.sh`           # env["stock.lot"].search([])
- Lint:    `pre-commit run --all-files`
- Port check to 19: `scripts/upgrade-dry-run.sh <module>`

## Odoo 17 conventions (this is NOT 18/19 - do not use newer APIs)
- Views: `<tree>` (not `<list>`); `invisible="expr"`, `readonly="expr"`, `required="expr"` as Python expressions (`attrs`/`states` were removed in 17).
- SQL constraints: `_sql_constraints = [(name, "CHECK(...)", msg)]` (`models.Constraint` is 19+).
- Translations: `from odoo import _` and `_("...")` (`self.env._` is 18+).
- Storable products: `detailed_type = "product"` (`is_storable` is 18+).
- Display name: `_compute_display_name` (`name_get` is deprecated).
- Aggregations: `_read_group(domain, groupby, aggregates)`.
- Access checks: `check_access_rights` / `check_access_rule` (`has_access` is 18+).
- HTTP JSON routes: `type="json"` (`jsonrpc` is 19+).
- Domains are plain lists; `odoo.osv.expression` helpers are fine in 17.

## Every new model must have
- `_description`; ACL rows in `security/ir.model.access.csv` (user + manager groups);
- `mail.thread` + `tracking=True` on quality-relevant fields when the record is audited;
- tests in `tests/` tagged `("post_install", "-at_install")`, positive and negative cases;
- a README section: business problem, what the module does, how to demo it.

## Forbidden without explicit human approval
- `sudo()` to get around an access error; `cr.commit()` in business logic;
- edits under `../odoo`; copying whole views or methods instead of `super()`;
- xpath by position (`//group[2]`), use `@name` anchors;
- new Python dependencies; network calls from tests.

## Definition of done
- `scripts/test.sh <module>` and `pre-commit run --all-files` pass;
- migration script in `migrations/<version>/` if the schema changed; version bumped in `__manifest__.py`;
- README updated with what changed and how to demo it.
