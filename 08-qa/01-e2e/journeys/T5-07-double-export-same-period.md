# T5-07 — Double accounting export of the same covered window

---
id: T5-07
tier: 5
guards: [BR-LED-004, BR-LED-017, NFR-16, NFR-20]
stories: [US-LED-016, US-INT-009]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Accounting exports are recorded batches, IDEMPOTENT per covered window — "no double-handover" (BR-LED-004; NFR-16: re-run blocked). If the same closed period can be exported twice, the tenant's ERP books the revenue twice and SMARTBillHub caused it. The system must refuse a second export of an already-covered window and route the user to the recorded batch (re-DOWNLOAD, never re-export).

**Fixture.** Tenant brazos-bend · period 2026-06 CLOSED · recorded export batch EXP-2606-01 (one summary JE per GL account, QBO file, default granularity per BR-LED-017).

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions (nothing changed) | Guard |
|---|---|---|---|---|
| 1 | Finance user opens S42 and requests a new export for period 2026-06, summary granularity | Refused: covered window already exported — 409 class, IS-7 failed state links EXP-2606-01 (who ran it, when, file) | No second export batch row; no new file generated; ERP hand-off count for 2026-06 remains exactly 1 | BR-LED-004 · NFR-16 |
| 2 | Same user retries via `POST /api/exports {period: 2026-06}` after a timeout (client retry storm ×3) | Every call blocked on the recorded-batch idempotency — same refusal, same link | export batch count unchanged; ledger rows untouched (export never mutates books); audit: attempt-logging not ratified (BR-AUD-001 scope) — assert zero new batch rows | BR-LED-004 · NFR-16 |
| 3 | User tries the OTHER granularity (weekly JEs) over the same already-covered 2026-06 window | Refused — idempotency is per covered window, whichever granularity was chosen; the window is handed over once | Still one recorded batch covering 2026-06; no overlapping-window batch exists | BR-LED-017 |
| 4 | Auditor drills a 2026-06 figure from the recorded batch back to its dimensioned journal lines | Drill-back resolves every figure (contrast/positive assertion — the recorded batch is complete evidence) | Figures reconcile to journal_lines exactly; nothing regenerated | BR-LED-004 · NFR-20 |
| 5 | RECOVERY — the ratified doors: re-DOWNLOAD EXP-2606-01's file from the recorded batch; a genuine 2026-06 correction posts (auto-forwarded) into the earliest OPEN period and rides the NEXT window's export | Download succeeds from the batch record; July correction JE appears in the 2026-07 export when that window closes | 2026-06 hand-over stays single; correction reaches the ERP exactly once, in the next covered window | BR-LED-004 · BR-TEN-038 |
