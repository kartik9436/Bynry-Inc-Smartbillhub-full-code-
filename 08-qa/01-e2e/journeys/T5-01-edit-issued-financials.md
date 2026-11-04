# T5-01 — Edit issued invoice / cleared payment / posted JE (append-only stands)

---
id: T5-01
tier: 5
guards: [BR-BIL-004, BR-PAY-002, BR-LED-003, BR-AUD-002, NFR-15]
hard_rules: [4]
stories: [US-BIL-026, US-BIL-015, US-PAY-010, US-LED-013, US-AUD-001]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** The system must REFUSE every UPDATE/DELETE against an issued invoice, an invoice line, a cleared payment, a posted journal entry, and any audit_log row — at the UI (no affordance), the API (no mutating route), and the DB (trigger/enforcement per B2). Hard rule 4 (CLAUDE.md/B8): financial history is append-only; if any of these rows can change in place, every downstream number (AR, ledger, exports, 7-yr reproducibility per NFR-7/15) is unprovable. Corrections exist — but only as NEW rows.

**Fixture.** Tenant brazos-bend · account ACC-1042 · issued bill BL-2607-0142 total **$97.41** (expected/money-triples.csv row `flat,cycle,full`) · cleared ACH payment PMT-3308 $97.41 · posted issue-JE JE-2607-0142 (balanced DR AR 97.41 / CR revenue+tax buckets).

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions (nothing changed) | Guard |
|---|---|---|---|---|
| 1 | Billing Clerk opens BL-2607-0142 (S30 detail) and looks for any edit affordance on header or lines | None exists: no Edit action in the IS-6 row dropdown for status=issued; document renders read-only | Invoice + invoice_lines rows byte-identical; rendered PDF byte-equivalent to issue-time render (BR-BIL-026) | BR-BIL-004 |
| 2 | Same clerk issues `PATCH /api/invoices/BL-2607-0142` (amount 89.00) via API client | Refused: no mutating route on issued invoices — 405/404 class, IS-7 failed-with-retry NOT offered (retry cannot succeed); error names the correction workflow | No UPDATE executed; invoice total still 97.41; AR unchanged; ledger balanced and unchanged; audit: attempt-logging not ratified (BR-AUD-001 scope = executed money actions) — assert zero new money-table rows | BR-BIL-004 · hard rule 4 |
| 3 | System Admin attempts `PATCH /api/payments/PMT-3308` (amount, method) and `DELETE /api/payments/PMT-3308` | Refused (payment is out of processing): 405/409 class; message posture points to Reverse (new reversing row), never edit | payments row untouched; allocations rows untouched (BR-PAY-031 reapply is the only rebuild path); account balance unchanged | BR-PAY-002 · NFR-15 |
| 4 | Finance user attempts to edit posted JE-2607-0142 lines in the journal (S56 list → detail) | UI shows one-click **Reverse + repost** only; direct edit refused server-side; drafts are the only editable JEs | journal_entries/journal_lines rows untouched; trial balance for the period identical before/after attempt | BR-LED-003 · hard rule 4 |
| 5 | Engineer attempts direct SQL `UPDATE audit_log SET ...` / `DELETE FROM audit_log` on the trail rows for steps above | Blocked by trigger enforcement — no UPDATE/DELETE path exists anywhere (UI, API, service, DB) | audit_log row count and content unchanged; append-only trigger fires | BR-AUD-002 |
| 6 | RECOVERY — the ratified doors: correction workflow for the bill (credit note/rebill, approval-gated), reversing row for the payment, Reverse+repost for the JE | Each path succeeds as NEW rows: credit note references BL-2607-0142 (original untouched, GT-6); reversing payment row links PMT-3308; mirror JE links JE-2607-0142 + prefilled new draft | Originals still immutable; every new row balanced and audited (BR-AUD-001) | BR-BIL-014 · BR-PAY-002 · BR-LED-003 |
