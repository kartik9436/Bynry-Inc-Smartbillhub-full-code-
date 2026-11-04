# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-005 (EP-INT-07) — BYO mailbox, CR-069 wave H task H1
# Rules:    BR-INT-005 · BR-INT-047 · BR-INT-037
# Tests:    06-backend/tests/test_us_int_005_oauth.py
# ───────────────────────────────────────────────────────
"""Google Workspace — one URL and one message shape, and nothing else.

See `adapters/email_microsoft.py`: the two files are the same size and differ
by these two declarations, which is the point of the base class.

Gmail wants RFC-2822 MIME, base64url-encoded, under the key `raw`, where Graph
wants structured JSON. That difference is the entire reason a `_message` hook
exists rather than one shared body-builder with a flag in it.

The MIME is `multipart/alternative` — the rendered text and its escaped HTML
alternative from `email_format`. ⚠ Until 2026-10-22 (`DEF-NOT-10420`) this was
ONE part, the plain text labelled `text/html`, so a mail client collapsed every
line break of every template into a single paragraph.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping, Sequence
from typing import Any

from apps.integrations import email_attachments
from apps.integrations.adapters import email_format
from apps.integrations.adapters.oauth_mailbox import OAuthMailboxAdapter


class EmailGoogleAdapter(OAuthMailboxAdapter):
    key = "email_google"
    provider_label = "Google Workspace"
    send_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"

    def _message(
        self,
        *,
        sender: str,
        to: str,
        subject: str,
        body: str,
        attachments: Sequence[Mapping[str, Any]] = (),
        language: str | None = None,
        html: str | None = None,
    ) -> dict[str, Any]:
        message = email_format.mime_alternative(
            email_format.compose(subject=subject, body=body, language=language, html=html),
            sender=sender,
            to=to,
        )
        # `DEF-NOT-10460` — `multipart/mixed`, the alternative first.
        email_attachments.add_to_mime(message, list(attachments))
        # ⚠ base64**url** — `urlsafe_b64encode`, not `b64encode`. Gmail rejects
        # the standard alphabet's `+` and `/` with a 400 whose text does not
        # mention encoding, so the wrong one here reads as a mystery rejection.
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        return {"raw": raw}


__all__ = ["EmailGoogleAdapter"]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-005 (EP-INT-07 — BYO mailbox) · BR-INT-005 · BR-INT-047
# generated: 2026-09-06 by the CR-069 wave H build lane
# checklist: A✔ B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a(the 🔒 half is the base class's token handling)
# gates: pytest tests/test_us_int_005_oauth.py · conformance kit (four public methods, no fifth)
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
