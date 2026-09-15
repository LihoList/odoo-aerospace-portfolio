from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestNcr(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.stock_loc = cls.warehouse.lot_stock_id
        cls.quarantine = cls.env.ref("aero_ncr_mrb.location_quarantine")
        cls.supplier_loc = cls.env.ref("stock.stock_location_suppliers")
        cls.Quant = cls.env["stock.quant"]

        def user(login, groups):
            return cls.env["res.users"].create(
                {
                    "name": login,
                    "login": login,
                    "email": f"{login}@example.com",
                    "groups_id": [(6, 0, [cls.env.ref(g).id for g in groups])],
                }
            )

        cls.ncr_user = user("ncr_user", ["aero_ncr_mrb.group_aero_ncr_user"])
        cls.engineer = user("ncr_engineer", ["aero_ncr_mrb.group_aero_engineering"])
        cls.manager = user(
            "ncr_manager",
            ["aero_ncr_mrb.group_aero_quality_manager", "mrp.group_mrp_manager"],
        )

        cls.supplier = cls.env["res.partner"].create(
            {"name": "Northern Alloys (synthetic)"}
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Ti bar (synthetic)",
                "detailed_type": "product",
                "tracking": "lot",
            }
        )
        cls.lot = cls.env["stock.lot"].create(
            {
                "name": "TI-0001",
                "product_id": cls.product.id,
                "company_id": cls.company.id,
            }
        )
        cls.Quant._update_available_quantity(
            cls.product, cls.stock_loc, 10.0, lot_id=cls.lot
        )
        cls.defect = cls.env.ref("aero_ncr_mrb.defect_dim")

    # ---- helpers -----------------------------------------------------------

    def _qty(self, location, lot=None):
        return self.Quant._get_available_quantity(
            self.product, location, lot_id=lot or self.lot, strict=True
        )

    def _ncr(self, user=None, **vals):
        base = {
            "product_id": self.product.id,
            "lot_id": self.lot.id,
            "qty_nonconforming": 3.0,
            "defect_type_id": self.defect.id,
            "description": "OD 24.7 mm vs 25.0 +/-0.1 (synthetic)",
            "partner_id": self.supplier.id,
        }
        base.update(vals)
        return self.env["aero.ncr"].with_user(user or self.ncr_user).create(base)

    def _to_mrb(self, ncr):
        ncr.with_user(self.ncr_user).action_submit()
        ncr.with_user(self.manager).action_start_mrb()
        return ncr.with_user(self.manager)

    # ---- basics ------------------------------------------------------------

    def test_sequence_and_defaults(self):
        ncr = self._ncr()
        self.assertTrue(ncr.name.startswith("NCR/"))
        self.assertEqual(ncr.state, "draft")
        self.assertEqual(ncr.detected_by_id, self.ncr_user)

    def test_quantity_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self._ncr(qty_nonconforming=0)

    def test_lot_must_match_product(self):
        other = self.env["product.product"].create(
            {"name": "Other", "detailed_type": "product", "tracking": "lot"}
        )
        with self.assertRaises(ValidationError):
            self._ncr(product_id=other.id)

    def test_tracked_product_needs_lot_on_submit(self):
        ncr = self._ncr(lot_id=False)
        with self.assertRaises(UserError):
            ncr.action_submit()

    # ---- quarantine --------------------------------------------------------

    def test_submit_moves_material_to_quarantine(self):
        ncr = self._ncr()
        ncr.action_submit()
        self.assertEqual(ncr.state, "open")
        self.assertEqual(ncr.quarantine_move_id.state, "done")
        self.assertAlmostEqual(self._qty(self.quarantine), 3.0)
        self.assertAlmostEqual(self._qty(self.stock_loc), 7.0)
        self.assertTrue(ncr.activity_ids, "quality managers should get an activity")

    def test_cancel_releases_quarantine(self):
        ncr = self._ncr()
        ncr.action_submit()
        ncr.with_user(self.manager).action_cancel()
        self.assertEqual(ncr.state, "cancel")
        self.assertAlmostEqual(self._qty(self.quarantine), 0.0)
        self.assertAlmostEqual(self._qty(self.stock_loc), 10.0)

    # ---- access model ------------------------------------------------------

    def test_plain_user_cannot_run_mrb(self):
        ncr = self._ncr()
        ncr.action_submit()
        with self.assertRaises(AccessError):
            ncr.action_start_mrb()  # still as ncr_user
        with self.assertRaises(AccessError):
            ncr.write(
                {"disposition": "scrap"}
            )  # RPC-level protection, not just the view

    def test_plain_user_cannot_delete(self):
        ncr = self._ncr()
        with self.assertRaises(AccessError):
            ncr.unlink()  # ACL: NCR users have no unlink right

    def test_submitted_ncr_cannot_be_deleted_even_by_manager(self):
        ncr = self._ncr()
        ncr.action_submit()
        with self.assertRaises(UserError):
            ncr.with_user(
                self.manager
            ).unlink()  # keep the record: close or cancel instead

    # ---- dispositions ------------------------------------------------------

    def test_scrap_disposition_and_close(self):
        ncr = self._to_mrb(self._ncr())
        ncr.write({"disposition": "scrap", "disposition_note": "Not repairable"})
        ncr.action_disposition()
        self.assertEqual(ncr.state, "dispositioned")
        self.assertEqual(ncr.scrap_id.state, "done")
        self.assertAlmostEqual(self._qty(self.quarantine), 0.0)
        self.assertAlmostEqual(self._qty(ncr.scrap_id.scrap_location_id), 3.0)
        ncr.action_close()
        self.assertEqual(ncr.state, "closed")
        self.assertEqual(ncr.closed_by_id, self.manager)

    def test_use_as_is_requires_engineering_then_releases(self):
        ncr = self._to_mrb(self._ncr())
        ncr.write({"disposition": "use_as_is"})
        with self.assertRaises(UserError):
            ncr.action_disposition()
        with self.assertRaises(AccessError):
            ncr.action_engineering_approve()  # manager is not engineering authority
        ncr.with_user(self.engineer).action_engineering_approve()
        self.assertEqual(ncr.eng_approver_id, self.engineer)
        ncr.action_disposition()
        self.assertEqual(ncr.release_move_id.state, "done")
        self.assertAlmostEqual(self._qty(self.quarantine), 0.0)
        self.assertAlmostEqual(self._qty(self.stock_loc), 10.0)

    def test_rework_releases_and_notifies_production(self):
        ncr = self._to_mrb(self._ncr())
        ncr.write({"disposition": "rework", "disposition_note": "Re-machine OD"})
        ncr.action_disposition()
        self.assertAlmostEqual(self._qty(self.stock_loc), 10.0)
        self.assertIn(
            self.manager,
            ncr.activity_ids.user_id,
            "production manager gets the rework activity",
        )

    def test_return_to_supplier_creates_picking(self):
        ncr = self._to_mrb(self._ncr())
        ncr.write({"disposition": "return"})
        ncr.action_disposition()
        picking = ncr.return_picking_id
        self.assertEqual(picking.location_dest_id, self.supplier_loc)
        self.assertEqual(picking.partner_id, self.supplier)
        self.assertEqual(picking.move_ids.move_line_ids.lot_id, self.lot)
        with self.assertRaises(UserError):
            ncr.action_close()  # not shipped yet
        picking.move_ids.picked = True
        picking.button_validate()
        self.assertEqual(picking.state, "done")
        self.assertAlmostEqual(self._qty(self.quarantine), 0.0)
        ncr.action_close()
        self.assertEqual(ncr.state, "closed")

    def test_major_needs_root_cause_and_capa(self):
        ncr = self._to_mrb(self._ncr(severity="major"))
        ncr.write({"disposition": "scrap"})
        ncr.action_disposition()
        with self.assertRaises(UserError):
            ncr.action_close()
        ncr.write(
            {
                "root_cause": "Worn insert",
                "corrective_action": "Insert change interval halved",
            }
        )
        ncr.action_close()
        self.assertEqual(ncr.state, "closed")

    # ---- report & lot link -------------------------------------------------

    def test_report_renders(self):
        ncr = self._to_mrb(self._ncr())
        html, _type = self.env["ir.actions.report"]._render_qweb_html(
            "aero_ncr_mrb.report_ncr", ncr.ids
        )
        self.assertIn(ncr.name.encode(), html)

    def test_lot_smart_button_count(self):
        ncr = self._ncr()
        self.assertEqual(self.lot.ncr_count, 1)
        ncr.with_user(self.manager).action_cancel()
        self.assertEqual(self.lot.ncr_count, 0)
