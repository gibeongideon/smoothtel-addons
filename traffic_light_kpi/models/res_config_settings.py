from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    kpi_outstanding_threshold = fields.Float(
        related="company_id.kpi_outstanding_threshold",
        readonly=False,
        string="Outstanding Threshold (%)",
    )
    kpi_exceeds_threshold = fields.Float(
        related="company_id.kpi_exceeds_threshold",
        readonly=False,
        string="Exceeds Expectations Threshold (%)",
    )
    kpi_green_threshold = fields.Float(
        related="company_id.kpi_green_threshold",
        readonly=False,
        string="Meets Expectations Threshold (%)",
    )
    kpi_yellow_threshold = fields.Float(
        related="company_id.kpi_yellow_threshold",
        readonly=False,
        string="Needs Improvement Threshold (%)",
    )

    @api.constrains(
        "kpi_yellow_threshold",
        "kpi_green_threshold",
        "kpi_exceeds_threshold",
        "kpi_outstanding_threshold",
    )
    def _check_kpi_thresholds(self):
        for rec in self:
            thresholds = [
                rec.kpi_yellow_threshold,
                rec.kpi_green_threshold,
                rec.kpi_exceeds_threshold,
                rec.kpi_outstanding_threshold,
            ]
            if any(value < 0 for value in thresholds):
                raise ValidationError("KPI thresholds must be zero or greater.")
            if any(low >= high for low, high in zip(thresholds, thresholds[1:])):
                raise ValidationError(
                    "KPI thresholds must increase: Needs Improvement < Meets Expectations "
                    "< Exceeds Expectations < Outstanding."
                )

    def set_values(self):
        result = super().set_values()
        self.env["kpi.result"].sudo()._compute_all_results()
        return result
