{
    "name": "Aero Material Out-time",
    "summary": "Out-time tracking for freezer-controlled materials "
    "(prepregs, film adhesives, sealants) with production blocking",
    "description": """
Composite prepregs and film adhesives are stored frozen and have a limited
cumulative "out-time" (hours outside the freezer). Once exceeded the material
is scrap. This module logs every freezer removal/return per lot, computes the
used and remaining out-time, and blocks completion of a manufacturing order
that consumed an expired lot.
""",
    "author": "Daniil Lutsyk",
    "website": "https://github.com/LihoList/odoo-aerospace-portfolio",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Manufacturing",
    "license": "LGPL-3",
    "depends": ["mrp"],
    "data": [
        "security/ir.model.access.csv",
        "views/aero_outtime_event_views.xml",
        "views/stock_lot_views.xml",
    ],
    "demo": ["data/demo.xml"],
    "installable": True,
    "application": False,
}
