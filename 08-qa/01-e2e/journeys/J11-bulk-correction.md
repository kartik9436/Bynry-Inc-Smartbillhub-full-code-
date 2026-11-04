# J11 — Bulk correction (wrong rate on a cycle → preview → Admin approve → credit notes/rebills ×N → re-allocation)

---
id: J11
tier: 2
rules: [BR-BIL-014, BR-BIL-004, BR-PAY-010, BR-PAY-031, BR-LED-003, BR-LED-007, BR-AUD-018, BR-REP-007]
stories: [US-BIL-016, US-BIL-017, US-PAY-008, US-LED-003, US-NOT-001, US-REP-009]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** A whole cycle went out priced wrong; the fix is a WORKFLOW, not an edit. BR-BIL-014 end-to-end at bulk scale: reason → scope → impact preview → the hard approval gate (proven by a refused early execute, attempt-audited per tonight's BR-AUD-018) → staged idempotent execution of credit-note + rebill pairs — the WE-9 pattern (**−247.87 / +227.95 → customer delta −19.92**) on the head fixture, ×N across the cycle — then payment re-allocation that never edits a row.

**Fixture.** Tenant brazos-bend · July cycle, **N = 240** issued bills, water charges overstated (head fixture ACC-1042 = the WE-9 bill: original current 247.87, corrected 227.95) · correction reason code "Rate applied in error" (reference data) · v1 rule: ALL corrections require System Admin approval · aggregate deltas across the other 239 bills **engine-computed** (00-e2e-design.md §5).

| # | Date · action | Handoff contract (what this step leaves) | Downstream assertions (bill · ledger · reports · queue · audit) | Rule |
|---|---|---|---|---|
| 1 | **Jul 15** — clerk opens bulk correction: reason code → scope = run/cycle (July) → **impact preview**: per-bill credit note, rebill lines, GL reversals, balance delta, payment re-allocation plan | Preview persisted as a staged correction set; **NO money-bearing write exists yet** | Zero new invoices/JEs in the books; preview shows ACC-1042 as credit −247.87 / rebill +227.95 / delta −19.92 (WE-9); audit row for correction-created | BR-BIL-014 |
| 2 | **Jul 15** — clerk clicks Execute before approval | **REFUSED** — approval gate holds; refusal writes a security-event **attempt row** (who/what/when/rule); the refused action itself writes NOTHING | Books byte-identical to step 1; attempt row present in audit_log | BR-BIL-014 · **BR-AUD-018** |
| 3 | **Jul 16** — System Admin approves (v1: all corrections) | Approval recorded (approver, timestamp) on the correction set | Audit; still no money movement until execution | BR-BIL-014 |
| 4 | **Jul 16** — staged idempotent EXECUTION: per bill, credit note (full GL reversal) + rebill (own GL stamps) — head fixture **−247.87 + 227.95**; per-bill results table; re-running the execution = no-op | 240 credit-note/rebill pairs, all append-only; originals untouched; aggregate delta engine-computed | Ledger: linked reversal pairs per bill (BR-LED-003); net revenue/tax effect −19.92 per WE-9-shaped bill (LE V-3 pattern); corrections report shows the batch (US-REP-009, posting basis label); audit per bill | BR-BIL-014 · BR-BIL-004 |
| 5 | **Jul 16** — payment re-allocation: paid-in-full accounts → **19.92 carries as account credit** (BR-PAY-010 overpayment pattern); partially-paid accounts → reversing allocation rows + new rows, reason + audit | No allocation row edited, ever; credits visible on accounts, auto-apply next bill, refundable on request | Allocation history append-only (BR-PAY-031); AR delta ties to the ledger delta exactly (BR-LED-007) | BR-PAY-010/031 |
| 6 | **Jul 16** — delivery: corrected bills render on the CURRENT template version citing the original bill (WE-9); one queue row per corrected bill per channel | Delivery records queued → dispatched in batches (BR-NOT-005) | Per-run delivery dashboard shows the correction wave; audit | BR-NOT-005 |
| 7 | **INVARIANCE** — every original July invoice byte-identical; the correction set executes exactly once (idempotent); no bill's computed amount was hand-adjusted anywhere in the flow | — | Append-only books; tie-outs hold; the approval + attempt rows reconstruct the whole gate history | hard rule 4 · BR-LED-007 |
