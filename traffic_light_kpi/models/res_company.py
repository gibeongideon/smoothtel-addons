from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    kpi_green_threshold = fields.Float(
        string="KPI Green Threshold (%)",
        default=80.0,
        help="Minimum progress percentage required for a KPI to be green.",
    )
    kpi_yellow_threshold = fields.Float(
        string="KPI Yellow Threshold (%)",
        default=50.0,
        help="Minimum progress percentage required for a KPI to be yellow. Lower values are red.",
    )
