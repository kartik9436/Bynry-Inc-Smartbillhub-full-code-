# ledger — User Stories (INDEX)
> Pack authored 2026-08-08 against the closed ledger/Finance session (BR-LED-001..016 all CONFIRMED; B2 Addendum r13 approved; reports law BR-REP-001..018; fixtures LE-1..10 / V-1..7, 08-worked-examples.md).
> **Extended 2026-08-15** with EP-LED-06 (US-LED-017..021), the cost-of-service capture — the PAYABLE side as system of record, implementing the PO rulings OQ-188 and OQ-190 of 2026-08-12. Fixtures LE-11..14 / V-8..12. Five open questions **OQ-200..204**.

**Stories live inside their epic files in [`06-epics/`](06-epics/).** This index is generated from story frontmatter at each pack merge — do not hand-edit story content here.

| Story | Title | Epic file | Status | Wave |
|---|---|---|---|---|
| US-LED-001 | Source-event posting contracts: every money event → one balanced entry via the posting service 🔒 | [EP-LED-01-posting-consumption.md](06-epics/EP-LED-01-posting-consumption.md) | draft | W5 |
| US-LED-002 | Dimension stamping: service · account · premises+unit · source · tax authority on every line | [EP-LED-01-posting-consumption.md](06-epics/EP-LED-01-posting-consumption.md) | draft | W5 |
| US-LED-003 | Reversal pairs: corrections, NSF, void — linked mirror entries under append-only books | [EP-LED-01-posting-consumption.md](06-epics/EP-LED-01-posting-consumption.md) | draft | W5 |
| US-LED-004 | Subledger tie-out views + drift red flag on S36 (release blocker) | [EP-LED-01-posting-consumption.md](06-epics/EP-LED-01-posting-consumption.md) | draft | W5 |
| US-LED-005 | Chart of accounts: seeded, tenant-customizable, audit-locked in use | [EP-LED-02-chart-mapping.md](06-epics/EP-LED-02-chart-mapping.md) | draft | W5 |
| US-LED-006 | Export codes on the Finance account-mapping page (qbo_ref · xero_ref) | [EP-LED-02-chart-mapping.md](06-epics/EP-LED-02-chart-mapping.md) | draft | W5 |
| US-LED-007 | S36 Revenue & AR: KPI strip + panels, all dimension-derived, basis-labeled | [EP-LED-03-trial-balance-reports.md](06-epics/EP-LED-03-trial-balance-reports.md) | draft | W5 |
| US-LED-008 | Trial balance (S56): period + premises filters, dimension expansion, export | [EP-LED-03-trial-balance-reports.md](06-epics/EP-LED-03-trial-balance-reports.md) | draft | W5 |
| US-LED-009 | Account ledger report (S59): full source vocabulary + running balance → PDF/CSV | [EP-LED-03-trial-balance-reports.md](06-epics/EP-LED-03-trial-balance-reports.md) | draft | W5 |
| US-LED-010 | By-premises summary report (S60): billed / collected / owed + collection % | [EP-LED-03-trial-balance-reports.md](06-epics/EP-LED-03-trial-balance-reports.md) | draft | W5 |
| US-LED-011 | Manual JE: draft → post lifecycle, three types, balanced at post | [EP-LED-04-manual-je.md](06-epics/EP-LED-04-manual-je.md) | draft | W5 |
| US-LED-012 | Accrual auto-reverse: day 1 of the next period, linked both ways | [EP-LED-04-manual-je.md](06-epics/EP-LED-04-manual-je.md) | draft | W5 |
| US-LED-013 | Posted-JE "edit" = one-click reverse + repost; the journal list (IS-5 row) | [EP-LED-04-manual-je.md](06-epics/EP-LED-04-manual-je.md) | draft | W5 |
| US-LED-014 | Dual-basis remittance (S41): billed vs collected per authority + the remittance payment JE | [EP-LED-05-remittance-close-export.md](06-epics/EP-LED-05-remittance-close-export.md) | draft | W5 |
| US-LED-015 | Month close: checklist, period lock, late-event auto-forward, SysAdmin reopen | [EP-LED-05-remittance-close-export.md](06-epics/EP-LED-05-remittance-close-export.md) | draft | W5 |
| US-LED-016 | S42 export: one summary JE per period per GL, idempotent recorded batches, drill-back, dimension CSVs | [EP-LED-05-remittance-close-export.md](06-epics/EP-LED-05-remittance-close-export.md) | draft | W5 |
| US-LED-017 | Cost-of-service chart section: proposed for finance signature, seeded only for the services a tenant sells | [EP-LED-06-cost-of-service-capture.md](06-epics/EP-LED-06-cost-of-service-capture.md) | draft | W5 |
| US-LED-018 | Capture a supplier invoice (S73): date · service · supplier free text · amount · OPTIONAL volume · GL account · period | [EP-LED-06-cost-of-service-capture.md](06-epics/EP-LED-06-cost-of-service-capture.md) | **blocked** (OQ-200 · OQ-201) | W5 |
| US-LED-019 | The captured-cost register (S73): list, search, edit while the period is open, void with reason — never delete | [EP-LED-06-cost-of-service-capture.md](06-epics/EP-LED-06-cost-of-service-capture.md) | **blocked** (OQ-203) | W5 |
| US-LED-020 | Bought vs billed (S74): the unaccounted-for percentage, and the ABSENT-with-reason case that protects it | [EP-LED-06-cost-of-service-capture.md](06-epics/EP-LED-06-cost-of-service-capture.md) | **blocked** (OQ-201 · OQ-202 · OQ-204) | W5 |
| US-LED-021 | The cost-of-service section of the accounting export (S42/S43): both sides leave in one idempotent batch | [EP-LED-06-cost-of-service-capture.md](06-epics/EP-LED-06-cost-of-service-capture.md) | **blocked** (OQ-200) | W5 |
