# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-WRK-9652 — a photograph whose data item the server HELD for
#          review got no link, so its bytes could never be uploaded: they stayed
#          on the tablet for ever and "N waiting to send" never reached 0
#          (WO-0046 in lane FIELD-2's walk: six items held "accept the job
#          first", the meter photo's bytes stuck).
# Rules:   TECHNICIAN SYNC DESIGN (decision log, 2026-10-04) — *"we cant drop
#          data record in sync process both ways"* · **BR-WRK-063 SUPERSEDED for
#          field items 2026-10-21** (PO: *"back to the technician"*) · (4) the
#          link is created with the record · hard-won law 14 (savepoint).
# Change:  CR-168-BRC10 round 6, lane CREWS-2; REWRITTEN by CR-187-BRC10.
# ───────────────────────────────────────────────────────
"""A photo the server cannot accept goes BACK — and its bytes are never stuck.

⚠ **REWRITTEN 2026-10-21.** This file proved that a HELD photo got a link so
its bytes could leave the tablet (`photo_links.declare_held`). The PO then
corrected the sync — something the server cannot accept goes back to the
technician — so there is no held photo any more: the item is REFUSED, kept on
the phone with its bytes, and resent once fixed, when `declare` makes its link
like any other. `DEF-WRK-9652`'s complaint (bytes with nowhere to go, for ever)
is still the thing asserted: a refused photo is not acknowledged, so the phone
does NOT count it as sent, and the resend gets a link.
"""

from __future__ import annotations

import hashlib
import uuid

from apps.work import mobile, photo_links, sync
from apps.work import models as work_models
from apps.work.evidence_models import WorkPhotoLink
from apps.work.sync_models import WorkSyncReceipt

from tests.test_cr168_technician_api import FIX, _job, _ready, _token
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_wrk_047_049_evidence import TINY_PNG

import pytest

pytestmark = pytest.mark.django_db


def _photo(token, *, key="held-photo-1", target=None):
    payload = {"photo_id": str(uuid.uuid4()), "sha256": hashlib.sha256(TINY_PNG).hexdigest()}
    payload.update(target or {})
    return {"key": key, "kind": "photo", "seq": 1, "captured_at": "2026-03-15T15:40:00Z",
            "capture_token": token, "location": FIX, "payload": payload}


def test_a_photo_the_server_cannot_accept_goes_back_and_stores_nothing(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = _job(dana, brazos)  # assigned, NOT accepted
        task = work_models.WorkOrderTask.objects.filter(work_order_id=oid, photo_required=True).first()
        item = _photo(_token(tech), target={"task_id": str(task.id)})
        out = sync.sync_batch(tech, oid, {"items": [item]})
        answer = out["items"][0]
        pid = item["payload"]["photo_id"]

        assert answer["result"] == "refused" and answer["ack"] is False
        assert answer["detail"]["reason"] == "accept_the_job_first"
        assert out["acknowledged"] == []
        assert "upload_url" not in answer["detail"]
        assert not WorkSyncReceipt.objects.filter(work_order_id=oid, key=item["key"]).exists()
        assert not WorkPhotoLink.objects.filter(photo_id=pid).exists()


def test_the_fixed_photo_resent_under_the_same_key_gets_its_link_and_lands(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = _job(dana, brazos)
        task = work_models.WorkOrderTask.objects.filter(work_order_id=oid, photo_required=True).first()
        item = _photo(_token(tech), target={"task_id": str(task.id)})
        sync.sync_batch(tech, oid, {"items": [item]})
        mobile.accept_job(tech, oid)  # the technician fixes it
        out = sync.sync_batch(tech, oid, {"items": [item]})
        answer = out["items"][0]
        pid = item["payload"]["photo_id"]

        assert answer["result"] == "accepted", answer
        assert answer["detail"]["upload_url"].endswith(f"/work/mobile/photos/{pid}")
        photo_links.receive_bytes(tech, pid, TINY_PNG, "image/png")
        link = WorkPhotoLink.objects.get(photo_id=pid)
        photo_links.run_photo_job({"payload": {"link_id": str(link.id)}})
        link.refresh_from_db()
        assert link.state == WorkPhotoLink.STATE_LANDED
        assert link.required is True
        assert WorkPhotoLink.objects.filter(work_order_id=oid).count() == 1


def test_an_accepted_photo_is_unchanged(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech = _ready(dana, brazos)
        task = work_models.WorkOrderTask.objects.filter(work_order_id=oid, photo_required=True).first()
        item = _photo(_token(tech), target={"task_id": str(task.id)})
        out = sync.sync_batch(tech, oid, {"items": [item]})
        link = WorkPhotoLink.objects.get(photo_id=item["payload"]["photo_id"])

    assert out["items"][0]["result"] == "accepted"
    assert link.required is True
