# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-9641 — a field photograph over 100 KB was refused and lost.
# Change:   CR-168-BRC10 §F, lane FIELD-FIX
# Rules:    BR-WRK-047 (as SUPERSEDED in its refusal clauses, PO 2026-10-04:
#           "we have to ensure phone is copressing it - but you cannot reject
#           the photo - that will drop the data")
# ───────────────────────────────────────────────────────
"""A real image of any size is accepted and stored shrunk; a non-image is not
a photograph and is still refused."""

from __future__ import annotations

import io
import os

import pytest

from apps.tenancy.document_models import StoredDocument
from apps.work import evidence, work_documents
from apps.work import models as work_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import field_actor, tenant_ctx
from tests.test_us_wrk_032_copies import _published_template, _raise

pytestmark = pytest.mark.django_db


def big_jpeg(min_bytes: int = 2 * 1024 * 1024) -> bytes:
    """A noisy 2,400 x 1,800 JPEG at quality 95 — over 2 MB, as a phone camera
    gives before anything compresses it."""
    from PIL import Image

    image = Image.frombytes("RGB", (2400, 1800), os.urandom(2400 * 1800 * 3))
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=95)
    data = out.getvalue()
    assert len(data) >= min_bytes, len(data)
    return data


def _job(actor, tenant):
    oid = _raise(actor, tenant, _published_template(actor, tenant))["id"]
    return oid, field_actor(oid, actor)


def test_9641_a_2mb_jpeg_is_accepted_and_stored_at_100kb_or_less(brazos, dana):
    raw = big_jpeg()
    with tenant_ctx(brazos):
        oid, tech = _job(dana, brazos)
        task = work_models.WorkOrderTask.objects.filter(
            work_order_id=oid, photo_required=True
        ).first()
        row = evidence.record_attachment(
            tech, oid, {"idempotency_key": "big-1", "task_id": str(task.id)}, raw
        )
        stored = work_models.WorkOrderAttachment.objects.get(pk=row["id"])
        doc = StoredDocument.objects.get(pk=stored.document_id)
        task.refresh_from_db()

    assert doc.byte_length <= work_documents.MAX_PHOTO_BYTES, doc.byte_length
    assert str(task.photo_attachment_id) == row["id"]


def test_9641_a_text_file_is_still_refused(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = _job(dana, brazos)
        with pytest.raises(errors.ValidationError) as refused:
            evidence.record_attachment(
                tech, oid, {"idempotency_key": "txt-1"}, b"this is not a photograph\n" * 10
            )

    assert refused.value.message_key == "work.attachment.not_an_image"
