from odoo import api, fields, models


class StockLot(models.Model):
    _inherit = "stock.lot"

    ncr_ids = fields.One2many("aero.ncr", "lot_id", string="Nonconformances")
    ncr_count = fields.Integer(compute="_compute_ncr_count")

    @api.depends("ncr_ids.state")
    def _compute_ncr_count(self):
        for lot in self:
            lot.ncr_count = len(lot.ncr_ids.filtered(lambda n: n.state != "cancel"))

    def action_view_ncrs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("NCRs of %s", self.name),
            "res_model": "aero.ncr",
            "view_mode": "list,form",
            "domain": [("lot_id", "=", self.id)],
            "context": {
                "default_lot_id": self.id,
                "default_product_id": self.product_id.id,
            },
        }
