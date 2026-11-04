# T5-08 — Export an OPEN period (the ERP never receives numbers that can still move)

---
id: T5-08
tier: 5
guards: [BR-LED-017, BR-LED-006, BR-LED-018, NFR-16]
stories: [US-LED-015, US-LED-016]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Export requires the covered period CLOSED (BR-LED-017, L-3b: "the ERP never receives numbers that can still move"). An open period's totals can still change — late reads, corrections, reversals — so exporting it would hand the accountant figures that silently drift from the books. The system must refuse the export until the month is closed.

**Fixture.** Tenant brazos-bend · period 2026-07 OPEN (run RUN-2607-A issued; payments still arriving) · period 2026-06 CLOSED with recorded batch EXP-2606-01.

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions (nothing changed) | Guard |
|---|---|---|---|---|
| 1 | Finance user opens S42 and requests an export covering 2026-07 | Refused: period not closed — 409/422 class; IS-7 failed state names the close requirement and links the close checklist | No export batch row created; no file; audit: attempt-logging not ratified (BR-AUD-001 scope) — assert zero batch rows | BR-LED-017 |
| 2 | Same user tries the weekly-JE granularity for a week fully inside open 2026-07 | Refused identically — granularity choice never bypasses the closed-period requirement (both granularities cover a CLOSED window) | Still zero batches covering any part of 2026-07 | BR-LED-017 |
| 3 | User attempts `POST /api/exports {period: 2026-07}` directly | Same refusal server-side; UI gating was convenience only | Ledger rows untouched; recorded-batch registry unchanged | BR-LED-017 · NFR-16 |
| 4 | Contrast: user exports CLOSED 2026-06 dimension-level CSV extracts | Allowed — closed windows export (subject to T5-07 idempotency) | Extract matches the recorded batch's figures | BR-LED-004 |
| 5 | RECOVERY — the ratified door: Finance closes 2026-07 per the close checklist (runs issued, batches reconciled, bank rec current, accruals posted, remittance recorded); incomplete items = WARN + CONFIRM with reason, never silent | Close succeeds (audited); period locks; export of 2026-07 now creates recorded batch EXP-2607-01 | Exported figures can no longer move (late events auto-forward per BR-TEN-038 — see T5-09) | BR-LED-006 · BR-LED-018 · BR-LED-017 |
