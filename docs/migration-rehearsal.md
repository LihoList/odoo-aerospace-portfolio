# Odoo 17 -> 19 migration rehearsal (sandbox)

A full migration cycle for my two custom modules (`aero_material_outtime`, `aero_ncr_mrb`), run on a
local Odoo 17 Community sandbox for the fictional company Borealis Launch Ltd. All data is synthetic
(Odoo demo data plus the modules' own demo records). Every number below was measured on
2026-09-17 on one Windows 11 laptop with Docker Desktop. Where something was not done or not
measured, this document says so.

Evidence files are in `docs/migration-rehearsal/` (SQL used, before/after snapshots, upgrade_code logs).

Images and sources used: `odoo:17.0` (17.0-20260908), `odoo:18.0`, `odoo:19.0` (19.0-20260908),
postgres 15 (sandbox) and 16 (19 test bench), OCA OpenUpgrade `18.0` @ 068c630 and `19.0` @ 546fa17,
openupgradelib 3.13.7.

---

## Summary

| What | Result |
|---|---|
| Installed modules in the source DB | 65 (63 Odoo S.A. + 2 custom) |
| Custom code (`odoo cloc`) | 1,113 lines of code (1,343 lines incl. comments/blank): outtime 239, NCR/MRB 874 |
| Source DB / filestore | 53 MB after copy (58 MB `dev` with bloat) / 17,954,718 bytes, 625 files, 947 attachment rows |
| Backup (pg_dump -Fc + tar.gz) | 1.8 s total; 5,176,681 + 7,489,259 bytes |
| Restore, end to end | 12.7 s (DB 11.7 s, filestore 1.0 s); repeat DB restore 13.4 s |
| Restore verification | snapshot identical; 947/947 attachment files present, 947/947 SHA-1 match |
| Code port 17 -> 19 | 10 distinct breakages hit at install/test time + 3 silent ones found by source review |
| Tests on Odoo 19 | `aero_material_outtime` 7/7, `aero_ncr_mrb` 16/16 (fresh DB with demo) |
| DB upgrade 17 -> 18 -> 19 (OpenUpgrade) | Worked after 3 fixes; 67 s + 72 s; business data reconciled; 23/23 tests pass on the upgraded DB |

---

## Step 1. Audit

**Done in the sandbox**

- Installed modules in `dev`: **65**. 63 are Odoo S.A. modules; **2 are custom** (`aero_material_outtime`,
  `aero_ncr_mrb`, both `17.0.1.0.0`). The apps are stock, mrp, purchase and maintenance, plus
  everything they pull in: account, point_of_sale, `pos_mrp` and `l10n_mt_pos` are installed too, which
  I did not expect. They matter for the upgrade because every installed module needs migration coverage.
- Custom code, `odoo cloc -p <module>` in the 17 image (same result with `odoo cloc -d dev`):

  | Module | Lines | Other (blank/comments) | Code |
  |---|---:|---:|---:|
  | aero_material_outtime | 289 | 50 | 239 |
  | aero_ncr_mrb | 1,054 | 180 | 874 |
  | **Total** | **1,343** | **230** | **1,113** |

- OpenUpgrade coverage for all 63 standard modules (from `docsource/modules170-180.rst` and
  `modules180-190.rst`):
  - 17->18: 23 "Done", 34 "Nothing to do", 3 blank (`account_add_gln`, `l10n_mt_pos` "No DB layout
    changes", `pos_online_payment` "No DB layout changes"), `account_payment_term` merged into `account`,
    `spreadsheet_dashboard_purchase(_stock)` removed (apriori renames them to `*_oca` modules).
  - 18->19: 27 "Done", 29 "Nothing to do", 2 blank (`account_check_printing`, `l10n_mt_pos`),
    `pos_epson_printer` merged into `point_of_sale`, `web_editor` merged into `html_editor`.

**In a real company** the audit also covers: who uses which menus (usage logs), customisations done in
Studio or directly in the database (views, server actions, automated actions), integrations (EDI, API
users, webhooks), reports and email templates, OCA/third-party modules and whether they exist for the
target version, and database size, which drives the timings.

## Step 2. Test upgrade #1: copy, neutralise, snapshot, backup, restore

### 2.1 Copy

`rehearsal_src` was created from `dev` with `pg_dump -Fc dev | pg_restore` (not `createdb -T dev`,
which needs zero connections, and the user had `dev` open in the browser). The filestore was copied
with `cp -a` in the Odoo container.

**Lesson learned from the copy:** comparing `dev` with the copy immediately afterwards showed one
difference: the copy had one zero-quantity quant (id 70, ENG-INJ-004 in Quarantine) that `dev` did not.
Cause: Docker Desktop had just restarted, `dev`'s "Procurement: run scheduler" cron was overdue
(nextcall was the previous day), it ran at 17:07:22 right after the copy, and its `_quant_tasks()` ->
`_unlink_zero_quants()` deleted the zero quant (`addons/stock/models/stock_rule.py:663`,
`stock_quant.py:1162`). The copy is consistent; the source moved on. In production this is exactly why
the source must be frozen (workers and crons stopped) before the final dump.

### 2.2 Neutralisation

`odoo neutralize -d rehearsal_src` (17 image). In 17 it runs the `data/neutralize.sql` of every
installed module (`odoo/modules/neutralize.py`); `--stdout` prints the SQL
without applying it. The sandbox had no outgoing mail server, so to have something to neutralise I
first inserted a clearly named fake one ("Simulated production SMTP (rehearsal seed)", host mailpit,
dummy user/password) into the copy only. Before/after, from `neutralize_check.sql`:

| Check | Before | After |
|---|---|---|
| `ir_mail_server` | 1 row, active, user and password set | seeded server inactive, user and password NULL; new active server "neutralization - disable emails" on host `invalid` |
| `ir_cron` active / inactive | 17 / 2 | 1 / 18 (only "Base: Auto-vacuum internal data" stays active) |
| `database.is_neutralized` | absent | `true` |
| `database.secret` | real value | `dummysecret` |
| view `web.neutralize_banner` | inactive | active (the "neutralized" banner) |
| `iap_account` token | real token | ends in `+disabled` |
| payment providers | 16 disabled | 16 disabled (nothing to change) |

Neutralize itself took about 2 s including container start-up.

### 2.3 Reconciliation snapshot (before)

`docs/migration-rehearsal/snapshot.sql` on `rehearsal_src` (full output in `snapshot_rehearsal_src.csv`):

| Metric | Value |
|---|---:|
| res_partner (all / active) | 43 / 39 |
| product_product | 68 |
| stock_lot | 20 |
| stock_move done / all | 56 / 93 |
| stock_quant rows in internal locations | 43 |
| sum(quantity) in internal locations | 1,554.0000 |
| aero_outtime_event | 4 |
| ir_attachment rows with a file | 947 |
| aero_ncr by state | open 1, mrb 1, dispositioned 1, closed 1 |
| mrp_production by state | draft 1, confirmed 2, done 3 |
| purchase_order by state | draft 6, sent 1, purchase 4 |

The per product + internal location quantity table has 43 rows (in the CSV).

### 2.4 Backup

| Part | Command | Size | Time |
|---|---|---:|---:|
| Database | `pg_dump -Fc rehearsal_src` | 5,176,681 bytes | 997 ms |
| Filestore | `tar -czf - rehearsal_src` | 7,489,259 bytes | 813 ms |
| **Total** | | **12.7 MB** | **1.8 s** |

### 2.5 Restore test = real rollback time

Restore into `rehearsal_restored`: `createdb` + `pg_restore --exit-on-error` from the dump, then untar
the filestore into a temporary folder and rename it.

| Part | Time |
|---|---:|
| createdb + pg_restore | 11,730 ms (repeat on a scratch DB: 13,372 ms) |
| filestore untar + rename | 955 ms |
| **End to end** | **12,686 ms** |

The DB restore is about 12x slower than the dump (11.7 s vs 1.0 s), most likely because a single-threaded restore rebuilds all indexes and constraints (not profiled). This does not
include starting Odoo on the restored DB or switching DNS/proxy.

Verification:
- The snapshot of `rehearsal_restored` is **byte-identical** to `rehearsal_src`.
- All 947 `ir_attachment.store_fname` files exist in the restored filestore and all 947 SHA-1 checksums
  match `ir_attachment.checksum`.
- The attachment is readable through the ORM: `odoo shell -d rehearsal_restored`, `res.partner(1).image_1920`
  decodes to 15,310 bytes starting with a PNG header, and `ir.attachment(4).raw` matches its checksum.

**My own mistake, kept here on purpose:** my first restore attempt untarred the archive directly into
`filestore/`, which silently overwrote `rehearsal_src`'s folder (same content) and then renamed it
away, leaving `rehearsal_src` without a filestore. I repaired it from the backup and threw away that
timing. Restore scripts must always extract into an empty temporary directory.

## Step 3. Porting the code

Branch `migrate-19`, worked in a separate `git worktree`
(`../odoo-aerospace-portfolio-19`). Reason: the running 17 sandbox bind-mounts `./addons` with
`--dev=xml`, which re-reads view XML from disk, so rewriting files or switching branches in the main
working tree would have broken the user's live `dev` database in the browser.

### 3.1 Odoo's `upgrade_code`

`scripts/upgrade-dry-run.sh <module> [--apply]` runs `odoo upgrade_code --from 17.0 --glob "<module>/**/*"`
in the `odoo:19.0` image (outputs in `docs/migration-rehearsal/upgrade_code/`).

- The script as committed on `main` **never worked**: the image entrypoint runs `wait-for-psql.py`
  against a host `db` before any `odoo` subcommand, so it only printed
  `could not translate host name "db"`. Fixed with `--entrypoint odoo` (upgrade_code needs no database).
- It rewrote 8 files: `<tree>` -> `<list>` and `view_mode` tree -> list (also inside Python action
  dicts), and `_sql_constraints` -> `models.Constraint`. I checked the diff by hand: all `<tree>` tags
  were on their own lines, so none of the one-line `<tree>..</tree>` cases were broken and the XML
  was still well formed.
- It does not touch `detailed_type`, security groups, the chatter, or anything else below.

### 3.2 Breakage log

Every entry was either hit on a fresh Odoo 19 DB (`scripts/test19.sh`, see step 4) or found by reading
the 19.0 source. File references are to the 19.0 source unless marked 17.

| # | Symptom (as reported) | Cause (18/19 change, source) | Fix |
|---|---|---|---|
| 1 | Test run **green**, `0 failed, 0 error(s) of 0 tests`; log: `The module aero_material_outtime has an incompatible version, setting installable=False` (WARNING) | Manifest still `17.0.1.0.0`; 19 refuses to load it and just skips the module | Version `19.0.1.0.0`; `test19.sh` now fails on "incompatible version" or on zero tests |
| 2 | `RELAXNG_ERR_INVALIDATTR: Invalid attribute expand for element group` -> `Invalid view aero.outtime.event.search definition` | `group` in `odoo/addons/base/rng/common.rng` lost the `expand` and `string` attributes (17 lines 301-302) | `<group expand="0" string="Group By">` -> `<group>` (both modules) |
| 3 | `Element '<xpath expr="//page[@name='description']">' cannot be located in parent view` | 19 lot form (`addons/stock/views/stock_lot_views.xml`) has no notebook; "description" is now a `<group name="description">` | Anchor on `//group[@name='description']`, add our own notebook with the out-time page |
| 4 | `ValueError: Invalid field 'detailed_type' in 'product.product'`, in demo data and in `setUpClass` | `detailed_type` removed; storable = `type='consu'` + `is_storable=True` (`addons/stock/models/product.py:839`) | Demo XML and tests updated. **Also:** a failing demo file is only a WARNING in 19 (`Module ... demo data failed to install, installed without demo data`, `odoo/modules/loading.py:75`), so `test19.sh` now fails on that too |
| 5 | `ValueError: Invalid field 'category_id' in 'res.groups'` | Groups hang off the new `res.groups.privilege` (`odoo/addons/base/models/res_groups.py:36`, `res_groups_privilege.py`), which carries `category_id`; `users` renamed `user_ids` | New privilege record, `privilege_id` on the 3 groups, `users` -> `user_ids` (same pattern as `addons/mrp/security/mrp_security.xml`) |
| 6 | `ValueError: Invalid field 'comment' in 'stock.location'` | Field removed (17: `addons/stock/models/stock_location.py:62` `comment = fields.Html`; nothing in 19) | Dropped from `data/stock_location.xml`, text kept as an XML comment. In a DB upgrade, any text in that field is left behind |
| 7 | `ValueError: Invalid field 'name' in 'stock.move'` (from `_demo_setup` -> `_create_done_move`) | `stock.move.name` removed; `_rec_name = 'reference'`, which is computed from picking/scrap/inventory only (`addons/stock/models/stock_move.py:22, 357`) | Label goes to `description_picking` (computed, inverse stores `description_picking_manual`). **Side effect:** our quarantine/release moves now have an empty Reference column (17 fell back to `name`); `origin` still holds the NCR number |
| 8 | `ValueError: Invalid field 'groups_id' in 'res.users'` (tests) | Renamed `group_ids` (`odoo/addons/base/models/res_users.py:257`) | Tests updated |
| 9 | 10 of 16 tests: `AttributeError: 'res.groups' object has no attribute 'users'` | `users` gone. In 17, `users` included implied members because `UsersImplied.create/write` stored implied groups (17: `res_users.py:1445-1475`); in 19 `user_ids` is explicit only and `all_user_ids` is explicit + implied (`res_groups.py:18`, computed from `all_implied_by_ids.user_ids`) | `group.users` -> `group.all_user_ids` to keep the 17 behaviour |
| 10 | (tooling) dry-run printed only `could not translate host name "db"` | See 3.1 | `--entrypoint odoo` |
| S1 | **Silent**, tests green: NCR form would have no chatter | 17 compiled `div.oe_chatter` (17: `addons/mail/static/src/views/web/form/form_compiler.js:74`); 19 only compiles `<chatter/>` (`addons/mail/static/src/chatter/web/form_compiler.js:47`), no JS references `oe_chatter` any more | `<chatter/>` |
| S2 | **Silent**: quantity precision | Decimal precision "Product Unit of Measure" (17: `addons/product/data/product_data.xml:36`) renamed "Product Unit" (`addons/uom/data/uom_data.xml:6`); `precision_get` returns 2 for an unknown name (`odoo/addons/base/models/decimal_precision.py:27`), so a company that set 3 or 4 digits would silently get 2 on NCR quantities | `digits="Product Unit"` |
| S3 | Not a breakage: modernisation | `_()` still works in 19 (`odoo/tools/translate.py:681`) but `self.env._(msg, *args)` is the 18+ form (`odoo/orm/environments.py:315`); `uom.uom.compare()` replaces `float_compare(precision_rounding=uom.rounding)` (`addons/uom/models/uom_uom.py:122`) | 44 call sites rewritten; one `float_compare` replaced |

Checked and **unchanged**:
- `_check_company_auto` still exists (`odoo/orm/models.py:451`).
- `stock.scrap.action_validate()` still returns `do_scrap()` (True) or the insufficient-quantity wizard
  dict (`addons/stock/models/stock_scrap.py:211-231`), so our `res is not True` check is still valid.
- Report `web.external_layout`: the render test passes and a 30,592-byte PDF was produced on the 19
  UAT DB. I did not look at the PDF.
- The global `ir.rule` with `company_ids`, and `has_group`, are exercised by the tests with non-admin
  users and pass. `numbercall` and `read_group` are not used by these modules.
- `stock.move.line` `quantity`/`picked` was already the 17 API.

Found in passing, **not a migration issue** and not changed: `message_post(body=_("...<b>%s</b>") % x)`
passes a plain `str`, which both 17 and 19 escape, so the `<b>` tags show literally in the chatter.
The fix would be `Markup`.

## Step 4. Test upgrade #2 and UAT

`scripts/test19.sh <module>` with `docker-compose.19.yml`: a separate compose project `aero19`
(`odoo:19.0`, `postgres:16`, own volumes, no published ports), so the 17 sandbox kept running. Fresh
DB, `--with-demo`, install, `--test-tags /<module>`.

| Module | Odoo 17 on `main` (`scripts/test.sh`) | Odoo 19 on `migrate-19` (`scripts/test19.sh`) |
|---|---|---|
| aero_material_outtime | 7/7, 36 s | **7/7**, 43 s |
| aero_ncr_mrb | 16/16, 42 s | **16/16**, 45 s |

(Times are wall clock for the whole script: fresh DB, install with dependencies, tests.)

"UAT" DB on 19 (`uat19`): stock, mrp, purchase, maintenance and both modules together with demo, installed
with no errors in 61 s. Through `odoo shell` I checked:
- the combined `stock.lot` form contains the out-time page, the NCR smart button and the chatter;
- the NCR form contains `<chatter/>`;
- the demo NCRs are in open/mrb/closed/draft;
- the quality manager group shows as "Aerospace Quality / Quality Manager (MRB)" with admin in `all_user_ids`;
- NCR quantity digits are (16, 2);
- demo lots compute 12 h / 250 h (expired) / 2 h of out-time;
- the NCR PDF renders.

**Not done:** clicking through the UI as a user. Real UAT needs key users running their own scenarios.

## Step 5. Dress rehearsal: database upgrade with OpenUpgrade

Community has no official upgrade service, so I used OCA OpenUpgrade. Both `18.0` and `19.0` branches
exist and list every installed standard module in their coverage tables (step 1). Runs used the `rehearsal_restored` copy,
`--load=base,web,openupgrade_framework -u all`, and small local images `FROM odoo:1x.0` +
`pip install openupgradelib` (3.13.7).

**Our modules need an intermediate 18.0 version.** A database can only go one major version at a time,
and at the 18 step the 17 code would not load. I built it from `main` (not committed; the recipe is below)
using only what 18.0 already needs, each item checked against the 18.0 source:
- `<tree>` -> `<list>`;
- `detailed_type` -> `type` + `is_storable`;
- chatter div -> `<chatter/>` (18 already only compiles `<chatter/>`);
- version `18.0.1.0.0`.

Everything else in the 19 port is 19-only. In 18.0, `expand` on search groups, the lot form notebook,
`res.groups.category_id`/`users`, `groups_id`, `stock.location.comment`, `stock.move.name`, the
"Product Unit of Measure" precision and `_sql_constraints` all still exist. On a fresh 18 DB this
build passes **23/23** tests.

| Run | Duration | Outcome |
|---|---:|---|
| 17->18, attempt 1 | 3 s | **Failed**: `PermissionError: [Errno 13] Permission denied: '/var/lib/odoo/filestore/ou_step18/checklist/...'`. The `odoo` user is uid **101** in `odoo:17.0` but uid **100** in `odoo:18.0` and `odoo:19.0`, so files written by 17 are not writable by 18. Fix: `chown -R 100:101` on the copied filestore |
| 17->18, attempt 2 | 66 s | Completed, but OpenUpgrade **turns a demo DB into a non-demo DB** unless `OPENUPGRADE_USE_DEMO=yes` (framework README): res_partner 43 -> 16, attachment files 947 -> 851, 5 deletions blocked by foreign keys. Not a problem for a production DB, but it ruins the reconciliation of this rehearsal |
| 17->18, attempt 3 (`OPENUPGRADE_USE_DEMO=yes`) | **67 s** | Completed. `ERROR ... inconsistent states: spreadsheet_dashboard_purchase_oca, spreadsheet_dashboard_purchase_stock_oca` (renamed by apriori to OCA modules that are not in the addons path; left in "to upgrade") |
| 18->19, attempt 1 | 36 s | **Failed** in `purchase`: `psycopg2.errors.InvalidParameterValue: cannot cast jsonb numeric to type boolean` on `res_partner.receipt_reminder_email` |
| 18->19, attempt 2 (after SQL fix) | **72 s** | Completed. Remaining ERROR lines: mail demo data, `chart template False unknown` (the sandbox company has no chart of accounts), the two `*_oca` modules |

Root cause of the 18->19 crash: in 17, company-dependent fields lived in `ir_property`, with booleans
stored in `value_integer`. `openupgradelib.openupgrade_180.convert_company_dependent()` maps `boolean`
to `value_integer` and copies it into the new jsonb column as a number: `{"1": 1}` instead of
`{"1": true}`. Odoo 18 reads that; Odoo 19 builds `(jsonb)::bool` and PostgreSQL refuses. The 19.0
OpenUpgrade scripts contain nothing that handles it. Workaround, run between the two steps:
`docs/migration-rehearsal/fix_company_dependent_booleans.sql`. It is generic for all boolean
company-dependent fields; here it fixed 3 rows (demo vendors with receipt reminders), and 0 rows for
`ignore_abnormal_invoice_amount/date`. This is worth reporting upstream.

**Reconciliation** (full CSVs in `docs/migration-rehearsal/`):

| Metric | 17 (source) | after 18 | after 19 |
|---|---:|---:|---:|
| res_partner (all / active) | 43 / 39 | 44 / 40 | 45 / 41 |
| product_product | 68 | 68 | 68 |
| stock_lot | 20 | 20 | 20 |
| stock_move done | 56 | 56 | 56 |
| stock_move all | 93 | 93 | 129 |
| stock_quant rows internal / sum(quantity) | 43 / 1,554 | 43 / 1,554 | 45 / 1,554 |
| aero_outtime_event | 4 | 4 | 4 |
| aero_ncr open/mrb/dispositioned/closed | 1/1/1/1 | 1/1/1/1 | 1/1/1/1 |
| mrp_production draft/confirmed/done | 1/2/3 | 1/2/3 | 1/2/3 |
| purchase_order draft/sent/purchase | 6/1/4 | 6/1/4 | 6/1/4 |
| ir_attachment rows with a file | 947 | 991 | 1,020 |
| per product/location quantities | 43 rows | identical | identical + 2 new rows with NULL quantity |
| DB size | 53 MB | 65 MB | 72 MB |

Every difference was traced to records created during the upgrade itself. They are new demo data of
18/19, loaded because of `OPENUPGRADE_USE_DEMO=yes`:
- new partners "OpenWood" (`base.res_partner_5`, 18) and "LightsUp" (`base.res_partner_6`, 19), both
  with demo XML ids (verified);
- files at 18: net +44. 48 attachments with files were created during the run (40 payment method
  images, 2 payment provider images, 5 image sizes of one partner, 1 spreadsheet dashboard), so about
  4 were replaced or removed; I did not itemise those. The net +29 at 19 was not itemised either;
- 36 new **draft** moves without origin, created during the 19 run;
- 2 new quants (products 5 and 19, WH/Stock), created during the 19 run, that only carry
  `inventory_quantity` and have `quantity` NULL.

That the moves and quants are demo data is my inference from their creation time and content; I did
not trace them to a specific demo file.

Done moves, on-hand quantities, lots, NCRs, out-time events, MOs and POs are unchanged. Our custom
tables came through with the 19.0.1.0.0 modules. On the upgraded DB:
- `-u aero_material_outtime,aero_ncr_mrb --test-tags` gives **23/23** tests passing (8 s);
- all 1,020 attachment files exist and match their SHA-1.

**Neutralisation does not survive an upgrade.** After 17->18 there were 3 active crons (new in 18:
"Mail: Post scheduled messages", "Discuss: users settings unmute"). After 18->19 there were 3 again
(new: "Stock Account: Inventory Valuation Closing"). `database.is_neutralized` stayed `true` and the
dummy mail server stayed. Re-running `odoo neutralize` (19 image) brought active crons back to 1.

## Step 6. Go / no-go

Based on this rehearsal only:

| Criterion | Status |
|---|---|
| Custom modules install and pass tests on 19 | Yes (7/7, 16/16; 23/23 on the upgraded DB) |
| Standard modules covered by OpenUpgrade | Yes, with 2 dashboard modules to uninstall before or add from OCA |
| Business data reconciles | Yes (differences traced to demo data only) |
| Upgrade needs manual fixes | Yes: filestore uid, demo flag (rehearsal only), jsonb boolean SQL |
| Rollback tested | Yes, 12.7 s for this size |
| UI acceptance by users | **Not done** |

For a real company this would be a **no-go until**:
- key users have done UAT on an upgraded copy of production;
- the two `spreadsheet_dashboard_purchase*` modules are dealt with;
- the jsonb fix is scripted and has passed a second full rehearsal without manual steps.

## Step 7. Cutover (what it would be)

Not executed; this is the plan the rehearsal supports:
1. Announce the freeze. Stop Odoo workers and crons on 17 (see the cron finding in 2.1).
2. Final backup (DB + filestore) and checksums. Keep it as the rollback point.
3. Restore into the upgrade environment, `chown` the filestore to the target image's uid, uninstall or
   replace the `*_oca` dashboards.
4. OpenUpgrade 17->18 with the 18.0 build of our modules, then the jsonb boolean fix, then 18->19 with
   the 19.0 modules. Do not set `OPENUPGRADE_USE_DEMO` on production.
5. Re-run the snapshot SQL and compare. Re-run the module tests on the upgraded DB.
6. Production is not neutralised, but a staging copy must be re-neutralised after every upgrade.
7. Smoke test by key users, then go live or restore the backup.

## Step 8. Hypercare (what it would be)

- First days: watch the server logs for `ERROR`/`WARNING` from our modules, failed crons (the new 18/19
  crons start active), and mail queue errors.
- Check the silent regressions from this rehearsal: chatter on NCRs, NCR quantity precision, the empty
  Reference column on quarantine moves.
- After some weeks: clean up the legacy columns OpenUpgrade keeps (`openupgrade_legacy_*`, "Not
  dropping the column ..." warnings) with `database_cleanup`, once no one needs them.

---

## What I would do differently in production

- **Freeze the source first.** A cron changed `dev` between copy and snapshot. Take the final dump
  with workers and crons stopped, and snapshot the same dump you upgrade.
- **Make test scripts fail loudly.** Odoo 19 skips a module with the wrong version and ends green with
  0 tests, and broken demo data is only a WARNING. CI must check the number of tests and the module
  state, not only the exit code.
- **Never rewrite code that a running instance is serving.** Use a separate worktree/checkout for the
  port.
- **Script every manual step**, including the one-off ones (filestore `chown`, jsonb boolean fix,
  dashboard modules), and repeat the whole rehearsal until it runs end to end without hands on the
  keyboard. Then time it on a production-size copy: 53 MB and 17 MB of files says nothing about a
  real database.
- **Keep an intermediate branch for each hop** (`18.0` build of our modules) under version control.
  In this rehearsal it lived only in a scratch folder.
- **Re-neutralise after each upgrade step** on any non-production copy.
- **Restore into an empty temporary directory**, never into the live filestore root.
- **Do UAT with real users** on the upgraded copy. Source review found 3 silent problems that all
  23 tests missed.
- Use `pg_restore -j` (from a dump file) on a real database: the DB restore was about 12x slower than the
  dump here and is the rollback bottleneck.

## Recipe: intermediate 18.0 build of the modules (not committed)

From `main`: run `odoo upgrade_code --script 17.5-01-tree-to-list` (19 image) on the modules; in demo
XML and tests replace `detailed_type="product"` with `type="consu"` + `is_storable=True`; replace the
NCR form's chatter div with `<chatter/>`; set both manifests to `18.0.1.0.0`.
