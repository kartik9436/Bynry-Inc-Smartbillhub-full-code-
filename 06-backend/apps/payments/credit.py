# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-007 (overpayment / carried credit: auto-apply, visible,
#           refundable) · US-PAY-002 (the deposit position this file publishes
#           for billing to draw on)   Screens: S21 · S33 · S58
# Rules:    BR-PAY-010 (overpayment → account credit; auto-applies to the next
#           bill in the ratified order) · BR-PAY-012 (prepay and any unapplied
#           purpose-money sit as the same account credit; a DEPOSIT does not) ·
#           BR-PAY-014 (refunds only from a real credit; ⚠ as amended
#           2026-08-12 — a credit built from SEVERAL overpayments must be
#           refundable, and a customer owing on another account is OFFSET
#           FIRST) · BR-PAY-041 (an account credit may go NEGATIVE and that is
#           a real debt) · BR-CUS-061 (opening credit balances import as the
#           same carried credit) · BR-PAY-002 (append-only — an application is
#           a new `allocations` row, never an edit) · CLAUDE.md rule 1 · rule 2
#           · rule 4 · rule 7
# Tests:    06-backend/tests/test_us_pay_007_credit.py
# Impacts:  apps/payments/selectors.account_credit_position (the signed figure
#           this module spends) · apps/payments/refunds.py (the payout route) ·
#           apps/billing (US-BIL-005 issue — the CALLER this module is waiting
#           for; nothing in billing calls `apply_credit_at_issue` yet) ·
#           apps/payments/purposes.py (a deposit is excluded from credit)
# ───────────────────────────────────────────────────────
"""The carried credit: what it is, where it goes, and what it may not do yet.

US-PAY-007's three verbs, and this file has one function per verb:

    VISIBLE      `credit_position` — the account's signed balance plus the rows
                 behind it, so S21/S33 can show "where did this come from?"
                 rather than one number nobody can explain.
    AUTO-APPLY   `apply_credit_at_issue` — writes `allocations` rows against a
                 newly issued bill, in the ratified order, up to what the bill
                 owes and never a cent beyond the credit.
    REFUNDABLE   `refundable_position` — what could lawfully be paid out today,
                 after BR-PAY-014's offset-first test. The payout itself is
                 `refunds.py`'s and stays there.

════════════════════════════════════════════════════════════════════════════
THE CREDIT MAY BE NEGATIVE, AND NOTHING HERE FLOORS IT
════════════════════════════════════════════════════════════════════════════
PO ruling 2026-08-11 (OQ-132), verbatim: **"Yes, it's a real debt"**. On J15's
frozen chain a $350.00 cheque clears against $292.87 leaving credit **57.13**,
the change is refunded taking it to **0.00**, and the cheque then bounces —
leaving **−57.13**, which the utility pursues. `selectors.account_credit_position`
returns a SIGNED Decimal for that reason and this module never calls `max(0, …)`
on it. `apply_credit_at_issue` applies NOTHING when the position is negative:
there is no credit, there is a debt, and "applying" it would reduce a bill by
money the customer owes.

════════════════════════════════════════════════════════════════════════════
IDEMPOTENCE IS ARITHMETIC HERE, NOT A LOCK (US-PAY-007 TC-5)
════════════════════════════════════════════════════════════════════════════
TC-5 is a bill issue RETRIED after a crash, and it requires that *"the credit
never over-applies beyond its balance"*. The guard is not a key and does not
need to be: every call recomputes BOTH sides from the rows — what the invoice
still owes (`total − Σ allocations`) and what the account still holds — and
applies the smaller. A second call therefore finds the invoice already met and
applies **0.00**, and a partial first call applies only the residual. Two
concurrent calls are serialised by `select_for_update` on the source payments.

The alternative — an "applied at issue" flag — would be a second copy of a fact
the `allocations` rows already state, free to disagree with them (hard-won law
5 in service form).

════════════════════════════════════════════════════════════════════════════
WHAT THIS FILE CANNOT DO, AND WHY EACH IS SOMEBODY ELSE'S
════════════════════════════════════════════════════════════════════════════
  * **NOTHING CALLS `apply_credit_at_issue`.** BR-PAY-010's *"auto-applies to
    the account's next issued bill"* needs the ISSUE path to call it, that path
    is `apps/billing/issue.py`, and `apps/billing` belongs to another lane this
    session. The function is published, tenant-scoped and tested; the caller is
    one line in billing and is REPORTED, never implied (hard-won law 2).
  * **A CREDIT BUILT FROM SEVERAL PAYMENTS CANNOT BE REFUNDED.** The PO closed
    OQ-167 on 2026-08-12 — *"user can do a refund or issue a credit - it will be
    manula decision"* — on the worked figure **$40.00 (June) + $17.13 (July) =
    $57.13**. The rule is RULED; the SCHEMA cannot express it: B2 §2 types
    `refunds.payment_id uuid NOT NULL`, so a refund names exactly ONE payment
    and there is no account column to name instead. `refund_from_credit_balance`
    refuses by name, citing **OQ-195**, which asks the contracts lane the
    question this lane may not answer alone: making a column of a SIGNED schema
    nullable and adding another is a B2 change, not a payments change. The
    single-source case that PE-9 freezes still works and is untouched.
  * **THE OFFSET IS NOT APPLIED HERE.** *"offset first"* (OQ-135) is served by
    `refunds.offset_before_refund`, which computes both figures and moves no
    money — the transfer between two accounts is one reviewed writer's
    (`apps/billing/final_bill.py`), never two.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Sum

from core import audit as core_audit
from core import tenancy as core_tenancy

from apps.payments import balance_rule, models, selectors
from apps.payments.exceptions import PaymentRuleError

ZERO = Decimal("0")

#: hard rule 7 — every money action writes `audit_log`.
AUDIT_CREDIT_APPLIED = "credit.applied"

#: US-PAY-007 §5 / field-map §2. Carried on the result rather than stated in a
#: docstring, because a caller must not have to infer an absence.
CREDIT_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "credit_auto_application_has_no_caller",
        "br_ref": "BR-PAY-010",
        "detail": "BR-PAY-010 auto-applies a carried credit to the account's NEXT ISSUED BILL. "
        "This module publishes `apply_credit_at_issue` and nothing calls it: the issue path is "
        "`apps/billing/issue.py` and belongs to another module. Until billing calls it, a credit "
        "is visible and refundable but does NOT settle the next bill by itself.",
    },
)


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


@dataclass(frozen=True)
class CreditSource:
    """One payment still holding unapplied money, and how much of it.

    `unapplied` is the payment's own amount less the allocations written against
    it — never a share of some pooled figure. That is what makes the position
    explainable on screen: US-PAY-007 TC-4b's $57.13 renders as June's $40.00
    and July's $17.13, which is exactly the pair the PO's ruling names.
    """

    payment_id: str
    payment_no: str | None
    posted_at: Any
    amount: Decimal
    unapplied: Decimal
    purpose: str


@dataclass(frozen=True)
class CreditPosition:
    """What the utility holds on account — signed, with its sources."""

    balance: Decimal
    sources: tuple[CreditSource, ...]
    problems: tuple[dict[str, Any], ...] = CREDIT_UNAVAILABLE

    @property
    def is_debt(self) -> bool:
        """BR-PAY-041 — below zero the customer OWES this, and screens must age
        it as a debt rather than render 0.00."""
        return self.balance < ZERO


@dataclass(frozen=True)
class CreditApplication:
    """What one bill issue drew down (US-PAY-007 TC-2/TC-3)."""

    invoice_id: str
    applied: Decimal
    remaining_credit: Decimal
    invoice_balance_after: Decimal
    rows: tuple[dict[str, Any], ...] = ()


def _unapplied_by_payment(account_id: Any, *, lock: bool = False):
    """Every counted payment of this account that still holds money — posted,
    cleared or a reversing row (`balance_rule`, CR-186-BRC10; never cancelled,
    failed or processing).

    Deposit-purpose payments are EXCLUDED, and that exclusion is the rule rather
    than an optimisation: US-PAY-002 TC-1 holds a deposit against the deposit
    position and says *"account credit NOT created"*. A $150.00 deposit that
    read as $150.00 of credit would auto-apply to the next bill below, and the
    utility would spend money it is holding for the customer.

    Reversing rows (negative amounts) are included exactly as they are in
    `selectors.account_credit_position`: a bounce nets itself out, and that is
    how the position reaches BR-PAY-041's −57.13.
    """
    tenant_id = _tenant_id()
    rows = (
        models.Payment.objects.filter(tenant_id=tenant_id, account_id=account_id)
        .filter(status__in=balance_rule.BALANCE_COUNTED_PAYMENT_STATUSES)  # CR-186-BRC10
        .exclude(purpose=models.PURPOSE_DEPOSIT)
        .order_by("posted_at", "created_at", "id")
    )
    if lock:
        rows = rows.select_for_update()
    return rows


def _applied_of(payment: models.Payment) -> Decimal:
    total = models.Allocation.objects.filter(
        tenant_id=payment.tenant_id, payment=payment
    ).aggregate(total=Sum("amount"))["total"]
    return total or ZERO


def credit_position(account_id: Any) -> CreditPosition:
    """US-PAY-007's *visible* half — the balance AND the rows behind it.

    The balance is `selectors.account_credit_position`, unchanged and unfloored:
    one function computes that figure for the whole module, so a screen and a
    refund can never disagree about how much credit exists.
    """
    balance = selectors.account_credit_position(account_id)
    sources: list[CreditSource] = []
    for payment in _unapplied_by_payment(account_id):
        unapplied = payment.amount - _applied_of(payment)
        if unapplied <= ZERO:
            continue
        sources.append(
            CreditSource(
                payment_id=str(payment.pk),
                payment_no=payment.payment_no,
                posted_at=payment.posted_at,
                amount=payment.amount,
                unapplied=unapplied,
                purpose=payment.purpose,
            )
        )
    return CreditPosition(balance=balance, sources=tuple(sources))


def deposit_payments_for_account(account_id: Any) -> Decimal:
    """What has been paid IN with purpose `deposit` (US-PAY-002 TC-2).

    Published for billing: BR-BIL-012 puts the deposit LINE on the first bill
    and BR-PAY-012 says a deposit-purpose payment *"satisfies the first-bill
    deposit line at issue"*. This is the figure that satisfaction draws on.

    ⚠ **THIS SAID "NOTHING CALLS IT" UNTIL 2026-09-02, AND IT HAD BEEN WRONG
    SINCE 2026-08-15 (`DEF-3152`).** Billing calls it on every first bill:
    `apps/billing/first_bill.deposit_line_for` → `apps/billing/payments_seam.
    deposit_paid_for_account` → `_resolve("credit", "deposit_payments_for_
    account")`. **The resolution is BY NAME at call time (B1), which is exactly
    why a grep for a caller finds nothing** — there is no import of this module
    anywhere in billing and there must not be.

    **The cost of the stale sentence is on the record.** `CR-059` CS-19 was
    specified from it, verbatim — *"Payments publishes the figure; billing never
    asks for it … a customer who paid their deposit at the counter is billed for
    it again on their first bill"* — and a lane was dispatched to build something
    that had shipped a fortnight earlier. Hard-won law 1 is usually about a
    comment claiming a guarantee; this is the same law with the sign flipped, and
    it is the more expensive direction because nothing contradicts it.

    The write is still billing's (US-BIL-010) and this module still may not make
    it. `tests/test_cr059_cs10_collections_schedule.py` asserts the contract from
    BOTH ends — the seam's constant and this function's name — so the two cannot
    part company again without a test going red.
    """
    # ⚖️ NET OF RELEASES (CR-171-BRC10 lane RULINGS, `OQ-CUS-12790` (a)): a
    # deposit released to credit is no longer held, so it can no longer satisfy
    # a deposit line — it is in the credit position instead.
    # ⚖️ AND A PROCESSING DEPOSIT COUNTS AS PAID HERE (PO 2026-10-06,
    # `DEF-BIL-9751` (a)): a cheque or card taken at move-in satisfies the
    # first bill's deposit line straight away; a void, cancel or bounce takes
    # it back out through the path that already exists. This reader only —
    # `deposit_still_held` (what a release may pay out) still waits for cleared
    # money. Until 2026-10-06 this returned `deposit_still_held`, which billed
    # M1's $150.00 and the church's $300.00 a second time.
    from apps.payments import deposit_release

    return deposit_release.deposit_counted_paid(account_id)


def deposit_awaiting_clearance(account_id: Any) -> Decimal:
    """Deposit-purpose money RECORDED and not yet cleared — a check in the
    drawer. Read-only, for `customers.seams.deposit_awaiting_clearance`.

    `DEF-CUS-9755`: the move's Billing tab subtracted only the cleared register
    from what was assessed, so a deposit taken by check read *Still to collect
    $150.00* the minute it was taken. This is the population
    `deposit_still_held` EXCLUDES (`status = processing`), stated on its own so
    a screen can say *not cleared yet* without anything changing what counts
    as held. (`DEF-BIL-9751`, ruled 2026-10-06: the same money counts as PAID
    for the first bill — `deposit_payments_for_account` — and is still not
    cleared, which is all this says.)
    """
    return (
        models.Payment.objects.filter(
            tenant_id=_tenant_id(),
            account_id=account_id,
            purpose=models.PURPOSE_DEPOSIT,
            status=models.PAYMENT_PROCESSING,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )


@transaction.atomic
def apply_credit_at_issue(
    *,
    actor: Any = None,
    account_id: Any,
    invoice_id: Any,
    invoice_total: Decimal,
    occurred_on: date | None = None,
) -> CreditApplication:
    """Draw a carried credit down against a newly issued bill (BR-PAY-010).

    `invoice_total` is the bill's own total and is the CALLER's figure — this
    module prices nothing and rounds nothing (B4 is finance-signed and lives in
    `core.money`). What is computed here is only the smaller of two balances.

    Worked, US-PAY-007's own cases:
      TC-2  credit 57.13, bill 184.20  → applies **57.13**, credit **0.00**
      TC-3  credit 57.13, bill  42.10  → applies **42.10**, credit **15.03**
            carried, which applies again next cycle and is never dropped.

    Writes ONE `allocations` row per source payment, so the "Applied to" column
    can name which money met the bill. Rows are append-only (BR-PAY-002): a
    later correction is `reapply`'s reversing pair, never an edit to these.
    """
    tenant_id = _tenant_id()
    if not isinstance(invoice_total, Decimal):
        raise PaymentRuleError(
            f"invoice_total {invoice_total!r} is not a Decimal — money is NUMERIC(18,6) and "
            "never a float (CLAUDE.md rule 2). Refused rather than converted.",
            br_ref="BR-PAY-010",
        )
    allocated = models.Allocation.objects.filter(
        tenant_id=tenant_id, invoice_id=invoice_id
    ).aggregate(total=Sum("amount"))["total"] or ZERO
    open_balance = invoice_total - allocated

    balance = selectors.account_credit_position(account_id)
    if balance <= ZERO or open_balance <= ZERO:
        # A negative position is a DEBT (BR-PAY-041) and a settled bill is not a
        # target. Both answer 0.00 applied — and 0.00 applied is a real answer
        # here, unlike an allocation row, which is only ever written for money
        # that moved.
        return CreditApplication(
            invoice_id=str(invoice_id),
            applied=ZERO,
            remaining_credit=balance,
            invoice_balance_after=open_balance,
        )

    to_apply = balance if balance < open_balance else open_balance
    remaining = to_apply
    rows: list[dict[str, Any]] = []
    for payment in _unapplied_by_payment(account_id, lock=True):
        if remaining <= ZERO:
            break
        unapplied = payment.amount - _applied_of(payment)
        if unapplied <= ZERO:
            continue
        share = unapplied if unapplied < remaining else remaining
        models.Allocation.objects.create(
            tenant_id=tenant_id,
            payment=payment,
            invoice_id=invoice_id,
            amount=share,
        )
        rows.append({"payment_id": str(payment.pk), "amount": str(share)})
        remaining -= share

    applied = to_apply - remaining
    if applied > ZERO:
        # hard rule 7. Inside the transaction, so a lost audit row takes the
        # application with it rather than leaving money moved and unexplained.
        core_audit.money_action(
            actor,
            AUDIT_CREDIT_APPLIED,
            "invoice",
            str(invoice_id),
            after={
                "account_id": str(account_id),
                "applied": str(applied),
                "invoice_total": str(invoice_total),
                "sources": rows,
                "occurred_on": occurred_on.isoformat() if occurred_on is not None else None,
                "job": None if actor is not None else "payments.credit.apply_at_issue",
            },
        )
    return CreditApplication(
        invoice_id=str(invoice_id),
        applied=applied,
        remaining_credit=selectors.account_credit_position(account_id),
        invoice_balance_after=open_balance - applied,
        rows=tuple(rows),
    )


def refundable_position(account_id: Any) -> CreditPosition:
    """What could lawfully be paid out — the *refundable* half of US-PAY-007.

    Deliberately thin: it reports the position and nothing else. BR-PAY-014's
    offset-first test and the Admin approval chain are `refunds.py`'s, and a
    second implementation of either here would eventually disagree with the one
    that actually pays the money.
    """
    return credit_position(account_id)


def contributing_payments(account_id: Any) -> tuple[dict[str, Any], ...]:
    """WHICH payments built this account's credit — CR-059 CS-7's evidence half.

    S58's own acceptance line: *"a credit built from two overpayments can be
    refunded, **listing the payments behind it**"*. That list is a READ, not a
    link: the PO's ruling of 2026-09-01 (`OQ-195`, option (a)) is precisely that
    a refund names the ACCOUNT and not one payment, so the payments behind a
    credit are shown rather than stored — and showing them cannot quietly make
    one of them *the* source again.

    ⚠ **THIS FUNCTION REPLACED A STUB THAT WAS RIGHT TO EXIST.**
    `refund_from_credit_balance` raised `NotImplementedError("OQ-195")` from
    2026-08-15 to 2026-09-03, because `refunds.payment_id` was NOT NULL in a
    SIGNED schema and a refund could therefore name exactly ONE payment. The
    question is now answered and `payments/0018` carries it, so the refusal is
    gone — and **nothing replaced it as a second write path**. A refund against
    the credit balance is `refunds.request_refund(account_id=…)` with no
    payment: ONE writer, the one that already tests the credit, applies the
    offset-first rule and posts to the books.

    Worked, on the case the PO ruled on: **$40.00 in June and $17.13 in July**
    against bills that took nothing, so the account holds **$57.13** and this
    answers both rows. Each carries what it CONTRIBUTED — the part of it no bill
    absorbed — because a $350.00 cheque that left $57.13 behind contributed
    $57.13 and not $350.00, and a screen listing the gross figure would tell a
    clerk they could refund $350.00.

    **A DEPOSIT IS NOT CREDIT AND DOES NOT APPEAR** (US-PAY-002 TC-1) — the same
    exclusion `credit_position` makes, for the same reason: it is money the
    utility HOLDS, and offering it back through the refund path would pay out a
    security deposit as though it were an overpayment.

    ⚠ **THE ROWS SUM TO THE POSITION ONLY WHILE NOTHING HAS BEEN REFUNDED YET.**
    `credit_position` subtracts issued and cleared refunds; this list does not
    attribute a past refund back to the payments it drew on, because **nothing
    records which ones it drew on** and inventing an attribution would be a
    figure nobody measured. So a caller states the POSITION as the refundable
    amount and this list as evidence — never the other way round.
    """
    from django.db.models import Sum

    tenant_id = _tenant_id()
    rows: list[dict[str, Any]] = []
    payments = (
        models.Payment.objects.filter(tenant_id=tenant_id, account_id=account_id)
        .filter(status__in=balance_rule.BALANCE_COUNTED_PAYMENT_STATUSES)  # CR-186-BRC10
        .exclude(purpose=models.PURPOSE_DEPOSIT)
        .order_by("posted_at", "created_at")
    )
    for payment in payments:
        applied = payment.allocations.aggregate(total=Sum("amount"))["total"] or ZERO
        contributed = payment.amount - applied
        if contributed == ZERO:
            # A payment every cent of which met a bill contributed nothing to
            # the credit. Listing it at 0.00 would be a row that means "money
            # moved" about money that did not — `allocation.py`'s own rule.
            continue
        rows.append(
            {
                "payment_id": str(payment.pk),
                "payment_no": payment.payment_no,
                "posted_at": payment.posted_at.isoformat(),
                # ⚠ **THROUGH `selectors._decimal_str`, NOT `str()`.** A raw
                # `Decimal` subtraction keeps the widest scale of its operands,
                # so `350.000000 - 292.870000` prints `57.130000000000` — twelve
                # places of a six-place column, on the wire, for a screen to
                # render at a customer. The quantize is the COLUMN's precision
                # (DB-3) and never money rounding, which is B4's at
                # finalization.
                "amount": selectors._decimal_str(payment.amount),
                "contributed": selectors._decimal_str(contributed),
                "currency": payment.currency,
            }
        )
    return tuple(rows)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-007@3c9f5a1 (sha1[:7] of the sources this slice was authored from, concatenated in order: 04-docs/05-modules/08-payments/06-epics/EP-PAY-02-allocation.md US-PAY-007 · 04-docs/05-modules/08-payments/02-business-rules.md BR-PAY-010/012/014/041 · 04-docs/05-modules/08-payments/03-field-map.md §2 · 04-docs/05-modules/08-payments/07-pre-session-model.md PE-4/PE-9 · 08-qa/01-e2e/journeys/J15-overpay-refund.md)
# generated: 2026-08-15 by story-coder (payments visible-half lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_pay_007_credit.py (TC-3's carry split and the deposit exclusion were driven RED first — transcripts in the lane report) · pytest tests -m isolation✔ · pytest tests -m golden✔
# exceptions: (1) NOTHING CALLS `apply_credit_at_issue`. BR-PAY-010's auto-apply needs `apps/billing/issue.py` to call it and that module belongs to another lane; every result carries `credit_auto_application_has_no_caller` so the absence is on the wire, not only in this docstring (hard-won law 2)
#         (2) `refund_from_credit_balance` RAISES `NotImplementedError("OQ-195")` — the SCHEMA question, which is open. The PO's ruling on the MECHANISM is closed and is deliberately NOT the id cited: a stub citing a closed question is a stale stub (G8), and the blocker here is `refunds.payment_id uuid NOT NULL` in a SIGNED schema, which is a contracts-lane change and not this lane's to make
#         (3) IDEMPOTENCE IS ARITHMETIC, NOT A KEY — both balances are recomputed from rows on every call, so a retried issue applies the residual and never doubles. An "applied at issue" flag would be a second copy of what the allocation rows already say
#         (4) DEPOSIT-PURPOSE PAYMENTS ARE EXCLUDED from the credit position and from auto-application (US-PAY-002 TC-1). A deposit is money HELD, and one that read as credit would be spent on the next bill
#         (5) THE POSITION IS SIGNED AND NEVER FLOORED (BR-PAY-041). A negative credit applies nothing and renders as the debt it is
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
