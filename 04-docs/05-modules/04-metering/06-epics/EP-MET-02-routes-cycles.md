# EP-MET-02 — Routes & Cycles
> Reconciled 2026-08-08 against PO rulings (decision log) — propagation sweep.
> **RE-RECONCILED 2026-08-23** against **CR-006** and **CR-029** (RC-W5-T3). Read the box below before this document's body: several rows underneath it describe the product as it was on 2026-08-08 and are kept for the record rather than followed.

---

## ⚠ RE-RECONCILIATION, 2026-08-23 — WHAT IN THIS EPIC IS NOW STALE

**The authority for these screens is `04-docs/02-decisions/17-cr029-routes-cycles-design.md` (B17) and the PO's thirteen CR-029 rulings, quoted verbatim in `12-governance/11-change-requests.md`.** Where the body of this epic disagrees with them, the ruling wins; the stale text is left in place because the SUPERSEDES chain is what makes a change auditable.

### The cycle's schedule — the biggest single change
A cycle is a **definition, not a schedule**, and it captures **three things about time** (PO, pre-CR 2026-08-23, verbatim): *"we can capture start day, frequency, monthly, weekly daily, biweekly, once in two months , quaterly etc and days to complete it ; give business names to frequence - 1 word."*

| This epic says | The product does |
|---|---|
| `cycles.window_start` / `window_end` — *"Read window start / end … start ≤ end"* | **Dropped** (metering 0021, RC-W5-T2). The window is **DERIVED**: *"start day + N days IS the read window"*, INCLUSIVE. `read_window_source` says so on the payload. |
| `cycles.bill_date` — *"Bill date … ≥ window_end"* | **Still a column and deliberately so**, and NOT what the config screen writes. It is billing's fallback bill date for a run where the clerk typed none, and nothing rules what replaces it — an **open question**, reported by RC-W5. |
| *"Due day"* on the S8 cycle table and modal | **`due_days`** — a COUNT of days after the bill date (BR-BIL-024), which is the fact billing reads. `cycles.due_day` (a day-of-month) is dropped. |
| `read_day_from` / `read_day_to` | **Dropped.** Superseded by `start_day` + `days_to_complete`. |
| frequency ∈ {monthly, bi-monthly, quarterly} | **Eight one-word business names**: Daily · Weekly · Fortnightly · Monthly · Bimonthly · Quarterly · Semiannual · Annual. The three old values are still ACCEPTED on write and mapped. |
| `read_schedules` *"seeds next period"* | **Retired** (D1, RC-W2). The period engine derives the next N occurrences on demand — nothing stored, nothing to go stale — and read windows became first-class **closable records**. |

### The screens
* **S8 Routes & Cycles is now Routes | Cycles SUB-TABS**, each with its own toolbar, column chooser and server-side pager (D7). The capability matrix below still describes two stacked config tables.
* **Two screens exist that this epic does not mention at all**: **SET-06D** (route detail — Premises · Units · Assets · Accounts · Audit, with per-premises drag-to-reorder, a printable route sheet and inline Read history) and **SET-07D** (cycle detail — Schedule · Routes · Coverage · Runs · Audit).
* **Both wizards are addressable full-page routes** (SET-06.1–4, SET-07.1–4), refresh-safe, with Edit opening pre-filled.
* **S26/S27's columns changed**: S27 carries Frequency · Start day · Days to complete beside the derived Read window, and both tabs cross-link to the details.

### Rulings that REMOVE things this epic implies
* **D6** — reader/device assignment is **out of scope**. No reader field in the wizard, no Reader column on the landing, no inline reader edit. `routes.assigned_to` stays as it is. (⚠ Whether the route's READ HISTORY still records who walked a past window is **OQ-343** — open.)
* **D12** — **no Balance column** on the route's Accounts tab. Status only.
* **D13** — **no account-level cycle assignment exists.** An account's cycle derives account → unit → route → cycle **at bill-run time**.
* **BR-MET-078 is HARDENED**: money never touches these surfaces, and three absences are asserted by test rather than trusted to the eye.

### What §7 "Finance Calculation" should now say
Still **N/A** — and the sentence *"due date arithmetic `bill_date + due_days`"* is unchanged in substance: due = the run's effective bill date + its effective due-days, where each is the clerk's value or the cycle's default (D9, `runs.effective_bill_date` / `effective_due_days`). No money is computed on either screen, and **no ❄️ FROZEN B4/B5 figure moved in any CR-029 wave** — golden 33 PASS / 0 FAIL throughout.

### Open questions live against these screens
~~**OQ-338**~~ **CLOSED-RULED 2026-08-23** — *"A: geography only - option a"*: an area is a tag on a premises, routes are created and edited in ONE place (the routes registry), and Settings' *Areas & sub-areas* holds nothing route-shaped. Written as **BR-MET-103**; the RC-W5-T1 stub it blocked is removed · **OQ-339** (a month-end start day in a short month) · **OQ-340** (a first run that disagrees with the start day) · **OQ-341** (days-to-complete longer than the period) · **OQ-342** (does a bill run get a number) · ~~**OQ-343**~~ **CLOSED-RULED 2026-08-23** — *"B: no reader anywhere, correct the screenshot and drop the stored name"*: the Read history is Window · Read on · Collected · Expected · Result, the PO's own screenshot is CORRECTED, and `read_windows.reader` is dropped by migration (`routes.assigned_to` and the ops tab's read-only display are untouched — D6 preserved them). ⚠ **AND SO WERE THE OTHER FOUR — OQ-339 · OQ-340 · OQ-341 · OQ-342 WERE ALL RULED ON THE SAME DAY, 2026-08-23.** None of these six is open. Their code stubs close in the lane that owns each engine; **what the FRONTEND owed OQ-340 landed in CR-029 RC-W6b** — the schedule surfaces render the SERVED `effective_start_day` rather than a stored `start_day` the engine ignores (*"start day becomes decorative"*), and OQ-341's `schedule_warning` is rendered as a translated sentence beside the overlapping windows it explains, never instead of them. Nothing is answered by a call site.

---

**Module:** metering (product name: **Meter Reads**) · **Wave:** W1 · **Screens:** S26, S27, S8 (Settings → Routes & Cycles tab) · **Status:** draft

## Scope
**In:** the operational **Routes** (S26) and **Cycles** (S27) tabs on the Reads page (progress views: meters/collected, read window, bill date, completion status) and the **Settings → Routes & Cycles** configuration tab (A1 Settings addendum tab 3): add/edit/delete/deactivate routes (name, type, **premises/unit membership selection with an OPTIONAL walk order — BR-MET-033; no numeric sequence/capacity ranges**, cycle assignment) and add/edit/delete billing cycles (code, routes, read window, bill date, due day) via the two Settings modals. Generates the cycle calendar that read import (EP-MET-03) tags against and billing runs (billing module) pick up.
**Out:** reads ingestion and the collected/pending numbers' source data (EP-MET-03) · read validation (EP-MET-04) · bill-run execution against a cycle (billing) · route-sheet PDF generation (S25 header action — reports/documents, W6) · field-ops mobile tooling (not in v1 design).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S26 Routes | route name/code | cycle, type, status | route code asc | code, meters, collected, last completion | 8 default (Route · Type · Assigned to · Cycle · Meters · Collected · Last completion · Status) / 8 available | — (read-only; "Manage in Settings" link) | — | CSV (IS-9) |
| S27 Cycles | cycle code | status | read window start desc (current first) | code, bill date, expected, collected | 8 default (Cycle · Routes · Read window · Bill date · Expected · Collected · Progress · Status) / 8 available | — (read-only; "Manage in Settings" link) | — | CSV (IS-9) |
| S8 Routes & Cycles (Settings — two config tables) | — | — | route/cycle code asc | — | Routes: Route · Type · Premises/Units (membership — BR-MET-033) · Meters · Cycle · Action; Cycles: Cycle · Route(s) · Read window · Bill date · Due day · Action | Edit, Deactivate (routes), Delete (audit-locked when referenced) | — | — |

## Stories

---
id: US-MET-005
epic: EP-MET-02
module: metering
screens: [S26, S27]
wave: 1
status: draft
blocked_by: []
depends_on: [US-MET-006, US-MET-010, US-SHL-006, US-SHL-007, US-SHL-008]
journeys: []
rules: [BR-MET-010, BR-MET-011]
golden_tests: []
finance_calc: none
---
### US-MET-005 — Reads Routes & Cycles operational tabs

**1 · Details** — As a staff user during a read window, I want the Routes tab to show each route's collection progress (meters, collected, last completion, status) and the Cycles tab to show each cycle's window, bill date, expected vs collected and a progress bar, so that I can see at a glance which routes are behind before billing day. Entry: Reads page (S25) → Routes / Cycles tabs. Exit: none (read-only; a "Manage in Settings →" link routes System Admins to the S8 config tab). Route types render as AMI · feeder F-nn (assigned "System (auto-pull)"), Walk-by or Drive-by (assigned to a named field-ops user); cycle status pills: `N pending` / Scheduled / Billed per prototype.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-MET-010 | A route is assigned to exactly one cycle at a time; a cycle's route list is exactly the set of routes assigned to it (no double membership, no orphan listing). | PROPOSED — derived from prototype (each route row shows a single cycle; cycle rows list route sets) |
| BR-MET-011 | S26/S27 are read-only operational views: all route/cycle CRUD lives in Settings → Routes & Cycles; collected/expected/progress figures derive from committed reads (EP-MET-03) against the units on each route's membership (BR-MET-033) — the tabs never write anything. | PROPOSED — derived from A1 Settings addendum tab 3 ("configurable: Add/Edit/Delete") vs A1 note that S26/S27 are stubs, + separation of ops view from config |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Marcus opens Routes with the §4 seed | 4 rows; Route 1 shows 412/412 · Complete; Route 3 shows 128/142 · "14 pending" warn pill; AMI routes read "System (auto-pull)", walk/drive routes show Ray Delgado |
| TC-2 | Marcus opens Cycles | 08-A: routes "1, 2", window Aug 1 – Aug 5, bill Aug 8, 620 expected / 606 collected, progress ≈98%, "14 pending"; 08-B Scheduled at 0%; 07-A shows Billed at 100% |
| TC-3 | A read batch for Route 3 commits (EP-MET-03) | Collected counts and progress bars update on next load — derived, not stored copies |
| TC-4 | Marcus (Billing Clerk) looks for edit controls | None on S26/S27; "Manage in Settings →" visible only to System Admin (RBAC per A4; server-enforced) |
| TC-5 *(negative)* | Cycles endpoint returns 500 | A18 failed-with-retry card; Retry re-issues the identical query |
| TC-6 *(isolation)* | J. Okafor (Lone Star Ridge) opens Routes/Cycles | Sees only Lone Star Ridge's route LSR-1 and cycle 08-A (their own row — codes are per-tenant); automated test asserts no Brazos Bend route/cycle id ever appears |

**4 · Test Data** — Brazos Bend routes: Route 1 · Katy Central (AMI · feeder F-01, System auto-pull, cycle 08-A, 412 meters, 412 collected, Aug 3 06:12, Complete); Route 2 · Mason Rd (AMI · F-02, 08-A, 208/194); Route 3 · Cane Island (Walk-by, Ray Delgado, 08-A, 142/128, In progress, 14 pending); Route 4 · Riverbend (Drive-by, Ray Delgado, 08-B, 184/0, Scheduled Aug 12). Meter counts derive from each route's premises/unit membership (BR-MET-033). Cycles: 08-A (routes 1, 2, 3 — window Aug 1–5 2026, bill Aug 8, due +20, 762 expected / 734 collected); 08-B (route 4 — Aug 12–16, bill Aug 19, Scheduled); 07-A (Billed, 100%). Lone Star Ridge: route LSR-1 (Walk-by), cycle 08-A (their own). Reference date 2026-08-08 (America/Chicago).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Route (name/code) | S26 | prototype-extracted ("Route 1 · Downtown") | `routes.code` + **PROPOSED-SCHEMA** `routes.name` | text | reference-data | unique (tenant, code) |
| Type / feeder | S26 | prototype-extracted (AMI · feeder F-01 / Walk-by / Drive-by) | **PROPOSED-SCHEMA** `routes.route_type` (walk \| drive \| ami) + `routes.feeder_ref` | enum/text | reference-data | feeder only for AMI |
| Assigned to | S26 | prototype-extracted | **PROPOSED-SCHEMA** `routes.assigned_to` (⚠ cross-module FK → identity `users`) | uuid | reference-data | null = "System (auto-pull)" |
| Cycle (per route) | S26 | prototype-extracted | **PROPOSED-SCHEMA** `routes.cycle_id` (B2 keeps `service_points.route_id`/`cycle_id`; cycle now derives via route — BR-MET-010) | uuid | reference-data | must exist |
| Meters (count) | S26 | prototype-extracted | count of units/assets in the route's membership (BR-MET-033) | integer | computed-display | — |
| Collected · Last completion · Status | S26 | prototype-extracted | derived from `meter_reads` in the cycle window | int/timestamptz/enum | computed-display | never stored on the route |
| Cycle code | S27 | prototype-extracted ('08-A') | `cycles.code` | text | reference-data | unique (tenant, code) |
| Read window | S27 | prototype-extracted (Aug 1 – Aug 5) | **PROPOSED-SCHEMA** `cycles.window_start` / `cycles.window_end` | date | reference-data | start ≤ end |
| Bill date · Due day | S27 | prototype-extracted (Aug 8 · +20 days) | **PROPOSED-SCHEMA** `cycles.bill_date` / `cycles.due_days` | date / integer days | reference-data | bill_date ≥ window_end; due_days ≥ 0 |
| Expected / Collected / Progress / Status | S27 | prototype-extracted | derived from `meter_reads` vs the membership of the cycle's routes | int/% /enum | computed-display | Billed state derives from bill run (billing, read-only) |

**6 · Acceptance**
- Given the §4 seed, When the tabs open, Then routes and cycles render with correct derived progress and status pills, And no edit control exists outside Settings.
- Given new committed reads, When the tabs reload, Then collected/progress reflect them without any stored counter.
- Given a Lone Star Ridge session, Then only its own routes/cycles are visible even where codes collide.

**7 · Finance Calculation** — N/A

**8 · Open Questions** — None.

---
id: US-MET-006
epic: EP-MET-02
module: metering
screens: [S8]
wave: 1
status: draft
blocked_by: []
depends_on: []
journeys: [J2]
rules: [BR-MET-008, BR-MET-009, BR-MET-010, BR-MET-033]
golden_tests: []
finance_calc: none
---
### US-MET-006 — Settings → Routes & Cycles configuration

**1 · Details** — As a System Admin, I want to configure routes (name, type Walk/Drive, **membership — select premises and their units, with an OPTIONAL walk order** (BR-MET-033), cycle assignment) and billing cycles (code, routes, read window start/end, bill date, due days after bill) from Settings → Routes & Cycles, so that reading and billing run on a calendar I control. Route membership is built by **selection, not by numeric ranges** — the prototype's sequence-range field is superseded (BR-MET-033). Entry: Settings (S8) → Routes & Cycles tab; **+ Add route** and **+ Add cycle** open the two modals (prototype `sm_routeAdd` / `sm_cycleAdd`); per-row action select Edit / Deactivate / Delete (routes), Edit / Delete (cycles). Every save fires a confirmation toast (A1 Settings addendum) and an audit row. Exit: modal close → refreshed tables. System Admin only; Billing Clerk and Executive get disabled-with-reason controls (IS-6) with server-side enforcement.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-MET-008 | Routes are tenant-scoped with a unique code per tenant (B2); carry name, type (Walk/Drive in the modal; AMI routes arrive via the meter-integration seam, B7), **membership = selected premises and their units with an OPTIONAL walk order (BR-MET-033 — no numeric capacity/sequence ranges, no slot exhaustion; OQ-041 CLOSED)** and one cycle assignment; IS-1 deactivate-first — Delete is audit-locked while any unit/service point is a member of the route (deactivate allowed). | PROPOSED (CRUD mechanics — B2 `routes` + prototype + IS-1); membership model CONFIRMED — BR-MET-033 (PO R7) |
| BR-MET-033 | **Routes are built by selecting Premises and their Units** (membership), with an OPTIONAL walk order — no numeric capacity ranges. Supersedes the sequence-range framing everywhere in this epic. | CONFIRMED — PO R7 (OQ-041) |
| BR-MET-009 | Cycles carry code (unique per tenant), assigned routes, a read window (start ≤ end), a bill date ≥ window end, and due days ≥ 0 (due date = bill date + due days, consumed by billing); Delete is audit-locked once any read batch or bill run references the cycle; `read_schedules` (frequency per B2) seeds the next period's cycle instances. | PROPOSED — B2 `cycles`/`read_schedules` + prototype cycle modal fields (Read window start/end, Bill date, "Due (days after bill)" default 20 shown as sample) |
| BR-MET-010 | *(shared with US-MET-005)* one cycle per route at a time — assigning a route to a new cycle moves it (with confirmation), never duplicates it. | PROPOSED |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana adds route "Route 5 · Gulf Fwy", Walk, selects premises P-00420 (its unit auto-included), walk order left blank, cycle 08-B | Row appears in the routes table and in S26 with member counts; walk order blank is allowed (optional — BR-MET-033); toast; `audit_log` `route.created` with the membership recorded |
| TC-2 | Dana adds cycle 09-A: routes 1, 2 · window Sep 1–5 · bill Sep 8 · due 20 | Cycle row created; routes 1 & 2 now show cycle 09-A (moved with confirmation per BR-MET-010); S27 lists 09-A as Scheduled |
| TC-3 | Dana edits Route 3's membership: adds premises P-00350's unit and sets a walk order across the members | Membership + walk order updated in place; audit row holds before/after (BR-MET-033) |
| TC-4 | Dana deactivates Route 4 (0 collected, future cycle) | Status inactive; hidden from assignment pickers; historical reads keep their route reference |
| TC-5 *(negative)* | Delete Route 1 (412 member meters) | Audit-locked 🔒: "412 meters on this route — deactivate instead"; row intact |
| TC-6 *(negative)* | Add cycle with window Sep 6 → Sep 2 (start > end) | Inline validation error; save blocked |
| TC-7 *(negative)* | Add cycle with bill date Sep 3 inside window Sep 1–5 | Blocked: bill date must be on/after window end |
| TC-8 *(negative)* | Marcus (Billing Clerk) opens the tab | Add/Edit/Delete disabled-with-reason; direct API call rejected 403 (server-enforced) |
| TC-9 *(negative)* | Delete cycle 08-A (has committed reads + a bill run) | Audit-locked; deactivation path offered only if no future window pending |
| TC-10 *(isolation)* | Lone Star Ridge admin creates their own "Route 5" and cycle "09-A" | Both succeed — uniqueness is per tenant; neither tenant sees the other's rows in tables or pickers; the premises/unit picker lists only their own premises |

**4 · Test Data** — Existing config per US-MET-005 §4. New: Route 5 · Gulf Fwy (Walk, members = P-00420 · Bldg 1, cycle 08-B, no walk order); Route 3 edit adds P-00350's unit with walk order 1–2 across members; cycle 09-A (routes 1, 2 · Sep 1–5, 2026 · bill Sep 8 · due 20 days → due date Sep 28). Actors: Dana Whitfield (System Admin), Marcus Vega (Billing Clerk — denied), J. Okafor (Lone Star Ridge System Admin).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Route name | S8 route modal | prototype-extracted ("Route 4") | `routes.code` + **PROPOSED-SCHEMA** `routes.name` | text | user-input | unique (tenant, code); required |
| Type | S8 route modal | prototype-extracted (Drive/Walk) | **PROPOSED-SCHEMA** `routes.route_type` | enum (walk \| drive \| ami) | user-input | modal offers walk/drive; ami via B7 seam |
| Premises/Units (membership) | S8 route modal | BR-MET-033 (PO R7 — supersedes the prototype's sequence-range field, OQ-041 CLOSED) | **PROPOSED-SCHEMA** `route_memberships` (tenant_id, route_id, unit_id, walk_order integer NULL) — selecting a premises includes its units; membership drives `service_points.route_id` | uuid / int | user-input | premises/units must exist, same tenant; a unit is on ≤1 route |
| Walk order (optional) | S8 route modal | BR-MET-033 ("optional walk order") | `route_memberships.walk_order` (NULL allowed) | integer | user-input | optional; when set, unique within the route |
| Assign to cycle | S8 route modal | prototype-extracted | **PROPOSED-SCHEMA** `routes.cycle_id` | uuid | user-input | must exist; move-with-confirm |
| Route status (Deactivate) | S8 | prototype-extracted (action option) | **PROPOSED-SCHEMA** `routes.status` (active \| inactive) — `deleted_at` reserved for true delete | enum | user-input | deactivate-first (IS-1) |
| Cycle code | S8 cycle modal | prototype-extracted ("09-A") | `cycles.code` | text | user-input | unique (tenant, code) |
| Routes (on cycle) | S8 cycle modal | prototype-extracted ("1, 2") | via `routes.cycle_id` (derived list — BR-MET-010) | — | user-input | routes must exist |
| Read window start / end | S8 cycle modal | prototype-extracted | **PROPOSED-SCHEMA** `cycles.window_start` / `cycles.window_end` | date | user-input | start ≤ end |
| Bill date | S8 cycle modal | prototype-extracted | **PROPOSED-SCHEMA** `cycles.bill_date` | date | user-input | ≥ window_end |
| Due (days after bill) | S8 cycle modal | prototype-extracted (value 20 — sample, not a constant) | **PROPOSED-SCHEMA** `cycles.due_days` | integer days | user-input | ≥ 0 |
| Schedule seed | — | B2 `read_schedules` (frequency 'monthly') | `read_schedules.cycle_id` / `frequency` + **PROPOSED-SCHEMA** generation bookkeeping (`last_generated_period`) | text | system-derived | generates next period's cycle rows |
| Config audit | — | A1 Settings addendum (toast) + CLAUDE.md #7 spirit | `audit_log` (`route.*` / `cycle.*` with before/after incl. membership changes) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given the Settings tab, When Dana adds, edits, deactivates routes (selecting premises/units as members, walk order optional — BR-MET-033) and adds cycles with valid windows, Then the config tables, S26/S27, and all pickers reflect the change with a toast and an audit row each.
- Given a route, Then no numeric sequence/capacity range exists anywhere in its config or validation (BR-MET-033); membership is the only assignment mechanism.
- Given a referenced route or cycle, When Delete is chosen, Then the 🔒 audit-lock blocks it with the deactivate alternative.
- Given invalid windows/dates or a non-admin actor, When save is attempted, Then it is rejected inline and server-side, And nothing is written.

**7 · Finance Calculation** — N/A (due date arithmetic `bill_date + due_days` is date math consumed by billing; no money is computed here).

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-041 | Route capacity rules: sequence range as hard constraint vs walk order; max meters per route | Nothing — closed | Product Owner (chat session) | CLOSED(→BR-MET-033) — routes = premises/unit selection + optional walk order; no ranges, no capacity constraint (PO R7) |
