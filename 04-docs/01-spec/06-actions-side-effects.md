# A6 — Actions & Side Effects

> Part A (extraction). Source: SMARTBillHub prototype `../../05-prototype/UtilityBilling.html`. Every control: writes, downstream effects, confirm, undo.
> Cardinal rule: anything not determinable from the UI is `UNKNOWN — <question>`, never invented.


| Screen | Control | Expected | Data changed | Side effects | Confirm? | Undoable? |
|---|---|---|---|---|---|---|
| S6 | Create utility & go live | Provision tenant | Tenant, Owner user, seeded lookups | Welcome email `INFERRED`; trial starts | — | — |
| S22 | Record payment ✓ | Post payment | Payment; bill/balance | Receipt email `INFERRED`; ledger entry `INFERRED` | — | via Reverse |
| S22 | Post adjustment ✓ | Adjust balance | Adjustment; balance; GL | Approval if flagged; audit; ledger `INFERRED` | approval | reverse `INFERRED` |
| S22 | Send statement ✓ | Send statement | — | Email/mail/SMS send | — | no |
| S22 | Print bill ✓ | Print/PDF | — | PDF render; printer/queue | — | — |
| S22 | Issue credit ✓ | Credit account | Credit; balance | Notify email; ledger `INFERRED` | — | reverse `INFERRED` |
| S22 | Disconnect notice ✓ | Queue notice | notice_history | Email/SMS/certified mail; field task `INFERRED` | — | no |
| S23 | Change plan ✓ | Reassign plan | Account.plan; proration | Customer notice; balance delta | preview shown | UNKNOWN |
| S24 | Send agreement ✓ | Payment plan | PaymentPlan + Installments | E-sign send; dunning paused; autopay enroll | — | UNKNOWN |
| S28 | Complete upload | Ingest reads | Read rows; flags | Rule engine run; compliance stamp (who/when) | — | UNKNOWN |
| S31 | Generate bills | Create bills | Bill rows | Emails/print batch; ledger; cycle close `INFERRED` | summary + compliance | UNKNOWN (correction path) |
| S31.3 | Bulk case actions | Apply to many | per-case | fees, notices, plans, estimates | — | UNKNOWN |
| S33 | Reverse / Reapply / Send receipts / Post to QuickBooks | bulk | Payment status/links | ledger; QBO push; emails | — | partial |
| S34 | Send reminder / Disconnect / Payment plan / Field visit / Write off | bulk AR | notice_history; balance; work orders | emails/SMS/mail; bad-debt GL (write-off) | write-off = Owner approval | mostly no |
| S38 | Reconcile 28 batches ✓ | Match & lock | Batch status | fee posting; lock; bookkeeper email | — | Unreconcile |
| S42/S43 | Send to QuickBooks | Push period | export record | QBO journal entries; period lock | — | UNKNOWN |
| S46 | Export / Schedule / Print | report | report_run | file gen; schedule job; email | — | — |

`INFERRED` items must be confirmed by product/finance. `UNKNOWN — whether emails are transactional templates the tenant can edit (Settings→Notifications was referenced but not built).`

---


## Addendum — User menu actions (2026-08-07)
| Control | Effect | Confirm | Undo |
|---|---|---|---|
| Change password ✓ | updates credential; option to revoke other sessions | — | no |
| Enable 2FA ✓ | enrolls TOTP/SMS second factor | — | disable later |
| Save profile ✓ | updates own name/email/phone | — | edit |
| Sign out | ends session → public screen | — | re-login |


## Addendum — Finance GL/refund actions (2026-08-07 r2)
| Control | Effect | Side effects | Undo |
|---|---|---|---|
| Post journal entry ✓ | creates balanced JE (standard/accrual/reversing) | journal_entries + lines; audit log; must balance | reversing entry |
| Record refund ✓ | outbound refund (check/ACH) with status | payment(type=refund); GL debit AR-credit/credit cash; status Issued→Cleared/Void | void |
| Export trial balance | download | file gen | — |
| Account ledger PDF/CSV | download per account+premises+range | file gen | — |
