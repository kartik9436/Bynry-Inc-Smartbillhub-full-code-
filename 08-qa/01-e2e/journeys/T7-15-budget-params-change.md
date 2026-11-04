# T7-15 — Config change: budget params (re-level cadence + settle-up month — next evaluation only)

---
id: T7-15
tier: 7
knob: relevel_cadence_months 6 → 3 · settle_up_month 4 → 7 (S66/S69 budget-rules card, BR-TEN-041)
rules: [BR-BIL-017, BR-BIL-021, BR-TEN-016, BR-TEN-020]
stories: [US-TEN-010, US-BIL-018, US-BIL-019, US-BIL-020]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Every budget parameter is a tenant setting seeded with the BR-BIL-017 defaults (level = trailing-12 avg whole $, re-level at ±20% drift each 6 months, annual settle-up month, off-budget after 2 missed). Changing the cadence and the settle-up month must alter only the NEXT evaluation and the NEXT settle-up: the enrolled account's level, its running variance balance, and every issued budget bill are derived/issued facts that a settings save may never touch.

**Fixture.** Tenant brazos-bend, budget settings at seeded defaults, `settle_up_month=4` (April), `relevel_cadence_months=6` · account ACC-1140 enrolled: level **97** (whole $), variance balance running at **-0.41** after the latest bill (money-triples `flat,budget` rows: actual 97.41 vs level 97), `last_leveled_at` = 2026-05-01 · April 2026 settle-up already billed (its line issued) · System Admin Alex Reed.

**Fixture amendment (2026-08-22, CR-014 · DEF-556).** Seeded by `seed_journey_fixture.seed_t7_15`. The account is **ACC-2140** (the cohort's range). Level **97**, variance **-0.41**, `settle_up_month` **4** and cadence **6** are the paragraph's own; the variance is PRODUCED by `record_bill` putting the money-triples `flat,budget` actual **97.41** against the level, never typed. ⚠ **NOT SEEDED, and named rather than faked:** *"April 2026 settle-up already billed (its line issued)"*. An issued settle-up line dated April 2026 sits before the LE-1 cutover (2026-06-30), so it would post a journal entry into the signed book. The step that needs it — that changing `settle_up_month` does not disturb an already-issued settle-up — cannot be asserted on this cohort and is reported rather than back-dated.

| # | Actor + action | Expected outcome (contract) | Downstream assertions (upstream/downstream) | Rule |
|---|---|---|---|---|
| 1 | Baseline: ACC-1140's budget state | Level 97, variance -0.41, cadence gate says next re-level eligibility = 2026-11-01 (6 mo after last_leveled_at); April's settle-up line stands as an issued, non-taxable AR-timing line | account_budget_status rows present (r10 #5); variance derivation append-only | BR-BIL-017 |
| 2 | Alex changes `relevel_cadence_months` 6→3 and `settle_up_month` 4→7 on the budget-rules card; atomic tab save | Toast → ONE audit row `billing_settings.updated` with both changed fields in before/after | BR-TEN-016 shape · BR-AUD-011: one atomic save = one row | BR-TEN-016 · BR-BIL-021 |
| 3 | Immediate re-read of ACC-1140 | Level STILL 97 — the save triggers no re-level; variance STILL -0.41; no settle-up line appears retroactively for July of the past year | Settings save is not an evaluation event | BR-BIL-017 · BR-TEN-020 |
| 4 | Next re-level evaluation runs (system job) | Cadence gate now evaluates on the 3-month cadence (server-side, per config in force at evaluation time); re-level fires only if drift exceeds the (unchanged) ±20%; any new level is a NEW derivation with `last_leveled_at` updated | With fixture drift below 20%, level stays 97 — cadence changed, threshold logic proven independent | BR-BIL-017 |
| 5 | The next settle-up renders in JULY (month 7), not April | The 2027 settle-up line lands on the July bill: variance collected/credited as the non-taxable AR-timing line, balance resets; April 2026's already-issued settle-up line untouched | Exactly one settle-up per cycle-year; no double-settle from the month move | BR-BIL-017 · WE-8 |
| 6 | INVARIANCE — sweep issued budget bills, variance history, postings before/after step 2 | Zero restated rows: every issued bill still shows level/actual/variance as printed; variance trail continuous across the config change; reprints pinned | Forward-only proven for a multi-knob save | BR-TEN-020 · NFR-22 |
