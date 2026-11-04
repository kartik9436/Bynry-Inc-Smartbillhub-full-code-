# ── Trace ──────────────────────────────────────────────
# Change:   CR-168-BRC10 §F — the technician API's photographs (PO 2026-10-04:
#           "images are async job with link created and saved in data record";
#           corrected: "link you ahve to create along with data record and pass
#           it to async job - otherway round"; "you cannot reject the photo";
#           TECHNICIAN SYNC DESIGN (4); the accept hold, ruled (a))
# Rules:    BR-WRK-062 · BR-WRK-047 (as superseded) · BR-WRK-040 · hard rules
#           1 and 7 · hard-won law 14
# Tests:    06-backend/tests/test_cr168_technician_api.py
# ───────────────────────────────────────────────────────
"""THE LINK IS CREATED WITH THE RECORD; THE BYTES FOLLOW IN THE BACKGROUND.

1. The phone's data page carries a `photo` item: its own `photo_id` (a client
   uuid), the `sha256` of the bytes it will send, and the task or reading it
   is for. `declare()` saves a `work_photo_links` row in the SAME save as the
   rest of the page and answers the link (`upload_url`). Re-sending the page
   answers the SAME link (unique `(tenant, photo_id)`).
2. The phone uploads the bytes to that link whenever it has a signal
   (`receive_bytes()`): the hash is checked against the declaration (a
   mismatch is asked for again, nothing stored); a non-image is refused;
   anything else is STAGED on the link and a background job is enqueued
   through `core.jobs`, the repo's one job mechanism.
3. The job (`run_photo_job`) shrinks what arrived to the band if it is over
   the ceiling (never refuses), files it as an evidence attachment for the
   task or reading, clears the staged bytes (only the compressed copy is
   kept) and marks the link LANDED. Re-uploading to a landed link adds
   nothing.
4. Until it lands, a link is PENDING — never missing. A close is accepted with
   its required photos pending; the office's ACCEPT is held while any
   REQUIRED link is pending (PO 2026-10-04, (a): *"Dana sees \\"3 photos
   uploading\\", and Accept stays unavailable until they've all arrived"*).
"""

from __future__ import annotations

import hashlib
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.work import evidence, work_documents
from apps.work import models
from apps.work.evidence_models import WorkPhotoLink
from core import audit as core_audit
from core import errors
from core import jobs as core_jobs
from core import tenancy as core_tenancy

#: The `core.jobs` kind the background filing runs under.
PHOTO_JOB = "work.photo_file"
#: A link still empty this long is LISTED for the office, never deleted
#: (TECHNICIAN SYNC DESIGN (4)).
STALE_AFTER_HOURS = 24


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None)


def _upload_url(photo_id: Any) -> str:
    from apps.work.seams import tenancy_seam

    return f"/api/{tenancy_seam.tenant_slug()}/work/mobile/photos/{photo_id}"


def _answer(link: WorkPhotoLink) -> dict[str, Any]:
    return {
        "photo_id": str(link.photo_id),
        "upload_url": _upload_url(link.photo_id),
        "state": link.state,
        "attachment_id": str(link.attachment_id) if link.attachment_id else None,
    }


def link_answer_for(photo_id: Any) -> dict[str, Any] | None:
    link = WorkPhotoLink.objects.filter(tenant_id=_tenant_id(), photo_id=photo_id).first()
    return _answer(link) if link is not None else None


def declare(actor: Any, order_id: Any, body: dict[str, Any], *, taken_at: Any = None) -> dict[str, Any]:
    """Create the link for one photograph, in the record's own save."""
    import uuid

    try:
        photo_id = uuid.UUID(str(body.get("photo_id") or ""))
    except ValueError:
        raise errors.ValidationError(
            errors.VAL_FORMAT, br_ref="BR-WRK-062", message_key="work.photo.id_required"
        ) from None
    digest = str(body.get("sha256") or "").strip().lower()
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise errors.ValidationError(
            errors.VAL_FORMAT, br_ref="BR-WRK-062", message_key="work.photo.sha256_required"
        )
    reading_row, task_row = evidence._checklist_target(_tenant_id(), order_id, body)
    owner = reading_row or task_row
    existing = WorkPhotoLink.objects.filter(tenant_id=_tenant_id(), photo_id=photo_id).first()
    if existing is not None:
        return _answer(existing)
    with transaction.atomic():
        link = WorkPhotoLink.objects.create(
            tenant_id=_tenant_id(),
            work_order_id=order_id,
            photo_id=photo_id,
            sha256=digest,
            reading_id=reading_row.id if reading_row else None,
            task_id=task_row.id if task_row else None,
            required=bool(getattr(owner, "photo_required", False)),
            taken_at=taken_at or timezone.now(),
            captured_by_id=_actor_id(actor),
        )
    return _answer(link)


# ⚠ `declare_held` — the link for a photograph whose data item was HELD for
# review (`DEF-WRK-9652`) — WAS DELETED 2026-10-21 with its one caller. The PO's
# correction (*"back to the technician"*, `BR-WRK-063` superseded for field
# items) means a photo the server cannot accept is REFUSED and kept on the
# phone, bytes and all, so there is no held item for a link to belong to; the
# fixed item is resent and `declare` makes its link exactly as for any other.
# Links it made before the ruling are ordinary rows and upload as before.


def receive_bytes(actor: Any, photo_id: Any, data: bytes, content_type: str = "") -> dict[str, Any]:
    """`PUT /work/mobile/photos/{photo_id}` — the bytes, to the link.

    Idempotent: a LANDED or STAGED link answers its state and adds nothing. A
    hash that does not match the declaration is refused (409) and nothing is
    kept, so the phone sends it again — a half-sent photo is never stored
    broken. A file that is not an image is refused (DEF-WRK-9641's one
    remaining refusal).
    """
    link = WorkPhotoLink.objects.filter(tenant_id=_tenant_id(), photo_id=photo_id).first()
    if link is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    if link.state in (WorkPhotoLink.STATE_LANDED, WorkPhotoLink.STATE_STAGED):
        return {**_answer(link), "duplicate": True}
    if hashlib.sha256(data or b"").hexdigest() != link.sha256:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-WRK-062",
            message_key="work.photo.hash_mismatch",
            params={"photo_id": str(photo_id), "bytes": len(data or b"")},
        )
    try:
        _probe(data)
    except work_documents.NotAnImage:
        raise errors.ValidationError(
            errors.VAL_FORMAT, br_ref="BR-WRK-047", message_key="work.attachment.not_an_image"
        ) from None
    with transaction.atomic():
        updated = WorkPhotoLink.objects.filter(
            pk=link.pk, state=WorkPhotoLink.STATE_PENDING
        ).update(
            staged=data,
            content_type=str(content_type or "image/jpeg"),
            bytes_received=len(data),
            state=WorkPhotoLink.STATE_STAGED,
        )
    link.refresh_from_db()
    if not updated:
        return {**_answer(link), "duplicate": True}
    record = core_jobs.enqueue(PHOTO_JOB, payload={"link_id": str(link.id)}, scope_key=str(link.id))
    link.refresh_from_db()
    return {**_answer(link), "duplicate": False, "job_id": str(record.get("id") or "")}


def _probe(data: bytes) -> None:
    from PIL import Image, UnidentifiedImageError
    import io

    try:
        Image.open(io.BytesIO(data)).verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise work_documents.NotAnImage(str(exc)) from exc


def run_photo_job(record: dict[str, Any]) -> str | None:
    """The background half: shrink, file, clear, land. Idempotent — a link
    already landed is a no-op, and the attachment's idempotency key is the
    photo id, so a retried job cannot file the photograph twice."""
    from types import SimpleNamespace

    link_id = (record.get("payload") or {}).get("link_id")
    link = WorkPhotoLink.objects.filter(tenant_id=_tenant_id(), pk=link_id).first()
    if link is None or link.state == WorkPhotoLink.STATE_LANDED:
        return None
    data = bytes(link.staged or b"")
    actor = SimpleNamespace(id=link.captured_by_id, role="field_technician")
    payload: dict[str, Any] = {
        "idempotency_key": f"photo-{link.photo_id}",
        "taken_at": link.taken_at,
        "content_type": link.content_type or "image/jpeg",
        "device": "",
    }
    if link.task_id:
        payload["task_id"] = str(link.task_id)
    if link.reading_id:
        payload["reading_id"] = str(link.reading_id)
    with transaction.atomic():
        row = evidence.record_attachment(actor, link.work_order_id, payload, data)
        stored = models.WorkOrderAttachment.objects.get(pk=row["id"])
        from apps.tenancy.document_models import StoredDocument

        kept = StoredDocument.objects.filter(pk=stored.document_id).values_list(
            "byte_length", flat=True
        ).first()
        WorkPhotoLink.objects.filter(pk=link.pk).update(
            staged=None,
            attachment_id=row["id"],
            bytes_stored=kept,
            state=WorkPhotoLink.STATE_LANDED,
            landed_at=timezone.now(),
        )
        core_audit.write_row(
            action="work.photo.landed",
            entity_type="work_order",
            entity_id=link.work_order_id,
            actor_user_id=link.captured_by_id,
            after={
                "photo_id": str(link.photo_id),
                "bytes_received": link.bytes_received,
                "bytes_stored": kept,
                "attachment_id": row["id"],
            },
        )
    # TECHNICIAN SYNC DESIGN (5) — the last REQUIRED photo of a closed job has
    # landed, so Accept is available: the office is told. Never raises.
    from apps.work import office_notices

    office_notices.after_photo_landed(link.work_order_id, required=link.required)
    return None


def pending_required(order_id: Any) -> int:
    """How many REQUIRED photographs of this job are still uploading."""
    return WorkPhotoLink.objects.filter(
        tenant_id=_tenant_id(), work_order_id=order_id, required=True
    ).exclude(state=WorkPhotoLink.STATE_LANDED).count()


def refuse_accept_while_uploading(order_id: Any) -> None:
    """PO 2026-10-04, (a): Accept is unavailable while any REQUIRED photo is
    still uploading. Optional photos never hold it. Called by metering's
    `accept_field_result`, below every door."""
    count = pending_required(order_id)
    if count:
        raise errors.BizError(
            errors.BIZ_LOCKED,
            br_ref="BR-WRK-062",
            message_key="work.order.photos_uploading",
            params={"count": count},
        )


def stale_links(*, hours: int = STALE_AFTER_HOURS, page: int = 1, per: int = 50) -> dict[str, Any]:
    """Links still empty after `hours` — LISTED for the office, never deleted.
    Paged (NFR-3): `{count, page, results}`, no cap."""
    from core.pagination import clamp_page_size

    cutoff = timezone.now() - timezone.timedelta(hours=hours)
    qs = WorkPhotoLink.objects.filter(
        tenant_id=_tenant_id(), state=WorkPhotoLink.STATE_PENDING, created_at__lt=cutoff
    ).order_by("created_at", "id")
    size = clamp_page_size(per)
    number = max(1, int(page or 1))
    rows = qs[(number - 1) * size : number * size]
    return {
        "count": qs.count(),
        "page": number,
        "results": [
            {
                "photo_id": str(row.photo_id),
                "work_order_id": str(row.work_order_id),
                "required": row.required,
                "declared_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
    }


def register() -> None:
    """The background filing's body AND queue — `push.register`'s shape."""
    from apps.work.push import WORK_QUEUE

    core_jobs.set_job_handler(PHOTO_JOB, run_photo_job)
    core_jobs.set_job_queue(PHOTO_JOB, WORK_QUEUE)
