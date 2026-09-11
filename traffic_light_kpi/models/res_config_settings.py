from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    kpi_green_threshold = fields.Float(
        related="company_id.kpi_green_threshold",
        readonly=False,
        string="Green Threshold (%)",
    )
    kpi_yellow_threshold = fields.Float(
        related="company_id.kpi_yellow_threshold",
        readonly=False,
        string="Yellow Threshold (%)",
    )

    @api.constrains("kpi_green_threshold", "kpi_yellow_threshold")
    def _check_kpi_thresholds(self):
        for rec in self:
            if rec.kpi_yellow_threshold < 0 or rec.kpi_green_threshold < 0:
                raise ValidationError("KPI thresholds must be zero or greater.")
            if rec.kpi_yellow_threshold >= rec.kpi_green_threshold:
                raise ValidationError("Yellow threshold must be lower than green threshold.")

    def set_values(self):
        result = super().set_values()
        self.env["kpi.result"].sudo()._compute_all_results()
        return result
