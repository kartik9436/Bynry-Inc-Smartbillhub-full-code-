# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-073 (EP-CWP-12) — tips: one slot, in season, and the page
#           closes up when there is none. Screens: CWP-073 · CWP-062
# Rules:    BR-CWP-095 (ON **and** in season; one per screen; top of the list
#           breaks the tie; no page of tips and no way to browse them) ·
#           BR-CWP-093 (no live tip ⇒ no slot in the DOM)
# Defect:   DEF-CWP-3820 — nothing on CWP-073 could reach `create_tip`,
#           `update_tip` or `delete_tip`; the editor built to close it reads
#           its *Where it shows* picker from `all_screens`, asserted below
# Tests:    this file — TC-1 (six written, four showing), TC-2 (Jun–Sep on 2
#           Sep, gone on 1 Oct with no edit), TC-3 negative (off AND out of
#           season, two reasons), TC-4 negative (two matching one screen → ONE
#           renders), TC-5 negative (no browse route), TC-7 negative (thirty
#           words accepted and flagged), TC-8 isolation, TC-9 (reorder moves
#           the tie-break)
# Impacts:  apps/tenancy/published_content.py · apps/portal/guest_api.py
# ───────────────────────────────────────────────────────
"""US-CWP-073. ⚠ The season cases pin the clock with `PORTAL_CLOCK_OVERRIDE`
under `DEBUG` — the only way to see a rule whose whole point is that it works
without anybody editing anything."""

import pytest
from django.test import override_settings

from apps.portal import guest_api
from apps.tenancy import published_content, published_content_api, published_content_sample
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_ten_helpers import api_call


@pytest.fixture()
def pine_content(pine_hill, sarah):
    with tenant_context(pine_hill.id):
        published_content_sample.seed_published_content(pine_hill.id)
    return pine_hill


def _pin(when):
    """A day, honoured only because the test settings leave `DEBUG` alone and
    this decorator turns it on for the case."""
    return override_settings(DEBUG=True, PORTAL_CLOCK_OVERRIDE=when)


@pytest.mark.django_db
def test_tc1_six_tips_and_on_a_november_wednesday_four_are_showing(pine_content, sarah):
    with _pin("2026-11-18T10:00:00"), tenant_context(pine_content.id):
        rows = published_content.back_office_tips(pine_content.id)
    assert len(rows) == 6
    showing = [row for row in rows if row["showing_today"]]
    assert len(showing) == 4
    quiet = [row for row in rows if not row["showing_today"]]
    # ⚠ NEITHER OMISSION IS A FAULT, and each says why it is quiet.
    assert {row["text"] for row in quiet} == {
        "Watering before 10am loses less to evaporation.",
        "Leave a tap dripping overnight when it freezes.",
    }


@pytest.mark.django_db
def test_tc2_the_watering_tip_appears_in_september_and_is_gone_on_1_october(pine_content):
    def tip_on_usage():
        return api_call(
            guest_api.tips,
            "get",
            f"/api/{pine_content.subdomain}/portal/public/tips",
            tenant=pine_content,
            query={"screen": "usage"},
        ).data["tip"]

    with _pin("2026-09-02T09:00:00"):
        september = tip_on_usage()
    assert september is not None
    assert september["text"] == "Watering before 10am loses less to evaporation."
    # ⚠ NOBODY EDITED ANYTHING BETWEEN THESE TWO LINES.
    with _pin("2026-10-01T09:00:00"):
        october = tip_on_usage()
    assert october is None


@pytest.mark.django_db
def test_tc3_the_freeze_tip_is_quiet_for_two_independent_reasons_and_the_home_has_no_container(
    pine_content,
):
    """⚠ NEGATIVE. Off **and** Dec–Feb: turning it on in September would still
    show nothing, and being in season in January would still show nothing."""
    with _pin("2026-09-04T09:00:00"), tenant_context(pine_content.id):
        rows = {row["text"]: row for row in published_content.back_office_tips(pine_content.id)}
        freeze = rows["Leave a tap dripping overnight when it freezes."]
        assert freeze["is_on"] is False
        assert freeze["in_season"] is False
        assert freeze["showing_today"] is False
        # And in January, when it IS in season, the switch still holds it.
    with _pin("2027-01-10T09:00:00"), tenant_context(pine_content.id):
        rows = {row["text"]: row for row in published_content.back_office_tips(pine_content.id)}
        freeze = rows["Leave a tap dripping overnight when it freezes."]
        assert freeze["in_season"] is True
        assert freeze["showing_today"] is False
    body = api_call(
        guest_api.tips,
        "get",
        f"/api/{pine_content.subdomain}/portal/public/tips",
        tenant=pine_content,
        query={"screen": "portal_home"},
    ).data
    # ⚠ AN EMPTY TIP RESPONSE IS A NORMAL RESPONSE — 200, `tip: null`, and the
    # screen draws no container at all (BR-CWP-093, BR-CWP-095).
    assert body == {"tip": None}


@pytest.mark.django_db
def test_tc4_two_tips_matching_one_screen_render_exactly_one_the_top_of_the_list(
    pine_content, sarah
):
    """⚠ NEGATIVE. Assert EXACTLY one, not *at least* one."""
    with tenant_context(pine_content.id):
        published_content.create_tip(
            sarah,
            pine_content.id,
            {"text": "Check the meter box for standing water.", "target_screen": "usage"},
        )
    with _pin("2026-09-04T09:00:00"), tenant_context(pine_content.id):
        chosen = published_content.tip_for_screen(pine_content.id, "usage")
        both = [
            row
            for row in published_content.back_office_tips(pine_content.id)
            if row["target_screen"] == "usage" and row["showing_today"]
        ]
    assert len(both) == 2  # two are eligible …
    assert chosen["text"] == "Watering before 10am loses less to evaporation."  # … one renders


@pytest.mark.django_db
def test_tc5_there_is_no_page_of_tips_and_no_route_to_browse_them(pine_content):
    """⚠ NEGATIVE. *"A tip the customer went looking for would be an answer."*
    The guest surface offers exactly one tip route and it requires a screen."""
    from django.urls import Resolver404, resolve

    for path in (
        f"/api/{pine_content.subdomain}/portal/public/tips/all",
        f"/api/{pine_content.subdomain}/portal/public/tips/list",
    ):
        with pytest.raises(Resolver404):
            resolve(path)
    # And the one route that exists answers nothing without a screen named.
    body = api_call(
        guest_api.tips,
        "get",
        f"/api/{pine_content.subdomain}/portal/public/tips",
        tenant=pine_content,
    ).data
    assert body == {"tip": None}


@pytest.mark.django_db
def test_tc7_a_thirty_word_tip_is_accepted_and_flagged_against_the_guidance(pine_content, sarah):
    """⚠ NEGATIVE, and the interesting half is that it is NOT refused: the rule
    is on the screen, not in a policy document and not in a CHECK constraint."""
    long_tip = " ".join(["word"] * 30)
    with tenant_context(pine_content.id):
        rows = published_content.create_tip(
            sarah, pine_content.id, {"text": long_tip, "target_screen": "overdue"}
        )
    written = next(row for row in rows if row["text"] == long_tip)
    assert written["word_count"] == 30
    assert written["word_guidance"] == 15


@pytest.mark.django_db
def test_tc8_isolation_oak_ridge_sees_only_its_own_tips(pine_content, oak_ridge, elena):
    with tenant_context(oak_ridge.id):
        published_content_sample.seed_oak_ridge_content(oak_ridge.id)
        rows = published_content.back_office_tips(oak_ridge.id)
    assert [row["text"] for row in rows] == ["Check the outside tap before the first frost."]


@pytest.mark.django_db
def test_tc9_reordering_moves_the_tie_break_on_a_shared_screen(pine_content, sarah):
    with tenant_context(pine_content.id):
        published_content.create_tip(
            sarah,
            pine_content.id,
            {"text": "Check the meter box for standing water.", "target_screen": "usage"},
        )
        rows = published_content.back_office_tips(pine_content.id)
        ids = [row["id"] for row in rows]
        newest = ids[-1]
        published_content.reorder_tips(
            sarah, pine_content.id, [newest, *[i for i in ids if i != newest]]
        )
    with _pin("2026-09-04T09:00:00"), tenant_context(pine_content.id):
        chosen = published_content.tip_for_screen(pine_content.id, "usage")
    assert chosen["text"] == "Check the meter box for standing water."


@pytest.mark.django_db
def test_the_six_screens_and_the_guidance_travel_WITH_the_list(pine_content, sarah):
    """⚠ **THE EDITOR'S PICKER READS `all_screens` FROM HERE, AND THAT IS THE
    WHOLE POINT** (`DEF-CWP-3820`).

    CLAUDE.md's first paragraph is one story: an eleventh service exists in the
    database, is served by the API, passes `tsc` and every test — and never
    appears on the sign-up screen, because the front end types that list out by
    hand. `TIP_SCREENS` is a closed set on the same kind of screen, so a seventh
    tip screen must arrive on the picker WITHOUT anybody editing React. This
    asserts the transport, not the constant: adding a screen and forgetting this
    response would go red here.
    """
    answered = api_call(
        published_content_api.tips,
        "get",
        f"/api/{pine_content.subdomain}/settings/portal/tips",
        user=sarah.user,
        role=sarah.role,
        tenant=pine_content,
    )
    assert answered.status_code == 200
    body = answered.data
    assert body["all_screens"] == list(published_content.TIP_SCREENS)
    assert len(body["all_screens"]) == 6
    # The fifteen-word guidance the editor flags against is the SERVER's number,
    # so the flag a clerk sees while typing and the flag on the saved row cannot
    # come from two different fifteens.
    assert body["word_guidance"] == 15
    assert body["tips"][0]["word_guidance"] == body["word_guidance"]


@pytest.mark.django_db
def test_the_back_office_list_is_a_staff_door_and_the_clerk_is_refused(pine_content, pine_clerk):
    refused = api_call(
        published_content_api.tips,
        "get",
        f"/api/{pine_content.subdomain}/settings/portal/tips",
        user=pine_clerk.user,
        role=pine_clerk.role,
        tenant=pine_content,
    )
    assert refused.status_code == 403
