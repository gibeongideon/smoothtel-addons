# KPI Traffic Light System – Build Progress

**Module:** `traffic_light_kpi`
**Odoo Version:** 18.0
**Started:** 2026-03-19
**Status:** 🔵 In Progress → ✅ Core implementation in place (target-based KPIs, immediate recompute, user dashboard drill-down, trend history, team KPIs, advanced compliance windows)

---

## Phase Overview

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Module Scaffold & Manifest | ✅ Done |
| 2 | Data Models | ✅ Done |
| 3 | KPI Computation Engine | ✅ Done |
| 4 | Traffic Light Logic | ✅ Done |
| 5 | Systray Widget (Frontend) | ✅ Done |
| 6 | KPI Dashboard View | ✅ Done |
| 7 | Role-Based Auto-Assignment | ✅ Done |
| 8 | Scheduled Automation (Cron) | ✅ Done |
| 9 | Security & Access Rights | ✅ Done |
| 10 | AI Insights (Optional) | ✅ Basic insight text done |
| 11 | Trend History & Team KPIs | ✅ Done |
| 12 | Demo Data & Testing | 🔵 Demo data done / automated tests pending |

---

## Detailed Task Checklist

### Phase 1 – Module Scaffold
- [x] `__manifest__.py` with correct dependencies
- [x] `__init__.py` files
- [x] `static/` folder structure
- [x] `views/`, `models/`, `security/` folders

### Phase 2 – Data Models
- [x] `kpi.definition` model (KPI name, target, period, type, data source)
- [x] Job-position assignment via `job_position_ids` Many2many on `kpi.definition`
- [x] `kpi.result` model (stores computed actual vs target per user)
- [x] `kpi.traffic.light` computed model (overall user status)

### Phase 3 – KPI Computation Engine
- [x] Compute method for CRM leads (count)
- [x] Compute method for CRM activities / follow-ups (count)
- [x] Compute method for Sales quotations → orders (conversion %)
- [x] Compute method for Sales revenue (amount)
- [x] Compute method for Procurement POs (count/amount)
- [x] Period boundary logic (daily/weekly/monthly/yearly)
- [x] `kpi.result` auto-populate on compute

### Phase 4 – Traffic Light Logic
- [x] Per-KPI status: Green ≥ 80%, Yellow 50–79%, Red < 50%
- [x] Overall user score (weighted average)
- [x] Overall status → single traffic light color

### Phase 5 – Systray Widget (OWL Component)
- [x] OWL component `KpiTrafficLight`
- [x] Systray registration in `web.systray`
- [x] Fetch user KPI status via RPC
- [x] Render colored circle (Red/Yellow/Green)
- [x] CSS blink animation for Red and Yellow
- [x] Click handler → opens dashboard

### Phase 6 – KPI Dashboard View
- [x] Dashboard action on `kpi.result`
- [x] Kanban dashboard with KPI-level target, actual, %, status, and traffic light
- [x] Color-coded rows/cards per status
- [x] "My KPIs" default filter (current user)
- [x] KPI drill-down action to filtered source records
- [ ] Manager dashboard employee switch/filter refinement

### Phase 7 – Role-Based Auto-Assignment
- [x] Automatic trigger on employee job position set
- [x] KPI results auto-load via immediate recompute and cron fallback
- [x] No manual KPI selection per user

### Phase 8 – Scheduled Automation
- [x] Cron job: recalculate all KPI results (hourly)
- [x] Period handling via recompute windows (daily/weekly/monthly/yearly)

### Phase 9 – Security & Access Rights
- [x] `ir.model.access.csv` for all models
- [x] Users see only own KPIs
- [x] Managers see team KPIs (group: `traffic_light_kpi.group_kpi_manager`)
- [x] Admin can configure KPI definitions

### Phase 10 – AI Insights (Optional)
- [x] Performance insight text per KPI
- [ ] Recommendation text based on gap analysis
- [ ] Pace prediction ("At current rate, you will reach X%")

### Phase 11 – Trend History & Team KPIs
- [x] KPI trend history snapshots for prior periods
- [x] Trend graph/pivot access from KPI dashboard
- [x] Team KPI scope using direct reports of the assignee user
- [x] Optional normalization per team member
- [x] Turnaround windows configurable in minutes, hours, or days
- [x] Operating-hours compliance KPI support
- [x] Generic custom turnaround compliance KPI support

### Phase 12 – Demo Data & Testing
- [x] Demo KPI definitions for Sales Admin role
- [x] Demo KPI definitions for Procurement Officer role
- [ ] Unit tests for compute logic
- [ ] Manual test checklist

---

## Recent Changes

### 2026-05-11
- **Trend History**: KPI results can now backfill prior periods and open graph/pivot trend views from dashboard cards and list rows.
- **Team KPI Scope**: KPI definitions can now measure either the individual assignee or that user’s direct-report team, with optional filtering by team-member job positions.
- **Per-Member Team Targets**: Count and amount KPIs can optionally normalize actual values by matched team-member count.
- **Advanced Compliance Windows**: Turnaround KPIs now support minute-, hour-, and day-based windows instead of day-only logic.
- **Custom Compliance KPI Types**: Added reusable KPI logic for custom turnaround compliance and operating-hours compliance to support future finance/stores builds.
- **Admin Configuration Upgrade**: KPI definition form now exposes trend period count, team scope, turnaround start/end fields, operating hours, and related advanced options.

### 2026-03-20
- **Immediate Recompute Hooks**: KPI definitions and employee role changes now trigger result recalculation immediately.
- **Target-Based Scoring**: KPI percentages and traffic lights are based on each KPI definition's configured `target_value`.
- **User KPI Dashboard**: Systray click opens a kanban-first dashboard of the logged-in user's KPI results.
- **Per-KPI Drill-Down**: Each KPI result can open filtered source records such as leads, sales orders, purchase orders, activities, or custom model rows.
- **UI Refresh**: Systray indicator was enlarged for better visibility.

---

```
traffic_light_kpi/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── hr_employee.py           # Recompute KPIs when employee role changes
│   ├── kpi_definition.py        # KPI template linked to job position, team scope, and compliance config
│   ├── kpi_result.py            # Computed actual vs target per user, trend history, and drill-down/trend actions
│   └── kpi_traffic_light.py     # Overall user traffic light status
├── wizards/
│   └── (none initially)
├── views/
│   ├── kpi_definition_views.xml
│   ├── kpi_result_views.xml
│   └── menu.xml
├── security/
│   ├── ir.model.access.csv
│   └── kpi_security.xml
├── data/
│   ├── kpi_cron.xml             # Scheduled actions
│   └── kpi_demo.xml             # Demo KPI definitions
├── static/
│   ├── description/
│   │   └── icon.png
│   └── src/
│       ├── js/
│       │   └── kpi_traffic_light_systray.js   # OWL systray component
│       ├── xml/
│       │   └── kpi_traffic_light_systray.xml  # OWL template
│       └── css/
│           └── kpi_traffic_light.css          # Blink + color styles
└── PROGRESS.md
```

---

## Current Session Log

### 2026-03-19
- [x] Created PROGRESS.md
- [x] Created SPEC.md (functional specification)
- [x] Created ARCHITECTURE.md (technical design)
- [x] Started Phase 1 – Module Scaffold

### 2026-03-20
- [x] Added immediate recompute hooks on KPI definition and employee updates
- [x] Switched active implementation back to KPI target-based scoring
- [x] Added user KPI dashboard with kanban cards
- [x] Added per-KPI source drill-down actions
- [x] Enlarged systray traffic light indicator

### 2026-05-11
- [x] Added historical KPI period backfill for dashboard trends
- [x] Added graph and pivot trend access for KPI results
- [x] Added team KPI evaluation scope with direct-report ownership
- [x] Added team-member role filtering and optional per-member normalization
- [x] Added configurable minute/hour/day turnaround windows
- [x] Added custom turnaround compliance and operating-hours compliance KPI types

---

## Notes & Decisions

- **OWL 2** used for frontend (Odoo 18 standard)
- **Stored KPI results** used for performance, with immediate recompute hooks plus cron fallback and optional history backfill for trend views
- **Job Position** (`hr.job`) used as the KPI assignment anchor
- **Team KPIs** currently use `hr.employee.parent_id.user_id` as the manager-to-team relationship
- **Advanced finance/stores KPIs** are implemented as configurable framework support first; exact production KPI definitions still depend on source-field mapping in the target database
- Traffic light blink via CSS `@keyframes` animation — no JS timers needed
