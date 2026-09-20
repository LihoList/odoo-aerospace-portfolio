# Minimal, hand-made data for the training database "lab".
# No Odoo demo data: only what the five exercises need.
company = env.company

# 1. Settings: lots/serial numbers on, so the receipt asks for a lot.
env["res.config.settings"].create(
    {
        "group_stock_production_lot": True,
        "group_stock_adv_location": False,
        "group_stock_multi_locations": False,
    }
).execute()

# 2. Partners: one supplier, one customer.
vendor = env["res.partner"].create(
    {"name": "Northern Alloys Ltd (synthetic)", "is_company": True, "supplier_rank": 1}
)
customer = env["res.partner"].create(
    {
        "name": "Caledonia Aerospace Ltd (synthetic)",
        "is_company": True,
        "customer_rank": 1,
    }
)

# 3. Products: a lot-tracked raw material and a finished part.
prepreg = env["product.product"].create(
    {
        "name": "Prepreg CF/Epoxy 200 gsm (synthetic)",
        "default_code": "MAT-PP-200",
        "detailed_type": "product",
        "tracking": "lot",
        "standard_price": 100.0,
        "list_price": 140.0,
        "purchase_method": "receive",
        "seller_ids": [(0, 0, {"partner_id": vendor.id, "price": 100.0, "min_qty": 1})],
    }
)
panel = env["product.product"].create(
    {
        "name": "Interstage Composite Panel (synthetic)",
        "default_code": "STR-PNL-010",
        "detailed_type": "product",
        "tracking": "none",
        "standard_price": 450.0,
        "list_price": 900.0,
    }
)

# 4. Bill of materials: one panel is made of one unit of prepreg.
bom = env["mrp.bom"].create(
    {
        "product_tmpl_id": panel.product_tmpl_id.id,
        "product_qty": 1.0,
        "type": "normal",
        "bom_line_ids": [(0, 0, {"product_id": prepreg.id, "product_qty": 1.0})],
    }
)

# 5. Defect type for the NCR exercises (the module's own demo data is not loaded here).
if not env["aero.ncr.defect.type"].search([], limit=1):
    env["aero.ncr.defect.type"].create(
        [
            {"code": "DIM", "name": "Dimensional out of tolerance", "sequence": 10},
            {
                "code": "CERT",
                "name": "Material certification missing or mismatched",
                "sequence": 20,
            },
            {"code": "OUTT", "name": "Out-time / shelf life exceeded", "sequence": 30},
        ]
    )

env.cr.commit()
print(
    "SEED OK |",
    "vendor:",
    vendor.name,
    "| customer:",
    customer.name,
    "| products:",
    prepreg.default_code,
    panel.default_code,
    "| bom lines:",
    len(bom.bom_line_ids),
    "| defect types:",
    env["aero.ncr.defect.type"].search_count([]),
    "| lots enabled:",
    env.user.has_group("stock.group_production_lot"),
)
