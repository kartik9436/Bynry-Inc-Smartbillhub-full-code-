# J17 — Delivery life (issue → queue → batch dispatch → bounce → bad-address → suppress → fix → resend)

---
id: J17
tier: 2
rules: [BR-BIL-016, BR-NOT-005, BR-NOT-009, BR-NOT-010, BR-PAY-018, BR-REP-007, BR-REP-015]
stories: [US-BIL-005, US-BIL-023, US-BIL-024, US-NOT-001, US-NOT-002, US-NOT-013, US-NOT-014, US-PAY-016]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** A bill's life AFTER it is issued: mass sends are never synchronous — every document is a queue row first (BR-NOT-005, platform-wide), a dispatcher works in tenant-config batches at provider pace, failures retry ×3 and then surface on a dashboard, a returned paper bill flags the account bad-address and SUPPRESSES paper while balances keep running, and the fix + resend closes the loop. Delivery is a lifecycle, not a fire-and-forget.

**Fixture.** Tenant brazos-bend · Aug 1 run issues **240 bills** · dispatch batch size 500 (tenant default) · channels: print/PDF live; email rows **W6-flagged** (dispatch lands with email rails per BR-BIL-016/OQ-073) · quiet hours 08:00–21:00 tenant time · ACC-1119 = the returned-mail case.

| # | Date · action | Handoff contract (what this step leaves) | Downstream assertions (bill · ledger · reports · queue · audit) | Rule |
|---|---|---|---|---|
| 1 | **Aug 1** — issue writes ONE delivery record per bill per channel: 240 print/PDF rows + email rows for paperless accounts (W6-flagged); nothing is sent inline | Queue rows status **queued**; each row carries bill, channel, template pin | Outbound table is the single source (BR-NOT-005); per-run delivery dashboard opens at 0% sent; audit | **BR-BIL-016** |
| 2 | **Aug 1** — dispatcher hands batches (≤500) to the channel at provider pace; statuses advance **queued → sent → delivered** | Batch handoffs recorded; pacing respected (no platform-speed burst — T5-24 proves the guard) | Dashboard fills; rows generated at 22:00 HOLD until the 08:00 window opens (quiet hours, BR-NOT-009 — print/PDF generation exempt) | BR-NOT-005/009 |
| 3 | **Aug 2** — one email BOUNCES (W6-flagged path) → **retry ×3 with backoff** → status **failed** | Failed row with attempt history retained | Delivery-queue health report counts it (BR-REP-007, US-REP-009); dashboard flags the failure for re-queue; audit | BR-NOT-005 |
| 4 | **Aug 6** — ACC-1119's paper bill comes back in the mail → staff mark the delivery record **returned** → account flagged **bad-address** → needs-attention queue + account banner → **paper suppressed** until address verified (config) | Returned status on the row; suppression active; BALANCES CONTINUE NORMALLY — due dates, late fees, aging unaffected | S32 returned-mail chip increments (BR-REP-015); subsequent documents for ACC-1119 queue but paper holds; audit | **BR-PAY-018** |
| 5 | **Aug 12** — address corrected and verified on the account → **bad-address flag clears** (the T4-14 transition); suppression lifts | Clean address; flag history append-only | Needs-attention row closes; chip decrements; audit rows for fix + clear | BR-PAY-018 |
| 6 | **Aug 12** — dashboard **re-queue**: the failed email re-queues (for W6 dispatch) and ACC-1119's held bill dispatches to the fixed address → **delivered** | All 240 bills reach a terminal good state or a worked exception; queue empty for the run | Per-run dashboard shows 100% resolved; delivery-queue health report clean; audit | BR-BIL-016 · BR-NOT-005 |
| 7 | **INVARIANCE** — the bill DOCUMENT never changed through bounce/return/resend (pinned template, byte-identical render); no send ever bypassed the queue; suppression never touched money (due dates and fees ran untouched); door-hanger never appeared as a channel (v2, BR-NOT-010) | — | Issued invoice immutable (BR-BIL-004); full queue-status history per row; every mark/clear/re-queue audited (hard rule 7) | BR-BIL-026 · BR-PAY-018 |
