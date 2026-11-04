# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 lane S-SYNC — T-31 (tombstones in the delta) and T-32
#           (a watermark cursor per table on the day read)
# Rules:    R56 (a pull is a delta against a watermark) · R57 (a delta carries
#           removals) · BR-WRK-063 (the change feed) · BR-WRK-025 (assignment
#           is an append-only history) · NFR-3/NFR-5 (paged, no cap) ·
#           CLAUDE.md hard rule 1 (tenant scoping)
# ───────────────────────────────────────────────────────
"""`GET /work/mobile/changes` — every way a job leaves a technician arrives as
a tombstone, and a refresh after the day read is a delta.

⚠ **THE FIRST CASE BELOW WAS RED ON THE FEED AS IT STOOD.** The old feed read
its removals as `WorkOrderAssignment(technician=me, act="unassign")`, and every
`unassign` row is written with `technician` NULL — so a reassigned job never
produced a tombstone and stayed on the old technician's handset for good.
Nothing on the screen looked wrong, which is Data.txt §6's warning word for
word.
"""

from __future__ import annotations

import base64
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.urls import resolve
from django.utils import timezone

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import dispatch, mobile
from apps.work import models as work_models
from apps.work import services as work_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import make_premises
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


# ── fixtures ──────────────────────────────────────────────────────────────
def _seed():
    for code in ("work_priorities", "work_order_types", "work_hold_reasons"):
        work_services.seed_reference_list(code, [], "test")


def _technician(tenant, email, name):
    from apps.identity import models as identity_models

    user = identity_models.User.objects.create(tenant_id=tenant.id, email=email, full_name=name)
    return work_models.Technician.objects.create(tenant_id=tenant.id, user=user)


def _as(tech):
    return SimpleNamespace(id=tech.user_id, role="field_technician")


def _raise(actor, address, service="water"):
    premises = make_premises(actor, address_line=address, services_available=[service])
    return w6.create_work_order(
        actor, None, {"type": "Leak investigation", "service": service, "premises_id": premises["id"]}
    )["id"]


def _assign(actor, oid, tech, reason=None):
    payload = {"act": "assign", "technician_id": str(tech.id)}
    if reason:
        payload["reason"] = reason
    dispatch.record_act(actor, oid, payload, push=False)


def _drain(actor, cursor=None, per=50):
    """Page the feed to the end, as the phone does; returns (changes, cursor, pages)."""
    seen, pages = [], 0
    while True:
        page = mobile.changes(actor, cursor=cursor, per=per)
        pages += 1
        seen.extend(page["changes"])
        cursor = page["next_cursor"]
        assert pages < 1000, "the feed never ran dry"
        if not page["has_more"]:
            return seen, cursor, pages


def _removed(changes):
    return {(c["order_id"], c["reason"]) for c in changes if c["change"] == "removed"}


def _upserted(changes):
    return {c["order_id"] for c in changes if c["change"] == "upsert"}


def _age(order_ids, hours=1):
    """Put these orders' last change an hour back — outside the settle window
    (`mobile.FEED_SETTLE`), which re-sends the last two minutes on purpose.
    `QuerySet.update` does not fire `auto_now`, so the stamp sticks."""
    work_tables.WorkOrder.objects.filter(pk__in=order_ids).update(
        updated_at=timezone.now() - timedelta(hours=hours)
    )


# ══════════════════════════════════════════════════════════════════════════
# T-31 · every way a job leaves a technician is a tombstone
# ══════════════════════════════════════════════════════════════════════════
def test_a_reassigned_job_arrives_as_a_tombstone_for_the_old_technician(brazos, dana):
    with tenant_ctx(brazos):
        _seed()
        ortiz = _technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        patel = _technician(brazos, "r-patel@brazos.test", "R. Patel")
        oid = _raise(dana, "221 Oak Ave")
        _assign(dana, oid, ortiz)
        first, cursor, _ = _drain(_as(ortiz))
        assert _upserted(first) == {str(oid)}

        _assign(dana, oid, patel, reason="Ortiz off sick")
        delta, _, _ = _drain(_as(ortiz), cursor)
        patel_feed, _, _ = _drain(_as(patel))

    assert _removed(delta) == {(str(oid), "reassigned")}, delta
    assert str(oid) not in _upserted(delta)
    assert _upserted(patel_feed) == {str(oid)}


def test_an_unassigned_job_arrives_as_a_tombstone(brazos, dana):
    with tenant_ctx(brazos):
        _seed()
        ortiz = _technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        oid = _raise(dana, "221 Oak Ave")
        _assign(dana, oid, ortiz)
        _, cursor, _ = _drain(_as(ortiz))
        dispatch.record_act(dana, oid, {"act": "unassign", "reason": "Back to the queue"}, push=False)
        delta, _, _ = _drain(_as(ortiz), cursor)

    assert _removed(delta) == {(str(oid), "unassigned")}, delta


def test_a_SCHEDULE_naming_somebody_else_moves_the_job_with_no_unassign_row_and_still_tombstones(
    brazos, dana
):
    """The way out with no `unassign` row at all: `record_act` writes a bare
    `schedule` naming the new technician, and `_refresh_cache` moves the
    holder. A feed keyed on `unassign` could not see this however it was
    fixed — only a walk of the holder history can."""
    with tenant_ctx(brazos):
        _seed()
        ortiz = _technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        patel = _technician(brazos, "r-patel@brazos.test", "R. Patel")
        oid = _raise(dana, "221 Oak Ave")
        _assign(dana, oid, ortiz)
        _, cursor, _ = _drain(_as(ortiz))
        soon = timezone.now() + timedelta(hours=3)
        dispatch.record_act(
            dana, oid,
            {"act": "schedule", "technician_id": str(patel.id), "window_start": soon.isoformat(),
             "window_end": (soon + timedelta(hours=1)).isoformat()},
            push=False,
        )
        acts = list(
            work_models.WorkOrderAssignment.objects.filter(work_order_id=oid).values_list("act", flat=True)
        )
        delta, _, _ = _drain(_as(ortiz), cursor)

    assert "unassign" not in acts, acts
    assert _removed(delta) == {(str(oid), "reassigned")}, delta


def test_a_cancelled_job_arrives_as_a_tombstone_and_leaves_the_day(brazos, dana):
    with tenant_ctx(brazos):
        _seed()
        ortiz = _technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        oid = _raise(dana, "221 Oak Ave")
        kept = _raise(dana, "223 Oak Ave")
        _assign(dana, oid, ortiz)
        _assign(dana, kept, ortiz)
        _, cursor, _ = _drain(_as(ortiz))
        dispatch.set_dispatch_state(dana, oid, "cancelled", "work.order.cancelled")
        delta, _, _ = _drain(_as(ortiz), cursor)
        day = mobile.today(_as(ortiz))
        fresh, _, _ = _drain(_as(ortiz))

    assert _removed(delta) == {(str(oid), "cancelled")}, delta
    # …and neither the day read nor a first full pass puts it back.
    assert [j["id"] for j in day["jobs"]] == [str(kept)]
    assert _upserted(fresh) == {str(kept)} and not _removed(fresh)


def test_a_job_that_comes_BACK_follows_its_tombstone_with_an_upsert(brazos, dana):
    with tenant_ctx(brazos):
        _seed()
        ortiz = _technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        patel = _technician(brazos, "r-patel@brazos.test", "R. Patel")
        oid = _raise(dana, "221 Oak Ave")
        _assign(dana, oid, ortiz)
        _, cursor, _ = _drain(_as(ortiz))
        _assign(dana, oid, patel, reason="swap")
        _assign(dana, oid, ortiz, reason="swap back")
        delta, _, _ = _drain(_as(ortiz), cursor)

    kinds = [(c["change"], c["order_id"]) for c in delta]
    assert kinds.index(("removed", str(oid))) < kinds.index(("upsert", str(oid))), kinds


def test_a_reassign_between_two_OTHER_people_is_not_a_tombstone_twice(brazos, dana):
    with tenant_ctx(brazos):
        _seed()
        ortiz = _technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        patel = _technician(brazos, "r-patel@brazos.test", "R. Patel")
        chen = _technician(brazos, "l-chen@brazos.test", "L. Chen")
        oid = _raise(dana, "221 Oak Ave")
        _assign(dana, oid, ortiz)
        _, cursor, _ = _drain(_as(ortiz))
        _assign(dana, oid, patel, reason="one")
        once, cursor_after, _ = _drain(_as(ortiz), cursor)
        _assign(dana, oid, chen, reason="two")
        later, _, _ = _drain(_as(ortiz), cursor_after)

    assert _removed(once) == {(str(oid), "reassigned")}
    # The settle window may re-send Ortiz's own tombstone; Patel → Chen adds none.
    assert {c["at"] for c in later if c["change"] == "removed"} <= {c["at"] for c in once}


def test_a_job_the_technician_CLOSED_is_an_upsert_not_a_tombstone(brazos, dana):
    """Closed is not taken away: FF-35 *Completed* keeps it for fourteen days
    (Data.txt §7), so the card arrives reading `completed`."""
    with tenant_ctx(brazos):
        _seed()
        ortiz = _technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        oid = _raise(dana, "221 Oak Ave")
        _assign(dana, oid, ortiz)
        _, cursor, _ = _drain(_as(ortiz))
        work_tables.WorkOrder.objects.filter(pk=oid).update(state="completed", updated_at=timezone.now())
        delta, _, _ = _drain(_as(ortiz), cursor)

    assert not _removed(delta)
    cards = [c["job"] for c in delta if c["change"] == "upsert" and c["order_id"] == str(oid)]
    assert cards and cards[-1]["state"] == "completed"


# ══════════════════════════════════════════════════════════════════════════
# T-32 · the day read hands out a cursor, and a refresh is a delta
# ══════════════════════════════════════════════════════════════════════════
def test_the_day_read_hands_out_a_cursor_and_the_refresh_after_it_is_a_delta(brazos, dana):
    with tenant_ctx(brazos):
        _seed()
        ortiz = _technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        old = [_raise(dana, f"{n} Elm St") for n in range(1, 4)]
        for oid in old:
            _assign(dana, oid, ortiz)
        _age(old)
        day = mobile.today(_as(ortiz))
        assert len(day["jobs"]) == 3 and day["cursor"]
        nothing, cursor, _ = _drain(_as(ortiz), day["cursor"])
        assert nothing == [], "a refresh straight after the day read re-sent the day"
        # Without the day's cursor the same call is a FULL pass — the contrast
        # that makes the empty answer above mean something.
        everything, _, _ = _drain(_as(ortiz))
        assert _upserted(everything) == {str(o) for o in old}

        new = _raise(dana, "9 Elm St")
        _assign(dana, new, ortiz)
        delta, _, _ = _drain(_as(ortiz), cursor)

    assert _upserted(delta) == {str(new)}, delta


def test_the_cursor_holds_a_watermark_PER_TABLE_and_is_opaque(brazos, dana):
    with tenant_ctx(brazos):
        _seed()
        ortiz = _technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        oid = _raise(dana, "221 Oak Ave")
        _assign(dana, oid, ortiz)
        _, cursor, _ = _drain(_as(ortiz))
    text = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
    assert '"wo":' in text and '"as":' in text and '"v":2' in text


def test_a_cursor_minted_before_CR_187_is_still_read(brazos, dana):
    """Additive: a web field app that stored the old `iso|id` cursor resumes."""
    with tenant_ctx(brazos):
        _seed()
        ortiz = _technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        patel = _technician(brazos, "r-patel@brazos.test", "R. Patel")
        oid = _raise(dana, "221 Oak Ave")
        _assign(dana, oid, ortiz)
        legacy = mobile._encode_cursor(timezone.now() - timedelta(seconds=1), mobile._NIL_ID)
        _assign(dana, oid, patel, reason="swap")
        delta, _, _ = _drain(_as(ortiz), legacy)
    assert _removed(delta) == {(str(oid), "reassigned")}


def test_a_malformed_cursor_is_refused_by_name(brazos, dana):
    with tenant_ctx(brazos):
        _seed()
        ortiz = _technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        for bad in ("not-a-cursor", base64.urlsafe_b64encode(b'{"v":9}').decode()):
            with pytest.raises(errors.ValidationError) as refused:
                mobile.changes(_as(ortiz), cursor=bad)
            assert refused.value.message_key == "work.mobile.cursor_malformed"


def test_the_feed_pages_with_no_cap_and_loses_or_doubles_nothing(brazos, dana):
    """NFR-3/NFR-5 — 120 jobs at a page of 50 is three pages, every job once."""
    with tenant_ctx(brazos):
        _seed()
        ortiz = _technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        premises = make_premises(dana, address_line="500 Main St", services_available=["water"])
        ids = []
        for _ in range(120):
            oid = w6.create_work_order(
                dana, None,
                {"type": "Meter read", "service": "water", "premises_id": premises["id"]},
            )["id"]
            _assign(dana, oid, ortiz)
            ids.append(str(oid))
        seen, _, pages = _drain(_as(ortiz), per=50)

    assert pages == 3, pages
    upserts = [c["order_id"] for c in seen if c["change"] == "upsert"]
    assert len(upserts) == 120 and set(upserts) == set(ids)


# ══════════════════════════════════════════════════════════════════════════
# Hard rule 1 · a second tenant's jobs never appear
# ══════════════════════════════════════════════════════════════════════════
def test_a_second_tenants_jobs_never_appear_in_the_feed(brazos, dana, lonestar, erin):
    with tenant_ctx(lonestar):
        _seed()
        okafor = _technician(lonestar, "j-okafor@lsr.test", "J. Okafor")
        theirs = _raise(erin, "1 Ridge Rd")
        _assign(erin, theirs, okafor)
        other = _raise(erin, "2 Ridge Rd")
        _assign(erin, other, okafor)
        _assign(erin, other, _technician(lonestar, "k-lee@lsr.test", "K. Lee"), reason="swap")
    with tenant_ctx(brazos):
        _seed()
        ortiz = _technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        mine = _raise(dana, "221 Oak Ave")
        _assign(dana, mine, ortiz)
        seen, cursor, _ = _drain(_as(ortiz))
        # The same login id under the other tenant's context finds no
        # technician at all — the profile is tenant-scoped.
        later, _, _ = _drain(_as(ortiz), cursor)
    with tenant_ctx(lonestar):
        stranger = mobile.changes(_as(ortiz))

    ids = {c["order_id"] for c in seen + later}
    assert str(theirs) not in ids and str(other) not in ids
    assert _upserted(seen) == {str(mine)}
    assert stranger["changes"] == []


# ══════════════════════════════════════════════════════════════════════════
# Wiring (hard-won law 2)
# ══════════════════════════════════════════════════════════════════════════
def test_the_feed_and_the_batch_routes_are_mounted():
    for path, name in (("/api/brazosbend/work/mobile/changes", "mobile_changes"),
                       ("/api/brazosbend/work/mobile/sync", "mobile_sync_batch")):
        match = resolve(path)
        assert match._func_path == f"apps.work.api.{name}", match
