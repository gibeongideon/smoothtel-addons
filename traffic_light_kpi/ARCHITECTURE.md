# KPI Traffic Light System – Technical Architecture

**Odoo Version:** 18.0
**Date:** 2026-05-11

---

## 1. Module Overview

```
traffic_light_kpi (Odoo module)
  │
  ├── Backend Models (Python)
  │     ├── kpi.definition        → KPI templates per job position
  │     ├── kpi.result            → Computed actuals per user per KPI + historical snapshots
  │     ├── kpi.traffic.light     → Aggregated user status (overall color)
  │     ├── approval.request      → inherited to track approver decision timestamp
  │     ├── approval.approver     → inherited with decision_date
  │     ├── hr.expense.sheet      → inherited with submitted_on
  │     └── hr.employee inherit   → Immediate KPI recompute on role changes
  │
  ├── Cron Jobs
  │     └── Hourly recalculation of kpi.result
  │
  ├── Frontend (OWL 2 / Odoo 18)
  │     ├── Systray component     → Traffic light dot in nav bar
  │     └── KPI dashboard         → User KPI cards + drill-down + trend views
  │
  └── Security
        ├── Groups: employee / manager / kpi_admin
        └── Record rules: own-data isolation
```

---

## 2. Data Model

### 2.1 `kpi.definition`

Defines a KPI template. Not user-specific.

```
kpi.definition
├── name                  (Char, required)
├── job_position_ids      (Many2many → hr.job)
├── evaluation_scope      (Selection: individual/team)
├── team_member_job_ids   (Many2many → hr.job, optional team filter)
├── normalize_per_member  (Boolean, optional team KPI normalizer)
├── target_value          (Float, required)
├── period                (Selection: daily/weekly/monthly/yearly)
├── measure_type          (Selection: count/percentage/amount)
├── trend_period_count    (Integer, default 6)
├── data_source           (Selection: crm_lead/crm_activity/sale_order/
│                                    sale_revenue/sale_conversion/
│                                    purchase_order/purchase_amount/
│                                    helpdesk_ticket/approval_request/
│                                    hr_expense/custom)
├── turnaround_start_field (Char, optional)
├── turnaround_end_field   (Char, optional)
├── turnaround_window_value (Float, optional)
├── turnaround_window_unit  (Selection: minute/hour/day)
├── compliance_time_field   (Char, optional)
├── operating_hour_start    (Float, optional)
├── operating_hour_end      (Float, optional)
├── domain_filter         (Char, optional JSON domain)
├── custom_model          (Char, for data_source=custom)
├── custom_date_field     (Char, for data_source=custom)
├── custom_user_field     (Char, default=user_id)
├── description           (Text)
├── weight                (Float, default=1.0, for weighted scoring)
└── active                (Boolean, default=True)
```

### 2.2 `kpi.result`

Stores the computed result for one user + one KPI definition.

```
kpi.result
├── kpi_id                (Many2one → kpi.definition, required)
├── user_id               (Many2one → res.users, required)
├── employee_id           (Many2one → hr.employee, related)
├── period_start          (Date, start of evaluated window)
├── period_end            (Date, end of evaluated window)
├── target_value          (Float, copied from kpi.definition at compute time)
├── actual_value          (Float, computed from Odoo data)
├── percentage            (Float, computed: actual/target * 100)
├── status                (Selection: green/yellow/red/grey)
├── data_point_count      (Integer, supporting turnaround/compliance KPIs)
├── insight_text          (Char, auto-generated insight)
└── last_updated          (Datetime)
```

_Unique constraint: (kpi_id, user_id, period_start)_

### 2.3 `kpi.traffic.light` (or computed on `res.users` extension)

Aggregated per-user overall status. Can be a computed field on `hr.employee` or a separate lightweight model.

```
kpi.traffic.light
├── user_id               (Many2one → res.users, unique)
├── employee_id           (Many2one → hr.employee)
├── overall_percentage    (Float)
├── overall_status        (Selection: green/yellow/red/grey)
├── kpi_count             (Integer)
└── last_updated          (Datetime)
```

---

## 3. Computation Engine

### 3.1 Entry Point

`kpi.result` model → method `_compute_all_results()` called by cron.

Immediate recompute is also triggered when:
- a `kpi.definition` is created, updated, archived, or deleted
- an employee's `job_id`, `user_id`, or `active` state changes

### 3.2 Flow

```
For each active hr.employee with a linked user:
  1. Get job_position → find all kpi.definition records
  2. For each kpi.definition:
     a. Calculate current period_start / period_end
     b. Resolve scope users:
        - individual KPI → the employee user
        - team KPI → employee direct reports via hr.employee.parent_id.user_id
     c. Run domain query against data_source model
     d. Calculate actual_value
        - optionally normalize by matched team-member count
     d. Read target_value from kpi.definition
     e. Calculate percentage = actual / target * 100
     f. Assign status (green/yellow/red)
     g. Generate insight_text
     h. Upsert kpi.result record
     i. Backfill prior periods on demand for trend display
  3. Remove stale `kpi.result` rows if the employee no longer matches a KPI
  4. Aggregate all results → update kpi.traffic.light
```

### 3.3 Data Source Implementations

```python
# crm_lead
domain = [('user_id', '=', user_id), ('create_date', '>=', period_start)]
count = env['crm.lead'].search_count(domain)

# crm_activity (done activities)
domain = [('user_id', '=', user_id), ('date_done', '>=', period_start),
          ('activity_type_id.name', 'ilike', 'call')]
count = env['mail.activity'].search_count(domain)  # or mail.activity.type

# sale_order (confirmed count)
domain = [('user_id', '=', user_id), ('state', 'in', ['sale','done']),
          ('date_order', '>=', period_start)]
count = env['sale.order'].search_count(domain)

# sale_revenue
domain = [('user_id', '=', user_id), ('state', 'in', ['sale','done']),
          ('date_order', '>=', period_start)]
orders = env['sale.order'].search(domain)
value = sum(orders.mapped('amount_total'))  # for amount type

# sale_conversion (% leads → orders)
leads_total = env['crm.lead'].search_count([('user_id','=',user_id), ...])
leads_won   = env['crm.lead'].search_count([('user_id','=',user_id),
              ('stage_id.is_won','=',True), ...])
pct = (leads_won / leads_total * 100) if leads_total else 0

# purchase_order
domain = [('user_id','=',user_id), ('state','in',['purchase','done']),
          ('date_order','>=',period_start)]

# purchase_amount
orders = env['purchase.order'].search(domain)
value = sum(orders.mapped('amount_total'))

# helpdesk_ticket_opened_count
domain = [('user_id', '=', user_id), ('create_date', '>=', period_start)]
count = env['helpdesk.ticket'].search_count(domain)

# helpdesk_ticket_closed_count
domain = [('user_id', '=', user_id), ('close_date', '!=', False),
          ('close_date', '>=', period_start)]
count = env['helpdesk.ticket'].search_count(domain)

# approval_decision_count
domain = [('user_id', '=', user_id), ('status', 'in', ['approved', 'refused']),
          ('decision_date', '>=', period_start)]
count = env['approval.approver'].search_count(domain)

# approval_decision_within_window
for approver in env['approval.approver'].search(domain):
    delta_days = (approver.decision_date.date() - approver.request_id.create_date.date()).days

# custom_turnaround_compliance
for record in env[custom_model].search(domain):
    start_value = record[turnaround_start_field]
    end_value = record[turnaround_end_field]
    within_window = delta(start_value, end_value) <= configured_minutes_hours_or_days

# operating_hours_compliance
for record in env[custom_model].search(domain):
    local_dt = to_user_timezone(record[compliance_time_field])
    within_hours = operating_hour_start <= local_hour <= operating_hour_end

# expense_approved_count
domain = [('approved_by', '=', user_id), ('approved_on', '>=', period_start),
          ('state', 'in', ['approved', 'done'])]
count = env['hr.expense'].search_count(domain)

# expense_approval_within_window
for expense in env['hr.expense'].search(domain):
    delta_days = (expense.approved_on.date() - expense.sheet_id.submitted_on.date()).days
```

---

## 4. Frontend Architecture (OWL 2)

### 4.1 Systray Component

File: `static/src/js/kpi_traffic_light_systray.js`

```javascript
// OWL Component registered in web.systray
KpiTrafficLightSystray:
  - onWillStart(): fetch kpi.result.get_my_kpi_summary()
  - render(): show colored traffic light dot + score
  - onClick(): open user KPI dashboard action
  - Auto-refresh: setInterval every 5 minutes OR on window focus
```

Template: `static/src/xml/kpi_traffic_light_systray.xml`

```xml
<t t-name="traffic_light_kpi.KpiTrafficLightSystray">
  <div class="kpi-traffic-light" t-on-click="openDashboard">
    <span t-att-class="trafficLightClass" title="My KPI Status"/>
  </div>
</t>
```

### 4.2 CSS Animation

File: `static/src/css/kpi_traffic_light.css`

```css
.kpi-tl-red    { background: #e74c3c; animation: blink 1s step-start infinite; }
.kpi-tl-yellow { background: #f39c12; animation: blink 1.5s step-start infinite; }
.kpi-tl-green  { background: #27ae60; }
.kpi-tl-grey   { background: #95a5a6; }

@keyframes blink {
  50% { opacity: 0; }
}
```

### 3.4 Historical Trend Strategy

- `kpi.result` keeps one row per `(kpi_id, user_id, period_start)`
- Current-period rows remain the primary dashboard source
- Prior-period rows are backfilled on demand using `trend_period_count`
- Trend history is exposed through graph/pivot/list views and via the systray summary RPC

---

## 4. Frontend Architecture (OWL 2)

### 4.3 KPI Dashboard

- Implemented as an Odoo `ir.actions.act_window` on `kpi.result`
- Opens a kanban-first dashboard filtered to the current user
- Each KPI card shows target, actual, percentage, status badge, and traffic light
- List and form views also expose the same KPI details
- Each KPI record has a `View Records` object action
- Each KPI record also has a `View Trend` action opening graph/pivot/list history

### 4.4 Source Drill-Down

Each `kpi.result` can open the underlying source records using
`action_open_source_records()`.

Supported drill-down targets:
- `crm_lead` / `sale_conversion` → `crm.lead`
- `crm_activity` → `mail.activity`
- `sale_order` / `sale_revenue` → `sale.order`
- `purchase_order` / `purchase_amount` → `purchase.order`
- `helpdesk_ticket` → `helpdesk.ticket`
- `approval_request` → `approval.approver`
- `hr_expense` → `hr.expense`
- `custom` → configured custom model

The action applies:
- the KPI period window (`period_start` → `period_end`)
- the current KPI user or resolved team scope
- any optional `domain_filter` from the KPI definition

---

## 5. Cron Schedule

```xml
<record id="cron_kpi_recalculate" model="ir.cron">
  <field name="name">KPI Traffic Light: Recalculate Results</field>
  <field name="model_id" ref="model_kpi_result"/>
  <field name="state">code</field>
  <field name="code">model._compute_all_results()</field>
  <field name="interval_number">1</field>
  <field name="interval_type">hours</field>
  <field name="numbercall">-1</field>
  <field name="active">True</field>
</record>
```

---

## 6. Security Groups

```
traffic_light_kpi.group_kpi_user    → base employees (auto-applied)
traffic_light_kpi.group_kpi_manager → managers (can see team)
traffic_light_kpi.group_kpi_admin   → can configure kpi.definition
```

Record rules:
- `kpi.result`: employees see only own records
- `kpi.traffic.light`: employees see only own record
- Managers: see all KPI records allowed by the manager rule

---

## 7. Dependencies

```python
# __manifest__.py
'depends': [
    'base',
    'hr',          # hr.employee, hr.job
    'crm',         # crm.lead
    'sale_management',  # sale.order
    'purchase',    # purchase.order
    'mail',        # mail.message / activity trail
    'web',         # systray
],
```

---

## 8. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| KPI assignment | Via job position (hr.job) | No per-user admin overhead |
| Result storage | Stored (not computed) | Cron-driven, avoids per-request queries |
| Frontend | OWL 2 systray | Native Odoo 18 pattern |
| Refresh strategy | Immediate hooks + cron hourly + client polling 5min | Fast feedback with scheduled safety net |
| Blink animation | CSS keyframes only | No JS timer, performant |
| Overall score | Weighted average of KPI percentages | Supports KPI importance |
| KPI drill-down | Object action per KPI result | Lets users inspect source records behind each KPI |
