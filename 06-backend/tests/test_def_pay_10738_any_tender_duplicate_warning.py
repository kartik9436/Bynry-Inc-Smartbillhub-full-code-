"""Q1 = A — "Looks like a duplicate" on ANY counter tender (BR-PAY-1199 widened).

PO ruling 2026-10-30, decision log *"Payments audit by level: answers to Q1, Q3,
Q5, Q6, Q7"*, verbatim *"Q1-A"*, put as: at the counter, ANY tender warns
"Looks like a duplicate" when the same account + amount + day is entered against
a bill already paid; *Record anyway* stays allowed and is audit-logged.

THE WORKED CASE, as the tester walked it (TC-4B step 5): Kevin Hall's bill of
$259.23 is already paid in cash; a second $259.23 in CASH, same day, was
accepted with no word to the clerk. Below it is warned and writes nothing;
*Record anyway* records it and the `payment.recorded` audit row carries the
override and the clerk who pressed it.

RED FIRST (hard-won law 7): against the tree before `duplicates.py` was widened,
`test_a_second_cash_payment_on_a_paid_bill_is_warned` failed with
`DID NOT RAISE` — the cash payment was saved and the account held two.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.payments import counters, duplicates, models, services
from apps.tenancy import published_content_models as content_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import audit_rows, tenant_ctx  # noqa: F401 — fixtures
from tests.test_us_pay_020_023_bank_rec import an_account_of, an_issued_bill

pytestmark = pytest.mark.django_db

KEVIN = Decimal("259.23")
TAKEN_AT = datetime(2026, 10, 21, 15, 0, tzinfo=UTC)


@pytest.fixture()
def till(brazos, dana):
    with tenant_ctx(brazos):
        centre = content_models.ServiceCentre.objects.create(
            tenant=brazos, slug="q1-window", name="Main office", address="101 Bend Road"
        )
        return counters.open_counter(
            dana,
            service_centre_id=centre.pk,
            opening_float=Decimal("100.0000"),
            opened_at=TAKEN_AT,
        ).session


def _cash(actor, account, till, *, confirmed=False):
    return services.record_payment(
        actor,
        account_id=account.pk,
        amount=KEVIN,
        posted_at=TAKEN_AT,
        cleared_at=TAKEN_AT,
        method_code="cash",
        idempotency_reference=uuid.uuid4(),
        counter_session_id=till.pk,
        warn_on_possible_duplicate=True,
        duplicate_confirmed=confirmed,
    )


def _kevin_paid(dana, brazos, till):
    account = an_account_of(dana, brazos)
    an_issued_bill(
        brazos, account, number="BL-2610-000925", total=KEVIN, issued_on=date(2026, 10, 1)
    )
    first = _cash(dana, account, till)
    return account, first


def test_a_second_cash_payment_on_a_paid_bill_is_warned(brazos, dana, till):
    with tenant_ctx(brazos):
        account, first = _kevin_paid(dana, brazos, till)
        assert models.Payment.objects.filter(account_id=account.pk).count() == 1
        with pytest.raises(duplicates.PossibleDuplicatePayment) as caught:
            _cash(dana, account, till)
        assert caught.value.earlier["payment_no"] == first.payment_no
        assert Decimal(caught.value.earlier["amount"]) == KEVIN
        assert caught.value.br_ref == "BR-PAY-1199"
        assert models.Payment.objects.filter(account_id=account.pk).count() == 1


def test_record_anyway_records_it_and_the_audit_row_names_the_clerk(
    brazos, dana, till, audit_rows
):
    with tenant_ctx(brazos):
        account, first = _kevin_paid(dana, brazos, till)
        second = _cash(dana, account, till, confirmed=True)
        assert second.created is True
        assert models.Payment.objects.filter(account_id=account.pk).count() == 2
        rows = [
            row
            for row in audit_rows
            if row["action"] == services.AUDIT_RECORDED
            and row["after"]["payment_no"] == second.payment_no
        ]
        assert len(rows) == 1
        assert rows[0]["after"]["duplicate_warning_overridden"] is True
        assert rows[0]["after"]["possible_duplicate_of"]["payment_no"] == first.payment_no
        assert str(rows[0]["actor_user_id"]) == str(dana.id)


def test_a_different_amount_the_same_day_is_not_warned(brazos, dana, till):
    """The check that stops the case above passing wrongly (law 7, habit 2):
    a matcher that warned on EVERY second payment would pass both cases above."""
    with tenant_ctx(brazos):
        account, _first = _kevin_paid(dana, brazos, till)
        other = services.record_payment(
            dana,
            account_id=account.pk,
            amount=Decimal("12.00"),
            posted_at=TAKEN_AT,
            cleared_at=TAKEN_AT,
            method_code="cash",
            idempotency_reference=uuid.uuid4(),
            counter_session_id=till.pk,
            warn_on_possible_duplicate=True,
        )
        assert other.created is True


# ── DEF-PAY-10749 — the ruling says "against a bill ALREADY PAID" ───────────
# The first build warned on account + amount + day alone, so two genuine
# $50.00 cash payments the same day for two DIFFERENT open bills warned.
# RED FIRST: against 5bd3645b1's matcher, the first two cases below raised
# `PossibleDuplicatePayment` on the second $50.00.

FIFTY = Decimal("50.00")


class _Named:
    """One bill the clerk named (`AllocationTargetLike`)."""

    def __init__(self, number):
        self.invoice_number = number
        self.amount = None


def _fifty(actor, account, till, **allocation):
    return services.record_payment(
        actor,
        account_id=account.pk,
        amount=FIFTY,
        posted_at=TAKEN_AT,
        method_code="cash",
        idempotency_reference=uuid.uuid4(),
        counter_session_id=till.pk,
        warn_on_possible_duplicate=True,
        **allocation,
    )


def _two_open_fifties(dana, brazos):
    account = an_account_of(dana, brazos)
    an_issued_bill(
        brazos, account, number="BL-2609-000501", total=FIFTY, issued_on=date(2026, 9, 1)
    )
    an_issued_bill(
        brazos, account, number="BL-2610-000502", total=FIFTY, issued_on=date(2026, 10, 1)
    )
    return account


def test_two_fifties_the_same_day_for_two_open_bills_are_not_warned(brazos, dana, till):
    with tenant_ctx(brazos):
        account = _two_open_fifties(dana, brazos)
        _fifty(dana, account, till)  # oldest first: pays BL-2609-000501
        second = _fifty(dana, account, till)  # BL-2610-000502 is still open
        assert second.created is True
        assert models.Payment.objects.filter(account_id=account.pk).count() == 2


def test_a_fifty_named_against_the_bill_still_open_is_not_warned(brazos, dana, till):
    from apps.payments.allocation import ORDER_SPECIFIC

    with tenant_ctx(brazos):
        account = _two_open_fifties(dana, brazos)
        _fifty(dana, account, till, order=ORDER_SPECIFIC, targets=(_Named("BL-2609-000501"),))
        second = _fifty(
            dana, account, till, order=ORDER_SPECIFIC, targets=(_Named("BL-2610-000502"),)
        )
        assert second.created is True


def test_a_third_fifty_once_both_bills_are_paid_is_warned(brazos, dana, till):
    """The check that stops the two cases above passing wrongly: a matcher that
    never warned would pass both of them."""
    with tenant_ctx(brazos):
        account = _two_open_fifties(dana, brazos)
        _fifty(dana, account, till)
        _fifty(dana, account, till)
        with pytest.raises(duplicates.PossibleDuplicatePayment):
            _fifty(dana, account, till)
        assert models.Payment.objects.filter(account_id=account.pk).count() == 2
