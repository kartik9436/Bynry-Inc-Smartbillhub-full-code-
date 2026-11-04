# PII Inventory & Data Map (regenerated 2026-08-08 — PO compliance sweep)

> Column-level register. Classification: HIGH = app-layer encrypted (OQ-016) · MED = disk encryption + masked display · LOW = disk encryption. Retention cites NFR/data-retention.md. Access = role gate.

| Data | Table.column | Class | Protection | Display | Retention |
|---|---|---|---|---|---|
| Staff email (per-tenant identifier) | users.email (citext, UNIQUE per tenant r11) | MED | disk | full (staff-facing) | membership life + audit 7yr |
| Staff name / phone | users.full_name/phone | MED | disk | full | same |
| TOTP secret (v2) | users.totp_secret | HIGH | app-layer, write-only | never | until 2FA disabled |
| Customer name/email/phone | contacts.* | MED | disk | full to staff; masked in exports per IS-11 filename rules | account life + 7yr (SC-7) |
| Customer DOB | contacts.dob | HIGH | app-layer | masked (MM/****) | same |
| Gov ID | contacts.gov_id_last4 | HIGH | tokenized last-4 ONLY — full ID never stored | ••••4218 | same |
| Service/mailing addresses | premises/addresses | LOW (PII-adjacent) | disk | full | premises life |
| Tenant EIN | tenants.ein (r14) | HIGH | app-layer | masked | tenant life |
| Payment method | payment_methods.brand_last4 | MED | tokenized display string only; NO PAN/account numbers v1 | Chase ••4021 | method life |
| Bank statement lines | bank_lines | MED | disk | Finance roles only | 7yr |
| Deposit/financial history | invoices/payments/journal | MED | disk; append-only | role-gated | 7yr, never pruned (NFR-25) |
| Message bodies (rendered bills/notices) | outbound_messages | MED | disk | — | bodies prunable 90d (NL-1, reproducible via pinning); status 18mo (NL-2); notice_history 7yr |
| Audit payloads (before→after) | audit_log | MED | disk | S61 viewer, tenant-scoped (OQ-029) | 7yr, 2yr hot (NFR-28) |
Exports: any report containing PII follows IS-11 + BR-SHL-016 (streamed, capped, money-export audit rows). B2 line-749 open item is CLOSED by OQ-016 (app-layer for HIGH, disk for rest).
