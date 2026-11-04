# B7 — Integrations

> **Part B — human/finance judgment.** Drafted from the prototype as a starting point. Every line marked **PLACEHOLDER** must be confirmed by a human before it is authoritative. Nothing here is extracted fact unless it cites the UI.


> Implied by the UI. **CONFIRMED (2026-08-07): keep a provision (adapter seam) for ALL of these** — build the integration interface for each so any can be enabled per tenant; the specific provider and v1-activation are per-tenant config, not hardcoded.

| Integration | UI evidence | Suggested provider | Provision |
|---|---|---|---|
| Card + ACH payments | payment methods, autopay, card settlement "STRIPE" line | **Stripe** | build seam · v1 likely |
| Bank connect | "connect via Plaid", bank sync | **Plaid** | build seam |
| Bank statement import | CSV / OFX / QBO / QFX upload | file parsers | build seam · v1 |
| Lockbox import | "Chase BAI2 · BofA CSV" | BAI2/CSV parsers | build seam |
| Accounting sync | QuickBooks Online push; IIF; Xero CSV | **QBO API** + file exports | build seam · QBO v1 likely |
| AMI / meter data | read source "AMI"; CSV upload wizard | CSV ingest; AMI vendor API later | build seam · v1 = CSV |
| Email | statements, reminders, receipts | SendGrid / SES | build seam · v1 |
| SMS | reminders, notices (opt-in) | Twilio | build seam |
| Print / mail | statements, certified mail for disconnect | Lob | build seam |
| E-signature | payment-plan agreement | DocuSign | build seam |
| SSO | `sso_links` table, no UI | OIDC/SAML | build seam |

**Design rule:** each integration sits behind a provider-agnostic interface (payment gateway, bank feed, accounting export, messaging, e-sign, SSO) with per-tenant enable/config — no provider hardcoded into business logic. For each: sandbox creds, webhook idempotency (B2 `payments.webhook_key`), retry policy, and failure surfacing (UI shows "Failed · Retry").


## Addendum — Email is BYO mailbox (confirmed 2026-08-07)
**Do not build/operate a shared email-sending service.** Instead build a **mailbox-connect** integration: tenants link their own email via **Google OAuth / Microsoft 365 OAuth / custom SMTP**, and all outbound customer email is sent from the tenant's own address. This removes a separate email engine from scope and improves deliverability/brand trust. Store per-tenant email credentials/tokens as secrets (encrypted); surface send failures the way the UI already does ("Failed · Retry"). SMS/print/e-sign remain separate provider seams (provision all).
