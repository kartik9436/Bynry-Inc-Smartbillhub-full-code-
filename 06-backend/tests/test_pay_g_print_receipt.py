# ── Trace ──────────────────────────────────────────────
# Ruling:   PO 2026-10-30, Q3 = A — *Print receipt* opens a one-page receipt in
#           the browser now (Rosa pays $68.00 cash → prints)
# Defect:   DEF-PAY-10743
# Tests:    this file (backend half; the DOM half is
#           07-frontend/src/features/payments/printReceipt.dom.test.tsx)
# ───────────────────────────────────────────────────────
"""Rosa pays $68.00 cash at Dana's counter: every fact the PO listed is served.

RED FIRST (law 7): before this change the route did not exist —
`payments/<id>/receipt/print` fell through to `payments/<id>`'s pattern and
answered 404 for the unknown reference `…/receipt/print`.

WHAT WOULD MAKE THIS PASS WRONGLY: serving the payment's database id as the
receipt number (B14 rule 31) — so the case asserts the PY- number AND that the
id appears in no value but `payment_id`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal as D

import pytest

from apps.customers import models as customer_models
from apps.payments import counters, detail_api, services
from apps.tenancy import published_content_models as content_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill
from tests.test_us_ten_helpers import api_call, seeding_ctx
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

ROSA = D("68.00")
OPENED = datetime(2026, 10, 30, 8, 0, tzinfo=UTC)
PAID = datetime(2026, 10, 30, 9, 15, tzinfo=UTC)


def _counter(tenant, actor):
    with seeding_ctx(tenant):
        centre = content_models.ServiceCentre.objects.create(
            tenant=tenant, slug="main-office", name="Main office", address="101 Bend Road"
        )
    return counters.open_counter(
        actor, service_centre_id=centre.slug, opening_float=D("200.0000"), opened_at=OPENED
    )


def test_pay_g_q3__rosas_68_cash_receipt_carries_every_listed_fact(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-ROSA-68")
        customer_models.Contact.objects.create(
            tenant=brazos, account=account, full_name="Rosa Delgado", is_primary=True
        )
        an_issued_bill(
            brazos, account, number="BL-2610-0068", total=D("100.00"), issued_on=date(2026, 10, 1)
        )
        opened = _counter(brazos, dana)
        session_id = opened.session.pk
        recorded = services.record_payment(
            dana,
            account_id=account.pk,
            amount=ROSA,
            method_code="cash",
            posted_at=PAID,
            idempotency_reference=uuid.uuid4(),
            counter_session_id=session_id,
        )

    response = api_call(
        detail_api.payment_receipt_print,
        "get",
        f"/api/brazos/payments/{recorded.payment_id}/receipt/print",
        user=dana.user,
        role=dana.role,
        tenant=brazos,
        payment_id=str(recorded.payment_id),
    )
    assert response.status_code == 200, response.data
    body = response.data
    assert body["payment_no"] and body["payment_no"] == recorded.payment_no
    assert body["account_no"] == "A-ROSA-68"
    assert body["customer_name"] == "Rosa Delgado"
    assert D(body["amount"]) == ROSA and body["currency"] == "USD"
    assert (body["method_name"] or "").lower() == "cash"
    assert [b["number"] for b in body["bills"]] == ["BL-2610-0068"]
    assert D(body["bills"][0]["amount"]) == ROSA
    # The BOOKS' figure (`receipts._ar_balance`, the receipt email's own) —
    # $32.00 on a posted $100.00 bill; this fixture issues its bill without
    # posting it to AR, so here it is what the payment posted. Never invented.
    from apps.payments import receipts

    with tenant_ctx(brazos):
        books = receipts._ar_balance(account.pk)
    assert (body["balance"] is None) == (books is None)
    if books is not None:
        assert D(body["balance"]) == books
    assert body["posted_at"].startswith("2026-10-30")
    if session_id is not None:
        assert body["counter"] and body["counter"].startswith("CTR-")
        assert body["taken_by"]
    # B14 rule 31: the id rides only in `payment_id`.
    others = {k: v for k, v in body.items() if k != "payment_id"}
    assert str(recorded.payment_id) not in str(others)
