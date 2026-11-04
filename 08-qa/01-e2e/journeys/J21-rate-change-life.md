# J21 — Rate-change life (v4 publish → next run on new prices, history on old, back-bill spans both)

---
id: J21
tier: 2
rules: [BR-RAT-021, BR-RAT-026, BR-BIL-018, BR-BIL-004, BR-CUS-040, BR-LED-002, BR-REP-021, BR-REP-001]
stories: [US-RAT-005, US-RAT-010, US-RAT-011, US-RAT-012, US-BIL-013, US-BIL-026, US-LED-002, US-REP-002]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Prices change; history does not. A water-tariff v4 publishes effective Apr 1 and three things must be simultaneously true forever after: bills for periods AFTER the boundary price on v4, every bill for a period BEFORE it stays priced (and reprints) on v3, and a back-bill that SPANS the boundary prices each sub-period on ITS version — the frozen WE-10 book: v3 months **45.10**, v4 months **47.84**, six period-labeled groups totalling **305.18**. This is the 7-year-reproducibility promise exercised end-to-end.

**Fixture.** Tenant brazos-bend · water tariff **v3** (T1 4.00 / T2 6.50 / base 8.00) → **v4** (4.25 / 6.85 / 8.50) effective **Apr 1, 2026** (B2 tariff_versions) · reference account 6 kgal/mo · back-bill account ACC-1290, unbilled Jan–Jun, discovered Jul · standalone monthly bill TOTALS incl. tax **engine-computed** (00-e2e-design.md §5 — only the WE-10 pre-tax period figures and the combined 305.18 are frozen).

| # | Date · action | Handoff contract (what this step leaves) | Downstream assertions (bill · ledger · reports · queue · audit) | Rule |
|---|---|---|---|---|
| 1 | **Mar 10** — Admin drafts and publishes water **v4 effective Apr 1** (effective-dated version; bulk update path records rate_change_batches + per-entity log with reason) | tariff_versions carries v3 (…–Mar 31) and v4 (Apr 1–…) side by side; nothing recomputes at publish time | Zero change to any issued bill or draft at publish; rate-change history report lists the version + reason (BR-REP-021, generic viewer v1); audit | US-RAT-010/011 |
| 2 | **Apr 1** — March cycle run (billing the March period) prices on **v3**: the 6 kgal fixture's period group = usage 26.50 + base 8.00 + sewer 10.60 = **45.10** pre-tax (WE-10 v3 month) | Last v3-priced cycle bill issued, GL-stamped, immutable | Balanced JE; posting-basis billed KPI labeled (BR-REP-001); delivery queued; audit | BR-RAT-026 · BR-BIL-011 |
| 3 | **May 1** — April cycle run prices on **v4**: period group = 28.10 + 8.50 + 11.24 = **47.84** pre-tax (WE-10 v4 month; bill total engine-computed) | First v4-priced bill; the boundary is the SERVICE PERIOD, never the run date | Revenue-by-service slice reflects the new prices only for April-and-later periods (BR-LED-002 dimensions); audit | BR-RAT-021/026 |
| 4 | **May 12** — reprint the MARCH bill | Renders the ISSUED invoice **verbatim** — v3 prices forever; reprints never recompute | Byte-identical document; no engine call re-prices history | **BR-CUS-040** · BR-BIL-004 |
| 5 | **Jul 9** — back-bill ACC-1290 for Jan–Jun (approval-gated, reason-coded): ONE bill, **6 period-labeled groups** — Jan–Mar on v3 **45.10/mo** + Apr–Jun on v4 **47.84/mo** → taxable **278.82** → tax **26.36** → total **305.18** (WE-10) — each period priced on ITS version, never today's rates | Immutable back-bill; per-group version linkage visible in line detail (US-BIL-026) | One balanced JE; back-bill report row (BR-REP-007); window respects the tenant cap (12 mo default — this span is within it); delivery queued; audit | **BR-BIL-018** |
| 6 | **INVARIANCE** — v3 remains fully reproducible (any pre-Apr period re-rated in a correction flow would still price on v3); no issued bill changed when v4 published or when the back-bill issued; the version timeline is append-only | — | 7-year reproducibility holds (US-RAT-010); tie-outs clean (BR-LED-007); every publish/approval audited (hard rule 7) | BR-BIL-004 · hard rule 4 |
