# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-005 (issue — the two payments-side writes that belong at the
#           moment a draft becomes a bill) · US-BIL-010 (the first bill's
#           DEPOSIT line, which draws on deposit-purpose money already paid)
#           Screens: S30 · S31 step 6 · S32
# Rules:    BR-PAY-010 (a carried credit is drawn down against a newly issued
#           bill) · BR-PAY-041 (a NEGATIVE credit position is a DEBT and is
#           never floored to zero) · BR-PAY-015 (an autopay capture intent is
#           recorded at issue, dated the bill's DUE date) · BR-PAY-012 (a
#           deposit-purpose payment satisfies the first bill's deposit line) ·
#           BR-BIL-012 (the first bill carries the deposit line) · BR-BIL-055
#           (a break never blocks the run) · CLAUDE.md rule 1 (tenant scoping) ·
#           rule 2 (money NUMERIC(18,6), never float) · rule 4 (immutability) ·
#           rule 6 (idempotency) · rule 7 (audit) · B1 (no cross-module import)
# Tests:    06-backend/tests/test_us_bil_005_payments_wiring.py
# Impacts:  apps/billing/issue.issue_invoice (calls both writes inside the issue
#           transaction) · apps/payments/credit.apply_credit_at_issue ·
#           apps/payments/credit.deposit_payments_for_account ·
#           apps/payments/autopay.record_intent_at_issue (all resolved BY NAME)
# ───────────────────────────────────────────────────────
"""billing → payments SEAM: the three call sites payments could not make itself.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this runs INSIDE `issue.issue_invoice`'s
transaction and moves a customer's money against an immutable financial record
(CLAUDE.md 🔒 + rule 4). AI-authored 2026-08-15 under the PO ruling of
2026-08-09; it needs a row in 12-governance/09-human-review-ledger.md.

⚠ CORRECTED 2026-09-01 (DEF-2791) — THE PARAGRAPH BELOW IS HISTORY, NOT THE
CURRENT STATE. `human_owned.txt` carries
`06-backend/apps/billing/payments_seam.py` today ("Billing→payments handoff —
applies a customer credit to an issued bill and records the autopay capture
intent"), measured 2026-09-01, so **G7 DOES read the markers above**. The list
does not date this line, so no ruling is dated here either — inventing one would
be worse than the gap. The ask below was answered; it is kept because why a
money path went unguarded is worth knowing.

⚠ **NO GLOB IN `10-scripts/gates/human_owned.txt` MATCHES THIS FILE**, so G7
does not read the markers above. Editing that guard list is a process event, so
the line is REPORTED for the PO batch rather than self-granted — the posture
`posting_seam.py`, `delivery_seam.py` and `pending.py` all took from here.

╔══════════════════════════════════════════════════════════════════════════╗
║  BUILT IS NOT WIRED (hard-won law 2). THIS FILE IS THE WIRE.             ║
╚══════════════════════════════════════════════════════════════════════════╝

The payments lane finished three functions and could not call any of them,
because the caller is billing's and B1 forbids payments writing billing's path.
Its own docstrings say so — `deposit_payments_for_account` carries *"⚠ NOTHING
CALLS IT"* in as many words. A function nothing calls is a feature that does not
exist in the running product, however green its own tests are: that is law 2,
and four defects in one day were exactly this.

  * **apply_credit_at_issue** (BR-PAY-010) — a customer who overpaid last month
    has that money sitting on the account, and the bill that just issued is what
    it is for. Worked, the payments lane's own frozen cases: a **57.13** credit
    against a **184.20** bill applies **57.13** and leaves **0.00**; against a
    **42.10** bill it applies **42.10** and **15.03** stays carried for next
    cycle; a retried issue applies **0.00**; a **−57.13** position is a DEBT and
    applies nothing rather than being read as credit.
  * **record_intent_at_issue** (BR-PAY-015) — an autopay-enrolled account's bill
    records what SHOULD be captured and when. Worked, PE-12: **292.87**
    scheduled **22 Aug 2026**, status `awaiting_rails`. **There are no payment
    rails in this release**; the intent is the record staff work from, and the
    money is recorded by hand. Naming that here rather than letting a reader
    assume a capture happened is the point of the state's name.
  * **deposit_payments_for_account** (BR-PAY-012) — the first bill's deposit
    line (BR-BIL-012) is satisfied by deposit-purpose money already paid.
    US-BIL-010 is what draws on it; see `deposit_paid_for_account` below.

────────────────────────────────────────────────────────────────────────────
AN UNWIRED SEAM REPORTS. IT NEVER ANSWERS ZERO.
────────────────────────────────────────────────────────────────────────────
The distinction is the whole safety of this file, and it is money in both
directions. If payments has not published a read, `deposit_paid_for_account`
returns **None** and its caller says *"we could not ask"* — because `0.00`
would mean *"the customer has paid no deposit"*, and a first bill that charged a
deposit already paid would take $150.00 twice from somebody moving house.

The same rule runs the other way for the two WRITES: neither is allowed to
break a bill run. `CreditOutcome` / `IntentOutcome` carry `problems` rather than
raising, so a deployment whose payments module is not migrated issues its bills
and reports what it could not do (BR-BIL-055 — a break never blocks the run).
The ONE exception is a payments-side rule refusal on a bill that IS being
credited: that is money, it is translated into `BillingRuleError` (DEF-047's
lesson, the same translation `posting_seam.PostingRefused` makes), and it takes
that bill's issue with it rather than 499 others.

────────────────────────────────────────────────────────────────────────────
RESOLVED BY NAME, AT CALL TIME
────────────────────────────────────────────────────────────────────────────
No `import apps.payments` anywhere here (B1, gate G6). The idiom is
`gather.py`'s, `posting_seam.py`'s and `delivery_seam.py`'s: `import_module` at
call time, `getattr`, and a `None` that the caller handles. The contract is
greppable by name from both sides, which is what G20 checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import Any

from apps.billing.exceptions import BillingRuleError

PAYMENTS_MODULE = "payments"
CREDIT_KIND = "credit"
AUTOPAY_KIND = "autopay"

#: Money's own zero. `Decimal("0")`, never `0` and never `0.0` — a comparison
#: against a float is how a binary fraction gets into a money path (rule 2).
ZERO = Decimal("0")

CREDIT_APPLY = "apply_credit_at_issue"  # (account_id, invoice_id, invoice_total, …)
CREDIT_DEPOSIT_READ = "deposit_payments_for_account"  # (account_id) -> Decimal
AUTOPAY_INTENT = "record_intent_at_issue"  # (account_id, invoice_id, amount, due_date, …)

#: BR-BIL-035's arrears read: every bill of one account that still owes money,
#: with what is left on each. Named here so the contract is greppable from BOTH
#: sides of the boundary, exactly as the three above are.
#:
#: It lives in payments' OWN seam module rather than in `apps.payments.selectors`
#: because that is where payments published it, and pointing at the real
#: publisher is the whole point of resolving by name — a constant naming a
#: function that does not exist is the "comment claiming a guarantee" hard-won
#: law 1 is about. The day payments moves it, this line moves and nothing else.
PRIOR_POSITION_MODULE = "billing_seam"
PRIOR_POSITION_READ = "open_invoices_for_account"  # (account_id) -> OpenPosition

#: CR-059 CS-36's PAID-IN-FULL read: Σ of payments' own allocation rows against
#: ONE bill, NET of the negative mirror rows a bounce or a release writes.
#:
#: It lives in payments' own seam module because that is where payments
#: published it — the same reason `PRIOR_POSITION_READ` points there — and a
#: constant naming a function that does not exist is the "comment claiming a
#: guarantee" hard-won law 1 is about.
ALLOCATED_MODULE = "billing_seam"
ALLOCATED_READ = "allocated_so_far"  # (invoice_id) -> Decimal (NET, signed)

#: `CR-101-BRC03` §06 — the Fix a bill wizard's step-1 table. The blueprint
#: (p133) draws the bills a scope resolves to as `BILL · PERIOD · AMOUNT ·
#: PAID · STATE` with a totals row (*"Six bills · $1,454.10 · $904.50"*), and
#: PAID is payments' fact: billing knows what a bill ASKED for and structurally
#: cannot know what has met it (OQ-113). Two reads, both over payments' own
#: `allocations` table, both ONE statement however many bills the scope holds
#: (`NFR-3` — a run at T5 is 40,000 bills and a page is fifty):
#:   * the per-bill map for the PAGE on screen, and
#:   * the Σ over the WHOLE scope for the totals row.
#: Published in payments' own seam module beside `allocated_so_far`, and named
#: here for the reason every other constant in this file gives.
ALLOCATED_MANY_READ = "allocated_for_invoices"  # (invoice_ids) -> {str(id): Decimal}
ALLOCATED_TOTAL_READ = "allocated_total_for_invoices"  # (invoice_ids) -> Decimal

#: CR-059 CS-36's RELEASE (BR-PAY-1072/1073/1074) — the correction's missing
#: fifth step. One NEGATIVE mirror row per payment still applied to the bill
#: being replaced, hung off that payment, editing nothing and posting NO
#: journal line. Payments executes it; billing only emits the plan
#: (BR-BIL-014, EP-BIL-04 §5 *"execution payments-owned"*).
RELEASE_MODULE = "allocation_release"
RELEASE_CALL = "release_allocations_for_invoice"  # (invoice_id, reason, …) -> Released

#: BR-BIL-160's settlement read (PO 2026-08-27, OQ-530). What the utility holds
#: ON ACCOUNT for this customer — payments' own signed figure, and the ONLY
#: record this product keeps of money paid against a MIGRATED opening balance.
#:
#: It lives in `apps.payments.selectors` because that is where payments
#: published it, and the constant points at the real publisher for the reason
#: every other name here does: a constant naming a function that does not exist
#: is the "comment claiming a guarantee" hard-won law 1 is about.
CREDIT_POSITION_MODULE = "selectors"
CREDIT_POSITION_READ = "account_credit_position"  # (account_id) -> Decimal (SIGNED)

#: CR-059 CS-38's WRITE — the half that makes a goodwill concession visible to
#: the customer. Payments records a CREDIT-type row that its own credit position
#: then picks up with no further change; billing keeps the credit note as the
#: document and the single ledger posting.
#:
#: Named here rather than imported for the reason every other constant in this
#: file gives, and the write is payments' OWN service function — billing writes
#: no payments table (B1, cross-module writes are forbidden).
CONCESSION_MODULE = "services"
CONCESSION_CALL = "record_concession_credit"  # (account_id, amount, reason_code, on_date, …)

#: What this seam CANNOT do, carried on every result so a caller never has to
#: infer an absence (the MOVE_OUT_UNAVAILABLE precedent, hard-won law 1).
PAYMENTS_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "no_payment_rails_in_this_release",
        "br_ref": "BR-PAY-015",
        "detail": "an autopay capture INTENT records what should be captured and when; "
        "nothing is charged. There are no payment rails in this release, the intent's own "
        "state is `awaiting_rails`, and staff record the money when it arrives. A reader "
        "who takes an intent for a payment would show a customer as paid when they are not.",
    },
)


@dataclass(frozen=True)
class CreditOutcome:
    """What a carried credit did to this bill — or why nothing was asked.

    `applied` is `None` when the seam could not be reached, and that is NOT the
    same fact as `Decimal("0.00")`: zero means *the customer had no credit*,
    and None means *nobody asked*. A screen that rendered the two the same way
    would tell a customer their credit was spent when it was never looked at.
    """

    invoice_id: str
    applied: Decimal | None = None
    remaining_credit: Decimal | None = None
    invoice_balance_after: Decimal | None = None
    problems: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class IntentOutcome:
    """The autopay capture intent this bill recorded — or why it did not.

    `created=False` with an `intent_id` is the hard-rule-6 REPLAY (a resumed
    release re-issuing the same invoice finds the intent already there and
    writes nothing, which is correct). `created=False` with no id is a
    non-enrolled account, which is the ordinary case and never an error.
    """

    invoice_id: str
    intent_id: str | None = None
    created: bool = False
    amount: Decimal | None = None
    scheduled_on: date | None = None
    status: str | None = None
    problems: tuple[dict[str, Any], ...] = field(default=PAYMENTS_UNAVAILABLE)


def _resolve(module: str, attribute: str) -> Any:
    """The owning module's callable, or None while it has not published one.

    getattr at CALL time — the idiom `gather.py`, `issue.py`, `posting_seam.py`
    and `delivery_seam.py` all use, so no import statement binds billing to
    payments' internals (B1) and nothing here needs re-wiring when the owner
    moves a function.
    """
    try:
        target = import_module(f"apps.{PAYMENTS_MODULE}.{module}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _payment_refusals() -> tuple[type[BaseException], ...]:
    """`apps.payments.exceptions.PaymentRuleError`, if payments publishes one.

    Resolved rather than imported for the same B1 reason as everything else
    here, and caught rather than allowed to escape for DEF-047's: a refusal in
    the OWNER's vocabulary sails straight through `issue_run`'s
    `except BillingRuleError` and takes the other 499 bills with it, which is
    what BR-BIL-055 forbids and what that defect already cost this repo once.
    """
    found: list[type[BaseException]] = []
    for module, name in (("exceptions", "PaymentRuleError"), ("services", "PaymentRuleError")):
        try:
            target = import_module(f"apps.{PAYMENTS_MODULE}.{module}")
        except ImportError:  # pragma: no cover - defensive
            continue
        candidate = getattr(target, name, None)
        if isinstance(candidate, type) and issubclass(candidate, BaseException):
            found.append(candidate)
    return tuple(found)


def _unwired(what: str, attribute: str, consequence: str) -> dict[str, Any]:
    return {
        "code": f"payments_{attribute}_not_published",
        "br_ref": "B1",
        "detail": (
            f"apps.payments.{what}.{attribute} is not published on this deployment, so "
            f"{consequence} Nothing was assumed and nothing was written."
        ),
    }


@dataclass(frozen=True)
class ConcessionOutcome:
    """What a goodwill concession left on the ACCOUNT, or why nothing was asked.

    `credit_position_after` is `None` when the seam could not be reached, and
    that is NOT the same fact as `Decimal("0.00")` — the `CreditOutcome`
    distinction above, for the same reason: zero means the credit was recorded
    and immediately spent, None means nobody recorded anything and the customer
    is about to be chased for money they were told they no longer owe.
    """

    credit_note_id: str
    payment_id: str | None = None
    payment_no: str | None = None
    amount: Decimal | None = None
    credit_position_after: Decimal | None = None
    created: bool = False
    problems: tuple[dict[str, Any], ...] = ()


def record_concession_credit(
    *,
    credit_note: Any,
    account_id: Any,
    amount: Decimal,
    reason_code: str,
    on_date: date,
    currency: str | None = None,
    memo: str | None = None,
    actor: Any = None,
) -> ConcessionOutcome:
    """CR-059 CS-38 — tell payments that this concession exists.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  BILLING KEEPS THE DOCUMENT AND THE POSTING. PAYMENTS GETS THE       ║
    ║  BALANCE. NEITHER SIDE POSTS TWICE.                                  ║
    ╚══════════════════════════════════════════════════════════════════════╝
    `execute_credit_only` has already written the credit note and emitted the
    ONE balanced entry the PO ruled on 2026-08-12 — DR write-off / CR customer
    credit balance. What it could not do is move a figure any customer or clerk
    can read: outstanding is bill totals less payment ALLOCATIONS and account
    credit is payments less allocations less refunds, and **neither reads
    `credit_notes`**. So a 25.00 concession was real in the books, invisible
    everywhere else, and a letter went out telling the customer about it.

    This call closes that, by asking payments to record a CREDIT-type row for
    the same amount, carrying `already_posted_source="credit_note"` so the row
    posts nothing. Payments' own credit position then picks it up with no change
    at all, and billing's existing draw-down consumes it at the next bill.

    **IT NEVER RAISES INTO THE CORRECTION.** A concession whose credit row could
    not be written is reported on `problems` and the credit note stands: the
    books are already right, the note is already issued, and hard rule 4 forbids
    unwinding either. Losing the balance half is bad; losing a posted, immutable,
    already-communicated concession because a downstream seam refused is worse.
    That is the same posture `apply_credit_at_issue` takes for the same reason.
    """
    write = _resolve(CONCESSION_MODULE, CONCESSION_CALL)
    note_id = str(getattr(credit_note, "pk", credit_note))
    if write is None:
        return ConcessionOutcome(
            credit_note_id=note_id,
            problems=(
                _unwired(
                    CONCESSION_MODULE,
                    CONCESSION_CALL,
                    "this goodwill concession is posted and the customer has been told about "
                    "it, and NOTHING has moved the balance they read (CR-059 CS-38): "
                    "outstanding still shows the bill in full and the collection ladder will "
                    "chase it.",
                ),
            ),
        )
    try:
        recorded = write(
            actor,
            account_id=account_id,
            amount=amount,
            reason_code=reason_code,
            on_date=on_date,
            currency=currency,
            memo=memo,
            # Hard rule 6 — the credit note is the stable key, so a correction
            # replayed after a crash finds the credit row it already wrote.
            source_reference=note_id,
        )
    except _payment_refusals() as refusal:
        return ConcessionOutcome(
            credit_note_id=note_id,
            problems=(
                {
                    "code": "concession_credit_not_recorded",
                    "br_ref": "BR-PAY-010",
                    "detail": f"the credit note and its journal entry stand, and payments "
                    f"refused the account credit that goes with them: {refusal}. The customer "
                    "has been told they were given this money and the balance they read has "
                    "not moved (CR-059 CS-38). Nothing was unwound — an issued credit note "
                    "and a posted entry are immutable (hard rule 4).",
                },
            ),
        )
    return ConcessionOutcome(
        credit_note_id=note_id,
        payment_id=getattr(recorded, "payment_id", None),
        payment_no=getattr(recorded, "payment_no", None),
        amount=getattr(recorded, "amount", None),
        credit_position_after=credit_position_for_account(account_id),
        created=bool(getattr(recorded, "created", False)),
        problems=tuple(getattr(recorded, "problems", ()) or ()),
    )


def apply_credit_at_issue(invoice: Any, *, actor: Any = None, occurred_on: date | None = None):
    """BR-PAY-010 — draw the account's carried credit against this new bill.

    Called from inside `issue.issue_invoice`'s transaction, AFTER the status
    moves, for the same reason the posting handoff and the delivery rows are:
    the allocation names an invoice that exists, and a credit spent against a
    draft that then breaks on a GL stamp would be money moved for a bill nobody
    ever received.

    **THE CALLER'S FIGURE IS THE BILL'S OWN TOTAL**, read off the row and passed
    across as a `Decimal` — this seam prices nothing, rounds nothing and floors
    nothing. The payments module refuses a non-Decimal outright (rule 2) and
    that refusal is left to it rather than pre-empted here.

    Worked, the payments lane's own frozen cases: **57.13** credit against a
    **184.20** bill applies **57.13** and leaves **0.00**; against a **42.10**
    bill it applies **42.10** and carries **15.03**; a retry applies **0.00**
    because the first application already met the bill; a **−57.13** position is
    a DEBT (BR-PAY-041) and applies nothing rather than being read as credit.

    A payments RULE refusal is translated and RAISED — that bill does not issue.
    An UNPUBLISHED seam is reported and the bill issues, because a deployment
    whose payments module is not migrated must still be able to bill.
    """
    invoice_id = str(getattr(invoice, "pk", invoice))
    apply = _resolve(CREDIT_KIND, CREDIT_APPLY)
    if apply is None:
        return CreditOutcome(
            invoice_id=invoice_id,
            problems=(
                _unwired(
                    CREDIT_KIND,
                    CREDIT_APPLY,
                    "no carried credit was drawn down against this bill (BR-PAY-010). The "
                    "customer's credit is untouched and still theirs; it will apply on the "
                    "next issue that can reach the seam.",
                ),
            ),
        )
    total = getattr(invoice, "total", None)
    if not isinstance(total, Decimal):
        raise BillingRuleError(
            f"bill {getattr(invoice, 'invoice_no', invoice_id)} carries a total that is not "
            f"a Decimal ({total!r}), so no credit can be applied against it. Money is "
            "NUMERIC(18,6) and never a float (CLAUDE.md rule 2) — refused rather than "
            "converted, because converting it is where a figure nobody can reproduce "
            "enters the books.",
            br_ref="BR-PAY-010",
        )
    try:
        result = apply(
            actor=actor,
            account_id=getattr(invoice, "account_id", None),
            invoice_id=invoice_id,
            invoice_total=total,
            occurred_on=occurred_on,
        )
    except _payment_refusals() as refusal:
        raise BillingRuleError(
            f"the payments module refused to apply this account's credit to bill "
            f"{getattr(invoice, 'invoice_no', invoice_id)}: {refusal}. The bill is not "
            "issued — a bill that issued while its credit application failed would show "
            "the customer owing money they had already paid.",
            br_ref="BR-PAY-010",
        ) from refusal
    return CreditOutcome(
        invoice_id=invoice_id,
        applied=getattr(result, "applied", None),
        remaining_credit=getattr(result, "remaining_credit", None),
        invoice_balance_after=getattr(result, "invoice_balance_after", None),
    )


def record_autopay_intent(invoice: Any, *, actor: Any = None):
    """BR-PAY-015 — record what autopay SHOULD capture, and when.

    One intent per invoice (`UNIQUE (tenant, invoice_id)` is the guarantee, not
    a SELECT-then-INSERT), dated the bill's own DUE date — never today, never
    user-set. Worked, PE-12: **292.87** scheduled **22 Aug 2026**, status
    `awaiting_rails`.

    A NON-ENROLLED ACCOUNT IS NOT AN ERROR and is the ordinary case: a run
    issuing four hundred bills must not fail because three hundred accounts are
    not on autopay. The payments module reports that itself and this passes the
    report through unchanged.

    **NOTHING IS CHARGED.** `awaiting_rails` is the state's own name — see
    `PAYMENTS_UNAVAILABLE`.
    """
    invoice_id = str(getattr(invoice, "pk", invoice))
    record = _resolve(AUTOPAY_KIND, AUTOPAY_INTENT)
    if record is None:
        return IntentOutcome(
            invoice_id=invoice_id,
            problems=PAYMENTS_UNAVAILABLE
            + (
                _unwired(
                    AUTOPAY_KIND,
                    AUTOPAY_INTENT,
                    "no autopay capture intent was recorded for this bill (BR-PAY-015). An "
                    "enrolled customer's bill will need collecting by hand until the seam "
                    "is reachable.",
                ),
            ),
        )
    due_date = getattr(invoice, "due_date", None)
    if due_date is None:
        # BR-PAY-015 dates the intent on the DUE date and BR-BIL-024 derives
        # that date at issue. Reaching a clock or the issue date instead would
        # promise a customer a capture on a day nobody agreed.
        return IntentOutcome(
            invoice_id=invoice_id,
            problems=PAYMENTS_UNAVAILABLE
            + (
                {
                    "code": "invoice_has_no_due_date",
                    "br_ref": "BR-PAY-015 · BR-BIL-024",
                    "detail": "an autopay capture intent is dated the bill's DUE date and this "
                    "bill carries none, so no intent was recorded. Nothing here substitutes "
                    "today's date: a capture on a day nobody agreed is money taken early.",
                },
            ),
        )
    total = getattr(invoice, "total", None)
    if not isinstance(total, Decimal):
        raise BillingRuleError(
            f"bill {getattr(invoice, 'invoice_no', invoice_id)} carries a total that is not "
            f"a Decimal ({total!r}), so no autopay capture intent can be recorded against "
            "it (CLAUDE.md rule 2).",
            br_ref="BR-PAY-015",
        )
    try:
        result = record(
            actor=actor,
            account_id=getattr(invoice, "account_id", None),
            invoice_id=invoice_id,
            amount=total,
            due_date=due_date,
            currency=getattr(invoice, "currency", "USD"),
        )
    except _payment_refusals() as refusal:
        raise BillingRuleError(
            f"the payments module refused an autopay capture intent for bill "
            f"{getattr(invoice, 'invoice_no', invoice_id)}: {refusal}.",
            br_ref="BR-PAY-015",
        ) from refusal
    return IntentOutcome(
        invoice_id=invoice_id,
        intent_id=getattr(result, "intent_id", None),
        created=bool(getattr(result, "created", False)),
        amount=getattr(result, "amount", None),
        scheduled_on=getattr(result, "scheduled_on", None),
        status=getattr(result, "status", None),
        problems=PAYMENTS_UNAVAILABLE + tuple(getattr(result, "problems", ()) or ()),
    )


def deposit_paid_for_account(account_id: Any) -> Decimal | None:
    """BR-PAY-012 — deposit-purpose money already paid, or **None** if unasked.

    US-BIL-010's first bill carries a DEPOSIT line (BR-BIL-012) and BR-PAY-012
    says a deposit-purpose payment *"satisfies the first-bill deposit line at
    issue"*. This is the figure that satisfaction draws on, and the payments
    lane published it with *"⚠ NOTHING CALLS IT"* on its own docstring.

    **`None` IS NOT `Decimal("0.00")` AND THE DIFFERENCE IS $150.00 OF SOMEBODY
    ELSE'S MONEY.** Zero means *this customer has paid no deposit*, so the first
    bill charges one. None means *the seam could not be reached*, and a caller
    that read None as zero would charge a deposit the customer has already paid
    — on a bill that is immutable the moment it issues. So the caller REPORTS
    and does not net; see `first_bill.deposit_line_for`.
    """
    read = _resolve(CREDIT_KIND, CREDIT_DEPOSIT_READ)
    if read is None:
        return None
    try:
        paid = read(account_id)
    except _payment_refusals():  # pragma: no cover - the read raises no rule today
        return None
    return paid if isinstance(paid, Decimal) else None


def allocated_against_invoice(invoice_id: Any) -> Decimal | None:
    """What payments has applied to this ONE bill — or **None** if unasked.

    CR-059 CS-36. Billing owns `invoices` and knows what a bill ASKED for; it
    does not own `allocations` and structurally cannot know what has met it.
    So the figure is payments' (`billing_seam.allocated_so_far`), resolved by
    name at call time like every other contract in this file, and it is the
    NET — the negative mirror rows a bounce or a release writes are in the sum,
    so a bill that was paid and then re-opened reads as re-opened.

    **`None` IS NOT `Decimal("0")`, AND HERE THE DIFFERENCE IS A WARNING THAT
    DOES NOT APPEAR.** Zero means *nothing has been paid against this bill*;
    None means *nobody could ask*. A caller that read None as zero would tell a
    clerk correcting Ajinkya's already-paid bill that nothing had been paid
    against it — which is the exact silence CS-36 exists to break — so
    `build_impact` raises no warning on None rather than raising the opposite
    one. Same rule and same reason as `deposit_paid_for_account` above.
    """
    read = _resolve(ALLOCATED_MODULE, ALLOCATED_READ)
    if read is None:
        return None
    try:
        allocated = read(invoice_id)
    except _payment_refusals():  # pragma: no cover - the read raises no rule today
        return None
    return allocated if isinstance(allocated, Decimal) else None


def allocated_for_invoices(invoice_ids: Any) -> dict[str, Decimal] | None:
    """What payments has applied to EACH of many bills — or **None** if unasked.

    `CR-101-BRC03` §06, the step-1 scope table's PAID column, one page at a
    time. Keyed by the bill id as a STRING; a bill absent from the map has no
    allocation row against it, which over payments' append-only table means
    `0.00` has been paid and the caller may say so.

    **`None` IS NOT AN EMPTY MAP.** An empty map means *nothing has been paid
    against any of these bills*; None means *nobody could ask*. A caller that
    read None as empty would draw every bill in a bill run as `Unpaid`, with
    every check green — so the caller publishes `null` and a problem naming
    the seam instead (the same rule as `allocated_against_invoice` above, at
    page grain).
    """
    read = _resolve(ALLOCATED_MODULE, ALLOCATED_MANY_READ)
    if read is None:
        return None
    try:
        allocated = read(invoice_ids)
    except _payment_refusals():  # pragma: no cover - the read raises no rule today
        return None
    if not isinstance(allocated, dict):
        return None
    return {str(key): value for key, value in allocated.items() if isinstance(value, Decimal)}


#: DEF-BIL-10200 — what met each bill and when the money arrived (BR-BIL-071).
RECEIPTS_READ = "receipts_for_invoices"  # (invoice_ids) -> {str(id): [{amount, arrived_on, recorded_on}]}


def receipts_for_invoices(invoice_ids: Any) -> dict[str, list[dict[str, Any]]] | None:
    """🔒 `{invoice_id: [{amount, arrived_on, recorded_on}]}` — payments' own
    facts, asked BY NAME for the bill run's late fee — or **None** when
    payments publishes no such read. None is not an empty map: an empty map
    says nothing met these bills, None says nobody could ask, and a caller
    reading None as empty would charge a late fee on bills paid on time."""
    read = _resolve(ALLOCATED_MODULE, RECEIPTS_READ)
    if read is None:
        return None
    try:
        found = read(invoice_ids)
    except _payment_refusals():  # pragma: no cover - the read raises no rule today
        return None
    return found if isinstance(found, dict) else None


def allocated_total_for_invoices(invoice_ids: Any) -> Decimal | None:
    """Σ paid against ALL the bills a scope resolves to — or **None** if unasked.

    The second figure of the step-1 totals row (*"Six bills · $1,454.10 ·
    $904.50"*). One statement over the whole scope, never a sum of the page on
    screen (`NFR-3`). `None` is not `0.00` for exactly the reason
    `allocated_for_invoices` gives: a totals row reading `$0.00` paid across a
    run nobody could ask payments about is a false fact on an approval screen.
    """
    read = _resolve(ALLOCATED_MODULE, ALLOCATED_TOTAL_READ)
    if read is None:
        return None
    try:
        total = read(invoice_ids)
    except _payment_refusals():  # pragma: no cover - the read raises no rule today
        return None
    return total if isinstance(total, Decimal) else None


#: DEF-BIL-8651 — payments' own word for whether a payment's money has arrived.
PAYMENT_STATUS_READ = "payment_statuses_after_cutoff"  # (account_ids, period_end, bill_date) -> {account_id: [status]}
#: The one status that meets no bill: no clearing date, no allocation.
PAYMENT_NOT_ARRIVED = "processing"


def payment_statuses(
    account_ids: Any, *, period_end: Any, bill_date: Any
) -> dict[str, list[str]] | None:
    """`{account_id: [status, ...]}` of the payments posted after the cut-off —
    or **None** if nobody could ask (DEF-BIL-8651).

    None is not an empty map: a caller that read it as *every payment has
    arrived* would let *Apply to this bill* stand on money nobody checked."""
    read = _resolve(ALLOCATED_MODULE, PAYMENT_STATUS_READ)
    if read is None:
        return None
    try:
        statuses = read(account_ids, period_end=period_end, bill_date=bill_date)
    except _payment_refusals():  # pragma: no cover - the read raises no rule today
        return None
    if not isinstance(statuses, dict):
        return None
    return {str(k): [str(v) for v in vs] for k, vs in statuses.items()}


@dataclass(frozen=True)
class ReleaseOutcome:
    """What came off the bill being replaced (CR-059 CS-36, BR-PAY-1072).

    `released` is a POSITIVE magnitude — what stopped pointing at the original
    — and 0.00 is a real answer twice over: a bill nobody paid, and a replayed
    execution that finds the money already released. Both mean the same thing to
    the caller, which is *no allocation now points at this bill*.

    **THERE IS NO `None` HERE, UNLIKE EVERY READ ABOVE.** The absence rule on
    this seam exists because a caller must not read *"nobody could ask"* as
    *"the answer is zero"* — and on this call there is no third state to
    confuse, because an unreachable payments module REFUSES the restatement
    outright rather than returning an outcome (see `release_allocations`).
    """

    invoice_id: str
    released: Decimal
    currency: str | None = None
    rows: tuple[dict[str, Any], ...] = ()


def release_allocations(invoice: Any, *, reason: str, occurred_on: date | None = None, actor=None):
    """BR-PAY-1074 — take the payments off the bill BEFORE the rebill issues.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THE ORDER IS THE RULE, NOT THE IMPLEMENTATION (CR-059 CS-36).       ║
    ╚══════════════════════════════════════════════════════════════════════╝
    Called from `corrections.execute_restatement`, between the credit note and
    the rebill, inside that function's transaction. Released AFTER the rebill
    issues, the rebill draws down a credit balance that does not exist yet and
    the customer is invoiced for money they have already paid — which is the
    defect this exists to close, with one extra step. The payments service
    REFUSES to run outside a transaction so that half of the rule cannot be lost
    by a caller; the ORDER is kept by the one call site and is asserted by test.

    **AN UNREACHABLE SEAM REFUSES THE CORRECTION, AND THAT IS THE OPPOSITE
    POSTURE TO `apply_credit_at_issue` ABOVE — DELIBERATELY.** There, an
    unpublished payments module reports and the bill still issues, because a
    deployment that cannot reach payments must still be able to bill. Here,
    proceeding would credit the original, issue a replacement, and leave the
    customer's money pointing at a bill nothing reads: outstanding 80.00,
    credit 0.00, six days late on arrival, and the books out by 100.00 with
    nothing reporting it. **A silent wrong number reaching a customer is worse
    than a loud refusal**, and hard-won law 3 says the unsafe option is the one
    you have to type. Nothing is written; the bill stays correctable.

    A payments RULE refusal (its transaction guard, or two currencies on one
    bill) is translated into `BillingRuleError` for DEF-047's reason — a refusal
    in the OWNER's vocabulary sails straight through `issue_run`'s
    `except BillingRuleError` and takes the other 499 bills with it.
    """
    invoice_id = str(getattr(invoice, "pk", invoice))
    release = _resolve(RELEASE_MODULE, RELEASE_CALL)
    if release is None:
        raise BillingRuleError(
            f"the payments module does not publish {RELEASE_CALL} on this deployment, so "
            f"the money already paid against bill {getattr(invoice, 'invoice_no', invoice_id)} "
            "cannot be released from it (BR-PAY-1072). The correction is REFUSED and "
            "nothing was written: crediting this bill and issuing a replacement while the "
            "payment still points at the original would invoice a customer for money they "
            "have already paid, and the books would disagree with the account screen by "
            "exactly that amount with nothing reporting it.",
            br_ref="BR-PAY-1072",
        )
    try:
        result = release(
            invoice_id=getattr(invoice, "pk", invoice),
            reason=reason,
            occurred_on=occurred_on,
            actor=actor,
        )
    except _payment_refusals() as refusal:
        raise BillingRuleError(
            f"the payments module refused to release the allocations against bill "
            f"{getattr(invoice, 'invoice_no', invoice_id)}: {refusal}. The correction is "
            "refused and this bill leaves no artifacts (BR-BIL-047).",
            br_ref="BR-PAY-1072",
        ) from refusal
    released = getattr(result, "released", None)
    if not isinstance(released, Decimal):
        raise BillingRuleError(
            f"the payments module answered the release of bill "
            f"{getattr(invoice, 'invoice_no', invoice_id)} with {released!r}, which is not a "
            "Decimal. Money is never a float (CLAUDE.md rule 2) and an unreadable answer is "
            "not evidence that the money came off, so the correction is refused.",
            br_ref="BR-PAY-1072",
        )
    return ReleaseOutcome(
        invoice_id=invoice_id,
        released=released,
        currency=getattr(result, "currency", None),
        rows=tuple(
            {
                "payment_id": row.payment_id,
                "payment_no": row.payment_no,
                "amount": str(row.amount),
                "allocation_id": row.allocation_id,
            }
            for row in getattr(result, "rows", ()) or ()
        ),
    )


@dataclass(frozen=True)
class PriorPosition:
    """BR-BIL-035's two arrears figures for one account, or why they are absent.

    `previous_balance` is the Σ of what the account's still-OPEN earlier bills
    ASKED for **plus its MIGRATED opening balance** (BR-BIL-160, PO 2026-08-27),
    and `payments_credits` is the Σ of what has already been allocated against
    those same bills **plus the part of that opening balance the account's
    credit position shows as settled**.

    ⚠ The first line read *"at their own issued totals"* until 2026-09-01 and
    that was exact only while every bill's ask WAS its total. A budget-billing
    bill asks for its LEVEL (BR-BIL-072, *"Level is due"*), so on ❄️ WE-8 the two
    are 292.87 and 242.00 — see the subtraction in `prior_position_for_account`
    for what printing the total here did to the middle line. The two are returned
    together and are never mixed with a figure from a different set, because
    the whole point of the pair is that it FOOTS:

        previous_balance − payments_credits == open_balance

    and therefore `open_balance + this bill's current charges` is the total due
    however the split is drawn. A screen or a page can print all three and the
    arithmetic on the paper will add up.

    **BOTH ARE `None` WHEN THE SEAM COULD NOT BE REACHED, AND THAT IS NOT ZERO.**
    Zero means *this customer owes nothing from before*; None means *nobody
    could ask*. A bill that printed "Previous balance 0.00" on an unreachable
    seam would tell a customer in arrears that they are square — see
    `deposit_paid_for_account` above for the same rule and the same reason.
    """

    account_id: str
    previous_balance: Decimal | None = None
    payments_credits: Decimal | None = None
    open_balance: Decimal | None = None
    bills: int = 0
    #: BR-BIL-160 (PO 2026-08-27, OQ-530) — the MIGRATED half of the two figures
    #: above, carried separately so a reviewer can see how much of a previous
    #: balance came from a bill and how much the account arrived with. Both are
    #: already INSIDE `previous_balance` / `payments_credits`; they are not a
    #: fifth and sixth thing to add on. `opening_buckets` is how many BR-CUS-048
    #: bands stood behind the figure — 0 on every account that was created in
    #: this product rather than migrated into it, which is nearly all of them.
    opening_balance: Decimal | None = None
    opening_settled: Decimal | None = None
    opening_buckets: int = 0
    problems: tuple[dict[str, Any], ...] = ()


def credit_position_for_account(account_id: Any) -> Decimal | None:
    """BR-BIL-160 — what the utility holds ON ACCOUNT, or **None** if unasked.

    Payments' own signed figure (`account_credit_position`: Σ payments − Σ
    allocations − Σ refunds), resolved BY NAME like everything else here. It is
    read for exactly one purpose: an account that arrived with a MIGRATED
    opening balance has no invoice for a payment to meet, so money paid against
    that balance becomes an unapplied credit and is the only record this
    product keeps that it was paid at all (OQ-570).

    **A NEGATIVE POSITION IS A DEBT AND IS NOT FLOORED HERE** (BR-PAY-041, PO
    2026-08-11 *"Yes, it's a real debt"*). It is returned as it is; the caller
    is what decides that a debt settles nothing.

    **`None` IS NOT `Decimal("0")`.** Zero means *the utility holds nothing for
    this customer*; None means *nobody could ask*, and a caller that read None
    as zero would state a settlement it had no evidence for.
    """
    read = _resolve(CREDIT_POSITION_MODULE, CREDIT_POSITION_READ)
    if read is None:
        return None
    try:
        balance = read(account_id)
    except _payment_refusals():  # pragma: no cover — the read raises no rule today
        return None
    return balance if isinstance(balance, Decimal) else None


#: 🔒 PO 2026-10-01 — the two payments reads the balance forward asks by name
#: (`apps/payments/billing_seam.py`): the money received in a window (OQ-217
#: closed, BR-BIL-1065) and an active plan's instalments split for one bill
#: (BR-BIL-1061).
RECEIVED_READ = "payments_received_for_account"
PLAN_SPLIT_READ = "plan_instalments_for_bill"


def payments_received_for_account(
    account_id: Any, *, after: Any = None, through_date: date | None = None
) -> Decimal | None:
    """🔒 HUMAN-REVIEW-PENDING · OQ-217 CLOSED (PO 2026-10-01, option A) —
    everything received on the account after `after` (and on or before
    `through_date`), less refunds: payments' own figure, asked BY NAME.
    **None, never zero, when payments does not publish it** — the caller then
    keeps the old open-bills window and says so on the bill."""
    read = _resolve(PRIOR_POSITION_MODULE, RECEIVED_READ)
    if read is None:
        return None
    try:
        value = read(str(account_id), after=after, through_date=through_date)
    except _payment_refusals():  # pragma: no cover — the read raises no rule today
        return None
    return value if isinstance(value, Decimal) else None


#: DEF-BIL-8682 — the two batched forms Sign off reads for a whole run.
CREDIT_POSITIONS_READ = "credit_positions_for_accounts"
RECEIVED_BY_TYPE_READ = "payments_received_by_type_for_accounts"
#: DEF-BIL-8696 / DEF-BIL-8720 — the open bills and an active plan's split, for
#: a whole run, so Sign off asks payments nothing per account.
OPEN_POSITIONS_READ = "open_invoices_for_accounts"
PLAN_SPLITS_READ = "plan_instalments_for_accounts"


def _ids_or_subquery(account_ids: Any) -> Any:
    """A queryset of account ids is handed over AS a queryset, so payments reads
    it as a subquery (`DEF-BIL-8696`: 40,000 bound ids cost ~7 s of Python per
    read); anything else as a list of text ids, as before."""
    if hasattr(account_ids, "query"):
        return account_ids
    return [str(account_id) for account_id in account_ids]


def credit_positions_for_accounts(account_ids: Any) -> dict[str, Decimal] | None:
    """`credit_position_for_account` for a whole run, asked BY NAME in one
    batch (NFR-3). None — never zeros — when payments does not publish it."""
    read = _resolve(PRIOR_POSITION_MODULE, CREDIT_POSITIONS_READ)
    if read is None:
        return None
    try:
        return read(_ids_or_subquery(account_ids))
    except _payment_refusals():  # pragma: no cover — the read raises no rule today
        return None


def payments_received_by_type_for_accounts(
    windows: dict[str, tuple[Any, date | None]],
    *,
    scope: Any = None,
) -> dict[str, dict[str, Any]] | None:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-8682` — `payments_received_for_account`
    for a whole run in one batch, PARTED by payments' own `type` column into
    payments and credits (`received` is their sum and is the same figure the
    per-account read returns). Asked BY NAME; None when unpublished. `scope`,
    a queryset of the same accounts' ids, is read as a subquery
    (`DEF-BIL-8696`)."""
    read = _resolve(PRIOR_POSITION_MODULE, RECEIVED_BY_TYPE_READ)
    if read is None:
        return None
    try:
        windows = {str(key): value for key, value in windows.items()}
        return read(windows) if scope is None else read(windows, scope=scope)
    except _payment_refusals():  # pragma: no cover — the read raises no rule today
        return None


def open_positions_for_accounts(account_ids: Any) -> dict[str, Any] | None:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-8696` — what `prior_position_for_account`
    asks payments per account (`open_invoices_for_account`), for a whole run in
    one batch: `{account_id: OpenPosition}`. Handed back into
    `prior_position_for_account(open_position=…)`, which keeps the one
    statement of the arithmetic. None when payments does not publish it — the
    caller then asks per account, exactly as before."""
    read = _resolve(PRIOR_POSITION_MODULE, OPEN_POSITIONS_READ)
    if read is None:
        return None
    try:
        return read(_ids_or_subquery(account_ids))
    except _payment_refusals():  # pragma: no cover — the read raises no rule today
        return None


def plan_instalments_for_accounts(
    account_ids: Any, *, due_by: date | None
) -> dict[str, dict[str, Any]] | None:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-8720` — `plan_instalments_for_bill` for
    a whole run: `{account_id: split}`, no key for an account with no ACTIVE
    plan. None when payments does not publish it."""
    read = _resolve(PRIOR_POSITION_MODULE, PLAN_SPLITS_READ)
    if read is None:
        return None
    try:
        return read(_ids_or_subquery(account_ids), due_by=due_by)
    except _payment_refusals():  # pragma: no cover — the read raises no rule today
        return None


ACTIVITY_KEY_READ = "activity_key_for_accounts"


def activity_key_for_accounts(account_ids: Any, *, invoice_ids: Any = None) -> str | None:
    """`DEF-BIL-8696` — payments' key over every row these accounts' money
    position is read from (`core.row_versions`), asked BY NAME. Sign off saves
    its whole-run summary under it and rebuilds when it moves. None — read as
    *cannot tell*, so the summary is built live — when payments does not
    publish it or the database cannot say."""
    read = _resolve(PRIOR_POSITION_MODULE, ACTIVITY_KEY_READ)
    if read is None:
        return None
    return read(_ids_or_subquery(account_ids), invoice_ids=invoice_ids)


def plan_instalments_for_bill(account_id: Any, *, due_by: date | None) -> dict[str, Any] | None:
    """🔒 HUMAN-REVIEW-PENDING · BR-BIL-1061 (PO 2026-10-01) — an ACTIVE plan's
    unpaid instalments split into *due now* (on or before `due_by`) and *not yet
    due*: payments' figures, asked BY NAME. None when there is no active plan or
    payments does not publish the read — the bill then asks its whole total due,
    exactly as before the ruling."""
    read = _resolve(PRIOR_POSITION_MODULE, PLAN_SPLIT_READ)
    if read is None:
        return None
    try:
        return read(str(account_id), due_by=due_by)
    except _payment_refusals():  # pragma: no cover — the read raises no rule today
        return None


#: `prior_position_for_account`'s "not handed in — ask" (None is a real answer).
_ASK = object()


def prior_position_for_account(
    account_id: Any,
    *,
    totals_by_invoice_id: Any,
    opening: Any,
    open_position: Any = _ASK,
    credit: Any = _ASK,
) -> PriorPosition:
    """BR-BIL-035 — what this account still owed on EARLIER bills, and what has
    been paid against them. The arrears half of the balance-forward section.

    ⚠ **AMENDED 2026-08-27 — BR-BIL-160, THE PO'S OWN RULING (OQ-530 CLOSED).**
    Verbatim: *"so when we run first bill; we have to take opening balance into
    account. you will generate first bill and against previous balance you will
    mention the opening balance."* `opening` is
    `apps/billing/customers_seam.OpeningPosition` — the account's MIGRATED
    receivable — handed in by the caller for the same reason
    `totals_by_invoice_id` is: the figure belongs to a third module, it is asked
    for BY NAME, and nothing here computes it. It is a REQUIRED argument and
    deliberately has no default — a default would let the wiring go missing and
    every bill would quietly go back to reading open invoices alone, which is
    hard-won law 2 ("built is not wired") in the shape that costs money.

    ⚠ **BOTH MIDDLE OPERANDS MOVE TOGETHER, AND THAT IS WHAT THIS AMENDMENT IS
    ACTUALLY FOR.** The three figures below are derived from ONE set — the open
    invoices — so an opening balance joining `previous_balance` alone would
    appear on bill 1 (correct), the customer would pay it, the payment would
    allocate against **no invoice in that set**, and **bill 2 would ask for it
    again, and every bill after it**. `allocations` is `payment × INVOICE`
    (B2 §2) and nothing ever reduces an `account_opening_buckets` row, so the
    only record that a migrated balance was paid is the account's own CREDIT
    position — and that is what joins the second operand:

        opening settled = min(credit position, opening balance)

    **The cap is what makes this change invisible to every account that was not
    migrated.** An account with no buckets has `opening balance = 0.00`, so
    `settled = 0.00` and all four printed figures are byte-identical to what
    they were before this rule — which is why ❄️ WE-1's `45.00 − 0.00 + 247.87
    = 292.87` and ❄️ PE-4's carried **57.13** are untouched. Credit ABOVE the
    opening position is the ordinary carried credit BR-PAY-010 already applies
    to the current bill at issue, and it is not a settlement of anything
    migrated.

    **Whether settlement should be a ROW rather than an inference is OQ-570,
    OPEN.** It is registered rather than chosen, and it is stated on the block
    so a reader of an immutable bill can tell how its figure was derived.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  WHY BILLING ASKS INSTEAD OF COMPUTING (B1, and it is not a style)   ║
    ╚══════════════════════════════════════════════════════════════════════╝
    Billing owns `invoices` and knows what was BILLED. It does not own
    `allocations` and cannot know what is OPEN — that is payments' row and
    payments' arithmetic (`apps/payments/billing_seam.py` states the split in as
    many words). So the open set comes from payments' published read, resolved
    BY NAME at call time, and the GROSS totals come from billing's own immutable
    invoice column, handed in by the caller. Neither module computes the other's
    half and no model crosses the boundary.

    **THE CURRENT BILL IS NOT IN THE SET BY CONSTRUCTION.** Payments' read
    covers `issued` and `paid` bills only; the bill being stamped is still a
    DRAFT at the moment this is called, so it cannot count itself. That is
    stronger than an id filter and it cannot rot: it stays true if the caller
    forgets to pass an exclusion.

    🔒 HUMAN-REVIEW-PENDING · **`DEF-BIL-8696` — `open_position` and `credit`
    MAY BE HANDED IN.** Sign off asks this for every bill of a run, and asking
    payments per account was 120,000 statements at 40,000 bills. A caller that
    read payments' open position (`open_positions_for_accounts`) and credit
    position (`credit_positions_for_accounts`) for the whole run in one batch
    hands each account's answer in, and NOTHING BELOW CHANGES: the same
    arithmetic runs over the same figures. Absent, each is asked here exactly
    as before — the issue path still asks per bill.

    ⚠ **SUPERSEDED FOR THE BILL 2026-10-01 — `OQ-217` CLOSED (PO, option A,
    BR-BIL-1065).** The bill now reads the WHOLE ACCOUNT since the last bill
    (`open_balance.whole_account`), built ON this function's open set. What
    follows is this function's own window, still true of what it returns:

    **THE WINDOW IS THE OPEN BILLS — OQ-217.**
    BR-BIL-035 signs the ARITHMETIC (*"previous balance − payments received +
    this period = total due"*) and names neither operand's window. This reads
    them over the bills that are still open, which reproduces the frozen WE-1
    figure exactly — one unpaid **45.00** prior bill with nothing paid against
    it gives **45.00 − 0.00 + 247.87 = 292.87**. The consequence a reader must
    know: a prior bill settled IN FULL leaves the set with its payment, so a
    customer who paid last month's bill sees `0.00 − 0.00` rather than
    `100.00 − 100.00`. The TOTAL DUE is identical either way — that is what the
    footing guarantee buys — so the question is what the two middle lines say,
    and it is the PO's. Registered rather than chosen.
    """
    account_key = str(account_id)
    read = (
        _resolve(PRIOR_POSITION_MODULE, PRIOR_POSITION_READ)
        if open_position is _ASK
        else (lambda _key: open_position)
    )
    if read is None:
        return PriorPosition(
            account_id=account_key,
            problems=(
                _unwired(
                    PRIOR_POSITION_MODULE,
                    PRIOR_POSITION_READ,
                    "the arrears half of BR-BIL-035's balance-forward section could not be "
                    "read, so previous balance, payments & credits and TOTAL DUE are absent "
                    "on this bill rather than printed as zero. A zero would tell a customer "
                    "in arrears that they are square.",
                ),
            ),
        )
    try:
        position = read(account_key)
    except _payment_refusals() as refusal:  # pragma: no cover — the read raises none today
        return PriorPosition(
            account_id=account_key,
            problems=(
                {
                    "code": "prior_position_refused_by_payments",
                    "br_ref": "BR-BIL-035",
                    "detail": f"payments refused the open-bill read for this account: "
                    f"{refusal}. Nothing was assumed; the balance-forward section is absent.",
                },
            ),
        )

    gross = Decimal("0")
    allocated = Decimal("0")
    open_balance = Decimal("0")
    counted = 0
    unknown: list[str] = []
    for open_invoice in getattr(position, "invoices", ()) or ():
        invoice_id = getattr(open_invoice, "invoice_id", None)
        balance = getattr(open_invoice, "balance", None)
        total = totals_by_invoice_id.get(str(invoice_id)) if invoice_id is not None else None
        if not isinstance(balance, Decimal) or not isinstance(total, Decimal):
            # An open bill whose own total billing cannot match is NOT folded in
            # at its balance: the pair would stop footing and the page would
            # print an arithmetic that does not add up. Named instead.
            unknown.append(str(getattr(open_invoice, "number", invoice_id)))
            continue
        # ⛔ **PREVIOUS BALANCE IS WHAT THE EARLIER BILLS ASKED FOR, NOT WHAT
        # THEY TOTALLED — DEF-2416 / BR-BIL-072, corrected 2026-09-01.** These
        # two summed `total` and derived the middle line by subtraction
        # (`allocated += total - balance`), which was exact while every bill's
        # ask WAS its total. It stopped being exact the hour payments began
        # measuring a bill at what it asks (the PO's *"Level is due"*): a
        # budget bill nobody had paid a cent against would have printed
        # **"Previous balance 292.87 · Payments & credits 50.87 · Open balance
        # 242.00"** — three lines that FOOT and one of which is a lie about a
        # payment the customer never made. Both operands are now taken from the
        # seam's own carried facts, so the section foots BY CONSTRUCTION
        # (`amount_due − allocated == balance`, per bill) and every line is a
        # figure somebody can point at.
        #
        # ❄️ NOTHING FROZEN MOVES. `amount_due` equals `total` for every bill
        # that is not budget-billing, so WE-1's `45.00 − 0.00 + 247.87 = 292.87`
        # and PE-4's carried 57.13 are byte-identical. `total` is still read and
        # still required above: matching each open bill to its own immutable
        # billed total is the guard that keeps a bill billing cannot identify
        # out of the sum entirely.
        asked = getattr(open_invoice, "amount_due", None)
        paid = getattr(open_invoice, "allocated", None)
        if not isinstance(asked, Decimal) or not isinstance(paid, Decimal):
            # The seam did not state them — an older `OpenInvoice`. Fall back to
            # the original subtraction rather than refusing: it is exact for
            # every bill that is not budget-billing, which is what a seam
            # predating those fields can only have been serving.
            asked, paid = total, total - balance
        gross += asked
        allocated += paid
        open_balance += balance
        counted += 1

    problems = [dict(entry) for entry in getattr(position, "problems", ()) or ()]
    if unknown:
        return PriorPosition(
            account_id=account_key,
            bills=counted,
            problems=tuple(
                problems
                + [
                    {
                        "code": "prior_open_bill_not_matched_to_its_billed_total",
                        "br_ref": "BR-BIL-035",
                        "detail": f"bill(s) {unknown} are open for this account and billing "
                        "could not match them to their own issued totals, so the previous "
                        "balance and the payments against it would not foot. The whole "
                        "balance-forward section is withheld rather than printed short — a "
                        "summary box whose three lines do not add up to its fourth is worse "
                        "than one that says the figure is absent.",
                    }
                ]
            ),
        )
    # ── BR-BIL-160 — THE MIGRATED HALF (PO 2026-08-27, OQ-530) ──────────────
    opening_gross = getattr(opening, "amount", None)
    if opening_gross is None:
        # The opening seam could not be asked. The WHOLE section is withheld,
        # not just the migrated part: an account that arrived owing money would
        # otherwise be shown a previous balance short by its whole migration,
        # which is the defect this rule closes wearing a different hat.
        return PriorPosition(
            account_id=account_key,
            bills=counted,
            problems=tuple(problems + [dict(entry) for entry in getattr(opening, "problems", ())]),
        )
    if opening_gross == ZERO:
        # Not migrated — the ordinary account, and by far the common case. No
        # credit read, no extra problem entry, and all four figures identical
        # to what they were before this rule existed.
        return PriorPosition(
            account_id=account_key,
            previous_balance=gross,
            payments_credits=allocated,
            open_balance=open_balance,
            bills=counted,
            opening_balance=ZERO,
            opening_settled=ZERO,
            problems=tuple(problems),
        )

    if credit is _ASK:
        credit = credit_position_for_account(account_id)
    if credit is None:
        # Nobody could ask what has been PAID against the migration. Stating the
        # gross alone would ask a customer who has already paid it for the money
        # a second time, on a page that is immutable the moment it is written —
        # so nothing is stated at all.
        return PriorPosition(
            account_id=account_key,
            bills=counted,
            problems=tuple(
                problems
                + [
                    {
                        "code": "payments_account_credit_position_not_published",
                        "br_ref": "BR-BIL-160",
                        "detail": f"this account carries a migrated opening balance of "
                        f"{opening_gross}, and apps.{PAYMENTS_MODULE}."
                        f"{CREDIT_POSITION_MODULE}.{CREDIT_POSITION_READ} is not published, so "
                        "what has already been PAID against it could not be read. The whole "
                        "balance-forward section is withheld rather than printed at the gross: "
                        "a customer who has settled their migrated arrears would be asked for "
                        "them again (OQ-530, PO 2026-08-27).",
                    }
                ]
            ),
        )

    # A NEGATIVE credit is a DEBT (BR-PAY-041) and settles nothing; it is not
    # floored into the figure either, it simply does not reduce the opening.
    settled = ZERO if credit <= ZERO else (credit if credit < opening_gross else opening_gross)
    return PriorPosition(
        account_id=account_key,
        previous_balance=gross + opening_gross,
        payments_credits=allocated + settled,
        open_balance=open_balance + (opening_gross - settled),
        bills=counted,
        opening_balance=opening_gross,
        opening_settled=settled,
        opening_buckets=int(getattr(opening, "buckets", 0) or 0),
        problems=tuple(
            problems
            + [dict(entry) for entry in getattr(opening, "problems", ())]
            + [
                {
                    "code": "opening_balance_settlement_is_inferred_not_recorded",
                    "br_ref": "BR-BIL-160",
                    "detail": f"this bill's previous balance includes a MIGRATED opening "
                    f"balance of {opening_gross} across "
                    f"{int(getattr(opening, 'buckets', 0) or 0)} aged bucket(s) (BR-CUS-048), "
                    f"and {settled} of it is shown as paid. Nothing in this product ALLOCATES "
                    "a payment against an opening bucket — `allocations` names an INVOICE "
                    "(B2 §2) and the buckets are append-only — so the settled figure is "
                    "inferred from the account's own credit position rather than recorded as "
                    "a row. Registered as OQ-570 and not chosen: the arithmetic foots at "
                    "every cycle, but a clerk cannot see WHICH money cleared the migration.",
                }
            ]
        ),
    )


def extend_plans_for_skips(*, bill_run: Any, account_id: str, actor: Any = None) -> dict[str, Any]:
    """🔒 PO ruling 2026-09-30 (fixed-charge case 5) — a clerk chose *"Skip this
    month"* for a payment-plan instalment in this run, so the PAYMENTS module
    extends the plan by one month (`apps.payments.plans.extend_plan_one_month`).
    Billing never writes a plan row; it names the instalment the run's saved
    Check found (`seq`, `due_on` on the `plan_instalment_due` finding) and asks.

    Called at ISSUE, never on a draft — a draft can be re-priced and re-decided,
    and an extension is a change to the customer's agreement. Idempotent: the
    payments service acts only while that instalment is still due on that day.
    Answers `{"extended", "reason", "ends_on"}`; nothing here raises for a
    missing fact, because a bill must not fail for want of a plan to extend.
    """
    from apps.billing import check_models, decisions

    skipped = [
        row
        for row in decisions.current_decisions(bill_run)
        if str(row.account_id) == str(account_id)
        and row.case == "plan_instalment_due"
        and row.choice == decisions.CHOICE_SKIP
    ]
    if not skipped:
        return {"extended": False, "reason": "no_skip", "ends_on": None}
    fact = (
        check_models.BillRunFinding.objects.filter(
            tenant_id=getattr(bill_run, "tenant_id", None),
            bill_run=bill_run,
            account_id=account_id,
            code="plan_instalment_due",
        )
        .order_by("-checked_at")
        .first()
    )
    params = dict(getattr(fact, "params", None) or {})
    if params.get("seq") is None or not params.get("due_on"):
        return {"extended": False, "reason": "no_saved_fact", "ends_on": None}
    extend = _resolve("plans", "extend_plan_one_month")
    if extend is None:
        return {"extended": False, "reason": "payments_unpublished", "ends_on": None}
    return extend(
        account_id=account_id,
        seq=int(params["seq"]),
        due_on=date.fromisoformat(str(params["due_on"])),
        actor=actor if actor is not None else skipped[0].decided_by_id,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-005@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md ·
#         08-payments/02-business-rules.md, the owner's half of this contract)
# generated: 2026-08-15 by Eng-Lead (payments-wiring lane — the three call sites
#         the payments lane published and could not make itself; hard-won law 2)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — a seam) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_bil_005_payments_wiring.py · three
#         mutations proved RED (the credit call removed, the intent call
#         removed, and `deposit_paid_for_account` returning 0 instead of None)
# exceptions: (1) [CLOSED 2026-09-01, DEF-2791] "NO GLOB IN human_owned.txt
#         MATCHES THIS FILE, so G7 does not read its markers" was true when
#         written and is false now: the glob is there and G7 checks this file.
#         Kept as history, per the module docstring's dated correction.
#         (2) An UNPUBLISHED seam is reported and the bill still issues
#         (BR-BIL-055); a payments RULE refusal on a bill being credited is
#         translated to `BillingRuleError` and stops THAT bill only (DEF-047).
#         (3) `deposit_paid_for_account` answers None rather than zero when it
#         cannot ask, because zero is a money claim.
# revised: 2026-08-27 (OQ-530 opening-balance lane) — **BR-BIL-160 BUILT.**
#         `prior_position_for_account` gains a REQUIRED `opening=` argument (billing's
#         `customers_seam` answers it) and `credit_position_for_account` is new. The
#         migrated opening balance joins `previous_balance` and `min(credit, opening)`
#         joins `payments_credits`, so both middle operands move together and a paid
#         migration CLEARS instead of being asked for again. RED-PROVED: with the
#         opening joining `previous_balance` alone, bill 2 asks `Decimal('367.880000')`
#         where `Decimal('100.58')` belongs; with the cap removed, ❄️ PE-4 moves
#         (`assert Decimal('57.130000') == Decimal('0')`). Settlement-by-inference is
#         **OQ-570, OPEN** — nothing allocates against an opening bucket.

# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
