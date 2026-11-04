# ── Trace ──────────────────────────────────────────────
# Change:   CR-190-BRC10 lane AGREEMENT — PO 2026-10-22, answer 1: *"A: email
#           it as a PDF attachment (plus a letter if the customer wants paper)"*
# Rules:    BR-TEN-017 (the envelope is the SNAPSHOT taken at queue time) ·
#           NFR-33 (the attached file is a STORED document, never a re-render) ·
#           CLAUDE.md hard rule 1 (the bytes are fetched under the row's tenant)
# Tests:    06-backend/tests/test_cr190_agreements.py
# Impacts:  apps/integrations/seams/notifications.dispatch_outbound_batch and
#           the email adapters (lane EMAIL-CORE — see "THE HAND-OFF" below) ·
#           apps/integrations/email_attachments.py (the per-provider shapes)
# ───────────────────────────────────────────────────────
"""A queued email's ATTACHMENTS — named on the row, fetched at hand-off.

WHERE THEY ARE RECORDED, AND WHY THERE
─────────────────────────────────────────────────────────────────────────────
In `outbound_messages.recipient_snapshot["attachments"]`, as a list of
`{document_id, filename, content_type}`. The snapshot is the ENVELOPE as it was
when the message was made (BR-TEN-017), and what was enclosed in it is part of
that envelope. No new column and no new table: the snapshot is already handed
to the provider seam on every message (`dispatcher._payload` → `snapshot`), so
an adapter that knows about attachments finds them where it already looks and
one that does not is unchanged.

**Only a STORED document is ever attached** (`tenancy.document_store`): the
bytes are frozen with a content hash before the row names them, so the file
the customer receives is the file the utility keeps.

THE HAND-OFF (WIRED — `DEF-NOT-10460`, closed by lane MERGE-MOVEIN 2026-10-22)
─────────────────────────────────────────────────────────────────────────────
`integrations.seams.notifications._work_item` calls `for_handoff` (resolved by
name) for every EMAIL message and puts the list on the work item as
`"attachments"`; each email adapter turns it into its provider's shape with
`apps.integrations.email_attachments` (MIME for SMTP and Gmail, the JSON arrays
SendGrid, Postmark and Microsoft Graph take). A file that cannot be fetched
fails that message RETRYABLY, so it waits rather than going out without the
PDF its body promises. Proved end to end in
`tests/test_def_not_10460_agreement_attachment.py`.
"""

from __future__ import annotations

from typing import Any

ATTACHMENTS_KEY = "attachments"


def attach_documents(message_id: Any, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Name these stored documents on one QUEUED email row. Idempotent.

    `documents` is `[{document_id, filename, content_type}]`. A row that has
    already left (`status != queued`) is not touched — its envelope is history.
    Returns the list now on the row.
    """
    from apps.notifications import models

    row = models.OutboundMessage.objects.filter(pk=message_id).first()
    if row is None:
        return []
    snapshot = dict(row.recipient_snapshot or {})
    current = list(snapshot.get(ATTACHMENTS_KEY) or [])
    if row.status != models.STATUS_QUEUED:
        return current
    known = {str(item.get("document_id")) for item in current}
    for item in documents:
        if str(item["document_id"]) in known:
            continue
        current.append(
            {
                "document_id": str(item["document_id"]),
                "filename": str(item["filename"]),
                "content_type": str(item.get("content_type") or "application/pdf"),
            }
        )
    snapshot[ATTACHMENTS_KEY] = current
    row.recipient_snapshot = snapshot
    row.save(update_fields=["recipient_snapshot", "updated_at"])
    return current


def named(snapshot: Any) -> list[dict[str, Any]]:
    """The attachments a snapshot names, without their bytes."""
    if not isinstance(snapshot, dict):
        return []
    return [dict(item) for item in snapshot.get(ATTACHMENTS_KEY) or [] if isinstance(item, dict)]


def for_handoff(snapshot: Any) -> list[dict[str, Any]]:
    """`[{filename, content_type, content: bytes}]` for the provider adapter.

    Fetched from the document store under the tenant already in context (the
    dispatcher runs per tenant, hard rule 1). A file that cannot be fetched
    RAISES — an email promising an attachment it does not carry is a wrong
    email, and the dispatcher's own failure path retries it.
    """
    from apps.tenancy import document_store

    out: list[dict[str, Any]] = []
    for item in named(snapshot):
        out.append(
            {
                "filename": item["filename"],
                "content_type": item.get("content_type") or "application/pdf",
                "content": document_store.fetch(item["document_id"]),
            }
        )
    return out


__all__ = ["ATTACHMENTS_KEY", "attach_documents", "for_handoff", "named"]
