from odoo import _, models
from odoo.exceptions import UserError


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    def button_mark_done(self):
        """Refuse to close a manufacturing order that consumed an expired lot.

        The check runs before the standard flow (consumption / backorder
        wizards) so the operator gets one clear message and nothing is posted.
        """
        for production in self:
            expired = production.move_raw_ids.move_line_ids.lot_id.filtered(
                "outtime_expired"
            )
            if expired:
                raise UserError(
                    _(
                        "Out-time exceeded, consumption blocked for lot(s): %s. "
                        "Raise a nonconformance and quarantine the material."
                    )
                    % ", ".join(expired.mapped("name"))
                )
        return super().button_mark_done()
