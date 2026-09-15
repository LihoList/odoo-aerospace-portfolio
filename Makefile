MODULE ?= aero_material_outtime

up:            ## start sandbox (http://localhost:8069)
	scripts/up.sh
init-db:       ## create dev database with demo data and our modules
	scripts/init-dev-db.sh
test:          ## fresh DB -> install $(MODULE) -> run its tests
	scripts/test.sh $(MODULE)
shell:         ## odoo shell on dev DB
	scripts/shell.sh
lint:          ## pre-commit on all files
	pre-commit run --all-files
upgrade-dry-run: ## what upgrade_code (Odoo 19) would rewrite in $(MODULE)
	scripts/upgrade-dry-run.sh $(MODULE)
logs:
	docker compose logs -f odoo
down:
	docker compose down
.PHONY: up init-db test shell lint upgrade-dry-run logs down
