# J5 — Month-end

---
id: J5
tier: 1
stories: [US-TEN-006, US-LED-015, US-LED-016, US-PAY-001]
---

<!-- FRONTMATTER ADDED 2026-08-15 (DEF-102). Not a pure transcription: the step
     table names US-TEN-006 explicitly and uses the WILDCARDS US-LED-** and
     US-PAY-**. Resolved to US-LED-015 (month close) and US-LED-016 (the export
     that closes it out), both built 2026-08-15, plus US-PAY-001 for the cash
     side the close reconciles. Note J19 covers month-end close in far more
     detail and IS story-ready; this journey is the original, coarser pass.
     Stated so the choice is reviewable. -->
**Fixture.** (authored 2026-08-22, CR-014) Tenant brazos-bend · **J19's cohort, shared** — the LE-1 July book (trial balance **598.69 / 598.69**, July window **553.69**), deposit batch DEP-0731 RECONCILED per OQ-219's ruling (realised cash **442.87** / undeposited **0.00**), no July accrual per OQ-218's ruling. ⚠ **Amended 2026-08-22 — OQ-333 CLOSED, PO verbatim: _"Chang the month if required"_.** On a DEMO-seeded stack the sample slice posts 47 invoice JEs dated Jul 2 into the same July (DEF-558), so J19's seeder — which this journey shares — moves the LE-1 book **three months forward to October 2026** and this journey closes that month. The footings are unchanged (**598.69 / 598.69** whole book, **553.69** in the closed month); only the book DATE moved. Where July is empty, July is kept.

deposits reconcile → trial balance → close → export.
| # | Story | Handoff |
|---|---|---|
| 1 | US-PAY-** deposit batches (wave 5) | batches matched/resolved, locked |
| 2 | US-LED-** trial balance (S56) | debits=credits, premises filter resolves via unit chain (BR-MET-046) |
| 3 | US-TEN-006 fiscal close (BR-TEN-038) | period closed; late-dated events auto-post forward w/ audit |
| 4 | US-LED-** export (S42) | one summary JE per month; QBO/CSV/IIF/Xero |
