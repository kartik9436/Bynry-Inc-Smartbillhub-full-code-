# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-10625 — every refusal recorded on the phone was refused by
#           the server ("A refusal needs a door-hanger photo."), and a signed
#           mark could not travel at all: the phone names its photographs by
#           its OWN photo id and uploads the bytes later on signal, while
#           `capture_signature` demanded an attachment that already existed
#           (refused) or inline bytes (signed).
# Ruling:   PO 2026-10-27 "start ... the signature fix" (decision log, same day)
# Rules:    BR-WRK-046 (signed or refused, never both) · BR-WRK-062 (the link is
#           created with the record, the bytes follow)
# ───────────────────────────────────────────────────────
"""The phone's signature item, through the sync, in the phone's own shape."""

from __future__ import annotations

import hashlib
import uuid

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.work import evidence, photo_links, sync
from apps.work import models as work_models
from apps.work.evidence_models import WorkPhotoLink
from core import errors

from tests.test_cr168_technician_api import FIX, _ready, _token
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_wrk_032_copies import _published_template, _raise
from tests.test_us_wrk_047_049_evidence import TINY_PNG

pytestmark = pytest.mark.django_db

DIGEST = hashlib.sha256(TINY_PNG).hexdigest()


def _item(token, key, kind, seq, payload):
    return {
        "key": key, "kind": kind, "seq": seq, "captured_at": "2026-03-15T15:40:00Z",
        "capture_token": token, "location": FIX, "payload": payload,
    }


def _refusal_then_photo(token, pid):
    """EXACTLY what the phone's outbox sends: the signature act at seq n and its
    photo declaration at n+1 (`outbox.capture` declares photos after the act)."""
    return [
        _item(token, "sig-1", "signature", 10, {
            "refused": True, "decline_reason": "Nobody home", "signed_at": "2026-03-15T15:40:00Z",
            "door_hanger_photo_id": pid, "door_hanger_sha256": DIGEST,
        }),
        _item(token, "photo-1", "photo", 11, {"photo_id": pid, "sha256": DIGEST}),
    ]


def _template_of(order_id):
    from apps.work import connection_models as work_tables

    return work_tables.WorkOrder.objects.get(pk=order_id).template_id


def _land(tech, pid):
    photo_links.receive_bytes(tech, pid, TINY_PNG, "image/png")
    link = WorkPhotoLink.objects.get(photo_id=pid)
    photo_links.run_photo_job({"payload": {"link_id": str(link.id)}})
    return WorkPhotoLink.objects.get(photo_id=pid)


def test_a_phone_refusal_is_accepted_before_its_photo_has_uploaded(brazos, dana):
    """The PO's report: Refused → Nobody home → photo → Record refusal → Sync."""
    with tenant_ctx(brazos):
        oid, tech = _ready(dana, brazos)
        pid = str(uuid.uuid4())
        out = sync.sync_batch(tech, oid, {"items": _refusal_then_photo(_token(tech), pid)})
        answers = {i["key"]: i for i in out["items"]}
        row = work_models.WorkOrderSignature.objects.filter(work_order_id=oid).first()
        before = evidence.signature_for_order(oid)

    assert answers["sig-1"]["result"] == "accepted", answers["sig-1"]
    assert answers["photo-1"]["result"] == "accepted", answers["photo-1"]
    assert row.refused is True and str(row.door_hanger_photo_id) == pid
    assert row.door_hanger_id is None
    assert before["door_hanger_attachment_id"] is None
    assert before["door_hanger_uploading"] is True


def test_the_door_hanger_is_shown_to_the_office_once_its_bytes_arrive(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = _ready(dana, brazos)
        pid = str(uuid.uuid4())
        sync.sync_batch(tech, oid, {"items": _refusal_then_photo(_token(tech), pid)})
        link = _land(tech, pid)
        after = evidence.signature_for_order(oid)

    assert link.attachment_id is not None
    assert after["door_hanger_attachment_id"] == str(link.attachment_id)
    assert after["door_hanger_uploading"] is False


def test_a_photo_declared_first_is_found_by_its_id_alone(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = _ready(dana, brazos)
        pid = str(uuid.uuid4())
        token = _token(tech)
        out = sync.sync_batch(tech, oid, {"items": [
            _item(token, "photo-1", "photo", 1, {"photo_id": pid, "sha256": DIGEST}),
            _item(token, "sig-1", "signature", 2, {
                "refused": True, "decline_reason": "Declined", "door_hanger_photo_id": pid,
            }),
        ]})

    assert [i["result"] for i in out["items"]] == ["accepted", "accepted"], out["items"]


def test_a_photo_declared_on_another_job_is_not_this_refusals_evidence(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = _ready(dana, brazos)
        other = _raise(dana, brazos, _template_of(oid))["id"]
        pid = str(uuid.uuid4())
        photo_links.declare(dana, other, {"photo_id": pid, "sha256": DIGEST})
        with pytest.raises(errors.ValidationError) as refused:
            evidence.capture_signature(tech, oid, {
                "refused": True, "decline_reason": "Declined", "door_hanger_photo_id": pid,
            })

    assert refused.value.message_key == "work.signature.door_hanger_required"


def test_a_photo_id_nobody_declared_and_no_hash_is_still_refused(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = _ready(dana, brazos)
        with pytest.raises(errors.ValidationError) as refused:
            evidence.capture_signature(tech, oid, {
                "refused": True, "decline_reason": "Declined", "door_hanger_photo_id": str(uuid.uuid4()),
            })

    assert refused.value.message_key == "work.signature.door_hanger_required"


def test_a_signed_mark_travels_as_a_declared_photo(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = _ready(dana, brazos)
        pid = str(uuid.uuid4())
        token = _token(tech)
        out = sync.sync_batch(tech, oid, {"items": [
            _item(token, "sig-1", "signature", 10, {
                "refused": False, "printed_name": "S. Miller", "signed_at": "2026-03-15T15:40:00Z",
                "image_photo_id": pid, "image_sha256": DIGEST,
            }),
            _item(token, "photo-1", "photo", 11, {"photo_id": pid, "sha256": DIGEST}),
        ]})
        row = work_models.WorkOrderSignature.objects.filter(work_order_id=oid).first()
        before = evidence.signature_for_order(oid)
        with pytest.raises(errors.NotFoundError):
            evidence.signature_image_bytes(oid)
        _land(tech, pid)
        after = evidence.signature_for_order(oid)
        data, _ = evidence.signature_image_bytes(oid)

    assert [i["result"] for i in out["items"]] == ["accepted", "accepted"], out["items"]
    assert row.refused is False and row.image_id is None and str(row.image_photo_id) == pid
    assert before["image_url"] is None
    assert after["image_url"] and after["image_url"].endswith("/signature/image")
    assert data


def test_the_web_paths_are_unchanged(brazos, dana):
    """The office's form: an existing attachment, and multipart bytes."""
    from tests.test_us_wrk_047_049_evidence import _order, _upload

    with tenant_ctx(brazos):
        oid = _order(dana, brazos)
        hanger = _upload(dana, oid, "img-hanger")
        out = evidence.capture_signature(dana, oid, {
            "refused": True, "decline_reason": "Declined", "door_hanger_attachment_id": hanger["id"],
        })
        oid2 = _raise(dana, brazos, _template_of(oid))["id"]
        signed = evidence.capture_signature(dana, oid2, {"printed_name": "S. Miller"}, TINY_PNG)

    assert out["door_hanger_attachment_id"] == hanger["id"]
    assert signed["image_url"]


def _raw(oid, tenant_id, **fields):
    with transaction.atomic():
        work_models.WorkOrderSignature.objects.create(
            tenant_id=tenant_id, work_order_id=oid, signed_at=timezone.now(), **fields
        )


def test_the_check_constraint_takes_a_photo_id_in_place_of_the_file(brazos, dana):
    """`ck_work_order_signatures_shape`: refused needs the attachment OR the
    phone's photo id; signed needs the image OR its photo id; never both shapes."""
    with tenant_ctx(brazos):
        tid = brazos.id
        tpl = _published_template(dana, brazos)
        a, b, c, d = (_raise(dana, brazos, tpl)["id"] for _ in range(4))
        _raw(a, tid, refused=True, decline_reason="Declined", door_hanger_photo_id=uuid.uuid4())
        _raw(b, tid, refused=False, printed_name="S. Miller", image_photo_id=uuid.uuid4())
        with pytest.raises(IntegrityError):
            _raw(c, tid, refused=True, decline_reason="Declined")
        with pytest.raises(IntegrityError):
            _raw(c, tid, refused=False, printed_name="S. Miller")
        with pytest.raises(IntegrityError):
            _raw(d, tid, refused=True, decline_reason="Declined",
                 door_hanger_photo_id=uuid.uuid4(), image_photo_id=uuid.uuid4())
        with pytest.raises(IntegrityError):
            _raw(d, tid, refused=False, printed_name="S. Miller",
                 image_photo_id=uuid.uuid4(), door_hanger_photo_id=uuid.uuid4())
