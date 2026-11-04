# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-10530 — a single/one-time bill's Email row stayed
#           "Waiting · 0 tries" forever (PO report, AC-2026-00071)
# Ruling:   PO 2026-10-22 (decision log "Bill emails stuck at 'Waiting · 0
#           tries' are marked FAILED, not sent") — *"mark them failed"*; email
#           pins `email_bill_ready`, a text `sms_bill_ready`, print and portal
#           keep the bill layout
# Rules:    BR-BIL-016 · BR-BIL-026 (pinned at queue time) · BR-NOT-005
#           (forward-only; retry) · CLAUDE.md hard rules 1, 7 · law 14
# Tests:    this file
# ───────────────────────────────────────────────────────
"""A bill's email is pinned to its WORDING, and a message that cannot render FAILS.

REPRODUCED BEFORE THE FIX (law 7), through the real one-time Send with delivery
*Email*, a connected (fake) SendGrid and three dispatch cycles:

    ROW pdf_print queued 0 None 01a164b1-… 1 None
    ROW email     queued 0 None 01a164b1-… 1 None      ← the bill LAYOUT's id
    ROW portal    queued 0 None 01a164b1-… 1 None
    PROBLEMS ['provider_status_unknown', 'render_held_missing_template',
              'channel_dispatch_deferred', 'render_held_missing_template']

The email row carried `template_code=None` and the bill layout's
`BillTemplateVersion` id; `load_pinned` found no notification version with that
id, the render was refused, and `_release(rows, reason=None)` gave it back with
its try reset — *Waiting · 0 tries* after every cycle.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):
  * asserting only that an email row EXISTS — it always did. Each case asserts
    the row's `template_code` and that its pin LOADS as a notification version;
  * asserting `status != "queued"` — `failed` would pass it. The send case
    asserts `sent` AND that the provider was handed the bill wording's subject;
  * a fixture whose print row happened to lose its pin too — the print and
    portal rows are asserted to carry the invoice's own layout id.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.apps import apps as django_apps
from django.db import connection

from apps.audit import models as audit_models
from apps.billing import delivery_seam
from apps.billing import models as billing_models
from apps.customers import models as customer_models
from apps.notifications import dispatch_config, dispatcher, services, template_service
from apps.notifications import models as outbound
from tests.test_def_not_10420_email_payload import SENDGRID_FIELDS
from tests.test_otb_a_one_time_api_contract import (  # noqa: F401 — autouse fixture
    _a_fee_draft,
    _clerk,
    _send,
    _the_unit_bills_on_a_cycle,
)
from tests.test_us_int_helpers_b import post_connect
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · lonestar
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: 15:00 UTC is 10:00 in America/Chicago — inside Brazos Bend's seeded window.
INSIDE_WINDOW = datetime(2026, 8, 9, 15, 0, tzinfo=UTC)

_migration = __import__(
    "apps.notifications.migrations.0027_def_bil_10530_fail_stuck_bill_emails",
    fromlist=["fail_stuck", "stuck_rows", "REASON"],
)


def _loads(row) -> bool:
    try:
        template_service.load_pinned(template_id=row.template_id, version=row.template_version)
    except template_service.TemplateRefused:
        return False
    return True


def _rows(source_id):
    return {
        row.channel: row for row in outbound.OutboundMessage.objects.filter(source_id=source_id)
    }


@pytest.fixture
def sendgrid(brazos, dana, monkeypatch):
    from apps.integrations import esp_fixtures as fixtures
    from apps.integrations.adapters import esp_email

    transport = fixtures.sendgrid_transport()
    monkeypatch.setattr(esp_email, "_urllib_transport", transport)
    connected = post_connect(brazos, dana, "sendgrid", SENDGRID_FIELDS)
    assert connected.status_code in (200, 201), getattr(connected, "data", connected)
    with tenant_ctx(brazos):
        dispatch_config.update_dispatch_settings(actor=dana, email_dispatch_active=True)
    return transport


def _email_contact(tenant, account_id, address="daniel@example.test"):
    customer_models.Contact.objects.create(
        tenant=tenant,
        account_id=account_id,
        full_name="Daniel Thomas",
        email=address,
        is_primary=True,
    )


# ══════════════════════════════════════════════════════════════════════════
# THE REPORTED PATH — Billing → Bills → Create single/one-time bill, Email
# ══════════════════════════════════════════════════════════════════════════


def test_def_bil_10530_tc1__a_one_time_bills_email_pins_its_wording_and_is_sent(
    brazos, dana, sendgrid
):
    user = _clerk(brazos)
    draft = _a_fee_draft(brazos, dana, user)
    with tenant_ctx(brazos):
        invoice = billing_models.Invoice.objects.get(pk=draft["invoice_id"])
        _email_contact(brazos, invoice.account_id)
    sent = _send(brazos, user, draft["run_id"])
    assert sent.status_code == 201, sent.data

    with tenant_ctx(brazos):
        invoice.refresh_from_db()
        rows = _rows(invoice.pk)
        assert sorted(rows) == ["email", "pdf_print", "portal"]
        email = rows["email"]
        assert email.template_code == "email_bill_ready"
        assert _loads(email), "the email's pin must be a notification template version"
        assert email.template_id != invoice.template_id
        # Print and the portal carry the DOCUMENT and keep the bill layout.
        for channel in ("pdf_print", "portal"):
            assert rows[channel].template_id == invoice.template_id, channel
            assert rows[channel].template_version == invoice.template_version, channel

        dispatcher.dispatch_cycle(now=INSIDE_WINDOW, channels=(outbound.CHANNEL_EMAIL,))
        email.refresh_from_db()
        assert email.status == outbound.STATUS_SENT, (email.status, email.last_error)
        assert email.attempts == 1

    sends = [one for one in sendgrid.sent if one[1].endswith("/v3/mail/send")]
    assert len(sends) == 1
    subject = sends[0][3]["subject"]
    assert subject.startswith("Your ") and "bill is ready" in subject, subject


def test_def_bil_10530_tc2__print_and_portal_rows_are_unchanged_by_a_cycle(brazos, dana, sendgrid):
    """The document channels still behave exactly as before: print is not
    dispatchable on this deployment and the portal row is handed back with no
    try spent and nothing written in *What went wrong*."""
    user = _clerk(brazos)
    draft = _a_fee_draft(brazos, dana, user)
    with tenant_ctx(brazos):
        invoice = billing_models.Invoice.objects.get(pk=draft["invoice_id"])
        _email_contact(brazos, invoice.account_id)
    assert _send(brazos, user, draft["run_id"]).status_code == 201
    with tenant_ctx(brazos):
        for _ in range(2):
            dispatcher.dispatch_cycle(now=INSIDE_WINDOW)
        rows = _rows(invoice.pk)
        for channel in ("pdf_print", "portal"):
            row = rows[channel]
            assert row.status == outbound.STATUS_QUEUED, channel
            assert row.attempts == 0, channel
            assert row.last_error is None, channel


# ══════════════════════════════════════════════════════════════════════════
# EVERY OTHER BILL PATH — they all reach `queue_bill_delivery`
# ══════════════════════════════════════════════════════════════════════════


def _a_bill(account_id, *, corrects=None):
    """The row `queue_bill_delivery` is handed — what `issue_invoice` (bill run,
    one-time, final bill), the correction rebill and Fix-a-bill's re-issue all
    pass it. Only the attributes the seam reads."""
    return SimpleNamespace(
        pk=uuid4(),
        invoice_no="BL-10530-000001",
        account_id=account_id,
        template_id=uuid4(),  # a bill LAYOUT id — not a notification template
        template_version=1,
        corrects_invoice_id=corrects,
        bill_payload={},
        period_start=None,
        period_end=None,
        due_date=None,
        total=None,
    )


@pytest.mark.parametrize(
    ("corrects", "expected"),
    [(None, "email_bill_ready"), ("corrected", "email_corrected_bill")],
)
def test_def_bil_10530_tc3__every_bill_path_pins_the_events_wording(
    brazos, dana, monkeypatch, corrects, expected
):
    from tests.test_cr048_a1_rule_at_queue_time import an_account

    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-10530")
        _email_contact(brazos, account.pk)
        bill = _a_bill(account.pk, corrects=uuid4() if corrects else None)
        with delivery_seam.clerk_delivery_choice("email"):
            delivery_seam.queue_bill_delivery(bill, actor=dana)
        rows = _rows(bill.pk)
        assert rows["email"].template_code == expected
        assert _loads(rows["email"])
        assert rows["pdf_print"].template_id == bill.template_id


def test_def_bil_10530_tc4__a_text_pins_sms_bill_ready_even_on_a_corrected_bill():
    calls = []

    class Pin:
        def __init__(self, code):
            calls.append(code)
            self.code = code

    real = delivery_seam._resolve

    def fake_resolve(module, attribute, kind):
        if attribute == delivery_seam.WORDING_CLASS_READ:
            catalog = {
                ("bill_ready", "email"): "email_bill_ready",
                ("bill_ready", "sms"): "sms_bill_ready",
                ("bill_corrected", "email"): "email_corrected_bill",
            }
            return lambda event, channel: catalog.get((event, channel))
        return real(module, attribute, kind)

    import unittest.mock as mock

    with mock.patch.object(delivery_seam, "_resolve", fake_resolve):
        pins = delivery_seam._wording_pins(Pin, "bill_corrected")
    assert {c: p.code for c, p in pins.items()} == {
        "email": "email_corrected_bill",
        "sms": "sms_bill_ready",
    }


def test_def_bil_10530_tc5__the_wording_class_is_the_catalogues_and_costs_no_query(
    brazos, django_assert_num_queries
):
    with tenant_ctx(brazos), django_assert_num_queries(0):
        assert services.template_class_for_event("bill_ready", "email") == "email_bill_ready"
        assert services.template_class_for_event("bill_ready", "sms") == "sms_bill_ready"
        assert services.template_class_for_event("bill_corrected", "email") == (
            "email_corrected_bill"
        )
        assert services.template_class_for_event("bill_corrected", "sms") is None
        assert services.template_class_for_event("bill_ready", "portal") is None
        assert services.template_class_for_event("no_such_event", "email") is None


# ══════════════════════════════════════════════════════════════════════════
# THE SILENT LOOP — a message that cannot render FAILS, by name
# ══════════════════════════════════════════════════════════════════════════


def _stuck_email(tenant, *, source_type="invoice", channel="email", address="x@example.test"):
    return outbound.OutboundMessage.objects.create(
        tenant=tenant,
        source_type=source_type,
        source_id=uuid4(),
        channel=channel,
        copy_no=0,
        template_code=None,
        template_id=uuid4(),  # names no notification template version
        template_version=1,
        recipient_address=address,
        status=outbound.STATUS_QUEUED,
    )


def test_def_bil_10530_tc6__an_unrenderable_email_fails_with_its_reason_and_stops(
    brazos, dana, sendgrid, audit_rows
):
    with tenant_ctx(brazos):
        row = _stuck_email(brazos, source_type="move")
        first = dispatcher.dispatch_cycle(now=INSIDE_WINDOW, channels=(outbound.CHANNEL_EMAIL,))
        handed = [one for one in audit_rows if one["action"] == dispatcher.AUDIT_ACTION]
        assert [one["after"]["failed"] for one in handed] == [1], "hard rule 7 — audited"
        row.refresh_from_db()
        assert row.status == outbound.STATUS_FAILED
        assert row.last_error == dispatcher.RENDER_FAILED_REASON == "template_not_resolved"
        assert row.attempts == 1, "the try was made and failed — it is counted"
        assert dispatcher.CYCLE_RENDER_FAILED in {p["code"] for p in first.problems}
        assert first.batches[0].failed == 1

        dispatcher.dispatch_cycle(now=INSIDE_WINDOW, channels=(outbound.CHANNEL_EMAIL,))
        row.refresh_from_db()
        assert (row.status, row.attempts) == (outbound.STATUS_FAILED, 1), "never looped"
    assert not [one for one in sendgrid.sent if one[1].endswith("/v3/mail/send")]


def test_def_bil_10530_tc7__a_portal_row_that_cannot_render_is_still_released(brazos):
    with tenant_ctx(brazos):
        row = _stuck_email(brazos, channel="portal", address="AC-10530")
        dispatcher.dispatch_cycle(now=INSIDE_WINDOW, channels=(outbound.CHANNEL_PORTAL,))
        row.refresh_from_db()
        assert (row.status, row.attempts, row.last_error) == (outbound.STATUS_QUEUED, 0, None)


# ══════════════════════════════════════════════════════════════════════════
# THE ROWS ALREADY STUCK — marked failed once, audited, never sent
# ══════════════════════════════════════════════════════════════════════════


def _run_migration():
    _migration.fail_stuck(django_apps, SimpleNamespace(connection=connection))


def test_def_bil_10530_tc8__the_migration_fails_stuck_rows_once_and_audits_each(
    brazos, lonestar, dana
):
    with tenant_ctx(brazos):
        stuck = _stuck_email(brazos)
        stuck_sms = _stuck_email(brazos, channel="sms", address="+15125550100")
        print_row = _stuck_email(brazos, channel="pdf_print", address="1 Main St")
        portal_row = _stuck_email(brazos, channel="portal", address="AC-1")
        healthy = services.queue_document(
            source_type="move",
            source_id=uuid4(),
            channels=(outbound.CHANNEL_EMAIL,),
            template=services.TemplatePin(code="email_welcome"),
            recipients=(
                services.Recipient(channel=outbound.CHANNEL_EMAIL, address="ok@example.test"),
            ),
            actor=dana,
        )
        healthy_row = outbound.OutboundMessage.objects.get(pk=healthy.messages[0].id)
        assert _loads(healthy_row)
    with tenant_ctx(lonestar):
        theirs = _stuck_email(lonestar)

    _run_migration()

    for tenant, row, expected in (
        (brazos, stuck, "failed"),
        (brazos, stuck_sms, "failed"),
        (brazos, print_row, "queued"),
        (brazos, portal_row, "queued"),
        (brazos, healthy_row, "queued"),
        (lonestar, theirs, "failed"),
    ):
        with tenant_ctx(tenant):
            row.refresh_from_db()
            assert row.status == expected, (row.channel, row.status)
            if expected == "failed":
                assert row.last_error == _migration.REASON
                assert row.sent_at is None, "marked failed — never sent"
                audits = audit_models.AuditLog.objects.filter(
                    tenant_id=tenant.id, action="outbound_message.failed", entity_id=row.pk
                )
                assert audits.count() == 1
                assert audits.first().after["last_error"] == _migration.REASON

    _run_migration()  # idempotent
    with tenant_ctx(brazos):
        assert (
            audit_models.AuditLog.objects.filter(
                tenant_id=brazos.id, action="outbound_message.failed"
            ).count()
            == 2
        )


def test_def_bil_10530_tc9__one_tenants_stuck_rows_are_not_anothers(brazos, lonestar):
    """Hard rule 1: the finder is scoped by tenant in its own query."""
    with tenant_ctx(lonestar):
        theirs = _stuck_email(lonestar)
    with tenant_ctx(brazos):
        mine = _stuck_email(brazos)
        found = {row.pk for row in _migration.stuck_rows(django_apps, brazos.id)}
    assert mine.pk in found and theirs.pk not in found
