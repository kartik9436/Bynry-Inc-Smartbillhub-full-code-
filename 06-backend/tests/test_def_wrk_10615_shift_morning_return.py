# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-10615 — End shift left the technician off on the board the
#           next day (decision log 2026-10-26, PO *"yes reset each morning"*)
# Rules:    BR-WRK-069 · hard rules 1 and 7
# Code:     apps/work/shifts.py `morning_return` · apps/work/shift_morning.py ·
#           apps/work/workforce.py `set_unavailable` (settles the End shift)
# ───────────────────────────────────────────────────────
"""A technician whom End shift set *off today* is back *on shift* at the start
of their next working day — and only then, and only that kind of *off*.

Calendar: Thu 29 Oct, Fri 30 Oct, Sat 31 Oct, Sun 1 Nov, Mon 2 Nov 2026."""

from __future__ import annotations

from datetime import date, datetime, time

import pytest

from apps.tenancy import models as tenancy_models
from apps.work import shift_morning, shifts, workforce
from apps.work import models as work_models
from apps.work.shift_models import TechnicianShiftEnd

from tests.test_cr187_order_helpers import person
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin · audit_rows
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

THU = date(2026, 10, 29)
FRI = date(2026, 10, 30)
SAT = date(2026, 10, 31)
SUN = date(2026, 11, 1)
MON = date(2026, 11, 2)


def _at(day: date, hh: int, mm: int = 0) -> datetime:
    return datetime.combine(day, time(hh, mm), tzinfo=shifts._tz())


def _ortiz(tenant, email="d.ortiz@field.test"):
    tech, actor = person(tenant, email, "D. Ortiz")
    work_models.Technician.objects.filter(pk=tech.id).update(shift_start=time(7, 0), shift_end=time(15, 30))
    tech.refresh_from_db()
    return tech, actor


def _end(actor, day: date, key: str) -> None:
    shifts.end_shift(actor, {"key": key, "at": _at(day, 15, 31).isoformat()}, now=_at(day, 15, 40))


def _status(tech) -> str:
    return work_models.Technician.objects.get(pk=tech.id).status


def test_friday_end_shift_weekend_off_monday_on_shift(brazos, audit_rows):
    with tenant_ctx(brazos):
        tech, actor = _ortiz(brazos)
        _end(actor, FRI, "end-fri")
        saturday = shifts.morning_return(now=_at(SAT, 0, 5))
        on_saturday = _status(tech)
        sunday = shifts.morning_return(now=_at(SUN, 0, 5))
        monday = shifts.morning_return(now=_at(MON, 0, 5))
        on_monday = _status(tech)
        again = shifts.morning_return(now=_at(MON, 1, 5))
        settled = TechnicianShiftEnd.objects.get(technician_id=tech.id).settled_at
        week = shifts.week(actor, None, now=_at(MON, 8))
    assert on_saturday == "off_today" and saturday == {"returned": 0, "kept_off": 1}
    assert sunday == {"returned": 0, "kept_off": 1}
    assert on_monday == "on_shift" and monday == {"returned": 1, "kept_off": 0}
    assert again == {"returned": 0, "kept_off": 0}  # idempotent
    assert settled is not None
    assert week["current"]["minutes_so_far"] == 60
    rows = [r for r in audit_rows if r["action"] == "work.shift.morning_return"]
    assert len(rows) == 1
    assert rows[0]["before"] == {"status": "off_today"}
    assert rows[0]["after"]["status"] == "on_shift" and rows[0]["after"]["shift_ended_on"] == "2026-10-30"


def test_a_saturday_working_day_returns_but_a_non_working_one_does_not(brazos, dana):
    with tenant_ctx(brazos):
        tech, actor = _ortiz(brazos)
        _end(actor, FRI, "end-fri")
        shifts.morning_return(now=_at(SAT, 0, 5))
        not_working = _status(tech)
        shifts.set_working_days(dana, workforce.technician_slug(
            work_models.Technician.objects.select_related("user").get(pk=tech.id)
        ), {"weekdays": ["mon", "tue", "wed", "thu", "fri", "sat"]})
        shifts.morning_return(now=_at(SAT, 1, 5))
        working = _status(tech)
    assert not_working == "off_today"
    assert working == "on_shift"


def test_a_utility_holiday_keeps_them_off_until_the_next_working_day(brazos):
    with tenant_ctx(brazos):
        tenancy_models.HolidayCalendar.objects.create(tenant_id=brazos.id, holiday_date=FRI, label="Founders Day")
        tech, actor = _ortiz(brazos)
        _end(actor, THU, "end-thu")
        shifts.morning_return(now=_at(FRI, 0, 5))
        on_holiday = _status(tech)
        shifts.morning_return(now=_at(MON, 0, 5))
        on_monday = _status(tech)
    assert on_holiday == "off_today"
    assert on_monday == "on_shift"


def test_a_whole_day_off_exception_keeps_them_off_a_window_returns_them(brazos, dana):
    with tenant_ctx(brazos):
        tech, actor = _ortiz(brazos)
        slug = workforce.technician_slug(work_models.Technician.objects.select_related("user").get(pk=tech.id))
        shifts.add_exception(dana, slug, {"date": MON.isoformat(), "kind": "off", "note": "Dentist"})
        _end(actor, FRI, "end-fri")
        shifts.morning_return(now=_at(MON, 0, 5))
        on_monday = _status(tech)
        shifts.add_exception(dana, slug, {"date": "2026-11-03", "kind": "window", "start": "10:00", "end": "14:00"})
        shifts.morning_return(now=_at(date(2026, 11, 3), 0, 5))
        on_tuesday = _status(tech)
    assert on_monday == "off_today"
    assert on_tuesday == "on_shift"


def test_an_off_status_the_office_set_is_never_touched(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        # (a) set by hand, no End shift at all
        by_hand, _a = _ortiz(brazos, "a.hand@field.test")
        work_models.Technician.objects.filter(pk=by_hand.id).update(status="off_today")
        # (b) End shift on Friday, then the office sets them off on Friday evening
        after_end, actor_b = _ortiz(brazos, "b.after@field.test")
        _end(actor_b, FRI, "end-b")
        workforce.set_unavailable(dana, after_end.id, {"status": "off_today", "reason": "Training Monday"})
        # (c) the office had them unavailable when they pressed End shift
        unavailable, actor_c = _ortiz(brazos, "c.unavail@field.test")
        workforce.set_unavailable(dana, unavailable.id, {"status": "unavailable", "reason": "Injury"})
        _end(actor_c, FRI, "end-c")
        out = shifts.morning_return(now=_at(MON, 0, 5))
        week_b = shifts.week(actor_b, None, now=_at(MON, 9))
        statuses = (_status(by_hand), _status(after_end), _status(unavailable))
    assert statuses == ("off_today", "off_today", "off_today")
    assert out == {"returned": 0, "kept_off": 0}
    assert week_b["current"] is None  # the phone obeys the office too
    assert not [r for r in audit_rows if r["action"] == "work.shift.morning_return"]


def test_another_utility_is_untouched_and_returns_in_its_own_context(brazos, lonestar):
    with tenant_ctx(brazos):
        mine, actor = _ortiz(brazos)
        _end(actor, FRI, "end-brazos")
    with tenant_ctx(lonestar):
        theirs, their_actor = _ortiz(lonestar, "l.tech@field.test")
        _end(their_actor, FRI, "end-lonestar")
    with tenant_ctx(brazos):
        here = shifts.morning_return(now=_at(MON, 0, 5))
        brazos_status = _status(mine)
    with tenant_ctx(lonestar):
        lonestar_before = _status(theirs)
        there = shifts.morning_return(now=_at(MON, 0, 5))
        lonestar_after = _status(theirs)
    assert here == {"returned": 1, "kept_off": 0} and brazos_status == "on_shift"
    assert lonestar_before == "off_today"
    assert there == {"returned": 1, "kept_off": 0} and lonestar_after == "on_shift"


def test_the_job_runs_in_its_utility_and_the_hourly_beat_entry_installs(brazos, dana):
    with tenant_ctx(brazos):
        tech, actor = _ortiz(brazos)
        # Every weekday a working day, so the real "today" the job reads is one.
        slug = workforce.technician_slug(work_models.Technician.objects.select_related("user").get(pk=tech.id))
        shifts.set_working_days(dana, slug, {"weekdays": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]})
        _end(actor, date(2020, 1, 3), "end-long-ago")  # a Friday, long past
    out = shift_morning.run_morning_return_job({"tenant_id": str(brazos.id), "payload": {}})
    with tenant_ctx(brazos):
        status = _status(tech)
    assert out["returned"] == 1 and status == "on_shift"

    class _App:
        class conf:  # noqa: N801 — celery's own attribute name
            beat_schedule: dict = {}

        @staticmethod
        def task(name, bind=False):
            return lambda fn: fn

    installed = shift_morning.install(_App)
    entry = _App.conf.beat_schedule[shift_morning.BEAT_ENTRY]
    assert installed["installed"] is True
    assert entry["task"] == shift_morning.SWEEP_TASK and entry["schedule"] == 3600.0
