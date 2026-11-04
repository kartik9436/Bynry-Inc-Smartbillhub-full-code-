"""DEF-PAY-9263 — "Looks like a duplicate" at New Connection step 4, on PostgreSQL.

PO ruling 2026-10-03: *"Same card or ACH payment entered twice - B Warn "Looks
like a duplicate", and let the clerk confirm"* (`BR-PAY-1199`).

Step 4's payment is recorded INSIDE the build's one commit (`BR-MET-1187`,
`BR-MET-112` both-or-neither). So the warning has to roll the WHOLE build back
— no unit, no invoice, no payment — and answer on step 4 with the earlier
payment named; *Record anyway* re-runs the commit with
`payment_duplicate_confirmed: true` and everything is written once.

PostgreSQL only (hard-won law 14): the warning is raised inside the commit's
`atomic()` and the build must roll back cleanly on a real database.

⚠ NARROWED 2026-10-30 (`DEF-PAY-10749`): Q1 = A warns only against a bill
ALREADY PAID, and step 4 pays the bill its own commit raises, which is open.
So step 4 with a matching card payment is NOT warned; the case below says so.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.payments import models as payment_models
from apps.payments import services as payment_services
from tests.isolation_helpers import requires_postgres
from apps.customers import services as customers_services
from tests import identity_fixtures
from tests.test_br_met_1187_books_entry_at_creation import (
    OWNER_NAME,
    POSTING_DATE,
    _commit,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (
    make_premises,
    make_unit,
    tenant_ctx,
)  # noqa: F401

pytestmark = [pytest.mark.django_db, requires_postgres]

AUTH = "AUTH-S8-0030"
THIRTY = "30.0000"


def _build_with_an_owner_account(actor):
    """`test_br_met_1187`'s builder, with the SECOND unit a master account now
    needs (`customers.account.master_needs_two_units`) — that file's own
    builder is red on PostgreSQL for exactly that reason (pre-existing)."""
    premises = make_premises(actor)
    make_unit(actor, premises["id"])
    make_unit(actor, premises["id"], label="Unit B")
    created = w6.create_connection(actor, {"premises_id": premises["id"]})
    connection = work_tables.Connection.objects.get(pk=created["id"])
    account = customers_services.create_master_account(
        actor,
        {
            "premises_id": premises["id"],
            "account_type": "commercial",
            "opened_at": "2026-08-01",
            "contact": {"full_name": OWNER_NAME},
            "customer": identity_fixtures.customer_block(OWNER_NAME, account_type="commercial"),
        },
    )
    w6.tag_charges_to_account(actor, connection.id, account["id"])
    connection.refresh_from_db()
    return connection, premises, account


def _earlier_card_payment(actor, account_id):
    """The first $30.00 card payment, AUTH-S8-0030, on the build's posting day."""
    moment = w6._moment_of(date.fromisoformat(POSTING_DATE))
    return payment_services.record_payment(
        actor,
        account_id=account_id,
        amount=Decimal(THIRTY),
        posted_at=moment,
        cleared_at=moment,
        method_code="card",
        confirmation=AUTH,
        idempotency_reference=uuid.uuid4(),
    )


def _step4_payment(**extra):
    return {
        "payment_method": "card",
        "payment_amount": THIRTY,
        "payment_date": POSTING_DATE,
        "payment_cleared_date": POSTING_DATE,
        "payment_reference": AUTH,
        **extra,
    }


def test_step4_pays_the_builds_own_open_bill_and_is_not_warned(brazos, dana, audit_rows):
    """⚠ REWRITTEN 2026-10-30 (`DEF-PAY-10749`, lane PAY-K). This case read
    *"step 4 warns, rolls the build back, then records on confirm"*. Q1 = A
    (PO 2026-10-30) warns only for a payment entered against a bill ALREADY
    PAID, and step 4's payment meets the one-time-charge bill the same commit
    raises — a bill that is open by construction. So the same $30.00 card
    payment with the same reference is a genuine payment of a new bill: it is
    NOT warned, the build commits once, and no override is audited.

    The roll-back-on-warning path stays in `connections.py` and is now reached
    only by a step-4 payment that meets no open bill."""
    with tenant_ctx(brazos):
        connection, premises, account = _build_with_an_owner_account(dana)
        first = _earlier_card_payment(dana, account["id"])
        payments_before = payment_models.Payment.objects.filter(account_id=account["id"]).count()

        result = _commit(dana, connection, **_step4_payment())
        payment_no = result["manifest"]["one_time_charge_payment_no"]
        assert payment_no and payment_no != first.payment_no
        assert result["manifest"]["one_time_charge_paid"] == THIRTY
        assert (
            payment_models.Payment.objects.filter(account_id=account["id"]).count()
            == payments_before + 1
        )
        recorded = [
            row
            for row in audit_rows
            if row["action"] == payment_services.AUDIT_RECORDED
            and row["after"]["payment_no"] == payment_no
        ]
        assert len(recorded) == 1
        assert not recorded[0]["after"].get("duplicate_warning_overridden")


def test_step4_with_another_reference_is_not_warned(brazos, dana):
    with tenant_ctx(brazos):
        connection, _unit, account = _build_with_an_owner_account(dana)
        _earlier_card_payment(dana, account["id"])
        result = _commit(dana, connection, **_step4_payment(payment_reference="AUTH-S8-0031"))
        assert result["manifest"]["one_time_charge_payment_no"]
