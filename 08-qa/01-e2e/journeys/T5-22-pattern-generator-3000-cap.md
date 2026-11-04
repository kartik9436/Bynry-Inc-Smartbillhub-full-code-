# T5-22 — Pattern generator over 3,000 units per run (the cap blocks generation)

---
id: T5-22
tier: 5
guards: [BR-MET-005, BR-MET-038, NFR-2]
stories: [US-MET-004]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** The unit pattern generator is capped at floors × units/floor ≤ **3,000 per run** (BR-MET-005/038, NFR-2). Pattern generation is a multiplication — one typo in "units per floor" can 10× the intended output; the live preview plus the hard cap are what keep a fat-finger from minting thousands of phantom units (each a future billing target). The generator must refuse to run over the cap, before creating anything.

**Fixture.** Tenant lakeview-mud · Premises PRM-031 "Harbor Tower" · S16 pattern step: 40 floors × **80** units/floor = 3,200 (typo for 8/floor = 320) · token pattern `{floor}-{seq}` (grammar per BR-MET-031).

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions (nothing changed) | Guard |
|---|---|---|---|---|
| 1 | Admin enters 40 floors × 80 units/floor in the pattern step | Live preview computes 3,200 and flags it over the 3,000/run cap immediately (IS-7 inline form validation); Generate is disabled with the count and cap shown | Zero units created; preview is computed display only; premises untouched | BR-MET-005 |
| 2 | Admin attempts to submit anyway (or replays `POST /api/units/pattern-generate {floors:40, perFloor:80}`) | Server refuses: 422 class, same count-vs-cap message — the cap is enforced server-side, not just in the preview | No unit rows; no batch/audit artifacts; audit: attempt-logging not ratified (BR-AUD-001 scope) — assert zero writes | BR-MET-005 · BR-MET-038 |
| 3 | Contrast probe: 40 × 8 = 320 units with `{floor}-{seq}` | Preview shows 320 with sample labels (e.g., 01-001…); Generate enabled; run creates exactly the previewed set | 320 unit rows, labels unique per (tenant, premise) per BR-MET-002; creation audited (BR-MET-048) | BR-MET-005 · BR-MET-002 |
| 4 | Probe: admin tries to chain runs to exceed 3,000 in one sitting (3,000 + 200) | Each run ≤3,000 is allowed — the cap is per RUN by design; the second run generates its 200 | Two audited runs; total 3,200 units exist legitimately; no single run exceeded the cap | BR-MET-005 |
| 5 | RECOVERY — the ratified doors for genuinely large builds: multiple pattern runs ≤3,000 each, or the units CSV path (≤10,000 rows/file, staged with per-row errors — T5-21) | Bulk build completes across capped runs/files; every batch staged, summarized ("N created · N failed"), audited | Premises/unit money-traceability intact (units never move between premises, BR-MET-046) | BR-MET-038 · BR-MET-005 |
