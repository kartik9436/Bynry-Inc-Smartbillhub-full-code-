# A15 — Notifications & Communications

> Part A (extraction). Source: SMARTBillHub prototype «../../05-prototype/UtilityBilling.html». Every send trigger, recipient, content, timing. Mostly INFERRED from side effects — confirm each.
> Cardinal rule: anything not determinable from the UI is «UNKNOWN — <question>», never invented.


| Trigger | Channel(s) | Recipient | Content | Timing | Confidence |
|---|---|---|---|---|---|
| Create utility & go live | email | Owner | welcome | signup | INFERRED |
| Record payment | receipt (opt) | customer | receipt | on demand | EXPLICIT |
| Send statement | email/mail/SMS | contact | statement PDF (current/trailing 12/custom/final) | on demand | EXPLICIT |
| Print bill | print/PDF | staff/customer | bill | on demand | EXPLICIT |
| Issue credit | email (opt) | customer | credit notice | on issue | EXPLICIT |
| Change plan | email | customer | plan-change confirmation | on confirm | EXPLICIT |
| Payment plan | email + SMS + print (opt) | customer | e-signature agreement | on send | EXPLICIT |
| Send reminder (bulk) | email/SMS/letter | accounts | tone Friendly/Firm/Final; pay-now link | on send | EXPLICIT |
| Disconnect notice | email+SMS / certified mail / door hanger | account | tier 1st(10d)/2nd(5d)/Final(48h); cut date; reconnect fee | on send | EXPLICIT |
| Deposit reconcile | email (opt) | bookkeeper | reconciliation summary | on reconcile | EXPLICIT |
| QuickBooks sync | email (opt) | bookkeeper | period copy | on send | EXPLICIT |
| Scheduled report | email | recipients | report file | overnight/scheduled | EXPLICIT |
| Billing run complete | print/email/SMS | customers | bills | end of run | EXPLICIT |
| Lockbox import | receipts (opt) | matched customers | receipts | on import | EXPLICIT |

## Delivery constraints noted
- Certified mail "required by TX PUC for final" disconnect.
- Medical-hold accounts auto-skipped on bulk disconnect.
- SMS requires opt-in.

## UNKNOWN
Provider (B7); full bodies/subjects; per-tenant editing (Settings → Notifications referenced, not built); retry/bounce; quiet hours; localization; delivery audit trail.



## Addendum — Bring-your-own email (confirmed 2026-08-07)
The platform does **not** ship its own email-sending engine. Each tenant **connects their own mailbox** (Settings → Integrations → Email) so all customer emails — bills, statements, reminders, receipts, notices — are sent **from the utility's own address**. Connect methods: **Google OAuth**, **Microsoft 365 OAuth**, or **custom SMTP** (host/port/credentials). A send-from address is configured and a test email offered on connect. Notification module must send through the tenant's connected mailbox, not a shared sender.


## Addendum — Templates pairing (2026-08-07 r8)
Each notification trigger maps to an editable template in Settings → Templates. Send action renders the current template version; changing copy never changes the trigger.
