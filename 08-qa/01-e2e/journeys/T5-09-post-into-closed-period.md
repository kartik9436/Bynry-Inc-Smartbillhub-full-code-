# T5-09 — Post into a closed period (the auto-forward proof)

---
id: T5-09
tier: 5
guards: [BR-TEN-038, BR-LED-006, NFR-26]
stories: [US-PAY-001, US-LED-011, US-LED-015]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Closed periods LOCK (BR-LED-006). A money event dated inside a closed period must never land there — it AUTO-POSTS to the earliest open period with an audit note (BR-TEN-038). The refusal here is the closed period's: its totals are frozen forever (that is what T5-07/T5-08 exports rely on), while the business event is still captured — the user is never blocked from recording reality, only from rewriting the closed month.

**Fixture.** Tenant brazos-bend · 2026-06 CLOSED (exported, EXP-2606-01) · 2026-07 earliest open · on 2026-07-03 a mailed check for ACC-1042 arrives, customer-dated and received 2026-06-28.

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions (nothing changed in the closed month) | Guard |
|---|---|---|---|---|
| 1 | Clerk records the payment with user-entered posting date 2026-06-28 (BR-PAY-033) | Accepted as a payment — but the ledger REFUSES the closed period: the posting JE auto-posts into 2026-07 (earliest open) with an audit note referencing the closed-period date | payments row keeps posting date 2026-06-28 (billing/on-time logic uses it, BR-PAY-021); journal entry period = 2026-07; audit note links event→forwarded period (BR-TEN-038) | BR-TEN-038 · BR-LED-006 |
| 2 | Harness re-reads 2026-06 trial balance and the close-time rollups after step 1 | 2026-06 totals byte-identical to close time; the exported figures (EXP-2606-01) still reconcile exactly | Closed-period rollups never invalidate (NFR-26); zero journal lines added to 2026-06 | BR-LED-006 · NFR-26 |
| 3 | Finance user drafts a manual JE (S-journal) dated 2026-06-15 and posts it | Post succeeds but lands in 2026-07 with the same auto-forward + audit note; no path posts lines into the locked period | journal_entries period = 2026-07; balanced at post; 2026-06 line count unchanged | BR-LED-003 · BR-TEN-038 |
| 4 | Adversarial probe: `POST /api/journal-entries {period: 2026-06, ...}` forcing the period field | Server ignores/refuses the forced period — forwarded to earliest open with audit note; response states the forwarding | Same assertions as step 3; audit: the forwarding note IS the ratified attempt-record here (BR-TEN-038 "with audit note") | BR-TEN-038 |
| 5 | RECOVERY — the ratified door when it genuinely MUST land in June: System Admin reopens 2026-06 (audit-logged), the entry posts, Finance re-closes per checklist | Reopen is Admin-only + audited; post lands in 2026-06; re-close relocks; the already-exported window discrepancy is handled by the export rules (T5-07: next window carries corrections) | Every reopen/close writes audit (BR-AUD-001); no silent history change ever | BR-TEN-038 · BR-LED-006 · BR-LED-018 |
