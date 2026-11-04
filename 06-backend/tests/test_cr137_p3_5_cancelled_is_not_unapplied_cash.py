# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-PAY-6454 — `PAYMENT_FROZEN_STATUSES` is DERIVED (`every status
#          but processing`), so `payments/0036` adding `cancelled` added it to
#          the month-end unapplied-cash tie-out as well, on a line nobody
#          edited and in a file nobody had to open.
# Change:  CR-137-BRC07 · P3.5 (the migration that introduced it)
# Rules:   CLAUDE.md hard rule 2 (money) · hard-won law 7 (prove it RED first)
#          · the "grep for the CONSUMERS" lesson under hard rule 8
# Impacts: apps/payments/selectors.unapplied_cash — read by runbook 9
#          (`month_end`) step 3 and by the payment-trace runbook
# ───────────────────────────────────────────────────────
"""A cancelled payment is not unapplied cash — it is money never taken.

WHY THIS TEST EXISTS
--------------------
`unapplied_cash` answers *"real money in the bank that nobody has put on a
bill"*, and the month-end runbook refuses to close against the figure. It picks
its rows with `status__in=PAYMENT_FROZEN_STATUSES`, which is **derived** —
`tuple(s for s in PAYMENT_STATUSES if s != PAYMENT_PROCESSING)`. So adding a
sixth payment status added it to a finance tie-out **with no edit anywhere near
that query**.

A cancelled payment has an `amount`, a `posted_at` and a `bill` purpose, and it
will never carry an allocation — it was taken by mistake and undone. It would
therefore have sat in unapplied cash for ever, overstating the figure by its own
amount, every month, until somebody reconciled by hand and could not.

⚠ **PROVED RED FIRST.** With the `.exclude(status=PAYMENT_CANCELLED)` removed
from `selectors.unapplied_cash`, `test_a_cancelled_payment_is_not_unapplied`
fails with the cancelled payment's `$61.00` in the total. The CONTROL below is
what makes that mean something: an ordinary unallocated `cleared` payment must
still be counted, or a green here would only say *this function returns
nothing*.

⚠ **THIS RUNS ON SQLITE AND THAT IS THE POINT.** The immutability trigger does
not exist there, so the fixture can write `status='cancelled'` directly. The
DATABASE behaviour of that status — that the move is permitted and the row then
frozen — is a different question and is proved on PostgreSQL 16 by
`10-scripts/p3_cancel_state_and_trigger_readback.py` (hard-won law 14 cuts both
ways: SQLite cannot prove the trigger, and it is a perfectly good place to prove
arithmetic).
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.payments import models, selectors, services
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_020_023_bank_rec import an_account_of

pytestmark = pytest.mark.django_db

POSTED_AT = datetime(2026, 8, 8, 10, 30, tzinfo=UTC)
WINDOW = (date(2026, 8, 1), date(2026, 8, 31))
CANCELLED_AMOUNT = Decimal("61.00")
REAL_AMOUNT = Decimal("74.25")


def a_payment(actor, tenant, amount, *, status):
    """One unallocated payment, left in `status`.

    The status is planted with an `UPDATE` because there is no cancel service
    in this module's test surface — `POST /payments/{id}/cancel` is `P3.2` and
    another lane's. On SQLite there is no trigger to refuse it; on PostgreSQL
    this same statement is exactly what `p3_cancel_state_and_trigger_readback`
    proves is PERMITTED out of `processing` and REFUSED afterwards.
    """
    account = an_account_of(actor, tenant)
    recorded = services.record_payment(
        actor,
        account_id=account.pk,
        amount=amount,
        method_code="cash",
        posted_at=POSTED_AT,
        cleared_at=POSTED_AT,
        idempotency_reference=uuid.uuid4(),
    )
    models.Payment.objects.filter(pk=recorded.payment_id).update(status=status)
    return models.Payment.objects.get(pk=recorded.payment_id)


def test_a_cancelled_payment_is_not_unapplied_cash(brazos, dana):
    """`DEF-PAY-6454`. RED before the exclusion: the total reads $61.00."""
    actor = dana
    with tenant_ctx(brazos):
        cancelled = a_payment(actor, brazos, CANCELLED_AMOUNT, status=models.PAYMENT_CANCELLED)
        answer = selectors.unapplied_cash(*WINDOW)
    assert answer["total"] == Decimal("0"), (
        f"a cancelled payment reached the month-end unapplied-cash figure as "
        f"{answer['total']} — it is money that was never taken"
    )
    # ⚠ the rows carry `payment_no`, not `id` — a first draft asserted `id`
    # and would have raised KeyError, which is a test red for the wrong
    # reason and reads exactly like the defect.
    assert cancelled.payment_no not in {row["payment_no"] for row in answer["payments"]}


def test_the_control_an_ordinary_unallocated_payment_is_still_counted(brazos, dana):
    """Without this, the case above would pass over a function that returns
    nothing at all — law 7 habit 2, the false pass named."""
    actor = dana
    with tenant_ctx(brazos):
        real = a_payment(actor, brazos, REAL_AMOUNT, status=models.PAYMENT_CLEARED)
        answer = selectors.unapplied_cash(*WINDOW)
    assert answer["total"] == REAL_AMOUNT
    assert real.payment_no in {row["payment_no"] for row in answer["payments"]}


def test_both_at_once_only_the_real_one_counts(brazos, dana):
    """The two cases above pass separately on a function that returns its FIRST
    row, or its last. This one cannot."""
    actor = dana
    with tenant_ctx(brazos):
        a_payment(actor, brazos, CANCELLED_AMOUNT, status=models.PAYMENT_CANCELLED)
        a_payment(actor, brazos, REAL_AMOUNT, status=models.PAYMENT_CLEARED)
        answer = selectors.unapplied_cash(*WINDOW)
    assert answer["total"] == REAL_AMOUNT
    assert answer["payment_count"] == 1
