from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    kpi_outstanding_threshold = fields.Float(
        string="KPI Outstanding Threshold (%)",
        default=120.0,
        help="Minimum achievement percentage for rating 5 – Outstanding (blue).",
    )
    kpi_exceeds_threshold = fields.Float(
        string="KPI Exceeds Expectations Threshold (%)",
        default=100.0,
        help="Minimum achievement percentage for rating 4 – Exceeds Expectations (green).",
    )
    kpi_green_threshold = fields.Float(
        string="KPI Meets Expectations Threshold (%)",
        default=80.0,
        help="Minimum achievement percentage for rating 3 – Meets Expectations (green).",
    )
    kpi_yellow_threshold = fields.Float(
        string="KPI Needs Improvement Threshold (%)",
        default=50.0,
        help="Minimum achievement percentage for rating 2 – Needs Improvement (yellow). "
             "Lower values are rated 1 – Unacceptable (red).",
    )
