# T4-15 — Meter swap via reassign-with-final-read (x = old meter on unit → y = new meter; the bill uses BOTH registers' spans)

---
id: T4-15
tier: 4
rules: [BR-MET-043, BR-MET-019, BR-MET-053, BR-MET-046, BR-MET-049, BR-RAT-038, BR-BIL-011]
stories: [US-AST-009, US-MET-010, US-RAT-012, US-BIL-007]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** x = meter M-2201 serving unit 104; y = meter M-3407 serving it, swapped mid-cycle through the ONLY ratified door: the assets reassign flow WITH final-read capture (BR-MET-043 "untag = assets reassign flow with final read"). The boundary matters because consumption is register arithmetic per meter (BR-MET-019): the cycle's usage must be the SUM of two spans — old meter (cycle start → its final read) + new meter (its initial read → cycle end) — never a single delta across two physical registers. A swap without the final read would either lose or invent consumption.

**Fixture.** Tenant brazos-bend · unit 104 (Vega Apts), ACC-1044 active · electric meter M-2201 (multiplier 1) swapped **Jul 18**: final read committed on M-2201, initial read committed on M-3407 (explicit UoM, register digits set) · span dollar figures are engine-computed per 00-e2e-design.md §5 — the law asserted here is the two-span structure.

**Fixture amendment (2026-08-22, CR-014).** Seeded by `seed_journey_fixture.seed_t4_15`. The account is **ACC-2044** (the cohort's range); unit **104** and meter **M-2201** are the paragraph's own, and the meter carries a committed prior read so step 1's final read has a span to compute against. The swap itself — final read on M-2201, initial read on M-3407 — is the journey's act and is deliberately NOT seeded: a fixture that performed it would leave the journey asserting over its own answer.

| # | Action | Upstream effect (what recomputes) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Clerk runs the assets **Reassign** flow on M-2201 (unit → inventory) — the flow REQUIRES a final read | Final read for M-2201 committed Jul 18 (append-only, channel `total`); M-2201's assignment row closes; asset returns to inventory (or proceeds to retirement via its own lifecycle) | `asset_assignments` history rows (old closed, with final-read link); audit rows; read enters committed status per the lifecycle | BR-MET-043 · BR-MET-053 |
| 2 | Clerk assigns M-3407 to unit 104 with its initial (install) read | New assignment row from Jul 18; initial read committed; UoM explicit and matching the billed unit (or a conversion factor defined — else rating blocks per BR-RAT-038); plan-required channel set tracked for the new meter | unit detail shows the meter succession; completeness tracking now expects M-3407's channels | BR-MET-043 · BR-MET-049 · BR-RAT-038 |
| 3 | Jul cycle bill run | Consumption = TWO register spans, each `(current − prior) × multiplier` on ITS OWN meter: M-2201 cycle-start→final-read span + M-3407 initial-read→cycle-end span; the engine sums the quantities into the period's priced usage (values engine-computed, §5 harness) | bill usage detail attributes both meters' spans; no negative or double-counted quantity; one balanced JE; delivery queued | BR-MET-019 · BR-BIL-011 |
| 4 | Harness inspects lineage + reports | — | read completeness report (channel-aware) shows the unit complete for Jul; both meters' read chains intact and queryable; premises-level money traceability holds — the UNIT never moved, only its asset (BR-MET-046) | BR-MET-046 · BR-REP-001 |
| 5 | **INVARIANCE** — what must NOT have changed | M-2201's historical reads and every previously issued bill byte-identical; the final read SUPERSEDES nothing — it appends; no read on M-2201 is accepted after retirement (T5-16 guard) | read rows append-only with intact chains; assignment history append-only; unit↔premises linkage untouched | BR-MET-053 · BR-MET-046 · hard rule 4 |
