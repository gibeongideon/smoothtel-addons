import ast
import json
import logging
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
import pytz

from odoo import models, fields, api
from odoo.exceptions import UserError

from .domain_utils import sanitize_domain_for_model

_logger = logging.getLogger(__name__)

GREEN = 'green'
YELLOW = 'yellow'
RED = 'red'
GREY = 'grey'

STATUS_COLORS = [
    (GREEN, 'Green'),
    (YELLOW, 'Yellow'),
    (RED, 'Red'),
    (GREY, 'Not Evaluated'),
]


def _get_period_bounds(period, reference_date=None):
    """Return (start_date, end_date) for the given period relative to reference_date."""
    today = reference_date or date.today()
    if period == 'daily':
        return today, today
    if period == 'weekly':
        start = today - timedelta(days=today.weekday())  # Monday
        end = start + timedelta(days=6)
        return start, end
    if period == 'monthly':
        start = today.replace(day=1)
        end = (start + relativedelta(months=1)) - timedelta(days=1)
        return start, end
    if period == 'yearly':
        start = today.replace(month=1, day=1)
        end = today.replace(month=12, day=31)
        return start, end
    return today, today


def _shift_period_reference(period, reference_date, offset):
    if period == 'daily':
        return reference_date + relativedelta(days=offset)
    if period == 'weekly':
        return reference_date + relativedelta(weeks=offset)
    if period == 'monthly':
        return reference_date + relativedelta(months=offset)
    if period == 'yearly':
        return reference_date + relativedelta(years=offset)
    return reference_date

class KpiResult(models.Model):
    _name = 'kpi.result'
    _description = 'KPI Result (per user per KPI)'
    _order = 'user_id, kpi_id'
    _rec_name = 'display_name'

    kpi_id = fields.Many2one(
        'kpi.definition',
        string='KPI',
        required=True,
        ondelete='cascade',
    )
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

    # Period snapshot
    period_start = fields.Date(string='Period Start')
    period_end = fields.Date(string='Period End')
    period = fields.Selection(related='kpi_id.period', store=True)

    # Values
    target_value = fields.Float(string='Target', digits=(16, 2))
    actual_value = fields.Float(string='Actual', digits=(16, 2))
    percentage = fields.Float(string='Progress (%)', digits=(5, 1))
    status = fields.Selection(STATUS_COLORS, string='Status', default=GREY)
    data_point_count = fields.Integer(string='Data Points')

    # Insight text (auto-generated)
    insight_text = fields.Char(string='Insight')

    last_updated = fields.Datetime(string='Last Updated')

    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
    )

    _sql_constraints = [
        (
            'unique_user_kpi_period',
            'UNIQUE(kpi_id, user_id, period_start)',
            'A result already exists for this user, KPI and period.',
        )
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

    @api.depends('kpi_id', 'user_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.user_id.name} – {rec.kpi_id.name}" if rec.kpi_id and rec.user_id else ''

    # ------------------------------------------------------------------
    # Core computation engine
    # ------------------------------------------------------------------

    @api.model
    def _compute_all_results(self):
        """Called by cron. Recalculates KPI results for all active employees."""
        self._ensure_enterprise_history_backfilled()
        Employee = self.env['hr.employee']
        employees = Employee.search([
            ('active', '=', True),
            ('user_id', '!=', False),
        ])
        _logger.info('KPI Traffic Light: Computing results for %d employees', len(employees))
        for emp in employees:
            self._compute_results_for_employee(emp, include_history=False)

    def _compute_results_for_employee(self, employee, include_history=False):
        """Compute/update all KPI results for a single employee."""
        if not employee.user_id:
            return

        user = employee.user_id
        user_results = self.search([('user_id', '=', user.id)])

        if not employee.active or not employee.job_id:
            if user_results:
                user_results.unlink()
            self.env['kpi.traffic.light']._refresh_for_user(user.id)
            return

        kpi_defs = self.env['kpi.definition'].search([
            ('job_position_ids', 'in', employee.job_id.id),
            ('active', '=', True),
        ])

        if user_results:
            stale_results = user_results.filtered(lambda r: r.kpi_id not in kpi_defs)
            if stale_results:
                stale_results.unlink()

        existing_map = {}
        for result in user_results:
            existing_map[(result.kpi_id.id, result.period_start)] = result

        if not kpi_defs:
            self.env['kpi.traffic.light']._refresh_for_user(user.id)
            return

        for kpi in kpi_defs:
            self._upsert_result(user, kpi, existing_map=existing_map)
            if include_history:
                self._ensure_kpi_history(user, kpi, existing_map=existing_map)

        self.env['kpi.traffic.light']._refresh_for_user(user.id)

    def _ensure_kpi_history(self, user, kpi, existing_map=None):
        history_size = max(int(kpi.trend_period_count or 0), 1)
        if history_size <= 1:
            return

        reference_date = date.today()
        for offset in range(1, history_size):
            history_reference = _shift_period_reference(kpi.period, reference_date, -offset)
            self._upsert_result(
                user,
                kpi,
                existing_map=existing_map,
                reference_date=history_reference,
            )

    def _upsert_result(self, user, kpi, existing_map=None, reference_date=None):
        """Compute actual value and upsert a kpi.result record."""
        effective_date = reference_date or date.today()
        period_start, period_end = _get_period_bounds(kpi.period, effective_date)
        actual = self._get_actual_value(user, kpi, period_start, period_end)
        target = kpi.target_value
        data_point_count = self._get_data_point_count(user, kpi, period_start, period_end)

        if self._is_turnaround_kpi(kpi):
            pct, status = self._compute_turnaround_score(actual, target, data_point_count, user.company_id)
        else:
            if target and target > 0:
                pct = min((actual / target) * 100.0, 999.9)
            else:
                pct = 0.0
            status = self._percentage_to_status(pct, user.company_id)

        insight = self._build_insight(kpi, actual, target, pct, status, data_point_count=data_point_count)

        existing = False
        if existing_map is not None:
            existing = existing_map.get((kpi.id, period_start))
        if not existing:
            existing = self.search([
                ('kpi_id', '=', kpi.id),
                ('user_id', '=', user.id),
                ('period_start', '=', period_start),
            ], limit=1)

        vals = {
            'target_value': target,
            'actual_value': actual,
            'percentage': pct,
            'status': status,
            'data_point_count': data_point_count,
            'insight_text': insight,
            'period_end': period_end,
            'last_updated': fields.Datetime.now(),
        }

        if existing:
            existing.write(vals)
        else:
            vals.update({
                'kpi_id': kpi.id,
                'user_id': user.id,
                'period_start': period_start,
            })
            existing = self.create(vals)
            if existing_map is not None:
                existing_map[(kpi.id, period_start)] = existing

    def _get_thresholds(self, company=None):
        company = company or self.env.company
        green = company.kpi_green_threshold or 80.0
        yellow = company.kpi_yellow_threshold or 50.0
        return yellow, green

    def _get_scope_users(self, user, kpi):
        if kpi.evaluation_scope != 'team':
            return user

        team_domain = [
            ('active', '=', True),
            ('user_id', '!=', False),
            ('parent_id.user_id', '=', user.id),
        ]
        if kpi.team_member_job_ids:
            team_domain.append(('job_id', 'in', kpi.team_member_job_ids.ids))
        team_members = self.env['hr.employee'].search(team_domain).mapped('user_id')
        return team_members

    def _get_scope_user_ids(self, user, kpi):
        return self._get_scope_users(user, kpi).ids

    def _should_normalize_per_member(self, kpi):
        return kpi.evaluation_scope == 'team' and kpi.normalize_per_member and kpi.measure_type in ('count', 'amount')

    @api.model
    def _current_period_start_for_kpi(self, kpi):
        period_start, _period_end = _get_period_bounds(kpi.period)
        return period_start

    @api.model
    def _get_current_results_for_user(self, user_id):
        results = self.search([('user_id', '=', user_id)])
        return results.filtered(lambda r: r.period_start == self._current_period_start_for_kpi(r.kpi_id))

    @api.model
    def _ensure_enterprise_history_backfilled(self):
        ICP = self.env['ir.config_parameter'].sudo()

        if ICP.get_param('traffic_light_kpi.approval_history_backfilled') != '1':
            ApprovalApprover = self.env['approval.approver'].sudo()
            missing_decisions = ApprovalApprover.search([
                ('decision_date', '=', False),
                ('status', 'in', ['approved', 'refused']),
            ])
            for approver in missing_decisions:
                approver.decision_date = approver.write_date or approver.create_date
            ICP.set_param('traffic_light_kpi.approval_history_backfilled', '1')

        if ICP.get_param('traffic_light_kpi.expense_history_backfilled') != '1':
            ExpenseSheet = self.env['hr.expense.sheet'].sudo()
            missing_submissions = ExpenseSheet.search([
                ('submitted_on', '=', False),
                ('state', 'in', ['submit', 'approve', 'post', 'done', 'cancel']),
            ])
            for sheet in missing_submissions:
                sheet.submitted_on = sheet.create_date
            ICP.set_param('traffic_light_kpi.expense_history_backfilled', '1')

    def _percentage_to_status(self, pct, company=None):
        yellow, green = self._get_thresholds(company)
        if pct >= green:
            return GREEN
        if pct >= yellow:
            return YELLOW
        return RED

    def _is_turnaround_kpi(self, kpi):
        return self._get_handler_key(kpi) in {
            'helpdesk_ticket_closed_within_window',
            'approval_decision_within_window',
            'store_requisition_approval_within_window',
            'quotation_approval_within_window',
            'expense_approval_within_window',
            'custom_turnaround_compliance',
            'operating_hours_compliance',
        }

    def _compute_turnaround_score(self, actual, target, data_point_count, company=None):
        if not data_point_count:
            return 0.0, GREY

        compliance_pct = max(0.0, min(actual, 100.0))
        if target and target > 0:
            if compliance_pct >= target:
                return compliance_pct, GREEN
            if compliance_pct >= (target * 0.8):
                return compliance_pct, YELLOW
            return compliance_pct, RED
        return compliance_pct, self._percentage_to_status(compliance_pct, company)

    def _get_data_point_count(self, user, kpi, start, end):
        handler_key = self._get_handler_key(kpi)
        if not self._is_turnaround_kpi(kpi):
            return 0

        extra = self._get_extra_domain(kpi)
        if handler_key == 'helpdesk_ticket_closed_within_window':
            return len(self._get_closed_helpdesk_tickets(user, kpi, start, end, extra))
        if handler_key in {
            'approval_decision_within_window',
            'store_requisition_approval_within_window',
            'quotation_approval_within_window',
        }:
            return len(self._get_approval_decisions(user, kpi, start, end, extra))
        if handler_key == 'expense_approval_within_window':
            return len(self._get_approved_expenses(user, kpi, start, end, extra))
        if handler_key in {'custom_turnaround_compliance', 'operating_hours_compliance'}:
            Model, domain = self._get_model_and_domain(user, kpi, start, end, extra)
            return Model.search_count(domain)
        return 0

    def _get_actual_value(self, user, kpi, period_start, period_end):
        """Dispatch to the correct data source handler."""
        ds = self._get_handler_key(kpi)
        extra_domain = self._get_extra_domain(kpi)

        handlers = {
            'crm_lead_count': self._src_crm_lead,
            'monetary_lead_generation': self._src_crm_lead_amount,
            'crm_qualified_lead_count': self._src_crm_qualified_lead,
            'activity_count': self._src_activity_count,
            'skills_count': self._src_skills_count,
            'certification_count': self._src_certification_count,
            'sale_order': self._src_sale_order,
            'sale_revenue': self._src_sale_revenue,
            'sale_conversion': self._src_sale_conversion,
            'sale_conversion_30d': self._src_sale_conversion_30d,
            'sale_converted_amount_30d': self._src_sale_converted_amount_30d,
            'purchase_order': self._src_purchase_order,
            'purchase_amount': self._src_purchase_amount,
            'purchase_order_count': self._src_purchase_order,
            'purchase_order_amount': self._src_purchase_amount,
            'helpdesk_ticket_opened_count': self._src_helpdesk_ticket_opened,
            'helpdesk_ticket_closed_count': self._src_helpdesk_ticket_closed,
            'helpdesk_ticket_closed_within_window': self._src_helpdesk_ticket_closed_within_window,
            'approval_decision_count': self._src_approval_decision_count,
            'approval_decision_within_window': self._src_approval_decision_within_window,
            'store_requisition_approval_within_window': self._src_approval_decision_within_window,
            'quotation_approval_within_window': self._src_approval_decision_within_window,
            'expense_approved_count': self._src_expense_approved_count,
            'expense_approval_within_window': self._src_expense_approval_within_window,
            'custom_turnaround_compliance': self._src_custom_turnaround_compliance,
            'operating_hours_compliance': self._src_operating_hours_compliance,
            'custom_count': self._src_custom,
            'custom_sum': self._src_custom,
            'custom': self._src_custom,
        }
        handler = handlers.get(ds)
        if not handler:
            return 0.0
        actual = handler(user, kpi, period_start, period_end, extra_domain)
        if self._should_normalize_per_member(kpi):
            member_count = len(self._get_scope_user_ids(user, kpi))
            if member_count:
                return round(actual / member_count, 2)
        return actual

    def _get_handler_key(self, kpi):
        return kpi.kpi_code or kpi.data_source

    def _get_extra_domain(self, kpi):
        extra_domain = []
        if kpi.domain_filter:
            try:
                extra_domain = json.loads(kpi.domain_filter)
            except Exception:
                _logger.warning('KPI %s: invalid domain_filter JSON', kpi.name)
        model_name = self._get_source_model_name(kpi)
        sanitized_domain, removed_paths = sanitize_domain_for_model(
            self.env, model_name, extra_domain
        )
        if removed_paths:
            _logger.warning(
                'KPI %s: removed invalid domain paths for model %s: %s',
                kpi.name,
                model_name,
                ", ".join(removed_paths),
            )
        return sanitized_domain

    def _append_date_range(self, domain, field_name, start, end, use_datetime=True):
        if use_datetime:
            start_value = fields.Datetime.from_string(str(start))
            end_value = fields.Datetime.from_string(str(end) + ' 23:59:59')
        else:
            start_value = str(start)
            end_value = str(end)
        return domain + [
            (field_name, '>=', start_value),
            (field_name, '<=', end_value),
        ]

    def _get_model_and_domain(self, user, kpi, start, end, extra_domain=None):
        extra_domain = extra_domain or []
        model_name = self._get_source_model_name(kpi)
        date_field = self._get_source_date_field(kpi)
        user_field = self._get_source_user_field(kpi)
        if not model_name or not date_field:
            raise UserError(f'KPI "{kpi.name}" is missing source model or source date field configuration.')
        try:
            Model = self.env[model_name]
        except KeyError as exc:
            raise UserError(f'Source model {model_name} was not found for KPI "{kpi.name}".') from exc

        scope_user_ids = self._get_scope_user_ids(user, kpi)
        if scope_user_ids:
            domain = [(user_field, 'in', scope_user_ids)]
        else:
            domain = [('id', '=', 0)]
        domain = self._apply_kpi_specific_filters(domain, kpi)
        domain += extra_domain
        domain = self._append_date_range(domain, date_field, start, end, self._is_datetime_field(Model, date_field))
        return Model, domain

    def _is_datetime_field(self, model, field_name):
        field = model._fields.get(field_name)
        return not field or field.type == 'datetime'

    def _get_source_model_name(self, kpi):
        return kpi.source_model or kpi.custom_model or {
            'crm_lead': 'crm.lead',
            'crm_activity': 'mail.activity',
            'sale_order': 'sale.order',
            'sale_revenue': 'sale.order',
            'sale_conversion': 'crm.lead',
            'purchase_order': 'purchase.order',
            'purchase_amount': 'purchase.order',
            'helpdesk_ticket': 'helpdesk.ticket',
            'approval_request': 'approval.approver',
            'hr_expense': 'hr.expense',
            'custom': kpi.custom_model,
        }.get(kpi.data_source)

    def _get_source_date_field(self, kpi):
        return kpi.source_date_field or kpi.custom_date_field or {
            'crm_lead': 'create_date',
            'crm_activity': 'date_deadline',
            'sale_order': 'date_order',
            'sale_revenue': 'date_order',
            'sale_conversion': 'create_date',
            'purchase_order': 'date_order',
            'purchase_amount': 'date_order',
            'helpdesk_ticket': 'create_date',
            'approval_request': 'decision_date',
            'hr_expense': 'approved_on',
            'custom': kpi.custom_date_field,
        }.get(kpi.data_source)

    def _get_source_user_field(self, kpi):
        return kpi.source_user_field or kpi.custom_user_field or 'user_id'

    def _apply_kpi_specific_filters(self, domain, kpi):
        domain = list(domain)
        if kpi.activity_type_id:
            domain.append(('activity_type_id', '=', kpi.activity_type_id.id))
        if kpi.stage_id:
            domain.append(('stage_id', '=', kpi.stage_id.id))
        return domain

    def _sum_records(self, records, field_name):
        if not field_name:
            return 0.0
        return float(sum(records.mapped(field_name)))

    def _build_source_action_config(self, result):
        kpi = result.kpi_id
        user = result.user_id
        start = result.period_start
        end = result.period_end
        extra = self._get_extra_domain(kpi)
        scope_user_ids = self._get_scope_user_ids(user, kpi)
        scope_user_domain = [('user_id', 'in', scope_user_ids)]
        expense_scope_domain = [('approved_by', 'in', scope_user_ids)]
        employee_scope_domain = [('employee_id.user_id', 'in', scope_user_ids)]

        handler_key = self._get_handler_key(kpi)
        converted_order_ids = []
        if handler_key in {'sale_conversion_30d', 'sale_converted_amount_30d'}:
            converted_order_ids = self._get_sale_conversion_order_ids(
                user, kpi, start, end, extra
            )
        configs = {
            'crm_lead': {
                'name': f'{kpi.name} Leads',
                'res_model': 'crm.lead',
                'domain': self._append_date_range(
                    scope_user_domain + extra,
                    'create_date',
                    start,
                    end,
                ),
                'context': {'search_default_assigned_to_me': 1},
            },
            'monetary_lead_generation': {
                'name': f'{kpi.name} Leads',
                'res_model': 'crm.lead',
                'domain': self._append_date_range(
                    scope_user_domain + extra,
                    'create_date',
                    start,
                    end,
                ),
                'context': {'search_default_assigned_to_me': 1},
            },
            'crm_lead_count': {
                'name': f'{kpi.name} Leads',
                'res_model': 'crm.lead',
                'domain': self._append_date_range(
                    self._apply_kpi_specific_filters(scope_user_domain, kpi) + extra,
                    'create_date',
                    start,
                    end,
                ),
                'context': {'search_default_assigned_to_me': 1},
            },
            'crm_qualified_lead_count': {
                'name': f'{kpi.name} Leads',
                'res_model': 'crm.lead',
                'domain': self._append_date_range(
                    self._apply_kpi_specific_filters(scope_user_domain, kpi) + extra,
                    'create_date',
                    start,
                    end,
                ),
                'context': {'search_default_assigned_to_me': 1},
            },
            'skills_count': {
                'name': f'{kpi.name} Skills',
                'res_model': 'hr.employee.skill',
                'domain': self._append_date_range(
                    employee_scope_domain + extra,
                    'create_date',
                    start,
                    end,
                ),
                'context': {},
            },
            'certification_count': {
                'name': f'{kpi.name} Certifications',
                'res_model': 'hr.resume.line',
                'domain': self._append_date_range(
                    employee_scope_domain + [('line_type_id.name', 'ilike', 'certificate')] + extra,
                    'date_start',
                    start,
                    end,
                    False,
                ),
                'context': {},
            },
            'crm_activity': {
                'name': f'{kpi.name} Activities',
                'res_model': 'mail.activity',
                'domain': self._append_date_range(
                    self._apply_kpi_specific_filters(scope_user_domain, kpi) + extra,
                    'date_deadline',
                    start,
                    end,
                    False,
                ),
                'context': {},
            },
            'activity_count': {
                'name': f'{kpi.name} Activities',
                'res_model': 'mail.activity',
                'domain': self._append_date_range(
                    self._apply_kpi_specific_filters(scope_user_domain, kpi) + extra,
                    'date_deadline',
                    start,
                    end,
                    False,
                ),
                'context': {},
            },
            'sale_order': {
                'name': f'{kpi.name} Sales Orders',
                'res_model': 'sale.order',
                'domain': self._append_date_range(
                    [
                        ('user_id', 'in', scope_user_ids),
                        ('state', 'in', ['sale', 'done']),
                    ] + extra,
                    'date_order',
                    start,
                    end,
                ),
                'context': {'search_default_my_quotation': 0},
            },
            'sale_revenue': {
                'name': f'{kpi.name} Sales Orders',
                'res_model': 'sale.order',
                'domain': self._append_date_range(
                    [
                        ('user_id', 'in', scope_user_ids),
                        ('state', 'in', ['sale', 'done']),
                    ] + extra,
                    'date_order',
                    start,
                    end,
                ),
                'context': {'search_default_my_quotation': 0},
            },
            'sale_conversion': {
                'name': f'{kpi.name} Leads',
                'res_model': 'crm.lead',
                'domain': self._append_date_range(
                    scope_user_domain + extra,
                    'create_date',
                    start,
                    end,
                ),
                'context': {'search_default_assigned_to_me': 1},
            },
            'sale_conversion_30d': {
                'name': f'{kpi.name} Quotations',
                'res_model': 'sale.order',
                'domain': [('id', 'in', converted_order_ids)],
                'context': {},
            },
            'sale_converted_amount_30d': {
                'name': f'{kpi.name} Converted Orders',
                'res_model': 'sale.order',
                'domain': [('id', 'in', converted_order_ids)],
                'context': {},
            },
            'purchase_order': {
                'name': f'{kpi.name} Purchase Orders',
                'res_model': 'purchase.order',
                'domain': self._append_date_range(
                    [
                        ('user_id', 'in', scope_user_ids),
                        ('state', 'in', ['purchase', 'done']),
                    ] + extra,
                    'date_order',
                    start,
                    end,
                ),
                'context': {},
            },
            'purchase_order_count': {
                'name': f'{kpi.name} Purchase Orders',
                'res_model': 'purchase.order',
                'domain': self._append_date_range(
                    [('user_id', 'in', scope_user_ids), ('state', 'in', ['purchase', 'done'])] + extra,
                    self._get_source_date_field(kpi) or 'date_order',
                    start,
                    end,
                ),
                'context': {},
            },
            'purchase_amount': {
                'name': f'{kpi.name} Purchase Orders',
                'res_model': 'purchase.order',
                'domain': self._append_date_range(
                    [
                        ('user_id', 'in', scope_user_ids),
                        ('state', 'in', ['purchase', 'done']),
                    ] + extra,
                    'date_order',
                    start,
                    end,
                ),
                'context': {},
            },
            'purchase_order_amount': {
                'name': f'{kpi.name} Purchase Orders',
                'res_model': 'purchase.order',
                'domain': self._append_date_range(
                    [('user_id', 'in', scope_user_ids), ('state', 'in', ['purchase', 'done'])] + extra,
                    self._get_source_date_field(kpi) or 'date_order',
                    start,
                    end,
                ),
                'context': {},
            },
            'helpdesk_ticket_opened_count': {
                'name': f'{kpi.name} Tickets',
                'res_model': 'helpdesk.ticket',
                'domain': self._append_date_range(
                    scope_user_domain + extra,
                    'create_date',
                    start,
                    end,
                ),
                'context': {'search_default_my_tickets': 1},
            },
            'helpdesk_ticket_closed_count': {
                'name': f'{kpi.name} Tickets',
                'res_model': 'helpdesk.ticket',
                'domain': self._append_date_range(
                    scope_user_domain + [('close_date', '!=', False)] + extra,
                    'close_date',
                    start,
                    end,
                ),
                'context': {'search_default_my_tickets': 1},
            },
            'helpdesk_ticket_closed_within_window': {
                'name': f'{kpi.name} Tickets',
                'res_model': 'helpdesk.ticket',
                'domain': self._append_date_range(
                    scope_user_domain + [('close_date', '!=', False)] + extra,
                    'close_date',
                    start,
                    end,
                ),
                'context': {'search_default_my_tickets': 1},
            },
            'approval_decision_count': {
                'name': f'{kpi.name} Approval Decisions',
                'res_model': 'approval.approver',
                'domain': self._append_date_range(
                    scope_user_domain + [('status', 'in', ['approved', 'refused']), ('decision_date', '!=', False)] + extra,
                    'decision_date',
                    start,
                    end,
                ),
                'context': {},
            },
            'approval_decision_within_window': {
                'name': f'{kpi.name} Approval Decisions',
                'res_model': 'approval.approver',
                'domain': self._append_date_range(
                    scope_user_domain + [('status', 'in', ['approved', 'refused']), ('decision_date', '!=', False)] + extra,
                    'decision_date',
                    start,
                    end,
                ),
                'context': {},
            },
            'store_requisition_approval_within_window': {
                'name': f'{kpi.name} Approval Decisions',
                'res_model': 'approval.approver',
                'domain': self._append_date_range(
                    scope_user_domain + [('status', 'in', ['approved', 'refused']), ('decision_date', '!=', False)] + extra,
                    'decision_date',
                    start,
                    end,
                ),
                'context': {},
            },
            'quotation_approval_within_window': {
                'name': f'{kpi.name} Approval Decisions',
                'res_model': 'approval.approver',
                'domain': self._append_date_range(
                    scope_user_domain + [('status', 'in', ['approved', 'refused']), ('decision_date', '!=', False)] + extra,
                    'decision_date',
                    start,
                    end,
                ),
                'context': {},
            },
            'expense_approved_count': {
                'name': f'{kpi.name} Expenses',
                'res_model': 'hr.expense',
                'domain': self._append_date_range(
                    expense_scope_domain + [('approved_on', '!=', False), ('state', 'in', ['approved', 'done'])] + extra,
                    'approved_on',
                    start,
                    end,
                ),
                'context': {},
            },
            'expense_approval_within_window': {
                'name': f'{kpi.name} Expenses',
                'res_model': 'hr.expense',
                'domain': self._append_date_range(
                    expense_scope_domain + [('approved_on', '!=', False), ('state', 'in', ['approved', 'done'])] + extra,
                    'approved_on',
                    start,
                    end,
                ),
                'context': {},
            },
        }

        if handler_key in ('custom', 'custom_count', 'custom_sum', 'custom_turnaround_compliance', 'operating_hours_compliance'):
            if not kpi.custom_model or not kpi.custom_date_field:
                raise UserError('This KPI uses a custom source, but the model or date field is not configured.')
            try:
                self.env[kpi.custom_model]
            except KeyError as exc:
                raise UserError(f'Custom model {kpi.custom_model} was not found.') from exc

            user_field = kpi.custom_user_field or 'user_id'
            return {
                'name': f'{kpi.name} Records',
                'res_model': kpi.custom_model,
                'domain': self._append_date_range(
                    [(user_field, 'in', scope_user_ids)] + extra,
                    kpi.custom_date_field,
                    start,
                    end,
                ),
                'context': {},
            }

        config = configs.get(handler_key)
        if not config:
            raise UserError('No source drill-down is configured for this KPI data source.')
        return config

    def action_open_source_records(self):
        self.ensure_one()
        config = self._build_source_action_config(self)
        return {
            'type': 'ir.actions.act_window',
            'name': config['name'],
            'res_model': config['res_model'],
            'view_mode': 'list,form',
            'target': 'current',
            'domain': config['domain'],
            'context': config.get('context', {}),
        }

    def action_open_trend_view(self):
        self.ensure_one()
        self.sudo()._ensure_kpi_history(self.user_id.sudo(), self.kpi_id.sudo())
        return {
            'type': 'ir.actions.act_window',
            'name': f'{self.kpi_id.name} Trend',
            'res_model': 'kpi.result',
            'view_mode': 'graph,list,form,pivot',
            'target': 'current',
            'domain': [
                ('user_id', '=', self.user_id.id),
                ('kpi_id', '=', self.kpi_id.id),
            ],
            'context': {
                'search_default_group_period_start': 1,
            },
        }

    @api.model
    def action_open_dashboard_from_systray(self):
        action = self.env.ref('traffic_light_kpi.action_my_kpi_dashboard').sudo().read()[0]
        ctx = action.get('context') or {}
        if isinstance(ctx, str):
            try:
                ctx = ast.literal_eval(ctx)
            except Exception:
                ctx = {}
        ctx.update({
            'search_default_my_kpis': 1,
            'default_user_id': self.env.user.id,
        })
        current_results = self._get_current_results_for_user(self.env.user.id)
        KpiResultSudo = self.sudo()
        for result in current_results.sudo():
            KpiResultSudo._ensure_kpi_history(result.user_id, result.kpi_id)
        action['context'] = ctx
        action['domain'] = [('id', 'in', current_results.ids)]
        return action

    # ------------------------------------------------------------------
    # Data source handlers
    # ------------------------------------------------------------------

    def _src_crm_lead(self, user, kpi, start, end, extra):
        Model, domain = self._get_model_and_domain(user, kpi, start, end, extra)
        return float(Model.search_count(domain))

    def _src_crm_lead_amount(self, user, kpi, start, end, extra):
        Model, domain = self._get_model_and_domain(user, kpi, start, end, extra)
        leads = Model.search(domain)
        return self._sum_records(leads, kpi.result_field or 'expected_revenue')

    def _src_skills_count(self, user, kpi, start, end, extra):
        domain = [('employee_id.user_id', '=', user.id)] + extra
        domain = self._append_date_range(
            domain,
            'create_date',
            start,
            end,
        )
        return float(self.env['hr.employee.skill'].search_count(domain))

    def _src_certification_count(self, user, kpi, start, end, extra):
        domain = [
            ('employee_id.user_id', '=', user.id),
            ('line_type_id.name', 'ilike', 'certificate'),
        ] + extra
        domain = self._append_date_range(
            domain,
            'date_start',
            start,
            end,
            False,
        )
        return float(self.env['hr.resume.line'].search_count(domain))

    def _src_crm_qualified_lead(self, user, kpi, start, end, extra):
        Model, domain = self._get_model_and_domain(user, kpi, start, end, extra)
        return float(Model.search_count(domain))

    def _src_crm_activity(self, user, kpi, start, end, extra):
        return self._src_activity_count(user, kpi, start, end, extra)

    def _src_activity_count(self, user, kpi, start, end, extra):
        Model, domain = self._get_model_and_domain(user, kpi, start, end, extra)
        return float(Model.search_count(domain))

    def _src_sale_order(self, user, kpi, start, end, extra):
        Model, domain = self._get_model_and_domain(user, kpi, start, end, extra)
        domain.append(('state', 'in', ['sale', 'done']))
        return float(Model.search_count(domain))

    def _src_sale_revenue(self, user, kpi, start, end, extra):
        Model, domain = self._get_model_and_domain(user, kpi, start, end, extra)
        domain.append(('state', 'in', ['sale', 'done']))
        orders = Model.search(domain)
        return self._sum_records(orders, kpi.result_field or 'amount_total')

    def _src_sale_conversion(self, user, kpi, start, end, extra):
        scope_user_ids = self._get_scope_user_ids(user, kpi)
        base_domain = [
            ('user_id', 'in', scope_user_ids),
            ('create_date', '>=', fields.Datetime.from_string(str(start))),
            ('create_date', '<=', fields.Datetime.from_string(str(end) + ' 23:59:59')),
        ] + extra
        total = self.env['crm.lead'].search_count(base_domain)
        if not total:
            return 0.0
        won = self.env['crm.lead'].search_count(
            base_domain + [('probability', '=', 100)]
        )
        return round((won / total) * 100.0, 2)

    def _src_sale_conversion_30d(self, user, kpi, start, end, extra):
        quotations = self._get_sale_conversion_orders(user, kpi, start, end, extra)
        total = len(quotations)
        if not total:
            return 0.0

        converted = 0
        for quotation in quotations:
            if self._is_sale_order_converted_in_window(quotation, kpi):
                converted += 1

        return round((converted / total) * 100.0, 2)

    def _src_sale_converted_amount_30d(self, user, kpi, start, end, extra):
        quotations = self._get_sale_conversion_orders(user, kpi, start, end, extra)
        converted_orders = quotations.filtered(lambda order: self._is_sale_order_converted_in_window(order, kpi))
        return self._sum_records(converted_orders, kpi.result_field or 'amount_total')

    def _src_purchase_order(self, user, kpi, start, end, extra):
        Model, domain = self._get_model_and_domain(user, kpi, start, end, extra)
        domain.append(('state', 'in', ['purchase', 'done']))
        return float(Model.search_count(domain))

    def _src_purchase_amount(self, user, kpi, start, end, extra):
        Model, domain = self._get_model_and_domain(user, kpi, start, end, extra)
        domain.append(('state', 'in', ['purchase', 'done']))
        orders = Model.search(domain)
        return self._sum_records(orders, kpi.result_field or 'amount_total')

    def _src_helpdesk_ticket_opened(self, user, kpi, start, end, extra):
        Model, domain = self._get_model_and_domain(user, kpi, start, end, extra)
        return float(Model.search_count(domain))

    def _src_helpdesk_ticket_closed(self, user, kpi, start, end, extra):
        Model, domain = self._get_model_and_domain(user, kpi, start, end, extra)
        domain.append(('close_date', '!=', False))
        return float(Model.search_count(domain))

    def _src_helpdesk_ticket_closed_within_window(self, user, kpi, start, end, extra):
        tickets = self._get_closed_helpdesk_tickets(user, kpi, start, end, extra)
        return self._compute_within_window_percentage(
            tickets,
            start_field=kpi.turnaround_start_field or 'create_date',
            end_field=kpi.turnaround_end_field or 'close_date',
            window_value=self._get_window_value(kpi, fallback=7),
            window_unit=self._get_window_unit(kpi),
        )

    def _src_approval_decision_count(self, user, kpi, start, end, extra):
        decisions = self._get_approval_decisions(user, kpi, start, end, extra)
        return float(len(decisions))

    def _src_approval_decision_within_window(self, user, kpi, start, end, extra):
        decisions = self._get_approval_decisions(user, kpi, start, end, extra)
        return self._compute_within_window_percentage(
            decisions,
            start_field=kpi.turnaround_start_field or 'request_id.create_date',
            end_field=kpi.turnaround_end_field or 'decision_date',
            window_value=self._get_window_value(kpi, fallback=2),
            window_unit=self._get_window_unit(kpi),
        )

    def _src_expense_approved_count(self, user, kpi, start, end, extra):
        expenses = self._get_approved_expenses(user, kpi, start, end, extra)
        return float(len(expenses))

    def _src_expense_approval_within_window(self, user, kpi, start, end, extra):
        expenses = self._get_approved_expenses(user, kpi, start, end, extra)
        return self._compute_within_window_percentage(
            expenses,
            start_field=kpi.turnaround_start_field or 'sheet_id.submitted_on',
            end_field=kpi.turnaround_end_field or 'approved_on',
            window_value=self._get_window_value(kpi, fallback=2),
            window_unit=self._get_window_unit(kpi),
        )

    def _get_sale_conversion_orders(self, user, kpi, start, end, extra):
        SaleOrder = self.env['sale.order']
        sanitized_extra, removed_paths = sanitize_domain_for_model(
            self.env, 'sale.order', extra
        )
        if removed_paths:
            _logger.warning(
                'KPI %s: removed non-sale-order domain paths for conversion KPI: %s',
                kpi.name,
                ", ".join(removed_paths),
            )

        user_field = 'user_id'
        date_field = 'date_order'
        scope_user_ids = self._get_scope_user_ids(user, kpi)
        domain = [(user_field, 'in', scope_user_ids)] + sanitized_extra if scope_user_ids else [('id', '=', 0)]
        domain = self._append_date_range(
            domain,
            date_field,
            start,
            end,
            self._is_datetime_field(SaleOrder, date_field),
        )
        return SaleOrder.search(domain)

    def _get_sale_conversion_order_ids(self, user, kpi, start, end, extra):
        orders = self._get_sale_conversion_orders(user, kpi, start, end, extra)
        converted_orders = orders.filtered(lambda order: self._is_sale_order_converted_in_window(order, kpi))
        return converted_orders.ids

    def _is_sale_order_converted_in_window(self, order, kpi):
        if order.state not in ('sale', 'done'):
            return False
        if not order.create_date or not order.date_order:
            return False
        return self._is_within_window(
            order.create_date,
            order.date_order,
            self._get_window_value(kpi, fallback=30),
            self._get_window_unit(kpi),
        )

    def _src_custom(self, user, kpi, start, end, extra):
        if not (kpi.custom_model or kpi.source_model) or not (kpi.custom_date_field or kpi.source_date_field):
            return 0.0
        try:
            Model, domain = self._get_model_and_domain(user, kpi, start, end, extra)
        except UserError:
            _logger.warning('KPI %s: custom source configuration is invalid', kpi.name)
            return 0.0
        if kpi.aggregation == 'sum':
            records = Model.search(domain)
            return self._sum_records(records, kpi.result_field)
        return float(Model.search_count(domain))

    def _src_custom_turnaround_compliance(self, user, kpi, start, end, extra):
        Model, domain = self._get_model_and_domain(user, kpi, start, end, extra)
        records = Model.search(domain)
        return self._compute_within_window_percentage(
            records,
            start_field=kpi.turnaround_start_field or kpi.custom_date_field or kpi.source_date_field,
            end_field=kpi.turnaround_end_field or kpi.custom_date_field or kpi.source_date_field,
            window_value=self._get_window_value(kpi, fallback=10),
            window_unit=self._get_window_unit(kpi, fallback='minute'),
        )

    def _src_operating_hours_compliance(self, user, kpi, start, end, extra):
        Model, domain = self._get_model_and_domain(user, kpi, start, end, extra)
        records = Model.search(domain)
        return self._compute_operating_hours_percentage(
            user,
            records,
            kpi.compliance_time_field or kpi.custom_date_field or kpi.source_date_field,
            kpi.operating_hour_start,
            kpi.operating_hour_end,
        )

    def _get_approval_decisions(self, user, kpi, start, end, extra):
        Model, domain = self._get_model_and_domain(user, kpi, start, end, extra)
        domain += [
            ('status', 'in', ['approved', 'refused']),
            ('decision_date', '!=', False),
        ]
        return Model.search(domain)

    def _get_closed_helpdesk_tickets(self, user, kpi, start, end, extra):
        Model, domain = self._get_model_and_domain(user, kpi, start, end, extra)
        domain += [('close_date', '!=', False)]
        return Model.search(domain)

    def _get_approved_expenses(self, user, kpi, start, end, extra):
        Model, domain = self._get_model_and_domain(user, kpi, start, end, extra)
        domain += [
            ('approved_on', '!=', False),
            ('state', 'in', ['approved', 'done']),
        ]
        return Model.search(domain)

    def _get_window_value(self, kpi, fallback=0):
        return kpi.turnaround_window_value or kpi.conversion_window_days or fallback

    def _get_window_unit(self, kpi, fallback='day'):
        return kpi.turnaround_window_unit or fallback

    def _is_within_window(self, start_value, end_value, window_value, window_unit):
        if not start_value or not end_value:
            return False

        if isinstance(start_value, date) and not isinstance(start_value, datetime):
            start_dt = datetime.combine(start_value, datetime.min.time())
        else:
            start_dt = start_value

        if isinstance(end_value, date) and not isinstance(end_value, datetime):
            end_dt = datetime.combine(end_value, datetime.min.time())
        else:
            end_dt = end_value

        delta_seconds = (end_dt - start_dt).total_seconds()
        if delta_seconds < 0:
            return False

        unit_map = {
            'minute': 60.0,
            'hour': 3600.0,
            'day': 86400.0,
        }
        limit_seconds = float(window_value or 0) * unit_map.get(window_unit or 'day', 86400.0)
        return delta_seconds <= limit_seconds if limit_seconds > 0 else False

    def _compute_within_window_percentage(self, records, start_field, end_field, window_value, window_unit):
        total = len(records)
        if not total:
            return 0.0

        within_window = 0
        for record in records:
            start_value = self._get_nested_value(record, start_field)
            end_value = self._get_nested_value(record, end_field)
            if self._is_within_window(start_value, end_value, window_value, window_unit):
                within_window += 1

        return round((within_window / total) * 100.0, 2)

    def _compute_operating_hours_percentage(self, user, records, field_path, hour_start, hour_end):
        total = len(records)
        if not total or not field_path:
            return 0.0

        timezone_name = user.tz or self.env.company.partner_id.tz or 'UTC'
        timezone = pytz.timezone(timezone_name)
        compliant = 0
        for record in records:
            value = self._get_nested_value(record, field_path)
            if not value:
                continue
            if isinstance(value, date) and not isinstance(value, datetime):
                value = datetime.combine(value, datetime.min.time())
            if value.tzinfo is None:
                value = pytz.UTC.localize(value)
            local_value = value.astimezone(timezone)
            local_hour = local_value.hour + (local_value.minute / 60.0) + (local_value.second / 3600.0)
            if hour_start <= local_hour <= hour_end:
                compliant += 1

        return round((compliant / total) * 100.0, 2)

    def _get_nested_value(self, record, field_path):
        value = record
        for field_name in field_path.split('.'):
            if not value:
                return False
            value = value[field_name]
        return value

    # ------------------------------------------------------------------
    # Insight text generator
    # ------------------------------------------------------------------

    def _build_insight(self, kpi, actual, target, pct, status, data_point_count=0):
        unit = {'count': '', 'percentage': '%', 'amount': ''}.get(kpi.measure_type, '')
        period_label = {'daily': 'today', 'weekly': 'this week', 'monthly': 'this month', 'yearly': 'this year'}.get(kpi.period, 'this period')
        scope_label = 'team' if kpi.evaluation_scope == 'team' else 'your'

        if self._is_turnaround_kpi(kpi) and not data_point_count:
            return f"No records to evaluate for {kpi.name} {period_label}."

        if self._is_turnaround_kpi(kpi):
            if status == GREEN:
                return f"{kpi.name}: {actual:.0f}% met the window for {period_label}."
            if status == YELLOW:
                return f"{kpi.name}: {actual:.0f}% met the window for {period_label}, slightly below target."
            return f"{kpi.name}: only {actual:.0f}% met the window for {period_label}."

        if status == GREEN:
            return f"Great! {scope_label.capitalize()} {kpi.name} reached {pct:.0f}% of target for {period_label}."
        if status == YELLOW:
            return f"{scope_label.capitalize()} {kpi.name} is at {pct:.0f}% of target for {period_label}."
        return f"Below target: {actual:.0f}{unit} vs {target:.0f}{unit} for {kpi.name} {period_label}."

    def _get_trend_results(self, result, limit=None):
        limit = limit or result.kpi_id.trend_period_count or 6
        return self.search(
            [
                ('user_id', '=', result.user_id.id),
                ('kpi_id', '=', result.kpi_id.id),
            ],
            order='period_start desc',
            limit=limit,
        )

    # ------------------------------------------------------------------
    # RPC method for systray
    # ------------------------------------------------------------------

    @api.model
    def get_my_kpi_summary(self):
        """Return current user's KPI results and overall status. Called by OWL component."""
        self._ensure_enterprise_history_backfilled()
        user = self.env.user
        traffic = self.env['kpi.traffic.light'].search([('user_id', '=', user.id)], limit=1)

        overall_status = traffic.overall_status if traffic else GREY
        overall_pct = traffic.overall_percentage if traffic else 0.0

        results = self._get_current_results_for_user(user.id)
        kpi_list = []
        KpiResultSudo = self.sudo()
        for r in results:
            result_sudo = r.sudo()
            KpiResultSudo._ensure_kpi_history(result_sudo.user_id, result_sudo.kpi_id)
            trend_results = self.search(
                [('user_id', '=', r.user_id.id), ('kpi_id', '=', r.kpi_id.id)],
                order='period_start desc',
                limit=r.kpi_id.trend_period_count or 6,
            )
            kpi_list.append({
                'id': r.id,
                'name': r.kpi_id.name,
                'period': r.kpi_id.period,
                'target': r.target_value,
                'actual': r.actual_value,
                'percentage': r.percentage,
                'status': r.status,
                'insight': r.insight_text or '',
                'last_updated': r.last_updated.isoformat() if r.last_updated else '',
                'trend': [
                    {
                        'period_start': trend.period_start.isoformat() if trend.period_start else '',
                        'actual': trend.actual_value,
                        'percentage': trend.percentage,
                        'status': trend.status,
                    }
                    for trend in trend_results
                ],
            })

        return {
            'overall_status': overall_status,
            'overall_percentage': overall_pct,
            'kpis': kpi_list,
        }
