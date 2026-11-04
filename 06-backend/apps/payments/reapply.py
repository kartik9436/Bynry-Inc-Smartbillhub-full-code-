# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-11 (task 37) — "Reapply a payment to a different bill".
#           The CR's own words: *"A clerk who applies money to the wrong bill
#           has no correction today except reversing the whole payment and
#           taking it again. The schema was built for this — a reapply is
#           reversing allocation rows plus new ones, and both tables are
#           append-only — and no service writes one."*
# Story:    US-PAY-006 (the allocation WRITE path)   Screens: S33 · S35
# Rules:    BR-PAY-031 (CONFIRMED — *"reapply = reversing allocation rows + new
#           rows"*; the mechanism is stated exactly and had simply never been
#           implemented) · BR-PAY-010 (which bill and which class the money
#           meets; the tenant's own order) · BR-PAY-038 (the four line classes,
#           fees LAST) · CLAUDE.md hard rule 4 (a correction is NEW ROWS) ·
#           rule 5 (only the ledger posting service writes journal lines — and
#           this writes NOTHING AT ALL) · rule 7 (audit) · BR-TEN-043 / gate G6
#           (the caller names the day; nothing here reads a clock)
# Ruling:   No new rule. CS-11's own §New rules reads *"None. BR-PAY-031 is
#           CONFIRMED and states the mechanism exactly."*
# Tests:    06-backend/tests/test_cr059_cs11_reapply.py
# Impacts:  apps/payments/open_bills.open_bill_position (CS-4's list, which the
#           modal reuses and this service validates against) ·
#           apps/payments/allocation_release.py (the same negative-mirror
#           mechanism, driven from the BILL's side instead of the payment's)
# ───────────────────────────────────────────────────────
"""Move a payment from the bill it met to the bill it should have met.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 this writes `allocations` on a money
path and states in terms that it posts no journal line. AI-authored 2026-09-03
under the PO ruling of 2026-08-09 (*"AI will do it; we will review it later as
human"*).

⚠ **CORRECTED 2026-09-30 (gate triage T6) — THE `human_owned.txt` SENTENCE BELOW IS
HISTORY, NOT THE CURRENT STATE.** This path was added to
`10-scripts/gates/human_owned.txt` by PO ruling 2026-09-30 (option A, commit
`dabb8a323`, with 51 others), so `G7` reads its markers now.

⚠ **NO GLOB IN `10-scripts/gates/human_owned.txt` MATCHES THIS FILE**, the same
finding `allocation_release.py` records in its own docstring and for the same
reason: that list names files by exact path and **editing it is a process event
and the PO's call, not a lane's**. REPORTED rather than self-granted.

════════════════════════════════════════════════════════════════════════════
⚠ IT POSTS NOTHING TO THE LEDGER, AND THAT IS THE WHOLE RULE
════════════════════════════════════════════════════════════════════════════
CS-11 says it in as many words and says why it is written down:

    *"⚠ IT MUST POST NOTHING TO THE LEDGER. The cash total has not changed —
    only which bill it met — so a reapply that posted would DOUBLE-COUNT the
    money. Saying so here is what stops the next lane adding a posting call
    because every other write path has one."*

So: **no `ledger_seam` import, no `PostingRequest`, no entry, no
`journal_entry_id` touched.** The money reached the books when it arrived
(DR the tender's holding account / CR receivables) and it is still there. What
changes is which INVOICE the receivable relieved, and `journal_lines` carries
an `account_id` dimension but no invoice dimension at all — so there is
literally nothing in the books that a reapply could make more true.

**Worked, so the double-count is a number rather than a warning.** A customer
pays **292.87** and the clerk meets bill `BL-0141` with it; it should have met
`BL-0155`. Reapplying writes a **−292.87** allocation against `BL-0141` and a
**+292.87** against `BL-0155`. Cash in the books: **292.87**, unchanged.
Receivables in the books: **292.87** relieved, unchanged. Had this path posted
the way `record_payment` does, the books would carry **585.74** of cash the
utility never took and its bank reconciliation would be out by the payment,
every time anybody fixed a typo.

════════════════════════════════════════════════════════════════════════════
WHY IT IS NOT A REVERSAL, AND WHY THAT MATTERS TO A CUSTOMER
════════════════════════════════════════════════════════════════════════════
The only correction available before this was to reverse the whole payment and
record it again. That is a `payments` row with status `reversed` on the
customer's history — **a payment that bounced when it did not** — and if the
tender was a cheque it can carry an NSF count and a cash-only flag behind it
(`reversal.py` draws that line in its own words). A reapply leaves the payment
exactly as it stands: same number, same amount, same dates, same receipt.

════════════════════════════════════════════════════════════════════════════
THE ARITHMETIC IS `allocations`' OWN, AND NOTHING HERE ROUNDS
════════════════════════════════════════════════════════════════════════════
Every figure below is a Σ of stored `NUMERIC(18,6)` amounts. `allocations`
refuses UPDATE and DELETE in every state (`payments/0002`), so *"unapplying"* is
a negative mirror row and `billing_seam.allocated_so_far` — which sums NET over
a bill — sees the bill re-open by exactly what came off it. That is the same
mechanism a bounce uses and the same one `allocation_release.py` uses from the
bill's side; three callers, one shape.

**❄️ NO SIGNED FIGURE MOVES.** This service mints no money: it moves rows that
already exist, by their own stored amounts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction

from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy

from apps.payments import billing_seam, models
from apps.payments.exceptions import PaymentRuleError

ZERO = Decimal("0")

#: EP-PAY-01 §5's shape: `<entity>.<verb>`. Its own code rather than
#: `payment.allocated`, so a screen can filter the trail for corrections without
#: reading a payload — the same reason `reversal._audit_action` has two.
AUDIT_REAPPLIED = "payment.reapplied"

#: What a reapply does NOT do, carried on EVERY result. The first row is the one
#: that matters and it is stated as a positive fact rather than left as a
#: silence, because *every other write path in this module posts* and the next
#: reader's instinct will be that a posting call is missing.
REAPPLY_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "nothing_posted_to_the_ledger",
        "br_ref": "BR-PAY-031",
        "detail": "a reapply posts NO journal entry, and that is the rule rather than an "
        "omission (CR-059 CS-11). The cash total has not changed — only which bill the money "
        "met — and the books carry no invoice dimension, so there is nothing an entry could "
        "make more true. A second entry here would be the payment counted twice.",
    },
    {
        "code": "account_balance_cache_not_updated",
        "br_ref": "BR-CUS-015",
        "detail": "`accounts.balance` is customers' CACHED column and payments may not write "
        "another module's table (B1 / DB-16). The per-bill position is right immediately; the "
        "cached account total follows when customers recomputes it.",
    },
)


@dataclass(frozen=True)
class Reapplied:
    """What one reapply moved — off which bills, on to which."""

    payment_id: str
    payment_no: str | None
    account_id: str
    amount: Decimal
    currency: str
    #: The bills the money came OFF, each with the POSITIVE figure taken back.
    #: The mirror rows themselves are negative.
    released: tuple[dict[str, Any], ...] = ()
    #: The bills it went ON to, each with what it met.
    applied_to: tuple[dict[str, Any], ...] = ()
    released_total: Decimal = ZERO
    applied_total: Decimal = ZERO
    #: What is left sitting as account credit AFTER the move — the part of the
    #: payment no bill absorbed. Signed for the same reason every credit figure
    #: in this module is (PO 2026-08-11, `OQ-132`).
    credit_carried: Decimal = ZERO
    problems: tuple[dict[str, Any], ...] = field(default=REAPPLY_UNAVAILABLE)


def _tenant_id() -> Any:
    """CLAUDE.md rule 1 — nothing touches a tenant table without `app.tenant_id`."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _payment(tenant_id: Any, payment_id: Any) -> models.Payment:
    """The payment being reapplied — this tenant's, and money that ARRIVED."""
    payment = models.Payment.objects.filter(tenant_id=tenant_id, pk=payment_id).first()
    if payment is None:
        raise PaymentRuleError(
            f"payment {payment_id} is not this tenant's. Nothing was reapplied.",
            br_ref="BR-TEN-003",
        )
    if payment.status == models.PAYMENT_PROCESSING:
        raise PaymentRuleError(
            f"payment {payment.payment_no or payment.pk} is still processing — the money has "
            "not arrived, so it has met no bill and there is nothing to move. A processing "
            "payment meets its bills when it clears (BR-PAY-021).",
            br_ref="BR-PAY-021",
        )
    if payment.reverses_payment_id is not None:
        raise PaymentRuleError(
            f"{payment.payment_no or payment.pk} is a REVERSING row. Its allocations are the "
            "mirror of another payment's and moving them would unpick a bounce rather than "
            "correct a mis-application.",
            br_ref="BR-PAY-031",
        )
    if payment.amount <= ZERO:
        raise PaymentRuleError(
            f"{payment.payment_no or payment.pk} carries {payment.amount}. A reapply moves money "
            "that met a bill; a negative row is one half of a correction already made.",
            br_ref="BR-PAY-031",
        )
    return payment


class _ReleasedBill:
    """A bill this payment settles, standing in for the open-bill row it has not got.

    It exists for one reason: a settled bill is absent from
    `billing_seam.open_invoices_for_account`, and the money about to be RELEASED
    is exactly what settled it. Its `balance` is ZERO — the bill really does owe
    nothing right now — and `_validated_targets` adds the released amount back,
    so the headroom is what the bill will owe once the mirror rows are written
    and not a figure this class invented.
    """

    def __init__(self, invoice_id: str, *, numbers: dict[str, str | None]) -> None:
        self.invoice_id = invoice_id
        self.number = numbers.get(invoice_id)
        self.balance = ZERO


def _numbers(invoice_ids: list[str]) -> dict[str, str | None]:
    """`{invoice_id: BL-…}` with STRING keys, through billing's published read.

    B14 rule 31 — *"no database id is ever the visible value of a field"* — so
    every bill this module names on the wire carries its NUMBER beside its id.
    `billing_seam.invoice_numbers` keys on the UUID objects it selected; the
    ids on this path are strings, so the keys are normalised here rather than
    at four call sites.
    """
    if not invoice_ids:
        return {}
    return {str(key): value for key, value in billing_seam.invoice_numbers(invoice_ids).items()}


def _net_by_invoice(payment: models.Payment) -> dict[str, Decimal]:
    """What this payment CURRENTLY has on each bill — NET of every mirror row.

    Netting is the whole point: a payment that has already been reapplied once,
    or partly released by a restatement, still has a true position and it is
    the sum of its rows. Reading only the positive rows would offer a clerk
    money that is not there any more, and the reapply would take it off twice.
    """
    net: dict[str, Decimal] = {}
    for row in payment.allocations.all().order_by("created_at", "id"):
        key = str(row.invoice_id)
        net[key] = net.get(key, ZERO) + row.amount
    return {invoice_id: amount for invoice_id, amount in net.items() if amount != ZERO}


def reapply_plan(*, payment_id: Any) -> dict[str, Any]:
    """What this payment currently meets — the left-hand side of the S35 modal.

    CS-11's screen note: *"the bills this payment met, and where to move it"*.
    The right-hand side is CS-4's open-bill list (`GET /accounts/{id}/open-bills`)
    and is deliberately NOT duplicated here — one list, one source, or the
    picker and the validator could offer different bills.

    A read: it writes nothing and may be taken twice with no consequence.
    """
    tenant_id = _tenant_id()
    payment = _payment(tenant_id, payment_id)
    net = _net_by_invoice(payment)
    numbers = _numbers(list(net))
    applied = sum(net.values(), ZERO)
    return {
        "payment_id": str(payment.pk),
        "payment_no": payment.payment_no,
        "account_id": str(payment.account_id),
        "amount": str(payment.amount),
        "currency": payment.currency,
        "meets": [
            {
                "invoice_id": invoice_id,
                "invoice_number": numbers.get(invoice_id),
                "amount": str(amount),
            }
            for invoice_id, amount in net.items()
        ],
        "applied_total": str(applied),
        # What is already sitting as credit and would still be available to move.
        "credit_carried": str(payment.amount - applied),
        "problems": [dict(problem) for problem in REAPPLY_UNAVAILABLE],
    }


def reapply_payment(
    actor: Any,
    *,
    payment_id: Any,
    targets: tuple[dict[str, Any], ...],
    reason: str,
    on_date: date,
    release: tuple[Any, ...] | None = None,
) -> Reapplied:
    """BR-PAY-031, at last — reversing allocation rows plus new ones, in ONE
    transaction, **posting nothing**.

    `targets` is the clerk's instruction, `({"invoice_id": …, "amount": …}, …)`.
    It is EXPLICIT rather than an allocation order, and that is the difference
    between this and `record_payment`: a reapply exists because the automatic
    order put the money in the wrong place, so re-running the same order would
    put it back where it was. The clerk names the bills.

    `release` is which bills to take the money OFF. `None` — the default and
    what the modal sends — means **every bill this payment currently meets**,
    which is the case CS-11 describes. Naming a subset is how one bill of three
    is corrected while the other two stand.

    `reason` is REQUIRED. Hard rule 7's audit row is the only record of why a
    customer's money was moved from one of their bills to another, and it is
    read months later by somebody who was not there.

    ⚠ **THE SUMS MUST FOOT, AND THE REFUSAL IS THE GUARD** (BR-PAY-031 read with
    hard rule 4): what goes on may not exceed what came off plus what was
    already sitting as credit, or the reapply would invent money. What goes on
    may be LESS — that is the clerk deliberately leaving part of the payment as
    account credit, which is a lawful outcome and the result states it.

    ⚠ **A TARGET MAY NOT EXCEED WHAT ITS BILL OWES.** Over-applying would create
    a bill in credit, which `allocation.py` refuses on the automatic path for the
    same reason: the excess belongs in the account's credit balance, where the
    next bill draws it down (BR-PAY-010), not on a document hard rule 4 freezes.

    ⚠ **EVERY BILL MUST BE THIS PAYMENT'S OWN ACCOUNT'S.** Moving money to
    another account's bill is a cross-account movement with its own reviewed
    writer (CS-8 / CS-32, `apps/payments/transfer.py`) and its own balanced
    entry; doing it here would relieve one account's receivable with another's
    cash and post nothing at all to say so.

    Raises `PaymentRuleError` for everything a human can act on.
    """
    tenant_id = _tenant_id()
    if not (reason or "").strip():
        raise PaymentRuleError(
            "a reapply needs a reason. Moving a customer's money from one of their bills to "
            "another is not self-explanatory later, and the audit row is where the answer "
            "will be.",
            br_ref="BR-PAY-031",
        )
    payment = _payment(tenant_id, payment_id)
    net = _net_by_invoice(payment)
    release_ids = [str(one) for one in release] if release is not None else list(net)
    for invoice_id in release_ids:
        if invoice_id not in net:
            raise PaymentRuleError(
                f"payment {payment.payment_no or payment.pk} has nothing on bill {invoice_id}, "
                "so there is nothing to take off it. A reapply moves money that is actually "
                "applied; the amounts on this screen may have moved since it was opened.",
                br_ref="BR-PAY-031",
            )
    released_total = sum((net[one] for one in release_ids), ZERO)
    # What the clerk has to work with: the money coming off the named bills PLUS
    # whatever the payment was already carrying as account credit.
    already_credit = payment.amount - sum(net.values(), ZERO)
    available = released_total + already_credit

    position = billing_seam.open_invoices_for_account(payment.account_id)
    open_by_id = {str(invoice.invoice_id): invoice for invoice in position.invoices}
    # ⚠ **A BILL THIS PAYMENT CURRENTLY SETTLES IS NOT AN "OPEN BILL", AND
    # LEAVING IT OUT REFUSED THE COMMONEST CORRECTION OF ALL.**
    # `open_invoices_for_account` drops a bill that owes nothing — correctly, and
    # for `allocation.py`'s own reason — but the money this reapply is about to
    # RELEASE is what settled it. So a clerk splitting 292.87 across the bill it
    # already met and one other was told *"BL-0141 is not an open bill of this
    # account"*, which is true of the world before the release and false of the
    # world the reapply creates.
    #
    # Every bill being released is therefore a candidate, with the headroom the
    # release gives it back. `_validated_targets` adds the released amount to
    # `invoice.balance` for the same reason, so a bill that is PARTLY settled is
    # not counted twice.
    for invoice_id in release_ids:
        if invoice_id not in open_by_id:
            open_by_id[invoice_id] = _ReleasedBill(invoice_id, numbers=_numbers([invoice_id]))
    plan = _validated_targets(
        payment=payment,
        targets=targets,
        available=available,
        open_by_id=open_by_id,
        net=net,
        release_ids=release_ids,
    )

    with transaction.atomic():
        released_rows: list[dict[str, Any]] = []
        for invoice_id in release_ids:
            amount = net[invoice_id]
            # BR-PAY-031's first half: a NEGATIVE mirror hung off this payment.
            # The original rows are untouched — `allocations` refuses UPDATE and
            # DELETE in every state (payments/0002) — so this is the only lawful
            # way to unmake an application, and `allocated_so_far` nets it.
            models.Allocation.objects.create(
                tenant_id=tenant_id,
                payment=payment,
                invoice_id=invoice_id,
                amount=-amount,
            )
            released_rows.append({"invoice_id": invoice_id, "amount": amount})

        applied_rows: list[dict[str, Any]] = []
        for target in plan:
            models.Allocation.objects.create(
                tenant_id=tenant_id,
                payment=payment,
                invoice_id=target["invoice_id"],
                amount=target["amount"],
            )
            applied_rows.append(dict(target))

        applied_total = sum((row["amount"] for row in applied_rows), ZERO)
        # ── hard rule 7, INSIDE the transaction ─────────────────────────────
        # `core.audit` raises rather than losing the row, which takes the whole
        # reapply with it. Money moved between two of a customer's bills with no
        # record of who moved it is the outcome rule 7 exists to prevent.
        core_audit.money_action(
            actor,
            AUDIT_REAPPLIED,
            "payment",
            str(payment.pk),
            after={
                "payment_no": payment.payment_no,
                "account_id": str(payment.account_id),
                "amount": str(payment.amount),
                "currency": payment.currency,
                "reason": reason,
                "on_date": on_date.isoformat(),
                "released": [{**row, "amount": str(row["amount"])} for row in released_rows],
                "applied_to": [{**row, "amount": str(row["amount"])} for row in applied_rows],
                "released_total": str(released_total),
                "applied_total": str(applied_total),
                "credit_carried": str(available - applied_total),
                # Stated on the trail as well as in the docstring, because this
                # is the one write path in the module that posts nothing and a
                # reader of the trail should not have to know that already.
                "posted_to_ledger": False,
                "job": None if actor is not None else "payments.reapply",
            },
        )

        numbers = _numbers([row["invoice_id"] for row in released_rows + applied_rows])
        return Reapplied(
            payment_id=str(payment.pk),
            payment_no=payment.payment_no,
            account_id=str(payment.account_id),
            amount=payment.amount,
            currency=payment.currency,
            released=tuple(
                {**row, "invoice_number": numbers.get(row["invoice_id"])} for row in released_rows
            ),
            applied_to=tuple(
                {**row, "invoice_number": numbers.get(row["invoice_id"])} for row in applied_rows
            ),
            released_total=released_total,
            applied_total=applied_total,
            credit_carried=available - applied_total,
        )


def _validated_targets(
    *,
    payment: models.Payment,
    targets: tuple[dict[str, Any], ...],
    available: Decimal,
    open_by_id: dict[str, Any],
    net: dict[str, Decimal],
    release_ids: list[str],
) -> list[dict[str, Any]]:
    """Every refusal a reapply can make, in one place, BEFORE anything is written.

    Nothing is validated halfway through the write: an over-application caught
    on the third target would leave two mirror rows and one new row committed if
    the transaction were not there, and even with it the refusal message would
    name a bill the clerk had already stopped thinking about.
    """
    if not targets:
        raise PaymentRuleError(
            "a reapply names at least one bill to move the money ON to. Taking it off every "
            "bill and putting it nowhere is not a reapply — it leaves the money as account "
            "credit, which is what the Reverse-and-record path already does and what CS-11 "
            "exists to avoid.",
            br_ref="BR-PAY-031",
        )
    plan: list[dict[str, Any]] = []
    seen: set[str] = set()
    for target in targets:
        invoice_id = str(target.get("invoice_id") or "")
        raw = target.get("amount")
        if not invoice_id:
            raise PaymentRuleError(
                "a reapply target names a bill and an amount; one arrived with no bill.",
                br_ref="BR-PAY-031",
            )
        if invoice_id in seen:
            raise PaymentRuleError(
                f"bill {invoice_id} is named twice in one reapply. Two rows against one bill "
                "would be two allocations a reader has to add up; name it once with the total.",
                br_ref="BR-PAY-031",
            )
        seen.add(invoice_id)
        if isinstance(raw, float):
            raise PaymentRuleError(
                f"the amount {raw!r} for bill {invoice_id} is a float. Money is NUMERIC(18,6) "
                "and never binary (CLAUDE.md rule 2) — refused rather than converted.",
                br_ref="BR-PAY-002",
            )
        amount = raw if isinstance(raw, Decimal) else Decimal(str(raw))
        if amount <= ZERO:
            raise PaymentRuleError(
                f"bill {invoice_id} was given {amount}. A reapply row means money MOVED; a "
                "bill the payment should not meet is left out of the list rather than named "
                "at 0.00 — `allocation.py` draws the same line for the same reason.",
                br_ref="BR-PAY-031",
            )
        invoice = open_by_id.get(invoice_id)
        if invoice is None:
            # Two different facts, and the message says which: a bill of another
            # account, or a bill of this one that owes nothing.
            raise PaymentRuleError(
                f"bill {invoice_id} is not an open bill of account {payment.account_id}. A "
                "reapply moves money BETWEEN one account's own bills; money that belongs on "
                "another account's bill is a cross-account movement with its own writer "
                "(CR-059 CS-32) and its own balanced entry. A bill that owes nothing is not "
                "offered either — an allocation against it would put the bill in credit.",
                br_ref="BR-PAY-031",
            )
        # What the bill can still take, ADDING BACK anything this same payment is
        # about to release from it. Without that term a clerk correcting the
        # SPLIT across two bills would be refused by the money they are removing.
        headroom = invoice.balance + (
            net.get(invoice_id, ZERO) if invoice_id in release_ids else ZERO
        )
        if amount > headroom:
            raise PaymentRuleError(
                f"bill {invoice.number} can take {headroom} and {amount} was named. Money a "
                "bill cannot absorb belongs in the account's credit balance, where the next "
                "bill draws it down (BR-PAY-010) — putting it on the bill would leave a "
                "document in credit, and hard rule 4 means nobody can go back and fix it.",
                br_ref="BR-PAY-010",
            )
        plan.append({"invoice_id": invoice_id, "amount": amount})

    total = sum((row["amount"] for row in plan), ZERO)
    if total > available:
        raise PaymentRuleError(
            f"this reapply puts {total} on to bills and only {available} is being moved "
            f"(payment {payment.payment_no or payment.pk} is {payment.amount}). A reapply "
            "moves money that exists; the difference would be money the customer never paid, "
            "sitting on a bill and reducing what the utility chases.",
            br_ref="BR-PAY-031",
        )
    return plan


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §8 CS-11 · §11 task 37 · BR-PAY-031 (CONFIRMED) · BR-PAY-010 ·
#         apps/payments/allocation_release.py (the same mechanism, bill-side) ·
#         apps/payments/open_bills.py (CS-4's list the modal reuses) ·
#         apps/payments/migrations/0002 (the append-only trigger on `allocations`)
# generated: 2026-09-03 by the CR-059 payments cross-account lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — CR-059 task 38 owns S33's
#            Reapply row action and S35's modal) F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions:
#   E1 no glob in `10-scripts/gates/human_owned.txt` matches this file, so G7
#      does not read its markers. Editing that list is a process event and the
#      PO's call (its own header says so, and `allocation_release.py` records
#      the identical finding). REPORTED, not self-granted.
#   E2 `targets` is EXPLICIT and this path accepts no allocation ORDER. A
#      reapply exists because the automatic order was wrong, so re-running it
#      would undo the correction. Stated rather than left as a missing argument.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
