# ── Trace ──────────────────────────────────────────────
# Change:   CR-190-BRC10 lane AGREEMENT — PO 2026-10-22, answer 1: *"email it
#           as a PDF attachment"*
# Rules:    B14 rule 43's backend twin (one piece of code, not a copy per
#           adapter) · BR-INT-041 (nothing here dials a provider)
# Tests:    06-backend/tests/test_cr190_agreements.py
# Impacts:  apps/integrations/adapters/email_*.py — lane EMAIL-CORE calls these
#           from the adapters it is rewriting; nothing here edits an adapter
# ───────────────────────────────────────────────────────
"""An email's attachments in each provider's own shape. PURE: no I/O.

The input is `apps.notifications.attachments.for_handoff`'s list —
`[{filename, content_type, content: bytes}]` — and every function here turns
that into what one provider accepts. They are separate from the adapters so the
six adapters cannot disagree about the encoding or the disposition, and so the
lane rewriting the adapter bodies (EMAIL-CORE) adds ONE call per adapter rather
than an encoder each.
"""

from __future__ import annotations

import base64
from email.message import EmailMessage
from typing import Any


def _split(content_type: str) -> tuple[str, str]:
    main, _, sub = (content_type or "application/octet-stream").partition("/")
    return (main or "application"), (sub or "octet-stream")


def _b64(content: bytes) -> str:
    return base64.b64encode(content).decode("ascii")


def add_to_mime(message: EmailMessage, attachments: list[dict[str, Any]]) -> EmailMessage:
    """SMTP, Gmail API and any adapter that sends a raw MIME message.

    `EmailMessage.add_attachment` turns a single-part or `multipart/alternative`
    message into `multipart/mixed` with the body kept as its first part, which
    is exactly the structure a mail client shows as *body + attachment*.
    """
    for item in attachments or ():
        main, sub = _split(item.get("content_type") or "")
        message.add_attachment(
            item["content"], maintype=main, subtype=sub, filename=item["filename"]
        )
    return message


def sendgrid(attachments: list[dict[str, Any]]) -> list[dict[str, str]]:
    """SendGrid v3 `attachments`."""
    return [
        {
            "content": _b64(item["content"]),
            "filename": item["filename"],
            "type": item.get("content_type") or "application/octet-stream",
            "disposition": "attachment",
        }
        for item in attachments or ()
    ]


def postmark(attachments: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Postmark `Attachments`."""
    return [
        {
            "Name": item["filename"],
            "Content": _b64(item["content"]),
            "ContentType": item.get("content_type") or "application/octet-stream",
        }
        for item in attachments or ()
    ]


def microsoft_graph(attachments: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Microsoft Graph `message.attachments` (file attachments)."""
    return [
        {
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": item["filename"],
            "contentType": item.get("content_type") or "application/octet-stream",
            "contentBytes": _b64(item["content"]),
        }
        for item in attachments or ()
    ]


__all__ = ["add_to_mime", "microsoft_graph", "postmark", "sendgrid"]
