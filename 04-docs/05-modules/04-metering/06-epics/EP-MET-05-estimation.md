# EP-MET-05 — Estimation & True-up
> Reconciled 2026-08-08 against PO rulings (decision log) — propagation sweep.

**Module:** metering (product name: **Meter Reads**) · **Wave:** W3 · **Screens:** S25, S28, S29, S31.2 (Estimated tab) · **Status:** draft (OQ-003 CLOSED — math confirmed as tenant-configurable defaults; buildable)

## Scope
**In:** auto-estimation of missing reads (trailing-3-cycle daily average × period days — **CONFIRMED defaults, OQ-003 CLOSED (PO R6), tenant-configurable via the S64 `read_validation_settings`: est_method trailing_3_daily_avg, est_max_consecutive 2 — B2 r5 #15**), running **PER CHANNEL** for multi-register meters (**BR-MET-058, CONFIRMED**: each TOU window estimated independently from its own trailing history; a flat meter is just the single `total` channel — B2 r8), the max-2-consecutive-estimates cap with forced field visit, estimate labeling (method + consecutive count, per A5 "Estimated (1st/2nd consecutive)"), true-up via register arithmetic at the next actual read (within one channel's lineage), and staff override/skip of an estimate with reason + audit. Invoked from S28 step 4 ("Estimate (trailing-3 avg)" / "Estimate all missing"), S25/S29 fix actions, and S31.2's "Auto-estimate the 11 missing reads" toggle.
**Out:** pricing the estimated or true-up quantities (rating, GT-9's money side) · the validation flags themselves (EP-MET-04) · the completeness gate that reports which channel records are missing (BR-MET-049 — EP-MET-04/US-MET-018 compute it; this epic only fills gaps on request) · vacancy/skip billing consequences (billing decides base-only vs skip per S31.3) · net-metering consumption/export handling (rating EP-RAT-06 — kWh-netting deferred to v1.1 per OQ-001 closure, PO Q&A R1) · the read-archival job (EP-MET-03 US-MET-020).

> **OQ-003 CLOSED (PO R6):** trailing-3 daily-avg × period days + the 2-consecutive cap ship as DEFAULTS; the tenant may change the method parameters in the same settings surface (S64 card, `read_validation_settings` — B2 r5 #15). BR-MET-026/027/029 are CONFIRMED. **Code-side note: GT-9 flips `skip` → `xfail`** — the expected values are signed; the test fails-expected until the engine lands, never skips.

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| — | *(no list screens owned by this epic — estimated rows render inside S25 (EP-MET-04) and S31.2 (billing))* | | | | | | | |

## Stories

---
id: US-MET-014
epic: EP-MET-05
module: metering
screens: [S25, S28, S31.2]
wave: 3
status: draft
blocked_by: []
depends_on: [US-MET-008, US-MET-010, US-MET-011, US-MET-012]
journeys: [J3]
rules: [BR-MET-026, BR-MET-027, BR-MET-028, BR-MET-058]
golden_tests: [GT-9]
finance_calc: confirmed
---
### US-MET-014 — Auto-estimate missing reads (trailing-3 daily average, max 2 consecutive, per channel)

**1 · Details** — As a billing clerk closing a cycle with unread meters, I want missing reads auto-estimated from the meter's own history — trailing-3-cycle **daily average × days in the estimated period**, actuals only — labeled Est. with method and consecutive count, capped at 2 consecutive estimates before a field visit is forced, so that bills go out on time without inventing numbers silently. Estimation runs **per channel** (**BR-MET-058**): each channel of a multi-register meter is estimated independently from **its own** trailing actual history — a TOU meter's tou_on window never borrows tou_mid history, and a flat meter is simply the single `total` channel (B2 r8). Entry points: S28 step 4 "Estimate (trailing-3 avg)" per row and "Estimate all missing" bulk (per-channel rows per the BR-MET-049 missing-record set); S25/S29 Estimate action on a pending meter; S31.2 "Auto-estimate the 11 missing reads" checkbox. Exit: estimated `meter_reads` rows (status `estimated`, one row per estimated channel, no current register value — consumption only) visible in S25 with the Est. pill and in S31.2's Estimated tab (columns Meter · Account · Estimated · Method · Consecutive · Fix per prototype).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-MET-026 | Estimation math: `daily_avg = Σ(consumption of last 3 actual reads) ÷ Σ(their day counts)`; `estimate = daily_avg × days_in_estimated_period`, NUMERIC(18,6) unrounded; **actual reads only** feed the average (estimates never compound); shorter history uses what exists (≥1 actual); no history → no estimate (field visit). Ships as the SEEDED DEFAULT method (`est_method trailing_3_daily_avg`), tenant-changeable in the S64 settings. | CONFIRMED — OQ-003 CLOSED (PO R6): defaults per B4 addendum, tenant-configurable (B2 r5 #15) |
| BR-MET-027 | Maximum 2 consecutive estimates per meter (seeded default `est_max_consecutive 2`, tenant-changeable); a consecutive miss beyond the cap must not auto-estimate — the row is forced to Schedule field visit (S31.2 shows "1st estimate"/"2nd estimate" accordingly). | CONFIRMED — OQ-003 CLOSED (PO R6); A5 "Estimated (1st/2nd consecutive)" |
| BR-MET-028 | Every estimate is labeled with method (`trailing_3_avg`) and consecutive number, carries `status = estimated` and `source` distinct from actuals, and is reversible by the next actual read (A5: "Estimated → trued-up on next real read"); estimated rows never supply a register `current_value` — only consumption. | PROPOSED — A5 (EXPLICIT) + prototype Estimated tab columns |
| BR-MET-058 | Estimation runs **PER CHANNEL** for multi-register meters: each TOU window is estimated independently from its own trailing history; the BR-MET-026 formula applies within one channel's actuals only — histories never mix across channels. | CONFIRMED — PO Reads pre-session RD-1 (BR-MET-058) |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | M-7001 missing for Aug 3 → Sep 2 (30 days); last 3 actuals: 612 kWh/30d, 618/30d, 624/30d | `daily_avg = 1,854 ÷ 90 = 20.600000`; estimate `20.600000 × 30 = 618.000000 kWh`; row status `estimated`, channel `total`, method trailing_3_avg, consecutive 1 |
| TC-2 | S31.2 Estimated tab after TC-1 | Row: M-7001 · A-00412 · 618 kWh · 3-cycle avg · "1st estimate" · Fix (Keep/Override) |
| TC-3 | M-7001 missing again next cycle | 2nd estimate allowed, labeled "2nd estimate"; average still uses the last 3 **actuals** (612/618/624) — the 618 estimate is excluded |
| TC-4 *(negative)* | M-7001 missing a 3rd consecutive cycle | Auto-estimate refused (cap = tenant's configured `est_max_consecutive`, seeded 2); disposition forced to Schedule field visit; batch/bulk actions skip it with the stated reason |
| TC-5 *(negative)* | Brand-new meter (0 actuals) in "Estimate all missing" | Skipped with reason "no history — field visit"; no invented value |
| TC-6 *(negative)* | Lone Star Ridge raises `est_max_consecutive` to 3 on S64; Brazos Bend keeps the seeded 2 | Caps evaluate per tenant config (OQ-003 closure — defaults tenant-changeable): Lone Star Ridge's 3rd consecutive estimate is allowed, Brazos Bend's still forces a field visit — never a hardcoded 2 |
| TC-7 | Water meter W-7004 estimate | Computes in raw register units (gallons) with explicit unit; billed-unit conversion per the OQ-004 closure (match-or-factor, kgal default) stays a rating-input concern |
| TC-8 *(isolation)* | Same-numbered meter in Lone Star Ridge with different history | Its estimate uses only Lone Star Ridge reads; cross-tenant history never leaks into an average |
| TC-9 | TOU meter M-7450 missing all Sep channel records; per-channel actual histories (3 × 30d cycles): tou_on 210+216+204 = 630 · tou_mid 118+121+115 = 354 · tou_off 96+99+93 = 288 · total 424+436+412 = 1,272 | **Four estimated rows, one per channel** (BR-MET-058), each from its own history: tou_on 630÷90×30 = 210.000000 · tou_mid 354÷90×30 = 118.000000 · tou_off 288÷90×30 = 96.000000 · total 1,272÷90×30 = 424.000000 kWh; no cross-channel mixing; each row labeled method + consecutive; Σ window estimates (424) = total estimate (424) — internally consistent |

**4 · Test Data** — Brazos Bend M-7001 (E, ×1, kWh, channel `total`): actuals May 5→Jun 4 = 612 kWh (30d), Jun 4→Jul 4 = 618 (30d), Jul 4→Aug 3 = 624 (30d); last actual register 42,864 on Aug 3, 2026. Estimated period Aug 3 → Sep 2 (30 days). W-7004 (W, gallons): trailing-3 total 11,160 gal / 90d → 124 gal/day × 30 = 3,720.000000 gal (3.72 kgal display per the OQ-004 closure conversion). TOU M-7450 (E, kWh) per-channel actuals per TC-9 (Jun/Jul/Aug cycles, 30d each). New meter M-7999 (no history). Settings: Brazos Bend est_max_consecutive 2 (seeded), Lone Star Ridge 3 (tenant-edited). Actor: Marcus Vega; cycle 09-A.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Estimated consumption | S25/S31.2 | prototype-extracted ("618 kWh") | `meter_reads.consumption` + `unit` (no `current_value`) | numeric(18,6)+unit | system-derived | per BR-MET-026; unrounded |
| Channel (estimate rows) | — | BR-MET-058 + B2 r8 | `meter_reads.channel` on each estimated row; trailing-history query filters (meter, channel) | enum | system-derived | per-channel histories never mix (BR-MET-058) |
| Status / pill | S25 | prototype-extracted ("Est.") | `meter_reads.status = 'estimated'` (B2 enum) | enum | system-derived | — |
| Method | S31.2 | prototype-extracted ("3-cycle avg") | **PROPOSED-SCHEMA** `meter_reads.estimation_method` ('trailing_3_avg') — method parameter from `read_validation_settings.est_method` (B2 r5 #15) | enum/text | system-derived | recorded on every estimate |
| Consecutive count | S31.2 | prototype-extracted ("1st/2nd estimate") | **PROPOSED-SCHEMA** `meter_reads.consecutive_estimate_no` | integer | system-derived | ≤ tenant `est_max_consecutive` (seeded 2 — BR-MET-027, cap per meter) |
| Period days | S29 | prototype-extracted ("31 days") | `meter_reads.period_start/period_end` + `days_since_prior` | dates/int | system-derived | matches estimate span |
| Estimate trigger (row/bulk/toggle) | S28/S25/S31.2 | prototype-extracted | write path via estimation service (only writer — B1); bulk generates per-channel rows per the BR-MET-049 missing set | — | user-input | role-gated; audited |
| Estimate audit | — | CLAUDE.md #7 spirit | `audit_log` (`read.estimated`: meter, channel, inputs, result, actor/trigger) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given a meter with 3 actuals, When estimated, Then the stored consumption equals the §7 formula exactly (NUMERIC(18,6)), labeled with method + consecutive count, And appears as Est. in S25 and in S31.2's Estimated tab.
- Given a multi-register meter, Then each missing channel is estimated independently from its own actual history — one estimated row per channel, never mixed (BR-MET-058).
- Given a consecutive miss beyond the tenant's cap or no history, Then no estimate is produced and field visit is forced with a stated reason.
- Given a tenant-changed estimation parameter (S64), Then the engine evaluates with the tenant's values — the shipped numbers are seeded defaults, never hardcoded (OQ-003 closure).

**7 · Finance Calculation** — **CONFIRMED — OQ-003 CLOSED (PO R6): defaults per B4 addendum, tenant-configurable.**
`estimate = (Σ last-3 actual consumptions ÷ Σ their day counts) × days_in_period`
Worked example (GT-9 fixture): actuals 612 + 618 + 624 = 1,854 kWh over 90 days → daily_avg = 20.600000 kWh/day; period 30 days → **estimate = 618.000000 kWh** (matches GT-9's "trailing-3 avg = 618 kWh billed"). Per channel (BR-MET-058): the same formula runs within each channel's own actual history — e.g. M-7450 tou_on 630 ÷ 90 × 30 = **210.000000 kWh**, computed from tou_on actuals only. Quantity only — pricing at current-period rates happens in rating; rounding only at invoice-line finalization (B4.4). Ref: **GT-9** (expected values signed via the OQ-003 closure — code-side test flips `skip` → `xfail` until the engine lands).

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-003 *(existing — referenced, not duplicated)* | Estimation math + consecutive-estimate cap + true-up | Nothing — closed | Product Owner (chat session) | CLOSED — defaults per B4 addendum, tenant-changeable via S64 settings (PO R6) |

---
id: US-MET-015
epic: EP-MET-05
module: metering
screens: [S25, S29, S31.2]
wave: 3
status: draft
blocked_by: []
depends_on: [US-MET-009, US-MET-010, US-MET-014]
journeys: [J3]
rules: [BR-MET-028, BR-MET-029, BR-MET-030, BR-MET-058]
golden_tests: [GT-9]
finance_calc: confirmed
---
### US-MET-015 — True-up at next actual read + estimate override/skip

**1 · Details** — As a utility, I want the next **actual** read after an estimate to self-correct the account by register arithmetic — the next billed quantity is the full register delta since the last actual minus what was already billed as estimates — and I want staff to be able to override an estimate's value or skip estimating entirely (reason + audit), so that customers are never permanently over- or under-billed from an estimate. True-up runs **within one channel's lineage** (BR-MET-058 + BR-MET-029): the next actual `tou_on` read trues up only the `tou_on` estimates since that channel's last actual — channels never cross. Entry: true-up runs automatically inside read commit (EP-MET-03) when an actual lands on a meter+channel whose latest read(s) are estimates; Override/Keep from S31.2's Estimated tab Fix select and S29's footer; Skip from the missing-read dispositions. Exit: trued-up read row; overridden estimate superseded (BR-MET-053 mechanics — US-MET-016); skipped meter stays `missing` for billing's exception handling (bill base only / hold, per S31.3 — billing's decision).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-MET-028 | *(shared)* estimates are reversible on the next real read (A5). | PROPOSED |
| BR-MET-029 | True-up by register arithmetic: at the next actual read, `trued_quantity = (actual_register − last_actual_register) × multiplier − Σ estimated consumption billed since that last actual`; the trued quantity bills at **current-period rates** (no retroactive repricing); negative trued quantities credit the same way; the true-up links to the estimate rows it corrects. | CONFIRMED — OQ-003 CLOSED (PO R6; GT-9 expected values signed) |
| BR-MET-058 *(shared)* | Per-channel scope: the BR-MET-029 arithmetic runs within one channel's lineage — actual register, last actual register and the Σ of billed estimates are all taken from the same (meter, channel); channels true up independently. | CONFIRMED — PO Reads pre-session RD-1 (BR-MET-058) |
| BR-MET-030 | Override/skip of an estimate requires a reason and writes audit: Override supersedes the estimate row with the staff value (re-validated per EP-MET-04); Skip leaves the meter `missing` for the cycle — metering never decides the billing consequence (base-only/hold belongs to S31.3). | PROPOSED — prototype Fix selects (Keep estimate / Override / Field visit; Skip cycle) + IS-6 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | After US-MET-014 TC-1 (618.000000 est., channel `total`), actual read Oct 2: register 44,182 | Register delta = 44,182 − 42,864 = 1,318.000000; Σ estimates billed = 618.000000; trued quantity = **700.000000 kWh** for Aug/Sep-corrected billing at current rates; true-up row links to the estimate; audit `read.trued_up` |
| TC-2 | GT-9 cross-check | 618 estimated, actual implies 700 → correction +82 kWh embedded in the trued quantity (700 = 618 + 82); numbers match GT-9's fixture exactly |
| TC-3 | Over-estimate case: register delta 1,100, estimates billed 1,236 (two cycles) | Trued quantity = −136.000000 → flows as a quantity credit at current rates; never a negative register |
| TC-4 | Marcus overrides the 618 estimate to 640 with reason "seasonal irrigation, per customer call" | Estimate superseded (new row, method `manual_override`, supersede mechanics per BR-MET-053/US-MET-016), re-validated, audited; consecutive counter unchanged |
| TC-5 | Skip: Marcus skips estimating M-7613 with reason "meter being replaced" | No estimate row; meter stays missing; S31.2 No-usage/Missing case handles the account; reason + audit stored |
| TC-6 *(negative)* | Override without reason / Keep-estimate modal dismissed | No write, no audit (IS-6) |
| TC-7 *(negative)* | Actual read commits on a meter+channel with no estimate since the last actual | Normal consumption path — no true-up row, no estimate links (Σ estimated = 0); nothing invented |
| TC-8 *(negative)* | Actual read arrives whose register is **less** than the last actual | Rollover rule applies (OQ-009 CLOSED, GT-14): a full register wrap auto-computes rollover consumption (flagged for review); any other negative usage is a hard error, never auto-fixed (BR-MET-052) — no negative true-up is ever computed from a wrapped register |
| TC-9 *(isolation)* | True-up on Brazos Bend M-7001 while Lone Star Ridge has an estimated meter of the same number | Each tenant's true-up reads only its own lineage; isolation suite asserts no cross-tenant read enters either computation |
| TC-10 | Per-channel true-up: M-7450 `tou_on` estimated 210.000000 (Sep); next actual tou_on register Oct 3 = 13,864 vs last actual 13,210 | tou_on trued quantity = (13,864 − 13,210) × 1 − 210.000000 = **444.000000 kWh** on the tou_on lineage only; tou_mid/tou_off/total true up independently from their own registers and estimates (BR-MET-058) — no cross-channel arithmetic |

**4 · Test Data** — M-7001 (`total`): last actual Aug 3 register 42,864 (×1, kWh); estimate 618.000000 (Sep bill); next actual Oct 2 register 44,182 → trued 700.000000. Over-estimate fixture: M-7305, delta 1,100 vs 1,236 estimated. Per-channel fixture: M-7450 tou_on last actual Aug 3 register 13,210, Sep estimate 210.000000, next actual Oct 3 register 13,864 → trued 444.000000 kWh. Override 618 → 640, reason "seasonal irrigation, per customer call". Skip: M-7613, reason "meter being replaced". Actors: Marcus Vega, Dana Whitfield.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Actual register at true-up | S29 | derived (commit path) | `meter_reads.current_value` (same meter+channel lineage — BR-MET-058) | numeric(18,6) | user-input (import) | rollover rule per OQ-009 closure (wrap auto-computed + flagged; other negatives = hard error, BR-MET-052) |
| Trued quantity | S31.2/S29 | GT-9 + B4 addendum (OQ-003 CLOSED) | `meter_reads.consumption` on the true-up row + **PROPOSED-SCHEMA** `meter_reads.trues_up_read_ids uuid[]` (links to corrected estimates, same channel) | numeric(18,6)+unit | system-derived | per BR-MET-029; may be negative; single-channel scope |
| Estimate override value + reason | S31.2/S29 | prototype-extracted ("Override") | superseding `meter_reads` row (**PROPOSED-SCHEMA** `estimation_method = 'manual_override'`; supersede link `superseded_by_id`/`superseded_at`, B2 r8) + reason | numeric(18,6)/text | user-input | reason required; ≥ 0 |
| Skip + reason | S28/S31.2 | prototype-extracted ("Skip cycle" / "Skip this month") | disposition `skip` + reason (no read row) | enum/text | user-input | reason required |
| True-up audit | — | CLAUDE.md #7 spirit | `audit_log` (`read.trued_up` / `read.estimate_overridden` / `read.estimate_skipped`, inputs + result incl. channel, before/after) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given an estimated meter+channel receiving an actual read, When commit runs, Then the trued quantity equals the §7 arithmetic exactly within that channel's lineage, links to the estimates it corrects, and bills at current-period rates — GT-9's fixture reproduces to the digit.
- Given a multi-register meter, Then each channel trues up independently (BR-MET-058) — no register or estimate from another channel ever enters the computation.
- Given an override or skip, Then a reasoned, audited supersede/disposition exists and metering never silently decides a billing outcome.
- Given tenant-changed estimation parameters (S64), Then true-up honors the tenant's configured method values (OQ-003 closure — config over constant).

**7 · Finance Calculation** — **CONFIRMED — OQ-003 CLOSED (PO R6; GT-9 expected values signed).**
`trued_quantity = (actual_register − last_actual_register) × multiplier − Σ estimated_consumption_billed_since_last_actual` — computed within a single (meter, channel) lineage (BR-MET-058).
Worked example (GT-9 fixture, channel `total`): (44,182 − 42,864) × 1 = 1,318.000000; minus 618.000000 estimated → **700.000000 kWh** billed on the next bill = the actual 700 for the period, i.e. a +82 kWh correction vs the estimate, exactly GT-9 ("trailing-3 avg = 618 kWh billed; next cycle real read implies actual 700 → true-up +82"). Per-channel example: M-7450 tou_on (13,864 − 13,210) × 1 − 210.000000 = **444.000000 kWh**. Quantity only; pricing + rounding are rating/billing per B4.4. Ref: **GT-9** (code-side test flips `skip` → `xfail` until the engine lands).

**8 · Open Questions**
| OQ | Question | Blocks | Routed to | Status |
|---|---|---|---|---|
| OQ-003 *(existing — referenced, not duplicated)* | Estimation math + true-up mechanics | Nothing — closed | Product Owner (chat session) | CLOSED — defaults per B4 addendum, tenant-changeable via S64 settings (PO R6) |
| OQ-009 *(existing — referenced, not duplicated)* | Meter rollover handling at the register-wrap edge | Nothing — closed | Product Owner (chat session) | CLOSED — wrap auto-computed + flagged; other negatives = hard error (BR-MET-052); GT-14 rule CONFIRMED (PO R7) |

---
> Reconciled 2026-08-08 — Reads pre-session (BR-MET-049..060, B2 r8).
