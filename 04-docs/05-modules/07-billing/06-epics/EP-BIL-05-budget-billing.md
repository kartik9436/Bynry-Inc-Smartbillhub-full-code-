# EP-BIL-05 — Budget billing (level-pay)

**Module:** billing · **Wave:** W4 (needs 12-mo billed history + payment events for drop-off) · **Screens:** S30 (Budget Bills tab), S66 (budget parameter rows) · **Status:** BACKEND BUILT 2026-08-11 (BR-BIL-001..029 all CONFIRMED — session closed 2026-08-08; **BR-BIL-017's drop-off clause SUPERSEDED by the PO on 2026-08-11 and BR-BIL-072 added**). The S30 Budget Bills TAB has no endpoint and no screen — reported, not built

## Scope
**In:** budget billing per BR-BIL-017 + OQ-068 closure: plan flag (BR-RAT-043) + eligibility (12-mo history), level = trailing-12-month average rounded to whole $, variance balance shown on every bill, auto re-level at ±20% drift each 6 months, annual settle-up month (tenant-set), ~~off-budget after 2 missed payments~~ (**SUPERSEDED — PO 2026-08-11, "nodrop we chase for payments until write off"; there is no drop-off, and off-budget is only ever a staff action from S30**) — **every parameter a tenant setting with these as seeded defaults** — and the per-account level override (allowed, reason + audit, bounded ±30% of computed). Settle-up is a **non-taxable AR-timing line** — revenue and tax were already recognized on the monthly actuals; the level payment is a collection schedule, never a price (WE-8).
**Out:** the plan flag CRUD (rating, BR-RAT-043) · payment capture/missed-payment detection events (payments — consumed here) · the prototype's bulk-enroll knobs that conflict with the ratified parameters (24-mo averaging, 15% YoY cap — superseded by BR-BIL-017's tenant-setting set) · dunning consequences of off-budget (collections).
**Tables (B2 r10 #5):** `account_budget_status` (level, variance balance, last_leveled_at, settle_up_month, level_override + reason) + tenant budget settings.

## Capability matrix (list screens only — B9 conformance)
| Screen | Search fields | Filters | Default sort | Sortable | Columns default/available | Row actions | Bulk actions | Export |
|---|---|---|---|---|---|---|---|---|
| S30 · Budget Bills tab | account #, customer | status (enrolled/off-budget/pending-settle-up), drift band | variance desc | level, variance, last leveled | Account · Customer · Level $ · Variance balance · Last leveled · Settle-up month · Status / +override flag, drift % (IS-5) | Open account · Re-level · Override level · Remove from budget | Enroll selected · Re-level selected | CSV (IS-9) |

## Stories

---
id: US-BIL-018
epic: EP-BIL-05
module: billing
screens: [S30, S66]
wave: 4
status: draft
blocked_by: []
depends_on: [US-RAT-002, US-BIL-005, US-TEN-010]
journeys: [J2]
rules: [BR-BIL-017, BR-BIL-021]
golden_tests: []
finance_calc: confirmed
---
### US-BIL-018 — Enrollment, eligibility & the level computation

**1 · Details** — As a Billing Clerk, I want to enroll accounts on budget billing (S30 Budget Bills tab: eligible list, single or selected enrollment) where eligibility = **12 months of billing history** on plans carrying the budget flag (BR-RAT-043), and the level = **trailing-12-month actuals ÷ 12, rounded to whole dollars** — with every parameter (eligibility months, level rounding, re-level %+cadence, settle-up month, drop-off count) a tenant setting seeded with the BR-BIL-017 defaults — so that seasonal swings smooth into a predictable monthly amount without any hardcoded number. Enrollment writes `account_budget_status` (level, variance 0, settle-up month from tenant setting) and is audited; confirmation renders the level to the customer per the prototype step-2 table.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-017 | Level = trailing-12-month average (whole $); eligibility = 12-mo history; every parameter a tenant setting with these seeded defaults. | CONFIRMED — PO A-2, 2026-08-08 |
| BR-RAT-043 *(consumed)* | Budget billing rides the plan flag. | CONFIRMED — rating pack |
| BR-BIL-021 | Budget params live in tenant billing config, seeded, nothing hardcoded. | CONFIRMED — PO Lane B-2, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | ACC-1042: trailing-12 actuals total $2,904 | Eligible (12 mo history, plan flagged); computed level **$242** (2,904 ÷ 12, whole $ — WE-8); enrollment writes status row (level 242, variance 0.00, settle-up month = tenant setting), audited |
| TC-2 | Account with 9 months history | Listed ineligible with the reason ("9/12 months"); tenant lowers eligibility to 9 in settings → becomes eligible (config, not constant) |
| TC-3 | Bulk-enroll 3 selected eligible accounts | Three status rows; per-account levels each from their own trailing-12; confirmation list mirrors the prototype step-2 layout |
| TC-4 *(negative)* | Enroll attempted on a plan without the budget flag | Rejected — BR-RAT-043 flag required; message names the plan |
| TC-5 *(negative)* | Enroll attempted twice for the same account | Rejected — one active budget status per account |
| TC-6 *(isolation)* | Lone Star Ridge enrollment | Its params + histories only (RLS); Brazos Bend's settings never apply |

**4 · Test Data** — WE-8 verbatim: ACC-1042 trailing-12 = $2,904 → level **$242**. Ineligible fixture ACC-1350 (moved in Jul — 1 month). Bulk fixture: ACC-1042 / ACC-1091 / ACC-1130. Tenant settings (seeded defaults per BR-BIL-017): eligibility 12 mo · whole-$ rounding · re-level ±20% / 6 mo · settle-up month April (tenant-set fixture) · drop-off 2. Actors: Priya Menon. Isolation: Lone Star Ridge, eligibility tenant-set 9.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Eligibility check | S30 Budget tab | BR-BIL-017 | computed: months of billed history ≥ tenant `eligibility_months` + plan flag (BR-RAT-043 read) | int | computed-display | reason shown when ineligible |
| Level | S30 | BR-BIL-017 | `account_budget_status.level` (r10 #5) | numeric whole $ | system-derived | §7 formula; rounding per tenant setting |
| Variance balance (init 0) | S30 | BR-BIL-017 | `account_budget_status.variance_balance` | numeric(18,6) USD | system-derived | starts 0.00 |
| Settle-up month | S30/S66 | BR-BIL-017 | `account_budget_status.settle_up_month` ← tenant setting | int 1–12 | reference-data | tenant-set |
| Tenant budget settings | S66 | BR-BIL-017/021 | tenant budget settings rows (r10 #5): eligibility_months, rounding, relevel_pct, relevel_cadence_months, settle_up_month, dropoff_missed_count | numerics | reference-data | seeded defaults = BR-BIL-017 values |
| Enrollment audit | — | CLAUDE.md #7 | `audit_log` `budget.enrolled` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given 12 months of history on a flagged plan, Then enrollment computes the whole-$ level per §7 and writes the status row audited.
- Given tenant-changed parameters, Then eligibility and rounding follow the settings — no seeded value is hardcoded.
- Given an unflagged plan or a second enrollment, Then the action is rejected with a named reason.
- Given tenants, Then histories, params and levels never cross.

**7 · Finance Calculation** — CONFIRMED (BR-BIL-017; WE-8 verbatim): `level = round_to_whole_$(Σ trailing-12-month actuals ÷ 12)`. Worked: $2,904 ÷ 12 → **$242**. Ref: BS-9.

**8 · Open Questions** — None.

---
id: US-BIL-019
epic: EP-BIL-05
module: billing
screens: [S30]
wave: 4
status: draft
blocked_by: []
depends_on: [US-BIL-018, US-BIL-005]
journeys: [J2]
rules: [BR-BIL-017]
golden_tests: []
finance_calc: confirmed
---
### US-BIL-019 — The budget bill: actuals computed monthly, variance on every bill, settle-up month

**1 · Details** — As the system, I want every enrolled account's cycle bill computed as **full actuals** (all normal lines, GL stamps, tax — nothing about pricing changes) while the customer's **amount to pay = the level** — and, since the PO's ruling of 2026-08-11 (*"Level is due"*, OQ-140 CLOSED → BR-BIL-072), **that level IS what is DUE**: paying it settles the month IN FULL, so the account does not age, earns no late fee and never enters the collection ladder; in the settle-up month the level is due AND the balance moves it (worked: 242 − 2.98 = **239.02** on a credit, 242 + 40.27 = **282.27** on a collection) — with the bill showing three columns — actual, level, variance movement — and the **running variance balance on every bill** (BR-BIL-017); in the tenant's settle-up month the accumulated balance is collected/credited as a **non-taxable AR-timing line** (revenue and tax were already recognized on the monthly actuals; the level payment is a collection schedule, never a price — WE-8) — so that finance recognition is always exact and the customer experience is smooth.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-017 | Actuals computed every month; customer pays level; variance accumulates and is shown on every bill; annual settle-up month. | CONFIRMED — PO A-2, 2026-08-08 |
| BR-BIL-011 *(shared)* | The monthly posting is the ACTUALS posting (per-GL buckets as any bill); the level is presentation + collection scheduling — no revenue re-timing. | CONFIRMED — WE-8 note ("revenue and tax were already recognized on the monthly actuals") |
| B4.2 *(cited)* | The settle-up line is non-taxable (AR-timing, not a charge). | CONFIRMED — WE-8 |
| BR-BIL-072 | **THE LEVEL AMOUNT IS WHAT IS DUE.** Actual 292.87, level 242 → the customer owes 242 and paying it settles the month in full: no aging, no late fee, no collection ladder. The bill stays FULL ACTUALS and the posting stays the ACTUALS posting. **AMENDED 2026-08-12: the FINAL bill of an enrolled account is the LEVEL ONLY — 242.00, not 282.27 (*"Level only"*, OQ-164 CLOSED).** | CONFIRMED — PO 2026-08-11 (OQ-140 CLOSED); closes DEF-061 · **AMENDED PO 2026-08-12 (OQ-164)** |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | July bill, ACC-1042 (level 242): actual 292.87 | Bill renders actual **292.87** · level **242** · variance movement **−50.87**; running balance **−50.87**; amount to pay = 242; posting = the ACTUALS posting (WE-1 buckets) |
| TC-2 | Aug actual 231.40; Sep actual 198.75 | Variance movements **+10.60**, **+43.25**; running balance −50.87 → **−40.27** → **+2.98** — all three columns on each bill (WE-8) |
| TC-3 | Settle-up month arrives with balance +2.98 | Settle-up line **credits 2.98** (customer used less than paid), non-taxable, AR-timing GL treatment; balance resets 0.00; audited |
| TC-4 | Settle-up with a negative balance (fixture −40.27 case) | Settle-up line **collects 40.27** — same line class, opposite sign; still non-taxable |
| TC-5 *(negative)* | A settle-up line forged as taxable or into a revenue GL | Rejected — AR-timing class, non-taxable by construction (WE-8); tax was recognized monthly |
| TC-6 *(negative)* | Variance recomputed by editing the stored balance directly | Rejected — the balance derives from bill events append-only; corrections ride J6 |
| TC-1b | ACC-1042 pays exactly **242** on the due date against the 292.87 bill | **Settled IN FULL** — overdue portion **0.00**, late fee **0.00**, no aging bucket, no notice (PO 2026-08-11). The rejected reading is asserted beside it: measured against the ACTUAL the same customer is **50.87** overdue and earns **$5.00** |
| TC-8 *(RULED 2026-08-12 — was routed to OQ-164)* | A budget account reaches its FINAL bill (move-out) with level **242** and variance balance **−40.27** | Amount due **242.00** — **the LEVEL ONLY** (PO 2026-08-12, OQ-164 CLOSED, verbatim *"Level only"*). **Not 282.27**: the accumulated variance is settled through the settle-up, which is its own event and is never folded into the last level payment. The `NotImplementedError("OQ-164")` on `budget.amount_due` for `bill_type="final"` is retired. The rejected reading is asserted beside it, as TC-1b does — folding the variance in asks a leaving customer for **282.27** |
| TC-7 *(isolation)* | Lone Star Ridge budget bills | Own levels/balances only (RLS) |

**4 · Test Data** — WE-8 verbatim: level 242; Jul actual 292.87 → −50.87; Aug 231.40 → +10.60; Sep 198.75 → +43.25; running −50.87 → −40.27 → **+2.98**; settle-up (April, tenant-set) credits 2.98. Negative-settle fixture: balance −40.27 → collect 40.27. Isolation: Lone Star Ridge level $180 account.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Actual charges | S30 detail | BR-BIL-017 | normal `invoices`/`invoice_lines` (full pricing + GL + tax) | numeric(18,6) | system-derived | identical to non-budget pricing |
| Level presentation ("amount to pay") | bill document | BR-BIL-017 | template-rendered from `account_budget_status.level` | numeric $ | computed-display | shown with actual + variance |
| Variance movement + running balance | bill document / S30 tab | BR-BIL-017 | `account_budget_status.variance_balance` (+= level − actual each bill) | numeric(18,6) | system-derived | shown on every bill; append-only derivation |
| Settle-up line | S30 detail | BR-BIL-017 + WE-8 | `invoice_lines` — non-taxable AR-timing class (collect or credit) | numeric(18,6) | system-derived | in the tenant settle-up month only; resets balance |
| Settle-up audit | — | CLAUDE.md #7 | `audit_log` `budget.settled` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given the WE-8 sequence, Then each bill shows actual/level/variance exactly and the running balance reproduces −50.87 → −40.27 → +2.98.
- Given the settle-up month, Then the balance collects/credits as a non-taxable AR-timing line and resets — with monthly revenue/tax recognition untouched.
- Given posting, Then every month posts the ACTUALS buckets; the level never reaches the ledger as a price.
- Given a forged taxable settle-up or a direct balance edit, Then the write is rejected.

**7 · Finance Calculation** — CONFIRMED (WE-8, workbook verbatim). `variance_movement = level − actual`; `running_balance += movement`. Worked: level **242**; Jul 292.87 → **−50.87**; Aug 231.40 → **+10.60**; Sep 198.75 → **+43.25**; running **−50.87 → −40.27 → +2.98**. Settle-up: balance collected/credited as a **non-taxable AR-timing line** — never revenue, never taxed (recognition happened on the monthly actuals). Ref: BS-9.

**8 · Open Questions** — ~~**OQ-164 (OPEN)**: a budget account's FINAL bill — is the amount due the LEVEL (242.00) or the whole closing position including the accumulated variance (282.27)? Routed, not chosen; `budget.amount_due` raises on `bill_type="final"`.~~ **OQ-164 CLOSED 2026-08-12 (PO): *"Level only"* → the final bill is 242.00, not 282.27 (TC-8 above, BR-BIL-017/072 as amended).** ⚠ **One question REMAINS and it is not this one — OQ-142 (OPEN): which account the settle-up line touches.** On 2026-08-12 the PO challenged the premise (*"thats why we have true up every 6 month of 12 months - until then what ever is billed that is what accouting keep counting - is there a gap in my understanding?"*) and the answer is TAX: the customer CONSUMES **$292.87** in July and is ASKED for **$242.00**, and a state taxes what was consumed, so recognising revenue on the level would under-remit every month on every budget customer. The fork — keep revenue on actuals and add one holding account (needs a finance re-sign), or move revenue to the level and need none — is the PO's; recommendation on record is **keep actuals**. The settle-up's GL side stays stubbed on OQ-142 until it is ruled.

---
id: US-BIL-020
epic: EP-BIL-05
module: billing
screens: [S30, S66]
wave: 4
status: draft
blocked_by: []
depends_on: [US-BIL-018, US-CUS-012]
journeys: [J2]
rules: [BR-BIL-017]
golden_tests: []
finance_calc: confirmed
---
### US-BIL-020 — Re-level at drift, ~~off-budget after missed payments~~, per-account override ±30%

> ⚠ **THE OFF-BUDGET HALF OF THIS STORY IS SUPERSEDED (PO ruling 2026-08-11, OQ-141 CLOSED).** Verbatim: *"nodrop we chase for payments until write off"*. There is no drop-off event and no missed-payment definition — that question became MOOT rather than answered. What remains is the re-level, the override, and a STAFF removal from S30 that carries the variance balance forward. TC-5 below is superseded and its replacement is stated in its own row.

**1 · Details** — As a Billing Clerk, I want the maintenance rules to run themselves and stay overridable: **auto re-level** when the recomputed level drifts ±20% from the current one, evaluated each 6 months (both tenant settings); ~~**off-budget** after 2 missed level payments (tenant setting; payments events consumed)~~ — **SUPERSEDED (PO 2026-08-11): nobody is dropped off.** The only way off is the S30 **Remove from budget** row action, a staff decision with a reason and an audit row, after which the account returns to plain actuals billing with its variance balance carried into the next bill (never silently dropped); and a **per-account level override** — staff may set a level different from the computed one WITH a reason, audited, bounded to ±30% of the computed level (OQ-068 closed) — so that the program self-maintains without trapping anyone (BR-BIL-017, r1.6).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-BIL-017 | Auto re-level at ±20% drift each 6 mo; ~~off-budget after 2 missed payments~~ — every parameter a tenant setting with these seeded defaults. | CONFIRMED — PO A-2, 2026-08-08; **drop-off clause SUPERSEDED — PO 2026-08-11** |
| BR-BIL-017 (override) | Per-account level override: allowed with reason + audit, bounded ±30% of computed. | CONFIRMED — OQ-068 closed (PO F-round) |
| ~~BR-CUS-055 pattern *(consumed)*~~ | ~~Missed-payment events come from payments; billing consumes, never detects payment state itself.~~ | **MOOT — PO 2026-08-11.** No missed-payment event is consumed, because there is nothing for one to trigger. Payments was never asked to emit it and now never will be |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | 6-month evaluation: recomputed level within ±20% of 242 | No change; `last_leveled_at` updated; evaluation audited |
| TC-2 | Recomputed level breaches the +20% drift band | Auto re-level to the new whole-$ computed level; customer-visible on the next bill; audited with old/new |
| TC-3 | Override: computed 242, staff sets 200 with reason "customer hardship request" | Accepted — within ±30% of computed (bounds 169.40–314.60 = 242 × 0.70 / × 1.30); `level_override` + reason stored; audit row |
| TC-4 *(negative)* | Override to 150 (below 169.40) or 320 (above 314.60); or override without a reason | Rejected — outside the ±30% bound / reason required (OQ-068) |
| ~~TC-5~~ | ~~Second missed level payment (payments event)~~ | **SUPERSEDED (PO 2026-08-11).** The account stays ENROLLED at the second miss and at the tenth; collections chases it to write-off. Asserted as the replacement in `test_us_bil_020_tc5`, which also proves no miss counter and no drop-off API exists |
| TC-5b | Staff use S30 **Remove from budget** with a reason | Status → off_budget, audited with the reason AND the carried variance balance (−40.27 is not cleared); the next bill is plain actuals |
| TC-6 *(negative)* | Re-level attempted mid-cadence by a forged job call | No-op — cadence gate (tenant `relevel_cadence_months`) enforced server-side; manual "Re-level" row action allowed with audit |
| TC-7 *(isolation)* | Lone Star Ridge overrides/drop-offs | Own settings + status rows only (RLS) |

**4 · Test Data** — Computed level 242 (WE-8). Override fixture: 200, reason "customer hardship request", bounds 169.40–314.60 (±30% of 242 — derived bound arithmetic on the OQ-068 rule). Drift fixtures: recomputed 250 (within band, no change); recomputed 300 (breach → re-level). Missed payments: ACC-1130 misses May + Jun level payments → off-budget Jul; carried variance −40.27 appears on the Jul actuals bill. Settings: ±20% / 6 mo / drop-off 2 (seeded); Lone Star Ridge drop-off 3. Actors: Priya Menon (override w/ reason), system job (re-level/drop-off).

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Re-level evaluation | system job + S30 row action | BR-BIL-017 | `account_budget_status.level` + `last_leveled_at` (r10 #5) | numeric $ / ts | system-derived | drift > tenant `relevel_pct`, each `relevel_cadence_months` |
| Level override + reason | S30 row action | OQ-068 | `account_budget_status.level_override` + reason (r10 #5) | numeric $ + text | user-input | within ±30% of computed; reason required; audited |
| Off-budget transition | system (payments event) | BR-BIL-017 | `account_budget_status` status → off_budget after tenant `dropoff_missed_count` | enum | system-derived | payments emits the missed events (B1) |
| Carried variance at drop-off | next bill | BR-BIL-017 | variance balance carried into the next actuals bill | numeric(18,6) | system-derived | never silently dropped |
| Maintenance audit | — | CLAUDE.md #7 | `audit_log` `budget.releveled/overridden/dropped` | jsonb | system-derived | old/new + reason |

**6 · Acceptance**
- Given the cadence + drift settings, Then re-levels fire only at cadence on breach, audited old→new.
- Given an override, Then it requires a reason, respects the ±30% bound, and is audited; out-of-bound or reason-less attempts fail.
- Given the tenant missed-payment count, Then off-budget transitions exactly then, carrying the variance balance forward visibly.
- Given tenants, Then all parameters evaluate per-tenant.

**7 · Finance Calculation** — CONFIRMED (BR-BIL-017 + OQ-068). Re-level trigger: `|recomputed − current| ÷ current > 20%` (tenant %), evaluated each 6 months (tenant cadence); new level per the US-BIL-018 formula (WE-8 base: 2,904 ÷ 12 → 242). Override bound: `override ∈ [computed × 0.70, computed × 1.30]` — worked on computed 242: **169.40 – 314.60** (bound arithmetic derived from the OQ-068 ±30% rule; the 242 itself is WE-8's figure). Ref: BS-9.

**8 · Open Questions** — None for the re-level and override. The drop-off clause is SUPERSEDED (OQ-141 CLOSED, MOOT).
