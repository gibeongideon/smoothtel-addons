from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    kpi_is_manager = fields.Boolean(
        string="KPI Manager",
        compute="_compute_kpi_roles",
        inverse="_inverse_kpi_is_manager",
    )
    kpi_is_admin = fields.Boolean(
        string="KPI Administrator",
        compute="_compute_kpi_roles",
        inverse="_inverse_kpi_is_admin",
    )

    @api.depends("groups_id")
    def _compute_kpi_roles(self):
        for user in self:
            user_as_self = user.with_user(user)
            user.kpi_is_manager = user_as_self.has_group("traffic_light_kpi.group_kpi_manager")
            user.kpi_is_admin = user_as_self.has_group("traffic_light_kpi.group_kpi_admin")

    def _inverse_kpi_is_manager(self):
        group_manager = self.env.ref("traffic_light_kpi.group_kpi_manager", raise_if_not_found=False)
        group_admin = self.env.ref("traffic_light_kpi.group_kpi_admin", raise_if_not_found=False)
        if not group_manager:
            return
        for user in self:
            if user.kpi_is_manager:
                user.write({"groups_id": [(4, group_manager.id)]})
            else:
                vals = [(3, group_manager.id)]
                if group_admin and group_admin in user.groups_id:
                    vals.append((3, group_admin.id))
                user.write({"groups_id": vals})

    def _inverse_kpi_is_admin(self):
        group_admin = self.env.ref("traffic_light_kpi.group_kpi_admin", raise_if_not_found=False)
        if not group_admin:
            return
        for user in self:
            if user.kpi_is_admin:
                user.write({"groups_id": [(4, group_admin.id)]})
            else:
                user.write({"groups_id": [(3, group_admin.id)]})
