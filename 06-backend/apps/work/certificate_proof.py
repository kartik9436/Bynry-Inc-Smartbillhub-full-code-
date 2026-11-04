# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 5, lane SRV-4 — image 33's PROOF column: a
#           technician's certificate held as a file (the server gap lane CREWS
#           reported, CR §19). Ruling 28 (*"here certification tab wireframe is
#           missing"* — a table with add and renew).
# Rules:    PO answer (2) of 2026-10-04 (a lapsed certification WARNS, never
#           blocks — `BR-WRK-030` SUPERSEDED) · CLAUDE.md hard rule 1 (a
#           cross-tenant id reads as absent) · hard rule 7 (audited)
# Tests:    06-backend/tests/test_cr168_srv4_crews.py
# ───────────────────────────────────────────────────────
"""A certificate's PROOF — the scan or photograph of the certificate itself.

`technician_certifications.evidence_document_id` has existed since wave F and
nothing ever wrote it, so image 33's PROOF column could only ever draw a dash.

    POST /work/technicians/{slug}/certifications/{type_id}/proof   (multipart `file`)
      → {id, name, content_type, bytes, url}
    GET  /work/technicians/{slug}/certifications/{type_id}/proof/content
      → the bytes, same-origin, `private, no-store`

Stored through the platform's document store (`tenancy.document_store`, kind
`work_certificate_proof`, `tenancy/0060`) exactly as a template's help document
is (`template_help.py`), and for its reason each upload is its own source. The
certificate row names the file it is proved by; the content route answers ONLY
for that file, so another technician's or another tenant's id reads as absent.

⚠ **A PROOF NEVER CHANGES WHETHER THE CERTIFICATE COUNTS.** PO answer (2): a
lapsed certification warns and never blocks. A proof is evidence for whoever
asks, not a gate; nothing in assignment or advice reads it.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.work import models as work_models
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy
from core.dbfields import uuid7

MAX_PROOF_BYTES = 10 * 1024 * 1024
PROOF_CONTENT_TYPES: tuple[str, ...] = ("application/pdf", "image/png", "image/jpeg", "image/jpg")


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _certification(technician_id: Any, type_id: Any) -> Any:
    row = work_models.TechnicianCertification.objects.filter(
        tenant_id=_tenant_id(), technician_id=technician_id, certification_type_id=type_id
    ).first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def content_path(slug: str, type_id: Any) -> str:
    return f"/work/technicians/{slug}/certifications/{type_id}/proof/content"


def proof_of(row: Any, slug: str) -> dict[str, Any] | None:
    """`{id, name, content_type, bytes, url}` for the certificate's proof, or
    None — the PROOF column's dash."""
    from apps.tenancy import document_models, document_store

    if not row.evidence_document_id:
        return None
    try:
        ref = document_store.reference(row.evidence_document_id)
    except (document_store.DocumentStoreError, ValueError):
        return None
    if ref.kind != document_models.KIND_WORK_CERTIFICATE_PROOF:
        return None
    return {
        "id": str(ref.id),
        "name": ref.display_name,
        "content_type": ref.content_type,
        "bytes": ref.byte_length,
        "url": content_path(slug, row.certification_type_id),
    }


def store(actor: Any, technician: dict[str, Any], type_id: Any, upload: Any) -> dict[str, Any]:
    """`POST …/certifications/{type_id}/proof` — store the file and point the
    certificate at it (a renewal's new scan REPLACES the pointer; the old file
    stays in the store on its schedule, because a job done under the old
    certificate is proved by it). Audited (hard rule 7)."""
    from apps.tenancy import document_models, document_store

    row = _certification(technician["id"], type_id)
    if upload is None:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="work.lookups.required", params={"field": "file"}
        )
    content_type = str(getattr(upload, "content_type", "") or "").split(";")[0].strip().lower()
    if content_type not in PROOF_CONTENT_TYPES:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="work.template.help_file_type",
            params={"allowed": "PDF, PNG, JPG"},
        )
    body = upload.read() if hasattr(upload, "read") else bytes(upload or b"")
    if not body:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="work.lookups.required", params={"field": "file"}
        )
    if len(body) > MAX_PROOF_BYTES:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            message_key="work.template.help_file_too_large",
            params={"max_mb": str(MAX_PROOF_BYTES // (1024 * 1024))},
        )
    name = str(getattr(upload, "name", None) or "certificate").strip()[:200] or "certificate"
    actor_id = getattr(actor, "id", None) or getattr(actor, "pk", None)
    with transaction.atomic():
        ref = document_store.store(
            kind=document_models.KIND_WORK_CERTIFICATE_PROOF,
            source_type=document_models.SOURCE_WORK_CERTIFICATE_PROOF,
            source_id=uuid7(),
            content_type=content_type,
            display_name=name,
            payload=body,
            actor_user_id=actor_id,
        )
        before = str(row.evidence_document_id) if row.evidence_document_id else None
        row.evidence_document_id = ref.id
        row.save(update_fields=["evidence_document_id", "updated_at"])
        core_audit.write_row(
            action="work.technician.certificate_proof_stored",
            entity_type="technician",
            entity_id=technician["id"],
            actor_user_id=actor_id,
            before={"proof": before},
            after={"certification_type_id": str(type_id), "name": ref.display_name,
                   "bytes": ref.byte_length},
        )
    return proof_of(row, technician["slug"]) or {}


def content(technician: dict[str, Any], type_id: Any) -> tuple[bytes, str, str]:
    """`(bytes, content_type, name)`, or a 404 identical to an absent file."""
    from apps.tenancy import document_store

    row = _certification(technician["id"], type_id)
    found = proof_of(row, technician["slug"])
    if found is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return document_store.fetch(found["id"]), found["content_type"], found["name"]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-168-BRC10 §19 (lane CREWS's server needs) · image 33
# generated: 2026-10-04 by CR-168 round 5 lane SRV-4
# checklist: A✔ B✔ C=n/a D✔ E=n/a F✔ G✔ H=tenancy/0060 (🔒, review-ledger row)
# gates: G78 (the tenancy store is the platform's, as evidence.py and template_help.py use it)
# status: AI-AUTHORED
# ──────────────────────────────────────────────────────────
