# Aero Nonconformance & MRB (Odoo 17)

**Business problem.** AS9100 8.7 requires that nonconforming product is
identified, segregated, dispositioned by an authorised board and recorded with
the decision and its justification. In most shops this lives in a spreadsheet
and a red tag; the ERP does not know the material is unusable.

**What the module does.**
- `aero.ncr`: nonconformance report against a product/lot with source,
  severity, defect type (configurable taxonomy) and requirement vs. actual.
- **Submit & quarantine**: the nonconforming quantity is moved (done internal
  move, lot-specific) into a *Quarantine* location, so it cannot be issued.
- **MRB review**: the Quality Manager records a disposition. *Use as is* and
  *repair* require **Engineering Authority** approval first (design authority).
- **Apply disposition** triggers the stock action:
  scrap -> validated `stock.scrap`; return -> outgoing transfer to the supplier
  reserving exactly that lot; use-as-is / rework / repair -> release back to
  stock, production manager gets an activity for rework/repair.
- **Close**: major/critical NCRs cannot close without root cause and
  corrective action; a return cannot close until the transfer is done.
- Chatter tracking on every decision field, printable NCR PDF, smart button on
  the lot, list/graph/pivot analysis by defect type, disposition and month.

**Security model (the interesting part).** Three groups: *NCR User*
(raise/submit), *Engineering Authority* (approve use-as-is/repair), *Quality
Manager* (MRB, close). Group checks are enforced in Python (`write()` and every
action), not only via `groups=` on buttons, because every public method and
field is reachable over RPC. Multi-company record rule included. No `sudo()`.

**Demo (3 minutes).** Quality > Nonconformances: one NCR quarantined and
waiting for MRB, one in review with *use as is* proposed (try *Apply
disposition* before *Engineering approval*), one scrapped and closed with CAPA.
Open the lot TI-2408-017 to see the NCR smart button and the quarantine move.

**Design decisions.**
- Quarantine is an *internal* location, not a scrap location: the material is
  still an asset and still counted until the MRB says otherwise.
- Stock effects reuse standard objects (`stock.move`, `stock.scrap`,
  `stock.picking`) so traceability reports and valuation keep working.
- The workflow is explicit states + buttons instead of a generic approval
  engine; cheaper to audit and to migrate.
- Not built (documented): CAPA as a separate object with effectiveness review,
  customer notification for escapes, 8D report.

**Tests.** `scripts/test.sh aero_ncr_mrb`: 16 tests covering quantities in
each location after every transition, the access model with three users, the
engineering gate, CAPA gate, return picking and PDF rendering.
