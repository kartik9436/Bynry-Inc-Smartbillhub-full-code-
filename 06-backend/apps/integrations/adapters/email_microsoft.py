# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-005 (EP-INT-07) — BYO mailbox, CR-069 wave H task H1
# Rules:    BR-INT-005 · BR-INT-047 · BR-INT-037
# Tests:    06-backend/tests/test_us_int_005_oauth.py
# ───────────────────────────────────────────────────────
"""Microsoft 365 — one URL and one message shape, and nothing else.

Everything that is not those two things is `adapters/oauth_mailbox.py`. If this
file grows a third idea, the idea belongs in the base class or in the manifest
— that is what keeps `P1`'s promise true (*"every time such integration comes
we dont want to change our integration framework"*).

Graph's `sendMail` sends AS the signed-in mailbox, which is why `sender` does
not appear in the body: the token decides who it is from. That is precisely
`BR-INT-005`'s guarantee made structural — there is no field here that COULD be
set to somebody else's address.

The body is `email_format`'s escaped HTML alternative with `contentType: HTML`.
Graph's JSON `sendMail` carries ONE body, so this is the one adapter that sends
no separate text part; the HTML's visible text is the rendered plain body. ⚠
Until 2026-10-22 (`DEF-NOT-10420`) the PLAIN text was sent labelled `HTML`, so
every line break of every template collapsed into a single paragraph.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from apps.integrations import email_attachments
from apps.integrations.adapters import email_format
from apps.integrations.adapters.oauth_mailbox import OAuthMailboxAdapter


class EmailMicrosoftAdapter(OAuthMailboxAdapter):
    key = "email_microsoft"
    provider_label = "Microsoft 365"
    send_url = "https://graph.microsoft.com/v1.0/me/sendMail"

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
        content = email_format.compose(subject=subject, body=body, language=language, html=html)
        message: dict[str, Any] = {
            "subject": content.subject,
            "body": {"contentType": "HTML", "content": content.html},
            "toRecipients": [{"emailAddress": {"address": to}}],
        }
        # `DEF-NOT-10460` — Graph `fileAttachment`s, base64 in the JSON.
        files = email_attachments.microsoft_graph(list(attachments))
        if files:
            message["attachments"] = files
        return {
            "message": message,
            # Not writing to the utility's Sent Items: a bill run of 240
            # messages would fill a mailbox a person also reads every morning.
            "saveToSentItems": False,
        }


__all__ = ["EmailMicrosoftAdapter"]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-005 (EP-INT-07 — BYO mailbox) · BR-INT-005 · BR-INT-047
# generated: 2026-09-06 by the CR-069 wave H build lane
# checklist: A✔ B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a(the 🔒 half is the base class's token handling)
# gates: pytest tests/test_us_int_005_oauth.py · conformance kit (four public methods, no fifth)
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
