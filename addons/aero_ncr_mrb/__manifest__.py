{
    "name": "Aero Nonconformance & MRB",
    "summary": "Nonconformance reports with automatic quarantine, Material Review "
    "Board dispositions and the stock actions they trigger (AS9100 8.7)",
    "description": """
Raise a nonconformance (NCR) against a product/lot from receiving, production or
final inspection. Submitting it moves the material into Quarantine. The Material
Review Board records a disposition (use-as-is, rework, repair, scrap, return to
supplier); use-as-is and repair need engineering authority approval. Each
disposition triggers the matching stock action: scrap, return picking, or release
back to stock. Major/critical NCRs cannot be closed without root cause and
corrective action. Everything is tracked in the chatter and printable as a PDF.
""",
    "author": "Daniil Lutsyk",
    "website": "https://github.com/LihoList/odoo-aerospace-portfolio",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Quality",
    "license": "LGPL-3",
    "depends": ["mrp"],
    "data": [
        "security/aero_ncr_security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "data/stock_location.xml",
        "data/defect_types.xml",
        "views/aero_ncr_defect_type_views.xml",
        "views/aero_ncr_views.xml",
        "views/stock_lot_views.xml",
        "views/menus.xml",
        "report/ncr_report.xml",
    ],
    "demo": ["data/demo.xml"],
    "installable": True,
    "application": True,
}
