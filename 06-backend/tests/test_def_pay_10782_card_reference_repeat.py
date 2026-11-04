"""P8 = A — the same card/ACH reference twice on one account and day is warned,
even when the bill is still open (BR-PAY-1199, widened again 2026-10-31).

PO ruling 2026-10-31, decision log *"Twelve open payment questions answered
(PO)"*, verbatim *"P8-A"*, put as: in addition to Q1's rule, the counter also
warns when the **same card/ACH reference repeats on the same account and day**
(e.g. AUTH 88412 entered twice on an open bill).

THE WORKED CASE: a $100.00 bill is open; $40.00 by card, AUTH 88412, is
recorded; a second $40.00 card, AUTH 88412, the same day. The bill still owes
$60.00, so Q1's paid-bill condition is not met — and before this file the
second was saved with no word. Now it is warned; *Record anyway* records it.

What must NOT move (the check that stops the case above passing wrongly):
two $50.00 cash payments the same day for two open bills are still not warned
(`test_def_pay_10738_*` holds that), and a different authorisation, a different
day or a cash payment with a typed note are not warned either.

RED FIRST (hard-won law 7): against the tip's `duplicates.py`,
`test_auth_88412_twice_on_an_open_bill_is_warned` and
`test_the_reference_is_compared_trimmed_and_case_blind` failed with
`DID NOT RAISE` — the second $40.00 was saved.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from apps.payments import counters, duplicates, models, services
from apps.tenancy import published_content_models as content_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import audit_rows, tenant_ctx  # noqa: F401 — fixtures
from tests.test_us_pay_020_023_bank_rec import an_account_of, an_issued_bill

pytestmark = pytest.mark.django_db

FORTY = Decimal("40.00")
TAKEN_AT = datetime(2026, 10, 21, 15, 0, tzinfo=UTC)


@pytest.fixture()
def till(brazos, dana):
    with tenant_ctx(brazos):
        centre = content_models.ServiceCentre.objects.create(
            tenant=brazos, slug="p8-window", name="Main office", address="101 Bend Road"
        )
        return counters.open_counter(
            dana,
            service_centre_id=centre.pk,
            opening_float=Decimal("100.0000"),
            opened_at=TAKEN_AT,
        ).session


def _take(actor, account, till, *, tender="card", ref="AUTH 88412", amount=FORTY,
          at=TAKEN_AT, confirmed=False):
    return services.record_payment(
        actor,
        account_id=account.pk,
        amount=amount,
        posted_at=at,
        cleared_at=at,
        method_code=tender,
        confirmation=ref,
        idempotency_reference=uuid.uuid4(),
        # A card or ACH payment never enters a drawer (PO 2026-09-23); only
        # cash is taken into the till.
        counter_session_id=till.pk if tender == "cash" else None,
        warn_on_possible_duplicate=True,
        duplicate_confirmed=confirmed,
    )


def _open_hundred(dana, brazos):
    account = an_account_of(dana, brazos)
    an_issued_bill(
        brazos, account, number="BL-2610-008841", total=Decimal("100.00"),
        issued_on=date(2026, 10, 1),
    )
    return account


def test_auth_88412_twice_on_an_open_bill_is_warned(brazos, dana, till):
    with tenant_ctx(brazos):
        account = _open_hundred(dana, brazos)
        first = _take(dana, account, till)
        with pytest.raises(duplicates.PossibleDuplicatePayment) as caught:
            _take(dana, account, till)
        assert caught.value.earlier["payment_no"] == first.payment_no
        assert caught.value.earlier["confirmation"] == "AUTH 88412"
        # The screen says WHY: the reference, not "the bill is paid".
        assert caught.value.earlier["matched_on"] == duplicates.MATCHED_ON_REFERENCE
        assert caught.value.br_ref == "BR-PAY-1199"
        assert models.Payment.objects.filter(account_id=account.pk).count() == 1


def test_the_same_reference_for_a_different_amount_is_warned(brazos, dana, till):
    """The ruling names the reference, the account and the day — not the amount."""
    with tenant_ctx(brazos):
        account = _open_hundred(dana, brazos)
        _take(dana, account, till)
        with pytest.raises(duplicates.PossibleDuplicatePayment):
            _take(dana, account, till, tender="ach", amount=Decimal("12.00"))


def test_the_reference_is_compared_trimmed_and_case_blind(brazos, dana, till):
    with tenant_ctx(brazos):
        account = _open_hundred(dana, brazos)
        _take(dana, account, till, ref="auth 88412 ")
        with pytest.raises(duplicates.PossibleDuplicatePayment):
            _take(dana, account, till, ref=" AUTH 88412")


def test_record_anyway_records_it_and_the_audit_row_says_so(brazos, dana, till, audit_rows):
    with tenant_ctx(brazos):
        account = _open_hundred(dana, brazos)
        first = _take(dana, account, till)
        second = _take(dana, account, till, confirmed=True)
        assert second.created is True
        rows = [
            row for row in audit_rows
            if row["action"] == services.AUDIT_RECORDED
            and row["after"]["payment_no"] == second.payment_no
        ]
        assert len(rows) == 1
        assert rows[0]["after"]["duplicate_warning_overridden"] is True
        assert rows[0]["after"]["possible_duplicate_of"]["payment_no"] == first.payment_no


def test_a_different_authorisation_on_an_open_bill_is_not_warned(brazos, dana, till):
    with tenant_ctx(brazos):
        account = _open_hundred(dana, brazos)
        _take(dana, account, till)
        other = _take(dana, account, till, ref="AUTH 88413")
        assert other.created is True


def test_the_same_reference_the_next_day_is_not_warned(brazos, dana, till):
    with tenant_ctx(brazos):
        account = _open_hundred(dana, brazos)
        _take(dana, account, till)
        later = _take(dana, account, till, at=TAKEN_AT + timedelta(days=1))
        assert later.created is True


def test_cash_with_the_same_note_on_an_open_bill_is_not_warned(brazos, dana, till):
    """Only a CARD or ACH reference is an authorisation; a cash note is not."""
    with tenant_ctx(brazos):
        account = _open_hundred(dana, brazos)
        _take(dana, account, till, tender="cash", ref="counter 1")
        again = _take(dana, account, till, tender="cash", ref="counter 1")
        assert again.created is True


def test_two_cash_fifties_for_two_open_bills_are_still_not_warned(brazos, dana, till):
    with tenant_ctx(brazos):
        account = an_account_of(dana, brazos)
        an_issued_bill(brazos, account, number="BL-2609-000601", total=Decimal("50.00"),
                       issued_on=date(2026, 9, 1))
        an_issued_bill(brazos, account, number="BL-2610-000602", total=Decimal("50.00"),
                       issued_on=date(2026, 10, 1))
        _take(dana, account, till, tender="cash", ref=None, amount=Decimal("50.00"))
        second = _take(dana, account, till, tender="cash", ref=None, amount=Decimal("50.00"))
        assert second.created is True
