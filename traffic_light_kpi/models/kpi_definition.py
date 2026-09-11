import json

from odoo import models, fields, api
from odoo.exceptions import ValidationError

from .domain_utils import sanitize_domain_for_model


class KpiDefinition(models.Model):
    _name = 'kpi.definition'
    _description = 'KPI Definition'
    _order = 'name'

    name = fields.Char(string='KPI Name', required=True)
    job_position_ids = fields.Many2many(
        'hr.job',
        'kpi_definition_job_position_rel',
        'kpi_id',
        'job_id',
        string='Job Positions',
        help='Roles this KPI applies to. Users with these positions get this KPI automatically.',
    )
    target_value = fields.Float(string='Target Value', required=True, default=1.0)
    evaluation_scope = fields.Selection(
        [
            ('individual', 'Individual'),
            ('team', 'Team'),
        ],
        string='Evaluation Scope',
        required=True,
        default='individual',
        help='Choose Team when the KPI should be measured on the assignee user direct reports.',
    )
    team_member_job_ids = fields.Many2many(
        'hr.job',
        'kpi_definition_team_member_job_rel',
        'kpi_id',
        'job_id',
        string='Team Member Positions',
        help='Optional role filter used when Evaluation Scope is Team.',
    )
    normalize_per_member = fields.Boolean(
        string='Normalize Per Team Member',
        help='For Team KPIs, divide count or amount results by the number of matched team members.',
    )
    department = fields.Selection(
        [
            ('sales', 'Sales'),
            ('procurement', 'Procurement'),
            ('customer_service', 'Customer Service'),
            ('finance', 'Finance'),
            ('operations', 'Operations'),
            ('other', 'Other'),
        ],
        string='Department',
        default='other',
        help='Business area this KPI belongs to.',
    )
    kpi_code = fields.Selection(
        [
            ('crm_lead_count', 'CRM Leads Count'),
            ('monetary_lead_generation', 'Monetary Lead Generation'),
            ('crm_qualified_lead_count', 'Qualified Leads Count'),
            ('activity_count', 'Activity Count'),
            ('skills_count', 'Skills'),
            ('certification_count', 'Certification'),
            ('sale_conversion_30d', 'Quotation Conversion Within Window'),
            ('sale_converted_amount_30d', 'Converted Sales Amount Within Window'),
            ('purchase_order_count', 'Purchase Order Count'),
            ('purchase_order_amount', 'Purchase Order Amount'),
            ('helpdesk_ticket_opened_count', 'Helpdesk Tickets Opened'),
            ('helpdesk_ticket_closed_count', 'Helpdesk Tickets Closed'),
            ('helpdesk_ticket_closed_within_window', 'Helpdesk Tickets Closed Within Window'),
            ('approval_decision_count', 'Approval Decisions Processed'),
            ('approval_decision_within_window', 'Approval Decisions Within Window'),
            ('store_requisition_approval_within_window', 'Store Requisition Issuing Within Window'),
            ('quotation_approval_within_window', 'Quotation Approval Within Window'),
            ('expense_approved_count', 'Expenses Approved'),
            ('expense_approval_within_window', 'Expense Approvals Within Window'),
            ('custom_turnaround_compliance', 'Custom Turnaround Compliance'),
            ('operating_hours_compliance', 'Operating Hours Compliance'),
            ('custom_count', 'Custom Count'),
            ('custom_sum', 'Custom Sum'),
        ],
        string='KPI Logic',
        required=True,
        default='crm_lead_count',
        help='Determines how the KPI is computed.',
    )
    period = fields.Selection(
        [
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
            ('yearly', 'Yearly'),
        ],
        string='Period',
        required=True,
        default='yearly',
    )
    measure_type = fields.Selection(
        [
            ('count', 'Count'),
            ('percentage', 'Percentage'),
            ('amount', 'Amount (Currency)'),
        ],
        string='Measure Type',
        required=True,
        default='count',
    )
    aggregation = fields.Selection(
        [
            ('count', 'Count'),
            ('sum', 'Sum'),
            ('percentage', 'Percentage'),
        ],
        string='Aggregation',
        required=True,
        default='count',
        help='How the KPI value should be aggregated from source records.',
    )
    data_source = fields.Selection(
        [
            ('crm_lead', 'CRM – Leads Created'),
            ('crm_activity', 'CRM – Activities Done'),
            ('sale_order', 'Sales – Confirmed Orders (Count)'),
            ('sale_revenue', 'Sales – Revenue (Amount)'),
            ('sale_conversion', 'Sales – Lead to Order Conversion (%)'),
            ('purchase_order', 'Procurement – Purchase Orders'),
            ('purchase_amount', 'Procurement – PO Amount'),
            ('helpdesk_ticket', 'Helpdesk – Tickets'),
            ('approval_request', 'Approvals – Decisions'),
            ('hr_expense', 'Expenses – Approvals'),
            ('custom', 'Custom (Admin Defined)'),
        ],
        string='Data Source',
        required=True,
        default='crm_lead',
    )
    source_model = fields.Char(
        string='Source Model',
        help='Technical model name used for this KPI, e.g. crm.lead or purchase.order.',
    )
    source_date_field = fields.Char(
        string='Source Date Field',
        help='Field used to apply the KPI period window, e.g. create_date or date_order.',
    )
    source_user_field = fields.Char(
        string='Source User Field',
        default='user_id',
        help='Field linking the source record to a responsible user.',
    )
    result_field = fields.Char(
        string='Result Field',
        help='Numeric field to sum for amount-based KPIs, e.g. amount_total.',
    )
    activity_type_id = fields.Many2one(
        'mail.activity.type',
        string='Activity Type',
        help='Optional activity type for call/visit KPIs.',
    )
    stage_id = fields.Many2one(
        'crm.stage',
        string='CRM Stage',
        help='Optional CRM stage for stage-based KPIs such as qualified leads.',
    )
    conversion_window_days = fields.Integer(
        string='Conversion Window (Days)',
        default=30,
        help='Used for time-bound conversion KPIs, e.g. convert within 30 days.',
    )
    turnaround_start_field = fields.Char(
        string='Turnaround Start Field',
        help='Field path used as the start timestamp for compliance checks.',
    )
    turnaround_end_field = fields.Char(
        string='Turnaround End Field',
        help='Field path used as the end timestamp for compliance checks.',
    )
    turnaround_window_value = fields.Float(
        string='Turnaround Window',
        default=0.0,
        help='Allowed turnaround size, for example 10 minutes or 1 hour.',
    )
    turnaround_window_unit = fields.Selection(
        [
            ('minute', 'Minutes'),
            ('hour', 'Hours'),
            ('day', 'Days'),
        ],
        string='Turnaround Unit',
        default='day',
        required=True,
    )
    compliance_time_field = fields.Char(
        string='Operating Hours Field',
        help='Datetime field checked against operating hours compliance.',
    )
    operating_hour_start = fields.Float(
        string='Operating Hours Start',
        default=10.0,
        help='Start hour in local time, for example 10.0 for 10:00 AM.',
    )
    operating_hour_end = fields.Float(
        string='Operating Hours End',
        default=16.5,
        help='End hour in local time, for example 16.5 for 4:30 PM.',
    )
    trend_period_count = fields.Integer(
        string='Trend Periods',
        default=6,
        help='How many historical periods should be shown in the KPI trend.',
    )
    # Custom source fields
    custom_model = fields.Char(
        string='Custom Model',
        help='Technical model name, e.g. project.task',
    )
    custom_date_field = fields.Char(
        string='Custom Date Field',
        help='Field to filter by date, e.g. create_date',
    )
    custom_user_field = fields.Char(
        string='Custom User Field',
        help='Field that links to res.users, e.g. user_id',
        default='user_id',
    )
    domain_filter = fields.Char(
        string='Extra Domain Filter',
        help='JSON domain appended to the query, e.g. [["stage_id.is_won","=",true]]',
    )
    weight = fields.Float(
        string='Weight',
        default=1.0,
        help='Relative weight when calculating overall score (default 1.0 = equal weight)',
    )
    description = fields.Text(string='Description / Notes')
    active = fields.Boolean(default=True)
    is_turnaround_kpi = fields.Boolean(
        string='Is Turnaround KPI',
        compute='_compute_is_turnaround_kpi',
    )
    target_field_help = fields.Char(
        string='Target Help',
        compute='_compute_target_field_help',
    )

    # Computed display
    job_position_count = fields.Integer(
        string='Positions',
        compute='_compute_job_position_count',
    )

    @api.depends('job_position_ids')
    def _compute_job_position_count(self):
        for rec in self:
            rec.job_position_count = len(rec.job_position_ids)

    @api.depends('kpi_code')
    def _compute_is_turnaround_kpi(self):
        turnaround_codes = {
            'helpdesk_ticket_closed_within_window',
            'approval_decision_within_window',
            'store_requisition_approval_within_window',
            'quotation_approval_within_window',
            'expense_approval_within_window',
            'custom_turnaround_compliance',
            'operating_hours_compliance',
        }
        for rec in self:
            rec.is_turnaround_kpi = rec.kpi_code in turnaround_codes

    @api.depends('is_turnaround_kpi')
    def _compute_target_field_help(self):
        for rec in self:
            if rec.is_turnaround_kpi:
                rec.target_field_help = (
                    'Use this as a compliance target percentage, for example 90 means '
                    '90% of records should meet the configured time window.'
                )
            else:
                rec.target_field_help = (
                    'Use this as the normal KPI target value, for example number of tickets, '
                    'amount, or percentage target.'
                )

    @api.model
    def _get_kpi_logic_presets(self):
        return {
            'crm_lead_count': {
                'department': 'sales',
                'evaluation_scope': 'individual',
                'measure_type': 'count',
                'aggregation': 'count',
                'data_source': 'crm_lead',
                'source_model': 'crm.lead',
                'source_date_field': 'create_date',
                'source_user_field': 'user_id',
                'result_field': False,
                'activity_type_id': False,
                'stage_id': False,
            },
            'monetary_lead_generation': {
                'department': 'sales',
                'evaluation_scope': 'individual',
                'measure_type': 'amount',
                'aggregation': 'sum',
                'data_source': 'crm_lead',
                'source_model': 'crm.lead',
                'source_date_field': 'create_date',
                'source_user_field': 'user_id',
                'result_field': 'expected_revenue',
                'activity_type_id': False,
                'stage_id': False,
            },
            'crm_qualified_lead_count': {
                'department': 'sales',
                'evaluation_scope': 'individual',
                'measure_type': 'count',
                'aggregation': 'count',
                'data_source': 'crm_lead',
                'source_model': 'crm.lead',
                'source_date_field': 'create_date',
                'source_user_field': 'user_id',
                'result_field': False,
                'activity_type_id': False,
            },
            'activity_count': {
                'evaluation_scope': 'individual',
                'measure_type': 'count',
                'aggregation': 'count',
                'data_source': 'crm_activity',
                'source_model': 'mail.activity',
                'source_date_field': 'date_deadline',
                'source_user_field': 'user_id',
                'result_field': False,
                'stage_id': False,
            },
            'skills_count': {
                'department': 'other',
                'evaluation_scope': 'individual',
                'measure_type': 'count',
                'aggregation': 'count',
                'data_source': 'custom',
                'source_model': 'hr.employee.skill',
                'source_date_field': 'create_date',
                'source_user_field': 'employee_id.user_id',
                'result_field': False,
                'activity_type_id': False,
                'stage_id': False,
            },
            'certification_count': {
                'department': 'other',
                'evaluation_scope': 'individual',
                'measure_type': 'count',
                'aggregation': 'count',
                'data_source': 'custom',
                'source_model': 'hr.resume.line',
                'source_date_field': 'date_start',
                'source_user_field': 'employee_id.user_id',
                'result_field': False,
                'activity_type_id': False,
                'stage_id': False,
            },
            'sale_conversion_30d': {
                'department': 'sales',
                'evaluation_scope': 'individual',
                'measure_type': 'percentage',
                'aggregation': 'percentage',
                'data_source': 'sale_conversion',
                'source_model': 'sale.order',
                'source_date_field': 'date_order',
                'source_user_field': 'user_id',
                'result_field': False,
                'conversion_window_days': 30,
                'turnaround_window_value': 30,
                'turnaround_window_unit': 'day',
                'activity_type_id': False,
                'stage_id': False,
            },
            'sale_converted_amount_30d': {
                'department': 'sales',
                'evaluation_scope': 'individual',
                'measure_type': 'amount',
                'aggregation': 'sum',
                'data_source': 'sale_revenue',
                'source_model': 'sale.order',
                'source_date_field': 'date_order',
                'source_user_field': 'user_id',
                'result_field': 'amount_total',
                'conversion_window_days': 30,
                'turnaround_window_value': 30,
                'turnaround_window_unit': 'day',
                'activity_type_id': False,
                'stage_id': False,
            },
            'purchase_order_count': {
                'department': 'procurement',
                'evaluation_scope': 'individual',
                'measure_type': 'count',
                'aggregation': 'count',
                'data_source': 'purchase_order',
                'source_model': 'purchase.order',
                'source_date_field': 'date_order',
                'source_user_field': 'user_id',
                'result_field': False,
                'activity_type_id': False,
                'stage_id': False,
            },
            'purchase_order_amount': {
                'department': 'procurement',
                'evaluation_scope': 'individual',
                'measure_type': 'amount',
                'aggregation': 'sum',
                'data_source': 'purchase_amount',
                'source_model': 'purchase.order',
                'source_date_field': 'date_order',
                'source_user_field': 'user_id',
                'result_field': 'amount_total',
                'activity_type_id': False,
                'stage_id': False,
            },
            'helpdesk_ticket_opened_count': {
                'department': 'customer_service',
                'evaluation_scope': 'individual',
                'measure_type': 'count',
                'aggregation': 'count',
                'data_source': 'helpdesk_ticket',
                'source_model': 'helpdesk.ticket',
                'source_date_field': 'create_date',
                'source_user_field': 'user_id',
                'result_field': False,
                'activity_type_id': False,
                'stage_id': False,
            },
            'helpdesk_ticket_closed_count': {
                'department': 'customer_service',
                'evaluation_scope': 'individual',
                'measure_type': 'count',
                'aggregation': 'count',
                'data_source': 'helpdesk_ticket',
                'source_model': 'helpdesk.ticket',
                'source_date_field': 'close_date',
                'source_user_field': 'user_id',
                'result_field': False,
                'activity_type_id': False,
                'stage_id': False,
            },
            'helpdesk_ticket_closed_within_window': {
                'department': 'customer_service',
                'evaluation_scope': 'individual',
                'measure_type': 'percentage',
                'aggregation': 'percentage',
                'data_source': 'helpdesk_ticket',
                'source_model': 'helpdesk.ticket',
                'source_date_field': 'close_date',
                'source_user_field': 'user_id',
                'result_field': False,
                'conversion_window_days': 7,
                'turnaround_window_value': 7,
                'turnaround_window_unit': 'day',
                'turnaround_start_field': 'create_date',
                'turnaround_end_field': 'close_date',
                'activity_type_id': False,
                'stage_id': False,
            },
            'approval_decision_count': {
                'department': 'operations',
                'evaluation_scope': 'individual',
                'measure_type': 'count',
                'aggregation': 'count',
                'data_source': 'approval_request',
                'source_model': 'approval.approver',
                'source_date_field': 'decision_date',
                'source_user_field': 'user_id',
                'result_field': False,
                'activity_type_id': False,
                'stage_id': False,
            },
            'approval_decision_within_window': {
                'department': 'operations',
                'evaluation_scope': 'individual',
                'measure_type': 'percentage',
                'aggregation': 'percentage',
                'data_source': 'approval_request',
                'source_model': 'approval.approver',
                'source_date_field': 'decision_date',
                'source_user_field': 'user_id',
                'result_field': False,
                'conversion_window_days': 2,
                'turnaround_window_value': 2,
                'turnaround_window_unit': 'day',
                'turnaround_start_field': 'request_id.create_date',
                'turnaround_end_field': 'decision_date',
                'activity_type_id': False,
                'stage_id': False,
            },
            'store_requisition_approval_within_window': {
                'department': 'procurement',
                'evaluation_scope': 'individual',
                'measure_type': 'percentage',
                'aggregation': 'percentage',
                'data_source': 'approval_request',
                'source_model': 'approval.approver',
                'source_date_field': 'decision_date',
                'source_user_field': 'user_id',
                'result_field': False,
                'conversion_window_days': 2,
                'turnaround_window_value': 2,
                'turnaround_window_unit': 'day',
                'turnaround_start_field': 'request_id.create_date',
                'turnaround_end_field': 'decision_date',
                'activity_type_id': False,
                'stage_id': False,
            },
            'quotation_approval_within_window': {
                'department': 'sales',
                'evaluation_scope': 'individual',
                'measure_type': 'percentage',
                'aggregation': 'percentage',
                'data_source': 'approval_request',
                'source_model': 'approval.approver',
                'source_date_field': 'decision_date',
                'source_user_field': 'user_id',
                'result_field': False,
                'conversion_window_days': 2,
                'turnaround_window_value': 2,
                'turnaround_window_unit': 'day',
                'turnaround_start_field': 'request_id.create_date',
                'turnaround_end_field': 'decision_date',
                'activity_type_id': False,
                'stage_id': False,
            },
            'expense_approved_count': {
                'department': 'finance',
                'evaluation_scope': 'individual',
                'measure_type': 'count',
                'aggregation': 'count',
                'data_source': 'hr_expense',
                'source_model': 'hr.expense',
                'source_date_field': 'approved_on',
                'source_user_field': 'approved_by',
                'result_field': False,
                'activity_type_id': False,
                'stage_id': False,
            },
            'expense_approval_within_window': {
                'department': 'finance',
                'evaluation_scope': 'individual',
                'measure_type': 'percentage',
                'aggregation': 'percentage',
                'data_source': 'hr_expense',
                'source_model': 'hr.expense',
                'source_date_field': 'approved_on',
                'source_user_field': 'approved_by',
                'result_field': False,
                'conversion_window_days': 2,
                'turnaround_window_value': 2,
                'turnaround_window_unit': 'day',
                'turnaround_start_field': 'sheet_id.submitted_on',
                'turnaround_end_field': 'approved_on',
                'activity_type_id': False,
                'stage_id': False,
            },
            'custom_turnaround_compliance': {
                'evaluation_scope': 'individual',
                'measure_type': 'percentage',
                'aggregation': 'percentage',
                'data_source': 'custom',
                'turnaround_window_value': 10,
                'turnaround_window_unit': 'minute',
            },
            'operating_hours_compliance': {
                'evaluation_scope': 'individual',
                'measure_type': 'percentage',
                'aggregation': 'percentage',
                'data_source': 'custom',
                'operating_hour_start': 10.0,
                'operating_hour_end': 16.5,
            },
            'custom_count': {
                'evaluation_scope': 'individual',
                'measure_type': 'count',
                'aggregation': 'count',
                'data_source': 'custom',
            },
            'custom_sum': {
                'evaluation_scope': 'individual',
                'measure_type': 'amount',
                'aggregation': 'sum',
                'data_source': 'custom',
            },
        }

    @api.onchange('kpi_code')
    def _onchange_kpi_code(self):
        config_map = self._get_kpi_logic_presets()
        for rec in self:
            values = config_map.get(rec.kpi_code, {})
            rec.update(values)

    @api.constrains('domain_filter')
    def _check_domain_filter(self):
        for rec in self.filtered('domain_filter'):
            try:
                parsed = json.loads(rec.domain_filter)
                if not isinstance(parsed, list):
                    raise ValueError
            except Exception as exc:
                raise ValidationError(f"Invalid JSON domain for KPI '{rec.name}'.") from exc

            sanitized_domain, removed_paths = sanitize_domain_for_model(
                self.env, rec._get_effective_source_model_name(), parsed
            )
            if removed_paths:
                raise ValidationError(
                    "Invalid field path(s) in KPI '%s' extra domain: %s"
                    % (rec.name, ", ".join(removed_paths))
                )

    def _get_effective_source_model_name(self):
        self.ensure_one()
        return self.source_model or self.custom_model or {
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
            'custom': self.custom_model,
        }.get(self.data_source)

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._prepare_logic_defaults(vals) for vals in vals_list]
        records = super().create(vals_list)
        records._trigger_kpi_recompute()
        return records

    def _prepare_logic_defaults(self, vals):
        vals = dict(vals)
        code = vals.get('kpi_code')
        if not code:
            return vals
        preset = self._get_kpi_logic_presets().get(code, {})
        for key, value in preset.items():
            vals.setdefault(key, value)
        return vals

    def _trigger_kpi_recompute(self):
        self.env['kpi.result'].sudo()._compute_all_results()

    def write(self, vals):
        vals = self._prepare_logic_defaults(vals)
        result = super().write(vals)
        if any(
            field in vals
            for field in (
                'department',
                'kpi_code',
                'job_position_ids',
                'target_value',
                'period',
                'measure_type',
                'aggregation',
                'data_source',
                'source_model',
                'source_date_field',
                'source_user_field',
                'result_field',
                'activity_type_id',
                'stage_id',
                'conversion_window_days',
                'turnaround_start_field',
                'turnaround_end_field',
                'turnaround_window_value',
                'turnaround_window_unit',
                'compliance_time_field',
                'operating_hour_start',
                'operating_hour_end',
                'evaluation_scope',
                'team_member_job_ids',
                'normalize_per_member',
                'trend_period_count',
                'custom_model',
                'custom_date_field',
                'custom_user_field',
                'domain_filter',
                'weight',
                'active',
            )
        ):
            self._trigger_kpi_recompute()
        return result

    def unlink(self):
        result = super().unlink()
        self.env['kpi.result'].sudo()._compute_all_results()
        return result
