# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 4, lane SRV-3 — the Crews server: three lists
#           paged in SQL (P3.4), a contractor's phone and email (P3.53), a
#           technician moved between crews (P3.44), a crew's skills (P3.52),
#           add crew member (ruling 26), a technician's figures, jobs and
#           performance (P3.46, P3.45 read)
# Rules:    PO ruling 30 (three lists; BR-WRK-028's last sentence superseded) ·
#           rulings 26, 27, 28 · NFR-3 · NFR-5 · hard rules 1 and 7
# ───────────────────────────────────────────────────────
"""The Crews server, round 4. SQLite is enough here — no trigger, RLS or
aborted transaction is involved (law 14); the PostgreSQL proof of the paged
reads is the recorded answers (`10-scripts/cr168_srv3_record_shapes.py`)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import models as work_models
from apps.work import services as work_services
from apps.work import technician_figures, workforce
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import make_premises
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _tech(tenant, email, name, crew=None):
    from apps.identity import models as identity_models

    user = identity_models.User.objects.create(tenant=tenant, email=email, full_name=name)
    return work_models.Technician.objects.create(tenant=tenant, user=user, crew=crew)


def _crew(tenant, name, kind="crew", **over):
    return work_models.Crew.objects.create(tenant=tenant, name=name, kind=kind, **over)


def _world(tenant):
    a = _crew(tenant, "Field crew A")
    b = _crew(tenant, "Field crew B")
    redline = _crew(tenant, "Redline Meter Services", kind="contractor")
    ortiz = _tech(tenant, "dortiz@b.test", "D. Ortiz", crew=a)
    patel = _tech(tenant, "rpatel@b.test", "R. Patel", crew=a)
    kaur = _tech(tenant, "jkaur@b.test", "J. Kaur")
    return {"a": a, "b": b, "redline": redline, "ortiz": ortiz, "patel": patel, "kaur": kaur}


# ── P3.4 · three lists, each cut in SQL ─────────────────────────────────────


def test_p3_4_each_view_is_cut_by_limit_and_offset_in_sql(brazos, dana):
    """⚠ Red on the tip (2.500.1): the old `crews_page` read every technician
    and every crew and sliced in Python, so no query carried a LIMIT —
    ``AssertionError: no query cut the page in SQL``."""
    with tenant_ctx(brazos):
        _world(brazos)
        with CaptureQueriesContext(connection) as seen:
            page = workforce.crews_page(view="technicians", per=50)
        assert any(
            "LIMIT" in q["sql"].upper() and '"technicians"' in q["sql"] for q in seen.captured_queries
        ), "no query cut the page in SQL"
        assert [r["name"] for r in page["rows"]] == ["D. Ortiz", "J. Kaur", "R. Patel"]
        assert page["counts"]["technicians"] == 3
        assert page["counts"]["crews"] == 2
        assert page["counts"]["contractors"] == 1


def test_p3_4_a_technician_row_names_its_crew_and_a_crew_row_counts_its_members(brazos, dana):
    with tenant_ctx(brazos):
        _world(brazos)
        techs = workforce.crews_page(view="technicians")["rows"]
        crews = workforce.crews_page(view="crews")["rows"]
        contractors = workforce.crews_page(view="contractors")["rows"]
    ortiz = next(r for r in techs if r["name"] == "D. Ortiz")
    assert ortiz["crew"]["name"] == "Field crew A"
    assert next(r for r in techs if r["name"] == "J. Kaur")["crew"] is None
    assert [(r["name"], r["members"]) for r in crews] == [("Field crew A", 2), ("Field crew B", 0)]
    assert [r["name"] for r in contractors] == ["Redline Meter Services"]


def test_p3_4_no_page_size_is_a_maximum_the_201st_is_on_page_2(brazos, dana):
    """NFR-5: a list has no maximum; it pages. 51 technicians at 50 a page put
    the 51st on page 2, not nowhere."""
    with tenant_ctx(brazos):
        for n in range(51):
            _tech(brazos, f"t{n:02d}@b.test", f"Tech {n:02d}")
        first = workforce.crews_page(view="technicians", per=50, page=1)
        second = workforce.crews_page(view="technicians", per=50, page=2)
    assert first["total"] == 51 and len(first["rows"]) == 50
    assert [r["name"] for r in second["rows"]] == ["Tech 50"]


def test_p3_4_the_one_table_still_pages_across_the_boundary_between_people_and_crews(brazos, dana):
    """The legacy no-`view` answer (one round): people first, then crews, then
    contractors — and a page that straddles the boundary is cut from both."""
    with tenant_ctx(brazos):
        _world(brazos)
        everyone = workforce.crews_page(per=50)
        assert [r["name"] for r in everyone["rows"]] == [
            "D. Ortiz", "J. Kaur", "R. Patel", "Field crew A (2)", "Field crew B",
            "Redline Meter Services",
        ]
        # Per is clamped to the product's sizes (50 minimum), so the straddle is
        # proved with 52 people: page 2 holds two people and the three crew rows.
        for n in range(49):
            _tech(brazos, f"x{n:02d}@b.test", f"X {n:02d}")
        second = workforce.crews_page(per=50, page=2)
    assert [r["kind"] for r in second["rows"]] == ["person", "person", "crew", "crew", "contractor"]


def test_p3_4_search_matches_a_skill_and_a_crew_and_the_page_count_follows_it(brazos, dana):
    with tenant_ctx(brazos):
        w = _world(brazos)
        skill = work_models.WorkSkill.objects.create(tenant=brazos, code="W1", name="Water I")
        work_models.TechnicianSkill.objects.create(tenant=brazos, technician=w["kaur"], skill=skill)
        page = workforce.crews_page(view="technicians", q="Water")
        by_crew = workforce.crews_page(view="technicians", q="crew A")
    assert [r["name"] for r in page["rows"]] == ["J. Kaur"]
    # The PAGE's count follows the search; the three tab badges count the
    # utility (⚠ this read `counts["technicians"] == 1` until 2026-10-04 — the
    # badges followed the search and read *Crews 0* while searching *Sam*; lane
    # CREWS reported it, lane SRV-4 changed it, `test_cr168_srv4_crews.py`).
    assert page["total"] == 1
    assert page["counts"]["technicians"] == 3
    assert {r["name"] for r in by_crew["rows"]} == {"D. Ortiz", "R. Patel"}


def test_p3_4_an_unknown_view_is_refused_by_name(brazos, dana):
    with tenant_ctx(brazos), pytest.raises(errors.ValidationError) as caught:
        workforce.crews_page(view="people")
    assert caught.value.message_key == "work.crews.view_unknown"


def test_p3_4_the_other_utility_sees_none_of_these_rows(brazos, lonestar, dana):
    with tenant_ctx(brazos):
        _world(brazos)
    with tenant_ctx(lonestar):
        page = workforce.crews_page(view="crews")
    assert page["total"] == 0 and page["counts"] == {
        "technicians": 0, "crews": 0, "contractors": 0, "rows": 0, "people": 0,
    }


# ── P3.53 · a contractor's phone and email ──────────────────────────────────


def test_p3_53_a_contractor_carries_a_phone_and_an_email(brazos, dana):
    with tenant_ctx(brazos):
        made = workforce.create_crew(
            dana,
            {"name": "Redline Meter Services", "kind": "contractor",
             "phone": "(512) 555-0199", "email": "dispatch@redline.example"},
        )
        row = workforce.crews_page(view="contractors")["rows"][0]
    assert made["phone"] == "(512) 555-0199"
    assert row["email"] == "dispatch@redline.example"


def test_p3_53_a_crew_with_a_phone_is_refused_by_name(brazos, dana):
    with tenant_ctx(brazos), pytest.raises(errors.ValidationError) as caught:
        workforce.create_crew(dana, {"name": "Field crew C", "kind": "crew", "phone": "555"})
    assert caught.value.message_key == "work.crew.contact_contractor_only"


# ── P3.44 · move a technician; members are counted ─────────────────────────


def test_p3_44_ortiz_moved_to_field_crew_b_field_crew_a_reads_one(brazos, dana):
    """The blueprint's own figure: *D. Ortiz moved to Field crew B; Field crew A
    reads (1)*."""
    with tenant_ctx(brazos):
        w = _world(brazos)
        workforce.move_technician(dana, w["ortiz"].id, w["b"].id)
        crews = {r["name"]: r["members"] for r in workforce.crews_page(view="crews")["rows"]}
        detail = workforce.technician_by_slug("d-ortiz")
    assert crews == {"Field crew A": 1, "Field crew B": 1}
    assert detail["crew"] == {"id": str(w["b"].id), "name": "Field crew B"}


def test_p3_44_a_crew_from_another_utility_is_refused(brazos, lonestar, dana):
    with tenant_ctx(lonestar):
        theirs = _crew(lonestar, "Their crew")
    with tenant_ctx(brazos):
        w = _world(brazos)
        with pytest.raises(errors.ValidationError) as caught:
            workforce.move_technician(dana, w["ortiz"].id, theirs.id)
    assert caught.value.message_key == "work.crew.unknown"


# ── P3.52 · a crew's skills ─────────────────────────────────────────────────


def test_p3_52_field_crew_c_saved_with_water_i_is_offered_for_a_water_i_job(brazos, dana):
    with tenant_ctx(brazos):
        crew_c = _crew(brazos, "Field crew C")
        water = work_models.WorkSkill.objects.create(tenant=brazos, code="W1", name="Water I")
        dig = work_models.WorkSkill.objects.create(tenant=brazos, code="EXC", name="Excavation")
        out = workforce.set_crew_skills(
            dana, crew_c.id,
            {"skills": [{"skill_id": str(water.id)}, {"skill_id": str(dig.id), "proficiency": "certified"}]},
        )
        match = workforce.skill_match(skill_id=water.id)
    assert {s["name"] for s in out["skills"]} == {"Water I", "Excavation"}
    assert "Field crew C" in {row["name"] for row in match["candidates"]}


# ── ruling 26 · add crew member ─────────────────────────────────────────────


def test_ruling_26_add_a_member_by_technician_and_by_login(brazos, dana):
    from apps.identity import models as identity_models

    with tenant_ctx(brazos):
        w = _world(brazos)
        workforce.add_crew_member(dana, w["b"].id, {"technician_id": str(w["kaur"].id)})
        login = identity_models.User.objects.create(tenant=brazos, email="new@b.test", full_name="N. Ew")
        out = workforce.add_crew_member(dana, w["b"].id, {"user_id": str(login.id)})
    assert out["members"] == 2


def test_ruling_26_a_contractors_people_are_not_added_here(brazos, dana):
    with tenant_ctx(brazos):
        w = _world(brazos)
        with pytest.raises(errors.ValidationError) as caught:
            workforce.add_crew_member(dana, w["redline"].id, {"technician_id": str(w["kaur"].id)})
    assert caught.value.message_key == "work.crew.members_crew_only"


# ── P3.46 · a technician's figures; P3.45 · their jobs ─────────────────────


def _finished(actor, tech, *, minutes_site, est, on_time, address):
    premises = make_premises(actor, address_line=address, services_available=["water"])
    raised = w6.create_work_order(
        actor, None, {"type": "Leak investigation", "service": "water", "premises_id": premises["id"]}
    )
    order = work_tables.WorkOrder.objects.get(pk=raised["id"])
    now = timezone.now()
    order.assignee_technician = tech
    order.state = work_tables.WO_COMPLETED
    order.completed_at = now
    order.due_at = now + timedelta(hours=1) if on_time else now - timedelta(hours=1)
    order.minutes_on_site = minutes_site
    order.est_duration = timedelta(minutes=est)
    order.save()
    return order


def test_p3_46_ortiz_two_closed_one_of_two_on_time_all_at_the_first_visit(brazos, dana):
    """The blueprint's own figure: *D. Ortiz: 2 closed, 1 of 2 on time, 100% at
    the first visit*. Against estimate: 34 + 42 minutes on site against 38 + 38
    planned is +0 min and 0.0%."""
    with tenant_ctx(brazos):
        work_services.seed_reference_list("work_priorities", [], "test")
        w = _world(brazos)
        _finished(dana, w["ortiz"], minutes_site=34, est=38, on_time=True, address="1 Elm St")
        _finished(dana, w["ortiz"], minutes_site=42, est=38, on_time=False, address="2 Elm St")
        detail = workforce.technician_by_slug("d-ortiz")
    month = detail["this_month"]
    assert (month["closed"], month["on_time"], month["on_time_of"]) == (2, 1, 2)
    assert month["first_visit_pct"] == "100.0"
    assert month["vs_estimate_pct"] == "0.0" and month["vs_estimate_minutes"] == 0
    assert detail["today"]["jobs"] == 0
    assert "utilisation" not in detail


def test_p3_46_performance_for_one_person_pages_its_job_types(brazos, dana):
    with tenant_ctx(brazos):
        work_services.seed_reference_list("work_priorities", [], "test")
        w = _world(brazos)
        _finished(dana, w["ortiz"], minutes_site=30, est=38, on_time=True, address="1 Elm St")
        _finished(dana, w["patel"], minutes_site=30, est=38, on_time=True, address="2 Elm St")
        out = technician_figures.performance("d-ortiz")
    assert out["tiles"]["closed"] == 1
    assert out["total"] == 1 and out["rows"][0]["volume"] == 1
    assert out["rows"][0]["vs_estimate_minutes"] == -8


def test_p3_45_a_job_moved_away_stays_on_the_first_holders_list(brazos, dana):
    from apps.work import dispatch

    with tenant_ctx(brazos):
        work_services.seed_reference_list("work_priorities", [], "test")
        work_services.seed_reference_list("work_order_types", [], "test")
        w = _world(brazos)
        premises = make_premises(dana, address_line="9 Oak St", services_available=["water"])
        raised = w6.create_work_order(
            dana, None, {"type": "Leak investigation", "service": "water", "premises_id": premises["id"]}
        )
        dispatch.record_act(dana, raised["id"], {"act": "assign", "technician_id": str(w["ortiz"].id)})
        dispatch.record_act(
            dana, raised["id"],
            {"act": "reassign", "technician_id": str(w["patel"].id), "reason": "Ortiz is off"},
        )
        ortiz_jobs = technician_figures.jobs_page("d-ortiz")
        patel_jobs = technician_figures.jobs_page("r-patel", state="open")
        done = technician_figures.jobs_page("d-ortiz", state="done")
    assert [r["still_holds"] for r in ortiz_jobs["rows"]] == [False]
    assert [r["still_holds"] for r in patel_jobs["rows"]] == [True]
    assert done["total"] == 0


def test_p3_46_the_wave_g_hold_is_gone():
    """`UNSERVED_UNTIL_WAVE_G` declared the figures unservable a month after
    wave G landed the column that serves them (law 2's mirror)."""
    assert not hasattr(workforce, "UNSERVED_UNTIL_WAVE_G")
