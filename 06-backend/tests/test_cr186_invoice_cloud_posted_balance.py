# ── Trace ──────────────────────────────────────────────
# Change:  CR-186-BRC10 · T15–T18 — Invoice Cloud make-payment saved `posted`,
#          applied at posting, and the NEXT consumer-info call shows the new
#          balance. `consumer-info` has no formula of its own: it is
#          `billing.open_balance`, which reads `payments.balance_rule`.
# Ruling:  decision log 2026-10-21 — *"Invoice Cloud real-time balance and
#          immediate posting: four rulings"* (ruling 1, `posted`) and *"The
#          payment lifecycle, stated by the PO for every method"* (rulings 3,
#          4 and 6). Shown to the PO: $150.00 bill, $120.00 posted → $30.00;
#          a $20.00 refund → $50.00; a cancelled payment never counts.
# Rules:   BR-INT-083 · BR-BIL-035 · CLAUDE.md hard rule 2 (the wire carries
#          four places as a string)
# ───────────────────────────────────────────────────────
"""The partner pays, and the partner's next read sees it.

Invoice Cloud's two asks were one loop: `make-payment` applies to the bill
immediately, and `consumer-info` returns the latest outstanding balance. Each
half was tested alone; this file is the loop, end to end, through the real
door both times with one key.

⚠ **THIS DEPENDS ON LANE PAY-CORE'S `record_payment` WRITING `posted` AT
ENTRY AND APPLYING THEN** (CR-186-BRC10 T5). Before that lands the payment is
`processing`, meets no bill, and the first case reads 150.0000 — which is the
pre-ruling behaviour this file exists to retire, and is red on purpose.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.integrations import partner_api, shapes
from apps.integrations.runners import serve

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_int_041_partner_surface import ALLOWED_ADDRESS, _bytes
from tests.test_invoice_cloud_make_payment import (
    ACCOUNT_NO,
    BILL_NO,
    KEY,
    _account,
    _body,
    _connect,
    _issue,
    _payments,
    _post,
)

pytestmark = pytest.mark.django_db

IC_RECORDS = shapes.INVOICE_CLOUD.envelope["records"]


def _consumer_info(tenant, *, key=KEY):
    from rest_framework.test import APIRequestFactory

    from core import tenancy as core_tenancy

    serve.reset_partner_limits()
    request = APIRequestFactory().get(
        f"/api/{tenant.subdomain}/partner/v1/consumer-info",
        {"consumer_id": ACCOUNT_NO},
        REMOTE_ADDR=ALLOWED_ADDRESS,
    )
    request.META["HTTP_AUTHORIZATION"] = f"Bearer {key}"
    request.tenant_id = tenant.id
    with core_tenancy.tenant_context(tenant.id):
        response = partner_api.partner_consumer_info(request)
    assert response.status_code == 200, _bytes(response)
    return json.loads(_bytes(response))[IC_RECORDS][0]["opening_balance"]


@pytest.fixture()
def a_150_bill(brazos, dana):
    serve.reset_partner_limits()
    with tenant_ctx(brazos):
        _connect(brazos, dana)
        account = _account(brazos, dana)
        invoice = _issue(brazos, account, total="150.0000")
    return account, invoice


def _pay(tenant, amount, reference):
    serve.reset_partner_limits()
    response = _post(
        tenant, body=_body(amount=amount, payment_reference=reference, bill_id=BILL_NO)
    )
    assert response.status_code == 200, _bytes(response)
    return json.loads(_bytes(response))


def test_120_posted_against_a_150_bill_reads_30_on_the_next_consumer_info(brazos, a_150_bill):
    assert _consumer_info(brazos) == "150.0000"
    reply = _pay(brazos, "120.00", "TID186001")
    assert reply["status"] == "posted", reply
    assert _consumer_info(brazos) == "30.0000", (
        "Invoice Cloud posted $120 and its next consumer-info call still shows the old balance"
    )


def test_a_20_refund_after_it_makes_50(brazos, dana, a_150_bill):
    from apps.payments import models as payment_models

    account, _invoice = a_150_bill
    _pay(brazos, "120.00", "TID186002")
    with tenant_ctx(brazos):
        payment_models.Refund.objects.create(
            tenant=brazos,
            account=account,
            amount=Decimal("20.00"),
            currency="USD",
            status=payment_models.REFUND_ISSUED,
            issued_at=timezone.now(),
        )
    assert _consumer_info(brazos) == "50.0000"


def test_a_cancelled_payment_never_counts(brazos, dana, a_150_bill):
    """Cancel is allowed from `posted` (PO 2026-10-21); it writes a reversing
    row, and neither row is counted. Back to $150.00."""
    from apps.payments import cancel

    _pay(brazos, "120.00", "TID186003")
    with tenant_ctx(brazos):
        payment = _payments(brazos).get()
        cancel.cancel_payment(
            actor=dana,
            payment_id=payment.pk,
            reason=cancel.CANCEL_REASON_DUPLICATE,
            cancelled_on=datetime.combine(timezone.now().date(), datetime.min.time()).replace(
                tzinfo=timezone.get_current_timezone()
            ),
            note="sent twice",
        )
    assert _consumer_info(brazos) == "150.0000"


def test_another_utility_never_sees_this_balance(brazos, lonestar, dana, a_150_bill):
    """The read stays one utility's: a Lone Star account with the same number
    and no money reads its own bill, never Brazos' payment."""
    from apps.payments import billing_seam

    account, _invoice = a_150_bill
    _pay(brazos, "120.00", "TID186004")
    with tenant_ctx(lonestar):
        assert billing_seam.payments_received_for_account(account.pk) == Decimal("0")
