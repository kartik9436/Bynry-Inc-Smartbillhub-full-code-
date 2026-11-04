# ── Trace ──────────────────────────────────────────────
# Change:   FB-033 — availability from the phone reaches the office (decision
#           log 2026-10-31, D1–D4) · DEF-FLD-10799
# Rules:    D1 (Off duty warns, assign allowed) · D2 (On break warns) · D3
#           (held jobs stay) · D4 (Off duty and End shift separate) · office
#           Unavailable wins · a late tap never overwrites a newer change ·
#           hard rules 1, 6, 7
# Code:     apps/work/availability.py · availability_models.py · advice.py ·
#           workforce.py · shifts.py · shifts_api.py
# ───────────────────────────────────────────────────────
"""What the technician says on the phone reaches the office."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from unittest import mock

import pytest
from django.test import Client
from django.utils import timezone

from apps.identity.models import User
from apps.work import advice, availability, dispatch, shifts, workforce
from apps.work import models as work_models
from apps.work.availability_models import TechnicianAvailabilityChange
from core import errors

from tests.isolation_helpers import writing_as_tenant
from apps.work import connection_models as work_tables
from tests.test_cr168_srv2_assign import _reference, _skilled_order
from tests.test_cr187_order_helpers import person
from tests.test_us_idn_helpers import (  # noqa: F401 — fixture used by name
    JSON,
    SC,
    api_path,
    idn,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin · audit_rows
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

WED = date(2026, 10, 28)


def _at(day: date, hh: int, mm: int = 0) -> datetime:
    return datetime.combine(day, time(hh, mm), tzinfo=shifts._tz())


def _dana_tech(tenant):
    tech, actor = person(tenant, "dana.field@field.test", "Dana Field")
    work_models.Technician.objects.filter(pk=tech.id).update(shift_start=time(7, 0), shift_end=time(15, 30))
    tech.refresh_from_db()
    return tech, actor


def _changes(rows, action=availability.ACTION):
    return [r for r in rows if r["action"] == action]


# ── each value ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("value", "status"),
    [("available", "on_shift"), ("on_break", "on_break"), ("off_duty", "off_duty")],
)
def test_each_value_sets_status_since_one_history_and_one_audit_row(brazos, audit_rows, value, status):
    with tenant_ctx(brazos):
        tech, actor = _dana_tech(brazos)
        tapped = _at(WED, 15, 30)
        out = availability.record(actor, {"key": f"av-{value}", "at": tapped.isoformat(), "value": value}, now=_at(WED, 15, 31))
        tech.refresh_from_db()
        history = list(TechnicianAvailabilityChange.objects.filter(technician_id=tech.id))
    assert out["applied"] is True and out["duplicate"] is False
    assert tech.status == status and tech.status_since == tapped
    assert datetime.fromisoformat(out["status_since"]) == tapped
    assert len(history) == 1 and history[0].value == value and history[0].at == tapped
    rows = _changes(audit_rows)
    assert len(rows) == 1 and rows[0]["after"]["status"] == status and rows[0]["after"]["applied"] is True


def test_the_same_key_twice_records_once(brazos, audit_rows):
    with tenant_ctx(brazos):
        tech, actor = _dana_tech(brazos)
        body = {"key": "av-1", "at": _at(WED, 10, 42).isoformat(), "value": "on_break"}
        first = availability.record(actor, body, now=_at(WED, 10, 43))
        again = availability.record(actor, body, now=_at(WED, 11, 0))
        count = TechnicianAvailabilityChange.objects.filter(technician_id=tech.id).count()
    assert first["duplicate"] is False and again["duplicate"] is True
    assert again["at"] == first["at"]
    assert count == 1 and len(_changes(audit_rows)) == 1


def test_a_future_time_is_refused(brazos):
    with tenant_ctx(brazos):
        _tech, actor = _dana_tech(brazos)
        with pytest.raises(errors.ValidationError) as future:
            availability.record(actor, {"key": "av-f", "at": _at(WED, 12).isoformat(), "value": "off_duty"}, now=_at(WED, 11))
        with pytest.raises(errors.ValidationError) as unknown:
            availability.record(actor, {"key": "av-u", "value": "sleeping"}, now=_at(WED, 11))
        with pytest.raises(errors.ValidationError) as no_key:
            availability.record(actor, {"value": "off_duty"}, now=_at(WED, 11))
        stored = TechnicianAvailabilityChange.objects.count()
    assert future.value.message_key == "work.availability.future_time"
    assert unknown.value.message_key == "work.technician_status_unknown"
    assert no_key.value.message_key == "work.sync.item_key_required"
    assert stored == 0


def test_an_older_offline_tap_never_overwrites_a_newer_office_change(brazos, dana, audit_rows):
    """On break pressed at 10:42 with no signal; the office sets the status at
    11:00; the tap arrives at 11:20 → recorded, status untouched."""
    with tenant_ctx(brazos):
        tech, actor = _dana_tech(brazos)
        with mock.patch.object(timezone, "now", return_value=_at(WED, 11, 0)):
            workforce.set_unavailable(dana, tech.id, {"status": "off_today"})
        out = availability.record(actor, {"key": "late", "at": _at(WED, 10, 42).isoformat(), "value": "on_break"}, now=_at(WED, 11, 20))
        tech.refresh_from_db()
        row = TechnicianAvailabilityChange.objects.get(key="late")
        office_at, tap_at = _at(WED, 11, 0), _at(WED, 10, 42)
    assert out["applied"] is False and out["not_applied_reason"] == "newer_change"
    assert tech.status == "off_today" and tech.status_since == office_at
    assert row.applied is False and row.at == tap_at
    assert len(_changes(audit_rows)) == 1  # the tap is still on the record


def test_an_office_unavailable_stays_whatever_the_phone_says(brazos, dana):
    with tenant_ctx(brazos):
        tech, actor = _dana_tech(brazos)
        with mock.patch.object(timezone, "now", return_value=_at(WED, 9, 0)):
            workforce.set_unavailable(dana, tech.id, {"reason": "Van in the shop"})
        out = availability.record(actor, {"key": "after", "at": _at(WED, 14, 5).isoformat(), "value": "available"}, now=_at(WED, 14, 6))
        tech.refresh_from_db()
        read_back = availability.current(actor)
    assert out["applied"] is False and out["not_applied_reason"] == "office_unavailable"
    assert tech.status == "unavailable"
    assert read_back["status"] == "unavailable"


def test_the_office_cannot_set_on_break_or_off_duty_by_hand(brazos, dana):
    with tenant_ctx(brazos):
        tech, _actor = _dana_tech(brazos)
        with pytest.raises(errors.ValidationError) as refused:
            workforce.set_unavailable(dana, tech.id, {"status": "off_duty"})
    assert refused.value.message_key == "work.technician_status_unknown"


def test_off_duty_and_end_shift_stay_separate_records(brazos):
    """D4 = B: Off duty at 15:30 then End shift at 17:02 → status off_today
    since 17:02; both facts in their own tables. Off duty after End shift is
    recorded and does not replace it; Available after it does."""
    with tenant_ctx(brazos):
        tech, actor = _dana_tech(brazos)
        availability.record(actor, {"key": "off", "at": _at(WED, 15, 30).isoformat(), "value": "off_duty"}, now=_at(WED, 15, 31))
        shifts.end_shift(actor, {"key": "end", "at": _at(WED, 17, 2).isoformat()}, now=_at(WED, 17, 3))
        tech.refresh_from_db()
        after_end = (tech.status, tech.status_since)
        again = availability.record(actor, {"key": "off2", "at": _at(WED, 17, 10).isoformat(), "value": "off_duty"}, now=_at(WED, 17, 11))
        back = availability.record(actor, {"key": "back", "at": _at(WED, 18, 0).isoformat(), "value": "available"}, now=_at(WED, 18, 1))
        tech.refresh_from_db()
        pressed = _at(WED, 17, 2)
    assert after_end == ("off_today", pressed)
    assert again["applied"] is False and again["not_applied_reason"] == "shift_ended"
    assert back["applied"] is True and tech.status == "on_shift"


def test_off_duty_from_yesterday_returns_on_shift_next_working_morning(brazos):
    with tenant_ctx(brazos):
        tech, actor = _dana_tech(brazos)
        availability.record(actor, {"key": "off", "at": _at(WED, 15, 30).isoformat(), "value": "off_duty"}, now=_at(WED, 15, 31))
        same_day = shifts.morning_return(now=_at(WED, 20, 0))
        tech.refresh_from_db()
        still = tech.status
        next_day = shifts.morning_return(now=_at(WED + timedelta(days=1), 6, 5))
        tech.refresh_from_db()
    assert still == "off_duty" and same_day["returned"] == 0
    assert next_day["returned"] == 1 and tech.status == "on_shift"


# ── the office: Crews, the technician page, the picker ─────────────────────


def test_crews_and_the_technician_page_carry_the_since_time(brazos):
    with tenant_ctx(brazos):
        tech, actor = _dana_tech(brazos)
        availability.record(actor, {"key": "brk", "at": _at(WED, 10, 42).isoformat(), "value": "on_break"}, now=_at(WED, 10, 43))
        row = work_models.Technician.objects.select_related("user", "crew").get(pk=tech.id)
        detail = workforce.technician_detail(row)
        ender, ender_actor = person(brazos, "m.ends@field.test", "M. Ends")
        shifts.end_shift(ender_actor, {"key": "end-m", "at": _at(WED, 17, 2).isoformat()}, now=_at(WED, 17, 3))
        rows = {r["id"]: r for r in workforce.crews_page(view="technicians", per=50)["rows"]}
    assert detail["status"] == "on_break" and detail["shift_ended"] is False
    assert detail["status_since"][11:16] == "10:42"
    assert rows[str(tech.id)]["status"] == "on_break" and rows[str(tech.id)]["status_since"][11:16] == "10:42"
    ended = rows[str(ender.id)]
    assert (ended["status"], ended["shift_ended"], ended["status_since"][11:16]) == ("off_today", True, "17:02")


def test_the_picker_warns_off_duty_and_on_break_and_still_offers_both(brazos, dana):
    """D1: Off duty at 16:10, a job for tomorrow → red Off duty, assignment
    accepted. D2: On break → a warning only."""
    with tenant_ctx(brazos):
        off_tech, off_actor = _dana_tech(brazos)
        brk_tech, brk_actor = person(brazos, "m.chen@field.test", "M. Chen")
        today = advice._local_today()
        now = timezone.now()
        availability.record(off_actor, {"key": "o", "at": (now - timedelta(minutes=5)).isoformat(), "value": "off_duty"})
        availability.record(brk_actor, {"key": "b", "at": (now - timedelta(minutes=5)).isoformat(), "value": "on_break"})
        rows = {r["id"]: r for r in advice.candidates_page(on=today + timedelta(days=1), per=50)["rows"]}
        today_rows = {r["id"]: r for r in advice.candidates_page(on=today, per=50)["rows"]}
        _reference()
        raised, _skill, _ = _skilled_order(dana, brazos)
        out = dispatch.record_act(dana, raised["id"], {"act": "assign", "technician_id": str(off_tech.id)})
        held = work_tables.WorkOrder.objects.get(pk=raised["id"]).assignee_technician_id
    off_advice = rows[str(off_tech.id)]["advice"]
    assert off_advice["availability"]["status"] == "off_duty"
    assert rows[str(brk_tech.id)]["advice"]["availability"]["status"] == "on_break"
    assert today_rows[str(off_tech.id)]["advice"]["off_that_day"] is True
    assert today_rows[str(brk_tech.id)]["advice"]["off_that_day"] is False
    assert out["against_advice"] is None or "missing_skill" in out["against_advice"]
    assert held == off_tech.id  # D1: warned, and allowed


def test_advice_asks_about_the_utilitys_today_not_the_servers(brazos):
    """From 19:00 in a UTC−5 utility it is already tomorrow on the server."""
    with tenant_ctx(brazos):
        tech, actor = _dana_tech(brazos)
        evening = _at(WED, 22, 30)
        shifts.end_shift(actor, {"key": "end", "at": evening.isoformat()}, now=evening)
        with mock.patch.object(timezone, "now", return_value=evening):
            rows = {r["id"]: r for r in advice.candidates_page(per=50)["rows"]}
            assert advice._local_today() == WED
    assert rows[str(tech.id)]["advice"]["off_that_day"] is True


def test_another_utility_cannot_see_or_change_this_technician(brazos, lonestar):
    with tenant_ctx(brazos):
        tech, actor = _dana_tech(brazos)
        availability.record(actor, {"key": "mine", "value": "off_duty"})
    with tenant_ctx(lonestar):
        seen = TechnicianAvailabilityChange.objects.filter(tenant_id=lonestar.id).count()
        with pytest.raises(errors.NotFoundError):
            availability.record(actor, {"key": "theirs", "value": "available"})
    assert seen == 0


# ── through the stack ──────────────────────────────────────────────────────

TECH = ("avail.fb033@silvercreek.example", "T. Osei", "Prairie2026grass")


@pytest.fixture()
def tech_client(idn):
    user, _membership = idn.make_user(idn.silvercreek, TECH[0], TECH[1], password=TECH[2], role="field_technician")
    with writing_as_tenant(idn.silvercreek):
        User.objects.filter(pk=user.pk).update(surface_scope="mobile")
        work_models.Technician.objects.create(tenant_id=idn.silvercreek.id, user_id=user.pk)
    client = Client()
    response = client.post(
        api_path("/auth/session", SC),
        data={"email": TECH[0], "password": TECH[2], "surface": "mobile"},
        content_type=JSON,
    )
    assert response.status_code == 201, response.content
    return client


def test_the_phone_door_through_the_stack(tech_client):
    sent = tech_client.post(api_path("/work/mobile/availability", SC), data={"key": "h1", "value": "on_break"}, content_type=JSON)
    again = tech_client.post(api_path("/work/mobile/availability", SC), data={"key": "h1", "value": "on_break"}, content_type=JSON)
    read = tech_client.get(api_path("/work/mobile/availability", SC))
    assert sent.status_code == 200, sent.content
    assert sent.json()["applied"] is True and again.json()["duplicate"] is True
    assert read.status_code == 200 and read.json()["status"] == "on_break" and read.json()["status_since"]
