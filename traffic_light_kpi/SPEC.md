# KPI Traffic Light System – Functional Specification

**Version:** 1.1
**Odoo Version:** 18.0
**Date:** 2026-05-11

---

## 1. Objective

Build an Odoo module that monitors employee performance based on predefined KPIs and displays a real-time traffic light indicator (Red, Yellow, Green) for each logged-in user.

KPI evaluation is automatically driven by the user's role/job position — no manual assignment per user.

---

## 2. Role-Based KPI Assignment

KPIs are not manually assigned per user. Instead:

- Each KPI is **linked to a Job Position** (`hr.job`)
- When a user logs in, the system **detects their job position** and **auto-loads all KPIs** for that role
- A KPI may measure either the **individual assignee** or the assignee's **direct-report team**

### Supported Roles (Initial)

| Role | Example KPIs |
|------|-------------|
| Sales Admin | Lead Generation, Follow-ups, Conversion Rate |
| Sales Admin – Tender Coordinator | Tender tracking, Quotation submission rate |
| Sales Admin – Follow-Up | Follow-up call count, Response time |
| Procurement Officer | PO processing, Vendor response rate |
| Customer Service Coordinator | Ticket resolution rate, Response SLA |
| Approver / Operations Manager | Approval decisions processed, Approval turnaround |
| Finance / Expense Approver | Expenses approved, Expense approval turnaround |

---

## 3. KPI Structure

Each KPI (`kpi.definition`) contains:

| Field | Type | Description |
|-------|------|-------------|
| name | Char | KPI name (e.g., "Lead Generation") |
| job_position_ids | Many2many → hr.job | Roles this KPI applies to |
| target_value | Float | Target number (e.g., 20) |
| evaluation_scope | Selection | `individual` or `team` |
| team_member_job_ids | Many2many → hr.job | Optional team-role filter when scope = team |
| normalize_per_member | Boolean | Divide count/amount KPI actuals by team-member count |
| period | Selection | daily / weekly / monthly |
| measure_type | Selection | count / percentage / amount |
| trend_period_count | Integer | Number of periods to expose in trend history |
| data_source | Selection | crm_lead / crm_activity / sale_order / purchase_order / helpdesk_ticket / approval_request / hr_expense / custom |
| turnaround_start_field | Char | Start timestamp field for custom compliance KPIs |
| turnaround_end_field | Char | End timestamp field for custom compliance KPIs |
| turnaround_window_value | Float | Window size for minute/hour/day compliance KPIs |
| turnaround_window_unit | Selection | minute / hour / day |
| compliance_time_field | Char | Datetime field used for operating-hours compliance |
| operating_hour_start | Float | Start of allowed issue/processing window |
| operating_hour_end | Float | End of allowed issue/processing window |
| domain_filter | Char | Optional domain to filter records |
| active | Boolean | Enable/disable this KPI |

---

## 4. KPI Performance Tracking

The system automatically computes actual performance using Odoo data sources:

### Data Source Mapping

| data_source | Model | Metric |
|-------------|-------|--------|
| `crm_lead` | `crm.lead` | Count of leads created in period |
| `crm_activity` | `mail.activity` | Count of activities done in period |
| `sale_order` | `sale.order` | Count of confirmed orders or revenue |
| `sale_conversion` | `crm.lead` + `sale.order` | % leads converted to orders |
| `purchase_order` | `purchase.order` | Count / amount of POs in period |
| `helpdesk_ticket` | `helpdesk.ticket` | Count of tickets opened or closed in period |
| `approval_request` | `approval.approver` | Count / turnaround of approval decisions |
| `hr_expense` | `hr.expense` | Count / turnaround of expense approvals |
| `custom` | (configurable) | Admin-defined model + domain |

Additional KPI logic patterns supported by the current build:
- custom turnaround compliance using configurable start/end fields and minute/hour/day windows
- operating-hours compliance using a configurable datetime field and allowed local-time range
- team KPIs measured on direct reports of the assigned manager

### Official Enterprise Time Tracking

The module adds lightweight tracking for exact turnaround calculations:

| Flow | Start | End |
|------|------|-----|
| Approval turnaround | `approval.request.create_date` | `approval.approver.decision_date` |
| Expense turnaround | `hr.expense.sheet.submitted_on` | `hr.expense.approved_on` |

### Ownership Rules

| KPI Family | Person measured |
|-----------|-----------------|
| Helpdesk | Assigned agent on `helpdesk.ticket.user_id` |
| Approvals | Approver on `approval.approver.user_id` |
| Expenses | Approver on `hr.expense.approved_by` |
| Team KPI | Direct reports of the KPI assignee via `hr.employee.parent_id.user_id` |

### Period Boundaries

| Period | Start of window |
|--------|----------------|
| Daily | 00:00 today (user timezone) |
| Weekly | Monday 00:00 of current week |
| Monthly | 1st of current month 00:00 |
| Yearly | 1st day of current year |

---

## 5. Traffic Light Logic

### Per-KPI Status

| Status | Condition | Color |
|--------|-----------|-------|
| Green | actual / target ≥ 80% | 🟢 |
| Yellow | 50% ≤ actual / target < 80% | 🟡 |
| Red | actual / target < 50% | 🔴 |

### Overall User Status

All KPIs for the user are evaluated:

- Score = average percentage across all KPIs
- Green: overall score ≥ 80%
- Yellow: 50% ≤ score < 80%
- Red: score < 50%

If a user has **no KPIs assigned**, status = **Grey** (not evaluated).

Turnaround/compliance KPI behavior:
- compliance KPIs use `actual_value` as a compliance percentage
- if no records exist in the KPI period, status becomes `Grey`
- compliance windows can be measured in minutes, hours, or days

---

## 6. User Interface

### 6.1 Systray Traffic Light

- Displayed in the **top navigation bar** (systray area)
- Visible immediately after login
- Shows one colored circle: Red / Yellow / Green
- **Blinks** when status is Red or Yellow
- **Steady** when Green
- Clicking opens the KPI Dashboard

### 6.2 KPI Dashboard

Accessible by clicking the traffic light. Shows:

- Header: Overall status + score
- Dashboard cards and list rows for all assigned KPIs:
  - KPI Name
  - Period
  - Target
  - Actual
  - Progress %
  - Status badge (colored)
- Trend access:
  - per-KPI graph/list/pivot history
  - prior periods based on `trend_period_count`
- "Last updated" timestamp
- Manager view: dropdown to select employee

---

## 7. Automation

- **Cron job** recalculates all `kpi.result` records every hour
- Period resets are implicit (results are recomputed from scratch each run)
- No manual data entry for KPI results
- Historical KPI rows are backfilled on demand for trend display

---

## 8. Security Model

| Actor | Permissions |
|-------|-------------|
| Employee | Read own `kpi.result` only |
| Manager (`group_kpi_manager`) | Read all employees' results |
| KPI Admin | Full CRUD on `kpi.definition` |
| System | Create/write `kpi.result` via cron |

---

## 9. AI Insights (Optional Phase)

Each KPI result can generate a natural-language insight:

| Insight Type | Example |
|-------------|---------|
| Status message | "You are at 45% of your monthly target" |
| Gap message | "You need 10 more leads to reach Green" |
| Recommendation | "Increase follow-up calls to improve conversion rate" |
| Pace prediction | "At current pace, you will end the month at ~60%" |

Implementation: Computed field using Python logic (no external AI API required for basic insights).

---

## 10. Success Criteria

- [ ] Every user sees a colored traffic light immediately after login
- [ ] KPIs auto-assign from job position — zero manual selection
- [ ] All metrics pulled automatically from Odoo data
- [ ] Red/Yellow lights blink to attract attention
- [ ] Clicking the light shows detailed KPI breakdown
- [ ] Users can open KPI trend history across prior periods
- [ ] Managers can view team performance
- [ ] Team KPIs can measure direct-report performance correctly
- [ ] System handles daily/weekly/monthly resets without manual intervention
