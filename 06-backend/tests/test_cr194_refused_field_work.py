# ── Trace ──────────────────────────────────────────────
# Change:   CR-194-BRC10 — refused field work kept on BOTH the phone and the
#           server (PO 2026-10-26, *"store on both"*)
# Rules:    BR-WRK-063 (as amended 2026-10-26) · BR-WRK-071 · BR-WRK-042 ·
#           BR-WRK-059 · CLAUDE.md hard rules 1, 6, 7
# Tests:    this file (SQLite) · tests/test_cr194_refused_field_work_pg.py
#           (the copy's own savepoint and RLS, on PostgreSQL)
# ───────────────────────────────────────────────────────
"""The office's copy of a refused field item.

The worked example the PO was shown: D. Ortiz's three readings on a job the
dispatcher had given to M. Chen while Ortiz was offline are refused back to
Ortiz's phone AND listed for the office, which can mark them reviewed or apply
them to the job.
"""

from __future__ import annotations

import hashlib
import uuid

import pytest
from django.test import Client

from apps.work import dispatch, evidence, mobile, refused_items, sync
from apps.work import connection_models as work_tables
from apps.work import models as work_models
from apps.work.refused_models import WorkRefusedItem
from apps.work.sync_models import WorkSyncReceipt
from core import errors
from tests.test_cr187_sync_volume import as_field, read_route, reading_items, seed_reference, technician
from tests.test_us_idn_helpers import JSON, SC, api_path, idn  # noqa: F401 — fixture used by name
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

from tests.test_us_wrk_047_049_evidence import TINY_PNG  # noqa: E402


def _token(tech):
    return mobile.issue_capture_token(as_field(tech))["capture_token"]


def _stamped(items, token):
    return [{**item, "capture_token": token} for item in items]


def _reassigned_job(dana, brazos, *, readings=3):
    """WO given to D. Ortiz, accepted on his phone, then given to M. Chen by
    the dispatcher while Ortiz was offline."""
    seed_reference()
    ortiz = technician(brazos)
    chen = technician(brazos, "m-chen@brazos.test", "M. Chen")
    oid, rows = read_route(dana, brazos, ortiz, readings=readings)
    mobile.accept_job(as_field(ortiz), oid)
    token = _token(ortiz)
    dispatch.record_act(dana, oid, {"act": "assign", "technician_id": str(chen.id), "reason": "Ortiz is off sick"}, push=False)
    return oid, rows, ortiz, chen, token


# ══════════════════════════════════════════════════════════════════════════
# 1 · The worked example — refused, copied, never a receipt
# ══════════════════════════════════════════════════════════════════════════
def test_ortiz_three_readings_on_a_reassigned_job_are_refused_AND_kept_for_the_office(brazos, dana):
    with tenant_ctx(brazos):
        oid, rows, ortiz, _chen, token = _reassigned_job(dana, brazos)
        items = _stamped(reading_items(oid, rows), token)
        out = sync.sync_batch(as_field(ortiz), oid, {"items": items})
        copies = list(WorkRefusedItem.objects.filter(work_order_id=oid).order_by("key"))
        receipts = WorkSyncReceipt.objects.filter(work_order_id=oid).count()
        order_no = work_tables.WorkOrder.objects.get(pk=oid).order_no

    # Still refused back to the phone, NOT acknowledged (2026-10-21 stands)…
    assert [i["result"] for i in out["items"]] == ["refused"] * 3
    assert out["acknowledged"] == []
    assert {i["detail"]["reason"] for i in out["items"]} == {"not_your_job"}
    # …and the phone is told the office holds a copy.
    assert all(i["detail"]["kept_for_office"] is True for i in out["items"])
    # NEVER a receipt — the key is not spent.
    assert receipts == 0
    assert len(copies) == 3
    first = copies[0]
    assert first.status == "open" and first.door == "job" and first.kind == "reading"
    assert first.captor_technician_id == ortiz.id, "the CAPTOR, from the token — never the new assignee"
    assert first.message_key == "work.mobile.not_your_job" and first.reason_code == "not_your_job"
    assert first.payload["unit"] == "kWh" and first.payload["value"] == "40001"
    assert "capture_token" not in first.payload, "a credential is never stored"
    assert first.refusal_count == 1 and first.captured_at is not None
    assert order_no


def test_a_refused_item_with_a_copy_still_posts_ONCE_when_fixed_and_the_copy_reads_applied_later(brazos, dana):
    """The never-accepted case: refused (accept the job first), copied, no
    receipt; the technician accepts and resends the SAME key → accepted once,
    and the copy closes as `applied_later`. A third send is a duplicate."""
    from apps.work import checklist

    with tenant_ctx(brazos):
        seed_reference()
        ortiz = technician(brazos)
        oid, rows = read_route(dana, brazos, ortiz, readings=1)
        item = _stamped(reading_items(oid, rows), _token(ortiz))[0]
        out = sync.sync_batch(as_field(ortiz), oid, {"items": [item]})
        kept = WorkRefusedItem.objects.get(key=item["key"])
        assert kept.status == "open" and kept.reason_code == "accept_the_job_first"
        assert not WorkSyncReceipt.objects.filter(work_order_id=oid, key=item["key"]).exists()

        mobile.accept_job(as_field(ortiz), oid)
        for row in work_models.WorkOrderSafety.objects.filter(work_order_id=oid):
            checklist.tick_safety(as_field(ortiz), oid, row.id)
        again = sync.sync_batch(as_field(ortiz), oid, {"items": [item]})
        third = sync.sync_batch(as_field(ortiz), oid, {"items": [item]})
        kept.refresh_from_db()
        receipts = WorkSyncReceipt.objects.filter(work_order_id=oid, key=item["key"]).count()

    assert out["items"][0]["detail"]["kept_for_office"] is True
    assert again["items"][0]["result"] == "accepted", again["items"][0]
    assert third["items"][0]["result"] == "duplicate"
    assert receipts == 1
    assert kept.status == "applied_later" and kept.applied_at is not None


def test_a_resend_refused_again_updates_ONE_copy_and_a_reviewed_copy_stays_reviewed(brazos, dana):
    with tenant_ctx(brazos):
        oid, rows, ortiz, _chen, token = _reassigned_job(dana, brazos, readings=1)
        items = _stamped(reading_items(oid, rows), token)
        sync.sync_batch(as_field(ortiz), oid, {"items": items})
        row = WorkRefusedItem.objects.get(work_order_id=oid)
        refused_items.mark_reviewed(dana, row.id, {"note": "Chen re-reads it Monday"})
        sync.sync_batch(as_field(ortiz), oid, {"items": items})
        copies = list(WorkRefusedItem.objects.filter(work_order_id=oid))

    assert len(copies) == 1
    assert copies[0].refusal_count == 2
    assert copies[0].status == "reviewed" and copies[0].note == "Chen re-reads it Monday"


def test_items_with_no_captor_on_a_job_no_longer_the_senders_are_kept_too(brazos, dana):
    """The batch across jobs: a group without capture tokens on a job of this
    utility that is not the sender's is refused whole (404) — and copied."""
    with tenant_ctx(brazos):
        seed_reference()
        ortiz = technician(brazos)
        patel = technician(brazos, "r-patel@brazos.test", "R. Patel")
        oid, rows = read_route(dana, brazos, patel, readings=2)
        out = sync.sync_across_jobs(as_field(ortiz), {"items": reading_items(oid, rows, with_order=True)})
        copies = WorkRefusedItem.objects.filter(work_order_id=oid)
        captors = set(copies.values_list("captor_technician_id", flat=True))

    assert [i["result"] for i in out["items"]] == ["refused", "refused"]
    assert all(i["detail"].get("kept_for_office") is True for i in out["items"])
    assert copies.count() == 2 and captors == {ortiz.id}


def test_an_item_for_another_utilitys_job_keeps_nothing_here(brazos, lonestar, dana, erin):
    """A swapped phone: the job is Brazos's, the sender is Lone Star's. Not
    found there, and nothing is kept there — the office of Lone Star has no
    job to hang it on, and Brazos's data never lands in Lone Star's table."""
    with tenant_ctx(brazos):
        seed_reference()
        ortiz = technician(brazos)
        oid, rows = read_route(dana, brazos, ortiz, readings=1)
    with tenant_ctx(lonestar):
        theirs = technician(lonestar, "x@lonestar.test", "X. Other")
        out = sync.sync_across_jobs(as_field(theirs), {"items": reading_items(oid, rows, with_order=True)})
        kept = WorkRefusedItem.objects.count()
    assert out["items"][0]["result"] == "refused"
    assert "kept_for_office" not in (out["items"][0].get("detail") or {})
    assert kept == 0


# ══════════════════════════════════════════════════════════════════════════
# 2 · Photographs refused with their item are kept as evidence
# ══════════════════════════════════════════════════════════════════════════
def test_photos_refused_with_a_reading_are_kept_delivered_bytes_linked_and_never_deleted(brazos, dana):
    with tenant_ctx(brazos):
        seed_reference()
        ortiz = technician(brazos)
        chen = technician(brazos, "m-chen@brazos.test", "M. Chen")
        oid, rows = read_route(dana, brazos, ortiz, readings=1)
        mobile.accept_job(as_field(ortiz), oid)
        token = _token(ortiz)
        reading = rows[0]
        # Ortiz's dial photo reached the server by #77 BEFORE the reassignment.
        delivered = evidence.record_attachment(
            as_field(ortiz), oid, {"idempotency_key": "dial-1", "reading_id": str(reading.id)}, TINY_PNG
        )
        dispatch.record_act(dana, oid, {"act": "assign", "technician_id": str(chen.id), "reason": "Ortiz is off sick"}, push=False)
        reading_item = _stamped(reading_items(oid, rows), token)[0]
        photo_id = str(uuid.uuid4())
        items = [
            reading_item,
            {"key": "ph-1", "kind": "photo", "seq": 2, "captured_at": "2026-10-21T08:02:00Z",
             "capture_token": token,
             "payload": {"photo_id": photo_id, "sha256": hashlib.sha256(TINY_PNG).hexdigest(),
                         "reading_id": str(reading.id)}},
            {"key": "att-1", "kind": "attachment", "seq": 3, "captured_at": "2026-10-21T08:02:00Z",
             "capture_token": token, "payload": {"idempotency_key": "dial-1", "reading_id": str(reading.id)}},
        ]
        out = sync.sync_batch(as_field(ortiz), oid, {"items": items})
        copy = WorkRefusedItem.objects.get(key=reading_item["key"])
        detail = refused_items.office_detail(copy.id)
        still_there = work_models.WorkOrderAttachment.objects.filter(pk=delivered["id"]).exists()

    assert [i["result"] for i in out["items"]] == ["refused"] * 3
    assert still_there, "delivered bytes of a refused item are never deleted"
    states = sorted(p["state"] for p in detail["photos"])
    assert states == ["on_phone", "uploaded"], detail["photos"]
    uploaded = next(p for p in detail["photos"] if p["state"] == "uploaded")
    assert uploaded["attachment_id"] == str(delivered["id"])
    assert detail["work"]["reading"]["value"] == "40001" and detail["work"]["reading"]["unit"] == "kWh"
    assert detail["work"]["reading"]["prompt"] == "Meter 0001"


# ══════════════════════════════════════════════════════════════════════════
# 3 · The office: list, detail, Mark reviewed, Apply to the job
# ══════════════════════════════════════════════════════════════════════════
def test_the_office_list_filters_searches_and_counts(brazos, dana):
    with tenant_ctx(brazos):
        oid, rows, ortiz, _chen, token = _reassigned_job(dana, brazos)
        sync.sync_batch(as_field(ortiz), oid, {"items": _stamped(reading_items(oid, rows), token)})
        order_no = work_tables.WorkOrder.objects.get(pk=oid).order_no
        page = refused_items.office_page(status="open")
        by_job = refused_items.office_page(status="all", q=order_no[-4:])
        nobody = refused_items.office_page(status="all", q="ZZ-NOPE")
        by_tech = refused_items.office_page(status="all", technician=str(ortiz.id))
        by_reason = refused_items.office_page(status="all", reason="job_cancelled")
        by_kind = refused_items.office_page(status="all", kind="reading")
        with pytest.raises(errors.ValidationError):
            refused_items.office_page(status="nonsense")

    assert page["total"] == 3 and page["counts"]["open"] == 3
    row = page["rows"][0]
    assert row["technician"] == "D. Ortiz" and row["work_order"]["order_no"] == order_no
    assert row["kind"] == "reading" and row["reason"] == "not_your_job" and row["status"] == "open"
    assert by_job["total"] == 3 and nobody["total"] == 0
    assert by_tech["total"] == 3 and by_reason["total"] == 0 and by_kind["total"] == 3
    assert page["facets"]["technicians"] == [{"id": str(ortiz.id), "name": "D. Ortiz"}]
    assert page["facets"]["reasons"] == [{"reason": "not_your_job", "message_key": "work.mobile.not_your_job"}]


def test_mark_reviewed_records_who_and_the_note_and_is_audited(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        oid, rows, ortiz, _chen, token = _reassigned_job(dana, brazos, readings=1)
        sync.sync_batch(as_field(ortiz), oid, {"items": _stamped(reading_items(oid, rows), token)})
        row = WorkRefusedItem.objects.get(work_order_id=oid)
        out = refused_items.mark_reviewed(dana, row.id, {"note": "Called Ortiz"})
        row.refresh_from_db()

    assert out["status"] == "reviewed" and out["note"] == "Called Ortiz"
    assert row.reviewed_by_id == dana.id and row.reviewed_at is not None
    assert any(r["action"] == "work.refused_item.reviewed" for r in audit_rows)


def test_apply_to_the_job_runs_the_normal_path_and_the_phones_resend_is_then_a_duplicate(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        oid, rows, ortiz, _chen, token = _reassigned_job(dana, brazos, readings=3)
        items = _stamped(reading_items(oid, rows), token)
        sync.sync_batch(as_field(ortiz), oid, {"items": items})
        copy = WorkRefusedItem.objects.get(key=items[0]["key"])
        out = refused_items.apply_to_job(dana, copy.id)
        copy.refresh_from_db()
        reading = work_models.WorkOrderReading.objects.get(pk=rows[0].id)
        receipt = WorkSyncReceipt.objects.get(work_order_id=oid, key=items[0]["key"])
        resend = sync.sync_batch(as_field(ortiz), oid, {"items": [items[0]]})
        with pytest.raises(errors.BizError) as twice:
            refused_items.apply_to_job(dana, copy.id)

    assert out["status"] == "applied" and copy.applied_by_id == dana.id
    assert str(reading.value) in ("40001", "40001.0000")
    assert receipt.captured_by_technician_id == ortiz.id, "the captor stays the technician"
    assert resend["items"][0]["result"] == "duplicate" and items[0]["key"] in resend["acknowledged"]
    assert twice.value.message_key == "work.refused.already_applied"
    assert any(r["action"] == "work.refused_item.applied" for r in audit_rows)


def test_apply_is_refused_with_the_reason_when_the_job_is_cancelled_and_nothing_moves(brazos, dana):
    with tenant_ctx(brazos):
        oid, rows, ortiz, _chen, token = _reassigned_job(dana, brazos, readings=1)
        items = _stamped(reading_items(oid, rows), token)
        sync.sync_batch(as_field(ortiz), oid, {"items": items})
        copy = WorkRefusedItem.objects.get(work_order_id=oid)
        work_tables.WorkOrder.objects.filter(pk=oid).update(dispatch_state="cancelled")
        with pytest.raises(errors.BizError) as refused:
            refused_items.apply_to_job(dana, copy.id)
        copy.refresh_from_db()
        receipts = WorkSyncReceipt.objects.filter(work_order_id=oid).count()

    assert refused.value.message_key == "work.sync.job_cancelled"
    assert copy.status == "open" and receipts == 0


def test_apply_is_refused_when_the_service_refuses_now_and_the_key_stays_unspent(brazos, dana):
    with tenant_ctx(brazos):
        oid, rows, ortiz, _chen, token = _reassigned_job(dana, brazos, readings=1)
        item = _stamped(reading_items(oid, rows), token)[0]
        item["payload"] = {**item["payload"], "unit": "gal"}  # the job measures kWh
        sync.sync_batch(as_field(ortiz), oid, {"items": [item]})
        copy = WorkRefusedItem.objects.get(work_order_id=oid)
        with pytest.raises(errors.BizError) as refused:
            refused_items.apply_to_job(dana, copy.id)
        copy.refresh_from_db()
        spent = WorkSyncReceipt.objects.filter(work_order_id=oid, key=item["key"]).exists()

    assert refused.value.message_key and refused.value.message_key != "work.refused.not_applied"
    assert copy.status == "open" and spent is False


def test_a_route_reads_copy_can_be_reviewed_but_never_applied_from_here(brazos, dana):
    with tenant_ctx(brazos):
        kept = refused_items.keep(
            door="reads",
            item={"key": "rr-1", "kind": "reading", "meter_no": "MTR-0471", "value": "52410",
                  "unit": "gal", "capture_token": "secret"},
            refusal={"result": "refused", "reason": "unit_missing",
                     "detail": {"reason": "unit_missing", "message_key": "work.mobile.reads.unit_missing"}},
            courier=dana,
        )
        copy = WorkRefusedItem.objects.get(key="rr-1")
        detail = refused_items.office_detail(copy.id)
        with pytest.raises(errors.BizError) as refused:
            refused_items.apply_to_job(dana, copy.id)
        reviewed = refused_items.mark_reviewed(dana, copy.id, {})

    assert kept is True and "capture_token" not in copy.payload
    assert detail["can_apply"] is False and detail["work"]["reading"]["meter_no"] == "MTR-0471"
    assert refused.value.message_key == "work.refused.apply_job_only"
    assert reviewed["status"] == "reviewed"


# ══════════════════════════════════════════════════════════════════════════
# 4 · The reads door keeps its refusals too
# ══════════════════════════════════════════════════════════════════════════
def test_the_reads_door_keeps_a_copy_of_what_it_refuses(brazos, dana):
    from apps.metering import field_reads

    with tenant_ctx(brazos):
        out = field_reads.sync_reads(
            dana, {"items": [{"key": "rd-unknown-1", "kind": "teleport", "captured_at": "2026-10-21T08:00:00Z"}]}
        )
        copy = WorkRefusedItem.objects.filter(key="rd-unknown-1").first()

    answer = out["items"][0]
    assert answer["result"] == "refused"
    assert answer["detail"]["kept_for_office"] is True
    assert copy is not None and copy.door == "reads" and copy.work_order_id is None
    assert copy.reason_code == "unknown_kind"


# ══════════════════════════════════════════════════════════════════════════
# 5 · Another utility sees nothing
# ══════════════════════════════════════════════════════════════════════════
def test_another_utility_cannot_see_or_act_on_the_copy(brazos, lonestar, dana, erin):
    with tenant_ctx(brazos):
        oid, rows, ortiz, _chen, token = _reassigned_job(dana, brazos, readings=1)
        sync.sync_batch(as_field(ortiz), oid, {"items": _stamped(reading_items(oid, rows), token)})
        copy_id = WorkRefusedItem.objects.get(work_order_id=oid).id
    with tenant_ctx(lonestar):
        page = refused_items.office_page(status="all")
        with pytest.raises(errors.NotFoundError):
            refused_items.office_detail(copy_id)
        with pytest.raises(errors.NotFoundError):
            refused_items.mark_reviewed(erin, copy_id, {})
        with pytest.raises(errors.NotFoundError):
            refused_items.apply_to_job(erin, copy_id)
    assert page["total"] == 0 and page["facets"]["technicians"] == []


# ══════════════════════════════════════════════════════════════════════════
# 6 · Through the stack — the four routes
# ══════════════════════════════════════════════════════════════════════════
CLERK = ("refused.cr194@silvercreek.example", "J. Rivera", "Prairie2026grass")


def test_the_four_office_routes_through_the_stack(idn):
    from tests.isolation_helpers import writing_as_tenant

    idn.make_user(idn.silvercreek, CLERK[0], CLERK[1], password=CLERK[2])
    with writing_as_tenant(idn.silvercreek):
        from core import tenancy as core_tenancy

        with core_tenancy.tenant_context(idn.silvercreek.id) if hasattr(core_tenancy, "tenant_context") else _noop():
            refused_items.keep(
                door="reads",
                item={"key": "http-1", "kind": "reading", "meter_no": "MTR-1", "value": "1", "unit": "gal"},
                refusal={"detail": {"reason": "unit_missing", "message_key": "work.mobile.reads.unit_missing"}},
            )
    client = Client()
    signed = client.post(
        api_path("/auth/session", SC), data={"email": CLERK[0], "password": CLERK[2]}, content_type=JSON
    )
    assert signed.status_code == 201, signed.content

    listed = client.get(api_path("/work/refused-items?status=all", SC))
    assert listed.status_code == 200, listed.content
    body = listed.json()
    assert body["count"] == 1 and body["counts"]["open"] == 1
    item_id = body["results"][0]["id"]

    detail = client.get(api_path(f"/work/refused-items/{item_id}", SC))
    assert detail.status_code == 200 and detail.json()["can_apply"] is False

    applied = client.post(api_path(f"/work/refused-items/{item_id}/apply", SC), data={}, content_type=JSON)
    assert applied.status_code == 409 or applied.status_code == 422, applied.content
    assert applied.json().get("message_key") == "work.refused.apply_job_only"

    reviewed = client.post(
        api_path(f"/work/refused-items/{item_id}/review", SC), data={"note": "seen"}, content_type=JSON
    )
    assert reviewed.status_code == 200 and reviewed.json()["status"] == "reviewed"


class _noop:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False
