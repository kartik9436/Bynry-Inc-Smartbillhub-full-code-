# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-044 TC-1/TC-2/TC-5/TC-6/TC-7 (offline capture, one sync) ·
#           US-WRK-045 TC-1/TC-5 (the close is `submit_field_result`) ·
#           US-WRK-046 TC-1/TC-2/TC-4/TC-7 (the reading that posts)
# Rules:    BR-WRK-042 · BR-WRK-041 · BR-WRK-037 · BR-WRK-003 · BR-WRK-015 ·
#           BR-MET-110 · hard rule 3
# ⚠ WHAT THIS FILE CANNOT PROVE: the SAVEPOINT. SQLite has no aborted-
#   transaction state, so `tests/test_us_wrk_044_sync_pg.py` is where law 14 is
#   actually checked, and a green here means nothing about it.
# ───────────────────────────────────────────────────────
"""CR-070 wave L — one sync, and the reading that becomes a meter read."""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.work import models as work_models
from apps.work import sync
from apps.work.sync_models import WorkSyncReceipt
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import field_actor  # CR-168 P1.34 — sync as the field
from tests.test_us_met_helpers import take_required_photos  # DEF-WRK-9625
from tests.test_us_met_helpers import make_asset, make_premises, tenant_ctx
from tests.test_us_wrk_032_copies import _published_template

pytestmark = pytest.mark.django_db


def _order_on_a_meter(actor, tenant, *, asset_no="E1P-33107"):
    """A job anchored on a METER, which is what `BR-WRK-003` needs.

    Wave H's `_raise` anchors on a premises, which is right for the copy tests
    and wrong here: a reading posts to the order's own meter, so a fixture
    without one exercises only the refusal.
    """
    tid = _published_template(actor, tenant)
    premises = make_premises(actor, address_line="221 Oak Ave", services_available=["electric"])
    asset = make_asset(actor, asset_no=asset_no)
    oid = w6.create_work_order(
        actor,
        None,
        {
            "premises_id": str(premises["id"]),
            "asset_id": str(asset["id"]),
            "type": "Meter exchange",
            "template_id": str(tid),
        },
    )["id"]
    # `DEF-WRK-9625` — the photographs travel #77 before the batch, as on the
    # phone; the close is refused while a required one is missing.
    take_required_photos(field_actor(oid, actor), oid)
    return oid


def _rows(oid):
    return {
        "safety": list(
            work_models.WorkOrderSafety.objects.filter(work_order_id=oid).order_by("seq")
        ),
        "tasks": list(work_models.WorkOrderTask.objects.filter(work_order_id=oid).order_by("seq")),
        "readings": list(
            work_models.WorkOrderReading.objects.filter(work_order_id=oid).order_by("seq")
        ),
    }


def _batch(oid, rows, *, prefix="ortiz-01-2026-03-15"):
    """D. Ortiz's queue for one job, in CAPTURE order: three safety ticks, seven
    task ticks, one reading, then the close — `J65` step 6's shape."""
    items = []
    n = 0

    def add(kind, payload, at):
        nonlocal n
        n += 1
        items.append(
            {"key": f"{prefix}-{n:03d}", "kind": kind, "seq": n, "captured_at": at, "payload": payload}
        )

    for row in rows["safety"]:
        add("safety_tick", {"safety_id": str(row.id)}, "2026-03-15T15:15:00Z")
    for row in rows["tasks"]:
        add("task_tick", {"task_id": str(row.id)}, "2026-03-15T15:30:00Z")
    add(
        "reading",
        {"reading_id": str(rows["readings"][0].id), "value": "1204", "unit": "kWh"},
        "2026-03-15T16:07:00Z",
    )
    add("close", {"outcome": "passed"}, "2026-03-15T16:07:00Z")
    return {"items": items}


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-044 · BR-WRK-042 — everything lands ONCE, and a re-sync adds nothing
# ══════════════════════════════════════════════════════════════════════════
def test_tc1_044_one_sync_applies_the_whole_day(brazos, dana):
    """TC-1 — every queued item is accepted once and answered individually."""
    with tenant_ctx(brazos):
        oid = _order_on_a_meter(dana, brazos)
        rows = _rows(oid)
        out = sync.sync_batch(field_actor(oid, dana), oid, _batch(oid, rows))

    assert out["accepted"] == len(out["items"]), out
    assert out["duplicate"] == 0 and out["refused"] == 0, out
    # ⚠ PER-ITEM RESULTS, NEVER A BOOLEAN (`07-endpoints.md` #90). A summary
    # that could not name WHICH item failed would make a half-applied batch
    # unfixable from the phone.
    assert {r["result"] for r in out["items"]} == {"accepted"}
    assert WorkSyncReceipt.objects.filter(work_order_id=oid).count() == len(out["items"])


def test_tc2_044_a_second_sync_of_the_same_queue_adds_nothing(brazos, dana):
    """TC-2 — **zero** new rows anywhere; every item answers *duplicate*.

    `WM-48`'s own worked figure, one job's worth: *a re-sync of the same jobs
    adds nothing*.
    """
    with tenant_ctx(brazos):
        oid = _order_on_a_meter(dana, brazos)
        batch = _batch(oid, _rows(oid))
        first = sync.sync_batch(field_actor(oid, dana), oid, batch)
        before = WorkSyncReceipt.objects.filter(work_order_id=oid).count()
        second = sync.sync_batch(field_actor(oid, dana), oid, batch)
        after = WorkSyncReceipt.objects.filter(work_order_id=oid).count()

    assert first["accepted"] == before
    assert second["duplicate"] == len(second["items"])
    assert second["accepted"] == 0
    assert after == before, "a re-sync wrote a receipt"


def test_tc5_044_the_server_does_not_re_sort_the_batch(brazos, dana):
    """TC-5 · `BR-WRK-037` — a close that arrives BEFORE its safety ticks is
    REFUSED, and the ticks after it still apply.

    ⚠ **THE TEMPTING "FIX" IS TO SORT SAFETY TICKS TO THE FRONT, AND IT WOULD
    DESTROY THE ONLY THING THIS PROVES.** The server re-derives the lock from
    `ticked_at` and never from the client's word; a server that helpfully
    re-ordered a tampered client's queue would report success over a job closed
    with its safety incomplete.
    """
    with tenant_ctx(brazos):
        oid = _order_on_a_meter(dana, brazos)
        rows = _rows(oid)
        good = _batch(oid, rows)["items"]
        close = good[-1]
        # The close first, then the safety ticks it is gated on.
        out = sync.sync_batch(field_actor(oid, dana), oid, {"items": [close, *good[:3]]})

    assert out["items"][0]["result"] == "refused", out["items"][0]
    assert [r["result"] for r in out["items"][1:]] == ["accepted"] * 3
    # And the refused close left NO receipt, so the phone may legitimately
    # re-queue the same key once the ticks have landed.
    assert not WorkSyncReceipt.objects.filter(work_order_id=oid, key=close["key"]).exists()


def test_tc6_044_an_item_for_another_tenants_order_is_404(brazos, lonestar, dana, erin):
    """TC-6 — a swapped phone. The job is not found, and nothing is applied."""
    from core import errors

    with tenant_ctx(brazos):
        oid = _order_on_a_meter(dana, brazos)
        rows = _rows(oid)
        batch = _batch(oid, rows)
    # ⚠ `NotFoundError` is its OWN class and NOT an `ApiError` subclass
    # (`core/errors.py`), which is a distinction a `pytest.raises(ApiError)`
    # here would have quietly got wrong — it would have failed for the right
    # reason with the wrong message.
    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            sync.sync_batch(erin, oid, batch)


def test_044_an_unknown_item_kind_is_refused_as_data_not_as_a_500(brazos, dana):
    """A kind the server does not recognise is REFUSED and NAMED — never
    accepted, and never a crash that loses the other nineteen items."""
    with tenant_ctx(brazos):
        oid = _order_on_a_meter(dana, brazos)
        rows = _rows(oid)
        items = _batch(oid, rows)["items"]
        # ⚠ **INSERTED, NOT SUBSTITUTED, AND THE FIRST DRAFT GOT THIS WRONG.**
        # Replacing item 1 — a safety tick — left the lock in place, so all
        # seven task ticks were refused too and the batch answered 3 accepted
        # rather than 11. The code was right and the test was measuring two
        # things at once. A case about an unknown KIND must change nothing else.
        items.insert(0, {
            "key": "ortiz-01-2026-03-15-999",
            "kind": "coffee_break",
            "seq": 0,
            "captured_at": "2026-03-15T15:14:00Z",
            "payload": {},
        })
        out = sync.sync_batch(field_actor(oid, dana), oid, {"items": items})

    # ⚠ AMENDED 2026-10-21 (PO: *"back to the technician"* — BR-WRK-063
    # superseded for field items): an unknown kind is REFUSED with its reason,
    # not acknowledged and not stored, so the phone keeps it. (2026-10-04 to
    # 2026-10-21 it was stored and answered `held_for_review`.)
    assert out["items"][0]["result"] == "refused"
    assert out["items"][0]["ack"] is False
    assert out["items"][0]["detail"]["reason"] == "unknown_item_kind"
    assert out["items"][0]["detail"]["message_key"] == "work.sync.unknown_item_kind"
    assert not WorkSyncReceipt.objects.filter(key="ortiz-01-2026-03-15-999").exists()
    assert "ortiz-01-2026-03-15-999" not in out["acknowledged"]
    assert out["accepted"] == len(items) - 1


def test_044_every_declared_kind_has_an_applier(brazos, dana):
    """The vocabulary and the behaviour cannot drift apart.

    ⚠ **AN EIGHTH KIND ADDED TO THE CONSTANT AND TO NOTHING ELSE WOULD DO
    NOTHING, SILENTLY** — which is `SignupWizard`'s eleventh service one module
    over: the row exists, the API serves it, `tsc` and every test pass, and the
    thing simply never happens.
    """
    from apps.work.sync_models import ITEM_KINDS

    assert set(ITEM_KINDS) == set(sync._APPLIERS) | {"close"}


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-045 · BR-WRK-041 / BR-MET-110 — the close ACTIVATES NOTHING
# ══════════════════════════════════════════════════════════════════════════
def test_tc1_045_the_close_completes_the_order_and_activates_nothing(brazos, dana):
    """TC-1 — `state = completed`, `accepted_by` NULL, **zero** meter reads.

    That NULL is the review queue (`BR-WRK-007`), and the zero is the whole of
    `BR-MET-110`: closing does not switch the supply on.
    """
    with tenant_ctx(brazos):
        oid = _order_on_a_meter(dana, brazos)
        sync.sync_batch(field_actor(oid, dana), oid, _batch(oid, _rows(oid)))
        order = work_tables.WorkOrder.objects.get(pk=oid)
        reads = metering_models.MeterRead.objects.filter(tenant_id=brazos.id).count()

    assert order.state == "completed"
    assert order.outcome == "passed"
    assert order.accepted_by_id is None
    assert reads == 0, "the close posted a meter read — BR-MET-110 says only acceptance does"


def test_tc1_045_completed_at_is_the_HANDSET_time_and_not_the_sync_time(brazos, dana):
    """⚠ **THE COLUMN THIS WHOLE WAVE TURNS ON.** The phone closed at 16:07 and
    reached the server at 17:40; `accept_field_result` dates every meter read
    from `completed_at`, so a wall-clock stamp here would move a whole offline
    day's readings into the wrong billing period, silently."""
    with tenant_ctx(brazos):
        oid = _order_on_a_meter(dana, brazos)
        sync.sync_batch(field_actor(oid, dana), oid, _batch(oid, _rows(oid)))
        order = work_tables.WorkOrder.objects.get(pk=oid)

    assert order.completed_at.isoformat().startswith("2026-03-15T16:07"), order.completed_at


def test_045_a_close_stamped_in_the_FUTURE_is_refused(brazos, dana):
    """A handset's clock is the handset's. A close dated tomorrow would date a
    meter read into a period nobody has billed yet."""
    with tenant_ctx(brazos):
        oid = _order_on_a_meter(dana, brazos)
        items = _batch(oid, _rows(oid))["items"]
        items[-1] = {**items[-1], "captured_at": "2099-01-01T00:00:00Z"}
        out = sync.sync_batch(field_actor(oid, dana), oid, {"items": items})

    # ⚠ AMENDED 2026-10-21 (PO: *"back to the technician"*): the close is not
    # APPLIED — the order stays open — and it goes BACK to the technician with
    # its reason, kept on the phone to fix the clock and resend.
    assert out["items"][-1]["result"] == "refused"
    assert out["items"][-1]["ack"] is False
    assert out["items"][-1]["detail"]["message_key"] == "metering.work_order_completed_at_future"
    assert out["items"][-1]["detail"]["reason"] == "work_order_completed_at_future"


# ══════════════════════════════════════════════════════════════════════════
# US-WRK-046 · BR-WRK-003 — the reading that becomes a meter read
# ══════════════════════════════════════════════════════════════════════════
def _accept(actor, oid):
    return w6.accept_field_result(actor, oid)


def test_tc1_046_the_read_lands_on_the_meter_dated_to_the_COMPLETION(brazos, dana):
    """TC-1 — the number D. Ortiz typed on **15 March** is on the meter's
    history dated **15 March**, though M. Torres accepted it on the 16th.

    `BR-TEN-043`: an event date, never a wall clock. This is the assertion the
    review-ledger row for `metering_seam.py` is written against.
    """
    with tenant_ctx(brazos):
        oid = _order_on_a_meter(dana, brazos)
        sync.sync_batch(field_actor(oid, dana), oid, _batch(oid, _rows(oid)))
        _accept(dana, oid)
        read = metering_models.MeterRead.objects.get(tenant_id=brazos.id)

    # ⚠ **THE DAY, NOT THE INSTANT.** `read_at` is a datetime, so a naive
    # `str(...) == "2026-03-15"` compares against `2026-03-15 00:00:00+00:00`
    # and fails over a correct value — which is what the first draft of this
    # line did. What the rule is about is the DATE (`BR-TEN-043`).
    assert read.read_at.date().isoformat() == "2026-03-15", (
        f"the read is dated {read.read_at} — the acceptance was 16 March, the job was the 15th"
    )
    # Compared as a NUMBER, never as a string: `meter_reads.current_value` is
    # one of the existing `NUMERIC(18,6)` columns CLAUDE.md hard rule 2 keeps as
    # a lawful container, so `1204.000000` and `1204.0000` are two spellings of
    # one value and only one of them is this column's.
    assert read.current_value == Decimal("1204"), read.current_value
    # …and the acceptance really did happen on a LATER day than the read, so
    # this case cannot pass by the two dates being the same.


def test_tc1_046_the_read_carries_its_unit(brazos, dana):
    """Hard rule 3 — *consumption always with an explicit unit; never assume*.

    ⚠ **THE UNIT ON THE COMMITTED READ IS THE REGISTER'S** (`BR-MET-143`), which
    is the right source. What this asserts is that it AGREES with the unit the
    technician measured in — the comparison `metering_seam.post_set_reads` makes
    on the way back out, because metering's own door drops the caller's unit
    today (`DEF-WRK-4072`).
    """
    with tenant_ctx(brazos):
        oid = _order_on_a_meter(dana, brazos)
        sync.sync_batch(field_actor(oid, dana), oid, _batch(oid, _rows(oid)))
        _accept(dana, oid)
        read = metering_models.MeterRead.objects.get(tenant_id=brazos.id)

    assert read.unit == "kWh", read.unit


def test_tc2_046_a_reading_not_marked_posts_as_meter_read_posts_NOTHING(brazos, dana):
    """TC-2 — *New meter serial* is recorded on the order and reaches no meter.

    The template's three readings carry exactly one `posts_as_meter_read`, so
    the serial and the second read stay observations. A door that posted every
    captured value would put a serial number in a consumption history.
    """
    with tenant_ctx(brazos):
        oid = _order_on_a_meter(dana, brazos)
        rows = _rows(oid)
        items = _batch(oid, rows)["items"]
        # Capture the SERIAL as well, and nothing else changes.
        serial = rows["readings"][2]
        items.insert(
            -1,
            {
                "key": "ortiz-01-2026-03-15-020",
                "kind": "reading",
                "seq": 20,
                "captured_at": "2026-03-15T16:05:00Z",
                "payload": {"reading_id": str(serial.id), "value": "77412", "unit": "serial"},
            },
        )
        sync.sync_batch(field_actor(oid, dana), oid, {"items": items})
        _accept(dana, oid)
        assert metering_models.MeterRead.objects.filter(tenant_id=brazos.id).count() == 1


def test_tc4_046_a_reading_with_NO_UNIT_never_reaches_metering(brazos, dana):
    """TC-4 · hard rule 3 — refused BEFORE the door, and the acceptance rolls
    back so the order stays in the review queue.

    ⚠ **THE COLUMN IS NOT NULL, so this is a blank rather than a NULL** — which
    is the shape a bad migration or a hand-edited row would take, and it is
    exactly the case a validator on the API alone cannot catch.
    """
    from core import errors

    with tenant_ctx(brazos):
        oid = _order_on_a_meter(dana, brazos)
        sync.sync_batch(field_actor(oid, dana), oid, _batch(oid, _rows(oid)))
        work_models.WorkOrderReading.objects.filter(
            work_order_id=oid, posts_as_meter_read=True
        ).update(unit_of_measure="")
        with pytest.raises(errors.ApiError):
            _accept(dana, oid)
        order = work_tables.WorkOrder.objects.get(pk=oid)
        assert order.accepted_at is None, "the acceptance did not roll back"
        assert metering_models.MeterRead.objects.filter(tenant_id=brazos.id).count() == 0


def test_046_two_posting_readings_are_REFUSED_by_name_and_never_guessed(brazos, dana):
    """⚠ **`OQ-WRK-1723` — WHICH METER A READING BELONGS TO IS UNRULED.**

    `work_order_readings` has six columns and none names a meter. A meter
    EXCHANGE has two meters and the only thing separating its two posting
    readings is the wording of a prompt a tenant may edit. Posting both to the
    order's anchor would write a second read on the OLD meter — a wrong number
    on a billing path, from a guess. So it refuses, and the question goes to the
    Product Owner (prime directive: never resolve an open question by choosing
    a value).
    """
    from core import errors

    with tenant_ctx(brazos):
        oid = _order_on_a_meter(dana, brazos)
        sync.sync_batch(field_actor(oid, dana), oid, _batch(oid, _rows(oid)))
        second = work_models.WorkOrderReading.objects.get(
            work_order_id=oid, prompt="Opening read, new meter"
        )
        second.posts_as_meter_read = True
        second.value = "48221"
        second.save(update_fields=["posts_as_meter_read", "value"])
        with pytest.raises(errors.ApiError) as caught:
            _accept(dana, oid)

    assert caught.value.params.get("tracks") == "OQ-WRK-1723", caught.value.params


def test_046_accepting_twice_posts_one_read(brazos, dana):
    """A second acceptance is refused as idempotent, so the meter's history
    cannot gain a duplicate from a double-click."""
    from core import errors

    with tenant_ctx(brazos):
        oid = _order_on_a_meter(dana, brazos)
        sync.sync_batch(field_actor(oid, dana), oid, _batch(oid, _rows(oid)))
        _accept(dana, oid)
        with pytest.raises(errors.ApiError):
            _accept(dana, oid)
        assert metering_models.MeterRead.objects.filter(tenant_id=brazos.id).count() == 1
