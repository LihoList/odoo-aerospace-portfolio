from odoo import api, fields, models
from odoo.exceptions import UserError


class StockLot(models.Model):
    _inherit = "stock.lot"

    outtime_limit_h = fields.Float(
        "Out-time limit (h)",
        tracking=True,
        help="Maximum cumulative time this lot may spend outside the freezer "
        "(from the material specification). 0 = not out-time controlled.",
    )
    outtime_event_ids = fields.One2many(
        "aero.outtime.event", "lot_id", string="Out-time log"
    )
    outtime_used_h = fields.Float("Out-time used (h)", compute="_compute_outtime")
    outtime_remaining_h = fields.Float(
        "Out-time remaining (h)", compute="_compute_outtime"
    )
    outtime_expired = fields.Boolean("Out-time exceeded", compute="_compute_outtime")
    outtime_open = fields.Boolean(
        "Currently out of freezer", compute="_compute_outtime"
    )

    @api.depends(
        "outtime_limit_h",
        "outtime_event_ids.date_out",
        "outtime_event_ids.date_in",
    )
    def _compute_outtime(self):
        # Not stored on purpose: an open interval keeps growing with the clock,
        # so a stored value would be stale the moment it is written.
        now = fields.Datetime.now()
        for lot in self:
            used = 0.0
            is_open = False
            for event in lot.outtime_event_ids:
                if not event.date_out:
                    continue
                if not event.date_in:
                    is_open = True
                end = event.date_in or now
                used += (end - event.date_out).total_seconds() / 3600.0
            limit = lot.outtime_limit_h
            lot.outtime_used_h = used
            lot.outtime_remaining_h = max(limit - used, 0.0) if limit else 0.0
            lot.outtime_expired = bool(limit) and used >= limit
            lot.outtime_open = is_open

    def action_outtime_remove(self):
        """Button: log a freezer removal (opens a new interval)."""
        now = fields.Datetime.now()
        for lot in self:
            if lot.outtime_open:
                raise UserError(
                    self.env._(
                        "Lot %s is already out of the freezer.", lot.display_name
                    )
                )
            self.env["aero.outtime.event"].create({"lot_id": lot.id, "date_out": now})
        return True

    def action_outtime_return(self):
        """Button: close the open interval (material back in the freezer)."""
        now = fields.Datetime.now()
        for lot in self:
            open_events = lot.outtime_event_ids.filtered(lambda e: not e.date_in)
            if not open_events:
                raise UserError(
                    self.env._("Lot %s is not out of the freezer.", lot.display_name)
                )
            open_events.write({"date_in": now})
        return True
