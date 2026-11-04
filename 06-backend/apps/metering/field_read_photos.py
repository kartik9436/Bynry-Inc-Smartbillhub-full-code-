# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 · DEF-FLD-10357 (lane INTEGRATE-2) — a route
#           photograph's door: declared with the data, bytes after
# Rules:    BR-WRK-062's shape (the link is created WITH the record) ·
#           R61 / R125 (the handset deletes its copy only once the bytes are
#           durable) · CLAUDE.md hard rules 1, 6, 7 · hard-won law 14
# Tests:    06-backend/tests/test_cr187_route_photos.py ·
#           06-backend/tests/test_cr187_route_photos_pg.py
# ───────────────────────────────────────────────────────
"""A ROUTE photograph: the link made with the declaring item, the bytes after.

`apps/work/photo_links.py` is the job door's version and the model for this
one; it cannot serve a route because its link belongs to a WORK ORDER, and a
route has none. The two steps:

1. `declare()` — called inside the savepoint of a reads-door item of kind
   `photo` (`field_reads._judge_photo`): the phone's own `photo_id`, the
   `sha256` of the bytes it will send. Creates the `field_read_photos` row (or
   answers the one already there — idempotent on `photo_id`) and gives the
   `upload_url`.
2. `receive_bytes()` — `PUT work/mobile/reads/photos/{photo_id}`: the hash is
   checked against the declaration (a mismatch keeps nothing and is asked for
   again, 409); a file that is not an image is refused; otherwise the bytes are
   kept on the row and the link is `landed`. A second upload adds nothing.

Any field login of the tenant may carry the bytes — on a shared tablet the
courier is whoever is signed in — because the declaration fixed whose
photograph it is (the CAPTOR, from the item's capture token) and the hash
fixes which bytes. The job door reasons the same way.
"""

from __future__ import annotations

import hashlib
import io
import uuid
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.metering.field_read_models import FieldReadPhoto
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy

BR_REF = "BR-WRK-062"


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def upload_url(photo_id: Any) -> str:
    """The same-origin address the bytes go to (`/api/<tenant>/work/mobile/reads/photos/<id>`)."""
    from apps.tenancy import models as tenancy_models

    row = tenancy_models.Tenant.objects.filter(pk=_tenant_id()).only("subdomain").first()
    slug = row.subdomain if row is not None else ""
    return f"/api/{slug}/work/mobile/reads/photos/{photo_id}"


def answer(link: FieldReadPhoto) -> dict[str, Any]:
    return {"photo_id": str(link.photo_id), "upload_url": upload_url(link.photo_id), "state": link.state}


class DeclarationRefused(Exception):
    """The declaration cannot be a link — `reason` is the reads door's word."""

    def __init__(self, reason: str, detail: dict[str, Any] | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail or {}


def declare(
    *, photo_id: Any, sha256: Any, key: str, reader_id: Any, route: Any, captured_at: Any
) -> FieldReadPhoto:
    """The link for one route photograph. Runs inside the caller's savepoint."""
    try:
        pid = uuid.UUID(str(photo_id or ""))
    except ValueError:
        raise DeclarationRefused("photo_id_required") from None
    digest = str(sha256 or "").strip().lower()
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise DeclarationRefused("photo_sha256_required")
    existing = FieldReadPhoto.objects.filter(tenant_id=_tenant_id(), photo_id=pid).first()
    if existing is not None:
        if existing.sha256 != digest:
            # Two different photographs under one id: never resolved to either.
            raise DeclarationRefused("photo_id_reused", {"photo_id": str(pid)})
        return existing
    return FieldReadPhoto.objects.create(
        tenant_id=_tenant_id(),
        photo_id=pid,
        sha256=digest,
        key=key,
        reader_id=reader_id,
        route=route,
        device_captured_at=captured_at,
    )


def link_answer_for(photo_id: Any) -> dict[str, Any] | None:
    link = FieldReadPhoto.objects.filter(tenant_id=_tenant_id(), photo_id=photo_id).first()
    return answer(link) if link is not None else None


def _probe(data: bytes) -> None:
    from PIL import Image, UnidentifiedImageError

    try:
        Image.open(io.BytesIO(data)).verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise errors.ValidationError(
            errors.VAL_FORMAT, br_ref="BR-WRK-047", message_key="work.attachment.not_an_image"
        ) from None


def receive_bytes(actor: Any, photo_id: Any, data: bytes, content_type: str = "") -> dict[str, Any]:
    """`PUT work/mobile/reads/photos/{photo_id}` — the bytes, to the link."""
    link = FieldReadPhoto.objects.filter(tenant_id=_tenant_id(), photo_id=photo_id).first()
    if link is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    if link.state == FieldReadPhoto.STATE_LANDED:
        return {**answer(link), "duplicate": True}
    if hashlib.sha256(data or b"").hexdigest() != link.sha256:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref=BR_REF,
            message_key="work.photo.hash_mismatch",
            params={"photo_id": str(photo_id), "bytes": len(data or b"")},
        )
    _probe(data)
    with transaction.atomic():
        landed = FieldReadPhoto.objects.filter(
            pk=link.pk, state=FieldReadPhoto.STATE_PENDING
        ).update(
            data=data,
            content_type=str(content_type or "image/jpeg"),
            bytes_received=len(data),
            state=FieldReadPhoto.STATE_LANDED,
            landed_at=timezone.now(),
        )
        if landed:
            core_audit.write_row(
                action="field_reads.photo_landed",
                entity_type="field_read_photo",
                entity_id=link.id,
                actor_user_id=getattr(actor, "id", None),
                after={
                    "photo_id": str(link.photo_id),
                    "bytes_received": len(data),
                    "declared_by": str(link.reader_id) if link.reader_id else None,
                    "br_ref": BR_REF,
                },
            )
    link.refresh_from_db()
    return {**answer(link), "duplicate": not landed}


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-187-BRC10 · DEF-FLD-10357 · lane INTEGRATE-2
# generated: 2026-10-21
# gates: pytest tests/test_cr187_route_photos.py (SQLite) and
#        tests/test_cr187_route_photos_pg.py (PostgreSQL 16)
# status: AI-AUTHORED · HUMAN-REVIEW-PENDING (writes a new RLS table)
# ──────────────────────────────────────────────────────────
