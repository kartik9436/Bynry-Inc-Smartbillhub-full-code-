# EP-CUS-06 — Payment Plan wizard

**Module:** customers (product name: Accounts) · **Wave:** W4 · **Screens:** S24 · **Status:** BACKEND BUILT 2026-08-11 (the wizard's maths, rules and handoffs; ❄️ GT-47 reproduced). **The plan ROWS are payments-owned (`payment_plans`, EP-PAY-05) and do not exist, so `send_agreement` REFUSES rather than reporting a plan it did not create.** S24 itself is not built

## Scope
**In:** the S24 three-step guided page — 1 Amount & term (balance to spread, optional down payment, installments, cadence, first date, auto-charge / suspend-late-fees / suspend-disconnect toggles) → 2 Editable installment schedule (per-row date + amount, running remaining) → 3 Agreement (summary, e-sign / SMS / print elections, **Send agreement ✓**) — the account-side flow. The plan + installment ROWS live in payments-owned tables (`payment_plans`, `payment_plan_installments`, B2); this wizard calls the payments service (B1). The agreement document renders from the S67 payment-plan contract template (A19 §3, BR-NOT-004 type ①) and goes out for e-signature (DocuSign seam, B7); the plan activates ONLY on signature (A5/A6), at which point dunning + disconnect pause while current — **over the ARREARS this plan spreads and nothing else (PO ruling 2026-08-11, OQ-138 CLOSED → BR-BIL-073: the current month's bill is due every month and is chased normally; worked, PE-13: instalment 36.22 + October's 184.20 = the customer owes 220.42)**. **And nobody is dropped off (PO ruling 2026-08-11, OQ-141 CLOSED): the `defaulted` state and the template's {missed_count} default clause are SUPERSEDED — a missed instalment is chased, never a void.**
**Out:** installment auto-charging execution (payments/integrations; OQ-059 scope applies to drafting) · write-offs (payments S34/S35) · the S34 bulk "Payment plan" entry (same wizard, payments-owned entry point) · template design (S67, notifications).

## Capability matrix (list screens only — B9 conformance)
No list screens — guided full page; the step-2 schedule is an editable form table.

## Stories

---
id: US-CUS-018
epic: EP-CUS-06
module: customers
screens: [S24]
wave: 4
status: draft
blocked_by: []
depends_on: [US-CUS-008, US-CUS-010]
journeys: [J4]
rules: [BR-CUS-037, BR-CUS-043, BR-CUS-044]
golden_tests: []
finance_calc: confirmed
---
### US-CUS-018 — Payment Plan wizard (amount & term → editable schedule → agreement & activation)

**1 · Details** — As a Billing Clerk, I want to spread an account's balance over installments: step 1 captures balance-to-spread (defaults to current balance), optional down payment, number of installments, cadence (Monthly-with-bill / Bi-weekly / Weekly), first installment date, and the three toggles (auto-charge from method on file · suspend late fees while active · suspend disconnect while active — defaults per prototype: auto-charge ON, late-fee suspend OFF, disconnect suspend ON); step 2 shows the generated schedule (# · due date · installment · remaining · note) with per-row edits that must re-sum to the total; step 3 summarizes (total spread, installments, auto-charge method, "Effective on sign: dunning + disconnect paused") and sends the agreement (email e-sign / SMS link / print for counter signature). Entry: S21 **Payment plan** (payments' S34 bulk uses the same wizard). Exit: **Send agreement ✓** → plan status `proposed → agreement_sent`; **the step-3 summary states "the current bill is still due every month" on its face (PO 2026-08-11) rather than leaving a clerk to infer it, because believing otherwise IS the defect**; toast "Payment plan agreement sent · 4 installments"; **activation on customer signature** → Active, dunning/disconnect paused (J4 step-3 handoff: dunning paused). This story owns the wizard + handoffs; payments owns the rows; notifications owns the document.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-043 | Schedule math: installment = balance_to_spread (less down payment) ÷ n, rounded 2dp half-up per installment (B4.4), remainder absorbed on the FINAL installment (A7 EXPLICIT "balance ÷ installments, remainder on final"); manual step-2 edits allowed but Σ installments (+ down payment) must equal the total exactly; while the plan is ACTIVE and CURRENT, dunning and disconnect are paused (A7/A19 §3); late-fee suspension is a per-plan election. | PROPOSED — A7 (EXPLICIT) + A19 §3 + B4.4 rounding; not yet finance-signed |
| BR-CUS-044 | Agreement & lifecycle: document renders from the tenant's S67 payment-plan contract template (content per A19 §3: terms, schedule table, autopay-from-{payment_method}, default clause "plan voids on {missed_count} missed → full balance due; fees resume"); e-sign via the DocuSign seam (B7); plan states proposed → agreement_sent → active(on sign) → closed(final installment) per A5, plus PROPOSED `defaulted` (A5's UNKNOWN broken-plan status) entered per the template's default clause; {missed_count} is template/tenant configuration, default 2. | PROPOSED — A19 §3 + A5 + BR-NOT-004 (broken-plan status + missed_count default are PROPOSED pending PO) |
| BR-CUS-037 | *(shared)* wizard → payments service for `payment_plans` + `payment_plan_installments`; customers writes neither. | PROPOSED — B1 + B2 ownership |
| BR-BIL-073 | **A PLAN DOES NOT SUSPEND THE CURRENT BILL — both are due every month.** Instalment 36.22 + October's bill 184.20 = **220.42** owed in October. The pause covers the arrears the plan spreads; the current bill is chased, late fee included. | CONFIRMED — PO 2026-08-11 (OQ-138 CLOSED); closes DEF-060 |
| BR-CUS-044 (default clause) | ~~plan voids on {missed_count} missed~~ | **SUPERSEDED — PO 2026-08-11 (OQ-141 CLOSED), "nodrop we chase for payments until write off"** |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | Marcus spreads A-10432's $247.30 over 4 monthly installments from Sep 1 2026, auto-charge ACH, disconnect-suspend on | Schedule 61.83 / 61.83 / 61.83 / 61.81 (§7), remaining column 185.47 / 123.64 / 61.81 / 0.00; notes "Bundled with Sep…Nov bill", final "plan closes"; Send → plan row (payments) status agreement_sent; toast; audit `payment_plan.proposed` |
| TC-2 | Customer signs the e-sign envelope | Plan → Active; dunning + disconnect paused while current (J4 handoff); autopay enrollment for installments per election; audit `payment_plan.activated` |
| TC-3 | Step-2 edit: installment 1 raised to $100.00 | Remaining recomputes; system rebalances or flags until Σ = 247.30 exactly; final row absorbs the remainder |
| TC-4 | Down payment $47.30, 4 installments | Spread = 200.00 → 4 × 50.00 exactly; down payment due immediately via US-CUS-012 flow |
| TC-5 *(negative)* | Step-2 edits summing to 240.00 (< total) | Continue blocked: "schedule must equal the total to spread" (BR-CUS-043); nothing sent |
| TC-6 *(negative)* | Installments = 0, or balance-to-spread > current balance | Inline errors; confirm disabled |
| TC-7 *(negative)* | Second concurrent plan proposed while one is agreement_sent/Active | Blocked — one live plan per account (A3: "usually 1 active" → enforced as exactly one live, PROPOSED); message links the existing plan |
| TC-1b | A customer on the PE-13 plan receives October's **$184.20** cycle bill | They owe **$220.42** — the $36.22 instalment AND the current bill. Not $36.22: the pause covers the ARREARS only (PO 2026-08-11). The current bill's late fee is billing's own, threshold included |
| TC-9 | The customer misses two instalments, then ten | **The plan stays ACTIVE at both.** No `defaulted`, no void, no full-balance acceleration — collections chases to write-off (PO 2026-08-11). Asserted as an absence: no `defaulted` in the state set, no {missed_count} threshold |
| TC-10 | A partial payment arrives against a month carrying both an instalment (**$36.22**) and a current bill (**$184.20**) | ~~`NotImplementedError("OQ-139")`~~ ⚠ **CLOSED PO 2026-08-12 (*"plan first"*): the payment reaches THE PLAN FIRST — a NAMED EXCEPTION to oldest-invoice-first (BR-PAY-010), scoped to instalment payments only. Short of the instalment, NOTHING reaches the current bill, so a part-paid instalment is still a missed one and the dunning pause lifts the next day (OQ-170)** |
| TC-11 *(PO 2026-08-12, OQ-170)* | The 1 Oct instalment of **$36.22** goes unpaid | On **2 Oct** chasing resumes over the arrears this plan spreads — *"Immediate"*, no grace period. The plan stays `active`; nobody is dropped |
| TC-12 *(PO 2026-08-12, OQ-171)* | The utility writes off the arrears of an account that paid the **$50.00** down payment on a **$267.30** plan and nothing since | The **write-off CLOSES the plan**, and the account may take a new plan tomorrow. The product supplies the mechanism and the report and **never the decision** — `close_plan_on_write_off` has no automatic caller |
| TC-8 *(isolation)* | J. Okafor opens S24 for a Brazos Bend account id | Denied (RLS); his own accounts list only Lone Star Ridge payment methods |

**4 · Test Data** — A-10432: balance $247.30, method ACH · Chase ••••4021; 4 monthly installments Sep 1 / Oct 1 / Nov 1 / Dec 1 2026 (prototype schedule). Down-payment variant per TC-4. Template: tenant S67 payment-plan agreement v1 ({missed_count} = 2 default). Actors: Marcus Vega (send), Sarah Miller (signer); isolation J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Balance to spread | S24 step 1 | prototype-extracted (defaults to balance) | `payment_plans.total_amount` (⚠ payments write via service) | numeric(18,6) USD | user-input | 0 < x ≤ balance |
| Down payment | S24 step 1 | prototype-extracted | **PROPOSED-SCHEMA** `payment_plans.down_payment` (A19 §3 tokens {down} exist; B2 column not named) | numeric(18,6) | user-input | ≥ 0, < total |
| Installments / cadence / first date | S24 step 1 | prototype-extracted | `payment_plan_installments` rows (seq, due_date, amount — B2 UNIQUE (plan, seq)) | int/enum/date | user-input | n ≥ 1; first date > today |
| Auto-charge / suspend-late-fee / suspend-disconnect toggles | S24 step 1 | prototype-extracted (3 checkboxes) | **PROPOSED-SCHEMA** `payment_plans.autopay_enabled`, `.suspend_late_fees`, `.suspend_disconnect` | boolean | user-input | BR-CUS-043; drafting execution OQ-059 |
| Editable schedule rows | S24 step 2 | prototype-extracted | `payment_plan_installments` (amounts editable pre-send) | numeric/date | user-input | Σ = total (BR-CUS-043) |
| Remaining column | S24 step 2 | prototype-extracted | derived (total − Σ prior installments) | numeric USD | computed-display | monotonic to 0.00 |
| Agreement elections (email / SMS / print) | S24 step 3 | prototype-extracted | notification instructions; e-sign envelope via DocuSign seam (⚠ integrations B7) | boolean | user-input | ≥ 1 channel |
| Agreement document | S24 step 3 | A19 §3 + S67 (BR-NOT-004 ①) | template render; signed copy lands in `account_documents` (US-CUS-011) | pdf | system-derived | versioned template |
| Plan status | — | A5 · **BR-CUS-044 as amended (PO 2026-08-12, OQ-171)** | `payment_plans.status` (proposed → agreement_sent → active → closed; ~~+ PROPOSED `defaulted`~~ **no `defaulted` — SUPERSEDED PO 2026-08-11**) — B2 O-8 value set flagged. **`closed` is reached by paying every instalment OR by the utility WRITING THE ARREARS OFF, never automatically** | enum | system-derived | activation on sign only |
| Dunning/disconnect pause | — | A19 §3 + A6 · **PO 2026-08-12 (OQ-170)** | collections-state flag consumed by billing late-fee & notice flows (⚠ read by billing/payments); **lifts the day AFTER an unpaid instalment due date — *"Immediate"*, no grace — while the plan stays `active`** | boolean | system-derived | while current only |

**6 · Acceptance**
- Given the §4 fixture, Then the generated schedule matches §7 to the cent, edits must re-sum exactly, And Send creates the payments-owned plan in agreement_sent.
- Given a signature, Then the plan activates, dunning + disconnect pause (J4 contract), and the signed agreement files under Documents.
- Given a **missed instalment**, Then the pause lifts the next day and chasing resumes over the arrears the plan spreads, while the plan stays `active` (PO 2026-08-12, OQ-170).
- Given an **instalment payment**, Then it meets the PLAN first and, if short, reaches the current bill not at all (PO 2026-08-12, OQ-139).
- Given a **write-off of the arrears**, Then the plan closes and a new plan becomes possible — and the product never initiates the write-off (PO 2026-08-12, OQ-171).
- Given a live plan, Then a second cannot be proposed for the same account.

**7 · Finance Calculation** — **CONFIRMED** (BR-CUS-043 is CONFIRMED in `03-customers/02-business-rules.md`, PO closure batch 2026-08-08 — this section's "PROPOSED" was stale against the canonical file) and ❄️ **FROZEN as GT-47** (PE-13 under B5's mechanical `PE-n → GT-(34+n)` allocation; `10-scripts/03-golden-verify.py` recomputes 36.22 / 36.20 from the inputs). A7 EXPLICIT + B4.4 rounding: `spread = total − down_payment`; `installment = round_half_up(spread / n, 2)` for installments 1…n−1; `final = spread − (n−1) × installment`. Worked example (§4): 247.30 / 4 = 61.825 → half-up **61.83**; installments 1–3 = 61.83 (Σ 185.49); final = 247.30 − 185.49 = **61.81** ✓ prototype (remaining column 185.47 / 123.64 / 61.81 / 0.00). Down-payment variant: (247.30 − 47.30) / 4 = **50.00** exactly, final = 50.00. GT ref: **GT-47** (PE-13: 267.30 − 50 over 6 → **5 × 36.22 + 36.20**), asserted in `06-backend/tests/golden/test_gt47_payment_plan_schedule.py`. The earlier note that "no GT exists for installment math" was WRONG — the mechanical allocation on B5 line 68 already covered it.

**8 · Open Questions** — **OQ-139 — CLOSED 2026-08-12.** The PO ruled *"plan first"*: an instalment payment reaches **the PLAN before the oldest bill**, a NAMED EXCEPTION to oldest-invoice-first that applies to instalment payments only. **Worked, on this frozen PE-13 plan:** the arrears sit in the OLD invoices the plan spreads and October's new bill is **$184.20**; under oldest-first the instalment would be spent on the very debt the plan already covers and the customer would fall behind on the current bill **while paying exactly what they agreed**. Short of the instalment, nothing reaches the current bill. `payment_plan.split_payment_between` no longer raises. ORIGINALLY: which of the instalment and the current bill a PARTIAL payment meets — the PO closed OQ-138 (both are due) and left the order open. · **OQ-170 — CLOSED 2026-08-12** (*"Immediate"*): a missed instalment lifts the dunning pause the next day, no grace — **$36.22** unpaid 1 Oct → chasing resumes 2 Oct, plan still `active`. · **OQ-171 — CLOSED 2026-08-12** (*"Write-off closes - these are user business decision, they will make a decision, we have to provide a mechanism and report it"*): a write-off closes a plan (**$267.30** plan, **$50.00** down, nothing since), which is also what lets an account whose arrears were given up on take a new plan under the one-live-plan rule. Installment auto-charge drafting still rides OQ-059. ~~broken-plan status + {missed_count} carried as PROPOSED~~ — **CLOSED by the PO's ruling of 2026-08-11: there is no broken-plan status and no threshold. The question is MOOT rather than answered.**
