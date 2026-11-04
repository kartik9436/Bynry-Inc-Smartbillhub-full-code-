# J09 — Budget billing YEAR (enroll → level months → re-level → settle-up → ~~2-miss drop-off~~ collections while ENROLLED)

> **STEP 7 IS SUPERSEDED (PO ruling 2026-08-11 → BR-BIL-017 drop-off clause).**
> PO verbatim: *"nodrop we chase for payments until write off"* (OQ-141 CLOSED,
> 12-governance/02-decision-log.md 2026-08-11). There is no off-budget event and
> no missed-payment counter: `apps/billing/budget_service.py` was built as an
> ABSENCE, with a test asserting that ten missed level payments leave the account
> ENROLLED. **Steps 1–6 and the step-8 invariance are unaffected and still
> describe the product.** Step 7 below is kept, struck through, with what
> replaces it — deleting it would lose the fact that this ride once ended in a
> drop-off and that a reader of an older commit will expect one.
> Stamped by the E2E journey-activation lane, 2026-08-11 (the budget/plan lane
> reported it and could not edit `08-qa/`).

---
id: J09
tier: 2
rules: [BR-BIL-017, BR-RAT-043, BR-PAY-010, BR-PAY-021, BR-LED-007, BR-REP-001, BR-REP-007, BR-TEN-043]
stories: [US-BIL-018, US-BIL-019, US-BIL-020, US-PAY-006, US-LED-008, US-REP-009]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** A full budget-billing year on one account, proving the WE-8 doctrine at every point: the level payment is a COLLECTION SCHEDULE, never a price — revenue and tax recognize on the monthly ACTUALS, variance is visible on every bill, the level auto-corrects at drift, the settle-up month is a non-taxable AR-timing line, and two missed payments end the ride. The WE-8 chain 242 / −50.87 → −40.27 → +2.98 anchors months 1–3.

**Fixture.** Tenant brazos-bend · ACC-1042, Residential Standard, 12+ months history · trailing-12 actuals **$2,904** → level **$242** (whole $, WE-8) · budget params = seeded defaults (re-level at ±20% drift each 6 mo · settle-up month April · off-budget after 2 missed payments — all tenant settings per BR-BIL-017) · enrollment **Jun 28, 2026**.

| # | Date · action | Handoff contract (what this step leaves) | Downstream assertions (bill · ledger · reports · queue · audit) | Rule |
|---|---|---|---|---|
| 1 | **Jun 28, 2026** — enroll: eligibility = 12-mo history passes; level computes **242** | Plan flag budget (BR-RAT-043); level + params stamped; variance balance opens at 0.00 | Budget-status report row (US-REP-009); audit row for enrollment | BR-BIL-017 |
| 2 | **Jul 1** — July bill: actual **292.87** computed and RECOGNIZED; presented level 242 | Variance **−50.87**; running balance −50.87; bill shows actual · level · running balance (all three columns, WE-8) | Ledger: revenue/tax post on the ACTUAL 292.87; cash expected 242 → AR-timing gap visible in TB (LE V-4 pattern); customer pays 242 per BR-PAY-010; posting-basis billed KPI reads 292.87 (BR-REP-001) | BR-BIL-017 |
| 3 | **Aug 1 / Sep 1** — Aug actual **231.40** → +10.60 (running −40.27); Sep actual **198.75** → +43.25 (running **+2.98**) | WE-8 chain lands exactly: −50.87 → −40.27 → +2.98 | Each month: actuals-based JE balanced; level 242 collected; variance column matches the frozen chain; delivery + audit rows monthly | BR-BIL-017 |
| 4 | **Oct 1 – Dec 1** — three more level months (actuals **engine-computed**, 00-e2e-design.md §5) | Running balance continues from +2.98 (engine-computed) | 6-month checkpoint reached with full history retained | BR-BIL-017 |
| 5 | **Jan 4, 2027** — 6-mo re-level checkpoint: drift ≥ ±20% (fixture winter usage) → auto RE-LEVEL to new whole-$ level (**engine-computed**) | New level effective forward only; old months unrestated; re-level recorded with computation inputs | Config-forward law: the level in force when each bill issued governs it — no retroactive re-timing (BR-TEN-043); audit row for re-level | BR-BIL-017 · BR-TEN-043 |
| 6 | **Apr 1, 2027** — SETTLE-UP month: running balance collected/credited as a **non-taxable AR-timing line** (amount engine-computed) | Balance resets to 0.00; revenue and tax were already recognized on the monthly actuals — the settle-up line touches NO revenue/tax GL | Ledger: AR-timing line only, balanced; remittance report unaffected by settle-up (tax recognized monthly); basis labels intact | BR-BIL-017 |
| 7 | ~~**May–Jun 2027** — customer misses the May and June level payments~~ **SUPERSEDED (PO 2026-08-11 → *"nodrop we chase for payments until write off"*).** As executed now: the customer misses the May and June level payments and **stays ENROLLED** | ~~1st miss recorded; **2nd miss → OFF-BUDGET** (BR-BIL-017); status `off_budget` recorded~~ · Now: no miss counter exists, no `off_budget` status is written, the level and its variance chain continue uninterrupted | ~~Jul 2027 bill = plain actuals, no level/variance columns~~ · Now: the Jul 2027 bill is a normal LEVEL bill; the arrears are chased through the ordinary collections ladder on the real balance, to write-off if it comes to that (BR-BIL-006); budget-status report still shows the account enrolled; audit | ~~BR-BIL-017 drop-off clause~~ → BR-BIL-006 |
| 8 | **INVARIANCE** — all 10 issued budget bills byte-identical forever; no month's revenue was ever the level; variance history append-only; re-level changed only FUTURE months | — | Σ(recognized revenue) = Σ(actuals) exactly — the level never leaked into revenue; tie-outs hold (BR-LED-007) | BR-BIL-004 · hard rule 4 |
