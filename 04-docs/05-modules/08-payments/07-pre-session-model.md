# payments — Pre-Session Model (PM understanding for PO review)

> **STATUS: DRAFT — FOR PRODUCT OWNER REVIEW. Nothing here is a rule** until ratified; confirmed items cite rulings, open items carry PA-# (Lane A) / PB-# (Lane B) IDs. Registry rows minted at closure.
> PO directive (2026-08-08): heavy volume — single AND bulk entry weekly/monthly; apply-to-bills; non-bill payments; error reconciliation; credits/debits; refunds; NSF/reversals; deposit batches + bank reconciliation; autopay capture; impact on outstanding + finance; payment-plan notices; receipts + email/TEXT collection comms (very important); returned bills (wrong address) → map those accounts.

## 1. Position

Payments owns money-IN and its lifecycle: intake (single/bulk/webhook) → clearing → **allocation** to bills (BR-PAY-010) → receipts → deposit batches → bank reconciliation → exceptions (NSF, reversals, refunds, write-offs) → collections support (reminders/plans). It posts nothing itself (ledger service 🔒) and never edits a bill. Screens: S22 modal · S32 Summary · S33 Record payments · S34 Outstandings · S35 modal suite (Record/Credit/Adjust/Lockbox/Reverse/Reminder/Notice/Write-off/Reapply/Receipts) · S37–S40 deposits + bank rec.

## 2. Intake — single, bulk, automatic

- **Single (S22/S35):** account → amount, method (cash/check/card/ACH/**wire**/money order — seeded lookup, tenant-extensible), date received, reference (check #), allocation choice (default: rules; options per BR-PAY-001 specific/carry/split). Idempotent save; audit.
- **Bulk (S35 Lockbox + CSV):** same staged pattern as read/account imports — batch → per-row validation (account match by account # / invoice # / name+amount heuristic flagged for review) → preview counts → commit; per-row errors skip with report; batch carries file+SHA-256 compliance stamp; idempotency = file+tags (the OQ-044 model).
- **Webhook (future rails):** `payments.webhook_key` UNIQUE — double delivery dedupes (BR-PAY-003).

## 3. Allocation — how money meets bills (ratified BR-PAY-010, worked)

Oldest invoice first; within an invoice usage+base → taxes → fees LAST; overpayment → account credit; tenant-reconfigurable.
⚠ **AMENDED TWICE SINCE.** **(1) FOUR CLASSES (PO 2026-08-11, OQ-109 → BR-PAY-038):** usage+base → taxes → **the TENANT-DEFINED class** → fees LAST. **(2) THE SEQUENCE IS A TENANT SETTING (PO 2026-08-12, OQ-189 → BR-PAY-010):** *"better to let user set the sequence; we can give default option and allow them to change the order"* — because a municipal utility, a submetering operator and an HOA are **three businesses with three regulators**. The four-class order above is the SHIPPED DEFAULT; its worked figure is unchanged — a **$120.00** payment on a **$128.88** bill (100.58 + 8.30 + 15.00 + 5.00) meets **100.58**, then **8.30**, then **11.12**, late fee LAST at **0.00**. **(3) ONE NAMED EXCEPTION (PO 2026-08-12, OQ-139 → BR-PAY-012):** an **instalment** payment reaches **the PLAN first**, not the oldest bill (PE-13's **36.22** before October's **184.20**), and short of the instalment nothing reaches the current bill.
- **PE-2 partial:** bill $247.87 (usage+base 221.90 · taxes 20.97 · late 5.00), pay $200 → covers usage+base only; outstanding $47.87 (21.90+20.97+5.00). Next late fee computes on that overdue portion (WE-15c).
- **PE-3 two bills:** open Jun 142.30 + Jul 247.87; pay $300 → Jun paid in full, Jul gets 157.70, Jul balance 90.17.
- **PE-4 overpayment:** open 292.87, pay 350 → bills settled + **credit 57.13** carries, auto-applies to the next bill, refundable on request (BR-CUS-061 pattern).
- **Reapply (S35):** staff move an allocation between bills — reversing allocation rows + new rows, reason + audit, never edits.

## 4. Non-bill payments (PA-1)

Money with no open bill: pre-move-in deposit payment, payment-plan down payment, customer prepay/on-account credit. Proposal: every payment carries a **purpose** (bill | deposit | plan-down | prepay); unapplied amounts sit as account credit; deposit-purpose links to the deposit position (satisfies the first-bill deposit line when it issues); plan-down links to the plan.

## 5. NSF & reversals (worked)

- **PE-7 NSF:** cleared check 292.87 bounces → reversing payment row −292.87 (append-only, BR-PAY-002), allocations reversed, AR reinstated at the ORIGINAL due date (late-fee clock never reset — PA-2), NSF charge code +$30 (tenant-config) auto-added → balance 322.87. NSF count increments; N NSFs → check/autopay privilege flag (config, PA-2).
- **Reversal windows (ratified BR-PAY-011):** ACH 60d · card 120d · check unlimited; cross-period/paid needs Admin/Executive approval; always reversing entries; consequence message first.

## 6. Refunds (PA-3)

Only from a real credit balance; request → approval (Admin) → execute check/ACH (card-refund needs rails → W7) → posting DR customer-credit / CR cash; refund row immutable, receipt/notice sent. Design already has the Record-refund modal (r2).

## 7. Deposit batches & bank reconciliation (worked)

- **PE-10 batch:** day's receipts group by method: checks 292.87+142.30+36.22 = **471.39** (DEP-0808-CHK) · cash 105.36+16.42 = **121.78** (DEP-0808-CSH). Batch totals lock when reconciled (BR-PAY-004; Unreconcile = the only undo).
  - ⚠ **SUPERSEDED ON THE CODE ONLY (PO 2026-08-12, OQ-162 → BR-PAY-025).** The two renderings above are kept as written because this file is the record of what was signed, not a description of what the system does. The PO ruled *"Add the year + Date is important"*, so the shipped codes are **`DEP-260808-CHK`** and **`DEP-260808-CSH`** — the year-less form repeated itself every twelve months against a UNIQUE-per-tenant column, and no utility could bank its second year of money on a go-live anniversary (DEF-066). **THE MONEY IS NOT SUPERSEDED: 471.39 and 121.78 are ❄️ frozen, and a label cannot move a total.** Live renderings live in EP-PAY-06 §4 and `apps/payments/reconciliation.batch_code`.
- **PE-11 bank rec (S38):** statement import (CSV/OFX) → auto-match bank line ↔ batch on amount + date ±N days (tolerance config, PA-8) → exceptions worked in the reconcile modal: bank 588.17 vs batch 593.17 → −5.00 explained (bank fee) with reason + GL → trail on S39/S40.

## 8. Autopay (PA-4)

Ratified BR-CUS-059: **capture-only v1** — enrollment + method stored/displayed; bill issue records a capture INTENT dated the due date; actual charging starts with payment rails (W7, no Stripe v1 per PO). v1 behavior: intent visible on S32/S33 ("autopay scheduled"), staff record the real payment when it arrives. Confirm this reading (PA-4).

## 9. Payment plans + notices (worked, PA-5)

- Schedule per BR-CUS-043: balance 267.30, down 50, 6 installments → 5 × **36.22** + final **36.20** (remainder-on-final, half-up). Agreement e-signs alone (BR-CUS-044); active plan pauses dunning + disconnect while current.
- **Notices (PA-5 proposal, tenant-config):** upcoming-installment reminder 3 days before · missed-installment notice day+1 · 2nd miss → plan VOIDS (A19 §3), full balance due, dunning resumes; every notice via the delivery queue, plan state on the account header.

## 10. Receipts & collection communications (PA-6 — PO: very important)

- **Receipt on every cleared payment**: auto-queued (delivery-queue pattern BR-BIL-016) — print/PDF v1; email/SMS when channels land. Manual re-send from S35.
- **Collection sequence (proposal, all tenant-config):** due+3 friendly reminder → due+grace late fee (billing) → tier-1 10-day notice → tier-2 5-day → final 48h certified (A19 §2, paper v1, medical-hold excluded) — email + **SMS with text-to-pay link** ride the same queue when their channels land. **Channel timing = PA-6**: bill email was ruled W6; SMS = Twilio seam v1.1 — given "very important," confirm whether collection email/SMS pull forward or ship with their rails (recommend: with rails; paper notices are v1-complete).
- Every send/skip appends `notice_history` (J4 step 2).

## 11. Returned mail — bad-address mapping (PA-7; PO addition, touches billing delivery)

Paper bill/notice comes back: staff mark the delivery record **returned** (S35/S30) → account flagged **bad-address** → lands in a needs-attention queue (S32 chip + account banner) → paper suppressed until address verified (config) while balances continue normally; fix clears flag; all audited. Bulk-mark supported (a returned-mail stack is a Tuesday chore).

## 12. Impact on outstanding + finance (the contract)

| Event | AR/outstanding | Ledger (posting service 🔒) |
|---|---|---|
| Payment cleared | ↓ | DR cash/undeposited · CR AR |
| NSF | ↑ reinstated + fee | reversing pair + fee line |
| Reversal/void | ↑ | reversing pair |
| Refund | credit ↓ | DR customer credit · CR cash |
| Write-off (PA-9: Owner/Admin approval) | ↓ | DR bad debt · CR AR |
| Credit/adjustment | per direction | per reason-code GL |
| Deposit batch / bank rec | none (grouping) | none; rec differences post per reason |
| Plan activation | none (schedule) | none |
S34 Outstandings and S36 aging read AR live; every row above writes `audit_log`.

## 13. Scenario catalog

PE-1 single check full-pay · PE-2 partial (47.87) · PE-3 two-bill split · PE-4 overpay credit 57.13 · PE-5 lockbox 40-row import, 2 errors · PE-6 non-bill deposit prepay · PE-7 NSF 322.87 · PE-8 window-blocked reversal → approval path · PE-9 refund 57.13 · PE-10 batches 471.39/121.78 · PE-11 rec diff −5.00 · PE-12 autopay intent → manual record · PE-13 plan 5×36.22+36.20 + notice cadence · PE-14 receipt queue · PE-15 collection sequence + text-to-pay · PE-16 returned mail → flag → suppress → fix.

## 14. Lanes

**Lane A (money, item-by-item):** PA-1 non-bill purposes model · PA-2 NSF (original due date stands; fee auto; N-NSF privilege flag) · PA-3 refunds (Admin approval; check/ACH v1) · PA-4 autopay v1 = capture-intent reading · PA-5 plan-notice cadence + 2-miss void · PA-6 collection comms channel timing · PA-7 returned-mail flow · PA-8 bank auto-match tolerance · PA-9 write-off (approval, GL, account state).
**Lane B (mechanical defaults):** PB-1 single-entry fields/UX · PB-2 bulk staged import reusing the ratified pattern · PB-3 receipt auto-queue · PB-4 batch grouping day×method + DEP numbering · PB-5 method seeds incl. wire + money order · PB-6 S33 capability row per IS-5 · PB-7 idempotency (webhook_key + file+tags) · PB-8 S34 outstandings bulk actions · PB-9 reversal consequence messaging UI · PB-10 Reapply modal mechanics.
**Lane C (schema batch #5 — preview, firms after Lane A):** *also carries 7 anchoring items from the billing field-map consolidation (D-1..D-6, D-8a): `account_plan_assignments` (BR-CUS-029 — confirmed rule, never schema'd), `number_series` mechanism (BR-TEN-035), final-settlement record (5-path enum + actor), account-level template override column (BR-BIL-025), budget off_budget status value, void-approval record, customer paperless-delivery preference — plus the 3 tenancy residuals (checklist_state, ein, lock_closed_periods).*  ⚠ **`account_plan_assignments` is SUPERSEDED (PO 2026-08-11)** — no account-side plan table is built; the plan lives once on `units.rate_plan_id` and the account derives it. See BR-CUS-029.
**Lane C (schema batch #5 — preview, firms after Lane A):** payment_import_batches/rows · payment purpose enum · receipts via outbound-delivery queue · refunds approval columns · autopay capture-intents · collection state + notice_history · accounts bad-address flag + delivery-return events · plan notice fields + missed_count · bank statement imports + match-rule config · write_offs table · NSF fields (nsf_count, privilege flag) · numbering series (payments, batches, receipts) · mechanics Eng-Lead 🔒.

## Addendum r1 — PO Lane A + B rulings (2026-08-08)
PA-1..9 ruled (→ BR-PAY-012..020); Lane B all confirmed (→ BR-PAY-022..031). **New PO ruling BR-PAY-021: posting date ≠ clearing date, always separate — posting = record enters the system, clearing = money actually received; BILLING consumes the posting date; NSF/bank-rec hang off clearing.** PA-8: bank rec surfaced in FINANCE (S37–S40). PA-9: write-off initiated in Payments, approved/reported in Finance. PA-6 recorded per PM recommendation (channels ship with their rails) — PO wrote "pa-5" twice, flagged for veto. Lane C #5 examples presented for approval.

## Addendum r2 — SESSION CLOSED (2026-08-08)
Lane C #5 APPROVED (examples confirmed) → B2 Addendum r12. PO volume ruling generalized the delivery queue platform-wide → BR-NOT-005 (all email/SMS written to table; dispatcher batches at provider pace). Payments rules complete: BR-PAY-001..031 all CONFIRMED (PA-6 recorded per PM rec, flagged). Pack authoring launched — stories test against PE-1..16.
