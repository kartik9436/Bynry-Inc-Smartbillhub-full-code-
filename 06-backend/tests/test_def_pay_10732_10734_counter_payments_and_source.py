"""DEF-PAY-10732 (L2-11) and DEF-PAY-10734 (L2-03) — a till's own payments, a
payment found by its number, and a counter payment that names its clerk.

Tester, 2026-10-30 (payments audit by level, imgs 25-27, 38, 39):
  * *"A newly opened counter with 0 payments lists many older payments. Searching
    by payment ID finds nothing."* — the 3·2 table sent `f.counter=<code>` and
    BE-05 dropped the undeclared name with a 200.
  * *"A counter payment says 'taken by Nobody named'"* — `payment_detail._source`
    hard-coded the till link to None while `counter_session_id` named it.
  * *"searching for the memo finds nothing"*.

RED FIRST (hard-won law 7), against the tip before the fix:
`test_a_new_counter_lists_none_of_the_older_payments` failed (`f.counter` was
dropped, so the list returned the older payment), the PY- and memo searches
returned nothing, and `taken_by` was None.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.payments import counters, payment_detail, selectors, services
from apps.payments import models as payment_models
from apps.tenancy import published_content_models as content_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import an_account

pytestmark = [pytest.mark.django_db]


@pytest.fixture()
def centre(brazos):
    with tenant_ctx(brazos):
        return content_models.ServiceCentre.objects.create(
            tenant=brazos, slug="l211-window", name="Main office", address="101 Bend Road"
        )


def _open(actor, centre):
    return counters.open_counter(
        actor,
        service_centre_id=centre.pk,
        opening_float=Decimal("100.0000"),
        opened_at=timezone.now(),
    ).session


def _take(actor, tenant, *, till=None, method_code="cash", memo=None):
    account = an_account(actor, tenant, account_no=f"A-{uuid.uuid4().hex[:6]}")
    recorded = services.record_payment(
        actor,
        account_id=account.pk,
        amount=Decimal("68.0000"),
        posted_at=timezone.now(),
        cleared_at=timezone.now(),
        method_code=method_code,
        idempotency_reference=uuid.uuid4(),
        counter_session_id=None if till is None else till.pk,
        memo=memo,
    )
    return payment_models.Payment.objects.get(pk=recorded.payment_id)


def _listed(q=None, **filters):
    raw = {f"f.{name}": value for name, value in filters.items()}
    if q is not None:
        raw["q"] = q
    params = selectors.list_params(raw)
    return {str(row.pk) for row in selectors.payment_list_queryset(params)}


# ══ L2-11 · the till's own payments ════════════════════════════════════════
def test_counter_is_a_declared_filter():
    assert "counter" in selectors.PAYMENT_FILTERS


def test_a_new_counter_lists_none_of_the_older_payments(brazos, dana, centre):
    with tenant_ctx(brazos):
        _take(dana, brazos, method_code="ach")  # an older payment, no till
        till = _open(dana, centre)
        assert till.code, "a till has a code a clerk reads"
        assert _listed(counter=till.code) == set()


def test_a_counter_lists_exactly_the_payments_it_took(brazos, dana, marcus, centre):
    with tenant_ctx(brazos):
        mine = _open(dana, centre)
        theirs = _open(marcus, centre)
        taken = _take(dana, brazos, till=mine)
        _take(marcus, brazos, till=theirs)
        _take(dana, brazos, method_code="ach")
        assert _listed(counter=mine.code) == {str(taken.pk)}


def test_an_unknown_counter_code_matches_nothing(brazos, dana):
    with tenant_ctx(brazos):
        _take(dana, brazos, method_code="ach")
        assert _listed(counter="CTR-000000-XX") == set()


def test_a_payment_number_finds_exactly_that_payment(brazos, dana, centre):
    with tenant_ctx(brazos):
        till = _open(dana, centre)
        wanted = _take(dana, brazos, till=till)
        _take(dana, brazos, till=till)
        assert wanted.payment_no
        assert _listed(q=wanted.payment_no) == {str(wanted.pk)}


# ══ L2-03 (c) · the memo is searched ═══════════════════════════════════════
def test_the_memo_is_searched(brazos, dana):
    with tenant_ctx(brazos):
        noted = _take(dana, brazos, method_code="ach", memo="Paid by Salvation Army pledge 77")
        _take(dana, brazos, method_code="ach", memo="ordinary")
        assert _listed(q="salvation army") == {str(noted.pk)}


# ══ L2-03 (a) · a counter payment names its clerk and its till ═════════════
def test_a_counter_payment_names_the_clerk_and_the_till(brazos, dana, centre):
    with tenant_ctx(brazos):
        till = _open(dana, centre)
        payment = _take(dana, brazos, till=till)
        source = payment_detail._source(payment)
        # The till's OWNER row — `dana` in these helpers is an actor namespace
        # over a real identity user, and the owner is that user.
        owner = till.owner
    expected = (getattr(owner, "full_name", "") or "").strip() or owner.email
    assert expected
    assert source["taken_by"] == expected
    assert source["counter_session_ref"] == till.code
    assert source["import_kind"] is None


def test_a_payment_with_no_till_still_names_nobody(brazos, dana):
    """Law 7 habit 2 — a fix that named the CURRENT user on every payment would
    pass the case above."""
    with tenant_ctx(brazos):
        payment = _take(dana, brazos, method_code="ach")
        source = payment_detail._source(payment)
    assert source["taken_by"] is None
    assert source["counter_session_ref"] is None


@pytest.fixture()
def real_audit_log():
    """Write `audit_log` for real — the shared helpers capture audit rows into a
    Python list, so `history_queryset` would read an empty table and this case
    could not pass (`test_cr137_p3_detail_cancel_receipt.py` records the trap)."""
    from apps.audit import services as audit_services
    from core import audit as core_audit

    previous = core_audit._sink
    core_audit.set_audit_sink(audit_services.store_row)
    yield
    core_audit.set_audit_sink(previous)


def test_a_reference_correction_is_listed_in_the_payments_history(brazos, dana, real_audit_log):
    """DEF-PAY-10735 (L3-05). RED FIRST: the trail read `entity_type='payment'`
    and a correction is written as `payments`, so History never showed it."""
    from apps.payments import amendments

    with tenant_ctx(brazos):
        # No method, so the correction touches the reference only — the
        # tester's case, and it keeps the banked-tender refusal out of it.
        payment = _take(dana, brazos, method_code=None)
        amendments.amend_reference(
            dana, payment_id=payment.pk, reference="4471", note="Typed 4417 by mistake."
        )
        actions = [row.action for row in payment_detail.history_queryset(payment)]
    assert "payment.reference_amended" in actions
    assert "payment.recorded" in actions, "the ordinary rows are still read"


def test_an_imported_payment_says_which_kind_of_import(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no=f"A-{uuid.uuid4().hex[:6]}")
        payment = payment_models.Payment(tenant=brazos, account=account, origin="import")
        assert payment_detail._source(payment)["import_kind"] == "file"
