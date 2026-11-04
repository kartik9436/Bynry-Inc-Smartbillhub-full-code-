# EP-RAT-06 — Capacity Charges (Solar / Battery)

**Module:** rating (product name: Plans & Rates) · **Wave:** W3 · **Screens:** — (engine path; capacity units captured on the account per BR-CUS-012, lines surface in S31.2/S21) · **Status:** draft

## Scope
**In:** billing solar and battery as **capacity charges** — `account_capacities.units` (effective-dated, per service) × `capacity_rates.rate_per_unit` (tenant-defined unit label, per BR-RAT-022) → one line per capacity service per bill, prorated by calendar days on mid-cycle starts/changes (B4.3), **taxable like base** (BR-RAT-029), reproducing **GT-15**. Same purity and 🔒 HUMAN-OWNED discipline as EP-RAT-05 (`engine.py` — Eng Lead writes the code; stories define behavior + tests).
**Out:** **net-metering kWh export credits — explicitly v1.1** (roadmap; OQ-001 CLOSED → BR-RAT-018: capacity model ships v1; net-meter read capture continues in assets EP-AST-05, unused by rating v1) · buy-all/sell-all (v1.1, B4) · capturing/editing account capacity values (customers module UI per BR-CUS-012 — this epic reads them) · capacity rate configuration (EP-RAT-02/US-RAT-007).

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| — | *(no list screens owned by this epic)* | | | | | | | |

## Stories

---
id: US-RAT-014
epic: EP-RAT-06
module: rating
screens: [S21, S31.2]
wave: 3
status: draft
blocked_by: []
depends_on: [US-RAT-007, US-RAT-012]
journeys: [J2]
rules: [BR-RAT-003, BR-RAT-004, BR-RAT-018, BR-RAT-019, BR-RAT-022, BR-RAT-029]
golden_tests: [GT-15]
finance_calc: confirmed
---
### US-RAT-014 — Capacity-charge lines: account_capacities × capacity_rates, calendar-day prorated, taxable like base

**1 · Details** — As the billing run, I want each account's capacity services priced as `units_in_effect × rate_per_unit` per bill period — using the `account_capacities` row(s) effective during the period and the plan's capacity schedule's `capacity_rates` from the tariff version in force — emitting one line per capacity service labeled with the tenant's own unit label (e.g. "Solar capacity · 4 panels @ $10.00"), prorated by calendar days when capacity starts or changes mid-cycle, flagged taxable like base, so that solar/battery revenue bills per the v1 model with zero kWh-credit math. Entry: engine call inside the bill run; lines preview in S31.2 and appear on the account's bills (S21). Mid-period capacity changes split the line into date-range segments (each prorated); no usage/consumption input is read at all for capacity services.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-RAT-018 / BR-RAT-019 | v1 bills solar & battery as capacity charges: tenant-set rate per capacity unit × account-level capacity; model `capacity` in `tariff_model`. NOT net-metering kWh credits — export-credit math deferred to v1.1. | CONFIRMED — PO Q&A R1 Q10 (OQ-001 closure) + B2 r5 #16 |
| BR-RAT-022 | Unit label + rate are tenant-defined per service; prorated calendar-days on mid-cycle start per B4.3. | CONFIRMED — PO Q&A R3 (OQ-051 closure); GT-15 |
| BR-RAT-029 | Capacity charges are taxable **like base** (join the percent-tax base; exempt account still zeroes, BR-RAT-006). | CONFIRMED — PO Q&A R6 (D1 OK, default in effect); GT-15 |
| BR-RAT-004 | *(shared)* proration = calendar days. | CONFIRMED — B4.3 |
| BR-RAT-003 | *(shared)* per-line half-up 2dp at finalization. | CONFIRMED — B4.4 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(GT-15)* | A-00733: solar 4 units @ $10.00, battery 2 units @ $12.00, full 30-day period | Two lines: "Solar capacity · 4 panel @ $10.00" = **40.00**, "Battery capacity · 2 kW block @ $12.00" = **24.00**; both `taxable = true`; tax joins the GT-10 base math (8.25% × (40+24+other taxable)) |
| TC-2 *(proration)* | Solar capacity effective from day 16 of a 30-day cycle | Line = 15/30 × 40.00 = **20.00** (calendar days, B4.3); period dates on the line show the covered range |
| TC-3 *(mid-period change)* | Battery 2 → 3 kW blocks effective day 11 of 30 | Two segments: 10/30 × 24.00 = 8.00 and 20/30 × 36.00 = 24.00 → **32.00** total across dated segment lines; NUMERIC(18,6) intermediates, rounding at finalization |
| TC-4 *(exempt)* | Same as TC-1 on a tax-exempt account | Capacity lines unchanged; tax 0 (BR-RAT-006 — account-level wins) |
| TC-5 *(negative)* | Net meter on the account records 964 kWh export during the period | Exports do **not** offset anything: no credit line, no kWh netting — capacity lines only (BR-RAT-018; kWh credits v1.1). Assertion: engine never reads import/export quantities for capacity services |
| TC-6 *(negative)* | Account has solar service but no `account_capacities` row in effect (units unknown) | No capacity line invented; the account surfaces in S31.3 exceptions as "capacity not set" for staff fix — never a silent 0-or-guess |
| TC-7 *(negative)* | `account_capacities.units` = −2 | Rejected at capture (r5 #5: units ≥ 0); engine asserts ≥ 0 defensively |
| TC-8 *(isolation)* | Lone Star Ridge account with solar 4 units, rate $6.00 "meter equivalent" | Bills 24.00 under its own label/rate; Brazos Bend's $10.00 "panel" rate never leaks (RLS on capacity_rates + account_capacities) |

**4 · Test Data** — Brazos Bend: account **A-00733** (Harvest Sky Homes, plan Solar Residential) — solar 4 "panel" @ $10.00, battery 2 "kW block" @ $12.00 (schedules per EP-RAT-02 §4), cycle Aug 1–30, 2026. Proration fixture: solar effective Aug 16. Change fixture: battery 2 → 3 effective Aug 11. Exempt fixture: A-00588. Export fixture: net meter NM-7401 with 964 kWh export (assets EP-AST-05 data — unused here). Lone Star Ridge: A-00120, solar 4 × $6.00 "meter equivalent".

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Account capacity units | S21 (capture UI: customers) | B2 r5 #5 + BR-CUS-012 | `account_capacities` (account, service, units ≥ 0, effective_from/to) — ⚠ cross-module read via service function (B1) | numeric(18,6) | reference-data | ≥ 0; effective-dated |
| Capacity rate + unit label | — | B2 r5 #4 | `capacity_rates.rate_per_unit` / `.unit_label` / `.currency` (per tariff version in force) | numeric(18,6)+text | reference-data | BR-RAT-007 version selection |
| Capacity line | S31.2/S21 | GT-15 (B4) | `invoice_lines` (service solar/battery, quantity = units, unit = unit_label, unit_price = rate_per_unit, amount, period range, `taxable = true`) | numeric(18,6) | system-derived | BR-RAT-029; half-up 2dp at finalization |
| Proration segments | S31.2 | B4.3 | dated `invoice_lines` rows per capacity segment | numeric(18,6) | system-derived | calendar days |
| "Capacity not set" exception | S31.3 | derived (A18/S31.3 exception pattern) | exception feed to billing run (no rating write) | — | system-derived | staff fix before bill |
| Net-meter export (context) | S50 Reads | A1 r4 addendum + BR-RAT-018 | `meter_reads` import/export (assets) — **explicitly unread by rating v1** | numeric(18,6) | integration | v1.1 (roadmap) |

**6 · Acceptance**
- Given GT-15's fixture, Then the engine emits exactly $40.00 + $24.00 taxable-like-base lines labeled with the tenant's unit labels.
- Given a mid-cycle capacity start/change, Then calendar-day prorated segments reproduce the §7 arithmetic to the digit.
- Given exports, missing capacity rows, or negative units, Then no netting, no invented lines, and no bad data respectively — each path behaves exactly as stated.
- Given the two-tenant fixture, Then labels and rates never cross tenants.

**7 · Finance Calculation** — **CONFIRMED (BR-RAT-018/022/029; GT-15).**
`capacity_line = units_in_effect × rate_per_unit × (covered_calendar_days ÷ period_days)`, one line (or dated segment) per capacity service; `taxable = true` (like base); half-up 2dp per line at finalization.
Worked examples: **GT-15**: solar 4 × 10.00 = **$40.00**; battery 2 × 12.00 = **$24.00**; with 8.25% tax and no other lines: tax = 0.0825 × 64.00 = 5.28 → total **$69.28**. **Proration**: 15/30 × 40.00 = **$20.00**. **Mid-period change**: 10/30 × 24.00 + 20/30 × 36.00 = 8.00 + 24.00 = **$32.00**. Ref: **GT-15** (expected values freeze with finance before the golden test un-skips; rules CONFIRMED).

**8 · Open Questions** — None (net-metering credit math is v1.1 by closed decision OQ-001 — referenced, not re-opened).
