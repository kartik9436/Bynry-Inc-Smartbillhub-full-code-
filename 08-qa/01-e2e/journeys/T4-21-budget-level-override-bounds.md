# T4-21 — Budget level override within ±30% (x = computed level $242 → y = staff override; band enforced, ±31% refused)

---
id: T4-21
tier: 4
rules: [BR-BIL-017, BR-RAT-043, BR-BIL-004, BR-TEN-041]
stories: [US-BIL-018, US-BIL-019, US-BIL-020]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** x = budget-billing level = the COMPUTED trailing-12-month average, whole $ — **$242** on the WE-8 fixture (trailing actuals $2,904); y = a per-account staff override. The boundary is the OQ-068 closure inside BR-BIL-017: override allowed WITH reason + audit, **bounded ±30% of the computed level** — a request outside the band is refused server-side. The band exists because the level is a collection schedule, not a price (WE-8): let staff flex it for hardship, but never so far that the variance balance becomes a hidden debt engine. Band-edge dollar values are engine-computed per 00-e2e-design.md §5 (the frozen workbook carries the $242 level, not the band edges).

**Fixture.** Tenant brazos-bend · ACC-1047 enrolled in budget billing (plan flag BR-RAT-043; 12-mo history satisfies eligibility) · computed level **$242** (WE-8) · override request A: **$250** with reason "customer requested rounding to expected raise" (inside the band — verified against the harness-computed edges) · override request B: computed level × **1.31** (outside the band by construction).

**Fixture amendment (2026-08-22, CR-014 · DEF-556).** Seeded by `seed_journey_fixture.seed_t4_21`. The account is **ACC-2047**, not ACC-1047 (the cohort's range). The **$242** level, the **$2,904** trailing total and the **±30%** band are the paragraph's own and are unmoved — and the level is COMPUTED by `budget_service.enroll` from twelve seeded actuals rather than written into the status row, so the fixture refuses if the engine ever returns anything but WE-8's figure.

| # | Action | Upstream effect (what recomputes) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Harness verifies the baseline | Level = trailing-12 average, whole $ → **$242**; variance balance runs per WE-8 (Jul actual 292.87 → −50.87 · Aug 231.40 → +10.60 · Sep 198.75 → +43.25 → running −50.87 → −40.27 → +2.98) | budget bill presents the level, actual, and variance columns every month; revenue recognized on ACTUALS, level = collection schedule (non-taxable AR-timing at settle-up) | BR-BIL-017 · WE-8 |
| 2 | Billing Clerk submits override A: level → **$250**, reason given | Server validates against the ±30% band of the computed $242 (edges engine-computed) → INSIDE → accepted; presented level becomes 250 from the next budget bill | audit row: actor, reason, computed level, override value; next bill presents $250; variance ledger keeps accumulating against ACTUALS unchanged | BR-BIL-017 (OQ-068) |
| 3 | Clerk submits override B: computed level × 1.31 | Server REFUSES — outside the ±30% bound; validation error names the band; no partial write | no override row; presented level stays $250 (step-2 state); no audit "executed" row for the refused attempt beyond the standard refusal handling | BR-BIL-017 (OQ-068) |
| 4 | Auto re-level + settle-up continue on the standing parameters | Auto re-level at ±20% drift each 6 mo evaluates against the COMPUTED level machinery; annual settle-up month collects/credits the variance balance as the WE-8 non-taxable AR-timing line; off-budget after 2 missed payments — every parameter a tenant setting (S69 budget-rules family) | settle-up line non-taxable; revenue/tax already recognized monthly — settle-up moves AR timing only; audit | BR-BIL-017 · BR-TEN-041 |
| 5 | **INVARIANCE** — what must NOT have changed | The COMPUTED level record ($242) — the override presents, it never overwrites the computation; every issued budget bill before the override; the variance balance accumulated to date | issued bills byte-identical; override history append-only with reasons; refusing step 3 changed nothing anywhere | BR-BIL-004 · BR-BIL-017 · hard rule 4 |
