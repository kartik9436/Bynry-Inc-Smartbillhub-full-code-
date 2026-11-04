# Data Retention

Defaults per B6 (indicative, confirm with finance/legal before first paying tenant):

| Data | Retention | Basis |
|---|---|---|
| Invoices, payments, journal entries | 7 years | US utility/tax practice |
| Meter reads | 7 years total: **2 years hot in DB, then archived to cold-storage backup** (PO Q&A R6) | regulatory |
| Audit log | 7 years total: 2 years hot, then archived (PO Q&A R6) | legal |
| Notices (disconnect/reminder) | 7 years | PUC dispute defense |
| Backups | daily full + PITR (WAL); RPO 1h, RTO 4h | B6 |
| Closed-tenant data | **OPEN** — offboarding export + deletion SLA needed | contract |

Financial records are append-only regardless of retention — deletion at end-of-retention is a supervised archival job, never an operational path.

## Addendum 2026-08-08 — consolidated retention schedule (post-capacity-math)
Financial (invoices/lines/payments/allocations/journal): 7yr, NEVER pruned, cold-store >2yr (NFR-25) · meter reads: 2yr hot → cold, 7yr total (BR-MET-055) · audit_log: 2yr hot, 7yr total (NFR-28) · rendered message bodies: 90d then prune — reproducible from pinned templates (NFR-29/NL-1) · outbound queue status rows: 18mo (NL-2 PO-confirmed) · notice_history: 7yr · scheduled-report files: 3 days (IS-11) · rate/plan/template versions: 7yr+/pinned-forever · closed-account PII: 7yr with financial records, masked (SC-7 CONFIRMED → BR-CUS-065). Volume basis: B6 capacity math (2.7B rows/3yr @ 1.6M accounts).
