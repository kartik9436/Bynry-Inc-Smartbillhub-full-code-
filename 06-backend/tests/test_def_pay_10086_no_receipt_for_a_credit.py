# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-10086 (J-FIX-TWENTY S6, 2026-10-12)
# Change:   CR-180-BRC10 walk — a goodwill credit is not a payment received
# ───────────────────────────────────────────────────────
"""A goodwill concession is recorded as a NON-CASH credit row, and must not
send the customer a *payment received* receipt. Walked: a $40.00 goodwill on
BL-2610-000098 queued print, email and SMS receipts for a $40.00 "payment"
beside the right *credit issued* notice. A real payment still gets its receipt
— the control that proves this test can tell the two apart."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.notifications import models as notification_models
from apps.payments import services

from tests.test_cr059_cs35_cs38_credit_rows import a_concession, a_gt6_bill
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db


def _receipts(payment_id) -> int:
    return notification_models.OutboundMessage.objects.filter(
        source_id=payment_id, event_key="payment_received"
    ).count()


def test_def_pay_10086_a_goodwill_credit_queues_no_payment_receipt(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_gt6_bill(brazos, account)
        credit = a_concession(dana, account, amount=Decimal("40.00"))
        assert _receipts(credit.payment_id) == 0, "a concession is not money received"


def test_def_pay_10086_control_a_real_payment_still_gets_its_receipt(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        a_gt6_bill(brazos, account)
        paid = services.record_payment(
            dana,
            account_id=account.pk,
            amount=Decimal("40.00"),
            posted_at=datetime(2026, 8, 20, 10, 0, tzinfo=UTC),
            cleared_at=datetime(2026, 8, 20, 10, 0, tzinfo=UTC),
            confirmation="4471",
            idempotency_reference=uuid.uuid4(),
        )
        assert _receipts(paid.payment_id) >= 1
