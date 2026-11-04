# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-FLD-10639 — FB-014: a phone whose clock runs ahead of the
#           server had its job time refused "That time is in the future"
# Ruling:   PO 2026-10-28, verbatim: *"job should be synced with the server
#           accept the future time"* (decision log of that date)
# Rules:    BR-TEN-043 · BR-WRK-003 · BR-WRK-020 · hard rule 7
# Code:     core/device_clock.py · core/field_app_version.py ·
#           apps/work/{field_labour,mobile,sync,field_raise,shifts}.py ·
#           apps/metering/field_reads.py
# ───────────────────────────────────────────────────────
"""**A PHONE'S CLOCK IS NEVER A REFUSAL: EVERY TIME IT SENDS IS SHIFTED ONTO
THE SERVER'S CLOCK.**

Every case sends from a phone whose clock disagrees with the server's — 30 s
fast, 10 min fast, 1 h fast, 10 min slow — which is the one thing no test in
this repo did before, because every fixture stamped its times from the
server's own `timezone.now()`.

RED FIRST (2026-10-28), against the services as they stood with only the
helper added: the fast phones were refused `work.labour.moment_in_future` /
`work.mobile.labour_time_out_of_order`, and the slow phone was ACCEPTED and
stored ten minutes early — no error at all, which is why it needs its own case.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone as dt_timezone

import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import timezone

from apps.metering import field_reads
from apps.work import connection_models as work_tables
from apps.work import dispatch, field_labour, sync
from core import device_clock, errors
from core.field_app_version import FieldAppVersionMiddleware
from tests.test_cr187_order_helpers import job
from tests.test_def_wrk_4127_labour_time import _ready, _with_times
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · audit_rows
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_wrk_044_046_sync import _batch, _rows

pytestmark = pytest.mark.django_db

#: (name, how far the phone is AHEAD of the server)
PHONES = [
    ("30s_fast", timedelta(seconds=30)),
    ("10min_fast", timedelta(minutes=10)),
    ("1h_fast", timedelta(hours=1)),
    ("10min_slow", timedelta(minutes=-10)),
]


def _iso(dt):
    return dt.isoformat()


# ── the helper ──────────────────────────────────────────────────────────


def test_the_po_worked_figure_phone_12_07_30_server_12_02_30_stores_12_02():
    """The figure the PO was shown: offset −5 min; 12:07 on the phone is 12:02."""
    server = datetime(2026, 10, 21, 12, 2, 30, tzinfo=dt_timezone.utc)
    with device_clock.measured("2026-10-21T12:07:30Z", server_now=server) as reading:
        assert reading.offset_s == -300
        stored = device_clock.correct(datetime(2026, 10, 21, 12, 7, tzinfo=dt_timezone.utc))
    assert stored == datetime(2026, 10, 21, 12, 2, tzinfo=dt_timezone.utc)


def test_two_seconds_is_the_network_not_the_clock():
    now = timezone.now()
    assert device_clock.measure(_iso(now - timedelta(seconds=2)), now).offset_s == 0
    assert device_clock.measure(_iso(now - timedelta(seconds=3)), now).offset_s == 3


def test_a_reading_with_no_zone_or_garbage_is_no_reading():
    assert device_clock.measure("2026-10-28T12:07:30") is None
    assert device_clock.measure("yesterday") is None
    assert device_clock.measure(None) is None


def test_a_shifted_time_still_ahead_is_clamped_to_now_never_refused():
    """The stated limitation: the clock was set back between capture and send."""
    now = timezone.now()
    with device_clock.measured(_iso(now)):
        moved = device_clock.correct(now + timedelta(hours=3))
    assert moved <= timezone.now()


def test_no_reading_clamps_five_minutes_and_leaves_the_rest_to_the_caller():
    now = timezone.now()
    assert device_clock.correct(now + timedelta(minutes=3)) <= timezone.now()
    far = now + timedelta(hours=2)
    assert device_clock.correct(far) == far


def test_the_middleware_measures_once_and_answers_its_own_time():
    seen = {}

    def view(request):
        seen["reading"] = device_clock.current()
        return HttpResponse("{}", content_type="application/json")

    phone = timezone.now() + timedelta(minutes=10)
    request = RequestFactory().get(
        "/api/brazos/work/mobile/week", HTTP_X_DEVICE_TIME=_iso(phone)
    )
    response = FieldAppVersionMiddleware(view)(request)
    assert seen["reading"] is not None
    assert -601 <= seen["reading"].offset_s <= -599
    assert response[device_clock.SERVER_TIME_HEADER]
    assert device_clock.current() is None, "the reading must not outlive its request"


# ── labour: the reported refusal ────────────────────────────────────────


@pytest.mark.parametrize("name,ahead", PHONES, ids=[p[0] for p in PHONES])
def test_labour_from_a_wrong_clock_is_accepted_shifted_and_its_minutes_kept(
    brazos, dana, audit_rows, name, ahead
):
    """FB-014's `Time · WO-0171`. The technician ends work JUST NOW on the
    phone after 42 minutes; it is stored on the server's clock, still 42."""
    server_now = timezone.now()
    phone_now = server_now + ahead
    with tenant_ctx(brazos):
        oid, lead = job(dana, brazos)
        with device_clock.measured(_iso(phone_now), server_now=server_now):
            out = field_labour.record_time(
                lead,
                oid,
                {"start_at": _iso(phone_now - timedelta(minutes=42)), "end_at": _iso(phone_now)},
            )
    assert out["labour_minutes"] == 42
    stored_end = datetime.fromisoformat(out["end_at"])
    assert abs((stored_end - server_now).total_seconds()) <= 1, (name, out["end_at"])
    recorded = [r for r in audit_rows if (r.get("action") if isinstance(r, dict) else getattr(r, "action", None)) == "work.labour.recorded"]
    after = recorded[-1]["after"] if isinstance(recorded[-1], dict) else recorded[-1].after
    assert after["clock_offset_s"] == -int(ahead.total_seconds()) or abs(ahead.total_seconds()) <= 2
    assert after["device_time"] == _iso(phone_now)


def test_with_no_reading_two_hours_ahead_is_still_refused_by_name(brazos, dana):
    with tenant_ctx(brazos):
        oid, lead = job(dana, brazos)
        with pytest.raises(errors.ValidationError) as refused:
            field_labour.record_time(lead, oid, {"end_at": _iso(timezone.now() + timedelta(hours=2))})
    assert refused.value.message_key == "work.labour.moment_in_future"


def test_with_no_reading_three_minutes_ahead_is_clamped_not_refused(brazos, dana):
    with tenant_ctx(brazos):
        oid, lead = job(dana, brazos)
        out = field_labour.record_time(lead, oid, {"end_at": _iso(timezone.now() + timedelta(minutes=3))})
    assert datetime.fromisoformat(out["end_at"]) <= timezone.now()


# ── the close: labour times, completed_at (which dates the read), the record ─


@pytest.mark.parametrize("name,ahead", PHONES, ids=[p[0] for p in PHONES])
def test_a_close_from_a_wrong_clock_is_accepted_and_dated_on_the_server_clock(
    brazos, dana, name, ahead
):
    server_now = timezone.now().replace(microsecond=0)
    phone_now = server_now + ahead
    arrived = phone_now - timedelta(minutes=95)
    finished = phone_now - timedelta(seconds=10)
    with tenant_ctx(brazos):
        oid, field = _ready(dana, brazos)
        batch = _with_times(_batch(oid, _rows(oid)), arrived=_iso(arrived), finished=_iso(finished))
        for item in batch["items"]:
            item["captured_at"] = _iso(finished)
        with device_clock.measured(_iso(phone_now), server_now=server_now):
            out = sync.sync_batch(field, oid, batch)
        assert out["refused"] == 0, out
        order = work_tables.WorkOrder.objects.get(pk=oid)
        closed = dispatch.order_row(oid)["closed"]
    shift = -ahead if abs(ahead.total_seconds()) > 2 else timedelta(0)
    assert order.completed_at == finished + shift, "the meter read is dated from this"
    assert order.minutes_on_site == 95, "the shift moves both ends; the minutes do not move"
    assert closed["labour_time"]["finished_at"] == _iso(finished + shift)
    clock = order.field_data["device_clock"]
    assert clock["offset_s"] == int(shift.total_seconds())
    assert clock["sent"]["finished_at"] == _iso(finished), "the phone's own time is kept"


def test_the_office_is_told_the_phone_clock_was_ten_minutes_fast(brazos, dana):
    server_now = timezone.now().replace(microsecond=0)
    phone_now = server_now + timedelta(minutes=10)
    with tenant_ctx(brazos):
        oid, field = _ready(dana, brazos)
        batch = _with_times(
            _batch(oid, _rows(oid)),
            arrived=_iso(phone_now - timedelta(minutes=30)),
            finished=_iso(phone_now),
        )
        with device_clock.measured(_iso(phone_now), server_now=server_now):
            sync.sync_batch(field, oid, batch)
        closed = dispatch.order_row(oid)["closed"]
    assert closed["device_clock"]["offset_s"] == -600


# ── route readings ──────────────────────────────────────────────────────


def test_a_route_reading_from_a_phone_an_hour_fast_is_not_dated_tomorrow():
    """23:30 on the server, 00:30 tomorrow on the phone: the reading's day is
    the server's day (BR-TEN-043)."""
    server = datetime(2026, 10, 27, 23, 30, tzinfo=dt_timezone.utc)
    with device_clock.measured("2026-10-28T00:30:00Z", server_now=server):
        stored = field_reads._captured_at("2026-10-28T00:29:00Z")
    assert stored == datetime(2026, 10, 27, 23, 29, tzinfo=dt_timezone.utc)
