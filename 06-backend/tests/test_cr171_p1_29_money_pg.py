# ── Trace ──────────────────────────────────────────────
# Change:  CR-171-BRC10 P1.29 (law-14 proof) for lane MVI-MONEY's paths —
#          P1.12 fees, P1.13 payment, P1.15 the held claim and certificate.
# Rules:   hard-won law 14 (a failed statement poisons a PostgreSQL
#          transaction; SQLite has no such state) · BR-SHL-019 (one commit)
# ───────────────────────────────────────────────────────
"""**The move-in's money paths, on real PostgreSQL.**

Skipped on SQLite BY DESIGN (`requires_postgres`). Run:

    DATABASE_URL=postgres://postgres@127.0.0.1:55433/<db> JOBS_EAGER=false \\
      pytest tests/test_cr171_p1_29_money_pg.py --ds=config.settings.pgtest -p no:xdist

⚖️ **THERE IS NO CATCH-AND-CONTINUE ON THESE PATHS SINCE 2.539.0.** Until then
`move_in_preferences._held` caught rating's refusal of a Billing Clerk inside a
SAVEPOINT and parked the claim for a System Admin. PO ruling 2026-10-05
(decision log *"FOUR PO RULINGS IN ONE REPLY"* (2), option (b)): *"Let billing
clerks record it themselves"* — rating admits the clerk and the catch is
deleted. Case 1 now proves the clerk's claim and certificate are WRITTEN inside
the one commit on PostgreSQL; case 3 proves that a refusal from rating now
rolls the WHOLE move-in back cleanly on PostgreSQL (nothing caught, so nothing
half-written and no aborted transaction left behind).
"""

from __future__ import annotations


import uuid
from decimal import Decimal

import pytest
from django.db import DatabaseError, connection

from apps.customers import discounts as customers_discounts
from apps.customers import services as customers_services
from apps.customers.account_document_models import AccountDocument
from apps.customers.move_in_extras import MoveFeeLine
from apps.payments import models as payment_models
from apps.rating import discount_services
from core import errors
from tests.isolation_helpers import requires_postgres
from tests.test_cr171_p1_12_move_in_fees import _fees, _move_in, _pay_now, _world
from tests.test_cr171_p1_15_move_in_preferences import PDF, _category
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import brazos, dana, marcus, tenant_ctx  # noqa: F401

pytestmark = [pytest.mark.django_db, requires_postgres]

SENIOR = str(uuid.uuid4())


@pytest.fixture()
def carried(monkeypatch):
    monkeypatch.setattr(
        discount_services, "discount_ids_carried", lambda account_id, on_day: {SENIOR}
    )


def _clerk_payload(category, discount_id=SENIOR):
    return dict(
        payment=_pay_now("215.00"),
        discount_claims=[{"discount_id": str(discount_id), "note": "Senior"}],
        tax_exemption={
            "category_id": str(category.id),
            "certificate_ref": "IA-EX-2231",
            "certificate": {
                "name": "ex.pdf",
                "content_type": "application/pdf",
                "content_base64": PDF,
            },
        },
    )


def test_p1_29__a_clerks_claim_and_certificate_commit_with_the_whole_move_in(
    brazos, marcus, dana, monkeypatch
):
    from apps.rating import discounts as discount_models
    from apps.rating import models as rating_models
    from tests.test_cr166_discounts_round2 import _discount

    assert connection.vendor == "postgresql"
    with tenant_ctx(brazos):
        senior = _discount(dana)
        monkeypatch.setattr(
            discount_services, "discount_ids_carried", lambda account_id, on_day: {senior.id}
        )
        _u, _p, outgoing = _world(marcus, brazos)
        category = _category(brazos)
        result = _move_in(marcus, outgoing, **_clerk_payload(category, senior.id))
        account_id = result["id"]
        assert discount_models.DiscountEnrolment.objects.filter(account_id=account_id).count() == 1
        assert (
            rating_models.TaxExemptionCertificate.objects.filter(account_id=account_id).count() == 1
        )
        assert [
            line.code for line in MoveFeeLine.objects.filter(move_record__account_id=account_id)
        ] == [
            "DEPOSIT",
            "CONN",
            "RUSH",
        ]
        paid = {
            row.purpose: row.amount
            for row in payment_models.Payment.objects.filter(account_id=account_id)
        }
        assert paid == {"deposit": Decimal("150.000000"), "prepay": Decimal("65.000000")}
        assert AccountDocument.objects.filter(account_id=account_id).count() == 1
    assert result["billing_extras"]["discounts"][0]["status"] == "pending"
    assert result["billing_extras"]["tax_exemption"]["status"] == "recorded"
    assert result["move_message"], "the welcome message queued AFTER the rating writes"


@pytest.mark.parametrize(
    "override",
    [
        {"fees": [{"kind": "fee", "source": "charge_code", "code": "RUSH", "amount": "35.00"}]},
        {"payment": _pay_now("999.00")},
    ],
)
def test_p1_29__a_refused_fee_or_payment_rolls_back_everything_on_postgres(brazos, dana, override):
    with tenant_ctx(brazos):
        _u, _p, outgoing = _world(dana, brazos)
        accounts = customers_services.models.Account.objects.count()
        payments = payment_models.Payment.objects.count()
        with pytest.raises(errors.ValidationError):
            _move_in(dana, outgoing, **override)
        assert customers_services.models.Account.objects.count() == accounts
        assert payment_models.Payment.objects.count() == payments
        assert MoveFeeLine.objects.count() == 0


def test_p1_29__a_refusal_from_rating_rolls_the_whole_move_in_back(
    brazos, marcus, carried, monkeypatch
):
    """Nothing on this path is caught any more. A claim writer that met a FAILED
    statement and then refused propagates its refusal: the move-in opens no
    account, writes no fee line and no payment, and the connection still
    answers — no aborted transaction is left behind on PostgreSQL."""

    def failed_then_refused(actor, account_id, programme_id, household_size=None):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 / 0")
        except DatabaseError:
            pass  # the naive catch law 14 is about — the outer commit is what must hold
        raise errors.AuthError(errors.AUTH_PERMISSION_DENIED, br_ref="BR-SHL-025")

    monkeypatch.setattr(customers_discounts, "claim_assistance", failed_then_refused)
    with tenant_ctx(brazos):
        _u, _p, outgoing = _world(marcus, brazos)
        accounts = customers_services.models.Account.objects.count()
        payments = payment_models.Payment.objects.count()
        with pytest.raises(errors.AuthError):
            _move_in(
                marcus,
                outgoing,
                fees=_fees(),
                payment=_pay_now("215.00"),
                discount_claims=[{"discount_id": SENIOR}],
            )
        assert customers_services.models.Account.objects.count() == accounts
        assert payment_models.Payment.objects.count() == payments
        assert MoveFeeLine.objects.count() == 0
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        assert cursor.fetchone() == (1,)
