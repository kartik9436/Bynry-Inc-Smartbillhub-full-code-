# T4-05 — Active → Marked disconnect → pay → Active (behavior class BILLABLE throughout)

---
id: T4-05
tier: 4
rules: [BR-CUS-055, BR-PAY-017, BR-PAY-021, BR-PAY-032, BR-PAY-010, BR-CUS-039, BR-NOT-009, BR-REP-012, BR-BIL-001]
stories: [US-CUS-008, US-CUS-015, US-PAY-001, US-PAY-014, US-BIL-005]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** x = Active; y = **Marked disconnect** (past-due ladder exhausted, cut scheduled but NOT executed), then payment → back to Active. The boundary matters because of the PO-delegated, PM-ruled behavior-class seed in BR-CUS-055: **Marked disconnect = billable** — the customer is still consuming until the cut, so billing continues at FULL charges through the entire marked window. If the mark silently stopped billing, every customer who strings out the ladder would get free service. Money figures from expected/money-triples.csv row `flat,cycle,none`.

**Fixture.** Tenant brazos-bend · ACC-1042 · issued bill BL-2607-0142 **$97.41** unpaid past grace (row `flat,cycle,none`: outstanding 97.41, next late fee **$5.00** floor per WE-15b) · collection ladder run per BR-PAY-017 · cut date Aug 18 (never reached).

**Fixture amendment (2026-08-22, CR-014 / DEF-556).** The unpaid 97.41 bill is seeded as **ACC-2042**'s August bill (period Aug 1–31, issued Sep 1, due Sep 22) — not “BL-2607-0142 on ACC-1042”: ACC-1042's July bill is the finance-signed WE-1 **247.87** (LE-1/LE-6), and a real July-period issue would move the signed July trial balance (measured 553.69 → 748.51). “Past grace” is reached by the journey's own evaluation date after Sep 22 (BR-TEN-043); the money rows (`flat,cycle,none`, the $5.00 floor) are unchanged.

| # | Action | Upstream effect (what recomputes) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Collection sequence advances (due+3 reminder → late fee → 10-day → 5-day → 48h certified final); Clerk sets status Active → **Marked disconnect** via the S22 disconnect-notice flow | Late fee assessed on the overdue portion: **$5.00** floor (max($5, 1.5% × 97.41)); "days late" everywhere = today − BL-2607-0142's due date (BR-PAY-032) | notice_history appended per tier; certified mail on the final tier; medical-hold accounts would be excluded (BR-CUS-039); every notice rides the outbound queue and respects quiet hours 08:00–21:00 (BR-NOT-009); audit rows for status + notices | BR-PAY-017 · BR-BIL-001 · BR-CUS-039 |
| 2 | Aug cycle bill run executes WHILE the account is Marked disconnect | **Billing continues unchanged** — behavior class billable: full base + usage lines for Aug, taxable per B4.2; nothing about the mark suppresses or reduces the draft | Aug bill issues at full charges (figures = the account's normal shape rows in money-triples); balanced JE; delivery queued | BR-CUS-055 (Marked disconnect = billable) |
| 3 | Harness checks reports during the marked window | — | "Active accounts" KPI still counts the account (Active + Marked disconnect + Vacation hold, BR-REP-012); AR aging shows 97.41 + 5.00 aging on POSTING basis, header labeled | BR-REP-012 · BR-REP-001 |
| 4 | Customer pays in full; Clerk records payment with POSTING date = day received (user-entered) | Allocation per BR-PAY-010: oldest invoice first, usage+base → taxes → fees last; balance clears; on-time/late logic reads the POSTING date (clearing may lag) | payment row carries posting ≠ clearing dates (both); allocations rows written; receipt auto-queued (BR-PAY-024); cash-side KPIs move on CLEARING basis (BR-REP-010) | BR-PAY-021 · BR-PAY-033 · BR-PAY-010 |
| 5 | Clerk sets **Marked disconnect → Active** (staff decision after payment — no auto-restore rule exists; the cut never happened, so no RECONN charge code applies) | Behavior class unchanged in money terms (billable → billable); ladder resets — collection state clears | audit row for the status change; scheduled cut cancelled; NO reconnect fee line (RECONN $45 exists as a tenant charge code but only a real reconnect earns it, BR-BIL-007) | BR-CUS-055 · BR-BIL-007 |
| 6 | **INVARIANCE** — what must NOT have changed | Every bill issued during the marked window stands at full charges — no retro-waiver, no re-rate on restore; the late-fee line stays (waiver would be a separate manual, audited action per BR-BIL-003) | issued invoices byte-identical; notice_history append-only; ledger balanced with no reversals from the status changes | BR-BIL-004 · BR-BIL-003 · hard rule 4 |
