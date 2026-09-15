from odoo import fields, models


class AeroNcrDefectType(models.Model):
    """Configurable defect taxonomy so NCRs can be analysed by category."""

    _name = "aero.ncr.defect.type"
    _description = "NCR defect type"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, size=8)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text()

    _sql_constraints = [
        ("code_uniq", "unique(code)", "Defect type codes must be unique."),
    ]

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.code}] {rec.name}"
