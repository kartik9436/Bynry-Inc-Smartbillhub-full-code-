# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-NOT-10571 — the HTML wrapper every email is sent in declared no
#           language (WCAG 2.1 SC 3.1.1). Portal a11y Group D leftover, reported
#           by lane A11Y-D (decision log 2026-10-23, "Groups D and E: how it is
#           built", *Not changed, and reported*).
# Code:     apps/integrations/adapters/email_format.py (`<html lang>`) ·
#           apps/integrations/seams/notifications.py (the message's language) ·
#           apps/integrations/seams/tenancy.py (`language()` for a default variant)
# ───────────────────────────────────────────────────────
"""The email's `<html>` says which language it is written in.

The language is the template variant the message was rendered from; a
`default` variant is written in the utility's own language (the one rendering
already writes its money in), so that is what it declares. A tag that is not a
language tag is never written, and nothing is invented when there is none.
"""

from __future__ import annotations

import pytest

from apps.integrations.adapters import email_format
from apps.integrations.adapters.email_postmark import EmailPostmarkAdapter
from apps.integrations.seams import notifications as seam
from apps.integrations.seams import tenancy as tenancy_seam
from tests.test_def_not_10420_email_payload import (
    _esp_view,
    _recording,
    _mailbox_view,
    MAILBOX_SECRETS,
    capturing_seam,  # noqa: F401 — fixture
    dispatcher_payload,
    fixtures,
    _Captured,
)
from apps.integrations.adapters.email_microsoft import EmailMicrosoftAdapter

SUBJECT = "Su factura está lista"
BODY = "Hola Alex,\n\nSu factura de octubre está lista."


@pytest.mark.parametrize(
    "language, opening",
    [
        ("es", '<html lang="es">'),
        ("en", '<html lang="en">'),
        ("es-MX", '<html lang="es-MX">'),
        ("pt_BR", '<html lang="pt-BR">'),
    ],
)
def test_the_wrapper_declares_the_messages_language(language, opening):
    html = email_format.compose(subject=SUBJECT, body=BODY, language=language).html
    assert html.startswith("<!DOCTYPE html>" + opening)


@pytest.mark.parametrize("language", [None, "", "default", 'en"><script>', 7])
def test_no_language_or_a_malformed_one_writes_no_attribute(language):
    html = email_format.compose(subject=SUBJECT, body=BODY, language=language).html
    assert html.startswith("<!DOCTYPE html><html><head>")
    assert "<script>" not in html


def test_the_seam_hands_on_the_variants_language(capturing_seam):  # noqa: F811
    payload = dispatcher_payload()
    payload["artifact"]["language"] = "es"
    capturing_seam.dispatch_outbound_batch("email", (payload,))
    (item,) = _Captured.work
    assert item["language"] == "es"


def test_a_default_variant_declares_the_utilitys_own_language(capturing_seam, monkeypatch):  # noqa: F811
    monkeypatch.setattr(tenancy_seam, "language", lambda: "es-MX")
    payload = dispatcher_payload()
    payload["artifact"]["language"] = "default"
    capturing_seam.dispatch_outbound_batch("email", (payload,))
    (item,) = _Captured.work
    assert item["language"] == "es-MX"


def test_the_utilitys_language_is_read_from_regional_settings(monkeypatch):
    from apps.tenancy import selectors

    monkeypatch.setattr(selectors, "regional_settings", lambda: {"language": "fr-FR"})
    assert tenancy_seam.language() == "fr-FR"
    monkeypatch.setattr(selectors, "regional_settings", lambda: {"language": ""})
    assert tenancy_seam.language() is None
    assert seam._message_language("es") == "es"


def test_an_esp_sends_the_language_in_its_html_body():
    transport = fixtures.postmark_transport()
    work = [
        {
            "ref": "r1",
            "address": "alex@example.test",
            "subject": SUBJECT,
            "body": BODY,
            "language": "es",
        }
    ]
    EmailPostmarkAdapter(transport).execute(
        _esp_view("postmark"), {"server_token": fixtures.POSTMARK_GOOD_TOKEN}, work
    )
    assert transport.sent[-1][3]["HtmlBody"].startswith('<!DOCTYPE html><html lang="es">')


def test_a_mailbox_sends_the_language_in_its_html_body():
    adapter_cls = _recording(EmailMicrosoftAdapter)
    work = [
        {
            "ref": "r1",
            "address": "alex@example.test",
            "subject": SUBJECT,
            "body": BODY,
            "language": "es",
        }
    ]
    adapter_cls().execute(_mailbox_view("email_microsoft"), MAILBOX_SECRETS, work)
    (sent,) = adapter_cls.sent
    assert sent["message"]["body"]["content"].startswith('<!DOCTYPE html><html lang="es">')
