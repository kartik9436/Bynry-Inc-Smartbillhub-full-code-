# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-31 · task 35 — "a staff-initiated reversal, the general
#           Reverse — THE SINGLE LARGEST HOLE". The CR's own words: *"A wrong
#           amount, a duplicate, a chargeback and a disputed payment are all
#           routine, and none of them has any lawful path. The engine that would
#           do the work is finished; what is missing is the rule around it."*
# Story:    US-PAY-010 (the staff reverse)   Screens: S33 · S35 · S36
# Rules:    BR-PAY-011 (CONFIRMED — *"Reversal windows: ACH 60d, card 120d,
#           check unlimited (NSF); paid/cross-period requires Admin/Executive
#           approval; always reversing entries; consequence message shown before
#           confirm"*. Three of those four clauses were never built and this
#           module is where they are) · BR-PAY-013 (the bounce rule, and its
#           NAME is the boundary — a staff correction is not a customer's
#           cheque coming back) · BR-PAY-1070 (reversing a payment is Admin-only
#           and the gate is on the SERVICE) · BR-PAY-037 (the same user may
#           initiate and approve in v1, both acts recorded distinctly) ·
#           BR-LED-006 (a closed period is locked) · BR-TEN-043 / gate G6 (the
#           caller names the day; nothing here reads a clock) · B14 rule 31 (a
#           bill is named by its NUMBER, never by its id)
# Tests:    06-backend/tests/test_cr059_cs31_staff_reversal.py
# Impacts:  apps/payments/reversal.py (SUPPORTED_REASONS widens to four and this
#           module's three checks stand behind it) · apps/payments/reversal_api
#           (the plan route the screen reads before it confirms)
# ───────────────────────────────────────────────────────
"""BR-PAY-011's three unbuilt clauses — windows, approval, consequences.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this module decides whether a payment may
be un-done and composes the sentence a clerk reads before they do it, so it is
enrolled under the CLAUDE.md sensitive-path protocol. AI-authored 2026-09-03
under the PO ruling of 2026-08-09; row in 12-governance/09-human-review-ledger.md.

**IT WRITES NOTHING.** Every function here is a read over rows that already
exist. The writes stay in `reversal.reverse_payment`, which is the sole writer
of a reversing payment row, and this module is what it asks before it writes.

════════════════════════════════════════════════════════════════════════════
THE CASE, AND WHY IT NEEDED A RULE RATHER THAN A ROUTE
════════════════════════════════════════════════════════════════════════════
CS-31's own worked case: a customer hands over a cheque for **100.00**, the
clerk types **1,000.00** and presses Record, and two minutes later they see it.
**Four doors, all shut.** Reverse it — the engine exists and would do exactly
this, but only for a bounce. Edit the amount — there is no PUT, PATCH or DELETE
on any payment path and the router answers 405. Post −900.00 — a negative amount
is refused, and it would be a second, invisible way to express a reversal. Delete
the row — financial rows are immutable.

**So what actually happens:** the account is **900.00 in credit**, money the
customer never paid, and it will be auto-applied to their next bill silently and
correctly, because the product believes the row. The books are **900.00 out**.
And after tonight it is worse, because once the batch is cut and tied to a bank
line the deposit total carries the wrong figure too.

**Nothing in that picture is a bug. Every refusal is a rule doing its job.** The
gap was that the one lawful way out had never been given a door — and the door
could not simply be opened, because `reverse_payment` is the BOUNCE machine and
running a staff correction through it would count an NSF against a customer who
did nothing wrong and could move them to cash-only.

════════════════════════════════════════════════════════════════════════════
CLAUSE 1 · THE WINDOW IS PER TENDER, AND IT IS NEVER READ FROM A CLOCK
════════════════════════════════════════════════════════════════════════════
BR-PAY-011 names three: **ACH 60 days · card 120 days · cheque unlimited**, and
it names NSF as the reason cheques are unlimited. CS-31 asks for it *"measured
from the clearing date where there is one, otherwise the posting date, and
returned to the screen as a REASON rather than a boolean so it can be shown"*.

⚠ **A TENDER THE RULE DOES NOT NAME GETS NO WINDOW, AND THE RESULT SAYS SO.**
This product seeds seven payment methods — `ach`, `card`, `check`, `cash`,
`lockbox`, `wire`, `money_order` — and BR-PAY-011 names three of them. Inventing
a limit for the other four would be this module writing law: a 60-day window on
a wire is a refusal no human ever agreed to, and a clerk meeting it has no way
to find out who decided. So they are UNLIMITED and every verdict carries
`window_not_named_by_the_rule` naming the tender, which is a gap somebody can
close rather than a number somebody has to discover.

⚠ **AND THE WINDOW DOES NOT APPLY TO A BOUNCE AT ALL.** BR-PAY-011 puts cheques
on an unlimited window and names NSF as the reason for it: a returned item is
the BANK's decision, arriving when the bank says it arrives, and there is no
window to be outside of. Applying one would refuse to record a return that has
already happened — the money is gone whatever this product says.

════════════════════════════════════════════════════════════════════════════
CLAUSE 2 · APPROVAL, AND WHAT IT IS AND IS NOT HERE
════════════════════════════════════════════════════════════════════════════
BR-PAY-011: *"paid/cross-period requires Admin/Executive approval"*. CS-31 makes
it concrete — approval is required when the payment **is already applied to an
issued bill**, or **falls in a closed accounting period** — and adds *"the
write-off queue is the pattern to copy; do not invent a second approval shape"*.

⚠ **THE HALF THAT IS BUILT AND THE HALF THAT IS NOT, STATED RATHER THAN
BLURRED.** CS-31's own Data section reads *"None. All four reasons are already
in the column and its check constraint."* A DURABLE queue — a reversal sitting
in `requested` until somebody works it, the way a write-off does — needs a table
and a status column, and CS-31 says there is no schema. So what is built is the
REQUIREMENT and its refusal: the service computes whether approval is needed,
refuses without one by name, and records the approval it was given in the audit
row. What is NOT built is a row that waits: a clerk cannot park a reversal for
an Admin to find later, and CS-31's S36 line (*"reversals awaiting approval join
the write-off queue"*) needs the schema its own Data line says it does not have.
**Named, not approximated** — every plan carries `no_durable_approval_queue`.

**The approver may be the same person, in v1.** BR-PAY-037 is CONFIRMED for
write-offs in exactly those words — *"the SAME user holding the approver role
MAY initiate AND approve in v1; both acts recorded distinctly; enforced
separation of duties is v2"* — and inventing a stricter rule here would be this
module overturning a signed one. The whole path is already Admin-only on the
service (BR-PAY-1070), so the approval is a deliberate, recorded second act by
somebody who holds the role, and the audit row carries it.

⚠ **CS-31's ROLE SENTENCE COLLIDES WITH A SIGNED RULE AND IS NOT TAKEN HERE.**
It reads *"the three staff reasons require Admin or Executive; the bounce does
not"*. `BR-PAY-1070` (CONFIRMED 2026-09-01) makes reversing a payment
**Admin-only**, on the service, for every reason. Admin-only is NARROWER than
Admin-or-Executive, so keeping it breaks neither sentence; WIDENING to include
the Executive would reverse a signed money gate on a lane's own reading, and
loosening the bounce below Admin would reverse it twice over. So the gate stands
exactly where BR-PAY-1070 put it and the collision is REPORTED rather than
resolved — every plan carries `staff_reversal_role_unchanged_br_pay_1070`.

════════════════════════════════════════════════════════════════════════════
CLAUSE 3 · THE CONSEQUENCE MESSAGE IS COMPOSED HERE, NOT ON THE SCREEN
════════════════════════════════════════════════════════════════════════════
CS-31: *"server-composed, listing every bill that re-opens and by how much, plus
any credit that goes negative. It must be computed by the service, not assembled
on the screen, or the warning and the outcome can disagree."*

That last clause is the whole reason this is a server read. The bills that
re-open are exactly the rows `_write_reversal` will mirror — the ORIGINAL's own
allocations, in the order it walks them — so the preview and the outcome are two
readings of one list rather than two implementations of one rule.

**The credit half is the PO's own figure.** A payment that left money sitting as
account credit takes that credit back when it is reversed, and it does NOT floor
at zero: PO ruling 2026-08-11, `OQ-132`, verbatim *"Yes, it's a real debt"*. So
a 57.13 credit already refunded to the customer goes to **−57.13**, and the
consequence panel says so before the clerk confirms rather than after.

**B14 rule 31 — a bill is named by its NUMBER.** `invoice_id` is a uuid and
never reaches this payload; a bill whose number has not been minted is a stated
absence, never an id.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from importlib import import_module
from typing import Any

from apps.payments import models

ZERO = Decimal("0")
MONEY_PLACES = Decimal("0.0001")

#: `models.REVERSAL_REASONS` minus the bounce. These three are OUR correction of
#: OUR record; the fourth is the bank telling us the money came back, and every
#: clause in this module draws the line in that one place.
STAFF_REASONS: tuple[str, ...] = (
    models.REVERSAL_REASON_BANK_CHARGEBACK,
    models.REVERSAL_REASON_DATA_ENTRY_ERROR,
    models.REVERSAL_REASON_CUSTOMER_DISPUTE,
)

#: BR-PAY-011's own three, by the tender's `payment_methods` code. `None` means
#: UNLIMITED and is a ruled value for `check`; a tender absent from this map is
#: also unlimited but is REPORTED, because the rule never spoke about it.
REVERSAL_WINDOW_DAYS: dict[str, int | None] = {
    "ach": 60,
    "card": 120,
    "check": None,
}

#: Why a reversal needs somebody to approve it. Codes, never prose — the screen
#: renders language and these ride into `audit_log` (B8).
APPROVAL_BILL_ISSUED = "applied_to_an_issued_bill"
APPROVAL_PERIOD_CLOSED = "falls_in_a_closed_accounting_period"


def _money(value: Decimal | None) -> str:
    return f"{(value or ZERO).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)}"


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """A neighbour's published callable, or None while it has not published one.

    Resolved BY NAME at call time (B1 / BR-TEN-013): payments never imports
    another module's models, and an unwired seam REPORTS rather than answering.
    """
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    return getattr(target, attribute, None)


def measured_from(payment: models.Payment) -> date:
    """CS-31's own words: *"the clearing date where there is one, otherwise the
    posting date"*.

    Both are the CALLER's business moments and neither is a clock (BR-PAY-033,
    BR-TEN-043). The clearing date is preferred because a window is about how
    long ago the money actually moved, and a cheque posted on the 1st that
    cleared on the 20th moved on the 20th.
    """
    moment = payment.cleared_at or payment.posted_at
    return moment.date()


def window_verdict(payment: models.Payment, *, on: date) -> dict[str, Any]:
    """How old this payment is, against the window BR-PAY-011 gives its tender.

    `on` is the business day the reversal is being made and is an INPUT — gate
    G6 greps every money path for a clock read, and a window that expired at
    midnight in the server's timezone would refuse a correction a clerk started
    before closing time.

    Returned as a REASON rather than a boolean, which is CS-31 asking for it in
    terms: the screen has to be able to say *"this ACH cleared 74 days ago —
    outside the 60-day window"*, and a `False` cannot say that.
    """
    tender = getattr(payment.method, "code", None)
    since = measured_from(payment)
    days = (on - since).days
    named = tender in REVERSAL_WINDOW_DAYS
    limit = REVERSAL_WINDOW_DAYS.get(tender) if named else None
    return {
        "tender": tender,
        "measured_from": since.isoformat(),
        "days_elapsed": days,
        "limit_days": limit,
        # A tender with no limit is unlimited, whether the rule named it (cheque)
        # or did not (wire). The two are DIFFERENT facts and `named_by_the_rule`
        # is what keeps them apart on the screen and in the problems list.
        "unlimited": limit is None,
        "named_by_the_rule": named,
        "within": limit is None or days <= limit,
    }


def approval_verdict(payment: models.Payment, *, on: date) -> dict[str, Any]:
    """BR-PAY-011's *"paid/cross-period requires approval"*, computed.

    Two triggers and they are different questions:

      * **The payment is already applied to an issued bill.** Reversing it
        re-opens that bill, which puts a customer back into arrears on a
        document they have been sent — so somebody holding the role signs for it.
      * **The reversal falls in a CLOSED accounting period.** BR-LED-006 locks a
        closed month, and a correction that reaches back into one is a finance
        decision rather than a counter decision.

    ⚠ **AN UNANSWERABLE QUESTION IS REPORTED, NEVER ANSWERED "NO".** When the
    ledger cannot say whether the period is closed, this returns the problem and
    does NOT add the trigger — but it also does not claim the period is open. A
    screen that read silence as "no approval needed" would be the check that
    cannot fail; the sentence is on the plan so a person can see the control did
    not run.
    """
    reasons: list[str] = []
    problems: list[dict[str, Any]] = []

    # ── trigger 1: an issued bill is being re-opened ────────────────────────
    # Read off the allocations this payment actually wrote — the same list the
    # reversal will mirror — rather than asking billing a second question, so
    # the trigger and the consequence can never disagree about which bills.
    applied = payment.allocations.exclude(amount=ZERO).exists()
    if applied:
        reasons.append(APPROVAL_BILL_ISSUED)

    # ── trigger 2: the books have closed the month it lands in ─────────────
    resolve_entry_date = _resolve("ledger", "resolve_entry_date", "close")
    if not callable(resolve_entry_date):
        problems.append(
            {
                "code": "closed_period_check_unavailable",
                "br_ref": "BR-LED-006",
                "detail": "the books could not be asked whether this month is closed, so that "
                "half of the approval rule did not run. It is reported rather than assumed "
                "open: an unchecked control and a satisfied one look identical on a screen.",
            }
        )
    else:
        try:
            _moved, note = resolve_entry_date(on)
        except Exception:  # pragma: no cover - a tenant with no fiscal calendar
            problems.append(
                {
                    "code": "closed_period_check_unavailable",
                    "br_ref": "BR-LED-006",
                    "detail": "this tenant has no fiscal calendar, so no period can be closed "
                    "and that half of the approval rule could not be evaluated. Reported "
                    "rather than assumed.",
                }
            )
        else:
            # `note is not None` IS the closed answer — `resolve_entry_date`
            # returns one only when it had to move the date. The moved date is
            # deliberately discarded: a reversal posts on the day the money went
            # back (BR-PAY-021) and forwarding it here would silently re-date a
            # money record, which is the caller's call and not this read's
            # (`posting._refuse_if_period_closed`'s own recorded reasoning).
            if note is not None:
                reasons.append(APPROVAL_PERIOD_CLOSED)

    return {"required": bool(reasons), "reasons": reasons, "problems": problems}


def consequences(payment: models.Payment) -> dict[str, Any]:
    """Every bill that re-opens and by how much, plus the credit that goes back.

    CS-31: *"It must be computed by the service, not assembled on the screen, or
    the warning and the outcome can disagree."* The rows below are the ORIGINAL's
    own allocations in the order `_write_reversal` walks them, so the preview and
    the outcome are two readings of ONE list.
    """
    rows = list(payment.allocations.all().order_by("created_at", "id"))
    invoice_numbers = _resolve("payments", "invoice_numbers", "billing_seam")
    numbers: dict[Any, Any] = {}
    problems: list[dict[str, Any]] = []
    if callable(invoice_numbers):
        numbers = invoice_numbers([row.invoice_id for row in rows]) or {}
    elif rows:
        problems.append(
            {
                "code": "bill_numbers_unavailable",
                "br_ref": "BR-BIL-001",
                "detail": "the bills this payment met could not be named, so they are counted "
                "and not listed. The amounts below are this payment's own rows and are exact.",
            }
        )

    reopening = []
    allocated = ZERO
    for row in rows:
        allocated += row.amount
        reopening.append(
            {
                # B14 rule 31 — the NUMBER. `invoice_id` is a uuid and does not
                # appear in this payload at all, so no screen can print one.
                "bill_no": numbers.get(row.invoice_id),
                "amount": _money(row.amount),
                "currency": payment.currency,
            }
        )

    # What the payment left sitting as account credit, which the reversal takes
    # back. Nothing floors it: PO 2026-08-11, OQ-132, *"Yes, it's a real debt"*.
    credit_taken_back = payment.amount - allocated
    credit_now = _credit_position(payment.account_id)
    credit_after = None if credit_now is None else credit_now - credit_taken_back
    if credit_now is None:
        problems.append(
            {
                "code": "credit_position_unavailable",
                "br_ref": "BR-PAY-041",
                "detail": "the account's credit balance could not be read, so what this "
                "reversal leaves it at is not shown. The bills above are exact.",
            }
        )

    return {
        "currency": payment.currency,
        "amount": _money(payment.amount),
        "bills_reopening": reopening,
        "bills_reopening_total": _money(allocated),
        "credit_taken_back": _money(credit_taken_back),
        "credit_after": None if credit_after is None else _money(credit_after),
        # The PO's own case, made visible BEFORE the clerk confirms rather than
        # discovered on the account afterwards.
        "credit_goes_negative": credit_after is not None and credit_after < ZERO,
        "problems": problems,
    }


def _reversed_so_far(payment: models.Payment) -> Decimal:
    """Σ of every reversal already standing against this payment, POSITIVE.

    Imported inside the function because `reversal` imports THIS module, and the
    Σ has exactly one owner (`reversal.reversed_so_far`): a second copy of it
    here would be a second answer to *"how much has come back"*, on a money
    path, which is the thing `BR-PAY-884`'s own docstring warns about.
    """
    from apps.payments import reversal

    return reversal.reversed_so_far(payment.tenant_id, payment.pk)


def _credit_position(account_id: Any) -> Decimal | None:
    from apps.payments import selectors

    reader = getattr(selectors, "account_credit_position", None)
    if not callable(reader):  # pragma: no cover - defensive
        return None
    try:
        return reader(account_id)
    except Exception:  # pragma: no cover - an unreadable account is reported
        return None


def reversal_plan(payment: models.Payment, *, reason: str, on: date) -> dict[str, Any]:
    """The whole of BR-PAY-011's *"shown before confirm"*, in one read.

    `reason` decides which clauses APPLY — that is the boundary BR-PAY-013 draws
    by its own name, and it is drawn in exactly one place:

        nsf                  the BANK returned the item. No window (there is
                             nothing to be outside of), no approval (nobody
                             chose this), and the count, the cash-only flag and
                             the returned-payment letter all fire.
        the other three      OUR correction of OUR record. Window and approval
                             apply, and none of the three NSF consequences fire.
    """
    staff = reason in STAFF_REASONS
    window = window_verdict(payment, on=on)
    approval = (
        approval_verdict(payment, on=on)
        if staff
        else {
            "required": False,
            "reasons": [],
            "problems": [],
        }
    )
    outcome = consequences(payment)

    problems: list[dict[str, Any]] = [*approval["problems"], *outcome["problems"]]
    if staff and not window["named_by_the_rule"]:
        problems.append(
            {
                "code": "window_not_named_by_the_rule",
                "br_ref": "BR-PAY-011",
                "detail": "the rule sets a reversal window for ACH, card and cheque payments "
                "and says nothing about this one, so no time limit is applied. Inventing one "
                "would be a refusal nobody agreed to.",
            }
        )
    problems.append(
        {
            "code": "no_durable_approval_queue",
            "br_ref": "BR-PAY-011",
            "detail": "a reversal that needs approval cannot be parked for somebody to work "
            "later. The approval is given at the moment it is done and recorded with it; "
            "there is no waiting list, because a row that waits needs a table this change "
            "does not add.",
        }
    )
    problems.append(
        {
            "code": "staff_reversal_role_unchanged_br_pay_1070",
            "br_ref": "BR-PAY-1070",
            "detail": "every reversal, for every reason, is still an Admin's act. A wider set "
            "of roles for staff corrections was proposed and is not taken here, because "
            "widening who may move money is a ruling rather than a reading.",
        }
    )
    if staff:
        problems.append(
            {
                "code": "staff_reversal_charges_no_returned_item_fee",
                "br_ref": "BR-PAY-013",
                "detail": "this is our own correction, so it counts no returned payment "
                "against the customer, does not move them to cash-only and sends them no "
                "returned-payment letter. Those three belong to a cheque that bounced.",
            }
        )

    return {
        "reason": reason,
        "is_staff_correction": staff,
        "on": on.isoformat(),
        # ── CR-059 CS-33 (task 67) — WHAT THIS PAYMENT STILL STANDS FOR ──────
        # The S35 modal's amount field defaults to the whole of it and shows
        # *"what will still stand afterwards"*. **That remainder is measured
        # against THIS figure and never against `payments.amount`**, because
        # after one partial reversal the two differ — and a screen doing its own
        # subtraction would offer a clerk an amount the service is about to
        # refuse, at the exact moment they are deciding. `reversed_payment_dict`
        # already serves `still_stands` AFTER the act for the same reason; this
        # is the same fact BEFORE it.
        #
        # `stands_for` reaches 0 when a payment is fully reversed, and then
        # nothing more may come back against it (BR-PAY-884): a customer who
        # pays again after a bounce makes a NEW payment.
        "already_reversed": _money(_reversed_so_far(payment)),
        "stands_for": _money(payment.amount - _reversed_so_far(payment)),
        "window": window,
        "window_applies": staff,
        "approval": approval,
        "consequences": outcome,
        # The one boolean a screen needs to decide whether Confirm is live, and
        # it is SERVED rather than derived from three fields on the client — the
        # same argument CS-31 makes for the consequence message.
        "can_reverse": (not staff) or window["within"],
        "problems": problems,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §8 CS-31 · §11 task 35 (sources: 12-governance/11-change-requests.md CR-059 §8 CS-31 verbatim · 04-docs/05-modules/08-payments/02-business-rules.md BR-PAY-011 / BR-PAY-013 / BR-PAY-1070 / BR-PAY-037 · 06-backend/apps/payments/reversal.py read function by function · apps/ledger/close.resolve_entry_date)
# generated: 2026-09-03 by the CR-059 W7 staff-reversal lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — the test file will not collect at the pinned tip (`ImportError: cannot import name 'reversal_rules'`) and the three staff reasons are refused by name there; verbatim in the lane report. Proved on real PostgreSQL (law 14), not the SQLite default.
# exceptions: (1) NO DURABLE APPROVAL QUEUE — CS-31's own Data line says *"None"* and a row that waits needs a table; the requirement and its refusal are built, the waiting list is named on every plan and not approximated · (2) THE ROLE GATE IS NOT WIDENED — CS-31 proposes Admin-or-Executive for staff reasons and BR-PAY-1070 (CONFIRMED) makes every reversal Admin-only; Admin-only is narrower and breaks neither sentence, so the collision is reported rather than resolved by a lane · (3) A TENDER BR-PAY-011 DOES NOT NAME GETS NO WINDOW and says so — a 60-day limit on a wire would be a refusal no human agreed to · (4) THE CLOSED-PERIOD ANSWER IS REPORTED WHEN IT CANNOT BE READ, never defaulted to open: an unchecked control and a satisfied one look identical on a screen · (5) THIS MODULE WRITES NOTHING and catches no database error, so no savepoint is involved (law 14) — stated rather than assumed
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
