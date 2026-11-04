# A13 — Copy & Microcopy

> Part A (extraction). Source: SMARTBillHub prototype «../../05-prototype/UtilityBilling.html». Verbatim UI text. Row-level dummy data is not copy (see A10). Variables shown as {token}.
> Cardinal rule: anything not determinable from the UI is «UNKNOWN — <question>», never invented.


## Global / shell
- Brand: **SMARTBillHub**; user block: name + role ("Alex Reed" / "Owner"); toasts auto-dismiss ~2.5s.

## Toast confirmations (verbatim)
- "Welcome to SMARTBillHub · your utility is live"
- "Payment $247.30 recorded · balance $0.00" · "Adjustment posted · –$25.00" · "Statement sent · email + mail" · "Bill sent to printer" · "Credit $15.00 issued · applied to next bill" · "Disconnect notice queued" · "Note added"
- "Plan changed · effective Sep 1 · customer notified" · "Payment plan agreement sent · 4 installments"
- "Reminders sent to N customers" · "Disconnect notices queued" · "Selected balances written off"
- "Deposit matched · batch reconciled" · "Pushed to QuickBooks Online · 6 entries" · "Bank statement reconciled · 28 matched · 3 flagged"
- "Report run · <name>" · "Report exported" · "Report scheduled · runs overnight" · "Saved to favorites" · "Lockbox import queued · 84 payments matched"

## Pricing (S1)
- Kicker "UTILITY BILLING · SMB"; hero "Billing that fits your one-person office."
- Sub: "The complete meter-to-cash platform for utilities and submetering operators under three thousand connections. Multi-service, multi-tenant, self-serve. Live in an afternoon — not a quarter."
- CTAs: "Start free — 14 days", "Book a walkthrough". Plans: Starter / Growth ("most popular") / Scale · "Choose plan".

## Setup wizard (S4–S6)
- Kicker "Create your utility · Growth plan · 14-day free trial"; title "Let's set up your utility."
- Steps: "Your utility & services" / "How you bill" / "Create your login"
- S1 title "Tell us about your utility." hint "Just the basics — everything else can wait until you're in." help "silvercreek.smartbillhub.app"; "Which services do you bill?"
- S2 title "How do you bill?" hint "We've pre-filled the most common setup. Change anything — or just accept the defaults and move on." toggle "Load standard charge codes & lookup tables (recommended)". Reassurance "You can add rate schedules, tiers, and per-service taxes later in Plans & Rates. Nothing here locks you in."
- S3 title "Create your login." hint "This is the owner account. You can invite your team later from Settings." terms "I agree to the Terms and DPA" commit "Create utility & go live ✓"
- Footer "Account & meter data migration happens separately in Settings — this only captures configuration."

## Billing run guidance
- S2 title "Here's what we found for Cycle 08-A." hint "We already pulled the customers, their plans, meter reads, and their payment history. Click any section to see the details and make corrections before billing."
- Callout "Anything to fix before we continue?" — "11 meters have no reading this cycle. We'll estimate them from the last 3 cycles unless you want to go collect them first." toggle "Auto-estimate the 11 missing reads".
- S3 case headers: "Used a lot more than usual — N customers" / "No usage this month — N customers" / "Reading was estimated — N customers" / "Owes a lot — N customers" / "Way past due — N customers (60+ days)" / "Late fee due — N customers" / "Extra charges to add — N customers".
- high helper: "These customers used more than double their normal amount. Usually it's fine, but a leak or misread can hide here."
- continue (S2): "Everything checked · Continue →"

## Finance
- Header sub "August 2026 · Open · Hand off to your bookkeeper by Sep 3"
- Deposits callout "Needs your attention" — "3 deposits do not match the bank. Usually a check bounced, a card batch settled a day late, or someone keyed an amount wrong. Import your bank statement →"
- Reconcile modal "Why doesn't this match?" + "Likely explanation".
- Export note "One summary journal entry per month — not one per bill. Your books stay tidy."

## Reminder / notice templates (previews)
- Reminder: "Hi {first_name}, this is a friendly reminder that your account {account} has a balance of {balance}. You can pay online at any time. Thanks for being a customer."
- Disconnect (2nd): "Dear {customer}, your account {account} has an outstanding balance of {balance}. Service will be interrupted on {cut_date} unless payment is received…"
- Receipt: "Thanks {first_name}! We received your payment of {amount} on {date}. Your new balance is {balance}. Confirmation {confirmation}."

## UNKNOWN
- Full email/SMS/print bodies (only previews), subject lines, per-tenant editability (Settings → Notifications referenced, not built) — see A15.
- Validation/error message strings — none designed (no error states; see A10).



## Addendum — Final pricing-card feature bullets (2026-08-07)
Three cards on S1. Bullets are cumulative ("everything in the lower tier, plus…").

**Starter — $1,000/mo — up to 300 connections**
- All services: Electric, Water, Gas, Sewer, Trash, Broadband
- Self-serve setup — live in an afternoon
- Meter reads (CSV import) + guided billing runs
- Payments, outstanding tracking & reminders
- Standard bill/statement templates
- Email + SMS notifications from your own mailbox
- 1 staff seat included · email support

**Growth — $5,000/mo — 300–1,000 connections** *(most popular)*
- Everything in Starter, plus:
- Unlimited staff seats & role-based access
- Finance: bank reconciliation + QuickBooks/Xero export
- Payment plans, budget billing & write-offs
- Full report library + scheduled reports
- Bank & lockbox import, autopay
- Priority support

**Scale — $8,000/mo — 1,000–3,000 connections**
- Everything in Growth, plus:
- SSO (Okta / Azure AD) & advanced security controls
- AMI/MDM meter integrations (Itron, Sensus)
- Custom document templates & numbering
- Dedicated onboarding + priority SLA
- API access

*(Connection counts are indicative bands, not hard caps — see B6.)*


## Added 2026-08-08 — implementation packages

Sold once, at signup (step 3), alongside the monthly subscription. Four selectable cards.

| Package | Duration | One-time price | Card copy |
|---|---|---|---|
| Self-serve | Live today | $0 | You configure it. Guided checklist, help docs, email support. |
| Guided | ~4 weeks | $5,000 | We configure with you, import your accounts and meters, one training session. |
| Standard | ~8 weeks | $9,000 | Everything in Guided · data cleanup · rate build · staff training for your whole team. |
| Full | ~12 weeks | $12,000 | Everything in Standard · historical bill migration · parallel-run validation before go-live. |

Section heading: **"How much help do you want getting set up?"**
Sub-line: *"One-time fee. Most utilities with fewer than 500 connections do this themselves."*
Running-total bar: *"Growth $5,000/mo · Self-serve setup $0 — Due today $0.00 · then $5,000/mo after your 14-day trial."*
