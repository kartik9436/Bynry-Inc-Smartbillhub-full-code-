# T5-14 — Billing without a plan snapshot (no snapshot, no draft — ever)

---
id: T5-14
tier: 5
guards: [BR-CUS-014, BR-MET-040, BR-BIL-015]
stories: [US-BIL-002, US-CUS-006, US-BIL-006]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
# Snapshot store note: account_plan_assignments is PROPOSED-SCHEMA (billing field-map D-1); the RULE is ratified.
---

**Intent.** Billing prices from the ACCOUNT'S plan snapshot as of service date — never the live unit plan (BR-CUS-014 sc.6). An active account with no snapshot has no lawful price source; guessing (falling back to the unit's current plan) would bill on rates the customer never agreed to. The run must surface the account as an exception and refuse to let it reach drafts — the ratified behavior pinned by US-BIL-002/TC-6 (EP-BIL-01).

**Fixture.** Tenant brazos-bend · account ACC-3055, status Active, on Unit 12C — seeded as a cutover DEFECT: no account_plan_assignments row (normal activation is impossible without a plan, BR-MET-040; only bad legacy data produces this state) · run RUN-2607-A, period 2026-07.

**Fixture amendment (2026-08-22, CR-014 · DEF-556).** Seeded by `seed_journey_fixture.seed_t5_14`. The account, status and missing snapshot are the paragraph's own (**ACC-3055** Active on Unit **12C**, no `account_plan_assignments` row); the RUN moves to an August cycle, because a July-period run posts its journal entries inside the finance-signed LE-1 window. ⚠ The seeder also asserts that `prepare_run` BLOCKS this account with `unit_has_no_plan` — seeding the state without proving the refusal is how a journey asserting *"the run surfaces it as an exception"* passes over an empty exception list.

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions (nothing changed) | Guard |
|---|---|---|---|---|
| 1 | Billing Clerk starts RUN-2607-A; opens S31.2 → Plans tab | ACC-3055 listed under "accounts missing plans/snapshots" as an exception; the run proceeds for everyone else | No draft for ACC-3055; zero priced lines exist for it; the other accounts draft from THEIR snapshots | BR-CUS-014 sc.6 · US-BIL-002/TC-6 |
| 2 | Clerk attempts to push ACC-3055 into drafts from the exceptions view | Refused — no pricing source exists; the engine never falls back to the live unit plan (that fallback is exactly what sc.6 forbids) | No invoice, no lines, no JE; account balance unchanged; audit: attempt-logging not ratified (BR-AUD-001 scope) — assert zero money writes | BR-CUS-014 sc.6 |
| 3 | Adversarial probe: `POST /api/bill-runs/RUN-2607-A/accounts/ACC-3055/draft` direct call | Server-side refusal, same reason — UI exception listing was convenience; the guard is in the rating handoff (priced from the snapshot as of service date, J2 step 7) | Same zero-write assertions | BR-CUS-014 sc.6 |
| 4 | Contrast: a NEW move-in on a plan-less unit is attempted (the front door to this state) | Move-in blocks with message — plan REQUIRED at account activation; the defect state cannot be created through the product | No active account without a snapshot can be minted by any wizard | BR-MET-040 |
| 5 | RECOVERY — the ratified door: staff assign the plan (Change-plan flow US-CUS-016/017 or cutover fix) which writes the snapshot (append-only assignment row + version); then bill ACC-3055 via catch-up sub-run | Snapshot row exists with plan+version, source, actor, reason; catch-up sub-run prices from it as of service date | Exactly one bill for ACC-3055, priced on the snapshot; Pending-billing queue drains; assignment + issue audited | BR-CUS-014 · BR-BIL-015 |
