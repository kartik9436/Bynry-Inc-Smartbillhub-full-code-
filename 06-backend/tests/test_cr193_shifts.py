# ── Trace ──────────────────────────────────────────────
# Change:   CR-193-BRC10 — MQ-040 STEP 1 (decision log 2026-10-26)
# Rules:    BR-WRK-068 · BR-WRK-069 · BR-WRK-070 · hard rules 1, 6, 7 · NFR-3
# Code:     apps/work/shifts.py · shifts_api.py · shift_models.py
# ───────────────────────────────────────────────────────
"""Working days and exceptions (office), the phone's week, End shift, Submit the day.

The PO's worked example is the first case: D. Ortiz Mon–Fri 07:00–15:30,
Fri 30 Oct a utility holiday → Mon–Thu 07:00–15:30, Fri *Holiday*."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest
from django.test import Client

from apps.identity.models import User
from apps.tenancy import models as tenancy_models
from apps.work import field_labour, shifts, workforce
from apps.work import models as work_models
from apps.work.shift_models import TechnicianShiftEnd, TimesheetSubmission
from core import errors

from tests.isolation_helpers import writing_as_tenant
from tests.test_cr187_order_helpers import job, person
from tests.test_us_idn_helpers import (  # noqa: F401 — fixture used by name
    JSON,
    SC,
    api_path,
    idn,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin · audit_rows
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

MON = date(2026, 10, 26)
FRI = date(2026, 10, 30)


def _at(day: date, hh: int, mm: int = 0) -> datetime:
    return datetime.combine(day, time(hh, mm), tzinfo=shifts._tz())


def _ortiz(tenant):
    tech, actor = person(tenant, "d.ortiz@field.test", "D. Ortiz")
    work_models.Technician.objects.filter(pk=tech.id).update(shift_start=time(7, 0), shift_end=time(15, 30))
    tech.refresh_from_db()
    return tech, actor


def _slug(tech) -> str:
    return workforce.technician_slug(work_models.Technician.objects.select_related("user").get(pk=tech.id))


def _holiday(tenant, day, label="Founders Day"):
    tenancy_models.HolidayCalendar.objects.create(tenant_id=tenant.id, holiday_date=day, label=label)


# ── the week ───────────────────────────────────────────────────────────────


def test_the_pos_worked_example_mon_to_thu_shifts_fri_holiday(brazos):
    with tenant_ctx(brazos):
        _tech, actor = _ortiz(brazos)
        _holiday(brazos, FRI)
        out = shifts.week(actor, None, now=_at(date(2026, 10, 28), 9, 15))
        started = _at(date(2026, 10, 28), 7).isoformat()
    kinds = [(d["date"], d["kind"], d["start"], d["end"], d["holiday"]) for d in out["days"]]
    assert out["from"] == "2026-10-26" and out["to"] == "2026-11-01"
    assert kinds[:4] == [(f"2026-10-2{n}", "shift", "07:00", "15:30", None) for n in (6, 7, 8, 9)]
    assert kinds[4] == ("2026-10-30", "holiday", None, None, "Founders Day")
    assert [k[1] for k in kinds[5:]] == ["off", "off"]
    # Today (Wed) at 09:15: on shift since 07:00 → 2h 15m so far.
    assert out["current"] == {
        "start": "07:00",
        "end": "15:30",
        "started_at": started,
        "minutes_so_far": 135,
    }


def test_an_exception_beats_the_rule_and_the_holiday(brazos, dana):
    with tenant_ctx(brazos):
        tech, actor = _ortiz(brazos)
        _holiday(brazos, FRI)
        slug = _slug(tech)
        shifts.add_exception(dana, slug, {"date": "2026-10-27", "kind": "off", "note": "Dentist"})
        shifts.add_exception(dana, slug, {"date": "2026-10-30", "kind": "window", "start": "06:00", "end": "10:00", "note": "On call"})
        out = shifts.week(actor, "2026-10-26", now=_at(MON, 6))
    tue, fri = out["days"][1], out["days"][4]
    assert (tue["kind"], tue["note"], tue["exception"]) == ("off", "Dentist", "off")
    assert (fri["kind"], fri["start"], fri["end"], fri["holiday"], fri["note"]) == ("shift", "06:00", "10:00", "Founders Day", "On call")
    assert out["current"] is None  # 06:00 Monday, before the 07:00 start


def test_working_days_replace_the_set_and_are_audited(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        tech, actor = _ortiz(brazos)
        slug = _slug(tech)
        before = shifts.working_days(slug)
        after = shifts.set_working_days(dana, slug, {"weekdays": ["tue", "wed", "thu", "fri", "sat"]})
        again = shifts.set_working_days(dana, slug, {"weekdays": ["sat", "tue", "wed", "thu", "fri"]})
        week = shifts.week(actor, "2026-10-26", now=_at(MON, 12))
        with pytest.raises(errors.ValidationError) as bad:
            shifts.set_working_days(dana, slug, {"weekdays": ["funday"]})
    assert before == {"weekdays": ["mon", "tue", "wed", "thu", "fri"], "is_default": True, "shift_start": "07:00", "shift_end": "15:30"}
    assert after["weekdays"] == ["tue", "wed", "thu", "fri", "sat"] and after["is_default"] is False
    assert again == after
    assert [d["kind"] for d in week["days"]] == ["off", "shift", "shift", "shift", "shift", "shift", "off"]
    assert week["current"] is None  # Monday is no longer a working day
    assert bad.value.message_key == "work.shifts.weekdays_invalid"
    set_rows = [r for r in audit_rows if r["action"] == "work.shift.working_days_set"]
    assert len(set_rows) == 1  # the second save changed nothing and wrote nothing


def test_exceptions_one_per_day_edit_remove_and_upcoming_first(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        tech, _actor = _ortiz(brazos)
        slug = _slug(tech)
        today = shifts._local_today()
        past = shifts.add_exception(dana, slug, {"date": (today - timedelta(days=3)).isoformat(), "kind": "off"})
        later = shifts.add_exception(dana, slug, {"date": (today + timedelta(days=9)).isoformat(), "kind": "off"})
        soon = shifts.add_exception(dana, slug, {"date": (today + timedelta(days=2)).isoformat(), "kind": "off"})
        with pytest.raises(errors.BizError) as taken:
            shifts.add_exception(dana, slug, {"date": soon["date"], "kind": "off"})
        with pytest.raises(errors.ValidationError) as backwards:
            shifts.add_exception(dana, slug, {"date": "2027-01-04", "kind": "window", "start": "10:00", "end": "09:00"})
        with pytest.raises(errors.ValidationError) as unknown:
            shifts.add_exception(dana, slug, {"date": "2027-01-04", "kind": "sick"})
        edited = shifts.edit_exception(dana, slug, soon["id"], {"kind": "window", "start": "12:00", "end": "16:00"})
        order = [r["date"] for r in shifts.exceptions_page(slug)["rows"]]
        shifts.remove_exception(dana, slug, later["id"])
        page = shifts.exceptions_page(slug, page=1, per=1)
    assert taken.value.message_key == "work.shifts.exception_exists"
    assert backwards.value.message_key == "work.shifts.window_invalid"
    assert unknown.value.message_key == "work.shifts.kind_invalid"
    assert (edited["kind"], edited["start"], edited["end"]) == ("window", "12:00", "16:00")
    assert order == [soon["date"], later["date"], past["date"]]
    assert page["total"] == 2 and [r["date"] for r in page["rows"]] == [soon["date"], past["date"]]
    actions = [r["action"] for r in audit_rows if r["action"].startswith("work.shift.exception_")]
    assert actions == ["work.shift.exception_added"] * 3 + ["work.shift.exception_changed", "work.shift.exception_removed"]


# ── End shift ──────────────────────────────────────────────────────────────


def test_end_shift_records_once_per_day_and_sets_off_today(brazos, audit_rows):
    with tenant_ctx(brazos):
        tech, actor = _ortiz(brazos)
        wed = date(2026, 10, 28)
        first = shifts.end_shift(actor, {"key": "end-1", "at": _at(wed, 15, 31).isoformat()}, now=_at(wed, 15, 40))
        replay = shifts.end_shift(actor, {"key": "end-1"}, now=_at(wed, 15, 45))
        other = shifts.end_shift(actor, {"key": "end-2"}, now=_at(wed, 16, 0))
        tech.refresh_from_db()
        after = shifts.week(actor, None, now=_at(wed, 15, 50))
        # Thursday morning: the off_today an End shift left behind is a new day.
        thursday = shifts.week(actor, None, now=_at(date(2026, 10, 29), 8))
        with pytest.raises(errors.ValidationError) as no_key:
            shifts.end_shift(actor, {}, now=_at(wed, 16))
        pressed_at = _at(wed, 15, 31).isoformat()
    assert first["duplicate"] is False and first["date"] == "2026-10-28"
    assert datetime.fromisoformat(first["ended_at"]) == datetime.fromisoformat(pressed_at)
    assert replay["duplicate"] is True and other["duplicate"] is True
    assert replay["ended_at"] == other["ended_at"] == first["ended_at"]
    assert TechnicianShiftEnd.objects.filter(technician_id=tech.id).count() == 1
    assert tech.status == "off_today"
    assert after["current"] is None and after["ended_at"] == first["ended_at"]
    assert thursday["current"]["minutes_so_far"] == 60 and thursday["ended_at"] is None
    assert no_key.value.message_key == "work.sync.item_key_required"
    ended = [r for r in audit_rows if r["action"] == "work.shift.ended"]
    assert len(ended) == 1 and ended[0]["before"] == {"status": "on_shift"}


def test_a_dispatchers_off_today_with_no_end_is_obeyed(brazos):
    with tenant_ctx(brazos):
        tech, actor = _ortiz(brazos)
        work_models.Technician.objects.filter(pk=tech.id).update(status="off_today")
        out = shifts.week(actor, None, now=_at(date(2026, 10, 28), 10))
    assert out["current"] is None


# ── Submit the day ─────────────────────────────────────────────────────────


def test_submit_the_day_snapshots_labour_and_travel_once(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        oid, lead = job(dana, brazos)
        tech = work_models.Technician.objects.get(user_id=lead.id)
        today = shifts._local_today() - timedelta(days=1)
        base = datetime.combine(today, time(0, 0), tzinfo=shifts._tz())
        now = base + timedelta(hours=14)
        field_labour.record_time(
            lead,
            oid,
            {
                "depart_at": (base + timedelta(hours=8)).isoformat(),
                "arrive_at": (base + timedelta(hours=8, minutes=14)).isoformat(),
                "start_at": (base + timedelta(hours=8, minutes=46)).isoformat(),
                "end_at": (base + timedelta(hours=9, minutes=58)).isoformat(),
            },
        )
        first = shifts.submit_day(lead, {"date": today.isoformat(), "key": "sheet-1"}, now=now)
        replay = shifts.submit_day(lead, {"date": today.isoformat(), "key": "sheet-1"}, now=now)
        other = shifts.submit_day(lead, {"date": today.isoformat(), "key": "sheet-2"}, now=now)
        # The office corrects the clock afterwards; the submitted day does not move.
        field_labour.record_time(lead, oid, {"end_at": (base + timedelta(hours=10)).isoformat()})
        listed = shifts.timesheets_page(_slug(tech))
        with pytest.raises(errors.ValidationError) as future:
            shifts.submit_day(lead, {"date": (today + timedelta(days=2)).isoformat(), "key": "sheet-3"}, now=now)
        with pytest.raises(errors.ValidationError) as bad_date:
            shifts.submit_day(lead, {"date": "yesterday", "key": "sheet-4"}, now=now)
    assert first["duplicate"] is False
    assert (first["jobs"], first["labour_minutes"], first["travel_minutes"]) == (1, 72, 14)
    assert first["lines"][0]["order_id"] == str(oid) and first["lines"][0]["order_no"]
    assert replay["duplicate"] is True and other["duplicate"] is True
    assert TimesheetSubmission.objects.filter(technician_id=tech.id).count() == 1
    assert listed["total"] == 1 and listed["rows"][0]["labour_minutes"] == 72
    assert future.value.message_key == "work.shifts.future_day"
    assert bad_date.value.message_key == "work.shifts.date_invalid"
    assert [r["action"] for r in audit_rows].count("work.timesheet.submitted") == 1


def test_a_day_with_no_clock_submits_zero_rather_than_refusing(brazos):
    with tenant_ctx(brazos):
        _tech, actor = _ortiz(brazos)
        out = shifts.submit_day(actor, {"date": "2026-10-01", "key": "empty-day"})
    assert (out["jobs"], out["labour_minutes"], out["travel_minutes"], out["lines"]) == (0, 0, 0, [])


# ── hard rule 1 ────────────────────────────────────────────────────────────


def test_another_utility_cannot_see_or_change_this_technician(brazos, lonestar, dana, erin):
    with tenant_ctx(brazos):
        tech, actor = _ortiz(brazos)
        slug = _slug(tech)
        shifts.add_exception(dana, slug, {"date": "2026-11-02", "kind": "off"})
        shifts.submit_day(actor, {"date": "2026-10-01", "key": "iso-1"})
    with tenant_ctx(lonestar):
        for call in (
            lambda: shifts.working_days(slug),
            lambda: shifts.exceptions_page(slug),
            lambda: shifts.timesheets_page(slug),
            lambda: shifts.set_working_days(erin, slug, {"weekdays": ["mon"]}),
            lambda: shifts.add_exception(erin, slug, {"date": "2026-11-03", "kind": "off"}),
        ):
            with pytest.raises(errors.NotFoundError):
                call()
        # The other utility's login is nobody's technician here.
        with pytest.raises(errors.NotFoundError):
            shifts.week(actor, None)
        with pytest.raises(errors.NotFoundError):
            shifts.end_shift(actor, {"key": "iso-end"})


def test_a_login_with_no_technician_profile_gets_404(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(errors.NotFoundError):
            shifts.week(dana, None)


# ── through the stack ──────────────────────────────────────────────────────

TECH = ("shifts.cr193@silvercreek.example", "T. Osei", "Prairie2026grass")


@pytest.fixture()
def tech_client(idn):
    user, _membership = idn.make_user(idn.silvercreek, TECH[0], TECH[1], password=TECH[2], role="field_technician")
    with writing_as_tenant(idn.silvercreek):
        User.objects.filter(pk=user.pk).update(surface_scope="mobile")
        work_models.Technician.objects.create(
            tenant_id=idn.silvercreek.id, user_id=user.pk, shift_start=time(7, 0), shift_end=time(15, 30)
        )
    client = Client()
    response = client.post(
        api_path("/auth/session", SC),
        data={"email": TECH[0], "password": TECH[2], "surface": "mobile"},
        content_type=JSON,
    )
    assert response.status_code == 201, response.content
    return client


def test_the_three_phone_doors_through_the_stack(tech_client):
    week = tech_client.get(api_path("/work/mobile/week?from=2026-10-26", SC))
    assert week.status_code == 200, week.content
    assert [d["date"] for d in week.json()["days"]][0] == "2026-10-26"
    ended = tech_client.post(api_path("/work/mobile/shift/end", SC), data={"key": "http-end"}, content_type=JSON)
    again = tech_client.post(api_path("/work/mobile/shift/end", SC), data={"key": "http-end"}, content_type=JSON)
    assert ended.status_code == 200 and again.json()["duplicate"] is True
    sheet = tech_client.post(
        api_path("/work/mobile/timesheet/submit", SC), data={"date": "2026-10-01", "key": "http-sheet"}, content_type=JSON
    )
    assert sheet.status_code == 200 and sheet.json()["duplicate"] is False
    missing = tech_client.post(api_path("/work/mobile/timesheet/submit", SC), data={"date": "2026-10-01"}, content_type=JSON)
    assert missing.status_code == 422 and missing.json()["message_key"] == "work.sync.item_key_required"


def test_the_office_routes_refuse_the_technician(tech_client):
    assert tech_client.get(api_path("/work/technicians/t-osei/timesheets", SC)).status_code == 403
    assert tech_client.put(api_path("/work/technicians/t-osei/working-days", SC), data={}, content_type=JSON).status_code == 403
