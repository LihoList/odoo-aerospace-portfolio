from datetime import timedelta

from psycopg2 import IntegrityError

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestOuttime(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Event = cls.env["aero.outtime.event"]
        cls.prepreg = cls.env["product.product"].create(
            {
                "name": "Prepreg PX-100 (synthetic)",
                "detailed_type": "product",
                "tracking": "lot",
            }
        )
        cls.panel = cls.env["product.product"].create(
            {"name": "Composite Panel (synthetic)", "detailed_type": "product"}
        )
        cls.bom = cls.env["mrp.bom"].create(
            {
                "product_tmpl_id": cls.panel.product_tmpl_id.id,
                "product_qty": 1.0,
                "type": "normal",
                "bom_line_ids": [
                    (0, 0, {"product_id": cls.prepreg.id, "product_qty": 1.0})
                ],
            }
        )

    # ---- helpers -----------------------------------------------------------

    def _lot(self, name="PP-0001", limit=10.0):
        return self.env["stock.lot"].create(
            {
                "name": name,
                "product_id": self.prepreg.id,
                "company_id": self.env.company.id,
                "outtime_limit_h": limit,
            }
        )

    def _event(self, lot, hours_ago_out, hours_ago_in=None):
        now = fields.Datetime.now()
        vals = {"lot_id": lot.id, "date_out": now - timedelta(hours=hours_ago_out)}
        if hours_ago_in is not None:
            vals["date_in"] = now - timedelta(hours=hours_ago_in)
        return self.Event.create(vals)

    def _mo_consuming(self, lot):
        """A confirmed MO for one panel whose prepreg component is picked from `lot`."""
        mo = self.env["mrp.production"].create(
            {"product_id": self.panel.id, "product_qty": 1.0, "bom_id": self.bom.id}
        )
        mo.action_confirm()
        mo.qty_producing = 1.0
        raw = mo.move_raw_ids
        self.assertEqual(len(raw), 1, "BoM should give exactly one raw move")
        self.env["stock.move.line"].create(
            {
                "move_id": raw.id,
                "product_id": self.prepreg.id,
                "product_uom_id": self.prepreg.uom_id.id,
                "lot_id": lot.id,
                "quantity": 1.0,
                "location_id": raw.location_id.id,
                "location_dest_id": raw.location_dest_id.id,
            }
        )
        raw.picked = True
        return mo

    # ---- out-time arithmetic ----------------------------------------------

    def test_closed_intervals_sum_up(self):
        lot = self._lot()
        self._event(lot, 8, 4)  # 4 h
        self._event(lot, 3, 0)  # 3 h
        self.assertAlmostEqual(lot.outtime_used_h, 7.0, places=2)
        self.assertAlmostEqual(lot.outtime_remaining_h, 3.0, places=2)
        self.assertFalse(lot.outtime_expired)
        self.assertFalse(lot.outtime_open)

    def test_open_interval_counts_until_now(self):
        lot = self._lot()
        self._event(lot, 12)  # still out, 12 h > 10 h limit
        self.assertTrue(lot.outtime_open)
        self.assertTrue(lot.outtime_expired)
        self.assertAlmostEqual(lot.outtime_remaining_h, 0.0, places=2)

    def test_no_limit_means_not_tracked(self):
        lot = self._lot(limit=0.0)
        self._event(lot, 100)
        self.assertFalse(lot.outtime_expired)
        self.assertAlmostEqual(lot.outtime_remaining_h, 0.0, places=2)

    # ---- buttons -----------------------------------------------------------

    def test_remove_and_return_buttons(self):
        lot = self._lot()
        lot.action_outtime_remove()
        self.assertTrue(lot.outtime_open)
        with self.assertRaises(UserError):
            lot.action_outtime_remove()  # already out
        lot.action_outtime_return()
        self.assertFalse(lot.outtime_open)
        with self.assertRaises(UserError):
            lot.action_outtime_return()  # nothing to return
        self.assertEqual(len(lot.outtime_event_ids), 1)

    # ---- data integrity ----------------------------------------------------

    def test_return_before_removal_is_rejected(self):
        lot = self._lot()
        now = fields.Datetime.now()
        with (
            self.assertRaises(IntegrityError),
            mute_logger("odoo.sql_db"),
            self.cr.savepoint(),
        ):
            self.Event.create(
                {"lot_id": lot.id, "date_out": now, "date_in": now - timedelta(hours=1)}
            )

    # ---- production blocking ----------------------------------------------

    def test_expired_lot_blocks_mo_completion(self):
        lot = self._lot()
        self._event(lot, 12)  # expired
        mo = self._mo_consuming(lot)
        with self.assertRaises(UserError) as cm:
            mo.button_mark_done()
        self.assertIn("PP-0001", str(cm.exception))
        self.assertNotEqual(mo.state, "done")

    def test_fresh_lot_mo_completes(self):
        lot = self._lot()
        self._event(lot, 3, 1)  # 2 h used of 10
        mo = self._mo_consuming(lot)
        mo.button_mark_done()
        self.assertEqual(mo.state, "done")
