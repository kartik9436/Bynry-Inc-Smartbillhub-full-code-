# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-9751 — a deposit paid by cheque (or card) at move-in was
#           billed AGAIN on the first bill while the payment was processing.
#           DEF-PAY-9782 — a voided deposit cheque still counted as HELD.
# Rules:    PO ruling 2026-10-06 (decision log, DEF-BIL-9751 option (a)),
#           verbatim: *"this is correct - I recommend (a). It matches what the
#           customer actually did at the counter, and bounced payments are
#           already handled by a process that exists today."* · BR-PAY-012 ·
#           BR-BIL-012 · BR-PAY-002 · BR-PAY-013 · US-PAY-002 TC-1
# Tests:    this file (SQLite + the same cases on PostgreSQL 16, see below)
# ───────────────────────────────────────────────────────
"""**A deposit taken at move-in counts as paid straight away, whatever the tender.**

THE PO's FIGURE, at this world's prices: the customer pays **$175.00** by
cheque at move-in — **$150.00** deposit + **$25.00** connection — and the
cheque is still processing. The first bill carries **no** deposit line. If the
cheque comes back, the EXISTING path takes it back out (a processing cheque is
CANCELLED, a cleared one is REVERSED), and the **$150.00** is owed again.

The church's case (M5) is the same arithmetic at the Commercial rule:
$325.00 = $300.00 + $25.00 → no $300.00 line; it is exercised end to end by
`10-scripts/cr171_e2e_matrix_run.mjs`.

WHAT IS NOT MOVED: a RELEASE (what a refund can pay out) still waits for
cleared money — `deposit_still_held` reads $0.00 while the cheque is in the
drawer.

RED FIRST (law 7): on the tip before this change,
`test_a_processing_cheque_deposit_is_not_billed_again` and the card case read a
$150.00 deposit line, and `test_a_voided_deposit_cheque_is_not_held` read held
$150.00.

WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2): a world whose plan asks no
deposit at all (every case first asserts `deposit_asked == 150`); a payment
recorded cleared rather than processing (the status is read back); a "return"
that wrote nothing (the reversing row is read back).

PostgreSQL 16:

    DATABASE_URL="postgres://…" DJANGO_SETTINGS_MODULE=config.settings.pgtest \\
      JOBS_EAGER=false pytest -q -p no:xdist tests/test_def_bil_9751_move_in_deposit_counts_paid.py
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.billing import first_bill
from apps.customers import models as customers_models
from apps.payments import cancel, cheques, deposit_release, reversal, services
from apps.payments import models as payment_models
from tests.test_cr171_p1_12_move_in_fees import MOVE_IN_DAY, _move_in, _pay_now, _world
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

DEPOSIT = Decimal("150")
FEES = [
    {"kind": "deposit", "source": "plan", "amount": "150.00"},
    {"kind": "fee", "source": "plan", "code": "CONN", "amount": "25.00"},
]
MOVED_IN = date(2026, 8, 15)
RETURNED = datetime(2026, 8, 20, 15, 0, tzinfo=dt_timezone.utc)


_PLANS: dict = {}


def _account(result, plan):
    account = customers_models.Account.objects.get(pk=result["id"])
    _PLANS[str(account.pk)] = plan.pk
    return account


def _moved_in(actor, tenant, **payment):
    _unit, plan, outgoing = _world(actor, tenant)
    result = _move_in(actor, outgoing, fees=FEES, payment=_pay_now("175.00", **payment))
    return _account(result, plan)


def _deposit_payment(account):
    return payment_models.Payment.objects.get(
        account_id=account.pk,
        purpose=payment_models.PURPOSE_DEPOSIT,
        reverses_payment__isnull=True,
    )


def _first_bill_deposit(account) -> first_bill.OneTimeLines:
    """`first_bill.deposit_line_for` — the function that writes or omits the
    first bill's deposit line — called with the four facts it reads off the
    gathered account. The move-in world prices no tariff, so a whole
    `prepare_first_bill` would refuse before reaching the deposit; the line
    itself is what this defect is about."""
    data = SimpleNamespace(
        account_id=account.pk,
        account_no=account.account_no,
        rate_plan_id=_PLANS[str(account.pk)],
        currency=account.currency,
    )
    return first_bill.deposit_line_for(data, account_type_id=account.account_type_id)


def _line(answer) -> Decimal:
    return sum((line.amount for line in answer.lines if line.kind == "deposit"), Decimal("0"))


@pytest.mark.parametrize("method_code", ["check", "card"])
def test_a_processing_deposit_is_not_billed_again(brazos, dana, method_code):
    with tenant_ctx(brazos):
        account = _moved_in(dana, brazos, method_code=method_code)
        paid = _deposit_payment(account)
        assert paid.status == payment_models.PAYMENT_PROCESSING, "the fixture must be uncleared"
        answer = _first_bill_deposit(account)
        held = deposit_release.deposit_still_held(account.pk)

    assert answer.deposit_asked == DEPOSIT, "the plan must ASK a deposit, or nothing is proved"
    assert _line(answer) == Decimal("0")
    assert answer.lines == ()
    assert answer.deposit_already_paid == DEPOSIT
    # A release still waits for cleared money: nothing may be paid OUT of it.
    assert held == Decimal("0")


def test_a_processing_cheque_returned_is_owed_again(brazos, dana):
    """Paid by cheque → no deposit line → the cheque comes back before it
    cleared → the EXISTING Cancel writes its reversing row → $150.00 owed."""
    with tenant_ctx(brazos):
        account = _moved_in(dana, brazos)
        assert _line(_first_bill_deposit(account)) == Decimal("0")

        paid = _deposit_payment(account)
        cancel.cancel_payment(
            actor=dana,
            payment_id=paid.pk,
            reason=cancel.CANCEL_REASON_NOT_TAKEN,
            cancelled_on=RETURNED,
            note="cheque returned",
        )
        returned = payment_models.Payment.objects.get(reverses_payment_id=paid.pk)
        answer = _first_bill_deposit(account)

    assert returned.amount == -paid.amount
    assert returned.purpose == payment_models.PURPOSE_DEPOSIT
    assert answer.deposit_asked == DEPOSIT
    assert _line(answer) == DEPOSIT


def test_a_cleared_cheque_that_bounces_is_owed_again(brazos, dana):
    """Paid by cheque and cleared → no deposit line → NSF through the EXISTING
    reversal (a new negative row, BR-PAY-013) → $150.00 owed again."""
    with tenant_ctx(brazos):
        account = _moved_in(dana, brazos)  # posted at entry (CR-186); no clearing date (DEF-CUS-10324)
        paid = _deposit_payment(account)
        assert paid.status != payment_models.PAYMENT_PROCESSING
        assert _line(_first_bill_deposit(account)) == Decimal("0")

        reversal.reverse_payment(
            dana,
            payment_id=paid.pk,
            returned_on=RETURNED,
            idempotency_reference=uuid.uuid4(),
        )
        answer = _first_bill_deposit(account)
        held = deposit_release.deposit_still_held(account.pk)

    assert _line(answer) == DEPOSIT
    assert held == Decimal("0")


def test_a_voided_deposit_cheque_is_not_held(brazos, dana):
    """DEF-PAY-9782 — a cheque voided at the counter moves to `failed` and
    writes no reversing row; it is neither held (a release cannot refund it)
    nor counted paid (the deposit line comes back)."""
    with tenant_ctx(brazos):
        _unit, plan, outgoing = _world(dana, brazos)
        result = _move_in(dana, outgoing, fees=FEES)  # nothing paid at the counter
        account = _account(result, plan)
        recorded = services.record_payment(
            dana,
            account_id=account.pk,
            amount=Decimal("150.00"),
            posted_at=RETURNED,
            cleared_at=None,
            method_code="check",
            confirmation="1187",
            cheque_date=MOVED_IN,
            drawer_bank="First National",
            purpose=payment_models.PURPOSE_DEPOSIT,
            idempotency_reference=uuid.uuid4(),
        )
        assert _line(_first_bill_deposit(account)) == Decimal("0")
        cheques.void_cheque(dana, payment_id=recorded.payment_id, reason="torn up", on_date=MOVED_IN)
        held = deposit_release.deposit_still_held(account.pk)
        answer = _first_bill_deposit(account)

    assert held == Decimal("0")
    assert _line(answer) == DEPOSIT
