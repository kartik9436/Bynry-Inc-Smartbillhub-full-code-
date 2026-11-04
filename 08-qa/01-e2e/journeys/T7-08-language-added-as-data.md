# T7-08 — Language added later: catalog + variants as DATA, zero code change, usable end-to-end

---
id: T7-08
tier: 7
language: fr (added post-launch as data)
rules: [NFR-37, BR-SHL-030, BR-TEN-042, BR-CUS-064, BR-NOT-006, TD-16]
stories: [US-TEN-006, US-SHL-013, US-NOT-005, US-NOT-006, US-BIL-022]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** NFR-37 made executable: adding a language is a DATA change — a platform catalog row + translation catalog + tenant template variants — never a deploy. The seed set (en/es/es-MX/de/hi) is "data-driven, extensible" (BR-TEN-042); this journey adds French and rides it from picker to pinned document, with the deployed build hash asserted UNCHANGED across the whole journey.

**Fixture.** Tenant brazos-bend, default en · platform language catalog = platform-shell-owned data asset (B2 r16 #6) · harness records the running build/release hash before step 1 · account ACC-1088 Luc Fontaine, Residential · money-triples row `flat,cycle,full`: 97.41.

| # | Actor + action | Expected outcome (contract) | Downstream assertions (upstream/downstream) | Rule |
|---|---|---|---|---|
| 1 | Platform ops adds fr to the language catalog + loads the fr UI translation catalog (data load, no deploy) | Catalog row + strings land as data; ONE catalog source builds both client bundles (TD-16 #1 / NFR-37) | Build hash unchanged; no migration beyond the seeded data path | NFR-37 · BR-SHL-030 |
| 2 | fr appears in all three pickers: tenant default (S8 Regional), per-user UI override, account preferred language | Pickers are catalog-driven — new entry shows without code; en/es/es-MX/de/hi untouched | Selecting fr as a per-user override renders fr chrome immediately | BR-TEN-042 · BR-SHL-030 · BR-CUS-064 |
| 3 | Tenant authors fr variants for the bill + receipt classes in the designers (S91+) | Variants save as new rows in the type × category × language variant space; publish per template rights | Version lifecycle identical to any language (BR-BIL-027 rights) | BR-NOT-006 |
| 4 | ACC-1088 preferred_language=fr; bill run issues BL-2608-0260 ($97.41) | Renderer selects (bill, Residential, fr); pin records language=fr — the new language rides the SAME pipeline end-to-end | Delivery queues; payment → receipt renders fr; classes without fr variants fall back to tenant default (BR-NOT-006) | BR-CUS-064 · BR-NOT-006 · TD-16 |
| 5 | Harness re-reads the build hash after the full ride | Identical to the pre-step-1 hash: language add was provably zero-code | CI check: journey fails if any deploy occurred mid-ride | NFR-37 |
| 6 | INVARIANCE — pre-existing documents (T7-01..06 pins) re-checked after fr exists | Every prior pin renders its own pinned language; adding a language restates NOTHING — no document, posting, or history row anywhere changed | Catalog/variant writes audited; ledger untouched | BR-NOT-006 · BR-TEN-020 · NFR-22 |
