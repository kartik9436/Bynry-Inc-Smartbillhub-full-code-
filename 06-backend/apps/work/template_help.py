# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 4, lane SRV-3 — P3.14 (a template holds a help
#           document), PO ruling 6 of 24 Sep (*"help can be an uploaded document
#           or a video link"*)
# Rules:    NFR-35 (the document store; bytes first, then the row) · BR-WRK-008
#           (a job copies its help rows) · CLAUDE.md hard rule 1 (tenant-scoped;
#           a foreign id reads as absent) · hard rule 7 (audited)
# Tests:    06-backend/tests/test_cr168_srv3_templates.py
# ───────────────────────────────────────────────────────
"""A template's help DOCUMENT — the upload ticket, the store, the bytes.

⚠ **THE ONLY WORK UPLOAD WAS SCOPED TO A WORK ORDER**, which a template does
not have (P3.14), so a *document* help row held a label pointing at nothing.
Now the builder:

  1. asks `POST /work/templates/{id}/help/upload-url {filename, content_type}`
     where to send it — our own address, the ceiling and the accepted types
     (`evidence.upload_ticket`'s posture: not a pre-signed URL, `BR-WRK-047a`);
  2. sends the file to `POST /work/templates/{id}/help/documents` — stored
     through `document_store.store()` exactly as a phone photograph is, and
     answered with the document's id;
  3. saves the help row `{kind: "document", label, ref: <that id>}` with the
     help collection's existing PUT.

The template's page opens it at `GET /work/templates/{id}/help/documents/{doc}
/content` — same-origin bytes, because the page policy refuses a storage host
(`DEF-WRK-9594`'s reason). The phone already opens a stored document by its id
(`mobile._help_row`), so a job raised from the template carries it with no phone
change.

⚠ **WHICH TEMPLATE A FILE SERVES IS SAID BY THE HELP ROW, NOT BY THE STORE.**
Each file is its own source (`SOURCE_WORK_TEMPLATE_HELP`) because the store
allows one artefact per source and content type; `document_of` answers only for
a document one of THIS template's help rows names, so another template's id —
or another tenant's — reads as absent.
"""

from __future__ import annotations

from typing import Any

from apps.work import models
from apps.work.seams import metering_seam
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy
from core.dbfields import uuid7

#: 10 MiB — the ceiling every other document upload in this product uses
#: (`customers.account_documents.MAX_UPLOAD_BYTES`).
MAX_HELP_BYTES = 10 * 1024 * 1024

#: PDF, PNG, JPG — what a help pack is (an SOP, a diagram, a photograph of a
#: label). Both spellings of a JPEG, because scanners send `image/jpg`. A video
#: is a LINK (ruling 6), never an upload.
HELP_CONTENT_TYPES: tuple[str, ...] = ("application/pdf", "image/png", "image/jpeg", "image/jpg")
HELP_EXTENSIONS = ("PDF", "PNG", "JPG")


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _header_or_404(template_id: Any) -> dict[str, Any]:
    row = metering_seam.template(template_id)
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def _content_type(value: Any) -> str:
    media = str(value or "").split(";")[0].strip().lower()
    if media not in HELP_CONTENT_TYPES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="work.template.help_file_type",
            params={"allowed": ", ".join(HELP_EXTENSIONS)},
        )
    return media


def upload_ticket(template_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work/templates/{id}/help/upload-url` — where to send the file."""
    header = _header_or_404(template_id)
    payload = dict(payload or {})
    _content_type(payload.get("content_type"))
    return {
        "upload_url": f"/work/templates/{header['id']}/help/documents",
        "method": "POST",
        "field": "file",
        "max_bytes": MAX_HELP_BYTES,
        "content_types": list(HELP_CONTENT_TYPES),
    }


def store(actor: Any, template_id: Any, upload: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work/templates/{id}/help/documents` — store one help file.

    Bytes first, then the row (`document_store.store()` does both, in that
    order). Answers `{id, ref, name, content_type, bytes, url}`; `ref` is what
    the builder puts on the help row.
    """
    from apps.tenancy import document_models, document_store

    header = _header_or_404(template_id)
    if upload is None:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="work.lookups.required", params={"field": "file"}
        )
    content_type = _content_type(
        getattr(upload, "content_type", None) or (payload or {}).get("content_type")
    )
    body = upload.read() if hasattr(upload, "read") else bytes(upload or b"")
    if not body:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="work.lookups.required", params={"field": "file"}
        )
    if len(body) > MAX_HELP_BYTES:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key="work.template.help_file_too_large",
            params={"max_mb": str(MAX_HELP_BYTES // (1024 * 1024))},
        )
    name = str(getattr(upload, "name", None) or (payload or {}).get("filename") or "help").strip()
    ref = document_store.store(
        kind=document_models.KIND_WORK_TEMPLATE_HELP,
        source_type=document_models.SOURCE_WORK_TEMPLATE_HELP,
        source_id=uuid7(),
        content_type=content_type,
        display_name=name[:200] or "help",
        payload=body,
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
    )
    core_audit.write_row(
        action="work_order_template.help_document_stored",
        entity_type="work_order_template",
        entity_id=header["id"],
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        after={"name": ref.display_name, "content_type": content_type, "bytes": ref.byte_length},
    )
    return {
        "id": str(ref.id),
        "ref": str(ref.id),
        "name": ref.display_name,
        "content_type": ref.content_type,
        "bytes": ref.byte_length,
        "url": content_path(header["id"], ref.id),
    }


def content_path(template_id: Any, document_id: Any) -> str:
    """The same-origin path the template's page opens a help document at."""
    return f"/work/templates/{template_id}/help/documents/{document_id}/content"


def _named_by_template(template_id: Any, document_id: Any) -> bool:
    return models.WorkOrderTemplateHelp.objects.filter(
        tenant_id=_tenant_id(),
        template_id=template_id,
        kind=models.HELP_KIND_DOCUMENT,
        ref=str(document_id),
    ).exists()


def document_of(template_id: Any, document_id: Any) -> dict[str, Any] | None:
    """`{id, name, content_type, bytes}` for a help document THIS template's help
    rows name, else None — a label typed before uploads existed (*SOP-W-12*),
    another template's file and another tenant's all read as no file."""
    from apps.tenancy import document_models, document_store

    if not _named_by_template(template_id, document_id):
        return None
    try:
        ref = document_store.reference(document_id)
    except (document_store.DocumentStoreError, ValueError):
        return None
    if ref.kind != document_models.KIND_WORK_TEMPLATE_HELP:
        return None
    return {
        "id": str(ref.id),
        "name": ref.display_name,
        "content_type": ref.content_type,
        "bytes": ref.byte_length,
    }


def content(template_id: Any, document_id: Any) -> tuple[bytes, str, str]:
    """`(bytes, content_type, name)` for the content route, or a 404 identical
    to a document that does not exist (hard rule 1)."""
    from apps.tenancy import document_store

    _header_or_404(template_id)
    found = document_of(template_id, document_id)
    if found is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return document_store.fetch(document_id), found["content_type"], found["name"]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-168-BRC10 §7.3 (POST /work/templates/{id}/help/upload-url) · §16
# generated: 2026-10-04 by CR-168 round 4 lane SRV-3
# checklist: A✔ B✔ C=n/a D✔ E=n/a F✔ G✔ H=n/a
# gates: G78 (the tenancy store is the platform's, as evidence.py uses it) · pytest
# status: AI-AUTHORED
# ──────────────────────────────────────────────────────────
