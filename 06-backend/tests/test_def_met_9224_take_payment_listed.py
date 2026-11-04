"""DEF-MET-9224 — a cheque taken with the request's own *Take payment* is listed under Paid so far.

Found by the New Connection end-to-end web walk (2026-10-02): on `CON-26-0129` the
clerk took cheque **4471** for **$40.00** from the request page; it was recorded
(`PY-261002-0090`, processing — a cheque meets no bill until it clears, BR-PAY-021)
and the request's *Charges › Paid so far* never showed it, because
`payments_for_bills` found a payment only by an allocation or by the Create-time
key `entry|new-connect:<id>`. The dialog now keys its payment
`new-connect:<id>:take:<token>` and the read takes that prefix too.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.payments import selectors as payment_selectors
from apps.payments import services as payment_services
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

POSTED_AT = datetime(2026, 10, 2, 15, 0, tzinfo=UTC)


def _cheque(actor, account, reference):
    return payment_services.record_payment(
        actor,
        account_id=account.pk,
        amount=Decimal("40.00"),
        posted_at=POSTED_AT,
        cleared_at=None,
        method_code="check",
        confirmation="4471",
        idempotency_reference=reference,
    )


def test_a_cheque_taken_on_the_request_is_listed_while_it_is_processing(brazos, marcus):
    build = uuid.uuid4()
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        taken = _cheque(marcus, account, f"new-connect:{build}:take:{uuid.uuid4()}")
        rows = payment_selectors.payments_for_bills([], entry_reference=f"new-connect:{build}")
    assert [row["id"] for row in rows] == [str(taken.payment_id)]
    # CR-186-BRC10 (PO 2026-10-21): every payment is POSTED at entry and
    # applied at posting; this account has no open bill, so nothing is applied.
    assert rows[0]["status"] == "posted"
    assert rows[0]["applied"] is False
    assert rows[0]["confirmation"] == "4471"


def test_another_builds_cheque_is_not_listed(brazos, marcus):
    mine, theirs = uuid.uuid4(), uuid.uuid4()
    with tenant_ctx(brazos):
        account = an_account(marcus, brazos)
        _cheque(marcus, account, f"new-connect:{theirs}:take:{uuid.uuid4()}")
        _cheque(marcus, account, str(uuid.uuid4()))
        rows = payment_selectors.payments_for_bills([], entry_reference=f"new-connect:{mine}")
    assert rows == []
