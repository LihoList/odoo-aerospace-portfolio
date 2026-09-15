# Aero Material Out-time (Odoo 17)

**Business problem.** Composite prepregs, film adhesives and sealants are stored
frozen and carry a cumulative *out-time* limit (hours outside the freezer,
from the material spec). Exceeding it means the material must be scrapped or
dispositioned through MRB. On paper this is tracked with freezer log sheets and
is a classic AS9100 audit finding.

**What the module does.**
- Adds an *Out-time limit* to every lot (`stock.lot`) and a log of freezer
  removals/returns (`aero.outtime.event`) with "Remove from freezer" /
  "Return to freezer" buttons on the lot form.
- Computes used / remaining out-time live (an open interval keeps counting).
- Blocks *Mark as Done* on a manufacturing order that consumed an expired lot,
  with a message telling the operator to raise a nonconformance.
- Shows remaining out-time and the expired flag in the lot list; a menu
  *Inventory > Products > Out-time log* lists every interval.

**Demo (2 minutes).**
1. Inventory > Products > Lots/Serial Numbers > pick a prepreg lot, set
   *Out-time limit* = 10:00, save.
2. Click *Remove from freezer*. Remaining out-time starts dropping.
3. Manufacturing > create an MO for a panel that uses that lot, *Mark as Done*
   -> blocked with the lot name once the lot is over its limit.

**Design decisions.**
- Used/remaining hours are *not stored*: an open interval grows with the clock,
  so a stored value would be stale immediately. Search/grouping on volume would
  use a cron-refreshed stored field instead (documented, not built).
- The block is in `button_mark_done` (the operator-facing action), before the
  standard consumption/backorder wizards, so the message is unambiguous.
- Only inheritance and `@name` xpath anchors: nothing in core is touched, so
  the module is cheap to carry across 17 -> 18 -> 19.

**Tests.** `scripts/test.sh aero_material_outtime` installs the module on a
fresh database and runs 7 tests: interval arithmetic, buttons, the SQL
constraint, and a real MO that is blocked / completes.
