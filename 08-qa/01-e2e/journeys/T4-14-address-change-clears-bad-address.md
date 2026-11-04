# T4-14 — Address change clears the bad-address flag (x = returned-mail suppression → y = paper resumes)

---
id: T4-14
tier: 4
rules: [BR-PAY-018, BR-NOT-005, BR-BIL-016, BR-REP-015]
stories: [US-PAY-016, US-NOT-014, US-CUS-009]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** x = account flagged **bad-address** (paper bill came back; delivery record marked returned per BR-PAY-018): paper output SUPPRESSED until the address is verified, account sitting in the needs-attention queue with a banner — while balances continue completely unaffected. y = staff verify/correct the mailing address → flag clears → paper RESUMES on the next queued document. The boundary matters because suppression is a delivery-state transition only: if it leaked into billing or AR, a wrong ZIP code would change what a customer owes. This is PE-16 run as a transition.

**Fixture.** Tenant brazos-bend · ACC-1042 · Jul bill BL-2607-0142 **$97.41** mailed, returned by USPS · returned-stack processed Aug 2 · address corrected Aug 9.

| # | Action | Upstream effect (what recomputes) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Clerk marks BL-2607-0142's delivery record **returned** (single or bulk returned-mail stack) | Account **bad-address flag** sets; account enters the needs-attention queue; paper channel SUPPRESSED (config) until verified | S32 needs-attention chip counts the account (BR-REP-015); account banner renders; audit row; delivery record status = returned | BR-PAY-018 |
| 2 | Aug cycle issues the account's next bill while flagged | Bill issues normally (money side untouched); the delivery-queue row for the PAPER channel is written but HELD/suppressed rather than dispatched | outbound row exists with suppressed disposition — the queue is still the single source of send truth (BR-NOT-005); balance, due date, late-fee clock all run exactly as if delivery were normal | BR-PAY-018 · BR-NOT-005 |
| 3 | Harness asserts the money non-effect during suppression | NOTHING recomputes: AR unchanged by the flag; aging continues; collections ladder unaffected in amount terms | account balance = the normal money-triples expectation for its payment behavior; zero adjustment/credit rows from the flag | BR-PAY-018 ("balances unaffected") |
| 4 | Clerk corrects + verifies the mailing address (Aug 9) | Bad-address flag CLEARS; account leaves the needs-attention queue; paper suppression lifts | audit row with before/after address + flag; banner gone; chip count decrements | BR-PAY-018 |
| 5 | Next queued paper document dispatches (held Aug bill re-queued or next cycle's document) | Dispatcher resumes the paper channel in tenant-config batches | delivery record transitions queued→sent; per-run delivery dashboard shows the resume; audit | BR-BIL-016 · BR-NOT-005 |
| 6 | **INVARIANCE** — what must NOT have changed | Across flag-on and flag-off: no invoice, payment, allocation, or JE was created, changed, or suppressed; only delivery-state rows and the account flag moved | issued documents byte-identical (a re-send renders the pinned version, BR-BIL-026); delivery/return event history append-only; every step audited | BR-PAY-018 · BR-BIL-026 · hard rule 4 |
