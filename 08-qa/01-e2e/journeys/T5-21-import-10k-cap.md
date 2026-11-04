# T5-21 — Bulk import over 10,000 rows (the file cap rejects at staging)

---
id: T5-21
tier: 5
guards: [BR-AST-034, BR-MET-038, BR-CUS-051, NFR-2]
stories: [US-AST-010, US-CUS-019, US-MET-004]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Every bulk import is STAGED with per-row validation and a **10,000-row-per-file cap** — assets (BR-AST-034), units (BR-MET-038), accounts (BR-CUS-051); NFR-2 makes it the platform import discipline. An uncapped file turns staging validation into an unbounded job and its error report into an unreadable wall. The system must reject the oversized file BEFORE staging a single row, tell the user the count, and point at splitting.

**Fixture.** Large-tenant fixture lakeview-mud · `assets-cutover.csv` with **12,481 rows** · same content split into `assets-cutover-1.csv` (10,000 rows) + `assets-cutover-2.csv` (2,481 rows).

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions (nothing changed) | Guard |
|---|---|---|---|---|
| 1 | System Admin uploads `assets-cutover.csv` (12,481 rows) to the assets bulk import (US-AST-010) | Refused at file acceptance: row count 12,481 > 10,000 — 422 class; IS-7 failed state shows the count and the cap and instructs splitting; no staging preview opens | ZERO rows staged (no batch row, no per-row records); assets table untouched; no partial acceptance of the first 10,000 | BR-AST-034 · NFR-2 |
| 2 | Same probe on the accounts onboarding upload (US-CUS-019) and the units CSV path (US-MET-004) with 10,001-row files | Identical refusal on every import surface — the cap is the shared import standard | No staged batches anywhere; no "N created · N failed" summary exists (nothing ran) | BR-CUS-051 · BR-MET-038 |
| 3 | Adversarial probe: direct `POST /api/imports/assets` with the oversized payload | Server-side count check refuses before validation work begins; UI check was convenience | No job enqueued; audit: attempt-logging not ratified (BR-AUD-001 scope) — assert zero import artifacts | NFR-2 |
| 4 | Contrast: admin uploads the two split files in sequence | Both accepted into staging; per-row validation runs; each commit reports "N created · N failed" with error report; skip-errors ON per the standard | Batches 1 and 2 committed independently; compliance stamps (file+SHA-256) recorded per batch; total created = rows passing validation across both files | BR-AST-034 · BR-MET-038 |
| 5 | RECOVERY — the ratified door: split oversized files into ≤10,000-row parts; premises/units must exist before asset refs resolve (unmatched refs error per BR-AST-034), so split along premises boundaries where possible | Split uploads succeed; re-upload of a matched asset# updates SPEC fields only (billing-affecting fields never via upload) | Full cutover lands across N capped batches, each staged, validated, stamped, and summarized | BR-AST-034 · NFR-2 |
