# EP-PAY-05 — Payment plans (rows + schedule math · notices + missed/void · dunning pause)

**Module:** payments · **Wave:** W4 · **Screens:** S24, S34, S21, S33 · **Status:** draft (BR-PAY-001..031 all CONFIRMED — session closed 2026-08-08; schema B2 Addendum r12)

## Scope
**In:** the payments-owned side of payment plans (B2 `payment_plans` + `payment_plan_installments`): plan creation via the S24 wizard (customers owns the wizard UI — US-CUS-018; payments owns the rows + math per BR-CUS-043, PE-13 figures), **activation ONLY on customer e-signature** (BR-CUS-044), the S34 bulk "Payment plan" entry (same wizard), **plan notices + missed-installment tracking + 2-miss VOID** (BR-PAY-016, r12 #9), and the **dunning/disconnect pause while active + current** with resume on void/close (BR-CUS-043 + BR-PAY-016, J4 step-3 contract). Installment on-time-ness follows the posting date (BR-PAY-021); down payments carry purpose plan_down (BR-PAY-012, US-PAY-002).
**Out:** the wizard's form UX (US-CUS-018) · agreement template content + e-sign seam (S67/BR-NOT-004 ①, DocuSign B7 — notifications/integrations) · installment auto-charging (rails W7; capture-only per BR-CUS-059/BR-PAY-015) · the collection ladder itself (US-PAY-014 — this epic feeds its pause/resume input).
**Tables (B2 + r12):** `payment_plans` (+ notice fields + `missed_count`, r12 #9), `payment_plan_installments`, `outbound_messages` (notices, r12 #16), `notice_history` (r12 #7).

## Capability matrix (list screens only — B9 conformance)
No list screens — S24 is a guided wizard (customers), plan state renders on S21 header, S34 column and S33 rows. IS-6 governs confirms.

## Stories

---
id: US-PAY-017
epic: EP-PAY-05
module: payments
screens: [S24, S34]
wave: 4
status: draft
blocked_by: []
depends_on: [US-CUS-018, US-PAY-002, US-BIL-005]
journeys: [J4]
rules: [BR-CUS-043, BR-CUS-044, BR-PAY-012]
golden_tests: []
finance_calc: confirmed
---
### US-PAY-017 — Plan rows + schedule math + activation on signature (payments-owned)

**1 · Details** — As the payments service called by the S24 wizard (US-CUS-018 owns the form; S34 bulk "Payment plan" opens the same wizard), I want to own the plan rows and the math: **installment = (total − down) ÷ n, 2dp half-up (B4.4), remainder on the FINAL installment** (BR-CUS-043, A7 EXPLICIT — PE-13 worked); step-2 edits must re-sum exactly; **one live plan per account**; down payment recorded as purpose plan_down (BR-PAY-012, US-PAY-002); states **proposed → agreement_sent → active (ON SIGNATURE ONLY, customer e-signature ALONE — BR-CUS-044) → closed (final installment) | void (BR-PAY-016 2nd miss, US-PAY-018)**. Installments are rows with seq + due_date + amount (B2 UNIQUE (plan, seq)). Installment payments arrive through normal intake (US-PAY-001) linked to the plan; on-time = **posted_at ≤ installment due date** (BR-PAY-021). Entry: wizard Send agreement. Exit: plan rows; agreement out via the e-sign seam; activation event on signature (J4 step-3 handoff: plan active → dunning paused, executed by US-PAY-019).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-043 | Schedule: installment = (total − down) ÷ n, 2dp half-up (B4.4), remainder on FINAL (A7 EXPLICIT); step-2 edits must re-sum exactly; while active + current, dunning and disconnect pause; late-fee suspension is a per-plan election; one live plan per account. | CONFIRMED — PO closure batch, 2026-08-08 |
| BR-CUS-044 | Agreement renders from the S67 template (A19 §3, BR-NOT-004 ①); e-sign via DocuSign seam (B7); proposed → agreement_sent → active(on sign) → closed; activation ONLY on signature; customer e-signature ALONE. | CONFIRMED — PO closure batch, 2026-08-08 |
| BR-PAY-012 | Down payment carries purpose plan_down, linked to its plan. | CONFIRMED — PO PA-1, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | PE-13: ACC-1310 balance 267.30, down 50.00, 6 monthly installments from Sep 1, 2026 | `payment_plans` row (total 267.30, down 50.00) + 6 installment rows: **5 × 36.22 + final 36.20** (§7); status proposed → agreement_sent on Send; down payment $50.00 recorded purpose plan_down linked to the plan; audit `payment_plan.proposed` |
| TC-2 | Customer signs the envelope | Status → active — signature alone activates (BR-CUS-044, no countersign); activation event to US-PAY-019 (dunning/disconnect pause); audit `payment_plan.activated` |
| TC-3 | Step-2 edit: installment 1 raised to 50.00 | Re-sum enforced: schedule must total 217.30 exactly (spread), final row absorbs; a set summing short blocks Send (BR-CUS-043) |
| TC-4 *(posting vs clearing)* | Installment 1 (due Oct 1) paid by check posted Oct 1, cleared Oct 3 | Installment ON-TIME (posted_at ≤ due, BR-PAY-021); missed_count unchanged; the payment links to the plan |
| TC-5 | Final installment paid | Plan → closed; header state clears; audit `payment_plan.closed` |
| TC-6 *(negative)* | Second plan proposed while one is agreement_sent/active | Blocked — one live plan per account (BR-CUS-043); message links the existing plan |
| TC-7 *(negative)* | Activation attempted via API without a signature event | Rejected — activation ONLY on signature (BR-CUS-044); status stays agreement_sent |
| TC-8 *(isolation)* | Lone Star Ridge plan | Its accounts/templates only; Brazos Bend plan ids 404 (RLS) |

**4 · Test Data** — PE-13 verbatim: ACC-1310, balance 267.30, down 50.00, 6 monthly installments Sep 1, 2026 – Feb 1, 2027 → 36.22 ×5 + 36.20. Elections (per-plan): suspend_late_fees ON (BR-CUS-043 election), suspend_disconnect ON. Agreement: tenant S67 payment-plan template v1. Actors: Priya Menon (send), the ACC-1310 customer (signer). Isolation: J. Okafor.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Plan totals (total, down) | S24 step 1 | BR-CUS-043 | `payment_plans.total_amount` + down-payment column (r12 #9 family; named in customers map) | numeric(18,6) USD | user-input | 0 < total ≤ balance; down ≥ 0 |
| Installment rows | S24 step 2 | BR-CUS-043 | `payment_plan_installments` (seq, due_date, amount; UNIQUE (plan, seq)) | rows | system-derived (+edits) | Σ = spread exactly |
| Cadence / first date | S24 step 1 | prototype-extracted | installment due_date generation | enum/date | user-input | first date > today |
| Per-plan elections | S24 step 1 | BR-CUS-043 (late-fee suspension per-plan) | plan election columns (customers map PROPOSED family → r12 #9) | boolean | user-input | recorded on the plan |
| Status | S21/S34 | BR-CUS-044 + BR-PAY-016 | `payment_plans.status` proposed\|agreement_sent\|active\|closed\|void (B2 O-8 resolved by BR-CUS-044/BR-PAY-016) | enum | system-derived | active on signature only |
| Down payment | S22/S35 | BR-PAY-012 | `payments` purpose plan_down + plan link (r12 #2) | numeric(18,6) | user-input | via US-PAY-001/002 |
| Installment payment link | S33 | BR-PAY-021 | payment → installment linkage; on-time = posted_at ≤ due | uuid/dates | system-derived | drives US-PAY-018 missed logic |
| Agreement + signature event | S24 step 3 | BR-CUS-044 | e-sign envelope via DocuSign seam (⚠ integrations B7); signed doc to account documents | event/pdf | integration | signature alone activates |
| Audit | — | CLAUDE.md #7 | `audit_log` `payment_plan.proposed/activated/closed` | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given PE-13 inputs, Then the schedule equals §7 to the cent, edits must re-sum exactly, and the plan activates only on the customer's signature.
- Given one live plan, Then a second cannot exist; given the final installment posted, the plan closes.
- Given an installment posted by its due date, Then it is on-time regardless of clearing.
- Given tenants, Then plans never cross.

**7 · Finance Calculation** — CONFIRMED (BR-CUS-043 + PE-13, model §9 verbatim). `spread = 267.30 − 50 = 217.30`; installment = round_half_up(217.30 ÷ 6, 2) → **36.22** for installments 1–5; final = remainder → **36.20** (remainder-on-final, half-up). Schedule: 5 × 36.22 + 36.20; Σ + down = 267.30 exactly.

**8 · Open Questions** — None.

---
id: US-PAY-018
epic: EP-PAY-05
module: payments
screens: [S21, S34, S33]
wave: 4
status: draft
blocked_by: []
depends_on: [US-PAY-017, US-BIL-023]
journeys: [J4]
rules: [BR-PAY-016, BR-NOT-005, BR-PAY-021]
golden_tests: []
finance_calc: confirmed
---
### US-PAY-018 — Plan notices + missed tracking: reminder −3d · missed day+1 · ~~2nd miss VOIDS~~ the chase resumes day+1

⚠ **THIS STORY'S VOID MACHINERY IS SUPERSEDED — read this first.** The *"2nd miss VOIDS the plan"* clause was superseded by the PO on **2026-08-11** (*"nodrop we chase for payments until write off"*, OQ-141 → BR-PAY-016 / BR-CUS-044) and this story was never restamped; the **2026-08-12** rulings then supplied what replaces it. **What is true now:** a plan is never voided and nobody is dropped; **a missed instalment lifts the dunning pause IMMEDIATELY, with no grace period** (PO 2026-08-12, OQ-170, *"Immediate"* — PE-13's **$36.22** unpaid on **1 Oct**, chasing resumes **2 Oct**); and a plan ends by being **PAID or WRITTEN OFF** (PO 2026-08-12, OQ-171). `missed_count` survives as a COUNTER WITH NO THRESHOLD. Every mention of *void* below is kept, struck or stamped rather than deleted, so the change is legible.

**1 · Details** — As the payments service, I want the plan-notice cadence (BR-PAY-016, tenant-config defaults): **upcoming-installment reminder 3 days before** each due date · **missed-installment notice day+1** after an unpaid due date · ~~**2nd miss → the plan VOIDS** (A19 §3): full remaining balance due~~ **SUPERSEDED (PO 2026-08-11/2026-08-12): no void — the missed notice goes out day+1 AND the dunning pause lifts the same day (OQ-170), while the plan stays `active`**, dunning resumes (US-PAY-019) — with `missed_count` on the plan (r12 #9, ~~2 → void~~ **a counter with no threshold**), every notice a **queue-write** (BR-NOT-005; paper v1, email/SMS deferred to rails per the ladder pattern) appended to `notice_history`, and the plan state on the account header. Missed = no payment with **posted_at ≤ installment due date** (BR-PAY-021 — clearing later never misses an installment); **and a PART-paid instalment is still a missed one — short of the instalment nothing reaches the current bill** (PO 2026-08-12, OQ-139 → BR-PAY-012). ~~A caught-up installment before the second miss keeps the plan alive (missed_count tracks misses; void only at the tenant threshold, default 2).~~ **The plan is alive at the tenth miss exactly as at the first.** Entry: scheduled evaluation. Exit: queue rows, notice_history, missed_count, ~~void transition when reached~~ **pause lifted day+1**.

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-PAY-016 | Plan notices (tenant-config defaults): reminder 3 days before installment · missed-notice day+1 · ~~2nd miss VOIDS plan (full balance due, dunning resumes)~~ **SUPERSEDED PO 2026-08-11 (*"nodrop we chase for payments until write off"*)**; via delivery queue; plan state on account header. **AMENDED PO 2026-08-12 (OQ-170, *"Immediate"*): a missed instalment lifts the dunning pause the NEXT DAY, no grace — PE-13's $36.22 unpaid 1 Oct → chasing resumes 2 Oct, plan still `active`.** | CONFIRMED — PO PA-5, 2026-08-08 (r12 #9) · **void SUPERSEDED 2026-08-11 · pause edge AMENDED 2026-08-12** |
| BR-CUS-044 *(consumed)* | A plan ends by being **PAID or WRITTEN OFF** — a write-off closes it; the product supplies the mechanism and the report, never the decision. | CONFIRMED — PO 2026-08-12 (OQ-171) |
| BR-PAY-012 *(consumed)* | An instalment payment reaches the **PLAN first** (named exception to oldest-invoice-first); short of the instalment, nothing reaches the current bill — a part-paid instalment is still a missed one. | CONFIRMED — PO 2026-08-12 (OQ-139) |
| BR-NOT-005 | Notice rows written to the outbound table; dispatcher sends. | CONFIRMED — PO volume ruling (r12 #16) |
| BR-PAY-021 | Missed evaluation = posting date vs installment due date. | CONFIRMED — PO explicit ruling, 2026-08-08 |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | ACC-1310 plan active; installment 2 due Oct 1 | Sep 28 (−3d): reminder queue row + notice_history; content shows installment 36.22 + due date |
| TC-2 | Oct 1 passes with no payment posted (PE-13 instalment **$36.22**) | Oct 2 (day+1): missed-installment notice queued; `missed_count` 0→1; header state shows "plan — 1 missed"; ~~dunning still paused (void needs 2)~~ ⚠ **AMENDED PO 2026-08-12 (OQ-170, *"Immediate"*): the dunning pause LIFTS on Oct 2 — chasing resumes over the arrears the plan spreads, with NO grace period, while the plan stays `active`** |
| TC-2b *(PO 2026-08-12, OQ-139)* | The customer sends **$20.00** against the **$36.22** instalment | The instalment is met FIRST and is **not** met — a part-paid instalment is still a missed one, so the pause lifts on day+1 exactly as in TC-2, and **nothing reaches October's $184.20 current bill** |
| TC-3 | ~~Second miss (installment 3, Nov 1 unpaid → Nov 2)~~ ⚠ **SUPERSEDED PO 2026-08-11 (OQ-141) — there is no threshold.** Replacement scenario: instalments 3 and 4 both unpaid | ~~missed_count → 2 = tenant threshold → plan void: full remaining balance due immediately, dunning resumes; void notice queued; audit `payment_plan.voided`~~ **The plan stays `active` at the second miss exactly as at the first** (and at the tenth). `missed_count` increments as a fact about how far behind the account is and triggers nothing; the chase — already resumed since the first day+1 — simply continues. No `defaulted`, no void, no acceleration |
| TC-3b *(PO 2026-08-12, OQ-171)* | The utility decides to write the arrears off on an account that paid its **$50.00** down payment on a **$267.30** plan and nothing since, eighteen months on | The **write-off CLOSES the plan** (`closed`), and the account may take a new plan tomorrow. The product never initiates it — `close_plan_on_write_off` has no automatic caller — and it reports the state rather than deciding it |
| TC-4 *(posting vs clearing)* | Installment posted Oct 1 (due date), clears Oct 4 | NOT missed (BR-PAY-021); no notice, no count |
| TC-5 | Catch-up after one miss | Late installment posted → plan stays active; missed_count remains 1 (history, not reset — BR-PAY-016 counts misses); ~~no void~~ **no void exists to avoid; the plan is `active` throughout and the pause returns once the plan is CURRENT again (BR-CUS-043: *"while active AND current"*)** |
| TC-6 | Tenant config: reminder −5d, ~~void at 3 misses~~ **(the void-count setting has nothing left to trigger — PO 2026-08-11)** | Next evaluation honors the cadence settings — defaults are config, not constants |
| TC-7 *(negative)* | Inline email attempt for a plan notice | Forbidden — queue-write only (BR-NOT-005) |
| TC-8 *(isolation)* | Lone Star Ridge plan notices | Its plans/settings/queue only (RLS) |

**4 · Test Data** — ACC-1310 plan (US-PAY-017 fixture): installments 36.22 due Sep 1 / Oct 1 / Nov 1 / Dec 1 / Jan 1 + 36.20 Feb 1. Tenant plan-notice settings seeded: reminder_days_before 3, missed_notice_day_after 1, void_missed_count 2. Miss fixtures per TC-2/3. Actors: system job; Priya Menon (review). Isolation: Lone Star Ridge plan.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Notice settings | S66 | BR-PAY-016 ("tenant-config defaults") | plan notice fields (r12 #9): reminder days, missed day, ~~void count~~ | ints | reference-data | seeded 3 / 1 / ~~2~~ — **the void count triggers nothing (PO 2026-08-11)** |
| Reminder / missed / ~~void~~ notice rows | — | BR-PAY-016 + BR-NOT-005 | `outbound_messages` (r12 #16) + `notice_history` (r12 #7) | rows | system-derived | queue-write only; send/skip recorded. **The third variant (plan-void notice) has nothing left to announce** |
| missed_count | S21 header | BR-PAY-016 | `payment_plans.missed_count` (r12 #9) | int | system-derived | increments per miss; ~~void at threshold~~ **a COUNTER WITH NO THRESHOLD — worth keeping as a fact about how far behind an account is, worth nothing as a trigger** |
| Missed evaluation | — | BR-PAY-021 · **BR-PAY-012 (PO 2026-08-12)** | computed: no linked payment posted_at ≤ installment due_date | boolean | system-derived | clearing date irrelevant; **a PART payment of the instalment is still a miss** |
| Dunning-pause lift | S21/S34 | **BR-PAY-016 / BR-CUS-043 as amended (PO 2026-08-12, OQ-170)** | collections-state flag drops the day AFTER an unpaid instalment due date — **no grace** | boolean | system-derived | plan stays `active`; chase covers the arrears the plan spreads |
| ~~Void transition~~ | S21/S34 | ~~BR-PAY-016 (A19 §3)~~ | ~~`payment_plans.status` → void; full remaining balance due~~ ⚠ **SUPERSEDED PO 2026-08-11 — no void state exists.** Replaced by: `payment_plans.status` → `closed` **on a human's write-off** (PO 2026-08-12, OQ-171 → BR-CUS-044) | enum | system-derived | **never automatic — `close_plan_on_write_off` has no automatic caller** |
| Header plan state | S21/S34 | BR-PAY-016 | read-model over plan status + missed_count | text | computed-display | "Active · 1 missed" etc. |
| Audit | — | CLAUDE.md #7 | `audit_log` `payment_plan.missed/voided` + notice events | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given the cadence settings, Then reminders and missed notices queue exactly on schedule with history appended, and the header state always reflects plan + misses.
- ~~Given the tenant threshold of misses, Then the plan voids: full balance due, dunning resumes — demoable end-to-end with TC-2/3.~~ ⚠ **REPLACED (PO 2026-08-11 + 2026-08-12):** given ONE missed instalment, Then the missed notice queues on day+1 **and the dunning pause lifts the same day, with no grace period**, while the plan stays `active` — demoable with TC-2/2b. Given ten misses, Then the plan is still `active`.
- Given a write-off on the account's arrears, Then the plan **closes** and a new plan becomes possible — and the product never initiates the write-off (TC-3b).
- Given an installment posted by its due date, Then no miss exists regardless of clearing; given a PART payment of the instalment, Then it is still a miss and nothing reaches the current bill.
- Given tenants, Then settings, counts and notices never cross.

**7 · Finance Calculation** — CONFIRMED (PE-13 cadence, model §9). No new money math. ~~On void, the amount due = remaining plan balance = 267.30 − down 50.00 − Σ installments posted~~ ⚠ **there is no void and therefore no acceleration (PO 2026-08-11);** what a customer owes in a missed month is the ordinary pair — the instalment **$36.22** AND October's cycle bill **$184.20** = **$220.42** (BR-CUS-043 / BR-BIL-073, PO 2026-08-11), with the instalment met FIRST (PO 2026-08-12, OQ-139). On a **write-off** closure the remaining plan balance is what the utility writes off — **267.30 − 50.00 down = 217.30** on the TC-3b fixture — and that is a human's decision, not a computation this story performs. Dunning/late fees thereafter are billing's (BR-BIL-001) per the resumed ladder.

**8 · Open Questions** — **None open. Two closed 2026-08-12 (PO), and both replace machinery this story still described:** **OQ-170** — *"Immediate"*: a missed instalment lifts the dunning pause the next day, no grace (PE-13's **$36.22** unpaid 1 Oct → chasing resumes **2 Oct**); it does not drop anybody. · **OQ-171** — *"Write-off closes - these are user business decision, they will make a decision, we have to provide a mechanism and report it"*: a write-off closes the plan (**$267.30** plan, **$50.00** down, nothing since, eighteen months live), and the product supplies the mechanism and the report and never the decision.

---
id: US-PAY-019
epic: EP-PAY-05
module: payments
screens: [S21, S34]
wave: 4
status: draft
blocked_by: []
depends_on: [US-PAY-017, US-PAY-018, US-PAY-014]
journeys: [J4]
rules: [BR-CUS-043, BR-PAY-016, BR-PAY-017]
golden_tests: []
finance_calc: none
---
### US-PAY-019 — Dunning + disconnect pause while active & current; resume on void/close

**1 · Details** — As the payments service, I want the plan state to gate collections (J4 step-3 handoff: *plan active on signature → dunning + disconnect paused while current*): while a plan is **active AND current** (~~no void; misses below threshold~~ **no missed instalment outstanding — PO 2026-08-12, OQ-170**), the collection ladder (US-PAY-014) pauses for the account and disconnect steps are blocked (BR-CUS-043); **late-fee suspension is the per-plan election** (BR-CUS-043 — suspend only if elected); ~~on **void** (US-PAY-018) dunning resumes with the full balance due (BR-PAY-016)~~ ⚠ **SUPERSEDED (PO 2026-08-11, no void): dunning resumes THE DAY AFTER a missed instalment, immediately and with no grace, over the ARREARS THE PLAN SPREADS — not over an accelerated full balance, and the plan stays `active` throughout** — the ladder re-evaluates from the account's arrears state (its own BR-PAY-017 tenant config; no tier invented here); on **close** — reached by paying every instalment **or by the utility writing the arrears off (PO 2026-08-12, OQ-171)** — no ladder applies to the closed plan. **Two further collections edges ruled 2026-08-12 land on this gate:** after a **bounced cheque the ladder restarts at its FIRST rung** (OQ-133 — a **$1,842.10** bill due 6 Jul, cheque posted 5 Jul, bounced three weeks later, so the payment that stopped the chase never existed), and **a partial payment pauses the ladder only if it meets a configured percentage of the outstanding balance** (OQ-136 — **$150** against **$948** is **15.8%**, so the ladder continues; a 25% threshold needs **$237.00**, 50% needs **$474.00**; the threshold is a TENANT SETTING in **Settings → Configure**, beside the collections/dunning settings). Plan state renders on the S21 header and the S34 Payment-plan column so staff always see why dunning is or isn't running. Entry: activation/miss/close events from US-PAY-017/018. Exit: pause/resume flags consumed by US-PAY-014 + billing's late-fee flow (election read).

**2 · Business Rules**
| BR | Statement | Status |
|---|---|---|
| BR-CUS-043 | While active + current: dunning and disconnect pause (A7/A19 §3); late-fee suspension is a per-plan election. **The pause covers the ARREARS THIS PLAN SPREADS only** (PO 2026-08-11) and **"current" ends the day an instalment is missed, with no grace** (PO 2026-08-12, OQ-170). | CONFIRMED — PO closure batch, 2026-08-08 · **scoped 2026-08-11 · edge fixed 2026-08-12** |
| BR-PAY-016 | ~~2nd miss voids: full balance due, dunning resumes~~ **SUPERSEDED PO 2026-08-11 — no void, nobody dropped. Dunning resumes on day+1 of a missed instalment while the plan stays `active`** (PO 2026-08-12, OQ-170); plan state on account header. **Plus: the ladder RESTARTS at rung 1 after a bounced cheque (OQ-133) and a partial payment pauses it only above a configured % of outstanding (OQ-136, tenant setting in Settings → Configure).** | CONFIRMED — PO PA-5, 2026-08-08 · **void SUPERSEDED 2026-08-11 · amended 2026-08-12** |
| BR-CUS-044 *(consumed)* | A **write-off closes** the plan; the product provides the mechanism and the report, never the decision. | CONFIRMED — PO 2026-08-12 (OQ-171) |
| BR-PAY-017 | The resumed ladder is the tenant-config sequence — resume mechanics are its normal evaluation over the reinstated arrears. **After a BOUNCE that resume starts at the FIRST rung, not where the ladder had reached** (PO 2026-08-12, OQ-133). | CONFIRMED — PO PA-6, 2026-08-08 · **restart amended 2026-08-12** |

**3 · Test Cases**
| TC | Scenario | Expected |
|---|---|---|
| TC-1 | ACC-1310 plan activates (US-PAY-017 TC-2) | Collection ladder paused (US-PAY-014 skips the account, skip recorded in notice_history); disconnect actions on S34/S22 blocked with the plan named; header "Payment plan · Active" |
| TC-2 | Late-fee election | Plan with suspend_late_fees ON → billing's late-fee candidates exclude the account while current; election OFF → late fees continue (per-plan election, BR-CUS-043) |
| TC-3 | One miss — PE-13's **$36.22** unpaid on **1 Oct** | ~~Plan still current-track (BR-PAY-016 voids at 2); pause holds; header shows "1 missed"~~ ⚠ **AMENDED PO 2026-08-12 (OQ-170, *"Immediate"*): on 2 Oct the pause LIFTS and chasing resumes over the arrears this plan spreads — no grace period. The plan stays `active` and nobody is dropped; the header shows "Active · 1 missed" with the chase running** |
| TC-4 | ~~Void (US-PAY-018 TC-3)~~ ⚠ **SUPERSEDED — no void state exists (PO 2026-08-11).** Replacement: the missed instalment of TC-3 | Pause lifts; ladder re-evaluates the account's arrears per tenant config (BR-PAY-017); disconnect actions re-enabled; header ~~"Plan voided — full balance due"~~ **"Active · 1 missed"; NO full-balance acceleration** |
| TC-4b *(PO 2026-08-12, OQ-133)* | A **$1,842.10** bill due **6 Jul** was paid by cheque posted **5 Jul** (chasing stopped); the cheque bounces three weeks later | The ladder **restarts at its first rung** — first notice onward — not at the step it had reached, because the payment that stopped it never existed |
| TC-4c *(PO 2026-08-12, OQ-136)* | An account owing **$948** pays **$150** the day before a disconnection notice | **15.8%** — under either threshold, so the ladder **continues**. At a 25% tenant threshold it would need **$237.00**; at 50%, **$474.00**. The threshold is a tenant setting (Settings → Configure), never a platform constant |
| TC-5 | Close — by the final installment **or by a write-off of the arrears** (PO 2026-08-12, OQ-171) | Account settled (or written off); no ladder for the closed plan; header state clears. **The write-off is a human's decision the product records and reports** |
| TC-6 *(negative)* | Disconnect-notice send forced via API for a plan-active account | Rejected server-side — disconnect paused while active + current (BR-CUS-043); UI state irrelevant |
| TC-7 *(isolation)* | Lone Star Ridge plan pause | Gates only its own accounts (RLS) |

**4 · Test Data** — ACC-1310 (US-PAY-017/018 fixtures): activation Sep 1; miss Oct 2; void Nov 2. Elections: suspend_late_fees ON / variant OFF. Ladder state: account previously at tier 1 before the plan. Actors: system; Priya Menon. Isolation: Lone Star Ridge.

**5 · Data Fields / Mapping**
| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation |
|---|---|---|---|---|---|---|
| Pause gate | — | BR-CUS-043 · **PO 2026-08-12 (OQ-170)** | computed: plan status active ∧ ~~missed_count < threshold~~ **no instalment past its due date unpaid** → collections pause flag consumed by US-PAY-014 | boolean | system-derived | evaluated before every ladder step; **lifts on day+1 of a miss, no grace** |
| Ladder restart point | — | **BR-PAY-017 / BR-PAY-016 as amended (PO 2026-08-12, OQ-133)** | after a BOUNCE the ladder position resets to **rung 1**, not to the step reached | enum/int | system-derived | *"Restart from the beginning"* — the payment that stopped the chase never existed |
| Partial-payment pause threshold | **Settings → Configure** (beside collections/dunning) | **BR-PAY-016 as amended (PO 2026-08-12, OQ-136)** | tenant setting: minimum % of outstanding a partial payment must meet to pause the ladder | percent | reference-data | tenant-set, **not a platform constant**; $150 / $948 = 15.8% does not pause |
| Disconnect block | S34/S22 | BR-CUS-043 | server-side gate on disconnect actions | boolean | system-derived | while active + current |
| Late-fee election read | — | BR-CUS-043 | plan election column (US-PAY-017 §5) — billing reads via service fn (B1) | boolean | reference-data | per-plan, not global |
| Resume on ~~void~~ **miss** | — | BR-PAY-016 + BR-PAY-017 | pause flag drops **the day after an unpaid instalment due date**; ladder normal evaluation resumes over the arrears the plan spreads | — | system-derived | no invented tier — config-driven; **no full-balance acceleration (no void exists)** |
| Close on write-off | S21/S34 | **BR-CUS-044 (PO 2026-08-12, OQ-171)** | `payment_plans.status` → `closed` when the utility writes the arrears off; `close_plan_on_write_off` | enum | user-initiated (utility) | **never automatic**; the account may take a new plan afterwards (one live plan per account, BR-CUS-043) |
| Header/column state | S21/S34 | BR-PAY-016 | read-model over plan status + missed_count | text | computed-display | always visible |
| Pause/resume audit | — | CLAUDE.md #7 | `audit_log` `collections.paused/resumed` (plan ref) | jsonb | system-derived | append-only |

**6 · Acceptance**
- Given activation, Then dunning and disconnect stop for the account (with skips recorded), and the late-fee election behaves exactly as elected.
- ~~Given void, Then the pause lifts and the tenant-config ladder resumes over the reinstated arrears; given close, nothing resumes.~~ ⚠ **REPLACED (PO 2026-08-12):** given a **missed instalment**, Then the pause lifts **the next day** and the tenant-config ladder resumes over the arrears the plan spreads, while the plan stays `active`; given close — by payment **or write-off** — nothing resumes.
- Given a **bounced cheque**, Then the ladder restarts at rung 1; given a partial payment **below the tenant threshold**, Then the ladder does not pause at all.
- Given a forced disconnect attempt during an active plan, Then the server refuses.
- Given tenants, Then gates never cross.

**7 · Finance Calculation** — N/A (gating story; money math lives in billing's late fee and US-PAY-017/018 figures). **Cited, not recomputed, for the 2026-08-12 edges:** the pause lifts on PE-13's **$36.22**; the bounce restart fixture is a **$1,842.10** bill; the threshold fixture is **$150** of **$948** = **15.8%** (25% → **$237.00**, 50% → **$474.00**).

**8 · Open Questions** — **None open. Four closed 2026-08-12 (PO):** **OQ-170** (*"Immediate"* — the pause lifts day+1, no grace) · **OQ-171** (*"Write-off closes"* — and the product supplies the mechanism and the report, never the decision) · **OQ-133** (*"Restart from the beginning"* — the ladder restarts at rung 1 after a bounce) · **OQ-136** (*"partial payment is okay it should be aleast 25% or 50% of outstanding; you ahve to allow user to set this limit in configuration or setting section, decide the place"* — a tenant setting, placed by Eng in Settings → Configure beside the collections settings).


---

## Build state (2026-08-16, payments SURFACE lane) — the POSITION is readable

US-PAY-018 and US-PAY-019 are gating stories: their output is a pause flag and a missed count that other things consume. **Nothing could SEE either.** `GET /accounts/{id}/collections` now serves one account's whole dunning position in one body — the pause decision with `covers` and `not_covered` beside it (BR-CUS-043's scope is a sentence a clerk repeats on the phone, and *"paused"* without *"but this month's bill is still due"* is how a customer is told the wrong thing), the live plan with its missed count, the ladder tier already sent, and the notice history including SKIPS.

**Sends and skips both, deliberately** (J4 step 2): an account excluded for a medical hold and one nobody ever chased must never read the same.

**`plan: null` means there is no plan, never "unknown".** `missed` is the figure BR-PAY-016 as amended turns on — the day one instalment is missed the pause lifts and chasing resumes, with **no grace** (PO 2026-08-12, OQ-170) and with the plan STILL ACTIVE. The header a screen draws from this is US-PAY-019 TC-3's own corrected wording: *"Active · 1 missed"* with the chase running.

**Still owed:** S24 itself. The plan WIZARD is US-CUS-018 (customers) and has neither endpoint nor screen, which is why US-PAY-017 remains on the surface-debt register.
