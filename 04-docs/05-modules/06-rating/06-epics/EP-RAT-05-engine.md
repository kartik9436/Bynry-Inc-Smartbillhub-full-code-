# EP-RAT-05 — Rating Engine Core 🔒

**Module:** rating (product name: Plans & Rates) · **Wave:** W3 · **Screens:** — (pure service; priced lines surface in S31.2/S31.3 and on invoices) · **Status:** draft

## Scope
**In:** the pure rating function — reads + in-force tariff version + plan config in → priced invoice-line candidates out — per the **CONFIRMED** B4 math: multiplier before tiers (BR-RAT-001, GT-5) · pure tiers reset per bill, thresholds scale with prorated periods (BR-RAT-002/026, GT-2) · per-line half-up 2dp rounding at finalization only (BR-RAT-003) · calendar-day proration of base AND usage (BR-RAT-004, B4.3, GT-3) · TOU window pricing on pre-split quantities (BR-RAT-021) · sewer % of water usage-charge dollars (BR-RAT-015) · UoM match-or-factor gate (BR-RAT-038, PO R6) · tax base usage+base with account-level exemption (BR-RAT-005/006, GT-10/11) · minimum bill both modes, per-service first then plan floor (BR-RAT-016/028, GT-13). Demand quantities (max-demand register read) are priced as inputs × stored rates; capacity charges are EP-RAT-06. **Plus (2026-08-10, PO modularity request):** the engine's INTERNAL SHAPE — every pricing model and every charge amount rule behind one plugin interface each, so a new rule type is a new module rather than an engine edit (BR-RAT-044/045, US-RAT-015). The engine's stages sit inside the seven-stage bill-run pipeline defined by BR-BIL-037 (stages 3 price-usage · 4 apply-charges · 5 compute-tax).
**Out:** invoice/bill-run orchestration, idempotency, issuance (billing module) · late fees (billing, GT-8) · estimation quantities (metering EP-MET-05 supplies them) · net-metering kWh credits (v1.1) · demand *measurement/ratchet* and PF penalties (PROPOSED in B4 addendum — engine consumes demand qty, computes no ratchet/PF) · capacity lines (EP-RAT-06) · **tenant-AUTHORED calculation rules (formulas) — EP-RAT-07**, which plugs into the BR-RAT-045 interface and changes nothing in this epic.

> **🔒 HUMAN-OWNED implementation.** `06-backend/apps/rating/engine.py` is on the CLAUDE.md do-not-touch list (rating math). These stories define behavior, fixtures and tests; the **Eng Lead writes the code**. Agents may scaffold interfaces/tests around the boundary but never author or alter the math. Stories are **draft (not blocked)** — every governing rule below is CONFIRMED; GT expected values freeze with finance before the tests un-skip (CLAUDE.md "Before writing billing code").

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| — | *(no list screens — engine output renders inside billing's S31.2/S31.3 and invoice views)* | | | | | | | |

## Stories

---
id: US-RAT-012
epic: EP-RAT-05
module: rating
screens: [S31.2]
wave: 3
status: draft
blocked_by: []
depends_on: [US-RAT-002, US-RAT-005, US-RAT-006, US-RAT-007, US-RAT-010, US-MET-010, US-MET-011]
journeys: [J2]
rules: [BR-RAT-001, BR-RAT-002, BR-RAT-003, BR-RAT-004, BR-RAT-011, BR-RAT-015, BR-RAT-021, BR-RAT-026, BR-RAT-038]
golden_tests: [GT-1, GT-2, GT-5]
finance_calc: confirmed
---
### US-RAT-012 — Usage pricing: consumption → priced lines (multiplier, tiers, TOU, %-of-water, proration, UoM gate)

**1 · Details** — As the billing run (the only caller), I want a pure function that takes a billing period's consumption per service point (post read-validation), the account's plan (version snapshot) and the tariff version in force on the service date, and returns priced line candidates — usage line(s) per service, base line per service — with quantity, unit, unit_price, exact NUMERIC(18,6) amount and a `taxable` flag, so that invoices are computed one way, tested against golden fixtures, with no side effects. Entry: called by S31's run pipeline; output previewed in S31.2. The engine: (1) gates UoM (BR-RAT-038); (2) applies meter multiplier to raw delta (BR-RAT-001 — metering supplies post-multiplier consumption; the engine asserts it); (3) prorates base and scales tier thresholds for short/long periods by calendar days (BR-RAT-002/004); (4) prices via the model (flat/tiered/TOU/demand/seasonal/%-of-water); (5) rounds each line half-up 2dp **only at finalization** (BR-RAT-003).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-RAT-001 | Multiplier applies BEFORE tier evaluation. | CONFIRMED — B4.4 (finance 2026-08-07); GT-5 |
| BR-RAT-002 | Tier thresholds reset each bill and scale with the prorated period. | CONFIRMED — B4 §Tiered; GT-2 |
| BR-RAT-026 | Pure tiers: every unit bills through tiers; base is separate (plan_services). | CONFIRMED — PO Q&A R5; GT-2 |
| BR-RAT-003 | Round per line, half-up, 2dp, at finalization only — intermediates stay NUMERIC(18,6). | CONFIRMED — B4.4 |
| BR-RAT-004 | Proration by calendar days; base AND usage both prorated. **EXTENDED 2026-08-12 (PO, OQ-155): a tariff change INSIDE a back-billed period is SPLIT BY DAYS** — two day-weighted segments, each priced at the version in force on those days (never the whole period at one version, never refused). Each segment measures usage from its OWN reads; where the cut day has no read the DEFAULT is a day-weighted usage estimate **marked as estimated** on the bill, with metering's own estimate (BR-MET-026) as a tenant option (OQ-191). | CONFIRMED — B4.3; GT-3; split-by-days CONFIRMED — PO 2026-08-12 |
| BR-RAT-021 | TOU: pre-split window quantities × per-season window prices; holidays → off-peak via tenant calendar. | CONFIRMED — PO Q&A R3 |
| BR-RAT-015 | Sewer line = % × water usage-charge dollars (excl. base, excl. tax). | CONFIRMED — PO Q&A R1 |
| BR-RAT-038 | UoM gate: read unit must match schedule/billed unit or a defined factor converts at rating input; else clear message + block rating for that read (no silent conversion). | CONFIRMED — PO R6 (OQ-004 closure) |
| BR-RAT-011 | Rollover-derived consumption arrives already computed+flagged by metering (GT-14 rule confirmed, PO R7); the engine prices what it receives. | CONFIRMED (rule; owned by metering) — B4 R7 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(GT-1)* | Flat E $0.12/kWh, base $18.50, usage 684 kWh | Lines: usage 684 × 0.12 = **82.08** (taxable), base **18.50** (taxable); subtotal 100.58; exact per GT-1 |
| TC-2 *(GT-2)* | Tiers 0–2 @ 3.00 / 2–5 @ 4.50 / 5+ @ 6.00; base 12.00; usage 3.72 kgal | Usage 2×3.00 + 1.72×4.50 = **13.74**; + base 12.00 = 25.74 pre-tax; tier boundaries consume exactly (BR-RAT-026/032) |
| TC-3 *(GT-5)* | Raw delta 274, multiplier ×10; tiers 0–1,000 @ 0.10 / 1,000+ @ 0.14 | Consumption 2,740 **before** tiering → 1,000×0.10 + 1,740×0.14 = **343.60**; multiplier-after-tiers (= 100.36) must NOT occur |
| TC-4 *(proration)* | Move-in day 16 of a 30-day cycle, base 30.50, tiered usage | Base 15/30 × 30.50 = **15.25** (GT-3); tier thresholds scale ×15/30 (0–1,000 → 0–500) before pricing (BR-RAT-002) |
| TC-4b *(split by days — PO 2026-08-12, OQ-155)* | WE-10's February water reprice: 6 kgal, v3 until Feb 14 and v4 from Feb 15, 14/28 days each side | Two day-weighted segments at their own versions: v3 base **4.00** + tier-1 **10.00** + tier-2 **3.25**; v4 base **4.25** + tier-1 **10.63** + tier-2 **3.43** → group **35.56**. **NOT 35.55** — the question summed v4's tiers before rounding (10.625 + 3.425 = 14.05); BR-RAT-003/B4.4 rounds PER LINE, so 10.63 + 3.43 = **14.06**. The bill is taxed **once**, over Σ(rounded taxable lines) across both segments (B4.2): on a Jan–Jun sub-period split 90/181 and 91/181, subtotal **75.59** → tax **6.24** in one pass, where taxing each segment apart and summing gives **6.23** |
| TC-4c *(split segment with no read — PO 2026-08-12, OQ-191)* | Tariff changes **15 Feb**; period 1–28 Feb, **6 kgal**, read on the 1st and the 28th and **not** on the 15th | DEFAULT: day-weighted usage estimate — **14/28 × 6 = 3 kgal each side** — and the segment is **MARKED AS ESTIMATED** on the bill. Tenant option: ask metering for the estimate under its own rules (BR-MET-026). Refusal by name (BR-BIL-015) remains ONLY where neither estimate can be produced |
| TC-5 *(TOU)* | US-RAT-006 §7 fixture (180 on-peak / 560 off-peak, summer weekday) | Two usage lines 39.60 + 50.40; a Jul 4 holiday read prices at off-peak via the tenant calendar |
| TC-6 *(sewer)* | Industrial: water usage lines $13.74, water base $12.00, sewer 40% | Sewer line = 0.40 × 13.74 = 5.496 → **5.50** finalized; base and tax excluded from the basis (BR-RAT-015) |
| TC-7 *(negative — UoM gate)* | Read in ccf, water billed kgal, no factor defined | Rating for that read blocks with the BR-RAT-038 message; no line produced, no silent conversion; with factor defined, conversion applies at input |
| TC-8 *(negative — purity)* | Engine called twice with identical inputs | Identical output, zero writes (no DB mutation, no audit from the engine itself — the caller audits); property test |
| TC-9 *(negative — unit discipline)* | Consumption supplied without an explicit unit | Rejected (CLAUDE.md #3); never assumed |
| TC-10 *(isolation)* | Two tenants, same schedule names, same period, different prices | Each run resolves only its tenant's `tariff_versions` under `app.tenant_id`; golden isolation test asserts no cross-tenant price leaks into any line |

**4 · Test Data** — GT-1/GT-2/GT-5 fixtures verbatim (§3). Proration: A-00390 move-in Aug 16, 30-day cycle, Residential Standard. TOU: A-00520 (Small Commercial) Jul 2026 with Jul 4 holiday. Sewer: A-00611 (Industrial, 40%). UoM: ccf read fixture on W-7004. Tenants: Brazos Bend + Lone Star Ridge (same-named "Res Water" schedule at different prices).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Input: consumption + unit | — | B2 `meter_reads` | `meter_reads.consumption` / `.unit` (read-only input) | numeric(18,6)+unit | integration | unit required; UoM gate |
| Input: plan + version snapshot | — | B2 r5 #13 | `unit_plan_assignments.plan_id/plan_version` + `plan_services`, `plan_rate_schedules` (read-only) | rows | reference-data | published plan version |
| Input: tariff version in force | — | B2 | `tariff_versions` window join on service date + child rows | rows | reference-data | BR-RAT-007 |
| Output: usage/base line candidates | S31.2 | B2 | `invoice_lines.service/tariff_version_id/description/quantity/unit/unit_price/amount/period_start/period_end` (written by billing, not the engine) | numeric(18,6) | system-derived | amounts exact; rounding at finalization |
| Output: taxable flag | — | B4.2 schema note | `invoice_lines.taxable` (true on usage/base only) | boolean | system-derived | BR-RAT-005 |
| UoM conversion factor | — | PO R6 (OQ-004) | **PROPOSED-SCHEMA** `tenant_services.billed_uom` + `tenant_services.uom_factor` (no column in B2/r5 — gap) | numeric(18,6) | reference-data | factor > 0 |

**6 · Acceptance**
- Given GT-1/GT-2/GT-5 fixtures, When the engine runs, Then every line amount reproduces the golden values to the digit, with intermediates unrounded.
- Given a prorated period, Then base and tier thresholds scale by calendar days exactly per B4.3/B4 §Tiered.
- Given a UoM mismatch without factor, a missing unit, or a repeat call, Then rating blocks (with message) / rejects / stays pure respectively.
- Given the two-tenant fixture, Then no line ever prices on the other tenant's version.

**7 · Finance Calculation** — **CONFIRMED (B4; finance 2026-08-07 + PO R1–R8).**
`consumption = (current − prior) × multiplier` (before tiers) → `usage = Σ tiers min(remaining, span×proration) × price`; `base = base_charge × days/period_days`; TOU `= Σ window_qty × season_window_price`; sewer `= pct × water_usage_$`; each line `round_half_up(amount, 2)` at finalization only.
Worked examples: **GT-5**: 274×10 = 2,740 → 1,000×0.10 + 1,740×0.14 = 100.00 + 243.60 = **$343.60**. **GT-2**: 2×3.00 + 1.72×4.50 = **$13.74** usage, +12.00 base = $25.74. **GT-1**: 684×0.12 = **$82.08** + 18.50 = $100.58 subtotal. **GT-3/B4.3**: 15/30 × 30.50 = **$15.25** base. Sewer: 0.40 × 13.74 = **$5.50**. **Split by days (PO 2026-08-12, OQ-155 — WE-10 February):** v3 4.00 + 10.00 + 3.25 and v4 4.25 + 10.63 + 3.43 → group **$35.56** (per-line rounding under BR-RAT-003/B4.4; the question's illustration said 35.55 because it summed 10.625 + 3.425 first). Refs: **GT-1, GT-2, GT-5** (fixtures freeze with finance before un-skip; rules already CONFIRMED).

**8 · Open Questions** — ~~None.~~ **AMENDED 2026-08-12 (PO rulings of the ~55-question batch).**
- **OQ-155 CLOSED — _"Split by days"_.** A tariff change inside a back-billed period prices as two day-weighted segments (TC-4b). **The worked group is 35.56 and the PO's own question said 35.55**; the difference is BR-RAT-003's per-line rounding, the rule was implemented exactly, and the cent was reported rather than hand-adjusted. ⚠ **The 35.56 figure is HUMAN-REVIEW-PENDING — it should be put to the PO in plain English, since what they were shown was 35.55.**
- **OQ-191 CLOSED — _"B is correct; and if required give option C also as backup ; I will make B default and C as option for user"_.** A split segment with no read on the cut day gets a **day-weighted usage estimate by default, marked as estimated**, with the metering estimate as a tenant option (TC-4c). **This SUPERSEDES the refuse-by-name behaviour shipped earlier the same day** under OQ-155 read literally; refusal survives only where neither estimate can be produced.
- **OQ-180 CLOSED — _"Base only"_** (BR-RAT-063): a mid-cycle plan-change PREVIEW shows the base half and states that usage is excluded — the engine still prices only consumption it is handed, and a preview has none.

---
id: US-RAT-013
epic: EP-RAT-05
module: rating
screens: [S31.2]
wave: 3
status: draft
blocked_by: []
depends_on: [US-RAT-009, US-RAT-012]
journeys: [J2]
rules: [BR-RAT-003, BR-RAT-005, BR-RAT-006, BR-RAT-016, BR-RAT-028, BR-RAT-036]
golden_tests: [GT-10, GT-11, GT-13]
finance_calc: confirmed
---
### US-RAT-013 — Totals: tax base + account exemption + minimum bill (per-service first, then plan floor)

**1 · Details** — As the billing run, I want the engine's totals pass to (1) apply **minimum bill** in both modes — per-service minimums first (`plan_services.minimum_amount`, mode A), then the plan floor tops up the total (`plans.minimum_bill_amount`, mode B) — emitting a taxable "minimum bill adjustment" line per shortfall; (2) compute **taxes**: percent taxes on Σ(taxable lines) = usage + base (+ minimum-adjustment, taxable like base) per jurisdiction attached via `plan_tax_rules` (override-aware), flat-per-bill and per-unit tax lines added per BR-RAT-036; (3) zero all tax for **tax-exempt accounts** regardless of service; so that GT-10/11/13 reproduce exactly. Fees and late charges never enter any base and are not this engine's concern (billing adds them after).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-RAT-016 / BR-RAT-028 | Minimum bill v1, both modes: (A) per-service minimum, (B) plan-level floor; when both set, per-service minimums apply first, then the plan floor tops up the total. Shortfall emits a "minimum bill adjustment" line, taxable like base (GT-13 / B4-addendum OQ-007 closure). | CONFIRMED — PO Q&A R1 Q9 + R5/R6 (D2 OK); GT-13 |
| BR-RAT-005 | Tax base = usage + base only; fees/late never taxed. `invoice_lines.taxable` drives the sum. | CONFIRMED — B4.2; GT-10 |
| BR-RAT-006 | Exemption is account-level (`accounts.tax_exempt`), regardless of service → tax = 0 for the whole account. | CONFIRMED — B4.2; GT-11 |
| BR-RAT-003 | Per-line half-up 2dp at finalization (tax lines included). | CONFIRMED — B4.4 |
| BR-RAT-036 | *(shared)* tax forms percent/flat/per-unit; no tax-on-tax, no fee taxation. | percent CONFIRMED / flat & per-unit PROPOSED | ⚠ **THE PER-UNIT FORM IS BUILT AND PRICING AS OF 2026-08-31 (`CR-052` W5 task 16, `v2.95.0`).** The ratification status of this rule is UNCHANGED — percent CONFIRMED, flat and per-unit PROPOSED — because building a form is not signing it; what changed is that the third form now produces a line instead of nothing. **The threshold is read as `BR-RAT-042` rules it: MARGINAL.** Worked, run and asserted: a Water Conservation Surcharge of `$0.25 / kgal` above `15` on a meter reading `18.72 kgal` is taxed on `3.72 kgal` and bills **`$0.93`**; read as a whole-bill levy the same rule bills **`$4.68`**, which is the customer paying a conservation surcharge on the first fifteen thousand gallons the rule exempts. `per_unit_uom` is MANDATORY and is CHECKED against the unit the usage was measured in — a rule levied per `kWh` against a meter read in `kgal` REFUSES and names both, because this engine holds no conversion factor (`BR-RAT-038`). **Whether the threshold PRORATES on a part period is unsigned and is `DEF-2702`**: built unscaled, which under-charges rather than over-charges. **PER-METER is still not priced anywhere** and the compounding half is still `DEF-381`.

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(GT-10)* | Usage 82.08 + base 18.50 taxable; late fee 8.13 present; 8.25% | Tax = 8.25% × 100.58 = 8.29785 → **8.30**; late excluded; total 100.58 + 8.13 + 8.30 = **116.01** |
| TC-2 *(GT-11)* | Same, account flagged tax_exempt | Tax = **0** regardless of service; total **108.71**; exemption ref/expiry surfaced to billing |
| TC-3 *(GT-13, mode A)* | Water: usage 6.10 + base 12.00 = 18.10 < per-service minimum 25.00 | "Minimum bill adjustment — Water" line **+6.90**, taxable; tax = 8.25% × 25.00 = 2.0625 → **2.06** |
| TC-4 *(both modes)* | E: usage+base 22.00 vs service-min 25.00 → +3.00; W: 15.00 vs min 12.00 → no adj; plan floor 45.00 | Per-service first: total 22.00+15.00+3.00 = 40.00; floor tops up **+5.00** plan-level adjustment → 45.00; order is service-min-then-floor, never floor-first (BR-RAT-028) |
| TC-5 | Plan tax rules with override: Senior plan, TX State rate_override 0 | TX State line 0.00 for that plan; Fort Bend still 2.00% (override is per jurisdiction) |
| TC-6 | Flat + per-unit taxes present (PUC $0.85; surcharge 0.25/kgal × 3.72) | Extra lines 0.85 and 0.93; neither joins any percent base (no tax-on-tax, BR-RAT-036) |
| TC-7 *(negative)* | A fee line wrongly marked taxable arrives from a mis-seeded charge | Engine refuses to include non-usage/base line kinds in the percent base (B4.2 is structural, not data-driven); discrepancy logged for the caller |
| TC-8 *(negative)* | Exempt account with expired `tax_exempt_expires` | Exemption not honored past expiry — taxes computed; flagged to billing for review (B4 "exemption evidence/expiry" placeholder handled as data, not silently ignored) |
| TC-9 *(isolation)* | Same-named jurisdiction "State Utility Tax" in both tenants at different rates | Each account taxes on its own tenant's jurisdiction rows only (RLS + plan_tax_rules scoping) |

**4 · Test Data** — GT-10/GT-11 fixture: usage 82.08, base 18.50, late 8.13, rate 8.25% (TX 6.25 + Fort Bend 2.00), account A-00412; exempt variant: church account A-00588 (tax_exempt, ref "TX 01-339 exemption cert", expires 2027-06-30). GT-13 fixture: usage 6.10, base 12.00, minimum 25.00. Both-modes fixture per TC-4 (plan floor 45.00). Senior plan override 0. Lone Star Ridge: "State Utility Tax" 4.00%.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Per-service minimum | — | B2 r5 #6 | `plan_services.minimum_amount` (NULL = none) | numeric(18,6) | reference-data | ≥ 0 |
| Plan floor | — | B2 r5 #18 | `plans.minimum_bill_amount` (NULL = none) | numeric(18,6) | reference-data | ≥ 0 |
| Minimum-adjustment line | S31.2 | GT-13 + B4 addendum (OQ-007) | `invoice_lines` (description "Minimum bill adjustment…", amount = shortfall, taxable = true) | numeric(18,6) | system-derived | per-service before floor |
| Taxable-base sum | — | B4.2 schema note | Σ `invoice_lines.amount` where `taxable` | numeric(18,6) | system-derived | usage/base/min-adj kinds only |
| Tax lines | S31.2 | B2 | `invoice_lines` per jurisdiction (+ `invoices.tax_total`) | numeric(18,6) | system-derived | half-up 2dp per line |
| Exemption flags | — | B4.2 schema note | `accounts.tax_exempt` / `.tax_exempt_ref` / `.tax_exempt_expires` (⚠ cross-module read, customers) | bool/text/date | reference-data | expiry honored (TC-8) |
| Plan tax attachment + override | — | B2 r5 #11 | `plan_tax_rules.rate_override` (NULL = jurisdiction rate) | numeric(18,6) | reference-data | per-jurisdiction |

**6 · Acceptance**
- Given GT-10/GT-11/GT-13 fixtures, Then totals reproduce 116.01 / 108.71 / (18.10 → 25.00 with +6.90 and 2.06 tax) exactly.
- Given both minimum modes set, Then per-service adjustments always precede the plan-floor top-up and the combined result equals the §7 arithmetic.
- Given any fee/late line, Then it never enters a percent-tax base under any data condition.
- Given cross-tenant jurisdictions, Then no account taxes on another tenant's rates.

**7 · Finance Calculation** — **CONFIRMED (B4.2 + BR-RAT-028).**
`per-service: adj_s = max(0, min_s − (usage_s + base_s))` → `plan floor: adj_plan = max(0, floor − Σ_s(usage_s + base_s + adj_s))` → `tax_j = rate_j × Σ(taxable lines)` per jurisdiction; exempt account ⇒ all tax_j = 0; each line half-up 2dp.
Worked examples: **GT-13**: 6.10 + 12.00 = 18.10; adj = 25.00 − 18.10 = **6.90**; tax = 0.0825 × 25.00 = 2.0625 → **2.06**; total **27.06**. **Both modes (TC-4)**: adj_E = 3.00; Σ after = 40.00; floor adj = 45.00 − 40.00 = **5.00**. **GT-10**: 0.0825 × 100.58 = **8.30**; total **116.01**. **GT-11**: tax 0 → **108.71**. Refs: **GT-10, GT-11, GT-13**.

**8 · Open Questions** — None.

---
id: US-RAT-015
epic: EP-RAT-05
module: rating
screens: [S31.2]
wave: 3
status: draft
blocked_by: []
depends_on: [US-RAT-005, US-RAT-006, US-RAT-007, US-RAT-008, US-RAT-012, US-RAT-013, US-RAT-014]
journeys: [J2]
rules: [BR-RAT-003, BR-RAT-019, BR-RAT-041, BR-RAT-044, BR-RAT-045]
golden_tests: [GT-1, GT-2, GT-5, GT-8, GT-15]
finance_calc: confirmed
---
### US-RAT-015 — Rule-type plugins: one interface per pricing model, one per charge amount rule (a new rule type is a new module)

**1 · Details** — As the Eng Lead maintaining a 🔒 money path, I want the engine's *shape* fixed by contract, not by convention: every **pricing model** (flat · tiered · TOU · demand · seasonal · capacity · percent-of-service) is its own module implementing the single interface `price(subscription_ctx, measured_usage, model_config) → line candidates` (BR-RAT-044), and every **charge amount rule** (flat · percent · percent-with-minimum today, BR-RAT-041) is its own module implementing `amount(charge_ctx) → NUMERIC(18,6)` (BR-RAT-045) — both resolved through a registry that is closed at import time. So that adding a rule type is adding a file, the way `capacity` was added after v1 scoping (BR-RAT-019) without moving any surrounding rule, and so that the seven-stage pipeline (BR-BIL-037) never grows a `if model == …` ladder. This story changes **no arithmetic**: every model's math stays exactly as US-RAT-012/013/014 specify it, and the golden suite is what proves the refactor is a refactor (BR-BIL-038). Entry: called by the bill run's price-usage and apply-charges stages; output previewed in S31.2. Nothing about this story is visible to a user — its whole value is that the next rule type costs a module instead of a surgery.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-RAT-044 | Every `tariff_model` value is a module behind one `price(...)` interface; the stage code carries no per-model branching; the registry is closed at import time (models are code, never tenant data). | PROPOSED — derived from B2 r5 #16 (`tariff_model` enum) + BR-RAT-019 (capacity was added to the enum post-scoping) + EP-RAT-05 scope |
| BR-RAT-045 | flat / percent / percent-with-minimum are three implementations of one `amount(charge_ctx)` interface; a fourth rule adds a module + registry row and changes no stage. No implementation rounds its own return value. | PROPOSED — derived from BR-RAT-041 + US-RAT-008 §7 (the three forms already share one call site) |
| BR-RAT-041 | Charge amount rules v1 = flat / percent / percent-with-minimum; "Formula" visible but disabled. **This story does not change that** — it only makes the fourth slot a module-shaped hole (filled, if the PO ratifies the amendment, by EP-RAT-07). | CONFIRMED — PO OQ-053 |
| BR-RAT-003 | Rounding is a *finalization* concern, never a plugin concern: a plugin returns NUMERIC(18,6). | CONFIRMED — B4.4 |
| BR-RAT-019 | `capacity` joined flat/tiered/TOU/demand/seasonal as a model — the precedent this interface generalises. | CONFIRMED — Lane C r5 approved by PO, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 *(GT-1/GT-2/GT-5)* | Flat, tiered and tiered-with-multiplier fixtures priced through the registry rather than a branch | 82.08 / 13.74 / 343.60 to the digit — identical to US-RAT-012 TC-1/2/3; the registry adds no arithmetic |
| TC-2 *(GT-15)* | Capacity model resolved through the registry | Solar 4 × 10.00 = **40.00**, battery 2 × 12.00 = **24.00**, taxable like base — identical to US-RAT-014 TC-1 |
| TC-3 *(GT-8 arithmetic)* | The three amount rules through one interface: flat CONN 85.00 · percent · percent-with-minimum LATE on overdue 542.10 | 85.00 · percent per its basis · max(5.00, 0.015 × 542.10) = **8.13**; each returns NUMERIC(18,6) unrounded, finalized once by the caller (BR-RAT-003) |
| TC-4 *(no branching)* | Architecture test greps the price-usage stage module | It names **no** model (`tiered`, `tou`, `capacity` … absent); the only model reference is the registry lookup. Proven RED first against the pre-refactor file (hard-won law 7) |
| TC-5 *(negative — fail closed)* | A `tariff_model` enum value with no registered plugin reaches the engine | The run **refuses** naming the model and the schedule; it never prices as 0 and never silently falls back to flat (hard-won law 3) |
| TC-6 *(negative — no self-rounding)* | A plugin returns `round(x, 2)` | Rejected by the plugin contract test: amounts leave a plugin at NUMERIC(18,6); rounding happens once, at finalization (BR-RAT-003, B4.4) |
| TC-7 *(negative — registry is code)* | A patch registers a plugin from a tenant row / a runtime string | Rejected: the registry is closed at import; no tenant data path can add or replace an implementation (this is the boundary EP-RAT-07 must plug into, not around) |
| TC-8 *(negative — purity)* | A plugin performs a DB read, writes a row, or reads the clock | Purity test fails (US-RAT-012 TC-8 extended to every plugin): plugins receive their inputs and return data |
| TC-9 *(isolation)* | Brazos Bend and Lone Star Ridge both price a `tiered` water schedule in the same process | Each resolves the same plugin with its **own** tariff version's tiers under `app.tenant_id`; a shared registry never becomes a shared config path |

**4 · Test Data** — Brazos Bend MUD registry set: `flat` (Res Electric $0.12/kWh, GT-1) · `tiered` (Res Water 0–2 @ 3.00 / 2–5 @ 4.50 / 5+ @ 6.00, GT-2) · `tou` (Small Commercial, US-RAT-006 fixture) · `demand` (14.2 kW × $9.50) · `seasonal` (summer/winter price sets) · `capacity` (A-00733 solar 4 × $10.00, battery 2 × $12.00, GT-15) · `percent_of_service` (sewer **90% of the water VOLUME at $5.0000/kgal**, A-00611 — `CR-081`, PO re-sign 2026-09-08; it read *"40% of water usage-$"* until that date and needed no rate of its own at all). Amount rules: CONN flat $85.00 · LATE percent-with-minimum 1.5% / $5.00 on overdue $542.10 (GT-8 fixture). Unregistered-model fixture: a `tariff_versions` row with model `interval` (not implemented) on schedule "Pilot Interval Water". Isolation: Lone Star Ridge `tiered` "Co-op Water" at 3.10 tier 1.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Model selector | S11 step 1 | B2 r5 #16 | `tariff_versions.model` (flat\|tiered\|tou\|demand\|seasonal\|capacity\|percent_of_service) | enum | reference-data | every enum value must resolve to a registered plugin (TC-5) |
| Model config | — | B2 r5 #2/#4/#17 | child rows per model: `rate_tiers` · `time_of_use_windows` · `rate_seasons` · `capacity_rates` (+ demand/percent-of-service PROPOSED-SCHEMA per field map) | rows | reference-data | validated by the owning model's rule (BR-RAT-032/033/034) |
| Amount rule selector | S12 step 2 | prototype-extracted + BR-RAT-041 | **PROPOSED-SCHEMA** `charges.amount_rule` (flat\|percent\|percent_min; `formula` only if the BR-RAT-046 amendment is ratified) — B2 today implies the rule from which of `amount`/`percent`/`min_amount` is filled | enum | user-input | exactly one rule per charge code |
| Plugin output: line candidate | S31.2 | B2 | `invoice_lines.quantity/unit/unit_price/amount/taxable/tariff_version_id` (written by billing) | numeric(18,6) | system-derived | unrounded at plugin boundary (TC-6) |
| Registry | — | GAP — no artefact today (this story creates it) | code-only map `model → module`, `amount_rule → module`; **no table** | — | system-derived | closed at import; TC-7 |

**6 · Acceptance**
- Given every golden fixture that exercises a model (GT-1/2/5/15) and the GT-8 amount-rule arithmetic, When priced through the registry, Then every figure is identical to the pre-refactor result.
- Given the price-usage stage module, Then it names no model — the only per-model knowledge lives in the plugins and the registry.
- Given an unregistered model, a self-rounding plugin, a runtime-registered plugin, or an impure plugin, Then each is refused with the reason stated — none degrades quietly.
- Given two tenants pricing the same model concurrently, Then each uses only its own tariff version.

**7 · Finance Calculation** — **CONFIRMED (unchanged from US-RAT-012/013/014 — this story moves code, not math).**
Per model: `flat = qty × unit_price` · `tiered = Σ min(remaining, span×proration) × price` · `tou = Σ window_qty × season_window_price` · `demand = peak_kW × demand_rate` · `capacity = units × rate_per_unit × days/period_days` · `percent_of_service = pct × source usage-$`. Per amount rule: `flat = amount` · `percent = percent × basis` · `percent_min = max(min_amount, percent × basis)`.
Worked: **GT-5** 274 × 10 = 2,740 → 1,000×0.10 + 1,740×0.14 = **$343.60** · **GT-2** 2×3.00 + 1.72×4.50 = **$13.74** · **GT-15** 4×10.00 = **$40.00** and 2×12.00 = **$24.00** · **GT-8** max(5.00, 0.015 × 542.10) = **$8.13**. Refs: **GT-1, GT-2, GT-5, GT-8, GT-15** — reproduced, never restated.

**8 · Open Questions** — None. *(The `percent` rule's basis is under-specified in BR-RAT-041/US-RAT-008 §7 — "percent × base_amount" never says which subtotal. That gap is raised where it becomes load-bearing, in EP-RAT-07 US-RAT-016 §8 candidate OQ-096(c); it is pre-existing and does not block this story, which passes the basis through unchanged.)*
