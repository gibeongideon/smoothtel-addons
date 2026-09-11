# KPI Traffic Light System – Usage Guide

**Module:** `traffic_light_kpi`  
**Odoo Version:** 18.0

## 1. Purpose

This guide explains how to configure and use KPI definitions in the KPI Traffic Light module.

The module works like this:
- A KPI is linked to one or more **Job Positions**
- Employees inherit KPIs automatically from their job position
- KPI results are computed automatically
- KPI definitions can measure either the individual assignee or the assignee's direct-report team
- Each user gets an overall traffic light:
  - `Green`
  - `Yellow`
  - `Red`
  - `Grey` if not evaluated

## 2. Before You Start

Make sure:
- the user creating KPIs has `KPI Administrator` access
- each employee has a linked `User`
- each employee has the correct `Job Position`
- the module has been upgraded after recent changes
- the dependent enterprise apps are installed when using the new KPI families:
  - `Helpdesk`
  - `Approvals`
  - `Expenses`

## 3. Where to Create KPIs

In Odoo, go to:

`KPI Tracker > Configuration > KPI Definitions`

Click `New` to create a KPI definition.

## 4. Main Fields Explained

### Basic Configuration

- `Name`
  Human-readable KPI name.
  Example: `Approval Decisions Within Window`

- `Department`
  Used to group KPIs by business area.
  Example: `Sales`, `Customer Service`, `Finance`

- `KPI Logic`
  Tells the engine how the KPI is computed.

  Current options:
  - `CRM Leads Count`
  - `Qualified Leads Count`
  - `Activity Count`
  - `Quotation Conversion Within Window`
  - `Converted Sales Amount Within Window`
  - `Purchase Order Count`
  - `Purchase Order Amount`
  - `Helpdesk Tickets Opened`
  - `Helpdesk Tickets Closed`
  - `Helpdesk Tickets Closed Within Window`
  - `Approval Decisions Processed`
  - `Approval Decisions Within Window`
  - `Expenses Approved`
  - `Expense Approvals Within Window`
  - `Custom Turnaround Compliance`
  - `Operating Hours Compliance`
  - `Custom Count`
  - `Custom Sum`

- `Evaluation Scope`
  Controls whether the KPI measures:
  - the assigned user only
  - the assigned user's direct-report team

- `Trend Periods`
  Number of current and prior KPI periods to keep available for trend views.

- `Normalize Per Team Member`
  For team KPIs, divide count or amount actuals by matched team-member count.

- `Period`
  The evaluation window:
  - `Daily`
  - `Weekly`
  - `Monthly`
  - `Yearly`

- `Measure Type`
  How the KPI is displayed:
  - `Count`
  - `Percentage`
  - `Amount`

- `Aggregation`
  How the value is calculated:
  - `Count`
  - `Sum`
  - `Percentage`

- `Target Value`
  The target the actual result is compared against.

- `Weight`
  Controls how much this KPI affects the employee's overall KPI score.

- `Assigned Job Positions`
  Users in these roles receive this KPI automatically.

### Computation Source

- `Data Source`
  Source family used by the engine.

- `Source Model`
  Technical model used to compute the KPI.

- `Source Date Field`
  Date field used for the KPI period.

- `Source User Field`
  Ownership field on the source model.

- `Result Field`
  Used for amount/sum KPIs.

- `Conversion Window (Days)`
  Used for time-bound KPIs such as:
  - quotation conversion within 30 days
  - approvals decided within 2 days
  - expenses approved within 2 days

- `Turnaround Start Field` / `Turnaround End Field`
  Used by advanced compliance KPIs to compare two timestamps.

- `Turnaround Window` / `Turnaround Unit`
  Used by advanced compliance KPIs when the SLA is measured in minutes, hours, or days.

- `Operating Hours Field`
  Datetime field checked for operating-hours compliance.

- `Operating Hours Start` / `Operating Hours End`
  Allowed local-time range for operating-hours compliance.

- `Activity Type`
  Used when the KPI logic is `Activity Count`.

- `CRM Stage`
  Used when the KPI logic is `Qualified Leads Count`.

- `Domain Filter`
  Optional JSON filter for extra restrictions.

  Example:
  ```json
  [["team_id", "=", 3]]
  ```

### Custom Source

For `Custom Count` and `Custom Sum`, also provide:
- `Custom Model`
- `Custom Date Field`
- `Custom User Field`

For advanced compliance-style custom KPIs, also provide as needed:
- `Turnaround Start Field`
- `Turnaround End Field`
- `Turnaround Window`
- `Turnaround Unit`
- `Operating Hours Field`

## 5. Ownership Rules for the New KPIs

These three rules are important when configuring CSC, approval, and expense KPIs.

### Helpdesk KPIs

- Model: `helpdesk.ticket`
- Owner measured: the assigned helpdesk user in `user_id`
- Opened KPI date: `create_date`
- Closed KPI date: `close_date`

This means `Helpdesk Tickets Closed` measures how many tickets the assigned CSC agent closed in the selected period.

For turnaround control, `Helpdesk Tickets Closed Within Window` measures how many closed tickets were closed within the configured number of days from `create_date` to `close_date`.
If no tickets were closed in the KPI period, this KPI is `Grey` (not evaluated), not `Red`.

### Approval KPIs

- Model: `approval.approver`
- Owner measured: the approver user in `user_id`
- Decision timestamp: tracked in `decision_date`
- Request start timestamp for turnaround: `approval.request.create_date`

This means approval turnaround is measured on the person who approves or refuses, not the requester.
If there are no approval decisions in the KPI period, the turnaround KPI is `Grey`.

### Expense KPIs

- Model: `hr.expense`
- Owner measured: the approving manager in `approved_by`
- Approval timestamp: `approved_on`
- Submission timestamp for turnaround: tracked on the expense sheet as `submitted_on`

This means expense approval turnaround is measured from expense report submission to approval.
If there are no approved expenses in the KPI period, the turnaround KPI is `Grey`.

### Team KPIs

- Team ownership is resolved from `hr.employee.parent_id.user_id`
- The KPI assignee is the team leader or manager
- Source records are measured on matched direct reports
- Optional `Team Member Positions` can narrow the team to specific roles such as Sales Admin members only
- Optional `Normalize Per Team Member` is useful for KPIs such as leads per team member or visits per team member

## 6. How KPI Status Is Calculated

For each KPI:

`progress % = actual_value / target_value * 100`

Traffic light thresholds:
- `Green`: 80% and above
- `Yellow`: 50% to 79%
- `Red`: below 50%

The overall user traffic light is calculated from the weighted average of all KPI percentages.

### Special Rule for Turnaround KPIs

Turnaround KPIs do not behave like count KPIs.

Examples:
- `Helpdesk Tickets Closed Within Window`
- `Approval Decisions Within Window`
- `Expense Approvals Within Window`

For these KPIs:
- `actual_value` is the compliance rate itself, for example `87%`
- if there are no matching records in the period, the KPI becomes `Grey`
- `Grey` turnaround KPIs are excluded from the overall traffic-light average for that period
- status is based on compliance against the KPI target, not on count-style volume progress
- advanced compliance windows can be measured in `minutes`, `hours`, or `days`

### How Weight Works

Formula:

`overall score = sum(kpi percentage x weight) / sum(weights)`

Example:
- `Tickets Closed` = `92%`, weight `3`
- `Tickets Opened` = `60%`, weight `1`

Overall score:

`(92 x 3 + 60 x 1) / (3 + 1) = 84%`

Recommended values:
- `1` = normal importance
- `2` = important
- `3` = high importance
- `5` = critical KPI only

## 7. Example: Helpdesk Tickets Closed KPI

### Business Requirement

`Each CSC agent should close 25 tickets per week`

### Recommended Configuration

- `Name`: `Helpdesk Tickets Closed`
- `Department`: `Customer Service`
- `KPI Logic`: `Helpdesk Tickets Closed`
- `Period`: `Weekly`
- `Measure Type`: `Count`
- `Aggregation`: `Count`
- `Target Value`: `25`
- `Weight`: `3.0`
- `Assigned Job Positions`: `Customer Service Coordinator`

### How It Works

The system:
1. reads `helpdesk.ticket`
2. filters tickets where `user_id` is the CSC agent
3. filters tickets with `close_date` inside the KPI period
4. counts them

## 7A. Example: Sales Team Leader KPI

### Business Requirement

`Measure quotation conversion performance of the Sales Admin team, and compare output per team member`

### Recommended Configuration

- `Name`: `Quotation Conversion Rate (Team)`
- `Department`: `Sales`
- `KPI Logic`: `Quotation Conversion Within Window`
- `Evaluation Scope`: `Team`
- `Team Member Positions`: `Sales Admin`
- `Period`: `Monthly`
- `Measure Type`: `Percentage`
- `Target Value`: `60`
- `Turnaround Window`: `30`
- `Turnaround Unit`: `Days`

For a per-member KPI such as qualified leads per team member:
- `KPI Logic`: `Qualified Leads Count`
- `Evaluation Scope`: `Team`
- `Normalize Per Team Member`: enabled

## 7B. Example: Stores / Finance Compliance KPI

### Business Requirement

`Measure whether goods are issued only during allowed operating hours`

### Recommended Configuration

- `Name`: `Stores Operating Hours Compliance`
- `KPI Logic`: `Operating Hours Compliance`
- `Data Source`: `Custom`
- `Custom Model`: target operational model
- `Custom Date Field`: period field for the KPI window
- `Custom User Field`: responsible user field
- `Operating Hours Field`: actual issue datetime field
- `Operating Hours Start`: `10.0`
- `Operating Hours End`: `16.5`
- `Target Value`: compliance target percentage such as `100`

## 7C. Trend Views

- Open the KPI dashboard from the systray
- Use `View Trend` on a KPI row or card
- The module opens graph/list/pivot history for that KPI
- History is based on `Trend Periods` from the KPI definition

## 8. Example: Helpdesk Tickets Opened KPI

### Business Requirement

`Track how many tickets are assigned/opened for each CSC agent this week`

### Recommended Configuration

- `Name`: `Helpdesk Tickets Opened`
- `Department`: `Customer Service`
- `KPI Logic`: `Helpdesk Tickets Opened`
- `Period`: `Weekly`
- `Measure Type`: `Count`
- `Aggregation`: `Count`
- `Target Value`: set your workload target, for example `30`
- `Weight`: `1.0`

Use this KPI carefully. It is best as a workload monitoring KPI, not always as a performance KPI.

## 9. Example: Helpdesk Tickets Closed Within Window KPI

### Business Requirement

`At least 90% of tickets created for a CSC agent should be closed within 7 days`

### Recommended Configuration

- `Name`: `Helpdesk Tickets Closed Within Window`
- `Department`: `Customer Service`
- `KPI Logic`: `Helpdesk Tickets Closed Within Window`
- `Period`: `Weekly` or `Monthly`
- `Measure Type`: `Percentage`
- `Aggregation`: `Percentage`
- `Target Value`: `90`
- `Weight`: `3.0`
- `Conversion Window (Days)`: `7`
- `Assigned Job Positions`: `Customer Service Coordinator`

### How It Works

The system:
1. reads closed `helpdesk.ticket` records for the assigned agent
2. keeps only tickets with `close_date` inside the KPI period
3. calculates `close_date - create_date`
4. counts the ticket as on time if that value is between `0` and the configured window
5. returns the percentage of on-time closures

### Example Result

- tickets closed this week: `20`
- tickets closed within 7 days from creation: `18`
- actual KPI value: `90`
- target value: `90`
- traffic light: `Green`

## 10. Example: Approval Decisions Processed KPI

### Business Requirement

`Each approver should process at least 40 approval decisions per month`

### Recommended Configuration

- `Name`: `Approval Decisions Processed`
- `Department`: `Operations`
- `KPI Logic`: `Approval Decisions Processed`
- `Period`: `Monthly`
- `Measure Type`: `Count`
- `Aggregation`: `Count`
- `Target Value`: `40`
- `Weight`: `2.0`
- `Assigned Job Positions`: `Operations Manager` or the approver role used in your company

### How It Works

The system counts `approval.approver` rows for the current approver user where:
- `status` is `approved` or `refused`
- `decision_date` falls inside the KPI period

## 11. Example: Approval Decisions Within Window KPI

### Business Requirement

`At least 90% of approval requests should be decided within 2 days`

### Recommended Configuration

- `Name`: `Approval Decisions Within Window`
- `Department`: `Operations`
- `KPI Logic`: `Approval Decisions Within Window`
- `Period`: `Monthly`
- `Measure Type`: `Percentage`
- `Aggregation`: `Percentage`
- `Target Value`: `90`
- `Weight`: `3.0`
- `Conversion Window (Days)`: `2`

### How It Works

For each approver decision in the KPI period, the system measures:

`decision_date - approval.request.create_date`

If the result is between `0` and the configured window, it is counted as on time.

## 12. Example: Expenses Approved KPI

### Business Requirement

`A finance or line manager should approve 60 expenses per month`

### Recommended Configuration

- `Name`: `Expenses Approved`
- `Department`: `Finance`
- `KPI Logic`: `Expenses Approved`
- `Period`: `Monthly`
- `Measure Type`: `Count`
- `Aggregation`: `Count`
- `Target Value`: `60`
- `Weight`: `2.0`

### How It Works

The system counts `hr.expense` records where:
- `approved_by` is the KPI user
- `approved_on` is inside the KPI period
- `state` is `approved` or `done`

## 13. Example: Expense Approvals Within Window KPI

### Business Requirement

`95% of submitted expense reports should be approved within 2 days`

### Recommended Configuration

- `Name`: `Expense Approvals Within Window`
- `Department`: `Finance`
- `KPI Logic`: `Expense Approvals Within Window`
- `Period`: `Monthly`
- `Measure Type`: `Percentage`
- `Aggregation`: `Percentage`
- `Target Value`: `95`
- `Weight`: `3.0`
- `Conversion Window (Days)`: `2`

### How It Works

For each approved expense in the KPI period, the system measures:

`approved_on - sheet.submitted_on`

If the result is between `0` and the configured window, it is counted as on time.

## 14. Example: Sales and Procurement KPIs

### Quotation Conversion Rate

- `Name`: `Quotation Conversion Rate`
- `Department`: `Sales`
- `KPI Logic`: `Quotation Conversion Within Window`
- `Period`: `Monthly`
- `Measure Type`: `Percentage`
- `Aggregation`: `Percentage`
- `Target Value`: `60`
- `Conversion Window (Days)`: `30`

### Converted Sales Amount

- `Name`: `Converted Sales Amount`
- `Department`: `Sales`
- `KPI Logic`: `Converted Sales Amount Within Window`
- `Period`: `Monthly`
- `Measure Type`: `Amount`
- `Aggregation`: `Sum`
- `Target Value`: `50000`
- `Result Field`: `amount_total`

### Purchase Order Count

- `Name`: `Purchase Orders Processed`
- `Department`: `Procurement`
- `KPI Logic`: `Purchase Order Count`
- `Period`: `Monthly`
- `Measure Type`: `Count`

### Purchase Order Amount

- `Name`: `Purchase Order Amount`
- `Department`: `Procurement`
- `KPI Logic`: `Purchase Order Amount`
- `Period`: `Monthly`
- `Measure Type`: `Amount`
- `Result Field`: `amount_total`

## 15. After Saving a KPI

When a KPI definition is created or updated:
- users in the matching job position are recalculated immediately
- `kpi.result` records are created or updated
- the overall traffic light is refreshed

## 16. Dashboard and Drill-Down

When a user clicks the systray traffic light:
- Odoo opens `My KPI Dashboard`
- the dashboard shows KPI cards for that user only
- each KPI shows:
  - target
  - actual
  - percentage
  - traffic light status

When the user clicks `View Records` on a KPI:
- Odoo opens the underlying source records
- records are filtered by:
  - the KPI user
  - the KPI period
  - the KPI source
  - any optional domain filter

Examples:
- Helpdesk KPI opens filtered `helpdesk.ticket`
- Approval KPI opens filtered `approval.approver`
- Expense KPI opens filtered `hr.expense`

## 17. Usage Walkthrough for Admins

Follow this sequence when setting up the new KPIs.

1. Confirm the employee has the right `Job Position` and linked `User`.
2. Create the KPI definition.
3. Choose the matching `KPI Logic`.
4. Set the `Target Value`.
5. If it is a turnaround KPI, set `Conversion Window (Days)`.
6. Assign the correct `Job Positions`.
7. Save the KPI.
8. Open the affected employee's dashboard and verify the KPI appears.
9. Use `View Records` to confirm the source records are the expected ones.

## 18. Troubleshooting

### KPI does not appear for a user

Check:
- employee has a linked user
- employee has the correct job position
- KPI is active
- KPI is linked to that job position

### Approval or expense turnaround KPI shows 0

Check:
- the module was upgraded after these changes
- the new timestamp fields were created in the database
- approval requests were actually approved or refused
- expense sheets were actually submitted and approved
- the responsible user matches the KPI ownership rule

### Helpdesk KPI shows 0

Check:
- ticket `user_id` is set
- the correct user is the assigned agent
- `close_date` exists for closure KPIs
- the ticket falls inside the KPI period
- for turnaround KPIs, `create_date` and `close_date` must both be present and the ticket must be closed

### KPI configuration form fails to save

Check:
- `domain_filter` must be valid JSON
- custom KPIs need custom model/date/user fields
- amount KPIs should have a `result_field`

## 19. Recommended First KPIs to Test

Start with these because they are easy to validate:

### Customer Service
- `Helpdesk Tickets Closed`
- `Helpdesk Tickets Closed Within Window`

### Operations
- `Approval Decisions Processed`
- `Approval Decisions Within Window`

### Finance
- `Expenses Approved`
- `Expense Approvals Within Window`

### Sales
- `Qualified Leads`
- `Quotation Conversion Rate`

## 20. Suggested Next Improvements

Possible future enhancements:
- prebuilt KPI templates by role
- dedicated CSC dashboard view
- approval turnaround by category
- expense turnaround by department
- automated test coverage for every KPI logic
