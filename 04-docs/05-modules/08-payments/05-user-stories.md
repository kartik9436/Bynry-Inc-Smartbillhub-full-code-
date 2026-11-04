# payments — User Stories (INDEX)
> Pack authored 2026-08-08 against the closed payments session (BR-PAY-001..031 all CONFIRMED; B2 Addendum r12 approved; PE-1..16 fixtures; platform outbound queue = BR-NOT-005).

**Stories live inside their epic files in [`06-epics/`](06-epics/).** This index is generated from story frontmatter at each pack merge — do not hand-edit story content here.

| Story | Title | Epic file | Status | Wave |
|---|---|---|---|---|
| US-PAY-001 | Single payment entry: posting date + clearing date, always both | [EP-PAY-01-record-payments.md](06-epics/EP-PAY-01-record-payments.md) | draft | W4 |
| US-PAY-002 | Payment purpose: bill · deposit · plan-down · prepay (money with no open bill) | [EP-PAY-01-record-payments.md](06-epics/EP-PAY-01-record-payments.md) | draft | W4 |
| US-PAY-003 | Bulk lockbox/CSV: staged import (batch → validate → preview → commit) | [EP-PAY-01-record-payments.md](06-epics/EP-PAY-01-record-payments.md) | draft | W4 |
| US-PAY-004 | S33 Record-payments ledger: full IS-5 capability row | [EP-PAY-01-record-payments.md](06-epics/EP-PAY-01-record-payments.md) | draft | W4 |
| US-PAY-005 | S32 Payments summary: today, method mix, failed, collections, needs-attention | [EP-PAY-01-record-payments.md](06-epics/EP-PAY-01-record-payments.md) | draft | W4 |
| US-PAY-006 | The allocation engine: oldest first; usage+base → taxes → fees last | [EP-PAY-02-allocation.md](06-epics/EP-PAY-02-allocation.md) | draft | W4 |
| US-PAY-007 | Overpayment / carried credit: auto-apply, visible, refundable | [EP-PAY-02-allocation.md](06-epics/EP-PAY-02-allocation.md) | draft | W4 |
| US-PAY-008 | Reapply: reversing allocation rows + new rows, reason + audit — never edits | [EP-PAY-02-allocation.md](06-epics/EP-PAY-02-allocation.md) | draft | W4 |
| US-PAY-009 | NSF: reversing row, original due date stands, fee auto-added, privilege flag | [EP-PAY-03-exceptions.md](06-epics/EP-PAY-03-exceptions.md) | draft | W4 |
| US-PAY-010 | Reverse: windows (ACH 60d · card 120d · check unlimited), approval path, consequence messaging | [EP-PAY-03-exceptions.md](06-epics/EP-PAY-03-exceptions.md) | draft | W4 |
| US-PAY-011 | Refunds: only from real credit, Admin approval, check/ACH v1, immutable + receipt | [EP-PAY-03-exceptions.md](06-epics/EP-PAY-03-exceptions.md) | draft | W5 |
| US-PAY-012 | Write-offs: initiated in Payments, approved + reported in Finance | [EP-PAY-03-exceptions.md](06-epics/EP-PAY-03-exceptions.md) | draft | W4 |
| US-PAY-013 | S34 Outstandings: AR high→low, aging KPIs, bulk actions | [EP-PAY-04-outstandings-collections.md](06-epics/EP-PAY-04-outstandings-collections.md) | draft | W4 |
| US-PAY-014 | The collection sequence engine: due+3 → late fee → 10-day → 5-day → 48h certified final | [EP-PAY-04-outstandings-collections.md](06-epics/EP-PAY-04-outstandings-collections.md) | draft | W4 |
| US-PAY-015 | Manual reminder + disconnect-notice modals (bulk, queue-writes, notice_history) | [EP-PAY-04-outstandings-collections.md](06-epics/EP-PAY-04-outstandings-collections.md) | draft | W4 |
| US-PAY-016 | Returned mail: mark returned → bad-address flag → needs-attention → paper suppressed | [EP-PAY-04-outstandings-collections.md](06-epics/EP-PAY-04-outstandings-collections.md) | draft | W4 |
| US-PAY-017 | Plan rows + schedule math + activation on signature (payments-owned) | [EP-PAY-05-payment-plans.md](06-epics/EP-PAY-05-payment-plans.md) | draft | W4 |
| US-PAY-018 | Plan notices + missed tracking: reminder −3d · missed day+1 · 2nd miss VOIDS | [EP-PAY-05-payment-plans.md](06-epics/EP-PAY-05-payment-plans.md) | draft | W4 |
| US-PAY-019 | Dunning + disconnect pause while active & current; resume on void/close | [EP-PAY-05-payment-plans.md](06-epics/EP-PAY-05-payment-plans.md) | draft | W4 |
| US-PAY-020 | Deposit batches: day × method, DEP- numbering, S37 list | [EP-PAY-06-deposits-bank-rec.md](06-epics/EP-PAY-06-deposits-bank-rec.md) | draft | W5 |
| US-PAY-021 | S38 bank import wizard: upload → auto-match (amount + date ±3d) → confirm & reconcile | [EP-PAY-06-deposits-bank-rec.md](06-epics/EP-PAY-06-deposits-bank-rec.md) | draft | W5 |
| US-PAY-022 | S40 reconcile modal: explain every difference with reason + GL | [EP-PAY-06-deposits-bank-rec.md](06-epics/EP-PAY-06-deposits-bank-rec.md) | draft | W5 |
| US-PAY-023 | S39 batch detail + the reconciled lock (Unreconcile is the only reversal) | [EP-PAY-06-deposits-bank-rec.md](06-epics/EP-PAY-06-deposits-bank-rec.md) | draft | W5 |
| US-PAY-024 | Autopay capture-intents: bill issue records the intent; staff record the money | [EP-PAY-07-autopay-receipts.md](06-epics/EP-PAY-07-autopay-receipts.md) | draft | W4 |
| US-PAY-025 | Receipts: auto-queued on every cleared payment; manual re-send from S35 | [EP-PAY-07-autopay-receipts.md](06-epics/EP-PAY-07-autopay-receipts.md) | draft | W4 |

**25 stories · 7 epics.** Rules: [`02-business-rules.md`](02-business-rules.md) · Model + PE-1..16 fixtures: [`07-pre-session-model.md`](07-pre-session-model.md) · Fields: [`03-field-map.md`](03-field-map.md) · Flows: [`04-flows.md`](04-flows.md) · Traceability: [`../../10-traceability-matrix.md`](../../10-traceability-matrix.md)
