# ── Trace ──────────────────────────────────────────────
# Change:   Payments audit Q4 (PO 2026-10-30, *"with bulk option is good ; we
#           write email in table once email serivce provider is up the all email
#           going out and provider is down the service will stop"*) ·
#           DEF-PAY-10747 · lane PAY-J
# Rules:    BR-PAY-024 · BR-PAY-018 · BR-NOT-005 · BR-PAY-031 · BR-PAY-010 ·
#           CLAUDE.md hard rules 4, 6, 7
# Tests:    this file
# ───────────────────────────────────────────────────────
"""Bulk Send receipts and bulk Reapply — the per-payment acts the bar runs.

THE WORKED CASE (the ruling's own): 20 payments ticked on the morning after a
29 Oct email outage. Fifteen receipts are still WAITING in the outbound table
(the provider was disconnected — they go out on their own when it is back);
five FAILED (the provider was up but failing, three tries, then rest). Send
receipts → **5 sent · 15 waiting for the email service** — and the fifteen are
NOT queued again, so the outage never produces two receipts. A payment whose
customer has no email on file is named *no contact on file*.

RED FIRST (law 7): run before `bulk_acts.py` existed, every case here failed on
`ImportError: cannot import name 'bulk_acts'`; with `_receipt_outcome_from_row`
answering None for `queued` (re-queue everything), the 20-payment case fails
`Counter({'sent': 20}) == Counter({'waiting': 15, 'sent': 5})` — measured.
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal as D

import pytest

from apps.customers import models as customer_models
from apps.notifications import dispatcher
from apps.notifications import models as nmodels
from apps.payments import billing_seam, bulk_acts, receipts, services
from apps.payments.exceptions import PaymentRuleError

from tests.test_cr049_t2_dispatch_freeze import (  # noqa: F401 — fixtures
    docs_dir,
    email_on,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_not_002_dispatcher import INSIDE_WINDOW, StubAdapter
from tests.test_us_pay_001_record_payment import a_payment, an_issued_bill
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

AMOUNT = D("68.00")
PAID_AT = datetime(2026, 10, 29, 10, 0, tzinfo=UTC)
TODAY = date(2026, 10, 30)


def _customer(tenant, dana, n, *, email=True):
    account = an_account(dana, tenant, account_no=f"A-PJ-{n:03d}")
    customer_models.Contact.objects.create(
        tenant=tenant,
        account=account,
        full_name=f"Customer {n}",
        email=f"c{n}@example.com" if email else "",
        is_primary=True,
    )
    an_issued_bill(
        tenant, account, number=f"BL-PJ-{n:03d}", total=AMOUNT, issued_on=date(2026, 10, 1)
    )
    return account


def _email_rows(payment_id):
    return nmodels.OutboundMessage.objects.filter(
        source_type=receipts.SOURCE_PAYMENT, source_id=payment_id, channel=nmodels.CHANNEL_EMAIL
    )


def _provider(monkeypatch, *, connected, raises=None):
    from apps.integrations import services as integrations_services

    adapter = StubAdapter(raises=raises)
    monkeypatch.setattr(integrations_services, "dispatch_outbound_batch", adapter, raising=False)
    state = {"connected": connected}
    monkeypatch.setattr(
        integrations_services,
        "provider_connection_status",
        lambda channel: {
            "channel": channel,
            "connected": state["connected"],
            "provider_key": "stub",
        },
        raising=False,
    )
    return adapter, state


def test_pay_j__twenty_ticked_five_sent_fifteen_waiting_none_doubled(
    brazos, dana, email_on, docs_dir, monkeypatch, audit_rows
):
    adapter, state = _provider(monkeypatch, connected=True, raises=RuntimeError("503"))
    with tenant_ctx(brazos):
        # Five recorded while the provider was up but FAILING: three tries, rest.
        failed = [a_payment(dana, _customer(brazos, dana, n), amount=AMOUNT) for n in range(5)]
        at = INSIDE_WINDOW
        for minutes in (0, 5, 15):
            at = at + timedelta(minutes=minutes)
            dispatcher.dispatch_cycle(now=at, channels=(nmodels.CHANNEL_EMAIL,), job="test")
        assert {_email_rows(p.payment_id).get().status for p in failed} == {nmodels.STATUS_FAILED}

        # Fifteen recorded during the OUTAGE (provider disconnected): queued, waiting.
        state["connected"] = False
        waiting = [a_payment(dana, _customer(brazos, dana, n), amount=AMOUNT) for n in range(5, 20)]
        dispatcher.dispatch_cycle(
            now=at + timedelta(hours=1), channels=(nmodels.CHANNEL_EMAIL,), job="t"
        )
        assert {_email_rows(p.payment_id).get().status for p in waiting} == {nmodels.STATUS_QUEUED}

        ticked = failed + waiting
        before = nmodels.OutboundMessage.objects.filter(channel=nmodels.CHANNEL_EMAIL).count()
        outcomes = Counter(
            bulk_acts.send_receipt(actor=dana, payment_id=p.payment_id)["outcome"] for p in ticked
        )
        assert outcomes == Counter({bulk_acts.RECEIPT_SENT: 5, bulk_acts.RECEIPT_WAITING: 15})
        after = nmodels.OutboundMessage.objects.filter(channel=nmodels.CHANNEL_EMAIL).count()
        assert after - before == 5, "only the five failed receipts are queued again"
        for p in waiting:
            assert _email_rows(p.payment_id).count() == 1, "a waiting receipt is never doubled"
        for p in failed:
            rows = list(_email_rows(p.payment_id).order_by("copy_no"))
            assert [(r.copy_no, r.status) for r in rows] == [(0, "failed"), (1, "queued")]

        # Pressed again: the five just queued now WAIT too. Nothing new is written.
        again = Counter(
            bulk_acts.send_receipt(actor=dana, payment_id=p.payment_id)["outcome"] for p in ticked
        )
        assert again == Counter({bulk_acts.RECEIPT_WAITING: 20})
        assert (
            nmodels.OutboundMessage.objects.filter(channel=nmodels.CHANNEL_EMAIL).count() == after
        )

        # The provider comes back: everything queued goes out (the PO's sentence).
        adapter.raises = None
        state["connected"] = True
        dispatcher.dispatch_cycle(
            now=at + timedelta(hours=2), channels=(nmodels.CHANNEL_EMAIL,), job="t"
        )
        for p in waiting:
            assert _email_rows(p.payment_id).get().status == nmodels.STATUS_SENT

        # Hard rule 7 — every press writes its row, waiting ones included.
        bulk_rows = [row for row in audit_rows if row["action"] == bulk_acts.AUDIT_BULK_RECEIPT]
        assert len(bulk_rows) == 40
        assert Counter(row["after"]["outcome"] for row in bulk_rows) == Counter(
            {bulk_acts.RECEIPT_SENT: 5, bulk_acts.RECEIPT_WAITING: 35}
        )


def test_pay_j__no_contact_on_file_is_named_and_nothing_is_queued(
    brazos, dana, email_on, docs_dir, monkeypatch
):
    _provider(monkeypatch, connected=False)
    with tenant_ctx(brazos):
        ben = a_payment(dana, _customer(brazos, dana, 50, email=False), amount=AMOUNT)
        before = _email_rows(ben.payment_id).count()
        assert bulk_acts.send_receipt(actor=dana, payment_id=ben.payment_id)["outcome"] == (
            bulk_acts.RECEIPT_NO_CONTACT
        )
        assert _email_rows(ben.payment_id).count() == before


def test_pay_j__a_payment_with_no_receipt_at_all_is_queued_through_the_first_time_path(
    brazos, dana, email_on, docs_dir, monkeypatch
):
    _provider(monkeypatch, connected=False)
    with tenant_ctx(brazos):
        paid = a_payment(dana, _customer(brazos, dana, 60), amount=AMOUNT)
        # Recorded while receipts were switched off: no rows at all.
        nmodels.OutboundMessage.objects.filter(source_id=paid.payment_id).delete()
        assert bulk_acts.send_receipt(actor=dana, payment_id=paid.payment_id)["outcome"] == (
            bulk_acts.RECEIPT_SENT
        )
        assert _email_rows(paid.payment_id).get().copy_no == 0


# ── Reapply ────────────────────────────────────────────────────────────────


def _cheque_before_its_bill(dana, tenant, n):
    """A lockbox cheque that arrived before the bill it pays: held as credit."""
    account = an_account(dana, tenant, account_no=f"A-PJR-{n:03d}")
    paid = services.record_payment(
        dana,
        account_id=account.pk,
        amount=D("76.40"),
        posted_at=PAID_AT,
        cleared_at=PAID_AT,
        method_code="cash",
        idempotency_reference=uuid.uuid4(),
    )
    bill = an_issued_bill(
        tenant, account, number=f"BL-PJR-{n:03d}", total=D("76.40"), issued_on=date(2026, 10, 30)
    )
    return account, paid, bill


def test_pay_j__reapply_moves_each_cheques_held_credit_onto_its_newer_bill(brazos, dana):
    with tenant_ctx(brazos):
        five = [_cheque_before_its_bill(dana, brazos, n) for n in range(5)]
        for _account, paid, bill in five:
            assert billing_seam.allocated_so_far(bill.pk) == D("0")
            out = bulk_acts.reapply_held(actor=dana, payment_id=paid.payment_id, on_date=TODAY)
            assert out["outcome"] == bulk_acts.REAPPLIED
            assert D(out["applied_total"]) == D("76.40")
            assert out["bills"] == [bill.invoice_no]
            assert billing_seam.allocated_so_far(bill.pk) == D("76.40")
            # Pressed again: nothing held, nothing moved.
            again = bulk_acts.reapply_held(actor=dana, payment_id=paid.payment_id, on_date=TODAY)
            assert again["outcome"] == bulk_acts.NOTHING_TO_REAPPLY
            assert billing_seam.allocated_so_far(bill.pk) == D("76.40")


def test_pay_j__a_fully_applied_payment_has_nothing_to_reapply(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-PJR-FULL")
        bill = an_issued_bill(
            brazos, account, number="BL-PJR-FULL", total=AMOUNT, issued_on=date(2026, 10, 1)
        )
        paid = a_payment(dana, account, amount=AMOUNT)
        assert billing_seam.allocated_so_far(bill.pk) == AMOUNT
        out = bulk_acts.reapply_held(actor=dana, payment_id=paid.payment_id, on_date=TODAY)
        assert out["outcome"] == bulk_acts.NOTHING_TO_REAPPLY


def test_pay_j__held_credit_with_no_open_bill_says_so(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-PJR-NONE")
        paid = a_payment(dana, account, amount=AMOUNT)
        out = bulk_acts.reapply_held(actor=dana, payment_id=paid.payment_id, on_date=TODAY)
        assert out["outcome"] == bulk_acts.NO_OPEN_BILL


def test_pay_j__a_payment_the_clerk_may_not_reapply_is_refused_by_name(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-PJR-DEP")
        an_issued_bill(
            brazos, account, number="BL-PJR-DEP", total=AMOUNT, issued_on=date(2026, 10, 1)
        )
        deposit = a_payment(dana, account, amount=D("150.00"), purpose="deposit")
        with pytest.raises(PaymentRuleError, match="deposit"):
            bulk_acts.reapply_held(actor=dana, payment_id=deposit.payment_id, on_date=TODAY)


def test_pay_j__the_two_doors_are_mounted_and_answer_per_payment(brazos, dana):
    """The HTTP doors: 200 with an outcome; a missing day is refused, never read off a clock."""
    from django.urls import resolve

    from apps.payments import bulk_acts_api
    from tests.test_us_ten_helpers import api_call

    assert resolve("/api/v1/payments/P-1/bulk-receipt").func is bulk_acts_api.payment_bulk_receipt
    assert resolve("/api/v1/payments/P-1/bulk-reapply").func is bulk_acts_api.payment_bulk_reapply
    with tenant_ctx(brazos):
        _account, paid, _bill = _cheque_before_its_bill(dana, brazos, 90)

    def call(data):
        return api_call(
            bulk_acts_api.payment_bulk_reapply,
            "post",
            user=dana.user,
            role="system_admin",
            tenant=brazos,
            data=data,
            payment_id=str(paid.payment_id),
        )

    missing = call({})
    assert missing.status_code in (400, 422), missing.data
    ok = call({"on_date": "2026-10-30"})
    assert ok.status_code == 200, ok.data
    assert ok.data["outcome"] == bulk_acts.REAPPLIED
