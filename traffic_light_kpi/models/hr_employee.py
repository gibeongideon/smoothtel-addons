from odoo import api, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def _trigger_kpi_recompute(self):
        self.env["kpi.result"].sudo()._compute_all_results()

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        employees._trigger_kpi_recompute()
        return employees

    def write(self, vals):
        result = super().write(vals)
        if any(field in vals for field in ("job_id", "user_id", "active")):
            self._trigger_kpi_recompute()
        return result
