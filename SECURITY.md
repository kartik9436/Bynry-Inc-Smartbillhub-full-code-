# Security Policy

SMARTBillHub processes utility-customer PII and money movements. Security reports are treated as P1.

## Reporting a vulnerability
Email **security@bynry.io** with reproduction steps. Do not open a public issue. Acknowledgement within 2 business days; status update within 7.

## Scope
- Tenant isolation (RLS) bypass — highest severity
- Financial integrity (mutation of issued invoices/payments/journal lines)
- AuthN/AuthZ (role escalation, 2FA bypass)
- PII exposure (contacts, DOB, gov-ID, bank/card fragments)

## Out of scope
- The `05-prototype/` folder (static design reference, no backend)
- Rate limiting on the public pricing page

## Handling rules for contributors
- No secrets in the repo — `.env.example` names variables, never values; pre-commit runs a secret scan.
- PII columns are enumerated in `04-docs/07-compliance/pii-inventory.md`; changes to that surface require review.
