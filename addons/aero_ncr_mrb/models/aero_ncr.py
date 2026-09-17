from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

GROUP_USER = "aero_ncr_mrb.group_aero_ncr_user"
GROUP_MANAGER = "aero_ncr_mrb.group_aero_quality_manager"
GROUP_ENGINEERING = "aero_ncr_mrb.group_aero_engineering"

# Fields only the MRB (quality manager) may write. Enforced in write(), not
# only in the view: anything reachable through RPC must be protected in Python.
MRB_FIELDS = {"disposition", "disposition_note", "root_cause", "corrective_action"}


class AeroNcr(models.Model):
    _name = "aero.ncr"
    _description = "Nonconformance Report"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_detected desc, id desc"
    _check_company_auto = True

    # ---- identification ----------------------------------------------------
    name = fields.Char(default="New", copy=False, readonly=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("open", "Quarantined"),
            ("mrb", "MRB review"),
            ("dispositioned", "Dispositioned"),
            ("closed", "Closed"),
            ("cancel", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
        copy=False,
    )
    severity = fields.Selection(
        [("minor", "Minor"), ("major", "Major"), ("critical", "Critical")],
        default="minor",
        required=True,
        tracking=True,
    )
    source = fields.Selection(
        [
            ("receiving", "Receiving inspection"),
            ("in_process", "In-process"),
            ("final", "Final inspection"),
            ("customer", "Customer return"),
            ("audit", "Audit / other"),
        ],
        default="in_process",
        required=True,
        tracking=True,
    )

    # ---- what is nonconforming ---------------------------------------------
    product_id = fields.Many2one(
        "product.product", required=True, check_company=True, tracking=True
    )
    product_uom_id = fields.Many2one(related="product_id.uom_id")
    tracking = fields.Selection(related="product_id.tracking")
    lot_id = fields.Many2one(
        "stock.lot",
        "Lot / Serial",
        domain="[('product_id', '=', product_id)]",
        check_company=True,
        tracking=True,
    )
    qty_nonconforming = fields.Float(
        "Quantity",
        required=True,
        default=1.0,
        # 19: decimal precision "Product Unit of Measure" was renamed "Product Unit"
        digits="Product Unit",
        tracking=True,
    )
    defect_type_id = fields.Many2one(
        "aero.ncr.defect.type", required=True, tracking=True
    )
    requirement = fields.Char("Requirement / drawing ref")
    description = fields.Text("Nonconformance (requirement vs. actual)", required=True)
    date_detected = fields.Datetime(default=fields.Datetime.now, required=True)
    detected_by_id = fields.Many2one(
        "res.users", "Detected by", default=lambda self: self.env.user, readonly=True
    )
    production_id = fields.Many2one(
        "mrp.production", "Manufacturing order", check_company=True
    )
    picking_id = fields.Many2one("stock.picking", "Transfer", check_company=True)
    partner_id = fields.Many2one("res.partner", "Supplier / customer")

    # ---- MRB decision ------------------------------------------------------
    disposition = fields.Selection(
        [
            ("use_as_is", "Use as is"),
            ("rework", "Rework"),
            ("repair", "Repair"),
            ("scrap", "Scrap"),
            ("return", "Return to supplier"),
        ],
        tracking=True,
        copy=False,
    )
    disposition_note = fields.Text("MRB rationale / instructions")
    requires_engineering = fields.Boolean(compute="_compute_requires_engineering")
    mrb_user_id = fields.Many2one("res.users", "MRB chair", readonly=True, copy=False)
    mrb_date = fields.Datetime("MRB date", readonly=True, copy=False)
    eng_approver_id = fields.Many2one(
        "res.users", "Engineering approval", readonly=True, copy=False, tracking=True
    )
    eng_approval_date = fields.Datetime(readonly=True, copy=False)
    root_cause = fields.Text()
    corrective_action = fields.Text("Corrective action (CAPA)")
    closed_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    date_closed = fields.Datetime(readonly=True, copy=False)

    # ---- stock trail -------------------------------------------------------
    quarantine_move_id = fields.Many2one("stock.move", readonly=True, copy=False)
    release_move_id = fields.Many2one("stock.move", readonly=True, copy=False)
    scrap_id = fields.Many2one("stock.scrap", readonly=True, copy=False)
    return_picking_id = fields.Many2one(
        "stock.picking", "Return transfer", readonly=True, copy=False
    )
    stock_move_count = fields.Integer(compute="_compute_stock_move_count")

    # ======================================================================
    # computes / constraints
    # ======================================================================
    @api.depends("disposition")
    def _compute_requires_engineering(self):
        # AS9100 8.7: use-as-is and repair need the design authority's approval.
        for ncr in self:
            ncr.requires_engineering = ncr.disposition in ("use_as_is", "repair")

    @api.depends(
        "quarantine_move_id",
        "release_move_id",
        "scrap_id.move_ids",
        "return_picking_id.move_ids",
    )
    def _compute_stock_move_count(self):
        for ncr in self:
            ncr.stock_move_count = len(ncr._get_stock_moves())

    @api.constrains("qty_nonconforming")
    def _check_qty(self):
        for ncr in self:
            # 19: uom.uom.compare() replaces float_compare(precision_rounding=uom.rounding)
            if ncr.product_uom_id.compare(ncr.qty_nonconforming, 0.0) <= 0:
                raise ValidationError(
                    self.env._("The nonconforming quantity must be positive.")
                )

    @api.constrains("lot_id", "product_id")
    def _check_lot_product(self):
        for ncr in self:
            if ncr.lot_id and ncr.lot_id.product_id != ncr.product_id:
                raise ValidationError(
                    self.env._(
                        "Lot %s does not belong to product %s.",
                        ncr.lot_id.name,
                        ncr.product_id.display_name,
                    )
                )

    # ======================================================================
    # CRUD
    # ======================================================================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("aero.ncr") or "New"
        return super().create(vals_list)

    def write(self, vals):
        if MRB_FIELDS & set(vals) and not self.env.user.has_group(GROUP_MANAGER):
            raise AccessError(
                self.env._(
                    "Only the Quality Manager (MRB) can record a disposition, root cause or corrective action."
                )
            )
        return super().write(vals)

    def unlink(self):
        if any(ncr.state not in ("draft", "cancel") for ncr in self):
            raise UserError(
                self.env._(
                    "Only draft or cancelled NCRs can be deleted; close them instead to keep the record."
                )
            )
        return super().unlink()

    # ======================================================================
    # workflow
    # ======================================================================
    def _require_group(self, group_xmlid, what):
        if not self.env.user.has_group(group_xmlid):
            raise AccessError(
                self.env._("Only %s can %s.", self.env.ref(group_xmlid).full_name, what)
            )

    def action_submit(self):
        """Draft -> Quarantined: move the nonconforming quantity into quarantine."""
        for ncr in self:
            if ncr.state != "draft":
                raise UserError(self.env._("Only draft NCRs can be submitted."))
            if ncr.tracking != "none" and not ncr.lot_id:
                raise UserError(
                    self.env._(
                        "Product %s is tracked: select the lot or serial number.",
                        ncr.product_id.display_name,
                    )
                )
            source = ncr._get_source_location()
            ncr.quarantine_move_id = ncr._create_done_move(
                source,
                ncr._get_quarantine_location(),
                self.env._("Quarantine %s", ncr.name),
            )
            ncr.state = "open"
            ncr._notify_quality_managers(
                self.env._(
                    "NCR %s submitted: material quarantined, MRB review needed.",
                    ncr.name,
                )
            )
        return True

    def action_start_mrb(self):
        self._require_group(GROUP_MANAGER, self.env._("open an MRB review"))
        for ncr in self:
            if ncr.state != "open":
                raise UserError(
                    self.env._("Only quarantined NCRs can go to MRB review.")
                )
            ncr.write(
                {
                    "state": "mrb",
                    "mrb_user_id": self.env.uid,
                    "mrb_date": fields.Datetime.now(),
                }
            )
        return True

    def action_engineering_approve(self):
        self._require_group(GROUP_ENGINEERING, self.env._("give engineering approval"))
        for ncr in self:
            if ncr.state != "mrb":
                raise UserError(
                    self.env._("Engineering approval is given during MRB review.")
                )
            if not ncr.requires_engineering:
                raise UserError(
                    self.env._(
                        "Disposition '%s' does not need engineering approval.",
                        ncr.disposition or "-",
                    )
                )
            ncr.write(
                {
                    "eng_approver_id": self.env.uid,
                    "eng_approval_date": fields.Datetime.now(),
                }
            )
            ncr.message_post(
                body=self.env._(
                    "Engineering approval for disposition <b>%s</b>.", ncr.disposition
                )
            )
        return True

    def action_disposition(self):
        """MRB review -> Dispositioned: execute the stock action for the decision."""
        self._require_group(GROUP_MANAGER, self.env._("record an MRB disposition"))
        for ncr in self:
            if ncr.state != "mrb":
                raise UserError(
                    self.env._("Dispositions are recorded during MRB review.")
                )
            if not ncr.disposition:
                raise UserError(self.env._("Select a disposition first."))
            if ncr.requires_engineering and not ncr.eng_approver_id:
                raise UserError(
                    self.env._(
                        "Disposition '%s' requires engineering approval before it can be applied.",
                        ncr.disposition,
                    )
                )
            handler = getattr(ncr, f"_apply_disposition_{ncr.disposition}")
            handler()
            ncr.state = "dispositioned"
        return True

    def action_close(self):
        self._require_group(GROUP_MANAGER, self.env._("close an NCR"))
        for ncr in self:
            if ncr.state != "dispositioned":
                raise UserError(self.env._("Only dispositioned NCRs can be closed."))
            if ncr.severity in ("major", "critical") and not (
                ncr.root_cause and ncr.corrective_action
            ):
                raise UserError(
                    self.env._(
                        "Major and critical NCRs need a root cause and a corrective action before closing."
                    )
                )
            if ncr.disposition == "return" and ncr.return_picking_id.state != "done":
                raise UserError(
                    self.env._(
                        "The return transfer %s must be done before closing.",
                        ncr.return_picking_id.name,
                    )
                )
            ncr.write(
                {
                    "state": "closed",
                    "closed_by_id": self.env.uid,
                    "date_closed": fields.Datetime.now(),
                }
            )
        return True

    def action_cancel(self):
        for ncr in self:
            if ncr.state in ("closed", "cancel"):
                raise UserError(self.env._("Closed NCRs cannot be cancelled."))
            if ncr.state != "draft":
                ncr._require_group(GROUP_MANAGER, self.env._("cancel a submitted NCR"))
            if ncr.state in ("open", "mrb"):
                # material is still in quarantine: put it back where it came from
                ncr.release_move_id = ncr._create_done_move(
                    ncr._get_quarantine_location(),
                    ncr.quarantine_move_id.location_id,
                    self.env._("Release %s (cancelled)", ncr.name),
                )
            ncr.state = "cancel"
        return True

    def action_reset_draft(self):
        self._require_group(GROUP_MANAGER, self.env._("reset an NCR to draft"))
        for ncr in self:
            if ncr.state != "cancel":
                raise UserError(
                    self.env._("Only cancelled NCRs can be reset to draft.")
                )
            ncr.write(
                {
                    "state": "draft",
                    "quarantine_move_id": False,
                    "release_move_id": False,
                }
            )
        return True

    # ---- dispositions --------------------------------------------------------
    def _apply_disposition_scrap(self):
        self.ensure_one()
        scrap = self.env["stock.scrap"].create(
            {
                "product_id": self.product_id.id,
                "product_uom_id": self.product_uom_id.id,
                "lot_id": self.lot_id.id,
                "scrap_qty": self.qty_nonconforming,
                "location_id": self._get_quarantine_location().id,
                "origin": self.name,
                "company_id": self.company_id.id,
            }
        )
        res = scrap.action_validate()
        if res is not True:
            # stock.scrap returned its "insufficient quantity" wizard instead of scrapping
            raise UserError(
                self.env._(
                    "Not enough of %s in quarantine to scrap %s.",
                    self.product_id.display_name,
                    self.qty_nonconforming,
                )
            )
        self.scrap_id = scrap

    def _apply_disposition_return(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(
                self.env._("Set the supplier on the NCR to create the return transfer.")
            )
        warehouse = self._get_warehouse()
        quarantine = self._get_quarantine_location()
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": warehouse.out_type_id.id,
                "partner_id": self.partner_id.id,
                "origin": self.name,
                "location_id": quarantine.id,
                "location_dest_id": self.env.ref("stock.stock_location_suppliers").id,
                "company_id": self.company_id.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "description_picking": self.env._(
                                "Return to supplier %s", self.name
                            ),
                            "product_id": self.product_id.id,
                            "product_uom_qty": self.qty_nonconforming,
                            "product_uom": self.product_uom_id.id,
                            "location_id": quarantine.id,
                            "location_dest_id": self.env.ref(
                                "stock.stock_location_suppliers"
                            ).id,
                            "company_id": self.company_id.id,
                        },
                    )
                ],
            }
        )
        picking.action_confirm()
        if self.lot_id:
            # reserve exactly the nonconforming lot, not "any lot in quarantine"
            move = picking.move_ids
            move.move_line_ids.unlink()
            self.env["stock.move.line"].create(
                {
                    "move_id": move.id,
                    "product_id": self.product_id.id,
                    "product_uom_id": self.product_uom_id.id,
                    "lot_id": self.lot_id.id,
                    "quantity": self.qty_nonconforming,
                    "location_id": quarantine.id,
                    "location_dest_id": move.location_dest_id.id,
                }
            )
        else:
            picking.action_assign()
        self.return_picking_id = picking

    def _release_to_stock(self, label):
        self.ensure_one()
        self.release_move_id = self._create_done_move(
            self._get_quarantine_location(), self.quarantine_move_id.location_id, label
        )

    def _apply_disposition_use_as_is(self):
        self._release_to_stock(self.env._("Release %s (use as is)", self.name))

    def _apply_disposition_rework(self):
        self._release_to_stock(self.env._("Release %s (rework)", self.name))
        self._notify_production(self.env._("Rework per NCR %s", self.name))

    def _apply_disposition_repair(self):
        self._release_to_stock(self.env._("Release %s (repair)", self.name))
        self._notify_production(
            self.env._("Repair per NCR %s (engineering approved)", self.name)
        )

    # ---- stock helpers -----------------------------------------------------
    def _get_warehouse(self):
        self.ensure_one()
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.company_id.id)], limit=1
        )
        if not warehouse:
            raise UserError(
                self.env._("No warehouse configured for %s.", self.company_id.name)
            )
        return warehouse

    def _get_quarantine_location(self):
        self.ensure_one()
        location = self.env.ref(
            "aero_ncr_mrb.location_quarantine", raise_if_not_found=False
        )
        if not location or location.company_id != self.company_id:
            location = self.env["stock.location"].search(
                [
                    ("name", "=", "Quarantine"),
                    ("usage", "=", "internal"),
                    ("company_id", "=", self.company_id.id),
                ],
                limit=1,
            )
        if not location:
            raise UserError(
                self.env._(
                    "No Quarantine location for %s: create an internal location named 'Quarantine'.",
                    self.company_id.name,
                )
            )
        return location

    def _get_source_location(self):
        """Where the nonconforming material physically is: the internal location holding
        the lot (largest quantity wins), else the warehouse stock location."""
        self.ensure_one()
        quarantine = self._get_quarantine_location()
        domain = [
            ("product_id", "=", self.product_id.id),
            ("location_id.usage", "=", "internal"),
            ("location_id", "!=", quarantine.id),
            ("company_id", "=", self.company_id.id),
            ("quantity", ">", 0),
        ]
        if self.lot_id:
            domain.append(("lot_id", "=", self.lot_id.id))
        quants = self.env["stock.quant"].search(domain, order="quantity desc", limit=1)
        return quants.location_id or self._get_warehouse().lot_stock_id

    def _create_done_move(self, location_from, location_to, name):
        """An immediate, done internal move with the lot: the same pattern stock.scrap uses."""
        self.ensure_one()
        move = self.env["stock.move"].create(
            {
                # 19: stock.move has no "name"; the label goes to the picking description
                "description_picking": name,
                "origin": self.name,
                "company_id": self.company_id.id,
                "product_id": self.product_id.id,
                "product_uom": self.product_uom_id.id,
                "product_uom_qty": self.qty_nonconforming,
                "location_id": location_from.id,
                "location_dest_id": location_to.id,
                "picked": True,
                "move_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_id.id,
                            "product_uom_id": self.product_uom_id.id,
                            "quantity": self.qty_nonconforming,
                            "lot_id": self.lot_id.id,
                            "location_id": location_from.id,
                            "location_dest_id": location_to.id,
                        },
                    )
                ],
            }
        )
        move._action_done()
        if move.state != "done":
            raise UserError(self.env._("Stock move %s could not be completed.", name))
        return move

    def _get_stock_moves(self):
        self.ensure_one()
        return (
            self.quarantine_move_id
            | self.release_move_id
            | self.scrap_id.move_ids
            | self.return_picking_id.move_ids
        )

    def action_view_stock_moves(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Stock moves of %s", self.name),
            "res_model": "stock.move",
            "view_mode": "list,form",
            "domain": [("id", "in", self._get_stock_moves().ids)],
        }

    # ---- notifications -----------------------------------------------------
    def _notify_group(self, group_xmlid, summary):
        group = self.env.ref(group_xmlid, raise_if_not_found=False)
        users = (
            # 19: "users" is gone; all_user_ids = explicit + implied members (17 "users" semantics)
            group.all_user_ids.filtered(lambda u: u.active and not u.share)
            if group
            else self.env["res.users"]
        )
        for user in users[:3]:  # do not flood every manager on big teams
            self.activity_schedule(
                "mail.mail_activity_data_todo", user_id=user.id, summary=summary
            )

    def _notify_quality_managers(self, summary):
        self._notify_group(GROUP_MANAGER, summary)

    def _notify_production(self, summary):
        self._notify_group("mrp.group_mrp_manager", summary)

    # ======================================================================
    # demo helper (called from data/demo.xml)
    # ======================================================================
    @api.model
    def _demo_setup(self):
        """Put demo lots into stock and walk demo NCRs through the workflow."""
        Quant = self.env["stock.quant"]
        stock = self.env.ref("stock.stock_location_stock")
        for xmlid, qty in (
            ("lot_bar_demo_1", 6.0),
            ("lot_bar_demo_2", 4.0),
            ("lot_bar_demo_3", 2.0),
        ):
            lot = self.env.ref(f"aero_ncr_mrb.{xmlid}")
            Quant._update_available_quantity(lot.product_id, stock, qty, lot_id=lot)
        # NCR 1: quarantined, waiting for MRB
        self.env.ref("aero_ncr_mrb.ncr_demo_1").action_submit()
        # NCR 2: in MRB review, disposition proposed
        ncr2 = self.env.ref("aero_ncr_mrb.ncr_demo_2")
        ncr2.action_submit()
        ncr2.action_start_mrb()
        ncr2.write(
            {
                "disposition": "use_as_is",
                "disposition_note": "Ra 1.8 vs 1.6 um on non-sealing face; no functional impact (stress report SR-0417).",
            }
        )
        # NCR 3: scrapped and closed (major -> CAPA recorded)
        ncr3 = self.env.ref("aero_ncr_mrb.ncr_demo_3")
        ncr3.action_submit()
        ncr3.action_start_mrb()
        ncr3.write(
            {
                "disposition": "scrap",
                "disposition_note": "Porosity above class B limit; not repairable.",
                "root_cause": "Powder lot humidity out of spec after 3-day storage outside cabinet.",
                "corrective_action": "Powder storage log added to shift handover; humidity check before each build.",
            }
        )
        ncr3.action_disposition()
        ncr3.action_close()
        return True
