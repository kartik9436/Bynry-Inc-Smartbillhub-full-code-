# T5-05 — Duplicate bill run (idempotency key refuses the re-run)

---
id: T5-05
tier: 5
guards: [BR-BIL-005, BR-BIL-015, NFR-16, NFR-4]
hard_rules: [6]
stories: [US-BIL-001, US-BIL-006]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Bill runs are idempotent on the unique tenant+cycle+period key (BR-BIL-005, hard rule 6). A second run for the same cycle+period — double-click, retry after timeout, or a second clerk racing the first — must be REFUSED, or every account gets billed twice and AR/ledger double. Catch-up sub-runs are the ratified way to bill stragglers: parent-linked and scope-keyed so they NEVER collide with the parent key (BR-BIL-015).

**Fixture.** Tenant brazos-bend · cycle CYC-A · period 2026-07 · completed run RUN-2607-A issued 1,240 invoices (sample invoice BL-2607-0142, $97.41 — money-triples row `flat,cycle,full`) · 3 accounts held to the Pending-billing queue.

| # | Actor + action | Expected refusal (IS-7 outcome) | Downstream assertions (nothing changed) | Guard |
|---|---|---|---|---|
| 1 | Billing Clerk starts a new run and selects CYC-A + 2026-07 again (S31 step 1) | Refused at creation: conflict (409 class) with link to RUN-2607-A ("run exists for this cycle+period — who/when"); IS-7 failed state offers navigation, not retry | No second bill_runs row; invoice count for the period still exactly 1,240; no new drafts | BR-BIL-005 · hard rule 6 |
| 2 | Same clerk replays `POST /api/bill-runs {cycle: CYC-A, period: 2026-07}` five times (simulated retry storm) | Every call hits the unique tenant+cycle+period key → same conflict, same original-run link; async job never enqueued twice | bill_runs count unchanged; job queue has zero new run jobs; ledger balanced, unchanged; audit: attempt-logging not ratified (BR-AUD-001 scope) — assert zero money writes | BR-BIL-005 · NFR-16 |
| 3 | Second clerk, second browser, submits the same run concurrently with a fresh (hypothetical) first run — race probe executed by the harness | Exactly ONE run row wins; the loser receives the conflict with the winner's link | Post-race: one run, one invoice set, zero duplicate invoice numbers in the BL-{YYMM}-{seq} series | BR-BIL-005 · NFR-4 |
| 4 | Clerk attempts to re-run "just the 3 held accounts" by launching a full CYC-A/2026-07 run again | Refused identically — a re-run is never the door for held accounts | Held accounts still in Pending-billing queue with aging; no duplicate billing of the 1,240 | BR-BIL-005 · BR-BIL-015 |
| 5 | RECOVERY — the ratified door: launch a catch-up SUB-RUN for the held accounts (parent-linked to RUN-2607-A, scope-keyed idempotency) | Sub-run creates cleanly — its scope key never collides with the parent run key | 3 accounts billed once each; parent linkage recorded; queue drains; every issue writes audit (BR-AUD-001) | BR-BIL-015 · NFR-4 |
