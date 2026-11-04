# ── Trace ──────────────────────────────────────────────
# Change:   CR-190-BRC10 · lane EMAIL-CORE (maintenance defect fix)
# Defect:   DEF-NOT-10420 — every outbound email carried the dispatcher's whole
#           internal dict as its body and an adapter fallback subject
# Rules:    BR-NOT-005 (the one hand-off) · PO 2026-10-22 ("don't do any
#           hardcoding" — no invented subject or body) · CLAUDE.md law 1
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**What an email adapter puts on the wire is the template's subject and body.**

REPRODUCED BEFORE THE FIX (law 7), through the seam the dispatcher really calls
with the payload `notifications.dispatcher._payload` really builds:

  * the seam handed the adapter
    ``subject=None`` and
    ``body={'subject': 'Welcome to Brazos Bend Utilities', 'body': 'Hi Alex,\\n\\n…',
    'template_code': 'email_welcome', 'template_version': 3, 'language': 'en'}`` —
    the subject was read from the RECIPIENT snapshot, which never holds one, and
    the body was the whole artifact dict;
  * every adapter then `str()`-ed that dict into the message and fell back to its
    own subject: SMTP ``Test message from your billing system``, SendGrid and
    Postmark ``Message from your utility``, the two mailboxes ``""``;
  * Google and Microsoft labelled the (plain) text as HTML, so its line breaks
    collapsed into one paragraph.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):
  * an adapter test that hand-builds ``{"subject", "body"}`` — which is exactly how
    the defect hid for every adapter's own suite. The seam cases here feed the
    DISPATCHER's payload shape through the real seam, and the end-to-end case
    queues a real ``email_welcome`` row and runs ``dispatch_cycle``;
  * a check that the subject is *present* rather than *the template's* — a
    fallback subject is present. Each case asserts the exact template subject
    and that no fallback string reached the wire;
  * a dict that is `str()`-ed into the HTML part instead of the text part — the
    cases assert ``{'subject'`` reaches neither part.
"""

from __future__ import annotations

import base64
import email
from email import policy
from typing import Any

import pytest

from apps.integrations import esp_fixtures as fixtures
from apps.integrations.adapters import email_format
from apps.integrations.adapters.base import ITEM_FAILED, ITEM_SUCCEEDED, ConnectionView
from apps.integrations.adapters.email_google import EmailGoogleAdapter
from apps.integrations.adapters.email_microsoft import EmailMicrosoftAdapter
from apps.integrations.adapters.email_postmark import EmailPostmarkAdapter
from apps.integrations.adapters.email_sendgrid import EmailSendgridAdapter
from apps.integrations.adapters.email_smtp import EmailSmtpAdapter
from apps.integrations.adapters.oauth_mailbox import REFRESH_TOKEN_FIELD

SUBJECT = "Welcome to Brazos Bend Utilities"
BODY = (
    "Hi Alex,\n\n"
    "Your account A-10432 is open.\n"
    "Service starts on 1 November.\n\n"
    "Brazos Bend Utilities"
)
SENDER = "billing@brazosbend.example"
RECIPIENT = "alex@example.test"

#: Every subject an adapter used to invent. None may reach the wire for a real message.
FALLBACK_SUBJECTS = (
    "Test message from your billing system",
    "Message from your utility",
)


def dispatcher_payload(*, subject=SUBJECT, body=BODY, artifact: Any = "default") -> dict:
    """ONE message exactly as `notifications.dispatcher._payload` builds it."""
    if artifact == "default":
        artifact = {
            "subject": subject,
            "body": body,
            "template_code": "email_welcome",
            "template_version": 3,
            "language": "en",
        }
    return {
        "id": "7f6c2d4e-0000-4000-8000-000000010420",
        "channel": "email",
        "address": RECIPIENT,
        # The recipient snapshot — a NAME and address lines, never a subject.
        "snapshot": {"name": "Alex Moreno", "account_no": "A-10432"},
        "source_type": "move",
        "source_id": "11111111-0000-4000-8000-000000000001",
        "account_id": None,
        "artifact": artifact,
    }


def work_item(subject=SUBJECT, body=BODY) -> dict:
    return {"ref": "ref-1", "address": RECIPIENT, "subject": subject, "body": body}


# ═══════════════════════════════════════════════════════════════════════════
# THE SEAM — what the dispatcher's payload becomes on the way to an adapter
# ═══════════════════════════════════════════════════════════════════════════


class _Captured:
    work: list = []


class _CapturingAdapter:
    def execute(self, conn, secrets, work):  # noqa: ANN001
        from apps.integrations.adapters.base import ItemResult, RunResult

        _Captured.work = list(work)
        return RunResult(
            items=tuple(ItemResult(ref=one["ref"], outcome=ITEM_SUCCEEDED) for one in work),
            confirmed=True,
        )


@pytest.fixture()
def capturing_seam(monkeypatch):
    """The real `dispatch_outbound_batch`, with only the CONNECTION faked.

    Everything between the dispatcher's payload and the adapter's `execute` —
    the part the defect lived in — runs as it does in production.
    """
    from types import SimpleNamespace

    from apps.integrations import services
    from apps.integrations.registry import REGISTRY
    from apps.integrations.runners import deliver
    from apps.integrations.runtime import Outcome  # noqa: F401 — shape reference
    from apps.integrations.seams import notifications as seam

    connection = SimpleNamespace(pk=1, provider_key="email_smtp", config={})
    monkeypatch.setattr(seam, "_connection_for_channel", lambda channel: connection)
    # `CR-198-BRC10` — SMS now goes through the PLATFORM's account (its own
    # branch, `test_cr198_sms_twilio.py`). This file proves the shared work-item
    # shaping on the connection path, so the platform branch is switched off
    # here and the SMS case still exercises `_work_item` exactly as before.
    monkeypatch.setattr(seam, "_platform_manifest", lambda category: None)
    monkeypatch.setattr(seam, "_sending_operation", lambda conn: None)
    monkeypatch.setattr(REGISTRY, "adapter_for", lambda key: _CapturingAdapter)
    monkeypatch.setattr(services, "credential_secrets", lambda conn: {})
    monkeypatch.setattr(deliver, "view_of", lambda conn: conn)
    monkeypatch.setattr(
        services,
        "guarded_adapter_call",
        lambda *, connection, operation, call: SimpleNamespace(
            skipped=False, timed_out=False, value=call(), sentence=None
        ),
    )
    _Captured.work = []
    return seam


def test_the_seam_hands_the_adapter_the_templates_subject_and_body(capturing_seam):
    answer = capturing_seam.dispatch_outbound_batch("email", (dispatcher_payload(),))

    (item,) = _Captured.work
    assert item["subject"] == SUBJECT
    assert item["body"] == BODY
    assert isinstance(item["body"], str)
    assert answer[dispatcher_payload()["id"]]["status"] == "sent"


@pytest.mark.parametrize(
    "artifact",
    [
        "Hi Alex — a bare string from an older row",
        None,
        ["not", "a", "render"],
    ],
)
def test_an_artifact_that_is_not_a_render_is_refused_never_stringified(
    capturing_seam, artifact
):
    payload = dispatcher_payload(artifact=artifact)
    answer = capturing_seam.dispatch_outbound_batch("email", (payload,))

    assert _Captured.work == [], "nothing may reach the adapter"
    entry = answer[payload["id"]]
    assert entry["status"] == "failed"
    # Waiting will not turn a non-render into one.
    assert entry["retryable"] is False
    assert entry["response"]["reason"] == "artifact_not_a_render"


@pytest.mark.parametrize(
    ("subject", "body", "reason"),
    [
        (None, BODY, "email_has_no_subject"),
        ("   ", BODY, "email_has_no_subject"),
        (SUBJECT, "", "message_has_no_body"),
        (SUBJECT, None, "message_has_no_body"),
    ],
)
def test_an_email_with_no_subject_or_no_body_is_refused_not_invented(
    capturing_seam, subject, body, reason
):
    payload = dispatcher_payload(subject=subject, body=body)
    answer = capturing_seam.dispatch_outbound_batch("email", (payload,))

    assert _Captured.work == []
    entry = answer[payload["id"]]
    assert entry["status"] == "failed" and entry["retryable"] is False
    assert entry["response"]["reason"] == reason


def test_an_sms_needs_a_body_and_no_subject(capturing_seam):
    """A text message has no subject line; requiring one would hold every SMS."""
    payload = dispatcher_payload(subject=None, body="Your bill of $42.10 is ready.")
    payload["channel"] = "sms"
    capturing_seam.dispatch_outbound_batch("sms", (payload,))

    (item,) = _Captured.work
    assert item["body"] == "Your bill of $42.10 is ready."
    assert item["subject"] is None


def test_good_rows_still_go_when_one_row_in_the_batch_is_refused(capturing_seam):
    good = dispatcher_payload()
    bad = dispatcher_payload(artifact="a bare string")
    bad["id"] = "bad-row"
    answer = capturing_seam.dispatch_outbound_batch("email", (good, bad))

    assert [one["ref"] for one in _Captured.work] == [good["id"]]
    assert answer[good["id"]]["status"] == "sent"
    assert answer["bad-row"]["status"] == "failed"


# ═══════════════════════════════════════════════════════════════════════════
# THE SHARED FORMAT — one HTML alternative for every adapter
# ═══════════════════════════════════════════════════════════════════════════


def test_the_html_alternative_escapes_and_keeps_paragraphs_and_line_breaks():
    content = email_format.compose(
        subject="Bill <ready>", body="Hi <script>alert(1)</script> & co,\n\nLine one\nLine two"
    )

    assert content.subject == "Bill <ready>"
    assert content.text == "Hi <script>alert(1)</script> & co,\n\nLine one\nLine two"
    assert "<script>" not in content.html
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; co," in content.html
    assert "<p" in content.html and content.html.count("<p ") == 2
    assert "Line one<br/>Line two" in content.html
    # Inline styles only: no stylesheet link, no external asset of any kind.
    assert "<link" not in content.html and "src=" not in content.html
    assert "http://" not in content.html and "https://" not in content.html
    # The <title> is the escaped subject.
    assert "<title>Bill &lt;ready&gt;</title>" in content.html


def test_windows_line_endings_make_the_same_paragraphs():
    unix = email_format.compose(subject=SUBJECT, body="A\n\nB\nC")
    windows = email_format.compose(subject=SUBJECT, body="A\r\n\r\nB\r\nC")
    assert unix.html == windows.html


@pytest.mark.parametrize(
    ("subject", "body"),
    [(None, BODY), ("", BODY), (SUBJECT, ""), (SUBJECT, None), ({"subject": "x"}, BODY), (SUBJECT, {"body": BODY})],
)
def test_compose_refuses_rather_than_inventing(subject, body):
    with pytest.raises(email_format.EmailContentMissing):
        email_format.compose(subject=subject, body=body)


# ═══════════════════════════════════════════════════════════════════════════
# EVERY ADAPTER — the message on the wire
# ═══════════════════════════════════════════════════════════════════════════


def _assert_parts(text: str, html: str) -> None:
    assert text == BODY
    assert "{'subject'" not in text and "{'subject'" not in html
    assert "<p " in html and "Hi Alex,</p>" in html
    assert "Your account A-10432 is open.<br/>Service starts on 1 November." in html


def _parts_of(message: email.message.EmailMessage) -> tuple[str, str]:
    assert message.get_content_type() == "multipart/alternative"
    plain = message.get_body(preferencelist=("plain",))
    html = message.get_body(preferencelist=("html",))
    return plain.get_content().replace("\r\n", "\n").rstrip("\n"), html.get_content()


class _FakeSmtp:
    sent: list = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):  # noqa: ANN002
        return False

    def send_message(self, message):  # noqa: ANN001
        type(self).sent.append(message)


@pytest.fixture()
def smtp(monkeypatch):
    _FakeSmtp.sent = []
    monkeypatch.setattr(EmailSmtpAdapter, "_session", lambda self, conn, secrets: _FakeSmtp())
    return EmailSmtpAdapter()


SMTP_VIEW = ConnectionView(
    provider_key="email_smtp",
    environment="production",
    config={"host": "localhost", "port": "587", "send_from": SENDER},
    label="Bills",
)


def test_smtp_sends_the_template_subject_and_a_multipart_body(smtp):
    result = smtp.execute(SMTP_VIEW, {"password": "x"}, [work_item()])

    assert result.items[0].outcome == ITEM_SUCCEEDED
    (message,) = _FakeSmtp.sent
    assert message["Subject"] == SUBJECT
    _assert_parts(*_parts_of(message))


def test_smtp_refuses_a_message_with_no_subject_instead_of_its_test_subject(smtp):
    result = smtp.execute(SMTP_VIEW, {"password": "x"}, [work_item(subject=None)])

    assert result.items[0].outcome == ITEM_FAILED
    assert _FakeSmtp.sent == []


def test_smtps_send_test_email_path_keeps_its_own_test_subject(smtp):
    """The *Send test email* button is where the test subject belongs — and
    only there."""
    result = smtp.test(SMTP_VIEW, {"password": "x"}, recipient=RECIPIENT)

    assert result.ok
    (message,) = _FakeSmtp.sent
    assert message["Subject"] == "Test message from your billing system"
    assert message.get_content_type() == "multipart/alternative"


def _esp_view(key: str) -> ConnectionView:
    return ConnectionView(
        provider_key=key,
        environment="production",
        config={"base_url": f"https://api.{key}.example", "send_from": SENDER},
        label="Bills",
    )


def test_sendgrid_sends_plain_then_html_content_and_the_template_subject():
    transport = fixtures.sendgrid_transport()
    result = EmailSendgridAdapter(transport).execute(
        _esp_view("sendgrid"), {"api_key": fixtures.SENDGRID_GOOD_KEY}, [work_item()]
    )

    assert result.items[0].outcome == ITEM_SUCCEEDED
    body = transport.sent[-1][3]
    assert body["subject"] == SUBJECT
    # SendGrid requires text/plain FIRST when both are given.
    assert [part["type"] for part in body["content"]] == ["text/plain", "text/html"]
    _assert_parts(body["content"][0]["value"], body["content"][1]["value"])


def test_postmark_sends_textbody_and_htmlbody_and_the_template_subject():
    transport = fixtures.postmark_transport()
    result = EmailPostmarkAdapter(transport).execute(
        _esp_view("postmark"), {"server_token": fixtures.POSTMARK_GOOD_TOKEN}, [work_item()]
    )

    assert result.items[0].outcome == ITEM_SUCCEEDED
    body = transport.sent[-1][3]
    assert body["Subject"] == SUBJECT
    _assert_parts(body["TextBody"], body["HtmlBody"])


@pytest.mark.parametrize(
    ("cls", "transport_of", "secrets"),
    [
        (EmailSendgridAdapter, fixtures.sendgrid_transport, {"api_key": fixtures.SENDGRID_GOOD_KEY}),
        (EmailPostmarkAdapter, fixtures.postmark_transport, {"server_token": fixtures.POSTMARK_GOOD_TOKEN}),
    ],
)
def test_an_esp_never_invents_a_subject_for_a_real_message(cls, transport_of, secrets):
    transport = transport_of()
    result = cls(transport).execute(_esp_view(cls.key), secrets, [work_item(subject=None)])

    assert result.items[0].outcome == ITEM_FAILED
    assert transport.sent == [], "nothing may be dialled for a message with no subject"


@pytest.mark.parametrize(
    ("cls", "transport_of", "secrets"),
    [
        (EmailSendgridAdapter, fixtures.sendgrid_transport, {"api_key": fixtures.SENDGRID_GOOD_KEY}),
        (EmailPostmarkAdapter, fixtures.postmark_transport, {"server_token": fixtures.POSTMARK_GOOD_TOKEN}),
    ],
)
def test_an_esps_test_button_still_sends_its_test_message(cls, transport_of, secrets):
    transport = transport_of()
    result = cls(transport).test(_esp_view(cls.key), secrets, recipient=RECIPIENT)
    assert result.ok


def _recording(cls):
    class Recording(cls):
        sent: list = []

        def _access_token(self, conn, refresh):  # noqa: ANN001
            return "TOKEN"

        def _send_one(self, token, *, sender, to, subject, body, attachments=(), language=None):  # noqa: ANN001
            type(self).sent.append(
                self._message(
                    sender=sender,
                    to=to,
                    subject=subject,
                    body=body,
                    attachments=attachments,
                    language=language,
                )
            )

    Recording.sent = []
    return Recording


MAILBOX_SECRETS = {REFRESH_TOKEN_FIELD: "refresh"}


def _mailbox_view(key: str) -> ConnectionView:
    return ConnectionView(
        provider_key=key, environment="production", config={"send_from": SENDER}, label="Bills"
    )


def test_google_sends_mime_multipart_with_the_template_subject():
    adapter_cls = _recording(EmailGoogleAdapter)
    result = adapter_cls().execute(_mailbox_view("email_google"), MAILBOX_SECRETS, [work_item()])

    assert result.items[0].outcome == ITEM_SUCCEEDED
    (sent,) = adapter_cls.sent
    message = email.message_from_bytes(
        base64.urlsafe_b64decode(sent["raw"]), policy=policy.default
    )
    assert message["Subject"] == SUBJECT
    _assert_parts(*_parts_of(message))


def test_microsoft_sends_the_html_alternative_as_graphs_html_body():
    adapter_cls = _recording(EmailMicrosoftAdapter)
    result = adapter_cls().execute(
        _mailbox_view("email_microsoft"), MAILBOX_SECRETS, [work_item()]
    )

    assert result.items[0].outcome == ITEM_SUCCEEDED
    (sent,) = adapter_cls.sent
    assert sent["message"]["subject"] == SUBJECT
    graph_body = sent["message"]["body"]
    assert graph_body["contentType"] == "HTML"
    assert graph_body["content"] == email_format.compose(subject=SUBJECT, body=BODY).html
    assert "Your account A-10432 is open.<br/>Service starts on 1 November." in graph_body["content"]


@pytest.mark.parametrize("cls", [EmailGoogleAdapter, EmailMicrosoftAdapter])
def test_a_mailbox_refuses_a_message_with_no_subject(cls):
    adapter_cls = _recording(cls)
    result = adapter_cls().execute(
        _mailbox_view(cls.key), MAILBOX_SECRETS, [work_item(subject="")]
    )
    assert result.items[0].outcome == ITEM_FAILED
    assert adapter_cls.sent == []


@pytest.mark.parametrize("cls", [EmailGoogleAdapter, EmailMicrosoftAdapter])
def test_a_script_tag_in_a_body_reaches_the_wire_escaped(cls):
    adapter_cls = _recording(cls)
    adapter_cls().execute(
        _mailbox_view(cls.key),
        MAILBOX_SECRETS,
        [work_item(body="Hi <script>alert(1)</script>")],
    )
    (sent,) = adapter_cls.sent
    wire = (
        base64.urlsafe_b64decode(sent["raw"]).decode()
        if "raw" in sent
        else sent["message"]["body"]["content"]
    )
    assert "&lt;script&gt;" in wire
    if "raw" not in sent:
        assert "<script>" not in wire


# ═══════════════════════════════════════════════════════════════════════════
# END TO END — a queued email_welcome / email_deposit row, a dispatch cycle,
# and what a provider is actually handed
# ═══════════════════════════════════════════════════════════════════════════

from datetime import datetime, timezone as dt_timezone  # noqa: E402
from uuid import uuid4  # noqa: E402

from tests.test_cr048_a1_rule_at_queue_time import an_account  # noqa: E402
from tests.test_us_int_helpers_b import post_connect  # noqa: E402
from tests.test_us_met_helpers import *  # noqa: E402,F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx  # noqa: E402

#: 15:00 UTC is 10:00 in America/Chicago — inside Brazos Bend's seeded window.
INSIDE_WINDOW = datetime(2026, 8, 9, 15, 0, tzinfo=dt_timezone.utc)

SENDGRID_FIELDS = {
    "base_url": "https://api.sendgrid.com",
    "api_key": fixtures.SENDGRID_GOOD_KEY,
    "sending_domain": "brazosbend.example",
    "send_from": SENDER,
}


@pytest.mark.django_db
@pytest.mark.parametrize("template_code", ["email_welcome", "email_deposit"])
def test_end_to_end_a_queued_template_email_reaches_the_wire_as_its_subject_and_body(
    brazos, dana, monkeypatch, template_code
):
    from apps.integrations.adapters import esp_email
    from apps.notifications import dispatcher, models, services  # noqa: F811

    transport = fixtures.sendgrid_transport()
    monkeypatch.setattr(esp_email, "_urllib_transport", transport)
    connected = post_connect(brazos, dana, "sendgrid", SENDGRID_FIELDS)
    assert connected.status_code in (200, 201), getattr(connected, "data", connected)

    source_id = uuid4()
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-10420")
        # The utility has switched email sending on (Settings → Notifications),
        # which is what a utility whose customers receive these emails has done.
        from apps.notifications import dispatch_config

        dispatch_config.update_dispatch_settings(actor=dana, email_dispatch_active=True)
        write = services.queue_document(
            source_type="move",
            source_id=source_id,
            channels=(models.CHANNEL_EMAIL,),
            template=services.TemplatePin(code=template_code),
            account_id=account.pk,
            recipients=(
                services.Recipient(
                    channel=models.CHANNEL_EMAIL,
                    address=RECIPIENT,
                    snapshot={"name": "Alex Moreno"},
                ),
            ),
            actor=dana,
        )
        rows = list(
            models.OutboundMessage.objects.filter(
                tenant_id=brazos.id,
                template_code=template_code,
                source_id=source_id,
                channel=models.CHANNEL_EMAIL,
            ).exclude(recipient_address__isnull=True)
        )
        assert rows, write.problems
        assert all(row.template_id is not None for row in rows), (template_code, write.problems)
        cycle = dispatcher.dispatch_cycle(now=INSIDE_WINDOW, channels=(models.CHANNEL_EMAIL,))
        from apps.notifications import rendering

        expected = {}
        for row in rows:
            row.refresh_from_db()
            assert row.status == models.STATUS_SENT, (row.status, row.last_error, cycle)
            expected[str(row.pk)] = rendering.render_for_dispatch(row)

    sends = [one for one in transport.sent if one[1].endswith("/v3/mail/send")]
    assert len(sends) == len(rows), transport.sent
    for _method, _url, _headers, body in sends:
        ref = body["personalizations"][0]["custom_args"]["tracking_ref"]
        render = expected[ref]
        assert render.subject and body["subject"] == render.subject
        assert body["subject"] not in FALLBACK_SUBJECTS
        plain, html = body["content"][0]["value"], body["content"][1]["value"]
        assert plain == render.body
        assert "{'subject'" not in plain and "'template_code'" not in plain
        assert "{'subject'" not in html and "<p " in html
