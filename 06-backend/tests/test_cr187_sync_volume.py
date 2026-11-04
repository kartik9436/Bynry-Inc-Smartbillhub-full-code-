# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 lane S-SYNC — T-30 (batched sync at volume) and the
#           batch across jobs (`POST /work/mobile/sync`)
# Rules:    R45 (fifty to a request, capture order within an order) · R46 (the
#           key is minted at capture) · R47 (per item, a savepoint each) · R49
#           (a send always resumes) · BR-WRK-042 · CLAUDE.md hard rule 1
#           (tenant scoping) · hard rule 6 (idempotency)
# ⚠ WHAT THIS FILE CANNOT PROVE: the SAVEPOINT. SQLite has no aborted-
#   transaction state; `tests/test_cr187_sync_volume_pg.py` is where it is
#   proved, on PostgreSQL, and was shown red without it.
# ───────────────────────────────────────────────────────
"""A read route's day — 1,000 readings — sent the way Data.txt §4 sends it:
twenty batches of fifty, in capture order, two of them retried mid-way.
Nothing is lost and nothing is doubled.

The retry shapes are the two a weak connection actually produces:

* **a batch that died halfway** — the server applied the first 23 and the
  answer never reached the phone, so the phone sends all 50 again: 23
  *duplicate*, 27 *accepted* (R49's own figure);
* **a batch whose answer was lost** — all 50 applied, all 50 re-sent: 50
  *duplicate*, and not one row anywhere moves.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.metering import connections as w6
from apps.work import dispatch, sync
from apps.work import models as work_models
from apps.work import services as work_services
from apps.work.sync_models import WorkSyncReceipt

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import make_premises
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

READINGS = 1000
BATCH = 50
#: (batch number, items the server took before the line dropped). Batch 7 died
#: after 23; batch 13 was applied whole and its answer lost.
RETRIED = {7: 23, 13: BATCH}


# ── the route ─────────────────────────────────────────────────────────────
def seed_reference():
    for code in ("work_priorities", "work_order_types", "work_hold_reasons"):
        work_services.seed_reference_list(code, [], "test")


def technician(tenant, email="d-ortiz@brazos.test", name="D. Ortiz"):
    from apps.identity import models as identity_models

    user = identity_models.User.objects.create(tenant_id=tenant.id, email=email, full_name=name)
    return work_models.Technician.objects.create(tenant_id=tenant.id, user=user)


def as_field(tech):
    return SimpleNamespace(id=tech.user_id, role="field_technician")


def read_route(actor, tenant, tech, *, readings, address="500 Main St"):
    """One job holding `readings` meter readings, given to `tech` through the
    dispatcher's own door (so its history is real)."""
    premises = make_premises(actor, address_line=address, services_available=["electric"])
    oid = w6.create_work_order(
        actor, None, {"type": "Meter read", "service": "electric", "premises_id": premises["id"]}
    )["id"]
    dispatch.record_act(actor, oid, {"act": "assign", "technician_id": str(tech.id)}, push=False)
    work_models.WorkOrderReading.objects.bulk_create(
        work_models.WorkOrderReading(
            tenant_id=tenant.id, work_order_id=oid, seq=10_000 + n,
            prompt=f"Meter {n:04d}", unit_of_measure="kWh", required=False,
        )
        for n in range(1, readings + 1)
    )
    rows = list(
        work_models.WorkOrderReading.objects.filter(work_order_id=oid, seq__gt=10_000).order_by("seq")
    )
    return oid, rows


def reading_items(oid, rows, *, route="r7", with_order=False):
    """The phone's outbox for these readings, in capture order — each key
    minted at capture (R46), each value distinct so a doubled or crossed
    apply would show."""
    items = []
    for n, row in enumerate(rows, start=1):
        item = {
            "key": f"{route}-2026-10-21-{n:04d}",
            "kind": "reading",
            "seq": n,
            "captured_at": f"2026-10-21T{8 + n // 120:02d}:{n % 60:02d}:00Z",
            "payload": {"reading_id": str(row.id), "value": str(40_000 + n), "unit": "kWh"},
        }
        if with_order:
            item["work_order_id"] = str(oid)
        items.append(item)
    return items


def batches(items, size=BATCH):
    return [items[i : i + size] for i in range(0, len(items), size)]


def send_the_day(send, items):
    """Twenty batches, two retried as `RETRIED` says. Returns the tallies."""
    totals = {"accepted": 0, "duplicate": 0, "refused": 0, "held_for_review": 0, "requests": 0}
    for number, batch in enumerate(batches(items), start=1):
        if number in RETRIED:
            # The attempt whose answer never arrived.
            lost = send(batch[: RETRIED[number]])
            totals["requests"] += 1
            for key in ("accepted", "duplicate", "refused", "held_for_review"):
                totals[key] += lost[key]
        out = send(batch)
        totals["requests"] += 1
        for key in ("accepted", "duplicate", "refused", "held_for_review"):
            totals[key] += out[key]
        assert len(out["items"]) == len(batch)
        assert [i["key"] for i in out["items"]] == [i["key"] for i in batch], "answers out of order"
    return totals


def _captures(audit_rows, rows):
    """Capture audit rows (`work.reading.captured`) written for these readings,
    read from the suite's audit sink (`tests.test_us_met_helpers.audit_rows`)."""
    ids = {str(r.id) for r in rows}
    return sum(
        1 for row in audit_rows
        if row.get("action") == "work.reading.captured" and str(row.get("entity_id")) in ids
    )


def assert_landed_once(oids_and_rows, audit_rows):
    """Every reading carries its own value, once: one receipt per key and one
    capture audit row per reading — a re-applied item would write a second."""
    for oid, rows in oids_and_rows:
        assert WorkSyncReceipt.objects.filter(work_order_id=oid, kind="reading").count() == len(rows)
        values = dict(
            work_models.WorkOrderReading.objects.filter(work_order_id=oid, seq__gt=10_000)
            .values_list("seq", "value")
        )
        assert len(values) == len(rows)
        assert all(v is not None for v in values.values()), "a reading was lost"
        assert sorted(int(v) for v in values.values()) == [40_000 + n for n in range(1, len(rows) + 1)]
        audits = _captures(audit_rows, rows)
        assert audits == len(rows), f"{audits} capture audit rows for {len(rows)} readings"


# ══════════════════════════════════════════════════════════════════════════
# T-30 · 1,000 readings, 20 batches of 50, through the per-job route (#90)
# ══════════════════════════════════════════════════════════════════════════
def test_1000_readings_in_20_batches_with_two_retried_mid_way_land_once(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        seed_reference()
        tech = technician(brazos)
        oid, rows = read_route(dana, brazos, tech, readings=READINGS)
        items = reading_items(oid, rows)
        totals = send_the_day(lambda b: sync.sync_batch(as_field(tech), oid, {"items": b}), items)
        assert_landed_once([(oid, rows)], audit_rows)

    assert totals["requests"] == 22, totals
    assert totals["accepted"] == READINGS, totals
    assert totals["duplicate"] == RETRIED[7] + RETRIED[13], totals
    assert totals["refused"] == 0 and totals["held_for_review"] == 0, totals


# ══════════════════════════════════════════════════════════════════════════
# T-30 · the batch ACROSS jobs (`POST /work/mobile/sync`)
# ══════════════════════════════════════════════════════════════════════════
def _four_jobs(actor, tenant, tech, per_job=250):
    jobs = []
    for n in range(4):
        oid, rows = read_route(actor, tenant, tech, readings=per_job, address=f"{500 + n} Main St")
        jobs.append((oid, rows))
    return jobs


def _interleave(jobs):
    """Round-robin the four outboxes — capture order kept WITHIN each job,
    which is all R45 asks — so every batch of fifty spans all four jobs."""
    queues = [reading_items(oid, rows, route=f"r{i}", with_order=True) for i, (oid, rows) in enumerate(jobs)]
    out = []
    for group in zip(*queues):
        out.extend(group)
    return out


def test_1000_readings_across_four_jobs_in_20_mixed_batches_land_once(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        seed_reference()
        tech = technician(brazos)
        jobs = _four_jobs(dana, brazos, tech)
        items = _interleave(jobs)
        assert len(items) == READINGS
        assert len({i["work_order_id"] for i in batches(items)[0]}) == 4, "a batch should span jobs"
        totals = send_the_day(lambda b: sync.sync_across_jobs(as_field(tech), {"items": b}), items)
        assert_landed_once(jobs, audit_rows)

    assert totals["accepted"] == READINGS, totals
    assert totals["duplicate"] == RETRIED[7] + RETRIED[13], totals
    assert totals["refused"] == 0, totals


def test_the_answer_carries_each_items_job_and_acknowledges_by_job_and_key(brazos, dana):
    with tenant_ctx(brazos):
        seed_reference()
        tech = technician(brazos)
        jobs = _four_jobs(dana, brazos, tech, per_job=3)
        items = _interleave(jobs)
        out = sync.sync_across_jobs(as_field(tech), {"items": items})

    assert [(i["work_order_id"], i["key"]) for i in out["items"]] == [
        (i["work_order_id"], i["key"]) for i in items
    ]
    assert out["acknowledged"] == [{"work_order_id": i["work_order_id"], "key": i["key"]} for i in items]
    assert sorted(j["accepted"] for j in out["jobs"]) == [3, 3, 3, 3]


def test_a_job_that_cannot_be_reached_refuses_its_own_items_and_costs_no_other_job(
    brazos, dana, lonestar, erin
):
    """A swapped phone (`J65` step 13): one job of the batch is another
    tenant's. Its items are refused and NOT acknowledged — they stay in the
    outbox — and the other job's items commit (hard rule 1: the foreign id is
    a 404 like any other, never a peek)."""
    with tenant_ctx(lonestar):
        seed_reference()
        theirs_tech = technician(lonestar, "j-okafor@lsr.test", "J. Okafor")
        premises = make_premises(erin, address_line="1 Ridge Rd", services_available=["water"])
        theirs = w6.create_work_order(
            erin, None, {"type": "Meter read", "service": "water", "premises_id": premises["id"]}
        )["id"]
        dispatch.record_act(erin, theirs, {"act": "assign", "technician_id": str(theirs_tech.id)}, push=False)
    with tenant_ctx(brazos):
        seed_reference()
        tech = technician(brazos)
        oid, rows = read_route(dana, brazos, tech, readings=4)
        mine = reading_items(oid, rows, with_order=True)
        foreign = [{**mine[0], "key": "swapped-1", "work_order_id": str(theirs)},
                   {**mine[1], "key": "swapped-2", "work_order_id": "not-a-uuid"}]
        out = sync.sync_across_jobs(as_field(tech), {"items": [mine[0], foreign[0], mine[1], foreign[1],
                                                               mine[2], mine[3]]})
        landed = WorkSyncReceipt.objects.filter(work_order_id=oid).count()
    with tenant_ctx(lonestar):
        leaked = WorkSyncReceipt.objects.filter(work_order_id=theirs).count()

    results = [(i["key"], i["result"]) for i in out["items"]]
    assert results == [
        (mine[0]["key"], "accepted"), ("swapped-1", "refused"), (mine[1]["key"], "accepted"),
        ("swapped-2", "refused"), (mine[2]["key"], "accepted"), (mine[3]["key"], "accepted"),
    ], results
    assert {a["key"] for a in out["acknowledged"]} == {m["key"] for m in mine}
    assert out["items"][1]["detail"] == {"message": "not found", "status": 404}
    assert landed == 4 and leaked == 0


def test_another_technicians_job_in_the_batch_is_refused_not_applied(brazos, dana):
    """The per-job route's own gate, per job: a group without capture tokens
    must be the signed-in technician's own job (DEF-WRK-9593)."""
    with tenant_ctx(brazos):
        seed_reference()
        ortiz = technician(brazos)
        patel = technician(brazos, "r-patel@brazos.test", "R. Patel")
        oid, rows = read_route(dana, brazos, patel, readings=2)
        out = sync.sync_across_jobs(as_field(ortiz), {"items": reading_items(oid, rows, with_order=True)})
        stored = WorkSyncReceipt.objects.filter(work_order_id=oid).count()

    assert [i["result"] for i in out["items"]] == ["refused", "refused"]
    assert out["acknowledged"] == [] and stored == 0


# ══════════════════════════════════════════════════════════════════════════
# Hard rule 6 · the same item twice is a duplicate receipt and one row
# ══════════════════════════════════════════════════════════════════════════
def test_the_same_item_twice_is_one_row_and_a_duplicate_receipt(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        seed_reference()
        tech = technician(brazos)
        oid, rows = read_route(dana, brazos, tech, readings=1)
        item = reading_items(oid, rows, with_order=True)[0]
        out = sync.sync_across_jobs(as_field(tech), {"items": [item, dict(item)]})
        again = sync.sync_across_jobs(as_field(tech), {"items": [dict(item)]})
        receipts = WorkSyncReceipt.objects.filter(work_order_id=oid, key=item["key"]).count()
        audits = _captures(audit_rows, rows)

    assert [i["result"] for i in out["items"]] == ["accepted", "duplicate"]
    assert [i["result"] for i in again["items"]] == ["duplicate"]
    # A duplicate is ACKNOWLEDGED — the phone may let it go (TECHNICIAN SYNC DESIGN (1)).
    assert len(out["acknowledged"]) == 2 and len(again["acknowledged"]) == 1
    assert receipts == 1 and audits == 1


def test_an_empty_or_oversized_request_is_refused_by_name(brazos, dana):
    from core import errors

    with tenant_ctx(brazos):
        tech_actor = SimpleNamespace(id=dana.id, role="field_technician")
        with pytest.raises(errors.ValidationError) as empty:
            sync.sync_across_jobs(tech_actor, {"items": []})
        with pytest.raises(errors.ValidationError) as huge:
            sync.sync_across_jobs(tech_actor, {"items": [{}] * (sync.MAX_ITEMS + 1)})
    assert empty.value.message_key == "work.sync.no_items"
    assert huge.value.message_key == "work.sync.too_many_items"
