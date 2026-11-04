# B10 — Subscription Billing (Bynry side)  [PROPOSED — Product Owner to ratify]

> What the tenant pays Bynry (S107–S109 + onboarding S112). HARD BOUNDARY: a different entity class from customer bills — never appears in Billing, Payments, Finance, or Reports. Platform tables, no tenant-RLS membership; surfaced only in Settings → Billing plan.

## Data model (B2 addendum — platform tables)
- `subscription_invoices` — invoice_no `SBH-INV-YYYY-####`, tenant_id, period_start/end, issued_at, due_at (Net-15), **plan_snapshot**, **method_snapshot** (S108: render as-at-issue), amount, currency, status `draft→open→paid | past_due | void`, stripe_invoice_id, pdf_url.
- `subscription_invoice_lines` — kind `subscription | implementation | overage | credit`, description, amount.
- `subscription_payment_methods` — kind `card | ach | invoice_wire`, brand+last4, exp, auto_charge flags, stripe_pm_id. **PAN/bank numbers never stored** (S109 copy).
- `implementation_orders` — package `self_serve|guided|standard|full`, price, milestones[], status.
No FK between these and any tenant-billing table except tenant_id. Separate number series from customer `BL-…`.

## Provider
**Stripe Billing** (Bynry's own account — distinct from the per-tenant Stripe seam tenants use to collect from their customers). Card entry via Stripe Elements browser→Stripe; SMARTBillHub stores tokens only. "Pay now" → Stripe hosted invoice/payment; receipts = Stripe PDFs.

## Implementation-package invoicing [PROPOSED]
| Package | Schedule | Terms |
|---|---|---|
| Self-serve $0 | — | — |
| Guided $5,000 | 100% at kickoff | Net-15 |
| Standard $9,000 | 50% kickoff · 50% go-live | Net-15 |
| Full $12,000 | 40% kickoff · 30% migration acceptance · 30% go-live | Net-15 |
Kickoff = trial conversion (kickoff line rides the first subscription invoice). Refunds: started milestones non-refundable; unreached milestones never invoiced; milestone slipping >2× stated duration by Bynry's fault → customer may cancel the remainder. Cancel before kickoff = $0.

## Tenant non-payment lifecycle [PROPOSED — also settles old A17 #20]
`trial (14d, no card) → active → past_due (14d grace, banner) → suspended (read-only, data intact) → canceled (90-day export window → archival)`.

## PO ratification with modifications (2026-08-08, Q&A R8) — supersedes conflicting lines above
- **NO Stripe.** No payment processor in v1. v1 ships the schema provision (platform tables) + the tenant-facing Billing plan screens (S107–S109) only.
- **Invoice creation/posting to tenants: v2/v3 provision** — no automated Bynry-side invoicing engine in v1; any v1 subscription invoices are recorded manually by Bynry ops. "Pay now" behavior defined in v2.
- **Payment terms: Net-7 or Net-15** (set per tenant/invoice by Bynry).
- **Implementation fees: 100% upfront OR max 2 installments** (e.g., 50% kickoff / 50% go-live). Milestone-split schedules (40/30/30) dropped.
- **Non-payment lifecycle CONFIRMED as proposed:** trial(14d, no card) → active → past_due(14d grace, banner) → suspended(read-only) → canceled(90d export → archive).
- **v2 committed scope:** Bynry admin console — monitor all tenants, create subscriptions, pricing, invoices. Not in v1.
