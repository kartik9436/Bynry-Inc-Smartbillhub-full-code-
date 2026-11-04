# EP-CUS-05 — Change Plan wizard

**Module:** customers (product name: Accounts) · **Wave:** W8 · **Screens:** S23 · **Status:** draft

## Scope
**In:** the S23 three-step guided page — 1 Pick new plan (compatible published plans for the unit's services) → 2 Effective date & proration preview (immediate / next cycle / custom; B4.3 CONFIRMED calendar-day proration of base + usage; ~~deposit differential per the OQ-011 closure~~ — **NO deposit differential: PO 2026-08-12, OQ-179, *"we dont have to give depoiste back in between it will be settled only at the time of closure"***) → 3 Confirm & notify (before/after summary, plan-change email, eligibility-proof logging). On confirm the change writes a new `unit_plan_assignments` row (source `change_plan`), effective-dated, and closes the previous row the day before it starts; issued bills untouched. **AMENDED 2026-08-11 (PO ruling):** BR-CUS-014 sc.3's "syncs unit and account" no longer means two rows. There is no account-side plan record — *"from unit you will derive the plan"* — so unit and account cannot diverge because the plan exists in exactly one place. Reprint fidelity comes from the bill's own locked-at-issue snapshot.
**Out:** the unit-side correction override (metering PU-12/BR-MET-042 — warning, NO proration, next unbilled period) · rebilling/credit notes for already-issued bills (J6, billing) · plan catalog content (rating) · deposit collection/refund execution (payments) — **and, since the PO's 2026-08-12 ruling (OQ-179), the deposit ENTIRELY: a plan change moves no deposit money, so this wizard neither computes, quotes nor registers a deposit figure. The deposit settles once, at closure, against everything outstanding (OQ-158, same day).**

## Capability matrix (list screens only — B9 conformance)
No list screens — guided full page; step-1 plan table is a wizard-scoped picker.

## Stories

---
id: US-CUS-016
epic: EP-CUS-05
module: customers
screens: [S23]
wave: 8
status: draft
blocked_by: []
depends_on: [US-CUS-006, US-CUS-008, US-RAT-012]
journeys: [J2]
rules: [BR-CUS-041, BR-CUS-042, BR-RAT-030, BR-RAT-043]
golden_tests: [GT-3]
finance_calc: confirmed
---
### US-CUS-016 — Pick plan, effective date & proration preview (steps 1–2)

⚠ **THE DEPOSIT HALF OF THIS STORY IS GONE (PO ruling 2026-08-12, OQ-179 CLOSED).** Verbatim: *"we dont have to give depoiste back in between it will be settled only at the time of closure"*. **There is no mid-plan deposit differential at all** — the ruling did not pick between BR-CUS-042 and BR-CUS-062, it **removed the question**: a plan change **moves no deposit money**, and the deposit settles ONCE, against everything outstanding, at CLOSURE. **Neither −$18.50 nor −$68.50 is ever shown to a customer** (decision log, 2026-08-12, verbatim). Every deposit line below is struck or stamped rather than deleted so the change is legible. ⚠ **FLAGGED, NOT CHOSEN:** **−$18.50 is the BASE delta** (RES-STD **$30.50** → Senior **$12.00**), not a deposit figure, and −$68.50 was the deposit-inclusive net; the ruling's sentence bans both. **Whether §7 may still state a base-only net impact is reported to the PO, not decided here.**

**1 · Details** — As a Billing Clerk, I want step 1 to list only plans compatible with the unit's services (current plan shown for contrast; per-row notes like "Drops water service" / "Requires CAP proof") and step 2 to set the effective date (Immediately / Next cycle start / Custom) with a **proration preview** — current-plan period line, new-plan line, ~~deposit differential~~ **(no deposit line — PO 2026-08-12)**, "Net impact next bill" — so that the customer hears the exact consequence before anything changes. Entry: S21 **Change plan**. Exit: Continue → step 3 (US-CUS-017); Cancel → S21 unchanged. Preview math comes from the rating engine via service function (US-RAT-012) — this story computes nothing itself and WRITES NOTHING.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-041 | Mid-tenancy plan change is account-initiated (S23); mid-cycle changes prorate by calendar days, base + usage both (B4.3); effective-date options immediate / next-cycle / custom; only PUBLISHED plans whose services ⊆ unit services are offered (BR-RAT-030); service-dropping changes surface an explicit warning. | CONFIRMED (proration — B4.3/GT-3) / option set + compatibility PROPOSED (prototype S23) |
| BR-CUS-042 | ~~Deposit differential on plan change = new plan's category amount − old plan's category amount from `plan_deposit_rules` (fixed $, category-driven); positive → billed, negative → credited/refunded.~~ ⚠ **SUPERSEDED PO 2026-08-12 (OQ-179): there is NO mid-plan deposit differential — the deposit settles only at CLOSURE, against everything outstanding.** The S23 preview states no deposit figure and the confirm registers no deposit instruction. | **SUPERSEDED — PO 2026-08-12** (was CONFIRMED — OQ-011 closure) |
| BR-CUS-062 | Deposit differential on plan change: **NO recompute** — the deposit set at move-in stands until settlement. The *"category-differential recompute = v1.1"* clause is **SUPERSEDED by the same 2026-08-12 sentence**: the recompute is not deferred, it is gone. | CONFIRMED (first half) — PO CL-5 (b), 2026-08-08 · **v1.1 clause SUPERSEDED PO 2026-08-12** |
| BR-RAT-030 | *(cited)* drafts never assignable; archived plans keep serving existing accounts but are not offered. | CONFIRMED (enum) / semantics PROPOSED — rating |
| BR-RAT-043 | *(cited)* eligibility (e.g. "Requires CAP proof") is advisory-with-audit in v1 — the wizard shows the note and logs the proof checkbox (step 3); no hard enforcement. | CONFIRMED — OQ-055 closure |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Marcus opens Change plan on A-10432 (RES-STD, E+W unit) | Step 1 lists Residential Electric-only ($18.50, note "Drops water service"), Senior / Low-income ($12.00, "Requires CAP proof"), Budget Billing (level-pay, $30.50) — all published, service-compatible; current plan named in the header copy |
| TC-2 | Senior selected; effective Next cycle start (Sep 1) | Step-2 preview: current plan Aug 1→Aug 31 $30.50 base; new plan effective Sep 1 $12.00 base; ~~deposit differential −$50.00 refund; Net impact next bill −$68.50~~ ⚠ **AMENDED PO 2026-08-12 (OQ-179): NO deposit line and no deposit-inclusive net — a plan change moves no deposit money, and neither −$18.50 nor −$68.50 is shown to the customer. The RES-STD $150.00 → Senior $100.00 deposit stands untouched until closure** |
| TC-2b *(PO 2026-08-12, OQ-179)* | The clerk looks for the deposit refund the old preview promised | There is none to find, at any effective date: the deposit is settled **once, at closure, against everything outstanding** (OQ-158, same day). `preview_plan_change` returning `deposit_differential: null` and `change_plan` reporting `deposit_differential_not_registered` are now **the rule**, not a parked stub |
| TC-3 | Effective Immediately (Aug 6) | Preview shows split-cycle proration: old base 5/31 × 30.50 + new base 26/31 × 12.00 and day-split usage (engine-computed); net impact recomputes |
| TC-4 | Custom date in the past, before the last issued bill's period end | Blocked: issued bills untouched (BR-CUS-014 sc.4 routes money corrections to J6); earliest allowed = start of the current unbilled period |
| TC-5 *(negative)* | Draft plan (Vacant / Standby) forged into the request | Rejected — published-only (BR-RAT-030); nothing previewed or written |
| TC-6 *(negative)* | Electric-only chosen for an E+W unit | Warning "Drops water service" requires explicit acknowledgment before Continue; no silent service loss |
| TC-7 *(isolation)* | J. Okafor's step-1 list | Lone Star Ridge plans only (RLS) |

**4 · Test Data** — A-10432 on RES-STD v3 ($30.50 = 18.50 E + 12.00 W); target Senior / Low-income ($12.00 base; residential deposit $100.00 vs RES-STD residential $150.00 → ~~differential −$50.00~~ **the two deposit amounts are fixture facts only — no differential is computed, quoted or billed (PO 2026-08-12, OQ-179); the deposit on file stays at its move-in amount until closure**); Budget Billing plan flagged budget per BR-RAT-043. Today Aug 6, 2026; cycle Aug 1–31 (31 days); next cycle start Sep 1, 2026. Actors: Marcus Vega; isolation J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Plan picker rows | S23 step 1 | prototype-extracted | `rate_plans` published + `plan_services` ⊆ unit services (⚠ rating read) | reference | user-input | BR-RAT-030; compatibility |
| Compatibility notes | S23 step 1 | prototype-extracted ("Drops water service" / "Requires CAP proof") | derived from plan_services diff + plan eligibility flags (BR-RAT-043) | text | computed-display | advisory |
| Effective date | S23 step 2 | prototype-extracted (3 options) | drives new assignment rows' `assigned_from` (written in US-CUS-017) | date | user-input | ≥ current unbilled period start |
| Proration preview lines | S23 step 2 | prototype-extracted | computed via rating engine service (US-RAT-012) — no write | numeric USD | computed-display | B4.3 |
| ~~Deposit differential line~~ | ~~S23 step 2~~ | ~~prototype-extracted ("–$50 refund (deposits reduce)")~~ | ~~`plan_deposit_rules` lookup diff~~ ⚠ **REMOVED — PO 2026-08-12 (OQ-179): the preview states NO deposit figure. The prototype's "–$50 refund (deposits reduce)" copy is superseded and must not be built** | — | — | **the deposit settles only at closure, against everything outstanding** |
| Net impact next bill | S23 step 2 | prototype-extracted | Σ preview lines — **the deposit line is no longer one of them (PO 2026-08-12)** | numeric USD | computed-display | display 2dp. ⚠ **FLAGGED, NOT CHOSEN: the ruling's sentence bans both −$68.50 and −$18.50, and −$18.50 is the BASE delta; whether a base-only net may still be stated is reported to the PO** |

**6 · Acceptance**
- Given an E+W unit, Then only compatible published plans list, with service-drop and eligibility notes.
- Given the §4 fixture and Sep 1 effective, Then the preview reproduces §7 exactly.
- Given any past date inside a billed period, Then the wizard blocks and points to the correction path (J6).

**7 · Finance Calculation** — CONFIRMED (B4.3 calendar days, base + usage; GT-3 rule): for effective date d in an N-day cycle, `old_base_share = days_old/N × old_base`, `new_base_share = days_new/N × new_base`; usage split on the same day basis and priced per each plan's schedule (engine). ~~Deposit differential (BR-CUS-042): `Δdeposit = deposit[new_plan, category] − deposit[old_plan, category]`.~~ ⚠ **SUPERSEDED PO 2026-08-12 (OQ-179) — there is no Δdeposit term in this calculation at any effective date.** ~~Worked example (§4, next-cycle effective — no mid-cycle split): Aug bill base $30.50 (old plan, full month); Sep onward base $12.00; base delta next bill = 12.00 − 30.50 = −18.50; Δdeposit = 100.00 − 150.00 = **−50.00** refund → net impact next bill −18.50 − 50.00 = **−$68.50** ✓ prototype.~~ **The −$50.00 refund is not computed, not quoted and not billed, and the customer is told nothing about their deposit at a plan change — it settles at closure (OQ-158, same day). ⚠ FLAGGED, NOT CHOSEN: the decision log's sentence bans BOTH −$68.50 AND −$18.50; −$18.50 is the base delta (12.00 − 30.50), a B4.3 proration figure this ruling never touched. Whether a base-only net impact may still be stated is reported to the PO rather than decided by this lane.** Immediate-effective example (TC-3, base proration only, unaffected by the deposit ruling): old base 5/31 × 30.50 = 4.9193… → **4.92**; new base 26/31 × 12.00 = 10.0645… → **10.06** (2dp half-up at finalization, B4.4). GT ref: GT-3.

**8 · Open Questions** — **OQ-179 — CLOSED 2026-08-12.** The PO ruled *"we dont have to give depoiste back in between it will be settled only at the time of closure"*: **there is no mid-plan deposit differential at all.** Two CONFIRMED rules had disagreed about one customer-facing figure — BR-CUS-042 (compute it) against BR-CUS-062 (do not, until v1.1) — and the ruling **removed the question** rather than choosing: a plan change moves no deposit money, both differential clauses are SUPERSEDED, and the deposit is settled once, at closure, against everything outstanding. ORIGINALLY this section read *"None (deposit differential settled by the OQ-011 closure)"*, which was the contradiction hiding in plain sight. Tier-boundary scaling for prorated periods remains CONFIRMED in B4.4 via the tiered note. ⚠ **ONE THING REPORTED, NOT DECIDED:** the ruling's recorded sentence bans **−$18.50** as well as −$68.50, and −$18.50 is the **base** delta rather than a deposit figure — the base-only net impact is therefore left to the PO rather than resolved here.

---
id: US-CUS-017
epic: EP-CUS-05
module: customers
screens: [S23]
wave: 8
status: draft
blocked_by: []
depends_on: [US-CUS-016]
journeys: [J2]
rules: [BR-CUS-011, BR-CUS-013, BR-CUS-014, BR-CUS-029, BR-CUS-042]
golden_tests: []
finance_calc: none
---
### US-CUS-017 — Confirm, sync unit + account & notify (step 3)

**1 · Details** — As a Billing Clerk, I want step 3 to show the From/To plans, effective date and net impact, capture the notification election (plan-change confirmation email per A19: before/after table, base delta, estimated impact, ~~deposit change~~ **— the deposit-change line is REMOVED, PO 2026-08-12** — "did not request this?" line) and the eligibility-proof log checkbox, and on **Change plan ✓** atomically: (a) append the `unit_plan_assignments` row (source `change_plan`, actor, reason, effective date), ~~(b) append the account snapshot row (new plan + current version — BR-CUS-013)~~ — **DROPPED 2026-08-11 (PO ruling): no account-side plan record.** The version snapshot BR-CUS-013 asks for lives on the unit row, which now carries `plan_version` frozen at assignment, ~~(c) register the deposit-differential instruction (bill or credit/refund via billing/payments)~~ — **DROPPED 2026-08-12 (PO ruling, OQ-179): there is NO deposit instruction to register. A plan change moves no deposit money; the deposit settles only at closure**, (d) queue the notification, (e) write audit — so that unit and account never diverge (BR-CUS-014 sc.3) and the customer is told. Exit: toast "Plan changed · effective Sep 1 · customer notified" → S21.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-014 sc.3 | Mid-tenancy changes go through Change-plan (proration) and sync BOTH unit and account. | CONFIRMED — PO PU-9 sc.3 |
| BR-CUS-011 | History rows carry who/when/from→to/reason/source (`change_plan`). | CONFIRMED — PO Q&A R1 (D10) |
| BR-CUS-013 | The new snapshot pins the plan's CURRENT version; later catalog edits never touch it. | CONFIRMED — D10 |
| BR-CUS-029 | *(shared)* account snapshot row in `account_plan_assignments` (PROPOSED-SCHEMA), append-only. — **SUPERSEDED 2026-08-11 (Product Owner): there is NO account-side plan record.** Verbatim: *"from unit you will derive the plan, you will also need to maintain attributes that are important at account level - A"*. The plan lives once, on the unit (`units.rate_plan_id`), and the account DERIVES it; a bill reprinted years later resolves its prices from that bill's own locked-at-issue snapshot, not from a live assignment row. A second live plan record would buy nothing and could disagree with the first. What the account DOES maintain is its own attributes — deposit_on_file · deposit_received_on · credit_tier · autopay · tax_exempt (+ref, +expiry) · bad_address · nsf_count · preferred_language · type/subtype · status · currency · balance — all of which already exist as columns. | **SUPERSEDED (PO 2026-08-11)** |
| BR-CUS-042 | ~~*(shared)* the differential instruction posts through billing (bill) or as credit/refund (payments) — customers writes neither table.~~ ⚠ **SUPERSEDED PO 2026-08-12 (OQ-179): there is no differential and therefore no instruction to route.** The deposit settles only at closure, against everything outstanding. | **SUPERSEDED — PO 2026-08-12** |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Confirm the §4 change (Senior, Sep 1, email on, CAP proof logged) | One transaction: unit_plan_assignments row {Senior, current version, from Sep 1, source change_plan, actor Marcus, prior row closed **Aug 31**} + ~~differential instruction −$50.00 (credit/refund path)~~ **NO differential instruction — PO 2026-08-12 (OQ-179); the deposit is untouched by a plan change** + notification queued + `audit_log` `plan.changed`; toast. **AMENDED 2026-08-11 (PO): the `account_plan_assignments` row is REMOVED from this expectation** — the plan lives once, on the unit, and the account derives it. The unit row is now genuinely WRITTEN (`apps/rating/services.record_unit_plan_assignment`); until 2026-08-11 it never was, because the history table's FK wanted a plan while the unit held a tariff, so this TC could not have passed as written. Covered by `tests/test_us_met_003_plan_history.py` TC-1/TC-2 (row written · prior row closed the day before). |
| TC-2 | Sep billing run (later, billing W3) | Prices Aug service dates from the OLD snapshot, Sep from the NEW (BR-CUS-014 sc.6) — asserted via the rating service contract |
| TC-3 | Eligibility checkbox "Log CAP eligibility proof (uploaded Jul 2026)" | Audit row links the S21 Documents entry (advisory-with-audit, BR-RAT-043); absence does NOT block v1 |
| TC-4 | Notification election off | No email; change still audited; toast omits "customer notified" |
| TC-5 *(negative)* | Concurrent second Change-plan confirm on the same account (double submit) | Second attempt rejected on the effective-dated append (overlapping current row); single history row survives |
| TC-6 *(negative)* | Direct UPDATE attempt on the prior assignment row | Rejected — append-only (r5 #13 / BR-CUS-029) |
| TC-7 *(isolation)* | Lone Star Ridge session confirms a change | Rows carry its tenant_id; Brazos Bend histories untouched (RLS) |

**4 · Test Data** — The US-CUS-016 §4 fixture (A-10432, RES-STD v3 → Senior current v1, effective Sep 1 2026, ~~differential −$50.00~~ **no deposit differential — PO 2026-08-12 (OQ-179)**, reason "customer qualified — CAP"). Notification: A19 plan-change email ("Your rate plan has changed — effective Sep 1"). Actors: Marcus Vega; isolation J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| From/To summary | S23 step 3 | prototype-extracted | display of the pending change | text | computed-display | — |
| Unit assignment row | — | B2 r5 #13 | `unit_plan_assignments` (source change_plan, actor, reason) — ⚠ cross-module WRITE via the plan-assignment service owned with metering; the reviewed interface (B2 §2) is the write path BR-CUS-010 established at move-in | uuid+int+dates | system-derived | append-only |
| ~~Account snapshot row~~ | — | BR-CUS-014 sc.1/3 | ~~**PROPOSED-SCHEMA** `account_plan_assignments`~~ — **DROPPED 2026-08-11 (PO ruling)**: no account-side plan record is built. The account reads the plan through `units.rate_plan_id`; reprint fidelity comes from the bill's locked-at-issue snapshot. | — | — | — |
| ~~Deposit differential instruction~~ | ~~S23 step 3 (from step-2 preview)~~ | ~~OQ-011 closure~~ ⚠ **REMOVED — PO 2026-08-12 (OQ-179)** | ~~billing line (positive) / credit-refund (negative)~~ **nothing is registered; `change_plan` reporting `deposit_differential_not_registered` is now the RULE, not a parked stub** | — | — | **the deposit settles only at closure (OQ-158)** |
| Notification election + eligibility log | S23 step 3 | prototype-extracted (2 checkboxes) | notification queue (A19 plan-change email) + audit link to `account_documents` | boolean | user-input | BR-RAT-043 advisory |
| Audit | — | CLAUDE.md #7 | `audit_log` `plan.changed` (from→to, dates, ~~differential~~ — **no differential field: PO 2026-08-12**) | jsonb | system-derived | every money action |

**6 · Acceptance**
- Given confirm, Then unit and account histories both gain matching effective-dated rows in one transaction, ~~the differential routes to the right module~~ **no deposit money moves and no deposit line is quoted (PO 2026-08-12, OQ-179)**, And the customer email queues when elected.
- Given any billed period, Then no existing bill changes (corrections remain J6's).
- Given a double submit, Then exactly one change lands.

**7 · Finance Calculation** — N/A (amounts were fixed in US-CUS-016's preview; this story persists instructions). **And one fewer instruction since 2026-08-12: the −$50.00 deposit differential is neither computed nor persisted (PO, OQ-179).**

**8 · Open Questions** — None.
