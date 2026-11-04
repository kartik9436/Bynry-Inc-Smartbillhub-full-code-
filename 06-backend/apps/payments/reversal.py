# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-009 (NSF — TC-1 the PE-7 bounce, TC-2 the ORIGINAL due date,
#           TC-3 the counts and the privilege flag, TC-5 the uncleared payment,
#           TC-6 the frozen rows, TC-7 isolation)
#           Screens: S33 · S35 · S40
#           (The staff-initiated Reverse story is deliberately NOT cited here —
#           see THE STAFF REVERSE IS NOT THIS STORY in the docstring below.)
# Rules:    BR-PAY-002 (append-only; a reversal is a NEW row, never an edit) ·
#           BR-PAY-011 (reversal windows; always reversing entries) ·
#           BR-PAY-013 (NSF: reversing row + allocations reversed; AR
#           reinstated at the ORIGINAL due date, the late-fee clock never
#           resets; NSF charge code auto-added; nsf_count++; N NSFs → cash-only
#           / no-autopay flag) · BR-PAY-021 (NSF hangs off the CLEARING side) ·
#           BR-PAY-028 (idempotency) · BR-PAY-031 (reversing allocation rows) ·
#           BR-PAY-1070 (2026-09-01, CR-059 CS-5 — reversing a payment is
#           Admin-only and the gate is on the SERVICE, not only the route) ·
#           BR-PAY-036 (a payment is always accepted — so nothing here reads
#           the account's standing either) · BR-BIL-007 (the NSF fee is the
#           tenant's charge code, never typed) · BR-BIL-071 (lateness is the
#           ACTUAL arrival date) · BR-LED-003 (a correction is a NEW mirror
#           entry) · CLAUDE.md rule 1 (tenant scoping) · rule 2 (money) · rule
#           4 (financial immutability) · rule 5 (only the ledger posts) · rule
#           6 (idempotency) · rule 7 (every money action writes audit_log)
# Tests:    06-backend/tests/test_us_pay_009_nsf.py ·
#           06-backend/tests/test_cr048_b3_payments_fires_its_events.py (the
#           `payment_failed` letter and the switch that stops it) ·
#           06-backend/tests/test_cr059_cs5_reverse_door.py (the door, the
#           service-level Admin gate and one reversal under a double submit)
# Impacts:  apps/payments/receipts.queue_failed_payment_notice (ADDED 2026-08-29
#           · CR-048 B3 — the customer's returned-payment letter, fired as the
#           SET-12 event `payment_failed` only when the reason is NSF) ·
#           apps/payments/ledger_seam.reverse_payment_entry + post_bank_fee ·
#           apps/payments/billing_seam.allocated_so_far (a reversing allocation
#           row is what re-opens the bill) · apps/payments/selectors
#           .account_credit_position (the figure that may now be NEGATIVE) ·
#           apps/payments/refunds (a refunded credit is what makes it negative)
# ───────────────────────────────────────────────────────
"""A payment comes BACK — the reversal half of this module (EP-PAY-03).

HUMAN-OWNED (CLAUDE.md 🔒 — this file holds an idempotency key on inbound money,
writes money rows, and hands a reversal to the ledger posting service).
HUMAN-REVIEW-PENDING — AI-authored 2026-08-11 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*); row in
12-governance/09-human-review-ledger.md.

Until this file existed a payment could be recorded, allocated and posted, and
**nothing in the product could reverse one.** A cheque that bounced was a
support call and a hand-written journal entry.

════════════════════════════════════════════════════════════════════════════
THE ONE SENTENCE THIS FILE IS BUILT AROUND (hard rule 4)
════════════════════════════════════════════════════════════════════════════
**A reversal is a NEW ROW. Nothing here edits the payment that bounced.**

BR-PAY-002: *"Payments append-only once out of processing; reversal = new
reversing row"*. PE-7 states the shape in the same breath: *"cleared check
292.87 bounces → reversing payment row **−292.87** (append-only, BR-PAY-002),
allocations reversed"*. So a bounce writes:

    payments      ONE new row, amount NEGATIVE, status `reversed`,
                  `reverses_payment_id` -> the original, `reversal_reason` set
    allocations   ONE new NEGATIVE row per row the original wrote, hung off the
                  REVERSING payment (the original's rows are untouchable)
    journal       the LEDGER'S OWN MIRROR of the original entry — never a
                  compensating entry composed here (BR-LED-003, US-LED-003 §5)
    audit_log     `payment.nsf` / `payment.reversed` (hard rule 7)

The original payment row is never opened. Its status stays `cleared`, because
the database refuses to change it and because that is the truth: the payment
DID clear, and then it came back. **"Has this payment been reversed?" is
therefore a question about the EXISTENCE of a reversing row, never about a flag
on the original** — `selectors.reversal_of` answers it. EP-PAY-03 §5's phrase
*"status reversed on the pair"* cannot mean the original row: hard rule 4 and
the trigger in `migrations/0002` both forbid it, and this is written down here
because the next reader will meet that phrase before they meet this file.

════════════════════════════════════════════════════════════════════════════
THE STAFF REVERSE IS NOT THIS STORY, AND THE DOOR TO IT IS SHUT
════════════════════════════════════════════════════════════════════════════
This file implements the CLEARING-SIDE failure — the bank returned the item —
and nothing else. The staff-initiated Reverse (S35's modal, US-PAY-010) is
governed by **BR-PAY-011**, CONFIRMED: *"Reversal windows: ACH 60d, card 120d,
check unlimited (NSF); paid/cross-period requires Admin/Executive approval;
always reversing entries; consequence message shown before confirm"*. **Only
the third of those four clauses is built here.**

The first version of this file accepted all four S35 reasons, which quietly made
it a general Reverse with no windows, no approval and no consequence message —
a clerk could have reversed an ACH payment on day 200 with nobody approving it.
Gate G10 is what caught it, by asking for that story's TC-named tests and
finding none. `SUPPORTED_REASONS` is now `(nsf,)` and the other three are
refused by name.

A bounce needs none of those clauses, which is why this split is not a
compromise: BR-PAY-011 itself puts cheques on an UNLIMITED window and names NSF
as the reason for it, and a returned item is the bank's decision rather than a
staff correction — there is no window to be outside of and nothing to approve.

════════════════════════════════════════════════════════════════════════════
THE ORIGINAL DUE DATE STANDS BECAUSE NOTHING TOUCHES IT
════════════════════════════════════════════════════════════════════════════
BR-PAY-013: *"AR reinstated at the ORIGINAL due date (late-fee clock never
resets)"*. There is no code below that reinstates a due date, and that absence
IS the implementation: a bill re-opens because its allocation was reversed, and
`invoices.due_date` was never written by anything in this module in the first
place. J12 step 2 states the consequence — *"the late-fee clock runs from Jul 22
as if the payment never happened"*.

The late-fee test itself is billing's and is NOT restated here.
`apps/billing/late_fee.overdue_portion` + `assess_late_fee` already implement
**BR-BIL-071** (PO ruling 2026-08-11: lateness is the ACTUAL arrival date), they
take payment records as an ARGUMENT, and they read `invoices.due_date`. A
reversed payment simply stops being money that arrived. Restating any of that
arithmetic here would give the product two late-fee rules that could disagree.

════════════════════════════════════════════════════════════════════════════
THE CREDIT MAY GO NEGATIVE, AND THAT IS A REAL DEBT (PO, 2026-08-11)
════════════════════════════════════════════════════════════════════════════
OQ-132, closed by the Product Owner in these words: **"Yes, it's a real debt"**.

Worked, on the frozen J15 chain:

    19 Jul   payment $350.00 against $292.87 open  ->  credit  $57.13
    24 Jul   refund cheque $57.13 issued and paid  ->  credit    $0.00
     3 Aug   the $350.00 cheque bounces            ->  credit  −$57.13

Reversing the payment pulls back $292.87 of allocations (the bills re-open) AND
$57.13 of a credit that has already left the building. The account credit lands
at **−$57.13** and stays there: it is a genuine receivable the utility pursues,
not a display artefact.

**Nothing in this module floors it at zero.** `selectors.account_credit_position`
returns the signed figure and says so in its own docstring; the ledger mirror
debits `customer_credit_balance` without asking whether the result is positive.
The PO's ruling states the consequence for everyone downstream: *"any code,
screen or report that assumes a customer credit is non-negative is wrong — the
balance may be below zero and must render and age as a debt"*.

════════════════════════════════════════════════════════════════════════════
IDEMPOTENCY: THREE GUARDS, THREE DIFFERENT FACTS (hard rule 6)
════════════════════════════════════════════════════════════════════════════
*"A webhook or file that reports the same bounce twice must not double the
debt."* Three independent things could go wrong and each has its own guard —
listed apart because **DEF-058 is what happens when one guard silently stands in
for another**, and each is asserted by its own test rather than by the shared
outcome:

  1. **The same bank ADVICE reference is used for a DIFFERENT payment** — a
     returns feed that reuses `RET-99012` for two cheques. `_by_advice` REFUSES
     it by name. Left unchecked, the insert reaches `uq_payments_webhook_key`,
     the `IntegrityError` handler finds the OTHER payment's reversal and reports
     "already reversed" — so a real bounce is silently swallowed and that
     customer's bills stay settled with money the bank took back.
  2. **The same PAYMENT is bounced twice** — a retried webhook (same key) or two
     clerks (different keys). `_by_payment` replays it, and
     `uq_payments_reverses`, the partial unique index on
     `(tenant, reverses_payment_id)`, is the database half: **a payment is
     reversed once.**
  3. **The same ENTRY is mirrored twice in the books.** Guarded by the ledger's
     own `posting_key` replay and by `uq_journal_entries_reversal`.

**GUARD 1 WAS REWRITTEN BECAUSE THE RED PROOF CAUGHT IT STANDING IN FOR NOTHING,
and that is worth recording rather than quietly fixing.** It first read "return
the reversal under this key, whatever it reverses" — and switching it off left
BOTH idempotency tests green, because guard 2 catches the same-payment case on
the same code path. That is precisely DEF-058: *"a second guard that silently
substitutes for the first is how the first stops being checked."* Rewriting it
to refuse a key that names a different payment gave it a fact of its own, an
observable absence, and a test that goes RED without it — and it turned out to
be a real defect, not a redundancy: the old shape lost a genuine bounce.

════════════════════════════════════════════════════════════════════════════
WHAT A BOUNCE STILL CANNOT DO, EVERY ONE OF IT REPORTED ON THE RESULT
════════════════════════════════════════════════════════════════════════════
Named here, carried as CODES on `ReversedPayment.problems`, and asserted by
tests — because a docstring that claims a gap is not a gap a screen can render
(hard-won law 1) and a feature that silently skips half of a CONFIRMED rule is
worse than one that refuses.

  * ~~**THE CUSTOMER'S NSF FEE IS NOT ADDED.**~~ **CLOSED 2026-10-30
    (`DEF-PAY-10698`), and the entry stays here rather than vanishing because
    the next reader will meet `nsf_fee_not_added` in the register and in two
    months of results.** It read *"`penalty_charge_line` refuses on exactly
    this gap today: 'rating publishes no charge-code read'"* — **false since
    2026-08-27** (`rating.selectors.charge_by_code`, DEF-708) and false of
    `penalty.py` itself since 2026-09-15 (DEF-BIL-5317), while this file kept
    citing it: a justification by reference outliving its reason (law 1). PO
    2026-10-30, verbatim: *"Do not hardcode check NSF Account> Unit> Plan>
    Charge code"*. An `nsf` bounce now asks BILLING (`billing_seam.raise_nsf_fee`
    → `apps/billing/nsf_fee.py`) to walk account → unit → plan → the plan's
    code DECLARED `is_nsf_fee` and raise it as an issued fee bill; the amount is
    the tenant's, never typed here. Worked: cheque 4102 $76.40 on a plan whose
    NSF is $30.00 → owes **$106.40**. The clerk may untick it WITH a reason
    (PO, same day). Every bounce carries its own outcome row
    (`NSF_FEE_OUTCOMES`): `nsf_fee_charged`, `nsf_fee_waived`, or the named
    reason none was charged — `nsf_fee_not_set_on_plan` above all, never $0.00.
  * ~~**`accounts.nsf_count` IS NOT INCREMENTED and the cash-only / no-autopay
    PRIVILEGE FLAG IS NOT SET.**~~ **BOTH ARE CLOSED (2026-08-15, DEF-069 +
    DEF-070) and the entry stays here rather than vanishing, because the next
    reader will meet its shape in the tests and in the register.** It read:
    *"both are on `accounts`, which is CUSTOMERS' table (B2 r12 #12), and
    payments may not write another module's table (B1 / DB-16); customers
    publishes no seam for either, and the privilege flag has no column at
    all."* Every clause was true. What closed it is **one published function in
    customers** — `apps.customers.services.record_nsf(account_id)` — resolved
    BY NAME here (`_record_nsf` below), plus the column r12 #12 always named
    (customers migration 0009). **BR-PAY-013's counting half is now
    implemented**, and until this landed no code was allowed to claim it was.
    What a bounce can still fail to do is decide the FLAG when the tenant's
    `nsf_privilege_n` cannot be read — reported as
    `nsf_privilege_threshold_unavailable`, never as an assumed 2.
  * ~~**THE LADDER IS NOT ACTUALLY RESTARTED — `resume_collections` is
    accepted, documented and read by nothing.**~~ **WIRED 2026-09-01 (CR-059
    CS-5), and the entry stays here rather than vanishing because the next
    reader will meet its shape in the register and in three weeks of results.**
    The ruling — **PO 2026-08-12, OQ-133 CLOSED**, *"Restart from the
    beginning"* — was on file the whole time; what was missing was the call.
    The question it answered was a consumer-protection one: by AGE, J12's own
    account is 58 days overdue the moment its cheque comes back, so the
    customer's first contact after the bounce would be a certified 48-hour
    disconnection notice for a bill they believed they had paid. Rung 1 gives
    them the whole sequence again. **What closed it is one call** —
    `ladder.restart_after_bounce`, this module's own collection state (B2 r12
    #7), resolved BY NAME in `_restart_ladder` below and made from
    `_write_reversal` **only when the caller passes `resume_collections=True`**.
    A bounce still PAUSES by default and a human resumes — the ruling settles
    WHERE it restarts, not that it should happen with nobody asking. Codes:
    `collection_ladder_paused` while paused, `collection_ladder_restarted` when
    it ran, `collection_ladder_not_restarted` when the reset could not be made.
    **This one is hard-won law 1 in the flesh** — `ladder.py`'s own docstring
    said *"`reversal.py` calls it"* for three weeks while nothing did, and no
    gate in this repo can read a sentence. The test that closed it reads the
    SYNTAX TREE instead — `tests/test_cr059_cs5_ladder_restart.py` — so the
    claim and the call now fail together.
  * ~~**NO CUSTOMER NOTICE IS QUEUED** (BR-PAY-013 + BR-NOT-005, US-PAY-009
    TC-4). `outbound_messages` is the platform queue and this path does not
    write it — US-PAY-025 / EP-PAY-07 owns that. Code:
    `no_nsf_notice_queued`.~~ **CLOSED 2026-08-29 (CR-048 B3), and the entry
    stays here rather than vanishing because the next reader will meet its shape
    in the register and in six months of results.** Every clause was true. What
    closed it is one call — `receipts.queue_failed_payment_notice`, US-PAY-025's
    own module, resolving `queue_document` BY NAME exactly as the receipt does —
    made from `_write_reversal` below **only when the reason is `nsf`**, and
    naming the SET-12 event `payment_failed` so this utility's rule decides
    whether the letter goes at all. The outcome rides every bounce as
    `payment_failed_notice_queued` or, when the utility has switched that
    notification off, as the queue's own reason for writing nothing. **What is
    still absent is the `notice_history` half of TC-4:** `NOTICE_TYPES`
    (`collections_models.py`) has no member for a returned payment, and minting
    one would be this lane defining a collections notice type. Reported, not
    invented.

════════════════════════════════════════════════════════════════════════════
A BOUNCE INSIDE A RECONCILED DEPOSIT BATCH NO LONGER REFUSES (OQ-134, RULED)
════════════════════════════════════════════════════════════════════════════
**The list above carried a sixth item until 2026-08-12**, and it read: *"a
bounce inside a RECONCILED deposit batch REFUSES — OQ-134 is open"*. What that
refusal claimed was that reversing a member of a locked batch either rewrites a
signed-off bank tie-out or leaves one saying money we no longer hold, and that
choosing between the two was a finance call rather than an implementing lane's.
**It was correct while the question stood.** It is recorded here rather than
deleted because the next reader will meet its shape in EP-PAY-06 and in the
tests, and a gap that quietly disappears is indistinguishable from one nobody
noticed.

**PO ruling, 2026-08-12 (OQ-134 CLOSED):** *"if this happen Utility will charge
Cheque bounce charges and add new entry - this will be mnaul process by utility
user in payments or in finance we have to decide the place - you decide for
me"*. **The lock HOLDS and the bounce is NEW ROWS.** DEP-260805-CHK's 8 cheques
stay at **$2,840.00** after cheque #4021 (**$100.00**) is returned three weeks
later, because the bank statement the batch was agreed against did not change —
and the utility raises its bounce charge as a new entry. The placement half was
delegated and decided HERE, in payments, on the payment;
`_refuse_if_batch_locked` carries that reasoning in full.

It is no longer a gap, so it is no longer a `problems` code. What that function
still refuses is a payment naming a batch this process cannot READ or that does
not exist for the tenant — a broken reference, which was never the question the
PO answered.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from importlib import import_module
from typing import Any

from django.db import IntegrityError, transaction

from core import audit as core_audit
from core import errors
from core import numbering
from core import permissions
from core import tenancy as core_tenancy

from apps.payments import billing_seam, idempotency, ledger_seam, models, reversal_rules
from apps.payments.exceptions import PaymentRuleError

__all__ = ["ReversedPayment", "reverse_payment", "REVERSE_UNAVAILABLE"]

ZERO = Decimal("0")

#: Audit action codes. Codes, never prose — the trail is grouped on them, and
#: EP-PAY-03 names both: US-PAY-009 §5 `payment.nsf`, US-PAY-010 §5
#: `payment.reversed`. A bounce is one specific KIND of reversal, so the reason
#: picks the code and a screen filtering on `payment.nsf` gets bounces only.
AUDIT_NSF = "payment.nsf"
AUDIT_REVERSED = "payment.reversed"


def _audit_action(reason: str) -> str:
    return AUDIT_NSF if reason == models.REVERSAL_REASON_NSF else AUDIT_REVERSED


#: What a reversal does NOT do, carried on EVERY result — the same discipline as
#: `services.RECORD_UNAVAILABLE` and `apps/billing/issue.ISSUE_UNAVAILABLE`. A
#: caller must not have to infer an absence and a reviewer must not have to take
#: a docstring's word for it.
REVERSE_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    # ⚠ `nsf_fee_not_added` LIVED HERE UNTIL 2026-10-30 (`DEF-PAY-10698`) and it
    # said *"Rating publishes no charge-code read … so there is no amount to
    # add"*. That stopped being true on 2026-08-27 (`charge_by_code`, DEF-708)
    # and the claim rode every result for two more months (hard-won law 1). The
    # fee is now charged on an `nsf` bounce — PO 2026-10-30, *"Do not hardcode
    # check NSF Account> Unit> Plan> Charge code"* — and every bounce carries
    # its OWN outcome row (`NSF_FEE_OUTCOMES` below) instead of this standing
    # claim: removed rather than reworded, for `no_nsf_notice_queued`'s reason.
    # ⚠ `no_nsf_notice_queued` LIVED HERE UNTIL 2026-08-29 (CR-048 B3) and it
    # said *"nothing is queued and nothing is sent"*. The queue half is done —
    # `_write_reversal` now calls `receipts.queue_failed_payment_notice` on an
    # NSF and every bounce carries that call's OWN outcome row instead of this
    # standing claim. It was removed rather than reworded because a static
    # "cannot" beside a per-bounce "did" is two answers to one question.
    {
        "code": "no_nsf_notice_history_row",
        "br_ref": "BR-PAY-017",
        "detail": "US-PAY-009 TC-4 has two halves — queue the customer's returned-payment "
        "letter AND append `notice_history`. The letter is queued (CR-048 B3). The history "
        "row is not: `NOTICE_TYPES` has no member for a returned payment, and minting one "
        "would define a collections notice type from inside the bounce path. So the S34 "
        "notice trail does not show this letter, and the outbound queue does.",
    },
    {
        "code": "account_balance_cache_not_updated",
        "br_ref": "BR-CUS-015",
        "detail": "`accounts.balance` is customers' CACHED column and payments may not write "
        "another module's table (B1 / DB-16). The LIVE position is derivable — invoice totals "
        "minus this module's `allocations` rows, which the reversing rows have just moved.",
    },
)

#: Kept OUT of `REVERSE_UNAVAILABLE` deliberately: this is not a gap in the
#: build. It was written while OQ-133 was an OPEN QUESTION — an unanswered
#: question and a missing feature read very differently to whoever picks this
#: up — and it survives the ruling of 2026-08-12 unchanged in KIND, because the
#: pause itself was never the question. A bounce still PAUSES and a person
#: resumes; what the PO settled is WHERE the ladder re-enters, which the detail
#: below now states.
#:
#: ⚠ **CARRIED ONLY WHEN THE CALLER DID NOT ASK TO RESUME (CR-059 CS-5).** It
#: rode EVERY result until 2026-09-01, including the results of bounces that
#: passed `resume_collections=True` — which was accurate then only because the
#: flag was read by nothing. A bounce that restarts the ladder carries
#: `LADDER_RESTARTED` instead: a static *"this ladder is paused"* beside a
#: per-bounce *"it was restarted"* is two answers to one question, which is the
#: reason `no_nsf_notice_queued` was removed rather than reworded on 2026-08-29.
LADDER_PAUSED: dict[str, Any] = {
    "code": "collection_ladder_paused",
    "br_ref": "BR-PAY-017",
    "detail": "This account's collection ladder is PAUSED by the bounce and a person resumes it. "
    "When it is resumed it restarts at the FIRST rung (PO 2026-08-12, OQ-133) rather than at "
    "whatever rung the account's age would reach: evaluated by AGE this account can be 58 days "
    "overdue the instant its cheque comes back (J12's worked case: $1,842.10 due 6 Jul, returned "
    "2 Sep), which would make a certified 48-hour disconnection notice the customer's first "
    "contact after a cheque they believed had cleared.",
}

#: The OTHER half of the same fact: this bounce DID reset the ladder, because
#: its caller asked. An OUTCOME row rather than a gap — `problems` has carried
#: what a bounce DID as well as what it could not do since the returned-payment
#: letter started reporting itself (CR-048 B3), and a caller must not have to
#: infer either one.
LADDER_RESTARTED: dict[str, Any] = {
    "code": "collection_ladder_restarted",
    "br_ref": "BR-PAY-016 · BR-PAY-017",
    "detail": "this account's collection ladder was reset to its FIRST rung — the due+3 friendly "
    "reminder — because the caller asked to resume collections on this bounce (PO 2026-08-12, "
    "OQ-133, verbatim 'Restart from the beginning'). Resuming by AGE instead would make a "
    "certified 48-hour disconnection notice the customer's first contact about a bill they "
    "believed they had paid: J12's own account is 58 days overdue the instant its $1,842.10 "
    "cheque comes back. The notices already sent are untouched — `notice_history` keeps the "
    "first walk of the ladder and the second one, in order.",
}

#: The caller asked and the reset could not be made. REPORTED BY NAME, never
#: assumed done and never silently skipped — the posture `_record_nsf` takes
#: when customers has not published its seam, and the posture customers' own
#: `record_nsf` takes when it cannot read the privilege threshold (it returns
#: `nsf_privilege_threshold_unavailable` and sets no flag rather than assuming
#: the shipped 2). The stake is the same here: a silent skip leaves a bounced
#: customer standing on the rung their AGE selected, which is the single
#: outcome OQ-133 was raised to prevent.
LADDER_RESTART_UNAVAILABLE: dict[str, Any] = {
    "code": "collection_ladder_not_restarted",
    "br_ref": "BR-PAY-016 · BR-PAY-017",
    "detail": "this bounce asked to resume collections and "
    "`apps.payments.ladder.restart_after_bounce` is not published on this deployment, so the "
    "collection state was NOT reset. The bounce itself is fully recorded and the reset is not "
    "guessed: the account still stands at whatever rung it had reached, which is exactly the "
    "outcome PO 2026-08-12 (OQ-133) ruled against, so a person must reset it from S34.",
}


#: ── DEF-PAY-10698 · THE NSF PENALTY, ONE OUTCOME PER BOUNCE (PO 2026-10-30) ──
#: An `nsf` reversal asks BILLING to charge the NSF code the account's PLAN
#: lists (account → unit → plan → charge code; `apps/billing/nsf_fee.py`), and
#: the result names what happened. Every absence is NAMED and none is a $0.00.
#: Keyed by billing's own status word, so the two modules cannot disagree.
NSF_FEE_OUTCOMES: dict[str, str] = {
    "charged": "the NSF penalty was charged as its own fee bill, at the price of the NSF code "
    "this account's plan lists (BR-PAY-013 · BR-BIL-007).",
    "nsf_fee_not_set_on_plan": "no NSF fee is set on this account's plan, so none was charged. "
    "The reversal is recorded in full.",
    "nsf_fee_ambiguous_on_plan": "this account's plan lists more than one NSF fee code, so none "
    "was charged rather than one picked by order. The reversal is recorded in full.",
    "nsf_fee_no_plan": "this account's unit stands on no plan, so no NSF fee could be found. The "
    "reversal is recorded in full.",
    "nsf_fee_cannot_be_priced": "the plan's NSF code could not be priced (billing's reason is "
    "attached — an account outside the billable set is one, DEF-PAY-10746), so none was "
    "charged. The reversal is recorded in full.",
    "nsf_fee_not_raised": "the NSF fee bill could not be raised (billing's reason is attached — "
    "an NSF fee already raised for this same bounced payment is the usual one; one fee per "
    "bounced payment, PO 2026-10-30). The reversal is recorded in full.",
    "nsf_fee_unavailable": "billing publishes no NSF fee service on this deployment, so none "
    "was charged. The reversal is recorded in full.",
    "nsf_fee_waived": "the clerk unticked the NSF penalty and gave a reason (PO 2026-10-30), so "
    "none was charged. The reason is on the audit row and the payment's history.",
}

#: The Bank memo's ceiling (PO 2026-10-30, LBX-04: *"optional free text (≤ 60
#: characters)"*). The bank's own words, kept on the REVERSING row.
BANK_MEMO_MAX = 60


def _nsf_fee_problem(outcome: dict[str, Any]) -> dict[str, Any]:
    status = str(outcome.get("status") or "nsf_fee_unavailable")
    code = "nsf_fee_charged" if status == "charged" else status
    row: dict[str, Any] = {
        "code": code,
        "br_ref": "BR-PAY-013 · BR-BIL-007",
        "detail": NSF_FEE_OUTCOMES.get(status, NSF_FEE_OUTCOMES["nsf_fee_unavailable"]),
    }
    if outcome.get("detail"):
        row["billing_detail"] = str(outcome["detail"])
    return row


def _clean_bank_memo(value: Any) -> str | None:
    """LBX-04 — the bank's words, trimmed; blank is absent; over 60 refuses."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > BANK_MEMO_MAX:
        raise PaymentRuleError(
            f"the Bank memo is {len(text)} characters and holds at most {BANK_MEMO_MAX} "
            "(PO 2026-10-30, LBX-04).",
            br_ref="BR-PAY-011",
        )
    return text


def _clean_waive(reason: str, charge_nsf_fee: bool, waive_reason: Any) -> str | None:
    """PO 2026-10-30, Q1 = A: the NSF penalty may be UNTICKED, and only WITH A
    REASON. A waiver with no words is refused rather than recorded blank —
    the reason is what the history shows a year later."""
    if reason != models.REVERSAL_REASON_NSF or charge_nsf_fee:
        return None
    text = str(waive_reason or "").strip()
    if not text:
        raise PaymentRuleError(
            "the NSF penalty was unticked without a reason. Say why it is not charged "
            "(PO 2026-10-30: it may be unticked WITH a reason).",
            br_ref="BR-PAY-013",
        )
    return text[:200]


@dataclass(frozen=True)
class ReversedPayment:
    """What one bounce did — and, on `problems`, what it could not do.

    `created=False` is the idempotent replay: this bounce has already been
    recorded, the FIRST reversing row is reported, and nothing was written the
    second time. A RESULT rather than an exception, for the reason
    `services.RecordedPayment` gives — a retried webhook is doing the right
    thing.

    `credit_reversed` is the part of the original payment that was sitting as
    account credit. When the customer has since been refunded it, the account's
    credit position goes NEGATIVE by exactly this much and that is a real debt
    (PO ruling 2026-08-11) — `credit_position_after` states the signed figure so
    a caller can assert it rather than recompute it.
    """

    reversal_id: str
    reversal_no: str | None
    original_payment_id: str
    created: bool
    amount: Decimal
    currency: str
    reason: str
    #: Σ of the reversing allocation rows, as a POSITIVE figure — how much AR
    #: was reinstated. The rows themselves are negative.
    allocations_reversed: Decimal = ZERO
    reopened: tuple[dict[str, Any], ...] = ()
    credit_reversed: Decimal = ZERO
    #: The account's credit position AFTER the bounce. May be below zero.
    credit_position_after: Decimal = ZERO
    journal_entry_id: str | None = None
    posting_key: str | None = None
    bank_fee: Decimal | None = None
    bank_fee_entry_id: str | None = None
    #: BR-PAY-013's counting half, through customers' published seam (DEF-069).
    #: `None` means the seam did not run — a REPLAY does not re-count a bounce
    #: that was already counted, and a bounce is not an NSF unless its reason
    #: says so. Never 0: "we did not count" and "the count is zero" are
    #: different facts and only one of them is safe to render.
    nsf_count: int | None = None
    #: BR-PAY-013's privilege half (DEF-070). `None` for the same reasons.
    cash_only_no_autopay: bool | None = None
    #: True only on the bounce that TRIPPED it — J12 step 4's moment.
    privilege_flag_tripped: bool = False
    #: ── CR-059 CS-33 ──────────────────────────────────────────────────────
    #: True when this reversal took back LESS than the payment still stood for.
    is_partial: bool = False
    #: What the payment still stands for AFTER this reversal. `0` means it is
    #: fully reversed and nothing more may come back against it. Served so a
    #: screen states the remainder rather than subtracting two figures itself
    #: and disagreeing with the service that will refuse the next request.
    still_stands: Decimal = ZERO
    #: ── DEF-PAY-10698 · the NSF penalty this bounce charged ─────────────────
    #: billing's status word (`charged`, `nsf_fee_not_set_on_plan`, …,
    #: `nsf_fee_waived`); None when the reason is not `nsf` or on a replay.
    nsf_fee_status: str | None = None
    nsf_fee_code: str | None = None
    #: The fee bill's total — None unless one was raised. Never 0.00 for "none".
    nsf_fee_amount: Decimal | None = None
    nsf_fee_invoice_id: str | None = None
    nsf_fee_invoice_no: str | None = None
    nsf_fee_waived_reason: str | None = None
    #: LBX-04 — the bank's own words, as saved on the reversing row.
    bank_memo: str | None = None
    problems: tuple[dict[str, Any], ...] = field(default=REVERSE_UNAVAILABLE)


def _tenant_id() -> Any:
    """CLAUDE.md rule 1 — nothing touches a tenant table without `app.tenant_id`."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _original(tenant_id: Any, payment_id: Any) -> models.Payment:
    """The payment that bounced — this tenant's, and CLEARED.

    US-PAY-009 TC-5, verbatim: *"NSF attempted on a payment that never cleared
    (still processing) → Rejected — NSF is a clearing failure (BR-PAY-021);
    processing payments cancel instead"*. A bounce is a fact about money that
    ARRIVED and went back; money that never arrived has nothing to go back.
    """
    try:
        payment = models.Payment.objects.filter(tenant_id=tenant_id, pk=payment_id).first()
    except (ValueError, TypeError):  # a malformed id is a caller mistake
        payment = None
    if payment is None:
        raise PaymentRuleError(
            f"payment {payment_id!r} is not one of this tenant's payments, so there is nothing "
            "to reverse (CLAUDE.md rule 1). Nothing is written.",
            br_ref="BR-PAY-002",
        )
    if payment.status == models.PAYMENT_PROCESSING:
        raise PaymentRuleError(
            f"payment {payment.payment_no or payment.pk} is still PROCESSING — the money never "
            "arrived, so it cannot come back. A bounce is a CLEARING-side failure (BR-PAY-021); "
            "a payment that has not cleared is CANCELLED instead (US-PAY-004 TC-2), which is a "
            "status move on a processing row and not a reversal.",
            br_ref="BR-PAY-021",
        )
    # ── CR-186-BRC10 (PO 2026-10-21) — a bounce works from `posted` AND
    # `cleared`: every new payment is posted, applied and journalled at entry,
    # so it can come back before or after its batch is reconciled. A
    # `cancelled` or `failed` payment never reached the bank and is refused
    # by name rather than by the arithmetic that happens to leave 0.00 to take.
    if payment.status in (models.PAYMENT_CANCELLED, models.PAYMENT_FAILED):
        raise PaymentRuleError(
            f"payment {payment.payment_no or payment.pk} is {payment.status} — it never reached "
            "the bank, so it cannot come back. Nothing is written.",
            br_ref="BR-PAY-021",
        )
    if payment.reverses_payment_id is not None:
        raise PaymentRuleError(
            f"payment {payment.payment_no or payment.pk} IS a reversing row — it is the record "
            "that another payment came back. Reversing a reversal would re-apply money the bank "
            "has taken; a customer who pays again after a bounce makes a NEW payment "
            "(BR-PAY-036: money is always accepted).",
            br_ref="BR-PAY-002",
        )
    if payment.amount <= ZERO:
        raise PaymentRuleError(
            f"payment {payment.payment_no or payment.pk} carries {payment.amount}, which is not "
            "money that can come back. Only a positive receipt is reversible.",
            br_ref="BR-PAY-002",
        )
    return payment


def reversed_so_far(tenant_id: Any, payment_id: Any) -> Decimal:
    """Σ of every reversal already standing against one payment, POSITIVE.

    CR-059 CS-33's first new rule (`BR-PAY-884`): *"a partial reversal may not
    exceed what the payment still stands for, and the sum of all reversals
    against one payment may never exceed it."*

    **THE SUM IS THE TRUTH AND `is_partial_reversal` IS NOT.** That column
    exists so a partial unique index can let ONE full reversal coexist with
    several partials; it is a fact about a single row. How much has come back is
    always this Σ, and a reader that trusted the flag instead would be one
    boolean away from letting a payment be reversed twice over.
    """
    from django.db.models import Sum

    total = models.Payment.objects.filter(
        tenant_id=tenant_id, reverses_payment_id=payment_id
    ).aggregate(total=Sum("amount"))["total"]
    return -(total or ZERO)


def reversed_so_far_by_payment(tenant_id: Any, payment_ids: Any) -> dict[str, Decimal]:
    """`reversed_so_far` for MANY payments in ONE query — Σ per original, POSITIVE.

    ⚠ **IT LIVES HERE RATHER THAN AT ITS CALLER BECAUSE THE RULE IS ONE RULE.**
    *How much of a payment has come back* is `BR-PAY-884`'s Σ over
    `reverses_payment_id`, and `reversed_so_far` directly above is the
    single-row form of exactly this. Written at a reader instead it would be a
    second implementation, free to drift the day a reversal gains a state — and
    what would drift is a figure a clerk reads off a deposit slip.

    **A PAYMENT WITH NO REVERSAL IS ABSENT FROM THE RESULT, NOT ZERO**, and a
    caller is expected to `.get(key, ZERO)`. That is not a convenience: this
    answers *what came back*, and a dict asserting `0` for every payment handed
    in would be a claim about rows it never looked at.

    Keys are `str(pk)`, because every caller is building a wire payload and a
    UUID key compared against a string one fails by finding nothing rather than
    by raising.
    """
    from django.db.models import Sum

    ids = list(payment_ids)
    if not ids:
        return {}
    rows = (
        models.Payment.objects.filter(tenant_id=tenant_id, reverses_payment_id__in=ids)
        .values("reverses_payment_id")
        .annotate(total=Sum("amount"))
    )
    return {str(row["reverses_payment_id"]): -(row["total"] or ZERO) for row in rows}


def _lock_original(tenant_id: Any, payment_id: Any) -> None:
    """⚠ **THE HALF OF `BR-PAY-884` A CHECK CANNOT DO ON ITS OWN (CS-33).**

    Two clerks each reverse 200.00 of a 292.87 payment at the same moment. Both
    read `reversed_so_far` as 0.00, both find 200.00 ≤ 292.87, and both commit —
    **and 400.00 has come back off a 292.87 payment.** No amount of arithmetic in
    Python closes that, because the two transactions never see each other's row.

    `SELECT … FOR UPDATE` on the ORIGINAL serialises them: the second waits, then
    reads the first's reversal and is refused by name. It is taken here, inside
    `reverse_payment`'s transaction and BEFORE the sum is read, because a lock
    taken after the read protects nothing.

    ⚠ **IT DOES NOTHING ON SQLITE, AND THAT IS WHY THE PROOF IS A POSTGRES
    TEST** (CLAUDE.md hard-won law 14). `config/settings/test.py` hardcodes
    in-memory SQLite, which serialises writers anyway and implements
    `select_for_update` as a no-op — so the whole race this function exists for
    is unobservable on the default suite and every test would pass with the lock
    deleted. `tests/test_cr059_cs33_partial_reversal.py` runs the concurrent
    case on real PostgreSQL under `requires_postgres`.

    ⚠ **AND THE DATABASE HOLDS THE SAME RULE INDEPENDENTLY.** `payments/0019`'s
    `trg_payment_reversal_sum` re-sums on INSERT and raises. Two guards on one
    arithmetic fact, which is the discipline `post_payment_cleared` already keeps
    for a balanced pair: a figure that is wrong here is wrong in the trial
    balance forever.
    """
    list(
        models.Payment.objects.select_for_update()
        .filter(tenant_id=tenant_id, pk=payment_id)
        .values_list("id", flat=True)
    )


def _reversible_amount(
    tenant_id: Any, original: models.Payment, amount: Decimal | None
) -> tuple[Decimal, bool]:
    """How much comes back, and whether that is PART of the payment.

    `None` means the whole of what still stands — which is the WHOLE payment on
    a first reversal and is what every caller before CS-33 meant. So the default
    behaviour is byte-for-byte what it was, and a payment already partly reversed
    can be finished off without the caller doing the subtraction.
    """
    already = reversed_so_far(tenant_id, original.pk)
    standing = original.amount - already
    if standing <= ZERO:
        raise PaymentRuleError(
            f"payment {original.payment_no or original.pk} is {original.amount} and {already} "
            "has already been reversed, so nothing of it still stands. A customer who pays "
            "again after a bounce makes a NEW payment (BR-PAY-036).",
            br_ref="BR-PAY-884",
        )
    if amount is None:
        return standing, already > ZERO
    if isinstance(amount, float):
        raise PaymentRuleError(
            f"the amount {amount!r} is a float. Money is NUMERIC(18,6) and never binary "
            "(CLAUDE.md rule 2) — refused rather than converted.",
            br_ref="BR-PAY-002",
        )
    if not isinstance(amount, Decimal):
        raise PaymentRuleError(
            f"the amount {amount!r} is not a Decimal.", br_ref="BR-PAY-002"
        )
    if amount <= ZERO:
        raise PaymentRuleError(
            f"a reversal of {amount} takes nothing back. Reversing a payment by a negative "
            "amount would be a second, invisible way to express a receipt.",
            br_ref="BR-PAY-884",
        )
    if amount > standing:
        raise PaymentRuleError(
            f"this reversal of {amount} would take the total reversed against payment "
            f"{original.payment_no or original.pk} to {already + amount}, and the payment is "
            f"{original.amount}. The sum of every reversal against one payment may never "
            "exceed it (BR-PAY-884) — anything more is money the customer never paid being "
            "taken back twice.",
            br_ref="BR-PAY-884",
        )
    return amount, amount < standing or already > ZERO


#: ⚠ **ALL FOUR, FROM 2026-09-03 (CR-059 CS-31, task 35). THIS TUPLE WAS
#: `(nsf,)` FOR THREE WEEKS AND THE REFUSAL WAS RIGHT WHILE IT STOOD.**
#:
#: The other three were refused BY NAME rather than quietly run through the NSF
#: machine, because `BR-PAY-011` governs a general reverse and three of its four
#: clauses were not implemented: a clerk could otherwise have reversed an ACH
#: payment on day 200, with no approval and no consequence message, through a
#: function whose subject is bounced cheques. Gate G10 caught the first version
#: of this file doing exactly that.
#:
#: **What changed is that the clauses are now built** — `reversal_rules.py`
#: carries the window, the approval requirement and the consequence composition,
#: and `_refuse_unless_staff_reversal_is_lawful` below stands them in front of
#: every staff reason. The NSF path is byte-for-byte what it was: no window, no
#: approval, and the count, the cash-only flag and the returned-payment letter
#: all still fire, because a returned item is the bank's decision and not a
#: staff correction. **The reason is the boundary and it is drawn in one place.**
SUPPORTED_REASONS: tuple[str, ...] = models.REVERSAL_REASONS


def _reason(reason: str) -> str:
    """One of BR-PAY-011's four reasons (US-PAY-009 the bounce, -010 the rest).

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THIS FUNCTION REFUSED THREE OF THE FOUR UNTIL 2026-09-03, AND THE   ║
    ║  REFUSAL WAS RIGHT WHILE IT STOOD. G10 IS WHAT PUT IT THERE.         ║
    ╚══════════════════════════════════════════════════════════════════════╝
    `reverse_payment` originally accepted all four reasons, which made it a
    general Reverse over a rule that was not implemented — **BR-PAY-011
    (CONFIRMED):** *"Reversal windows: ACH 60d, card 120d, check unlimited
    (NSF); paid/cross-period requires Admin/Executive approval; always reversing
    entries; consequence message shown before confirm"*. Only the third of those
    four clauses was built. So a clerk could have reversed an ACH payment on day
    200, with no approval and no consequence message, through a function whose
    subject is bounced cheques.

    **CR-059 CS-31 (task 35) BUILT THE OTHER THREE** — `reversal_rules.py` — and
    that is what re-opened this door, rather than a lane deciding the refusal had
    outlived its usefulness. `_refuse_unless_staff_reversal_is_lawful` below
    stands them in front of every staff reason, and the refusal here now fires
    only on a reason the COLUMN does not carry.

    A bounce still needs none of those clauses: BR-PAY-011 itself puts cheques on
    an UNLIMITED window and names NSF as the reason for it, and a returned item
    is the bank's decision rather than a staff correction, so there is no window
    to be outside of and nothing to approve.
    """
    if reason not in models.REVERSAL_REASONS:
        raise PaymentRuleError(
            f"{reason!r} is not one of the reversal reasons the S35 Reverse modal offers "
            f"({list(models.REVERSAL_REASONS)}). The reason decides which flow runs, so an "
            "invented reason is a reversal nobody can classify. The tenant-extensible lookup "
            "B2 r14 #2 anchors does not exist yet; when it does, it replaces this set.",
            br_ref="BR-PAY-011",
        )
    if reason not in SUPPORTED_REASONS:  # pragma: no cover - the two sets are equal today
        raise PaymentRuleError(
            f"a reversal with reason {reason!r} cannot be recorded on this path. The column "
            "carries it and this service does not implement it, which is a gap rather than a "
            "rule — it is refused by name instead of being run through a flow written for a "
            "different event.",
            br_ref="BR-PAY-011",
        )
    return reason


def _refuse_unless_staff_reversal_is_lawful(
    original: models.Payment, *, reason: str, on: date, approval: str | None
) -> dict[str, Any]:
    """BR-PAY-011's window and approval clauses, in front of a STAFF reversal.

    ⚠ **IT DOES NOTHING AT ALL FOR A BOUNCE, AND THAT IS THE RULE RATHER THAN A
    SHORTCUT.** BR-PAY-013 is the bounce rule and its NAME is the boundary: a
    returned item is the bank's decision, arriving when the bank says it
    arrives. A window would refuse to record a return that has already happened
    — the money is gone whatever this product says — and there is nobody to ask
    for approval, because nobody chose it. So the NSF path through this function
    is byte-for-byte what it was before CS-31 landed.

    For the three staff reasons it refuses twice, each by name:

      * **outside the tender's window** (ACH 60 days, card 120 days; a cheque and
        any tender BR-PAY-011 does not name are unlimited). The refusal carries
        the tender, the days elapsed and the limit, because CS-31 asks for the
        window *"returned as a reason rather than a boolean so it can be
        shown"*.
      * **approval required and not given** — the payment is already applied to
        an issued bill, or the day falls in a closed accounting period. The
        refusal names WHICH trigger fired, so a clerk is told what to go and get
        rather than that something is wrong.

    Returns the plan, so the caller records the very figures it refused on.
    """
    plan = reversal_rules.reversal_plan(original, reason=reason, on=on)
    if not plan["is_staff_correction"]:
        return plan

    window = plan["window"]
    if not window["within"]:
        raise PaymentRuleError(
            f"payment {original.payment_no or original.pk} was paid by "
            f"{window['tender']} on {window['measured_from']}, which is {window['days_elapsed']} "
            f"days ago, and a {window['tender']} payment may be reversed for "
            f"{window['limit_days']} days. It is outside that window, so this correction is not "
            "recorded. A payment past its window is put right by a credit note or a refund, "
            "both of which leave the original record standing.",
            br_ref="BR-PAY-011",
        )

    if plan["approval"]["required"] and not (approval or "").strip():
        triggers = ", ".join(plan["approval"]["reasons"])
        raise PaymentRuleError(
            f"reversing payment {original.payment_no or original.pk} needs an approval and none "
            f"was given ({triggers}). Reversing it re-opens a bill the customer has already "
            "been sent, or reaches into a month the books have closed, so somebody holding the "
            "role signs for it and the approval is recorded with the reversal.",
            br_ref="BR-PAY-011",
        )
    return plan


#: `CR-174-BRC10` — the shape of a Nacha return code: `R` and two characters
#: (`R01`, `R10`, `R1B`). Anything else is refused by name rather than stored,
#: because a code nobody can look up in the Nacha table explains nothing.
_NACHA_RETURN_CODE = re.compile(r"^R[0-9A-Z]{2}$")


def _return_code(value: Any) -> str | None:
    """The bank's return code, upper-cased and checked — or None for none."""
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text:
        return None
    if not _NACHA_RETURN_CODE.match(text):
        raise PaymentRuleError(
            f"{value!r} is not a bank return code. A Nacha return code is the letter R and "
            "two characters (R01, R10). Nothing was reversed.",
            br_ref="BR-PAY-013",
        )
    return text


def _returned_on(value: Any) -> datetime:
    """The moment the bank returned it. An INPUT, never a clock (BR-TEN-043).

    BR-PAY-021 hangs NSF off the CLEARING side, and the returned date is what
    the bank's advice states. Reading a clock here would let the moment a
    webhook happened to be processed decide which accounting period a reversal
    lands in — and gate G6 greps every money path for exactly that.
    """
    if not isinstance(value, datetime):
        raise PaymentRuleError(
            "a reversal needs the date the bank returned the item, and it is the bank's "
            "(BR-PAY-021 — NSF hangs off the CLEARING side; BR-TEN-043 — the caller names the "
            "moment). A value taken from the clock would let the minute a webhook was processed "
            "decide which month the reversal posts into.",
            br_ref="BR-PAY-021",
        )
    return value


def _resolve(module: str, attribute: str, kind: str) -> Any:
    """A neighbour's published callable, or None while it has not published one."""
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    return getattr(target, attribute, None)


def _refuse_if_batch_locked(payment: models.Payment) -> None:
    """**THE LOCK HOLDS AND THE BOUNCE IS NEW ROWS** — PO 2026-08-12, OQ-134.

    Verbatim: *"if this happen Utility will charge Cheque bounce charges and add
    new entry - this will be mnaul process by utility user in payments or in
    finance we have to decide the place - you decide for me"*.

    Worked on the prototype fixture: **DEP-260805-CHK**, 8 cheques, recorded
    **$2,840.00**, reconciled and locked; three weeks later cheque #4021
    (**$100.00**) is returned. The batch total stays **$2,840.00** — the bank
    statement it was agreed against did not change, and rewriting it to $2,740.00
    would edit a signed-off money record in place, which hard rule 4 forbids.
    The bounce is the ordinary reversing row plus the utility's bounce fee, both
    NEW rows, exactly as a bounce on an unbatched cheque is.

    **THE PLACEMENT WAS DELEGATED TO ME AND I DECIDED IT: HERE, IN PAYMENTS, ON
    THE PAYMENT.** A returned cheque is an event on a payment; this module
    already reverses one and hands the ledger its mirror; and the bounce fee is a
    charge against the customer's account. The deposit batch owns none of those
    facts — it owns a bank tie-out that is still true. Finance's reconciliation
    screen shows the consequence; payments records the cause. Written down as a
    decision so the next reader finds a reason rather than a habit.

    **THE UNRESOLVABLE CASE STILL FAILS CLOSED, and that is not the same
    question.** A payment naming a batch this process cannot READ has an unknown
    lock state. The ruling settles what to do when a batch IS locked; it does not
    make it safe to proceed while blind, so that case still refuses — now with a
    plain reason rather than an open-question id.
    """
    batch_id = getattr(payment, "deposit_batch_id", None)
    if batch_id is None:
        return  # never banked in a batch: nothing to check
    batch_model = _resolve("payments", "DepositBatch", "bankrec_models")
    if batch_model is None:
        raise PaymentRuleError(
            f"payment {payment.payment_no or payment.pk} names deposit batch {batch_id} and this "
            "process cannot read deposit batches at all, so it cannot tell what it is about to "
            "touch. Refused rather than assumed safe.",
            br_ref="BR-PAY-004",
        )
    # A locked batch is FINE (PO 2026-08-12): its total does not move, so there
    # is nothing here to refuse. The read stays because a batch id that resolves
    # to no row is a broken reference, not a locked batch.
    if not batch_model.objects.filter(tenant_id=payment.tenant_id, pk=batch_id).exists():
        raise PaymentRuleError(
            f"payment {payment.payment_no or payment.pk} names deposit batch {batch_id}, which "
            "does not exist for this tenant. A payment pointing at a missing batch is a broken "
            "reference, and reversing it would leave the books referring to it too.",
            br_ref="BR-PAY-004",
        )


def _by_advice(tenant_id: Any, key: str | None, original_id: Any) -> models.Payment | None:
    """GUARD 1 — the same bank ADVICE arriving twice. Keyed on `webhook_key`.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THIS GUARD ANSWERS A QUESTION GUARD 2 CANNOT, AND THE RED PROOF     ║
    ║  IS WHAT FOUND IT (DEF-058's lesson, live).                          ║
    ╚══════════════════════════════════════════════════════════════════════╝
    This function was first written to return "the reversal under this key,
    whatever it reverses", and both idempotency tests stayed GREEN with it
    switched off — because guard 2's lookup catches the same-payment case on the
    same code path and one guard was silently standing in for the other. That is
    exactly the shape DEF-058 records, so the guard was rewritten until its
    absence is observable, rather than kept because it felt like defence in
    depth.

    What it actually protects, and what guard 2 structurally cannot see: **the
    same advice reference arriving for a DIFFERENT payment.** A returns feed that
    reuses `RET-99012` for two cheques is a broken feed, and the row it finds is
    another payment's reversal:

      * WITHOUT this check, the insert reaches `uq_payments_webhook_key`, the
        `IntegrityError` handler looks the key up, finds the OTHER payment's
        reversal and reports "already reversed" — so a REAL bounce of a
        different cheque is silently swallowed and that customer's bills never
        re-open.
      * WITH it, the collision is REFUSED by name and a human fixes the feed.

    So a key that names a different payment is an error, never a replay.
    """
    if key is None:
        return None
    by_key = models.Payment.objects.filter(tenant_id=tenant_id, webhook_key=key).first()
    if by_key is None:
        return None
    if by_key.reverses_payment_id != original_id:
        raise PaymentRuleError(
            f"idempotency key {key!r} has already been used, and it was used for a DIFFERENT "
            f"payment ({by_key.payment_no or by_key.pk}). This bounce is NOT recorded and is "
            "NOT treated as a duplicate: two different returned items sharing one reference is "
            "a broken feed, and swallowing the second as a replay would leave a real bounce "
            "unrecorded and that customer's bills settled with money the bank took back "
            "(BR-PAY-003 / hard rule 6).",
            br_ref="BR-PAY-028",
        )
    return by_key


def _by_payment(tenant_id: Any, original_id: Any) -> models.Payment | None:
    """GUARD 2 — the same PAYMENT bounced in FULL under a DIFFERENT advice id.

    Two clerks, or a webhook and a manual S33 mark: the keys differ, so guard 1
    cannot see it. `uq_payments_full_reverses` is the database half and this is
    the cheap pre-insert half.

    ⚠ **NARROWED TO FULL REVERSALS ON 2026-09-03 (CR-059 CS-33), AND THE
    NARROWING IS THE WHOLE DIFFICULTY OF THAT CHANGE.** This read used to return
    ANY reversal of the payment and the caller treated it as a replay — which was
    exact while a payment could be reversed once. **With partials it would be a
    silent data-loss bug:** a clerk reversing 100.00 of a 292.87 payment and then
    a further 92.87 would have the second request answered with the FIRST
    reversal and `created=False` — a success message, and 92.87 that never came
    back off the customer's account.

    So a REPLAY is now the idempotency KEY's job (guard 1 plus
    `uq_payments_webhook_key`, which `reversal_api` has required since
    2026-09-01 for exactly this day), and this guard answers only the question it
    can still answer soundly: **has this payment already been reversed in
    full?** A full reversal is the whole of what stood, so a second one is
    always a duplicate and never a lawful second correction.
    """
    return models.Payment.objects.filter(
        tenant_id=tenant_id, reverses_payment_id=original_id, is_partial_reversal=False
    ).first()


def _existing(tenant_id: Any, key: str | None, original_id: Any) -> models.Payment | None:
    """Both guards, in order, each able to fail on its own (see each above)."""
    return _by_advice(tenant_id, key, original_id) or _by_payment(tenant_id, original_id)


def _replayed(reversal: models.Payment, *, credit_position: Decimal) -> ReversedPayment:
    """The no-op answer for a bounce this tenant has already recorded.

    CR-059 CS-33: it carries the PARTIAL facts too, read back off the rows that
    exist. A retried partial that reported `still_stands` as zero would tell a
    clerk the payment was finished when 192.87 of it was not.
    """
    rows = tuple(reversal.allocations.all().order_by("created_at", "id"))
    reversed_total = -sum((row.amount for row in rows), ZERO)
    return ReversedPayment(
        reversal_id=str(reversal.pk),
        reversal_no=reversal.payment_no,
        original_payment_id=str(reversal.reverses_payment_id),
        created=False,
        amount=reversal.amount,
        currency=reversal.currency,
        reason=reversal.reversal_reason or "",
        allocations_reversed=reversed_total,
        credit_reversed=-reversal.amount - reversed_total,
        credit_position_after=credit_position,
        # CR-059 CS-33 — read back off the rows that exist, never assumed. A
        # retried partial that reported `still_stands` as zero would tell a
        # clerk the payment was finished when part of it was not.
        is_partial=bool(getattr(reversal, "is_partial_reversal", False)),
        still_stands=(
            reversal.reverses_payment.amount
            - reversed_so_far(reversal.tenant_id, reversal.reverses_payment_id)
        ),
        # ⚠ `LADDER_PAUSED` RODE THIS PATH TOO UNTIL 2026-09-01 (CR-059 CS-5)
        # and it is gone rather than reworded, for the reason the row's own
        # comment gives. A replay writes NOTHING, so it does not know — and must
        # not claim — where the ladder stands: the FIRST bounce may have
        # restarted it, and a replay asserting "paused" would be exactly the
        # false guarantee this change was raised to remove. What the replay does
        # know is that it changed nothing, and the row below says so.
        problems=REVERSE_UNAVAILABLE
        + (
            {
                "code": "duplicate_bounce_ignored",
                "br_ref": "BR-PAY-028",
                "detail": f"this payment was already reversed by "
                f"{reversal.payment_no or reversal.pk}. Nothing was written: one reversing row, "
                "one set of reversing allocations, one mirror entry — the debt is not doubled. "
                "The collection ladder is untouched by this replay for the same reason and "
                "stands wherever the FIRST bounce left it (PO 2026-08-12, OQ-133).",
            },
        ),
    )


@permissions.require_role(permissions.SYSTEM_ADMIN, br_ref="BR-PAY-1070")
def reverse_payment(
    actor: Any,
    *,
    payment_id: Any,
    returned_on: datetime,
    reason: str = models.REVERSAL_REASON_NSF,
    memo: str | None = None,
    bank_fee: Decimal | None = None,
    resume_collections: bool = False,
    approval: str | None = None,
    amount: Decimal | None = None,
    targets: tuple[Any, ...] = (),
    idempotency_source: str = idempotency.SOURCE_ENTRY,
    idempotency_reference: Any = None,
    return_code: str | None = None,
    charge_nsf_fee: bool = True,
    nsf_fee_waive_reason: str | None = None,
    bank_memo: str | None = None,
) -> ReversedPayment:
    """A payment came back (BR-PAY-013 / BR-PAY-011) — all of it, or none of it.

    ⚠ **THE ONE FEE-AWARE REVERSAL — EVERY DOOR CALLS THIS (`DEF-PAY-10698`,
    PO 2026-10-30).** The Payments list, an account's Payments tab and a bank
    statement's returned line all reverse a bounce through this function, so
    the NSF penalty is charged once and in one place:

      * `reason="nsf"` with `charge_nsf_fee=True` (the default) charges the NSF
        code the account's PLAN lists — the walk account → unit → plan → charge
        code is BILLING's (`apps/billing/nsf_fee.py`, BR-BIL-007), never an
        amount typed here. Cheque 4102 $76.40 on a plan whose NSF is $30.00 →
        a $30.00 fee bill → the account owes **$106.40**.
      * `charge_nsf_fee=False` is the clerk UNTICKING it, and needs
        `nsf_fee_waive_reason` (PO: *"may untick it with a reason"*) — refused
        without one; recorded on the audit row; nothing charged.
      * Any other reason charges nothing and ignores both arguments.
      * No NSF code on the plan → the reversal STILL succeeds and the result
        names `nsf_fee_not_set_on_plan`; never a guessed $0.00.
      * A replay (same idempotency key, or the payment already reversed)
        writes nothing — the fee is never charged twice.

    `bank_memo` (LBX-04, PO 2026-10-30, ≤ 60 characters) is the bank's own
    words — *"NSF"*, *"ACCOUNT CLOSED"* — saved on the REVERSING row's `memo`
    (the original is never edited, hard rule 4) and on the audit row. When
    given it takes the place of the older free-text `memo`.

    `return_code` (`CR-174-BRC10`) is the bank's own Nacha code when the return
    arrived as an advice that carried one (`R01`). It is stored on the
    REVERSING row beside `reason` and never instead of it — `reason` decides
    what the bounce does, the code records what the bank said. `None` for every
    staff reversal and every advice without a code.

    One service function = one transaction boundary (B1). The reversing payment
    row, its reversing allocations, the ledger mirror and the audit row all
    commit together or none of them does. **A reversal that cannot reach the
    books does not happen**: a bounce recorded with the money still sitting in
    the trial balance is the state nothing can repair, because both rows are
    immutable the instant they commit.

    `returned_on` is the bank's date and this function reads no clock
    (BR-PAY-021 / BR-TEN-043). It is used for BOTH the reversing row's dates and
    the ledger entry date: the reversal is a fact of the day the bank returned
    the item, and booking it on the original payment's day would silently amend
    a month that may already be closed.

    `bank_fee`, when given, is the utility's OWN charge from its bank — posted
    DR 6800 bank fees / CR cash as a SEPARATE entry. It is never the customer's
    NSF fee (see the module docstring) and it never touches the customer's
    balance.

    `resume_collections=True` **RESTARTS THE LADDER AT ITS FIRST RUNG** by
    calling `ladder.restart_after_bounce` inside this transaction — PO
    2026-08-12, OQ-133 CLOSED, verbatim: *"Restart from the beginning"*. The
    result then carries `collection_ladder_restarted`; the default carries
    `collection_ladder_paused`; and if this deployment publishes no
    `restart_after_bounce`, it carries `collection_ladder_not_restarted` and the
    bounce is still recorded — an absence is reported, never assumed away.

    ⚠ **THIS PARAGRAPH DESCRIBED A FLAG NOTHING READ UNTIL 2026-09-01 (CR-059
    CS-5).** The argument was declared, documented here in full, and loaded by
    no statement in the body, so a caller passing `True` silently got the
    default and `ladder.restart_after_bounce` had no caller at all. It is
    recorded rather than quietly fixed because it is hard-won law 1 — *a comment
    claiming a guarantee is not the guarantee* — and because the claim is now
    pinned by a test that fails when the body stops reading the argument.

    **THE CONSUMER-PROTECTION HAZARD THIS ANSWER REMOVES** is why the question
    was raised rather than settled here. Resuming the ladder BY AGE means an
    account can be 58 days overdue the instant its cheque comes back, so the
    customer's first contact after the bounce would be a certified 48-hour
    disconnection notice — for a bill they believed they had paid, through no
    fault they knew about. Restarting from the beginning gives them the whole
    sequence again: first notice, then the rest, in order.

    Worked, on the PO's own case: a **$1,842.10** bill due **6 Jul** is paid by
    cheque posted **5 Jul**, so chasing stops; the cheque returns three weeks
    later. The account re-enters the ladder at rung 1, not at whatever rung 21
    days of age would have reached.

    The default is still `False` — a bounce PAUSES and a human resumes — because
    restarting a collection sequence is an action with consequences for a real
    person, and this ruling settles WHERE it restarts, not that it should happen
    without anybody asking.

    ⚠ **REVERSING A PAYMENT IS ADMIN-ONLY, AND THE GATE IS HERE RATHER THAN ON
    THE ROUTE (BR-PAY-1070, CR-059 CS-5, 2026-09-01).** CS-5's one new rule,
    verbatim: *"reversing a payment is Admin-only, matching the refund gate; the
    service carries no role gate today"*. `@require_role` on the SERVICE is what
    `approve_refund`, `void_refund` and `approve_write_off` already do, and the
    reason is BR-SHL-025: **server-side enforcement is THE enforcement**, so a
    job, a shell or a second endpoint that forgot to gate is refused all the
    same. `reversal_api.payment_reverse` mirrors it with `SystemAdminOnly`
    rather than widening it — a Billing Clerk must not be promised a reach this
    function denies and then meet a 403 from a layer they cannot see.

    **What it costs, stated rather than discovered:** a Billing Clerk records
    the $292.87 cheque and cannot record its return. That is the rule as ruled,
    and it is the same asymmetry `BR-PAY-014` already imposes on money going
    out. **Every existing caller was a test passing a clerk**, and all of them
    moved to an Admin in the same commit; nothing else in this repo called this
    function.

    ⚠ **AND IT NAMES A COLLISION FOR CS-1, WHICH IS REPORTED RATHER THAN
    DECIDED HERE.** A gateway returns feed has no user and therefore no role
    (`_by_advice` above is written for exactly that caller, and
    `idempotency_source` already reserves `webhook|…`). Under this gate such a
    feed is refused, because `getattr(None, "role", None)` is not
    `system_admin`. That is CORRECT today — nothing calls this but a person —
    and it is a decision CS-1 must make when the rails land, so it is written
    down here instead of pre-empted with a service account nobody has ruled on.

    ════════════════════════════════════════════════════════════════════════
    PART OF A PAYMENT MAY COME BACK — CR-059 CS-33, 2026-09-03
    ════════════════════════════════════════════════════════════════════════
    **`amount=None` IS THE WHOLE OF WHAT STILL STANDS AND IS EXACTLY WHAT EVERY
    CALLER BEFORE TODAY MEANT.** On a payment nothing has been reversed against,
    that is the whole payment; on one already partly reversed, it is the
    remainder — so a bounce finishes a payment off without the caller doing the
    subtraction, and no existing call site changes behaviour.

    `amount=X` takes back part of it. CS-33's case: *"a partial chargeback, or a
    cheque where the words and the figures disagree and the bank honours the
    lower"*. Before this the office had to reverse the whole thing and record a
    second payment for the part that stood — **so the customer's history showed
    a payment that bounced when it did not, and if it was a cheque an NSF count
    and a cash-only flag could follow from it.**

    **THE TWO NEW RULES, AND WHERE EACH LIVES:**

      * `BR-PAY-884` — the SUM of every reversal against one payment may never
        exceed it. Three places, deliberately: `_reversible_amount` refuses it
        with a sentence a clerk can read, `_lock_original` serialises two
        clerks racing so the sum is TRUE, and `payments/0019`'s
        `trg_payment_reversal_sum` re-sums in the database on INSERT. A figure
        that is wrong here is wrong in the trial balance forever, which is why
        it is checked twice and locked once.
      * `BR-PAY-885` — a partial reversal unwinds allocations **newest bill
        first**, unless the clerk names the bills in `targets`. Newest-first is
        the rule's own wording and it is the kind answer: the OLDEST debt is the
        one nearest disconnection, so leaving it settled and re-opening the
        newest is what keeps a customer out of the collection ladder over money
        the bank only partly took.

    ⚠ **THE INDEX THAT USED TO MAKE A LOST RACE AND A REPLAY THE SAME FACT IS
    GONE, AND THE GUARANTEE IS NOT.** `uq_payments_reverses` was narrowed to
    `uq_payments_full_reverses` (full reversals only), so what stands between a
    retried request and a doubled debt is now the REQUIRED `idempotency_key` and
    `uq_payments_webhook_key` underneath it — which `reversal_api` has demanded
    since 2026-09-01, naming this change in advance as the reason.

    Raises `PaymentRuleError` for everything a human can act on. Returns
    `ReversedPayment(created=False)` for a replay — never an exception.
    """
    tenant_id = _tenant_id()
    reason = _reason(reason)
    returned_on = _returned_on(returned_on)
    # DEF-PAY-10698 / LBX-04 — both refused BEFORE anything is read or written.
    waived_reason = _clean_waive(reason, charge_nsf_fee, nsf_fee_waive_reason)
    bank_memo = _clean_bank_memo(bank_memo)
    if bank_memo is not None:
        memo = bank_memo
    original = _original(tenant_id, payment_id)
    _refuse_if_batch_locked(original)
    # ── BR-PAY-011's other two clauses (CR-059 CS-31, task 35) ──────────────
    # BEFORE the idempotency lookup, so a staff reversal that is outside its
    # window or missing its approval is refused on its own terms rather than
    # answered as somebody else's replay. It is a no-op for a bounce — the
    # reason is the boundary and `reversal_rules` draws it in one place.
    plan = _refuse_unless_staff_reversal_is_lawful(
        original, reason=reason, on=returned_on.date(), approval=approval
    )

    key = (
        idempotency.inbound_payment_key(source=idempotency_source, reference=idempotency_reference)
        if idempotency_reference is not None
        else None
    )

    # Cheap path first: a replay costs two SELECTs and opens no transaction.
    # The two unique indexes below are what make a LOST RACE indistinguishable
    # from a replay — neither writes a second reversing row.
    already = _existing(tenant_id, key, original.pk)
    if already is not None:
        return _replayed(already, credit_position=_credit_position(original.account_id))

    try:
        with transaction.atomic():
            # ⚠ ORDER IS THE RULE HERE (CR-059 CS-33). The lock is taken FIRST,
            # inside the transaction, so that the sum `_reversible_amount` reads
            # a moment later is TRUE against every concurrent reversal of the
            # same payment. A sum read before the lock protects nothing.
            _lock_original(tenant_id, original.pk)
            reversing_amount, is_partial = _reversible_amount(tenant_id, original, amount)
            return _write_reversal(
                actor=actor,
                original=original,
                returned_on=returned_on,
                reason=reason,
                memo=memo,
                bank_fee=bank_fee,
                resume_collections=resume_collections,
                approval=approval,
                plan=plan,
                key=key,
                idempotency_source=idempotency_source,
                reversing_amount=reversing_amount,
                is_partial=is_partial,
                targets=targets,
                return_code=_return_code(return_code),
                charge_nsf_fee=charge_nsf_fee,
                nsf_fee_waived_reason=waived_reason,
                bank_memo=bank_memo,
            )
    except IntegrityError:
        # The race either unique index exists for: another request reversed this
        # same payment between our SELECT and our INSERT. A lost race and a
        # replay are the same fact — one reversal exists, ours is not it.
        winner = _existing(tenant_id, key, original.pk)
        if winner is None:
            raise
        return _replayed(winner, credit_position=_credit_position(original.account_id))


# ══════════════════════════════════════════════════════════════════════════
# CR-175-BRC10 — A BILLING CLERK MARKS AN ACH PAYMENT RETURNED (PO 2026-10-07)
# ══════════════════════════════════════════════════════════════════════════
# HUMAN-REVIEW-PENDING — a 🔒 money path (who may reverse a payment). Row in
# 12-governance/09-human-review-ledger.md, 2026-10-07, CR-175-BRC10.

#: The tenant's payment-method code that IS ACH. The same code US Payments'
#: tender mapping lands `ACHCHECK` / `ACHSAVINGS` on (`CR-174-BRC10`) and the
#: code `reversal_rules.REVERSAL_WINDOW_DAYS` keys BR-PAY-011's 60 days on —
#: one meaning of "ACH" across the product, never a second list.
ACH_TENDER_CODE = "ach"

#: The reasons a BANK return carries. The other two (`data_entry_error`,
#: `customer_dispute`) are our own correction of our own record and stay a
#: System Admin's Reverse — the ruling is about money the bank sent back.
ACH_RETURN_REASONS: tuple[str, ...] = (
    models.REVERSAL_REASON_NSF,
    models.REVERSAL_REASON_BANK_CHARGEBACK,
)

#: Money that ARRIVED. A processing payment is cancelled, not returned
#: (BR-PAY-021), and a cancelled or failed one never reached the bank.
ACH_RETURNABLE_STATUSES: tuple[str, ...] = (models.PAYMENT_CLEARED, models.PAYMENT_POSTED)


@permissions.require_role(
    permissions.SYSTEM_ADMIN, permissions.BILLING_CLERK, br_ref="BR-PAY-1070"
)
def mark_ach_returned(
    actor: Any,
    *,
    payment_id: Any,
    returned_on: datetime,
    reason: str,
    return_code: Any,
    memo: str | None = None,
    idempotency_reference: Any = None,
    bank_memo: str | None = None,
) -> ReversedPayment:
    """The bank sent an ACH payment back, and a billing clerk records it.

    ⚠ **THE ONE CASE `BR-PAY-1070` NO LONGER COVERS, AND NOTHING ELSE.** PO,
    2026-10-07, verbatim: *"(a) Let billing clerks mark an ACH payment returned,
    any day, with a reason and the bank code. The same effect follows: balance
    restored, fee and notice."* All four conditions are checked HERE, on the
    service, because server-side enforcement is THE enforcement (BR-SHL-025):

      * the tender is ACH (`ACH_TENDER_CODE`) — a card, cash or cheque payment
        from another day is refused by name, exactly as before;
      * the actor is a billing clerk or a System Admin (the decorator);
      * the reason is one a bank return carries (`ACH_RETURN_REASONS`);
      * a Nacha return code is given — `_return_code` is CR-174's own check, so
        a clerk's code and US Payments' code are validated by one function.

    **`reverse_payment` KEEPS ITS ADMIN-ONLY GATE.** This function passes it
    through `__wrapped__` — the same door `agent_door.post_return` uses for US
    Payments, for the same reason: the authority is a ruling about this case,
    not a person's role in general. The effect is therefore byte-for-byte the
    existing reversal — the original kept, a negative row carrying the code in
    `return_code`, allocations released, the ledger's mirror, the audit row —
    and the reversing row is what the returned-payments runbook reads.

    ⚠ **A SECOND RETURN OF THE SAME PAYMENT IS REFUSED, NOT REPLAYED.**
    `reverse_payment` answers a second full reversal under a NEW key with the
    first one and `created=False` — right for a feed, wrong for a clerk, whose
    screen would read success for a click that did nothing. The SAME submit
    retried (the same key) is still a replay and writes nothing (hard rule 6).

    **WORKED:** Dana (billing clerk) marks Rosa's $100.00 ACH of 7 Oct returned
    R01 on 10 Oct; Rosa owes $177.89 before and $277.89 after.
    """
    tenant_id = _tenant_id()
    original = _original(tenant_id, payment_id)
    tender = getattr(original.method, "code", None)
    if tender != ACH_TENDER_CODE:
        raise PaymentRuleError(
            f"payment {original.payment_no or original.pk} was not paid by ACH, so it cannot be "
            "marked returned here. Only a System Admin may reverse it.",
            br_ref="BR-PAY-1070",
        )
    if original.status not in ACH_RETURNABLE_STATUSES:
        raise PaymentRuleError(
            f"payment {original.payment_no or original.pk} is {original.status}, so the money "
            "never arrived and cannot come back.",
            br_ref="BR-PAY-021",
        )
    if reason not in ACH_RETURN_REASONS:
        raise PaymentRuleError(
            f"{reason!r} is not a reason a bank return carries. Choose returned by the bank or "
            "chargeback; a correction of our own record is a System Admin's Reverse.",
            br_ref="BR-PAY-1070",
        )
    code = _return_code(return_code)
    if code is None:
        raise PaymentRuleError(
            "a bank return code is required to mark an ACH payment returned (R01, R10). "
            "Nothing was reversed.",
            br_ref="BR-PAY-1070",
        )
    key = (
        idempotency.inbound_payment_key(
            source=idempotency.SOURCE_ENTRY, reference=idempotency_reference
        )
        if idempotency_reference is not None
        else None
    )
    if _by_advice(tenant_id, key, original.pk) is None:
        earlier = (
            models.Payment.objects.filter(tenant_id=tenant_id, reverses_payment_id=original.pk)
            .order_by("created_at")
            .first()
        )
        if earlier is not None:
            raise PaymentRuleError(
                f"payment {original.payment_no or original.pk} was already returned as "
                f"{earlier.payment_no or earlier.pk}. Nothing was reversed again.",
                br_ref="BR-PAY-028",
            )
    return reverse_payment.__wrapped__(  # type: ignore[attr-defined]
        actor,
        payment_id=original.pk,
        returned_on=returned_on,
        reason=reason,
        memo=memo,
        idempotency_reference=idempotency_reference,
        return_code=code,
        # LBX-04 — the bank's own words (PO 2026-10-30), on the reversing row.
        bank_memo=bank_memo,
    )


@permissions.require_role(permissions.SYSTEM_ADMIN, permissions.EXECUTIVE, br_ref="BR-PAY-1070")
def reverse_returned_by_bank(
    actor: Any,
    *,
    payment_id: Any,
    returned_on: datetime,
    charge_nsf_fee: bool = True,
    nsf_fee_waive_reason: str | None = None,
    bank_memo: str | None = None,
) -> ReversedPayment:
    """A BANK STATEMENT says the cheque came back — the one reversal an Executive may make.

    ⚠ **BR-PAY-1070 NARROWED FOR EXACTLY ONE DOOR (`DEF-PAY-10765`).** PO
    2026-10-30, decision log *"Final-walk questions W1–W4 answered"*, verbatim
    *"W1-A -Allow Finance Executive"*: a Finance Executive reconciling the bank
    statement may match a returned line to its payment, and that match reverses
    the cheque. Scope as put to the PO and nothing wider — reason *Returned by
    the bank*, the NSF fee charged unless unticked with a reason, the line's
    own text as the Bank memo, audit-logged. **"Any other reversal path keeps
    its current roles unless ruled."** So `reverse_payment` keeps its
    System-Admin-only gate untouched, and this function passes it through
    `__wrapped__` — the shape `mark_ach_returned` above already uses for the
    Billing Clerk's ACH door.

    **WHAT MAKES IT A DOOR AND NOT A HOLE:** it takes no `reason`, no `amount`,
    no `targets`, no `bank_fee` and no `resume_collections`. The reason is
    pinned to *Returned by the bank* (`nsf`), the whole cheque comes back, and
    the collection ladder pauses as on every bounce. An Executive cannot reach
    a staff correction (*entered in error*, *customer dispute*) or a partial
    reversal through here — a test calls it with `reason=` and is refused.

    The only caller is `reconciliation._reverse_for_returned_line`, whose own
    public door `match_returned_line` carries the same two roles.
    """
    return reverse_payment.__wrapped__(  # type: ignore[attr-defined]
        actor,
        payment_id=payment_id,
        returned_on=returned_on,
        reason=models.REVERSAL_REASON_NSF,
        charge_nsf_fee=charge_nsf_fee,
        nsf_fee_waive_reason=nsf_fee_waive_reason,
        bank_memo=bank_memo,
    )


def _credit_position(account_id: Any) -> Decimal:
    """The account's credit position, signed. Imported late to avoid a cycle."""
    from apps.payments import selectors

    return selectors.account_credit_position(account_id)


def _record_nsf(account_id: Any, *, actor: Any) -> tuple[Any, tuple[dict[str, Any], ...]]:
    """BR-PAY-013's `nsf_count++` and privilege flag — CUSTOMERS' write (DEF-069).

    `accounts` is customers' table and payments may not write another module's
    (B1 / DB-16), so this resolves `apps.customers.services.record_nsf` BY NAME
    at call time — the same shape `services._account` uses for
    `account_queryset`, and the shape G20 checks from both sides.

    **AN UNWIRED SEAM REPORTS; IT NEVER ANSWERS ZERO.** If customers has not
    published the function the bounce is still fully recorded and the result
    carries `nsf_count_not_incremented` — because a count of 0 returned here
    would tell a clerk this customer's first cheque had just bounced when it was
    their third, and the privilege threshold would never be reached.

    A refusal from customers is NOT swallowed and NOT translated into a problem
    code: it propagates, inside the reversal's transaction, so a bounce whose
    count could not be written is not committed half-done. That is DEF-047's
    lesson — a seam that adapts the owner's RESULT but not the owner's REFUSAL
    is a seam that loses money events.
    """
    try:
        customers_services = import_module("apps.customers.services")
    except ImportError:  # pragma: no cover - the app package always imports
        customers_services = None
    fn = getattr(customers_services, "record_nsf", None) if customers_services else None
    if not callable(fn):
        return None, (
            {
                "code": "nsf_count_not_incremented",
                "br_ref": "BR-PAY-013",
                "detail": "BR-PAY-013 increments `accounts.nsf_count` on every bounce and trips "
                "the cash-only / no-autopay flag at the tenant's N. `accounts` is CUSTOMERS' "
                "table (B2 r12 #12) and payments may not write another module's table "
                "(B1 / DB-16), so this path calls `apps.customers.services.record_nsf` by name "
                "— and this deployment does not publish it. The bounce itself is fully "
                "recorded; the COUNT and the FLAG are what is missing, and neither is "
                "guessed. DEF-069 / DEF-070.",
            },
        )
    outcome = fn(account_id, actor=actor)
    return outcome, tuple(getattr(outcome, "problems", ()) or ())


def _release_deposit(
    account_id: Any, *, amount: Decimal, actor: Any
) -> tuple[Any, tuple[dict[str, Any], ...]]:
    """BR-CUS-670 — take a reversed deposit back OUT of the customer register.

    The `_record_nsf` shape, and for the same reason: `accounts` is CUSTOMERS'
    table and payments may not write another module's (B1 / DB-16), so
    `apps.customers.services.record_deposit_movement` is resolved BY NAME at
    call time.

    **AN UNWIRED SEAM REPORTS; IT NEVER ANSWERS ZERO.** If customers publishes
    no writer, the reversal is still fully recorded and the result carries
    `deposit_register_not_released` — because a silent no-op would leave the
    2300 liability reversed and the register standing, which is DEF-177 in the
    opposite direction and reads as a healthy book on every report that foots.

    A refusal from customers PROPAGATES rather than becoming a problem code
    (DEF-047): a bounce whose register move was refused must not commit.
    """
    try:
        customers_services = import_module("apps.customers.services")
    except ImportError:  # pragma: no cover — the app package always imports
        customers_services = None
    fn = (
        getattr(customers_services, "record_deposit_movement", None)
        if customers_services
        else None
    )
    if not callable(fn):
        return None, (
            {
                "code": "deposit_register_not_released",
                "br_ref": "BR-CUS-670 · BR-LED-007 · DEF-177",
                "detail": "the reversing entry has taken this deposit back out of the 2300 "
                "deposit-liability account, and `apps.customers.services."
                "record_deposit_movement` — the writer that takes it out of the customer "
                "register too — is not published on this deployment. The register therefore "
                "still shows money the books no longer hold; the S36 tie-out reports the "
                "difference by name.",
            },
        )
    return fn(account_id, amount, actor=actor, released=True), ()


def _restart_ladder(account_id: Any, *, on_date: date, actor: Any) -> tuple[dict[str, Any], ...]:
    """OQ-133's reset — `ladder.restart_after_bounce`, resolved BY NAME.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THIS CALL DID NOT EXIST UNTIL 2026-09-01 (CR-059 CS-5), AND THE     ║
    ║  TWO DOCSTRINGS THAT SAID IT DID ARE HARD-WON LAW 1 EXACTLY.         ║
    ╚══════════════════════════════════════════════════════════════════════╝
    `reverse_payment` declared `resume_collections`, documented in eleven lines
    what `True` did, and **read it nowhere** — so `ladder.restart_after_bounce`
    had no caller outside its own test, `ladder.py`'s module docstring told
    every reader that *"`reversal.py` calls it"*, and a bounced customer's next
    contact was still whatever rung their AGE selected. The ruling had been on
    file for three weeks. Nothing could see the gap because no gate in this repo
    reads prose, which is why the fix ships with a test that reads the syntax
    tree instead (`tests/test_cr059_cs5_ladder_restart.py`).

    **THE LADDER IS THIS MODULE'S OWN TABLE, NOT A NEIGHBOUR'S.**
    `account_collection_state` is payments' (B2 r12 #7), so nothing here crosses
    a module boundary and B1 / DB-16 is not in play. The resolve-by-name is for
    the OTHER reason this file already uses it for `bankrec_models.DepositBatch`:
    a bounce must not fail because an optional part of its own module is absent,
    and an absence must be REPORTED rather than assumed away.

    **AN UNWIRED SEAM REPORTS; IT NEVER PRETENDS.** No `restart_after_bounce`
    means `collection_ladder_not_restarted` on the result and the bounce
    committing anyway — the shape `_record_nsf` and `_release_deposit` both
    take, and the shape customers' own `record_nsf` takes when it cannot read
    the privilege threshold.

    **A REFUSAL FROM THE LADDER PROPAGATES AND IS NOT CAUGHT (DEF-047).** It
    runs inside `reverse_payment`'s transaction, so a bounce whose collection
    reset was refused does not commit half-done. ⚠ **DO NOT "TIDY" THIS INTO A
    `try: … except: pass`** — CLAUDE.md law 14: on PostgreSQL the failed
    statement has already aborted the whole transaction, so the reversal would
    be lost at COMMIT anyway while the suite stayed green on SQLite, which has
    no aborted-transaction state. If a later lane ever does need to continue
    past a ladder failure, it needs a SAVEPOINT — a nested
    `transaction.atomic()` — the way `receipts._queue_one` does, and that is a
    different decision from this one.
    """
    restart = _resolve("payments", "restart_after_bounce", "ladder")
    if not callable(restart):
        return (LADDER_RESTART_UNAVAILABLE,)
    # `on_date` is the bank's return date, never a clock (BR-PAY-021 /
    # BR-TEN-043) — the same date the reversing row and the ledger entry carry.
    restart(account_id, on_date=on_date, actor=actor)
    return (LADDER_RESTARTED,)


def _write_reversal(
    *,
    actor: Any,
    original: models.Payment,
    returned_on: datetime,
    reason: str,
    memo: str | None,
    bank_fee: Decimal | None,
    resume_collections: bool,
    approval: str | None,
    plan: dict[str, Any],
    key: str | None,
    # CR-132-BRC07 — passed in rather than read from an enclosing scope, which
    # is what a first draft did and what `NameError` caught at once: this helper
    # is a separate function and `reverse_payment`'s locals are not its own.
    idempotency_source: str,
    reversing_amount: Decimal | None = None,
    is_partial: bool = False,
    targets: tuple[Any, ...] = (),
    return_code: str | None = None,
    charge_nsf_fee: bool = True,
    nsf_fee_waived_reason: str | None = None,
    bank_memo: str | None = None,
) -> ReversedPayment:
    """The whole reversal, inside `reverse_payment`'s transaction.

    Split out for readability only — it is NOT a second transaction boundary and
    must never be called from anywhere else.

    `plan` is what `_refuse_unless_staff_reversal_is_lawful` already computed and
    is passed in rather than recomputed, so the figures the audit row carries are
    the ones the refusal was decided on. `approval` is the acknowledgement
    BR-PAY-011 asks for when a bill re-opens or a closed month is touched; it is
    recorded, never interpreted.
    """
    reversal = models.Payment.objects.create(
        tenant_id=original.tenant_id,
        account_id=original.account_id,
        # BR-TEN-035: numbered from the tenant's PMT- series inside this
        # transaction, under the date the money went BACK. A reversing row is a
        # payment record in its own right and appears on S33 as one.
        payment_no=numbering.next_number(numbering.PAYMENT, returned_on.date()),
        type=models.PAYMENT_TYPE_PAYMENT,
        method=original.method,
        # PE-7, verbatim: "reversing payment row −292.87". The sign lives on the
        # AMOUNT, not on the type: `type` stays `payment` because that is what
        # came back, and B2's O-4 residue (do credits/adjustments store a signed
        # amount?) is therefore never consulted — this row's sign is explicit.
        # CR-059 CS-33: the size of THIS reversal, which is the whole of what
        # still stands unless the caller named part of it. `PE-7`'s −292.87 is
        # unchanged, because a first full bounce reverses the whole payment.
        amount=-(original.amount if reversing_amount is None else reversing_amount),
        currency=original.currency,
        status=models.PAYMENT_REVERSED,
        purpose=original.purpose,
        confirmation=original.confirmation,
        memo=memo,
        # CR-059 CS-33 — for the CONSTRAINT, not for a reader. See the model.
        is_partial_reversal=is_partial,
        # BOTH dates are the bank's return date (BR-PAY-021). The reversal
        # entered the system and the money left on the same day — that is what
        # a returned item IS — and neither is read from a clock.
        posted_at=returned_on,
        cleared_at=returned_on,
        reverses_payment=original,
        reversal_reason=reason,
        # CR-174-BRC10 — the bank's code, written HERE or never (hard rule 4;
        # `ck_payments_return_code_on_reversal` allows it on this row only).
        return_code=return_code,
        webhook_key=key,
        # ── CR-132-BRC07 · WHERE THIS MONEY CAME FROM ──────────────────────
        # THE REVERSAL'S OWN ORIGIN, NOT THE ORIGINAL PAYMENT'S, and the
        # difference is the whole reason it is read from the caller. A card
        # payment taken online and bounced by the bank a week later is a
        # `webhook` receipt reversed by a `webhook` return; the same payment
        # reversed by a clerk after a phone call is a `webhook` receipt
        # reversed by an `entry`. Copying `original.origin` would report the
        # second as an online event and hide the human who did it.
        #
        # WRITE-ONCE (hard rule 4) — a reversing row is a payment record in
        # its own right — and OBSERVED, so never derived.
        origin=idempotency_source,
        origin_is_derived=False,
    )

    # ── the reversing allocations (BR-PAY-013, BR-PAY-031) ──────────────────
    # One NEGATIVE row per row the original wrote, hung off the REVERSING
    # payment. The original's rows are append-only and are not touched, so
    # `billing_seam.allocated_so_far` — which sums NET over a bill — sees the
    # bill re-open by exactly what was taken off it.
    #
    # NOTHING WRITES A DUE DATE HERE. The bill re-opens at its own
    # `invoices.due_date`, which no code in this module has ever written, and
    # that is how "the late-fee clock never resets" is implemented (BR-PAY-013).
    reopened: list[dict[str, Any]] = []
    reversed_total = ZERO
    # ── BR-PAY-885 · WHICH BILLS RE-OPEN, AND IN WHAT ORDER (CR-059 CS-33) ──
    # A FULL reversal unwinds every row and the order is irrelevant — which is
    # why this walk was `created_at` ascending and stayed correct for three
    # weeks. A PARTIAL reversal has to choose, and the rule chooses for it:
    # *"unwinds allocations in the reverse of the order they were made, newest
    # bill first, unless the clerk names which bill to re-open."*
    #
    # **NEWEST-FIRST IS THE KIND ANSWER AND THE RULE SAYS SO RATHER THAN THIS
    # FILE INVENTING IT.** The OLDEST debt is the one nearest disconnection, so
    # re-opening the newest keeps a customer off the collection ladder over
    # money the bank only partly took back.
    #
    # `targets` is the clerk's override — the bills to re-open, in their order.
    # A bill this payment never met is refused by name rather than skipped: a
    # silently ignored target is a clerk believing they re-opened something.
    rows = list(original.allocations.all().order_by("created_at", "id"))
    if targets:
        wanted = [str(one) for one in targets]
        by_invoice: dict[str, list[Any]] = {}
        for row in rows:
            by_invoice.setdefault(str(row.invoice_id), []).append(row)
        unknown = [one for one in wanted if one not in by_invoice]
        if unknown:
            raise PaymentRuleError(
                f"payment {original.payment_no or original.pk} never met bill(s) {unknown}, so "
                "reversing against them would re-open money that was never there. Name the "
                "bills this payment actually met, or leave the list empty and the newest is "
                "unwound first (BR-PAY-885).",
                br_ref="BR-PAY-885",
            )
        rows = [row for one in wanted for row in by_invoice[one]]
    elif is_partial:
        rows = list(reversed(rows))

    remaining = -reversal.amount
    for row in rows:
        if remaining <= ZERO:
            break
        # Capped at what is left to take back, so the LAST bill touched by a
        # partial reversal re-opens by part of what it received rather than by
        # all of it. `allocated_so_far` sums NET, so the bill re-opens by
        # exactly this figure and by nothing else.
        share = row.amount if row.amount <= remaining else remaining
        remaining -= share
        mirror = models.Allocation.objects.create(
            tenant_id=original.tenant_id,
            payment=reversal,
            invoice_id=row.invoice_id,
            amount=-share,
        )
        # ⚠ **CR-060 C19 / task T7d — THE CLASS BREAKDOWN REVERSES WITH IT.**
        # A bounced cheque takes back the tax it collected as well as the
        # revenue, and `allocation_classes` is what the collected-remittance
        # basis is read from — so a mirror with no breakdown would leave a
        # utility remitting tax on money that came back. The negated rows are
        # copied from the ORIGINAL's own children rather than recomputed: what
        # the payment met is already a recorded fact and re-deriving it here
        # would be a second implementation that could disagree with the first
        # (the same reason `billing/posting_seam` refuses to re-resolve a GL
        # account it was handed). Original rows are untouched — the table
        # refuses UPDATE and DELETE in every state (payments/0016).
        # ⚠ **A PARTIAL UNWIND OF ONE ROW TAKES ITS CLASSES IN THE SAME
        # PROPORTION (CR-059 CS-33).** Copying the whole breakdown on to a
        # part-sized mirror would take back more tax than money — and the
        # *collected* remittance basis is read from these rows, so a utility
        # would remit on a figure that never existed. When the whole row is
        # unwound the proportion is 1 and the rows are the negated originals,
        # byte for byte, which is what a full reversal has always written.
        children = list(row.classes.all().order_by("line_class"))
        if share == row.amount or not children:
            shares = [(child.line_class, child.amount) for child in children]
        else:
            shares = []
            spread = ZERO
            for index, child in enumerate(children):
                if index == len(children) - 1:
                    # The LAST class takes the remainder, so the parts sum to
                    # `share` exactly and no cent is created or lost by
                    # rounding — `money.finalize`'s own discipline, applied to
                    # a split rather than to a price.
                    part = share - spread
                else:
                    part = (child.amount * share / row.amount).quantize(
                        child.amount, rounding=ROUND_HALF_UP
                    )
                    spread += part
                shares.append((child.line_class, part))
        models.AllocationClass.objects.bulk_create(
            [
                models.AllocationClass(
                    tenant_id=original.tenant_id,
                    allocation=mirror,
                    line_class=line_class,
                    amount=-part,
                )
                for line_class, part in shares
                if part != ZERO
            ]
        )
        reversed_total += share
        reopened.append({"invoice_id": str(row.invoice_id), "amount": share})

    # What the payment had left sitting as account credit. When the customer has
    # since been refunded it, this is exactly how far below zero the credit
    # position goes — the PO's $57.13 (ruling 2026-08-11, "Yes, it's a real
    # debt"). Nothing floors it.
    # CR-059 CS-33: what THIS reversal took back that no bill had. On a full
    # reversal it is `original.amount - reversed_total`, unchanged, because the
    # reversing row is the whole payment.
    credit_reversed = (-reversal.amount) - reversed_total

    # ── DEF-PAY-10698 · THE NSF PENALTY (PO 2026-10-30) ─────────────────────
    # INSIDE this transaction and AFTER the reversing rows, so a fee can never
    # point at a bounce that rolled back. ONLY for `nsf`: a staff correction is
    # not the customer's cheque failing. Billing walks account → unit → plan →
    # the plan's NSF code and raises the fee bill in a SAVEPOINT (law 14), so a
    # fee that cannot be charged is a named outcome and the reversal stands.
    # Before the audit row, so the row states what was charged or waived.
    nsf_fee: dict[str, Any] | None = None
    if reason == models.REVERSAL_REASON_NSF:
        if charge_nsf_fee:
            # DEF-PAY-10740 — keyed on the BOUNCED payment, so two cheques
            # bouncing on one account on one day are two fees (PO 2026-10-30).
            nsf_fee = billing_seam.raise_nsf_fee(
                actor,
                account_id=original.account_id,
                on_date=returned_on.date(),
                payment_id=original.pk,
                issued_at=returned_on,
            )
        else:
            nsf_fee = {"status": "nsf_fee_waived", "code": None, "amount": None}

    # ── hard rule 7, INSIDE the transaction ─────────────────────────────────
    core_audit.money_action(
        actor,
        _audit_action(reason),
        "payment",
        str(original.pk),
        after={
            "reversal_payment_id": str(reversal.pk),
            "reversal_no": reversal.payment_no,
            "account_id": str(original.account_id),
            "amount": str(reversal.amount),
            "currency": reversal.currency,
            "reason": reason,
            # CR-174-BRC10 — what the bank SAID, beside what the bounce DOES.
            "return_code": return_code,
            "returned_on": returned_on.isoformat(),
            "allocations_reversed": str(reversed_total),
            "credit_reversed": str(credit_reversed),
            # CR-059 CS-33 — a reader of the trail must be able to tell a
            # partial from a bounce without adding up other rows, and must be
            # able to see what the payment still stood for at the moment of it.
            "is_partial_reversal": is_partial,
            "reversed_amount": str(-reversal.amount),
            "original_amount": str(original.amount),
            "still_stands_after": str(
                original.amount - reversed_so_far(original.tenant_id, original.pk)
            ),
            "reopened": [{**row, "amount": str(row["amount"])} for row in reopened],
            "bank_fee": None if bank_fee is None else str(bank_fee),
            # The clerk's collections choice, recorded with the rest of this
            # bounce's INPUTS (CR-059 CS-5). The reset's own who/when is the
            # ladder's `collection.restarted` row, written by
            # `restart_after_bounce` inside this same transaction — two rows
            # because they are two facts about two entities, a payment and an
            # account, and hard rule 7 wants both.
            "resume_collections": resume_collections,
            # BR-PAY-011's approval clause (CR-059 CS-31). The acknowledgement a
            # person gave and the triggers that asked for it, on the row hard
            # rule 7 already writes for every money action — there is no second
            # place to look, and no durable queue that could disagree with this.
            "approval": approval,
            "approval_required": plan["approval"]["required"],
            "approval_reasons": list(plan["approval"]["reasons"]),
            # The window this reversal was judged against, recorded whether or
            # not it constrained anything: *"the ACH was 12 days old"* is the
            # fact somebody re-reading a correction in a year actually needs.
            "window_days_elapsed": plan["window"]["days_elapsed"],
            "window_limit_days": plan["window"]["limit_days"],
            "window_tender": plan["window"]["tender"],
            "idempotency_key": key,
            "memo": memo,
            # LBX-04 (PO 2026-10-30) — the bank's own words, beside the reason.
            "bank_memo": bank_memo,
            # DEF-PAY-10698 — what the NSF penalty did on this bounce: charged
            # (code, amount, the fee bill's number), waived (with the clerk's
            # reason), or why none was charged. Absent for a staff reason.
            "nsf_fee": None
            if nsf_fee is None
            else {
                "status": nsf_fee.get("status"),
                "code": nsf_fee.get("code"),
                "amount": None if nsf_fee.get("amount") is None else str(nsf_fee["amount"]),
                "currency": nsf_fee.get("currency"),
                "invoice_no": nsf_fee.get("invoice_no"),
            },
            "nsf_fee_waived_reason": nsf_fee_waived_reason,
            "job": None if actor is not None else "payments.reverse",
        },
    )

    # ── the ledger MIRROR (rule 5, BR-LED-003) ──────────────────────────────
    # The seam hands the ORIGINAL entry to `posting.reverse_entry`, which copies
    # every leg with the sides swapped. That is what unwinds the correct step
    # after the PO's OQ-143 ruling (the receipt debited UNDEPOSITED funds, so
    # the mirror credits undeposited funds and bank cash is untouched), and it is
    # what puts the customer-credit account into DEBIT when the credit has
    # already been refunded — a negative credit, which is a real debt.
    # ⚠ **THE POSTING FORKS ON WHETHER THIS IS PART OF THE PAYMENT, AND THE
    # FORK IS THE MOST DANGEROUS LINE IN CS-33.**
    #
    # A FULL reversal keeps the ledger's own MIRROR, byte for byte: `reverse_
    # entry` copies the original entry with the sides swapped, so it unwinds the
    # right step (undeposited funds, never bank cash), drives customer credit
    # into debit where the credit has already been refunded, and links the two
    # halves so S56 renders both forever. None of that changes.
    #
    # A PARTIAL reversal **cannot use it**, and not for convenience:
    #   * `reverse_entry` reverses the WHOLE entry — a 100.00 reversal of a
    #     292.87 payment would take all 292.87 out of the books while 192.87 of
    #     the money is still in the utility's hands;
    #   * the ledger's `uq_journal_entries_reversal` REFUSES a second mirror of
    #     one entry, so two partials of one payment are structurally unmirrorable.
    #
    # So `ledger_seam.post_partial_reversal` composes the receipt's own legs
    # inverted for the part that came back, from the rows THIS reversal just
    # wrote — never re-derived — and refuses the request if they do not foot.
    # Its docstring carries the full argument and the question it leaves open
    # for the ledger lane.
    if is_partial:
        posting = ledger_seam.post_partial_reversal(
            original=original,
            reversal=reversal,
            allocations_reversed=reversed_total,
            credit_reversed=credit_reversed,
            entry_date=returned_on.date(),
            posted_at=returned_on,
            actor=actor,
            clearing_account_id=ledger_seam.tender_clearing_account_id(original),
        )
    else:
        posting = ledger_seam.reverse_payment_entry(
            payment=original,
            entry_date=returned_on.date(),
            posted_at=returned_on,
            event=ledger_seam.EVENT_NSF_REVERSED,
            memo=f"{reason} reversal of payment {original.payment_no or original.pk}",
            actor=actor,
        )

    fee_posting = None
    if bank_fee is not None:
        fee_posting = ledger_seam.post_bank_fee(
            payment=original,
            amount=bank_fee,
            entry_date=returned_on.date(),
            posted_at=returned_on,
            actor=actor,
        )

    # ── BR-PAY-013's COUNTING HALF (DEF-069 + DEF-070) ──────────────────────
    # INSIDE this transaction, and after the reversing rows, for the reason the
    # posting handoff is: the count is a fact about a bounce that EXISTS. A
    # count committed for a reversal that then broke would tell a clerk about a
    # returned cheque that never came back.
    #
    # ⚠ **ONLY WHEN THE REASON IS NSF.** BR-PAY-013 is the bounce rule; a
    # staff-initiated reversal (a duplicate, an error, a wrong account) is not a
    # customer's cheque coming back and must not count against them or move
    # them onto cash-only. The rule's own name is the boundary.
    nsf_outcome = None
    nsf_problems: tuple[dict[str, Any], ...] = ()
    notice_problems: tuple[dict[str, Any], ...] = ()
    if reason == models.REVERSAL_REASON_NSF:
        nsf_outcome, nsf_problems = _record_nsf(original.account_id, actor=actor)
        # ── THE CUSTOMER'S LETTER (CR-048 B3, 2026-08-29) ───────────────────
        # US-PAY-009 TC-4's queue half, closing `no_nsf_notice_queued`. Fired as
        # the SET-12 event `payment_failed`, so a utility that has switched
        # *Payment failed* off on Settings → Notifications gets no letter and the
        # result says which switch decided it.
        #
        # ⚠ **THE REASON IS THE TRIGGER, and it is the same boundary the count
        # above draws for the same reason.** A staff-initiated reversal — a
        # duplicate, a data-entry error, a wrong account — is OUR correction and
        # not the customer's payment failing; telling them it did would be a
        # letter about a fault they do not have. No new flag was added for this.
        #
        # INSIDE this transaction, and AFTER the reversing rows and the posting,
        # so a queued letter can never point at a bounce that rolled back.
        # `receipts` returns outcome rows and never raises through the money
        # path — the same law the receipt is built on, and it is why a broken
        # notification cannot cost a utility the record of returned money.
        from apps.payments import receipts  # local: keeps the seam one-way

        # DEF-PAY-10744 (audit L2-04) — the fee and the Bank memo travel to the
        # letter, so it names what the bounce cost and what the bank said.
        notice_problems = receipts.queue_failed_payment_notice(
            reversal=reversal,
            original=original,
            actor=actor,
            nsf_fee=nsf_fee,
            bank_memo=bank_memo,
        )

    # ── BR-CUS-670 · A REVERSED DEPOSIT LEAVES THE REGISTER TOO (DEF-177) ────
    # The mirror entry above has already taken the money back out of the 2300
    # deposit-liability account. A register that did NOT fall with it would
    # re-open the drift this rule was written to close — one bounced cheque at
    # a time, on a book that foots perfectly, which is the shape nothing else
    # can see (BR-LED-007's tie-out is the only check that could).
    #
    # ⚠ **EVERY REASON, NOT ONLY NSF — and that is the opposite of the count
    # above.** BR-PAY-013's count is a judgement about the CUSTOMER and belongs
    # to a bounce alone; this is a statement about WHERE THE MONEY IS. A
    # duplicate, an error or a wrong-account reversal moves the money back just
    # as an NSF does, and a register that only fell on NSF would be wrong for
    # every other reason a deposit is reversed.
    deposit_problems: tuple[dict[str, Any], ...] = ()
    if original.purpose == models.PURPOSE_DEPOSIT:
        _, deposit_problems = _release_deposit(
            original.account_id, amount=original.amount, actor=actor
        )

    # ── COLLECTIONS: OQ-133's RESET, AND ONLY BECAUSE THE CALLER ASKED ──────
    # PO 2026-08-12, verbatim *"Restart from the beginning"*. The default is
    # still a PAUSE that a person lifts — the ruling settles WHERE the ladder
    # re-enters, not that it should re-enter with nobody asking — so the flag is
    # the trigger and this is the statement of what happened either way.
    #
    # INSIDE this transaction and LAST, for the reason the count and the letter
    # are: a collection state that had been reset for a bounce which then rolled
    # back would put a customer back on rung 1 for money that never came back.
    #
    # ⚠ **NOT GATED ON THE REASON, and that is deliberate.** BR-PAY-013's count
    # is a judgement about the CUSTOMER and belongs to a bounce alone; this is a
    # consequence of the BILL RE-OPENING, which every reversal reason causes —
    # the same argument the deposit release above makes. It changes nothing
    # today: `SUPPORTED_REASONS` is `(nsf,)`, so every reversal that reaches
    # here IS a bounce. When US-PAY-010 opens the other three, the caller's
    # explicit choice stays the trigger and no new flag is needed.
    ladder_problems: tuple[dict[str, Any], ...] = (LADDER_PAUSED,)
    if resume_collections:
        ladder_problems = _restart_ladder(
            original.account_id, on_date=returned_on.date(), actor=actor
        )

    return ReversedPayment(
        reversal_id=str(reversal.pk),
        reversal_no=reversal.payment_no,
        original_payment_id=str(original.pk),
        created=True,
        amount=reversal.amount,
        currency=reversal.currency,
        reason=reason,
        allocations_reversed=reversed_total,
        reopened=tuple(reopened),
        credit_reversed=credit_reversed,
        credit_position_after=_credit_position(original.account_id),
        journal_entry_id=posting.entry_id,
        posting_key=posting.posting_key,
        bank_fee=bank_fee,
        bank_fee_entry_id=None if fee_posting is None else fee_posting.entry_id,
        nsf_count=getattr(nsf_outcome, "nsf_count", None),
        cash_only_no_autopay=getattr(nsf_outcome, "cash_only_no_autopay", None),
        privilege_flag_tripped=bool(getattr(nsf_outcome, "flag_tripped_now", False)),
        is_partial=is_partial,
        still_stands=original.amount - reversed_so_far(original.tenant_id, original.pk),
        nsf_fee_status=None if nsf_fee is None else nsf_fee.get("status"),
        nsf_fee_code=None if nsf_fee is None else nsf_fee.get("code"),
        nsf_fee_amount=None if nsf_fee is None else nsf_fee.get("amount"),
        nsf_fee_invoice_id=None if nsf_fee is None else nsf_fee.get("invoice_id"),
        nsf_fee_invoice_no=None if nsf_fee is None else nsf_fee.get("invoice_no"),
        nsf_fee_waived_reason=nsf_fee_waived_reason,
        bank_memo=bank_memo,
        problems=REVERSE_UNAVAILABLE
        + ladder_problems
        + nsf_problems
        + notice_problems
        + deposit_problems
        + (() if nsf_fee is None else (_nsf_fee_problem(nsf_fee),)),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-009@f4d2b18 (sha1[:7] of the sources this slice was authored from, concatenated in order: 04-docs/02-decisions/02-database-design-brief.md — §2 payments DDL + Addenda r12/r14 — · 04-docs/05-modules/08-payments/06-epics/EP-PAY-03-exceptions.md · 04-docs/05-modules/08-payments/02-business-rules.md · 04-docs/05-modules/08-payments/07-pre-session-model.md §5 PE-7 · 08-qa/01-e2e/journeys/J12-nsf-life.md · 12-governance/02-decision-log.md 2026-08-11 OQ-132 and OQ-143 closures)
# generated: 2026-08-11 by Eng-Lead (NSF + refunds lane, EP-PAY-03)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S33 Reverse has no endpoint; US-PAY-010's modal is unbuilt) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_pay_009_nsf.py · PROVED RED BEFORE GREEN, each mutated, RUN and quoted verbatim in the lane report before being trusted: (1) the bounce EDITING the original row instead of writing a reversing one · (2) the credit floored at zero instead of reaching −57.13 · (3) the ledger mirrored but the allocations left applied, and the reverse · (4) the reinstated bill given the RETURN date as a new due date instead of keeping 22 Aug · (5) each idempotency guard disabled ALONE, observed on the PATH (DEF-058's lesson) rather than on the outcome
# exceptions: (1) ~~THE CUSTOMER'S NSF FEE IS NOT ADDED~~ — CLOSED 2026-10-30
#         (DEF-PAY-10698): an `nsf` bounce charges the plan's NSF code through
#         billing (`billing_seam.raise_nsf_fee`); the claim that rating
#         published no charge-code read had been false since 2026-08-27
#         (2) `accounts.nsf_count` IS NOT INCREMENTED (customers' table, no
#         seam — DEF-069) and the CASH-ONLY / NO-AUTOPAY PRIVILEGE FLAG HAS NO
#         COLUMN AT ALL (r12 #12 names it; customers built only nsf_count —
#         DEF-070). Both ride every result as codes
#         (3) ⚠ [AMENDED 2026-09-01 · CR-059 CS-5] THE OQ-133 HALF OF THIS
#         ENTRY WAS A DOCUMENTED RULING WITH NO CODE BEHIND IT. `reverse_payment`
#         declared `resume_collections`, described its effect in eleven lines and
#         READ IT NOWHERE, so `ladder.restart_after_bounce` had no caller outside
#         its own test and `ladder.py` told every reader that this file called
#         it. Wired now, in `_restart_ladder` → `_write_reversal`, with the reset
#         reported on every result as `collection_ladder_restarted` /
#         `collection_ladder_not_restarted` and the ruling asserted end to end by
#         `tests/test_cr059_cs5_ladder_restart.py` — which also reads this file's
#         SYNTAX TREE, because a parameter nothing loads and a docstring naming a
#         caller that does not exist are both invisible to every other gate here.
#         OQ-133 (ladder re-entry) and OQ-134 (a bounce inside a RECONCILED
#         batch) were OPEN when this file was authored on 2026-08-11 and both
#         paths refused by name, citing their question ids. Each refusal was
#         correct while its question stood; both were RULED on 2026-08-12 and
#         both are gone. OQ-133: the ladder RESTARTS at rung 1. OQ-134: the
#         deposit-batch LOCK HOLDS and the bounce is new rows — DEP-260805-CHK
#         stays $2,840.00 when cheque #4021's $100.00 comes back, and the
#         utility raises its bounce charge as a new entry. What still refuses is
#         a payment naming a batch this process cannot READ or that does not
#         exist for the tenant: a broken reference is not a lock, and it was
#         never the question that was asked
#         (4) THE ORIGINAL'S STATUS IS NEVER CHANGED. EP-PAY-03 §5 says "status
#         reversed on the pair"; hard rule 4 and the 0002 trigger forbid touching
#         a cleared row, so the REVERSING row carries the status and "has this
#         been reversed?" is answered by the existence of that row. Reported —
#         the epic's phrase needs a documentation fix this lane did not make
#         (5) ⚠ [AMENDED 2026-08-29 · CR-048 B3] THIS READ "NO NOTICE IS QUEUED
#         (BR-NOT-005 / US-PAY-025)". THE LETTER IS QUEUED NOW — one `email` row
#         on the reversing payment's own id, template `email_payment_failed`,
#         fired as the SET-12 event `payment_failed` and therefore stoppable by
#         the utility on Settings → Notifications. What is still absent is the
#         `notice_history` row (no NOTICE_TYPES member for a returned payment),
#         and `accounts.balance` IS STILL NOT UPDATED — both ride every result
#         (6) THE REVERSAL-REASON SET IS THE PROTOTYPE'S FOUR, IN CODE. B2 r14 #2
#         anchors a tenant-extensible lookup in tenancy and it does not exist;
#         the column is plain text so the lookup can take it over
#         (7) ONLY `nsf` HAS A WRITE PATH. The first version of this file accepted
#         all four reasons, which made it a general Reverse — and BR-PAY-011
#         governs a general reverse with WINDOWS (ACH 60d, card 120d), an
#         Admin/Executive APPROVAL path and a CONSEQUENCE MESSAGE, of which none
#         is built. It would have let a clerk reverse an ACH payment on day 200
#         with nobody approving it. Found by gate G10 asking for US-PAY-010's
#         TC-named tests and finding none; the three staff-initiated reasons are
#         now refused by name
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
