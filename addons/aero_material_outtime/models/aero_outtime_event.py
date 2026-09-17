from odoo import api, fields, models


class AeroOuttimeEvent(models.Model):
    """One interval a lot spent outside the freezer.

    An event with no ``date_in`` is still "open": the lot is on the shop floor
    right now and its out-time keeps counting until it is returned.
    """

    _name = "aero.outtime.event"
    _description = "Material out-of-freezer interval"
    _order = "date_out desc, id desc"

    lot_id = fields.Many2one(
        "stock.lot", required=True, ondelete="cascade", index=True, string="Lot"
    )
    product_id = fields.Many2one(related="lot_id.product_id", store=True)
    company_id = fields.Many2one(related="lot_id.company_id", store=True)
    date_out = fields.Datetime(
        "Removed from freezer", required=True, default=fields.Datetime.now
    )
    date_in = fields.Datetime("Returned to freezer")
    duration_h = fields.Float("Duration (h)", compute="_compute_duration_h", store=True)
    user_id = fields.Many2one(
        "res.users", "Logged by", default=lambda self: self.env.user, readonly=True
    )
    note = fields.Char("Reason / work order")

    _check_dates = models.Constraint(
        "CHECK(date_in IS NULL OR date_in >= date_out)",
        "Return time must be after removal time.",
    )

    @api.depends("date_out", "date_in")
    def _compute_duration_h(self):
        for event in self:
            if event.date_out and event.date_in:
                delta = event.date_in - event.date_out
                event.duration_h = delta.total_seconds() / 3600.0
            else:
                event.duration_h = 0.0
