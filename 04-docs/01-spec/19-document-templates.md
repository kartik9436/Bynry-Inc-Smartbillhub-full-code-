# A19 — Document Templates

> Layout specs for the printed/emailed documents the system generates. Field tokens shown as {token}; all money 2dp, dates render per tenant Regional settings. Added 2026-08-07.

## 1. Bill / Statement (printed + PDF)
Single page, letter/A4. Sections top→bottom:
1. **Masthead:** {utility_logo} left · {utility_name}, {utility_address}, {support_phone/email} right.
2. **Bill meta band:** Account {account_no} · {customer_name} · Service address {service_address} · Bill # {bill_no} · Cycle {cycle} · Bill date {bill_date} · **Due {due_date}**.
3. **Summary box (right):** Previous balance {prev_balance} · Payments/credits {payments} · Current charges {current_charges} · **Total due {total_due}**.
4. **Per-service lines** (repeat per service E/W/S/…): service name · meter {meter_no} · prior {prior_read} · current {current_read} · usage {usage} {unit} · rate description · amount. Tiered lines itemize each tier.
5. **Base & fees:** base charge, any charge-code lines (CONN/LATE/…). **Taxable lines only feed tax.**
6. **Tax lines:** per authority {authority} {rate}% {amount}.
7. **Usage graph:** 12-month bars (optional).
8. **Messages / footer:** payment methods, remittance stub with {account_no}, {total_due}, {due_date}.
- **Statement** variant: same masthead; body is a dated ledger (charges, payments, adjustments, running balance) over the selected range instead of one cycle's lines.

## 2. Disconnect notice — 3 tiers (letter + certified mail for final)
Shared header: {utility_name}, {customer_name}, {account_no}, {balance}, {service_address}.
- **Tier 1 — 1st notice (10-day):** tone informative. "Your account is past due in the amount of {balance}. Please pay by {pay_by_date} (10 days) to avoid service interruption." Payment options + assistance/payment-plan offer.
- **Tier 2 — 2nd notice (5-day):** firmer. "FINAL REMINDER. Service to {service_address} is scheduled for disconnection on {cut_date} unless {balance} is received. A reconnect fee of {reconnect_fee} applies to restore service."
- **Tier 3 — Final notice (48-hour, certified):** "NOTICE OF DISCONNECTION. Service will be disconnected on {cut_date} ({48h}). To avoid disconnection pay {balance} immediately. Medical/critical-care customers: call {support_phone}." Certified-mail block + regulatory language ({state_puc_ref}); medical-hold accounts are excluded (A15).

## 3. Payment-plan agreement (e-signature)
1. Header: {utility_name} · {customer_name} · {account_no} · date {today}.
2. Terms: total {balance} spread over {n} installments; schedule table (# · due date · amount · remaining); down payment {down} if any.
3. Conditions: autopay from {payment_method}; dunning + disconnect **paused while current**; default clause (plan voids on {missed_count} missed → full balance due; fees resume).
4. Signature block: {customer_signature}, {date}; countersign {utility_rep}. On sign → plan activates (A6).

## Addendum — Templates are user-editable (2026-08-07 r8)
All document/email/SMS templates in A19/A13/A15 are **editable in Settings → Templates** with a variable palette + versioning. Email renders through the tenant's connected mailbox; SMS via the messaging provider (opt-in); printed notices via print/certified-mail. Notifications (A15) controls *when*; Templates control *content*.


---

## Revision 2026-08-07 — every template now has distinct, real content

Each of the 16 templates in **Settings → Reference data → Document & message templates** opens its own designer with a true-to-life preview. They are **not** variations of one layout; each carries content the others do not.

### Printable (6) — paper preview + variable list + per-template options

| Template | What makes it different |
|---|---|
| Bill · residential | Usage lines per service, tiered rate detail, 12-month usage graph, remittance stub |
| Bill · commercial | Adds **PO number**, **tax ID**, **per-meter breakdown table** (prior/current/usage/rate), **demand charge** line (peak kW × $/kW), sewer-as-%-of-water, Net-20 terms, W-9 note. Residential has none of these |
| Statement | A **running ledger over a date range** — date / description / reference / charges / payments / balance. No rates, no meter reads, no due date. Carries the explicit "not a bill, nothing is due" disclaimer |
| Disconnect notice (3 tiers) | Tier banner (10-day / 5-day / **48-hour final**), certified-mail number, "how to stop this" 3-column block, and the **regulatory rights footer** — dispute rights, medical hold (physician-certified, 60-day renewable), weather suppression (<32°F / >100°F), weekend/holiday suppression, PUC complaint line |
| Dunning 1 / 2 / 3 | A **reminder**, not a legal notice. Stage banner (day 7 friendly / day 14 firm / day 30 final), unpaid-bill table with days-late, late-fee line, payment-plan offer. Escalates *into* the disconnect notice |
| Receipt | **One transaction** — amount, method, confirmation number, applied-to bill, balance before/after, processed-by staff name. No usage, no rates, no due date |

### Email (6) — subject + preheader + rendered body + merge fields

| Template | Subject | Distinct content |
|---|---|---|
| Bill ready | "Your Silver Creek Water bill is ready — $247.30 due Aug 25" | Usage breakdown by service, **year-over-year comparison** ("12% more electricity"), pay button + PDF link, autopay reminder line |
| Payment receipt | "Payment received — thank you, $247.30" | Confirmation number, applied-to bill, balance now, next bill date. Shortest of the email set |
| Past-due reminder | "Friendly reminder: $412.80 is past due…" | **Three tones** (friendly / firm / final) selected at send time from Payments → Outstandings; payment-plan offer |
| Plan change confirmation | "Your rate plan has changed — effective Sep 1" | Before/after plan table, base-rate delta, effective date, **estimated bill impact**, deposit change, "did not request this?" line |
| Credit issued | "A $15.00 credit has been added to your account" | Credit amount, **the clerk's memo shown as the customer-visible reason**, reference number, when it applies |
| Statement email | "Your August account statement is ready" | Period summary table (opening / charges / payments / credits / closing), attaches statement PDF, explicit "not a bill" line |

### SMS (4) — phone-bubble preview + character/segment counter

| Template | Chars | Distinct content |
|---|---|---|
| Bill ready | 103 | Amount, due date, short pay link, STOP opt-out. Skipped when the customer is on autopay |
| Past-due reminder | 138 | Amount, days late, short link **plus phone number** (past-due customers want a person) |
| Disconnect notice | 156 | Leads with **URGENT**, names the service address and cut date. **Supplements the mailed notice, never replaces it** — regulators require the letter |
| Payment received | 99 | Amount, new balance, confirmation. Shortest template in the system |

### Rules that fall out of this

1. **Statement ≠ bill.** Both the printed statement and the statement email must say nothing is due, or customers pay twice.
2. **Dunning ≠ disconnect notice.** Dunning is a courtesy reminder with no regulatory footer; the disconnect notice is regulated and tiered.
3. **SMS never stands alone for disconnection.** The certified letter is the legal instrument.
4. **Commercial ≠ residential.** PO number, tax ID, per-meter table and demand charges only exist on the commercial bill.
5. **160-character segment limit** is surfaced live in the SMS editor — going over doubles the per-message cost.
6. Every template is **versioned and audit-logged**; the header shows version and last-edited date.

> **Addendum 2026-08-08 (PO ruling):** §3 signature block corrected — the payment-plan agreement executes via the customer's e-signature alone; the utility countersign line is dropped. No other signature is required (BR-CUS-044).
> **Addendum 2026-08-08 (reports audit):** (a) Template **version pinning** is law — bills store template+version at issue; reprints render the pinned version forever; a pinned version can never be deleted (BR-BIL-026/027) — applies to every designer S91+. (b) §2/dunning day numbers (7/14/30) are **seeded defaults of the tenant-config sequence** (BR-PAY-017); stage mapping = RQ-8 with PO. (c) §3 countersign block SUPERSEDED — customer e-signature alone (BR-CUS-044, addendum above). (d) §1 note: statement is a distinct template class carrying the "nothing is due" disclaimer (rule 1); penalty statements render on the statement class (BR-BIL-019); bill template gains a budget-variance block (BR-BIL-017) and final bills a settlement summary (BR-BIL-013); back-bills show period-labeled line groups (BR-BIL-018).
> **Addendum 2026-08-08 (NT-1/NT-2):** the template set gains a 17th class — **Payment-plan notices** (upcoming/missed/void variants; copy skeletons PM-specced, PO-reviewed). Regulated collection-ladder steps always render the disconnect-notice class (BR-NOT-008). Template classes now carry language variants (BR-NOT-006, B2 r15).
