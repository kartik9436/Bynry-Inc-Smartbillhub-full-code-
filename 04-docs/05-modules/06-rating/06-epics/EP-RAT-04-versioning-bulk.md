# EP-RAT-04 — Tariff Versioning & Bulk Rate Updates

> Reconciled 2026-08-08 against PO rulings (decision log) — propagation sweep: board approval removed per BR-RAT-031-as-modified (PO R5-1, out-of-system).

**Module:** rating (product name: Plans & Rates) · **Wave:** W1 · **Screens:** S9 (History), S11 (step 3 Effective date) · **Status:** draft

## Scope
**In:** effective-dated tariff versioning (`tariff_versions` windows, non-overlap EXCLUDE constraint, in-force selection by service date — BR-RAT-007) with 7-year reproducibility (BR-RAT-017); the **single** rate-update flow (edit a schedule → new version with effective date, reason, optional approval) and the **bulk** rate-update flow (select many schedules/plans → one `rate_change_batches` run with per-entity `rate_change_log` rows — D9, r5 #14); the S9 **History** view over the compliance log. Reason is REQUIRED on every change (r5 #14 `reason NOT NULL` — compliance).
**Out:** the wizard steps that create a *first* version (EP-RAT-02) · plan-content versioning UX (EP-RAT-01/US-RAT-003 — same log, plan side) · repricing execution against historical versions (EP-RAT-05 consumes `tariff_versions`; billing corrections own rebills) · regulator notification sending (notifications module; the notify-30d flag is captured in EP-RAT-02).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S9 History view | entity name, reason, actor | entity type (plan/schedule/charge/tax), date range, batch, actor | changed_at desc | changed_at, entity, actor | 7 default (When · Entity · Change (before → after) · Reason · Actor · Published by · Batch) / 8 available (+Effective date) — IS-5 | View diff (drawer) | — (append-only; no row mutation ever) | CSV (IS-9) |

## Stories

---
id: US-RAT-010
epic: EP-RAT-04
module: rating
screens: [S9, S11]
wave: 1
status: draft
blocked_by: []
depends_on: [US-RAT-005, US-SHL-006, US-SHL-007, US-SHL-008]
journeys: []
rules: [BR-RAT-007, BR-RAT-017, BR-RAT-025, BR-RAT-037]
golden_tests: []
finance_calc: none
---
### US-RAT-010 — Effective-dated versioning & single rate update (7-year reproducibility)

**1 · Details** — As an Owner/Admin, I want every price change to a live schedule to create a **new** `tariff_versions` row with its own effective window — the old version's `effective_to` closes the day before, the new one opens on the stated date, windows never overlap — with reason, actor and optional approval captured, so that any historical invoice reprices against the version in force on its service date for at least 7 years. Entry: S9 rate card **Edit** → S11 pre-filled (step 3 sets the new effective date); **History** shows the trail. Exit: new version row + `rate_change_log` entry; S9 card shows "Change pending approval" until approved (when required). Mid-cycle effective dates prorate automatically at billing time (B4.3 — noted in S11 step-3 copy).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-RAT-007 | Historical invoices reprice against the tariff version in force on the **service date**, never the current one. | CONFIRMED (schema) — A8 §Versioning + B2 `tariff_versions` comment |
| BR-RAT-017 | Versions stay reproducible for 7 years (rebill/audit). | CONFIRMED — PO Q&A R1 Q12 |
| BR-RAT-037 | In-force versions are never edited in place: every change = a new `tariff_versions` row (old window closed, no overlap per the B2 EXCLUDE constraint) + a `rate_change_log` row with before/after jsonb, actor and **reason (required)**; the log is append-only. | PROPOSED — derived from B2 DDL + r5 #14 + BR-RAT-007/017 |
| BR-RAT-025 | D9: versioned rate changes with history/audit/compliance log, single AND bulk. | CONFIRMED — PO Q&A R3 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana raises Res Water · Inclining tier 1 from 3.20 → 3.45 effective Sep 1, 2026, reason "TWDB pass-through 2026" | Old version gets effective_to Aug 31; new version (effective_from Sep 1) with new tiers; `rate_change_log` row (before/after jsonb, reason, actor); S9 card notes the pending change |
| TC-2 | Billing reprices an Aug 15 service date after TC-1 | The Aug version (3.20) is selected via the `ix_tariff_versions_lookup` window join — never the Sep rates (BR-RAT-007) |
| TC-3 | History view after TC-1 | Row: When · "Res Water · Inclining" · 3.20 → 3.45 (tier 1) · "TWDB pass-through 2026" · Dana Whitfield · published state · batch — |
| TC-4 | Version created dated 7 years back (audit rebill drill) | Version + tiers for Aug 2019-era window still resolvable; nothing purged (BR-RAT-017; retention per OQ-017 closure) |
| TC-5 *(negative)* | New version entered with effective_from Aug 15 while the current window still runs open-ended | Blocked by the non-overlap EXCLUDE constraint, surfaced as inline error "windows may not overlap — close the current version first" |
| TC-6 *(negative)* | Change submitted with reason blank | Blocked: "reason is required for every rate change" (r5 #14); nothing written |
| TC-7 *(negative)* | API UPDATE against the superseded version's `unit_price` | Rejected (BR-RAT-037 — corrections are new versions); audit records the attempt |
| TC-8 *(isolation)* | Lone Star Ridge edits its Co-op Water Flat rate | Its version chain and log rows are invisible to Brazos Bend's History in every filter permutation |

**4 · Test Data** — Res Water · Inclining: v1 effective Aug 1, 2026 (3.20/4.80/7.20), v2 effective Sep 1, 2026 (3.45/4.80/7.20), reason "TWDB pass-through 2026", published directly by System Admin (board approval happens outside the system, BR-RAT-031-as-modified). Repricing probe: invoice service date Aug 15, 2026. Lone Star Ridge: Co-op Water Flat 3.10 → 3.25 effective Oct 1, 2026. Actors: Dana Whitfield; J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Effective from/to | S11 step 3 | prototype-extracted | `tariff_versions.effective_from/effective_to` | date | user-input | non-overlap (EXCLUDE gist) |
| New-version content | S11 step 2 | prototype-extracted | new `tariff_versions` + child rows (`rate_tiers` / `time_of_use_windows` / `capacity_rates` / `rate_seasons`) | rows | user-input | complete structure |
| Reason | change flow | B2 r5 #14 | `rate_change_log.reason` (NOT NULL) | text | user-input | required — compliance |
| Before/after diff | change flow | B2 r5 #14 | `rate_change_log.entity` + before/after jsonb + actor | jsonb | system-derived | append-only |
| Approver | S11 step 3 / History | prototype-extracted ("Published (approval out-of-system per BR-RAT-031)") | `tariff_versions.approved_by` | uuid | user-input (gated) | System Admin/Executive (BR-RAT-031) |
| In-force selection | — | B2 comment | window join: service_date ∈ [effective_from, effective_to) via `ix_tariff_versions_lookup` | — | system-derived | BR-RAT-007 |
| Version retention | — | BR-RAT-017 + OQ-017 closure | no purge < 7 yrs (2 yrs hot, then archive) | — | system-derived | — |

**6 · Acceptance**
- Given a rate change with reason, When saved, Then a new non-overlapping version exists, the log captures before/after/actor/reason, and prior service dates still price on the old version.
- Given a blank reason, an overlapping window, or an in-place edit attempt, Then the operation is rejected with the stated message.
- Given a 7-year-old service date, Then its version and child rows are still resolvable.

**7 · Finance Calculation** — N/A (version selection, not arithmetic; pricing in EP-RAT-05 per B4).

**8 · Open Questions** — None.

---
id: US-RAT-011
epic: EP-RAT-04
module: rating
screens: [S9]
wave: 1
status: draft
blocked_by: []
depends_on: [US-RAT-010, US-SHL-008]
journeys: []
rules: [BR-RAT-017, BR-RAT-025, BR-RAT-037, BR-RAT-040]
golden_tests: []
finance_calc: none
---
### US-RAT-011 — Bulk rate update (rate_change_batches + per-entity log, reason required)

**1 · Details** — As an Owner/Admin applying a board-approved annual increase, I want to select multiple rate schedules (and/or plan base charges), state one change set (e.g. +3.0% on all tier prices, or set base to a value), preview every resulting before → after per entity, give **one reason**, set one effective date, and apply — creating one `rate_change_batches` row and a `rate_change_log` row per changed entity — so that an across-the-board change is one auditable action instead of N hand edits. Entry: S9 → History → **Bulk update** (or multi-select on the Rates tab). Flow: select entities → define change → preview diffs → reason + effective date (+ approval when required) → apply atomically. Exit: N new versions, one batch, toast "N schedules updated"; History filterable by batch.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-RAT-025 | D9: single AND bulk updates, with history/audit/compliance log. | CONFIRMED — PO Q&A R3 |
| BR-RAT-037 | *(shared)* every changed entity gets a new version row + log row; reason required. | PROPOSED |
| BR-RAT-040 | Bulk mechanics: one batch = one reason + one effective date + one actor; per-entity log rows reference the batch; the apply is atomic (all preview rows or none — a failed entity aborts the batch); batches are append-only and never re-run (re-apply = new batch). | CONFIRMED (batch/log substance — B2 r5 #14, D9) / flow details PROPOSED — derived from IS-6 bulk pattern |
| BR-RAT-017 | *(shared)* 7-year reproducibility applies to batch results identically. | CONFIRMED |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Dana selects Res Electric · Tiered + Res Water · Inclining + Comm Water · Flat, change "+3.0% on all unit prices", effective Jan 1, 2027, reason "Board order 2026-12 annual adjustment", applies | 1 `rate_change_batches` row + 3 `rate_change_log` rows (each before/after jsonb, batch ref) + 3 new `tariff_versions`; preview showed 0.11 → 0.1133, 3.45 → 3.5535 etc. (NUMERIC(18,6), no premature rounding — display 4dp+); toast "3 schedules updated" |
| TC-2 | History filtered by the TC-1 batch | Exactly the 3 rows, shared reason/actor/effective date |
| TC-3 | Aug 2026 service date repriced after TC-1 | Still prices on the pre-batch versions (BR-RAT-007) |
| TC-4 *(negative)* | Apply attempted with reason blank | Blocked at the confirm modal (IS-6): "reason is required"; no batch, no versions |
| TC-5 *(negative)* | One selected schedule has an overlapping pending version (conflict) | Whole batch aborts with the entity named; zero partial writes (BR-RAT-040 atomicity) |
| TC-6 *(negative)* | Re-apply of the same batch (double-click / replayed request) | Second apply creates nothing — batches never re-run; UI disables the button after success; server rejects a replay of a completed batch |
| TC-7 *(negative)* | Marcus Vega attempts a bulk update | Role-forbidden: control disabled-with-reason; server rejects (A4 — Plans & Rates is Admin-only for writes) |
| TC-8 *(isolation)* | Lone Star Ridge runs its own bulk +2% | Its batch touches only Lone Star Ridge tariffs; entity pickers never list Brazos Bend schedules |

**4 · Test Data** — Batch BRC-2026-001: 3 schedules, +3.0%, effective Jan 1, 2027, reason "Board order 2026-12 annual adjustment", actor Dana Whitfield. Expected new tier-1 prices: Res Electric 0.11 → 0.1133; Res Water 3.45 → 3.5535; Comm Water 2.90 → 2.987. Conflict fixture: schedule with pending Sep 1 version. Lone Star Ridge: batch +2% on Co-op Water Flat.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Entity selection | bulk flow | derived (D9 "single AND bulk") + IS-6 multi-select | batch membership → per-entity `rate_change_log.entity` | uuid[] | user-input | same tenant; ≥1 |
| Change set (+%/set-to) | bulk flow | derived (D9) | applied to new `tariff_versions` child rows; parameters recorded on **PROPOSED-SCHEMA** `rate_change_batches.change_spec jsonb` | jsonb | user-input | percent ≠ 0 or value ≥ 0 |
| Preview diffs | bulk flow | IS-6 (confirm before money action) | computed (before/after per entity) | — | computed-display | must be reviewed before apply |
| Reason (one per batch) | bulk flow | B2 r5 #14 | `rate_change_batches.reason` → copied to each `rate_change_log.reason` (NOT NULL) | text | user-input | required |
| Effective date | bulk flow | derived (versioning) | each new `tariff_versions.effective_from` | date | user-input | no overlap per entity |
| Batch + log rows | — | B2 r5 #14 | `rate_change_batches` (actor, created_at) + `rate_change_log` (entity, before/after, batch ref) | rows | system-derived | append-only |
| Audit | — | CLAUDE.md #7 | `audit_log` (`rating.bulk_rate_update`: batch id, count, actor) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a 3-schedule batch with reason, When applied, Then exactly one batch + three log rows + three new versions exist atomically, and History reconstructs every before → after.
- Given a blank reason, a conflicting entity, a replayed apply, or a non-admin actor, Then nothing is written and the reason is stated.
- Given historical service dates, Then batch changes never affect them (BR-RAT-007).

**7 · Finance Calculation** — N/A (the batch multiplies stored prices — e.g. 0.11 × 1.03 = 0.1133, kept at NUMERIC(18,6); no invoice math occurs; rounding remains an invoice-line-finalization concern, B4.4/BR-RAT-003).

**8 · Open Questions** — None.
