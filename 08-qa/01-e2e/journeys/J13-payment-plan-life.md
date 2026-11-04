# J13 — Payment-plan life (267.30 → e-sign → installments → notices → ~~2nd-miss VOID~~ the plan STAYS ACTIVE → money still taken)

> **STEP 6 IS SUPERSEDED (PO ruling 2026-08-11 → BR-PAY-016's *"2nd miss VOIDS
> plan"* clause, and BR-CUS-044's `defaulted` state with it).** PO verbatim:
> *"nodrop we chase for payments until write off"* (OQ-141 CLOSED,
> 12-governance/02-decision-log.md 2026-08-11). `apps/customers/payment_plan.py`
> was built as an ABSENCE: there is no `missed_count` column, no void path and
> no `defaulted` state, and a test asserts that a plan with misses against it is
> still `active`. **Steps 1–5 and 7–8 are unaffected.** The title's *"born to
> die"* framing is superseded with the step — a plan is not born to die, it is
> chased. Step 6 is kept, struck through, with what replaces it; deleting it
> would lose the fact that this ride once ended in a void.
> Stamped by the E2E journey-activation lane, 2026-08-11 (the budget/plan lane
> reported it and could not edit `08-qa/`).

---
id: J13
tier: 2
rules: [BR-CUS-043, BR-CUS-044, BR-PAY-012, BR-PAY-016, BR-PAY-010, BR-PAY-036, BR-NOT-005, BR-NOT-007, BR-REP-016]
stories: [US-CUS-018, US-PAY-017, US-PAY-018, US-PAY-019, US-PAY-001, US-NOT-011, US-NOT-012]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** ~~One payment plan, born to die:~~ (superseded — see the banner) One payment plan, chased not voided: the frozen PE-13 schedule (**267.30 − 50 down → 5 × 36.22 + final 36.20**, remainder-on-final half-up) activates on the customer's e-signature ALONE, pauses dunning while current, sends its ratified notice types through the platform queue, ~~voids on the 2nd miss with the full balance due~~ **stays ACTIVE through every miss while the arrears are chased (PO 2026-08-11)** — and then proves BR-PAY-036: money offered while the account is behind is still taken, and taking it changes no plan state.

**Fixture.** Tenant brazos-bend · ACC-1177, past-due balance **267.30** · plan: down **50.00**, 6 monthly installments due the 1st → **5 × 36.22 + 36.20** (BR-CUS-043) · notices at tenant defaults: reminder −3d · missed day+1 · 2nd miss = VOID (BR-PAY-016) · agreement = S67 contract type ① (payment-plan agreement), Residential variant · running balances **engine-computed** (00-e2e-design.md §5).

| # | Date · action | Handoff contract (what this step leaves) | Downstream assertions (bill · ledger · reports · queue · audit) | Rule |
|---|---|---|---|---|
| 1 | **Sep 1** — plan wizard: balance 267.30, down 50, n=6 → schedule **36.22 ×5 + 36.20** (2dp half-up, remainder on FINAL; step-2 edits must re-sum exactly) | Plan proposed; schedule rows persisted; ONE live plan per account enforced | Schedule sums to 267.30 to the cent; no ledger effect (a schedule is not money); audit | BR-CUS-043 |
| 2 | **Sep 1** — agreement renders from the S67 template (type ①, category variant, pinned version) → DocuSign seam → **ACTIVE on customer e-signature alone** — no countersign exists | Plan state proposed → agreement_sent → active; agreement document pinned to its template version | While active + current: dunning AND disconnect PAUSED (BR-CUS-043); plan state pill on the account header; audit | BR-CUS-044 |
| 3 | **Sep 1** — down payment **50.00** recorded, purpose = **plan-down**, linked to the plan | Cleared payment; allocation per BR-PAY-010; receipt queued | Purpose-aware reporting: plan-down shown as its own line, never in collection % (BR-REP-014); DR cash / CR AR balanced | BR-PAY-012 |
| 4 | **Sep 28 → Oct 1 → Nov 1** — reminder queues −3 days before each installment; Oct and Nov installments paid **36.22** each | Two on-time installments; plan current; missed_count 0 | Upcoming-installment notices are queue rows first, dispatched in batches (BR-NOT-005, template class per BR-NOT-007); balances engine-computed; audit per send | BR-PAY-016 |
| 5 | **Dec 1 missed** → **Dec 2** missed-installment notice (day+1); missed_count=1 | Plan still active; dunning still paused (one miss ≠ default) | Missed-installment notice row in the queue + notice_history appended; account header shows plan at-risk state | BR-PAY-016 |
| 6 | ~~**Jan 1 missed — 2nd miss → plan VOIDS**~~ **SUPERSEDED (PO 2026-08-11 → *"nodrop we chase for payments until write off"*).** As executed now: **Jan 1 missed — the plan stays ACTIVE** | ~~Plan state closed/void; collection ladder re-engages~~ · Now: no void record, no `defaulted` state, no `missed_count`; the plan and its schedule stand, and the arrears are chased through the ordinary collections ladder to write-off if it comes to that (BR-BIL-006) | ~~plan-void notice (the 3rd BR-NOT-007 variant) queues~~ · Now: the missed-installment notice of step 5 is the last of the three variants this ride sends; the real balance ages on posting basis; audit rows for the miss, none for a void | ~~BR-PAY-016 void clause~~ → BR-BIL-006 |
| 7 | **Jan 9** — customer pays **100.00** ~~after the void~~ **while the plan is still ACTIVE and behind** (SUPERSEDED with step 6) | **ACCEPTED** (BR-PAY-036 — always, in any state), tagged to the account, allocated oldest-first per BR-PAY-010; the payment does NOT reinstate the plan — any new plan is a new wizard pass | Receipt queued; DR cash / CR AR; dunning continues on the reduced balance; audit | **BR-PAY-036** · BR-PAY-010 |
| 8 | **INVARIANCE** — the schedule always re-sums to 267.30; the signed agreement renders its pinned template version forever; plan history (active → missed ×2 → ~~void~~ **still active**) is append-only; no notice was sent inline (queue rows exist for all five sends) | — | notice_history complete; ledger untouched by plan state transitions themselves; tie-outs hold (BR-LED-007) | BR-CUS-043 · BR-NOT-005 |
