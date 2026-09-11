import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)

STATUS_COLORS = [
    ('green', 'Green'),
    ('yellow', 'Yellow'),
    ('red', 'Red'),
    ('grey', 'Not Evaluated'),
]


class KpiTrafficLight(models.Model):
    _name = 'kpi.traffic.light'
    _description = 'KPI Traffic Light – Aggregated User Status'
    _order = 'overall_percentage asc, red_count desc, yellow_count desc, user_id'
    _rec_name = 'user_id'

    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        ondelete='cascade',
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        compute='_compute_employee',
        store=True,
    )
    overall_percentage = fields.Float(string='Overall Score (%)', digits=(5, 1))
    overall_status = fields.Selection(STATUS_COLORS, string='Overall Status', default='grey')
    kpi_count = fields.Integer(string='# KPIs')
    green_count = fields.Integer(string='# Green')
    yellow_count = fields.Integer(string='# Yellow')
    red_count = fields.Integer(string='# Red')
    last_updated = fields.Datetime(string='Last Updated')

    _sql_constraints = [
        ('unique_user', 'UNIQUE(user_id)', 'One traffic light record per user.'),
    ]

    @api.depends('user_id')
    def _compute_employee(self):
        Employee = self.env['hr.employee']
        user_ids = self.mapped('user_id').ids
        employee_map = {}
        if user_ids:
            employees = Employee.search([('user_id', 'in', user_ids)])
            employee_map = {emp.user_id.id: emp for emp in employees}
        for rec in self:
            rec.employee_id = employee_map.get(rec.user_id.id, False)

    @api.model
    def _refresh_all(self):
        """Recompute overall status for every user that has kpi.result records."""
        KpiResult = self.env['kpi.result']
        user_ids = KpiResult.search([]).mapped('user_id.id')
        user_ids = list(set(user_ids))
        for uid in user_ids:
            self._refresh_for_user(uid)

    @api.model
    def _refresh_for_user(self, user_id):
        """Recompute overall traffic light for a single user_id."""
        KpiResult = self.env['kpi.result']
        user = self.env['res.users'].browse(user_id)
        results = KpiResult._get_current_results_for_user(user_id)

        if not results:
            # Remove stale record if exists
            self.search([('user_id', '=', user_id)]).unlink()
            return

        active_results = results.filtered(lambda r: r.status != 'grey')

        if not active_results:
            vals = {
                'overall_percentage': 0.0,
                'overall_status': 'grey',
                'kpi_count': len(results),
                'green_count': 0,
                'yellow_count': 0,
                'red_count': 0,
                'last_updated': fields.Datetime.now(),
            }
            existing = self.search([('user_id', '=', user_id)], limit=1)
            if existing:
                existing.write(vals)
            else:
                vals['user_id'] = user_id
                self.create(vals)
            return

        # Weighted average of currently evaluable KPIs only
        total_weight = 0.0
        weighted_sum = 0.0
        green_count = yellow_count = red_count = 0

        for r in active_results:
            w = r.kpi_id.weight or 1.0
            total_weight += w
            weighted_sum += r.percentage * w
            if r.status == 'green':
                green_count += 1
            elif r.status == 'yellow':
                yellow_count += 1
            elif r.status == 'red':
                red_count += 1

        overall_pct = (weighted_sum / total_weight) if total_weight else 0.0

        company = user.company_id or self.env.company
        yellow_threshold = company.kpi_yellow_threshold or 50.0
        green_threshold = company.kpi_green_threshold or 80.0

        if overall_pct >= green_threshold:
            overall_status = 'green'
        elif overall_pct >= yellow_threshold:
            overall_status = 'yellow'
        else:
            overall_status = 'red'

        vals = {
            'overall_percentage': overall_pct,
            'overall_status': overall_status,
            'kpi_count': len(active_results),
            'green_count': green_count,
            'yellow_count': yellow_count,
            'red_count': red_count,
            'last_updated': fields.Datetime.now(),
        }

        existing = self.search([('user_id', '=', user_id)], limit=1)
        if existing:
            existing.write(vals)
        else:
            vals['user_id'] = user_id
            self.create(vals)

    def action_open_user_kpis(self):
        self.ensure_one()
        action = self.env.ref('traffic_light_kpi.action_team_member_kpis').sudo().read()[0]
        ctx = action.get('context') or {}
        if isinstance(ctx, str):
            ctx = {}
        ctx.update({
            'default_user_id': self.user_id.id,
            'search_default_group_employee': 0,
            'search_default_group_user': 0,
        })
        current_results = self.env['kpi.result']._get_current_results_for_user(self.user_id.id)
        action.update({
            'name': f'{self.employee_id.name or self.user_id.name} KPI Results',
            'domain': [('id', 'in', current_results.ids)],
            'context': ctx,
        })
        return action
