# CR-191-BRC10 · A portal application with a fee is paid online by card before it is submitted

**Raised:** 2026-10-23 by the Product Owner, in chat, answering lane PORTAL-SR-ACK's question about the acknowledgement of a fee-bearing portal application.

**Requester's words, verbatim:**
1. *"Provide an option for the user to choose whether to pay the $10.00 application fee now or later, and display the applicable fee message accordingly."* (superseded by 2–4)
2. *"if there is a application or service fee then consumer will have to pay it online; they can't say pay later"*
3. *"That is application fee it is not refunded generally many time utilities charger 0 application fees"*
4. *"3A"* — card on the same screen, through the portal's existing online payment, and the request is submitted only once the payment succeeds.

**Rulings:** decision log 2026-10-23, *"Portal application fee: paid online at submission, no "Pay later", not refunded"*, and the build judgments in *"Portal application fee paid online: how it is built"*.

**Classification:** CHANGE. Users cannot pay an application fee in the portal today, and the ruling reverses a signed rule for portal requests (*"THE APPLICATION FEE IS RAISED AT APPROVAL, NOT AT CAPTURE"*, 2026-09-22).

## What changes

| Surface | Change |
|---|---|
| Portal application, last step | Fee above $0.00 → card fields and a consequence box; the button reads *Pay $10.00 and submit*. $0.00 or no fee → no payment step, *Nothing is charged today.* stays. |
| Submit endpoint | Charges the card through `payments.gateway.charge()` (the same call quick pay uses), then writes the request in one transaction. A decline or silence writes nothing. |
| Books | A `counter_receipts` row (card), the counter's collection pair and its release pair at once; state `earned`. |
| Approval | Nothing to raise or collect; the release posts nothing. Staff requests unchanged. |
| Acknowledgement | The fee class (*"You paid $10.00 by card. Your receipt number is SR-…"*). |

## What does not change
Staff-entered requests; quick asks and reports (no fee); *no application fee is ever carried to an account*.

## Status
BUILT (2026-10-23), lane PORTAL-FEE — commits on `claude/serene-noether-71ie5b`; version not bumped (the coordinator releases). The PostgreSQL run is DONE (2026-10-23, lane PORTAL-FEE-2): 20/20 on PostgreSQL 16, including the five `DEF-PAY-10554` cases. `DEF-PAY-10554` (a reload after an approved charge and a failed save could charge twice) is fixed in `3a0dcbeba`: the key is the server's, kept on the draft, and an approval is kept on the draft before the request is written. Residual: `DEF-PAY-10568` (low).
