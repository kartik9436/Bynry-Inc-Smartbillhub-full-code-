# J16 — Held-account catch-up (missing read → hold → queue aging → read arrives → sub-run → issue)

---
id: J16
tier: 2
rules: [BR-BIL-015, BR-BIL-005, BR-BIL-024, BR-BIL-016, BR-MET-012, BR-MET-017, BR-REP-015, BR-REP-001, BR-LED-007]
stories: [US-BIL-003, US-BIL-006, US-BIL-005, US-MET-007, US-REP-017, US-LED-001]
# journey→story wiring sweep pending: story frontmatter `journeys:` updated in a later sweep (00-e2e-design.md §6)
---

**Intent.** Hold ≠ forget. When a service read is missing at run time, BR-BIL-015 gives staff a per-case choice — this journey takes the HOLD path and proves the account cannot fall through the cracks: it enters the Pending-billing queue with a KPI chip and visible aging, and when the read lands it bills via a catch-up SUB-RUN that is parent-linked with a scope-keyed idempotency key — never a colliding re-run of the cycle.

**Fixture.** Tenant brazos-bend · August cycle run **Aug 1, 2026**, 240 accounts · ACC-1077 water read missing at run time (electric complete) · read arrives by import **Aug 9** · sub-run **Aug 10** · catch-up bill amount **engine-computed** (00-e2e-design.md §5) · cycle due-days 21.

| # | Date · action | Handoff contract (what this step leaves) | Downstream assertions (bill · ledger · reports · queue · audit) | Rule |
|---|---|---|---|---|
| 1 | **Aug 1** — cycle run, exceptions step: ACC-1077 water missing → staff per-case choice = **HOLD** (the other options — estimate / bill-without-service — explicitly not taken); run completes for the other 239 | ACC-1077 in the **Pending-billing queue**; run issued for 239 with its tenant+cycle+period idempotency key (BR-BIL-005); no invoice for ACC-1077 | 239 balanced JEs; ACC-1077 absent from Aug billed KPI (posting basis, labeled per BR-REP-001); hold decision audited with reason | **BR-BIL-015** |
| 2 | **Aug 4** — queue review: ACC-1077 shows aging (3 days held), escalation as aging grows | Queue row with age; KPI chip "pending billing" on S7 + S32 counts it (no new screen) | Chip deep-links to the queue (US-REP-017); nothing billable yet; no silent expiry — the row persists until acted on | BR-BIL-015 · BR-REP-015 |
| 3 | **Aug 9** — the water read arrives: staged import → validation → commit with compliance stamp (file + SHA-256) | Committed meter_read for the missing service/channel; validation flags resolved | Read links to its batch (BR-MET-017); queue row now shows "ready for catch-up" | BR-MET-012/017 |
| 4 | **Aug 10** — **catch-up SUB-RUN**: parent-linked to the Aug 1 run, **scope-keyed idempotency** (parent key untouched — never a colliding re-run); preview → draft → issue BL-2608-1077 (amount engine-computed); due = issue + 21 (BR-BIL-024) | Immutable invoice, GL-stamped; sub-run recorded with parent linkage; ACC-1077 leaves the queue | One balanced JE; delivery row queued (BR-BIL-016); billed lands in AUGUST on posting basis; chip count decrements; audit | **BR-BIL-015** · BR-BIL-005 |
| 5 | **Aug 10** — re-execute the same sub-run scope | **No-op** — the scope key already exists; no duplicate invoice, blocked with link to the existing sub-run | Books byte-identical; idempotency proven at sub-run granularity | BR-BIL-005 · BR-BIL-015 |
| 6 | **INVARIANCE** — the parent run's 239 invoices untouched throughout; the hold left NO estimated or partial bill behind; queue history (enter → age → clear) fully audited; tie-outs hold | — | No invoice for ACC-1077 dated before its real read; append-only books (hard rule 4); BR-LED-007 clean | BR-BIL-004 · BR-LED-007 |
