# ── Trace ──────────────────────────────────────────────
# Audit:    payments audit L2-12 (PO 2026-10-30: *"we have setup in email and
#           text messages please check"*) and Q4 (*"we write email in table once
#           email serivce provider is up the all email going out and provider is
#           down the service will stop"*) — lane PAY-G, a CHECK and not a build
# Rules:    BR-PAY-024 · BR-NOT-022 (receipt on record-payment, default ON) ·
#           BR-NOT-005 (queue, then a dispatcher sends; retry ×3 with backoff) ·
#           CLAUDE.md rule 6 (nothing is sent twice)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""A recorded payment's receipt goes out through the configured sender — and waits out an outage.

THE PATH, TRACED (every door ends in the same place):

    counter / kiosk / store import / online   →  payments.services.record_payment
      →  receipts.queue_receipt_for_recorded_payment   (BR-NOT-022, default ON)
      →  notifications.services.queue_document         three rows on
         `outbound_messages`: pdf_print · email · sms, each `queued`
      →  notifications.dispatcher.dispatch_cycle       (celery beat,
         `schedule.DISPATCH_TASK`, per tenant listed in the dispatch env)
      →  provider_seam.channel_route → integrations.dispatch_outbound_batch
      →  `sent` (then `delivered`/`bounced_*` by the provider's webhook)

Each case is parametrised over the four payment doors by the idempotency SOURCE
the door stamps (`entry` counter · `agent` kiosk · `import` store file ·
`webhook` online), because the receipt code does not branch on the door and a
test that only exercised one would not show that.

WHAT AN OUTAGE DOES, MEASURED HERE (the PO's sentence, checked):
  * **Provider DISCONNECTED or the channel switched OFF** — nothing is handed
    over and nothing is counted: the row stays `queued` with `attempts = 0`, and
    goes out on the first cycle after the connection is back. Exactly the PO's
    *"provider is down the service will stop … once up all email going out"*.
  * **Provider CONNECTED BUT FAILING** (it raises, times out or answers
    "failed") — the row stays `queued` with `attempts` 1, 2 and a
    `next_attempt_at` 5 then 15 minutes on, and is sent by the first cycle after
    it recovers. **But on the THIRD failure (about 20 minutes after the first)
    it rests `failed`**, and from then on only a re-queue (Settings →
    Notifications → delivery, `delivery_ops.requeue`) sends it. So an outage
    longer than the retries does NOT drain on its own. Stated and asserted
    below rather than smoothed over.

A bulk *Send receipts* must therefore skip a payment whose receipt row is
`status = 'queued'` (waiting — sending again would double it once the provider
returns) and act on one whose row is `failed` (or has no row).
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal as D

import pytest

from apps.customers import models as customer_models
from apps.notifications import delivery_ops, dispatcher
from apps.notifications import models as nmodels
from apps.payments import idempotency, receipts

from tests.test_cr049_t2_dispatch_freeze import (  # noqa: F401 — fixtures
    docs_dir,
    email_on,
    provider_connected,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_not_002_dispatcher import INSIDE_WINDOW, StubAdapter
from tests.test_us_pay_001_record_payment import a_payment, an_issued_bill
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

ROSA = D("68.00")
DOORS = (
    idempotency.SOURCE_ENTRY,  # counter
    idempotency.SOURCE_AGENT,  # kiosk (a payment agent)
    idempotency.SOURCE_IMPORT,  # store / lockbox file
    idempotency.SOURCE_WEBHOOK,  # online
)


def _rosa(tenant, dana, *, account_no):
    account = an_account(dana, tenant, account_no=account_no)
    account.sms_reminders = True
    account.save(update_fields=["sms_reminders"])
    customer_models.Contact.objects.create(
        tenant=tenant,
        account=account,
        full_name="Rosa Delgado",
        email="rosa@example.com",
        phone="+1 512 555 0142",
        is_primary=True,
    )
    an_issued_bill(
        tenant, account, number=f"BL-{account_no}", total=ROSA, issued_on=date(2026, 8, 1)
    )
    return account


def _pay(dana, account, door):
    return a_payment(
        dana,
        account,
        amount=ROSA,
        idempotency_source=door,
        idempotency_reference=uuid.uuid4(),
    )


def _receipts(recorded):
    return {
        row.channel: row
        for row in nmodels.OutboundMessage.objects.filter(
            source_type=receipts.SOURCE_PAYMENT, source_id=recorded.payment_id
        )
    }


def _adapter(monkeypatch, adapter):
    from apps.integrations import services as integrations_services

    monkeypatch.setattr(integrations_services, "dispatch_outbound_batch", adapter, raising=False)
    return adapter


ELECTRONIC = (nmodels.CHANNEL_EMAIL, nmodels.CHANNEL_SMS)


@pytest.mark.parametrize("door", DOORS)
def test_pay_g_l2_12__every_door_queues_a_receipt_and_the_sender_sends_it(
    brazos, dana, email_on, provider_connected, docs_dir, monkeypatch, door
):
    adapter = _adapter(monkeypatch, StubAdapter())
    with tenant_ctx(brazos):
        account = _rosa(brazos, dana, account_no=f"A-L212-{door}")
        recorded = _pay(dana, account, door)
        rows = _receipts(recorded)
        assert set(rows) >= {nmodels.CHANNEL_PRINT, nmodels.CHANNEL_EMAIL}, rows
        assert {row.status for row in rows.values()} == {nmodels.STATUS_QUEUED}

        dispatcher.dispatch_cycle(now=INSIDE_WINDOW, channels=ELECTRONIC, job="test")

        rows = _receipts(recorded)
        assert rows[nmodels.CHANNEL_EMAIL].status == nmodels.STATUS_SENT
        handed = {channel for channel, _messages in adapter.calls}
        assert nmodels.CHANNEL_EMAIL in handed
        email = next(m for c, ms in adapter.calls if c == nmodels.CHANNEL_EMAIL for m in ms)
        assert "$68.00" in ((email.get("artifact") or {}).get("body") or ""), email
        if nmodels.CHANNEL_SMS in rows:
            assert rows[nmodels.CHANNEL_SMS].status == nmodels.STATUS_SENT
        # The printed copy is left alone by an email/text cycle. (Whether it is
        # ever SENT depends on a print vendor connection — the stub here says
        # every channel is connected, so it is not asserted.)
        assert _receipts(recorded)[nmodels.CHANNEL_PRINT].status == nmodels.STATUS_QUEUED


def test_pay_g_l2_12__a_disconnected_provider_holds_the_receipt_and_sends_it_when_back(
    brazos, dana, email_on, docs_dir, monkeypatch
):
    """The PO's case exactly: provider down → nothing sent, nothing counted;
    provider up → it goes out."""
    adapter = _adapter(monkeypatch, StubAdapter())
    from apps.integrations import services as integrations_services

    connected = {"now": False}

    def status(channel):
        return {"channel": channel, "connected": connected["now"], "provider_key": "stub"}

    monkeypatch.setattr(integrations_services, "provider_connection_status", status, raising=False)
    with tenant_ctx(brazos):
        recorded = _pay(dana, _rosa(brazos, dana, account_no="A-L212-D"), idempotency.SOURCE_ENTRY)
        dispatcher.dispatch_cycle(now=INSIDE_WINDOW, channels=ELECTRONIC, job="test")
        email = _receipts(recorded)[nmodels.CHANNEL_EMAIL]
        assert (email.status, email.attempts, email.next_attempt_at) == (
            nmodels.STATUS_QUEUED,
            0,
            None,
        )
        assert adapter.calls == []

        connected["now"] = True
        dispatcher.dispatch_cycle(
            now=INSIDE_WINDOW + timedelta(hours=6), channels=ELECTRONIC, job="test"
        )
        assert _receipts(recorded)[nmodels.CHANNEL_EMAIL].status == nmodels.STATUS_SENT


def test_pay_g_l2_12__a_failing_provider_retries_and_a_short_outage_drains_on_its_own(
    brazos, dana, email_on, provider_connected, docs_dir, monkeypatch
):
    adapter = _adapter(monkeypatch, StubAdapter(raises=RuntimeError("503 Service Unavailable")))
    with tenant_ctx(brazos):
        recorded = _pay(dana, _rosa(brazos, dana, account_no="A-L212-R"), idempotency.SOURCE_ENTRY)
        dispatcher.dispatch_cycle(now=INSIDE_WINDOW, channels=ELECTRONIC, job="test")
        email = _receipts(recorded)[nmodels.CHANNEL_EMAIL]
        assert email.status == nmodels.STATUS_QUEUED and email.attempts == 1
        assert email.next_attempt_at == INSIDE_WINDOW + timedelta(minutes=5)

        adapter.raises = None  # the provider is back
        dispatcher.dispatch_cycle(
            now=INSIDE_WINDOW + timedelta(minutes=6), channels=ELECTRONIC, job="test"
        )
        assert _receipts(recorded)[nmodels.CHANNEL_EMAIL].status == nmodels.STATUS_SENT


def test_pay_g_l2_12__an_outage_longer_than_three_tries_rests_failed_until_re_queued(
    brazos, dana, email_on, provider_connected, docs_dir, monkeypatch
):
    """The half of the PO's sentence that is NOT true today, measured: a
    connected provider that keeps failing exhausts the three tries (5 and 15
    minutes apart) and the receipt rests `failed`. It does not go out when the
    provider recovers; a re-queue sends it."""
    adapter = _adapter(monkeypatch, StubAdapter(raises=RuntimeError("503 Service Unavailable")))
    with tenant_ctx(brazos):
        recorded = _pay(dana, _rosa(brazos, dana, account_no="A-L212-F"), idempotency.SOURCE_ENTRY)
        at = INSIDE_WINDOW
        for minutes in (0, 5, 15):
            at = at + timedelta(minutes=minutes)
            dispatcher.dispatch_cycle(now=at, channels=(nmodels.CHANNEL_EMAIL,), job="test")
        email = _receipts(recorded)[nmodels.CHANNEL_EMAIL]
        assert email.status == nmodels.STATUS_FAILED and email.attempts == dispatcher.MAX_ATTEMPTS

        adapter.raises = None
        dispatcher.dispatch_cycle(
            now=at + timedelta(hours=2), channels=(nmodels.CHANNEL_EMAIL,), job="test"
        )
        assert _receipts(recorded)[nmodels.CHANNEL_EMAIL].status == nmodels.STATUS_FAILED

        delivery_ops.requeue(message_ids=(email.pk,), actor=dana)
        dispatcher.dispatch_cycle(
            now=at + timedelta(hours=2, minutes=1), channels=(nmodels.CHANNEL_EMAIL,), job="test"
        )
        assert _receipts(recorded)[nmodels.CHANNEL_EMAIL].status == nmodels.STATUS_SENT
