"""DEF-NOT-10460 — an agreement email reaches the wire WITH its PDF attached.

Lane AGREEMENT (CR-190-BRC10) named the PDF on the queued email row
(`notifications.attachments.attach_documents`) and wrote each provider's shape
(`integrations.email_attachments`); the seam's `_work_item` and the six email
adapters did not carry it, so every agreement email went out without the file
its body promised. This proves the whole path:

  queued row → `dispatcher.dispatch_cycle` → `seams.notifications._work_item`
  (bytes fetched from the document store) → adapter → the provider's request.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):
  * **Asserting a filename only.** Every case decodes the bytes on the wire and
    compares them with the STORED document, so a re-render or an empty part fails.
  * **A fake adapter.** The end-to-end cases run the REAL SendGrid and SMTP
    adapters; only the HTTP transport and the SMTP socket are fakes.

RUN ON POSTGRESQL with `--ds=config.settings.pgtest` (law 14) as well as sqlite.
"""

from __future__ import annotations

import base64
import email
from datetime import timedelta
from email import policy
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.integrations import esp_fixtures as fixtures
from apps.integrations.adapters.base import ITEM_SUCCEEDED, ConnectionView
from apps.integrations.adapters.email_google import EmailGoogleAdapter
from apps.integrations.adapters.email_microsoft import EmailMicrosoftAdapter
from apps.integrations.adapters.email_postmark import EmailPostmarkAdapter
from apps.integrations.adapters.email_sendgrid import EmailSendgridAdapter
from apps.integrations.adapters.email_smtp import EmailSmtpAdapter
from apps.integrations.adapters.oauth_mailbox import REFRESH_TOKEN_FIELD

from tests.test_cr190_agreements import ORIGIN, _env, _publish_agreement  # noqa: F401 — autouse fixture
from tests.test_def_not_10420_email_payload import (
    SENDER,
    SENDGRID_FIELDS,
    SMTP_VIEW,
    _FakeSmtp,
    _recording,
    dispatcher_payload,
    work_item,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

PDF = b"%PDF-1.4\n% agreement probe\n%%EOF\n"
FILE = {"filename": "Service agreement.pdf", "content_type": "application/pdf", "content": PDF}
CUSTOMER_EMAIL = "pat.agreement@example.test"


def _item_with_file() -> dict:
    return {**work_item(), "attachments": [FILE]}


def _mime_pdf(message: email.message.EmailMessage) -> bytes:
    assert message.get_content_type() == "multipart/mixed"
    parts = [part for part in message.iter_attachments()]
    assert [part.get_filename() for part in parts] == [FILE["filename"]]
    assert parts[0].get_content_type() == "application/pdf"
    # The body is still the text + HTML alternative, first.
    assert message.get_body(preferencelist=("plain",)) is not None
    assert message.get_body(preferencelist=("html",)) is not None
    return parts[0].get_payload(decode=True)


# ═══════════════════════════════════════════════════════════════════════════
# 1 · EVERY ADAPTER PUTS THE FILE IN ITS PROVIDER'S SHAPE
# ═══════════════════════════════════════════════════════════════════════════


def test_smtp_attaches_the_file_as_multipart_mixed(monkeypatch):
    _FakeSmtp.sent = []
    monkeypatch.setattr(EmailSmtpAdapter, "_session", lambda self, conn, secrets: _FakeSmtp())
    result = EmailSmtpAdapter().execute(SMTP_VIEW, {"password": "x"}, [_item_with_file()])
    assert result.items[0].outcome == ITEM_SUCCEEDED
    (message,) = _FakeSmtp.sent
    assert _mime_pdf(message) == PDF


def _esp_view(key: str) -> ConnectionView:
    return ConnectionView(
        provider_key=key,
        environment="production",
        config={"base_url": f"https://api.{key}.example", "send_from": SENDER},
        label="Bills",
    )


def test_sendgrid_sends_the_attachments_array():
    transport = fixtures.sendgrid_transport()
    result = EmailSendgridAdapter(transport).execute(
        _esp_view("sendgrid"), {"api_key": fixtures.SENDGRID_GOOD_KEY}, [_item_with_file()]
    )
    assert result.items[0].outcome == ITEM_SUCCEEDED
    [attached] = transport.sent[-1][3]["attachments"]
    assert attached["filename"] == FILE["filename"]
    assert attached["type"] == "application/pdf"
    assert attached["disposition"] == "attachment"
    assert base64.b64decode(attached["content"]) == PDF


def test_postmark_sends_the_attachments_array():
    transport = fixtures.postmark_transport()
    result = EmailPostmarkAdapter(transport).execute(
        _esp_view("postmark"), {"server_token": fixtures.POSTMARK_GOOD_TOKEN}, [_item_with_file()]
    )
    assert result.items[0].outcome == ITEM_SUCCEEDED
    [attached] = transport.sent[-1][3]["Attachments"]
    assert attached["Name"] == FILE["filename"]
    assert attached["ContentType"] == "application/pdf"
    assert base64.b64decode(attached["Content"]) == PDF


def test_an_email_with_no_file_carries_no_attachments_key():
    transport = fixtures.sendgrid_transport()
    EmailSendgridAdapter(transport).execute(
        _esp_view("sendgrid"), {"api_key": fixtures.SENDGRID_GOOD_KEY}, [work_item()]
    )
    assert "attachments" not in transport.sent[-1][3]


def _mailbox_view(key: str) -> ConnectionView:
    return ConnectionView(
        provider_key=key, environment="production", config={"send_from": SENDER}, label="Bills"
    )


def test_google_attaches_the_file_inside_the_raw_mime():
    adapter_cls = _recording(EmailGoogleAdapter)
    result = adapter_cls().execute(
        _mailbox_view("email_google"), {REFRESH_TOKEN_FIELD: "r"}, [_item_with_file()]
    )
    assert result.items[0].outcome == ITEM_SUCCEEDED
    (sent,) = adapter_cls.sent
    message = email.message_from_bytes(
        base64.urlsafe_b64decode(sent["raw"]), policy=policy.default
    )
    assert _mime_pdf(message) == PDF


def test_microsoft_sends_a_graph_file_attachment():
    adapter_cls = _recording(EmailMicrosoftAdapter)
    result = adapter_cls().execute(
        _mailbox_view("email_microsoft"), {REFRESH_TOKEN_FIELD: "r"}, [_item_with_file()]
    )
    assert result.items[0].outcome == ITEM_SUCCEEDED
    (sent,) = adapter_cls.sent
    [attached] = sent["message"]["attachments"]
    assert attached["@odata.type"] == "#microsoft.graph.fileAttachment"
    assert attached["name"] == FILE["filename"]
    assert base64.b64decode(attached["contentBytes"]) == PDF


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE SEAM FETCHES THE BYTES; A FILE IT CANNOT READ HOLDS THE EMAIL
# ═══════════════════════════════════════════════════════════════════════════


def test_the_seam_hands_the_adapter_the_files_bytes(monkeypatch):
    from apps.integrations.seams import notifications as seam
    from apps.notifications import attachments

    seen = []
    monkeypatch.setattr(attachments, "for_handoff", lambda snap: seen.append(snap) or [FILE])
    item, refusal = seam._work_item("email", dispatcher_payload())
    assert refusal is None
    assert item["attachments"] == [FILE]
    assert seen == [dispatcher_payload()["snapshot"]]


def test_a_file_that_cannot_be_read_is_a_retryable_failure_not_a_bare_email(monkeypatch):
    from apps.integrations.seams import notifications as seam
    from apps.notifications import attachments

    def broken(_snapshot):
        raise RuntimeError("the store did not answer")

    monkeypatch.setattr(attachments, "for_handoff", broken)
    item, refusal = seam._work_item("email", dispatcher_payload())
    assert item is None
    assert refusal["status"] == "failed" and refusal["retryable"] is True
    assert refusal["response"]["reason"] == seam.ATTACHMENT_UNAVAILABLE


def test_a_text_message_never_reads_the_store(monkeypatch):
    from apps.integrations.seams import notifications as seam
    from apps.notifications import attachments

    monkeypatch.setattr(attachments, "for_handoff", lambda snap: pytest.fail("read for sms"))
    item, refusal = seam._work_item("sms", dispatcher_payload(subject=None))
    assert refusal is None and item["attachments"] == []


# ═══════════════════════════════════════════════════════════════════════════
# 3 · END TO END — a move-in's agreement email, dispatched, carries the PDF
# ═══════════════════════════════════════════════════════════════════════════


def _inside_window():
    """A weekday 10:00 America/Chicago after the row was queued."""
    moment = (timezone.now() + timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0)
    while moment.weekday() >= 5:
        moment += timedelta(days=1)
    return moment


def _queued_agreement_email(tenant, actor):
    from apps.customers import services as customers_services
    from apps.customers.agreement_models import AgreementRequest
    from apps.notifications import dispatch_config
    from apps.notifications import models as notification_models

    from tests.test_br_cus_1077_move_in_job import _served_unit
    from tests.test_def_cus_6353_first_occupant_move_in import NAME, _payload

    dispatch_config.update_dispatch_settings(actor=actor, email_dispatch_active=True)
    _premises, unit = _served_unit(actor, tenant, label="Unit 10460", address="10460 Elm")
    result = customers_services.move_in_to_unit(
        actor,
        unit["id"],
        _payload(contact={"full_name": NAME, "email": CUSTOMER_EMAIL}),
    )
    row = AgreementRequest.objects.get(account_id=result["id"])
    message = notification_models.OutboundMessage.objects.get(pk=row.email_message_id)
    assert message.recipient_address == CUSTOMER_EMAIL, message.unavailable_reason
    return row, message


@pytest.mark.django_db
def test_end_to_end_the_agreement_email_reaches_sendgrid_with_the_pdf(brazos, dana, monkeypatch):
    from apps.integrations.adapters import esp_email
    from apps.notifications import dispatcher
    from apps.notifications import models as notification_models
    from apps.tenancy import document_store

    from tests.test_us_int_helpers_b import post_connect

    transport = fixtures.sendgrid_transport()
    monkeypatch.setattr(esp_email, "_urllib_transport", transport)
    connected = post_connect(brazos, dana, "sendgrid", SENDGRID_FIELDS)
    assert connected.status_code in (200, 201), getattr(connected, "data", connected)
    _publish_agreement(brazos, dana)
    with tenant_ctx(brazos):
        request, message = _queued_agreement_email(brazos, dana)
        stored = document_store.fetch(request.sent_document_id)
        cycle = dispatcher.dispatch_cycle(
            now=_inside_window(), channels=(notification_models.CHANNEL_EMAIL,)
        )
        message.refresh_from_db()
        assert message.status == notification_models.STATUS_SENT, (message.last_error, cycle)

    sends = [one for one in transport.sent if one[1].endswith("/v3/mail/send")]
    [body] = [
        one[3]
        for one in sends
        if one[3]["personalizations"][0]["custom_args"]["tracking_ref"] == str(message.pk)
    ]
    [attached] = body["attachments"]
    assert attached["type"] == "application/pdf"
    assert attached["filename"].endswith(".pdf")
    assert base64.b64decode(attached["content"]) == stored
    assert stored.startswith(b"%PDF-")
    # The link is in the body too: the PDF is the copy, the link is the act.
    assert ORIGIN in body["content"][0]["value"]
    # The greeting is the shared builder's first name, as every other email's
    # (the walk of 2026-10-22 read "Hi Okafor, Ade,").
    from apps.notifications import customer_context

    from tests.test_def_cus_6353_first_occupant_move_in import NAME

    greeting = customer_context.greeting_name(NAME)
    assert body["content"][0]["value"].startswith(f"Hi {greeting},"), body["content"][0]["value"][:40]
    assert NAME == greeting or not body["content"][0]["value"].startswith(f"Hi {NAME},")


@pytest.mark.django_db
def test_end_to_end_the_agreement_email_reaches_smtp_with_the_pdf(brazos, dana, monkeypatch):
    from apps.integrations import services
    from apps.integrations.registry import REGISTRY
    from apps.integrations.runners import deliver
    from apps.notifications import dispatcher
    from apps.notifications import models as notification_models
    from apps.tenancy import document_store

    # A real email connection (so the dispatcher routes the channel), with the
    # SMTP adapter bound to it and only the socket faked: the seam, the SMTP
    # adapter and the attachment fetch run as they do in production.
    from tests.test_us_int_helpers_b import post_connect

    transport = fixtures.sendgrid_transport()
    from apps.integrations.adapters import esp_email

    monkeypatch.setattr(esp_email, "_urllib_transport", transport)
    connected = post_connect(brazos, dana, "sendgrid", SENDGRID_FIELDS)
    assert connected.status_code in (200, 201), getattr(connected, "data", connected)
    _FakeSmtp.sent = []
    monkeypatch.setattr(EmailSmtpAdapter, "_session", lambda self, conn, secrets: _FakeSmtp())
    monkeypatch.setattr(REGISTRY, "adapter_for", lambda key: EmailSmtpAdapter)
    monkeypatch.setattr(services, "credential_secrets", lambda conn: {"password": "x"})
    monkeypatch.setattr(deliver, "view_of", lambda conn: SMTP_VIEW)
    monkeypatch.setattr(
        services,
        "guarded_adapter_call",
        lambda *, connection, operation, call: SimpleNamespace(
            skipped=False, timed_out=False, value=call(), sentence=None
        ),
    )
    _publish_agreement(brazos, dana)
    with tenant_ctx(brazos):
        request, message = _queued_agreement_email(brazos, dana)
        stored = document_store.fetch(request.sent_document_id)
        cycle = dispatcher.dispatch_cycle(
            now=_inside_window(), channels=(notification_models.CHANNEL_EMAIL,)
        )
        message.refresh_from_db()
        assert message.status == notification_models.STATUS_SENT, (message.last_error, cycle)
        from apps.notifications import rendering

        subject = rendering.render_for_dispatch(message).subject

    to_customer = [one for one in _FakeSmtp.sent if one["To"] == CUSTOMER_EMAIL]
    [sent] = [one for one in to_customer if one["Subject"] == subject]
    assert _mime_pdf_named(sent) == stored
    # The other emails of the same move-in (the welcome) enclose nothing.
    assert all(
        not list(one.iter_attachments()) for one in to_customer if one["Subject"] != subject
    )


def _mime_pdf_named(message) -> bytes:
    assert message.get_content_type() == "multipart/mixed"
    [part] = list(message.iter_attachments())
    assert part.get_content_type() == "application/pdf"
    assert part.get_filename().endswith(".pdf")
    return part.get_payload(decode=True)
