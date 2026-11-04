# T4-07 — Rate version publish mid-history (x = tariff v3 in force → y = v4 from Apr 1; history reprices on ITS version)

---
id: T4-07
tier: 4
rules: [BR-RAT-037, BR-RAT-007, BR-RAT-017, BR-BIL-018, BR-BIL-004]
stories: [US-RAT-010, US-RAT-012, US-BIL-013, US-BIL-005]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** x = water tariff v3 (T1 4.00 / T2 6.50 / base 8.00); y = v4 (4.25 / 6.85 / 8.50) published effective Apr 1 — the WE-10 fixture. The boundary is the DB-5 law (B2 §DB register): *effective-dated pricing via tariff_versions — history bills on its version, never current*. Publishing a new version must change NOTHING about how any past service date prices: a rebill or back-bill of March uses v3 forever; only service dates ≥ Apr 1 see v4. This is the 7-year reproducibility guarantee (BR-RAT-017) exercised as a transition.

**Fixture.** Tenant brazos-bend · water service, 6 kgal/mo Jan–Jun (WE-10) · v3 in force through Mar 31, v4 published Apr 1 · per-version monthly figures (frozen workbook): Jan–Mar **$45.10/mo** (26.50 usage + 8.00 base + 10.60 sewer) · Apr–Jun **$47.84/mo** (28.10 + 8.50 + 11.24).

| # | Action | Upstream effect (what recomputes) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | System Admin publishes tariff **v4 effective Apr 1** via the single rate update (S11 versioning) | NEW `tariff_versions` row (windows non-overlapping per B2 EXCLUDE); append-only `rate_change_log` row with before/after jsonb, actor, required reason; v3 row untouched — in-force versions are NEVER edited in place | audit row; version list shows v3 (…Mar 31) + v4 (Apr 1…); no bill, JE, or report number moves at publish time — publishing prices nothing by itself | BR-RAT-037 |
| 2 | Back-bill runs for the 6 unbilled months Jan–Jun (WE-10) | Rating resolves the version PER SUB-PERIOD by service date: Jan/Feb/Mar priced on v3 → 45.10/mo; Apr/May/Jun on v4 → 47.84/mo — never today's rates | one bill, 6 period-labeled groups; taxable **$278.82** → tax **$26.36** → total **$305.18** (WE-10); balanced JE; approval + reason code per BR-BIL-018 | BR-BIL-018 · BR-RAT-007 · DB-5 |
| 3 | A March-period single-bill CORRECTION (J6) executes after v4 exists | The rebill reprices March against **v3** — the version in force on the service date — regardless of what is published today | rebill line group carries v3 rates (45.10 basis); credit note references the original; both new rows GL-stamped | BR-RAT-007 · BR-BIL-014 |
| 4 | Next regular cycle run (Apr period) | Prices on **v4**: 47.84 monthly shape | Apr bill lines at v4 rates; revenue KPI delta = the issued totals, posting basis, header labeled | DB-5 · BR-REP-001 |
| 5 | **INVARIANCE** — what must NOT have changed | Every ISSUED historical invoice byte-identical after the publish; v3's stored rates unmodified (append-only version chain); no draft anywhere re-priced retroactively except through the explicit, approval-gated flows above | `tariff_versions` v3 row + `rate_change_log` history immutable; 7-year reproducibility holds: re-running the March pricing at any future date yields the same v3 figures | BR-RAT-017 · BR-BIL-004 · hard rule 4 |
