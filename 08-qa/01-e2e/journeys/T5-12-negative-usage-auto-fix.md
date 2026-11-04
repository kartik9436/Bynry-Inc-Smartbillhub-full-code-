# T5-12 — Negative-usage auto-fix attempt (the hard error stands)

---
id: T5-12
tier: 5
guards: [BR-MET-052, BR-MET-015, BR-MET-019, BR-MET-016]
stories: [US-MET-008, US-MET-011, US-MET-012]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Negative usage (current < prior after the multiplier) is a HARD ERROR, never auto-fixed (BR-MET-052). The system must not swap the values, take an absolute value, or silently assume a register rollover — any of those manufactures consumption and therefore money. The error must stand until a human resolves it through an explicit, reason-coded disposition (BR-MET-015); rollover is a deliberate classification (OQ-009 lineage), never a guess.

**Fixture.** Tenant brazos-bend · meter MTR-0451 (electric, ×1 multiplier, channel `total`) · prior committed read 45,210 (2026-06-14) · import row current 44,890 (2026-07-14) → computed consumption −320 kWh (BR-MET-019 formula, unrounded).

**Fixture amendment (2026-08-22, CR-014).** The prior committed read 45,210 is seeded dated **2026-07-01** — the paragraph's 2026-06-14 predates MTR-0451's own T5-16 install date of Jul 1. The VALUE is the load-bearing part: the import row 44,890 still computes **−320 kWh** against it (BR-MET-019). The import row itself stays the journey's act.

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions (nothing changed) | Guard |
|---|---|---|---|---|
| 1 | Clerk imports `reads-CYC-A-2026-07.csv` containing the 44,890 row; validation runs at staging | Row flagged severity ERROR "negative usage" with the threshold math shown (45,210 → 44,890 = −320); no auto-correction of any kind applied | Staged only — zero meter_reads rows committed (BR-MET-012); the stored row value is EXACTLY 44,890 as filed (no swap/abs/rollover rewrite) | BR-MET-052 · BR-MET-019 |
| 2 | Clerk tries to commit the batch with the error unresolved | Commit refused: errors must be resolved (reject / override / investigate) before post — 422 class, IS-7 inline-validation posture listing the blocking rows | No meter_reads row for MTR-0451/2026-07-14; billing inputs untouched; cycle completeness bar still shows the meter outstanding | BR-MET-015 |
| 3 | Adversarial probe: clerk attempts a bulk "accept all warnings" sweep hoping the error rides along | Errors are NOT warnings — the sweep skips the row; it remains ERROR; no accept-with-reason path exists at error severity without an explicit per-row disposition | Row disposition still empty; commit still blocked; audit: the disposition record (when made) IS the ratified attempt-trail (BR-MET-015 "disposition+reason stored per row") | BR-MET-015 · BR-MET-052 |
| 4 | Probe: API `POST /api/read-imports/rows/{id}/autofix` or any equivalent | No such path exists (404/405 class) — never auto-fixed is a system property, not a permission | Nothing written | BR-MET-052 |
| 5 | RECOVERY — the ratified doors, each explicit + reason-coded: (a) investigate → true register ROLLOVER → classify per the rollover rule (OQ-009 lineage) with reason; (b) data-entry error → REJECT the row and re-import the correct value; (c) unrecorded meter swap → asset reassign with final-read capture (US-AST-009), then re-import | Chosen disposition stored per row with reason; commit proceeds only after every error resolved; corrections to committed history travel as supersede rows (BR-MET-016) | Exactly one truthful consumption reaches rating; original filed value stays visible in the lineage | BR-MET-015 · BR-MET-016 |
