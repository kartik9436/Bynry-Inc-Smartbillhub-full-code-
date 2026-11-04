# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-074 (EP-CWP-12) — service centres, and *hidden* is a state,
#           not a deletion. Screens: CWP-074 · CWP-075 · CWP-013 · CWP-014
# Rules:    BR-CWP-096 (`is_shown_to_customers = false` is a REAL STATE;
#           holiday closures come from the tenant's existing calendar, typed by
#           nobody) · BR-CWP-093 (no centre shown ⇒ no visit page and no header
#           link) · what a centre CANNOT do is shown, not omitted
# Tests:    this file — TC-1 (three, one hidden, two public), TC-2 (Wednesday →
#           *opens Thursday at 9:00am*, computed), TC-3 (Thanksgiving closes
#           both with nobody editing), TC-4 negative (four of five rows say
#           no), TC-5 negative (hide every centre → the page 404s), TC-6 (what
#           each takes), TC-7 isolation, TC-8 (reorder), TC-9 negative (remove
#           is the danger act and hiding is what a clerk should reach for)
# Impacts:  apps/tenancy/published_content.py · apps/portal/guest_api.py
# ───────────────────────────────────────────────────────
"""US-CWP-074. The clock cases pin `PORTAL_CLOCK_OVERRIDE` under `DEBUG`."""

import pytest
from django.test import override_settings

from apps.tenancy import published_content, published_content_api, published_content_sample
from apps.tenancy import published_content_models as content
from core import errors
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_ten_helpers import api_call


@pytest.fixture()
def pine_content(pine_hill, sarah):
    with tenant_context(pine_hill.id):
        published_content_sample.seed_published_content(pine_hill.id)
    return pine_hill


def _pin(when):
    return override_settings(DEBUG=True, PORTAL_CLOCK_OVERRIDE=when)


@pytest.mark.django_db
def test_tc1_three_centres_one_hidden_and_the_public_page_shows_two(pine_content, sarah):
    with _pin("2026-11-18T10:00:00"), tenant_context(pine_content.id):
        back_office = published_content.back_office_centres(pine_content.id)
        public = published_content.public_centres(pine_content.id)
    assert len(back_office) == 3
    assert len(public) == 2
    # ⚠ THE DEPOT IS ABSENT FROM ONE AND STILL IN THE OTHER. That is the rule.
    assert "Depot" in [row["name"] for row in back_office]
    assert "Depot" not in [row["name"] for row in public]
    depot = next(row for row in back_office if row["name"] == "Depot")
    assert depot["is_shown_to_customers"] is False


@pytest.mark.django_db
def test_tc2_on_a_wednesday_the_north_counter_opens_thursday_at_nine(pine_content):
    """⚠ COMPUTED FROM THE CLOCK, never typed. The drawing `CWP-014.png` says
    *Tuesday* and a screen showing Tuesday on a Wednesday has typed the day
    (`DEF-CWP-3604`, 2026-09-03) — so this asserts the weekday NUMBER the
    server derived, which no copy-and-paste can produce."""
    with _pin("2026-11-18T10:00:00"), tenant_context(pine_content.id):  # a Wednesday
        centre = published_content.public_centre(pine_content.id, "north-counter")
    today = centre["today"]
    assert today["is_open_now"] is False
    assert today["opens_later_today"] is False
    assert today["next_open_weekday"] == 3  # Thursday, Monday=0
    assert today["next_open_at"] == "09:00"
    assert today["next_open_date"] == "2026-11-19"
    assert today["next_open_is_today"] is False
    # ⚠ AND NO SENTENCE TRAVELLED (B14 rule 35): the payload carries facts.
    assert "Thursday" not in str(centre)
    assert "Closed today" not in str(centre)


@pytest.mark.django_db
def test_tc2b_on_a_thursday_morning_it_opens_later_today_and_then_is_open(pine_content):
    with _pin("2026-11-19T08:00:00"), tenant_context(pine_content.id):
        early = published_content.public_centre(pine_content.id, "north-counter")["today"]
    assert early["is_open_now"] is False and early["opens_later_today"] is True
    assert early["next_open_is_today"] is True and early["next_open_at"] == "09:00"
    with _pin("2026-11-19T10:00:00"), tenant_context(pine_content.id):
        midday = published_content.public_centre(pine_content.id, "north-counter")["today"]
    assert midday["is_open_now"] is True and midday["closes_at"] == "13:00"


@pytest.mark.django_db
def test_tc3_thanksgiving_closes_both_centres_and_nobody_edited_the_page(pine_content):
    """⚠ 26 November is in `holiday_calendars` and in NO centre's hours. The
    main office opens Mon–Fri and would otherwise be open on a Thursday."""
    from apps.tenancy import models as tenancy_models

    with tenant_context(pine_content.id):
        # ⚠ THE CLOSURE IS IN NO CENTRE'S HOURS. Three centres × seven days =
        # twenty-one rows, every one of them a WEEKDAY pattern; nothing in this
        # table can name 26 November at all.
        assert content.ServiceCentreHour.objects.filter(tenant_id=pine_content.id).count() == 21
        # It is one row of the list Reference data already keeps.
        assert (
            tenancy_models.HolidayCalendar.objects.filter(
                tenant_id=pine_content.id, holiday_date="2026-11-26"
            ).count()
            == 1
        )
    with _pin("2026-11-26T10:00:00"), tenant_context(pine_content.id):  # Thanksgiving, a Thursday
        centres = {row["name"]: row for row in published_content.public_centres(pine_content.id)}
    for name in ("Main office", "North counter"):
        today = centres[name]["today"]
        assert today["is_open_now"] is False, name
        # ⚠ THE LABEL IS THE CALENDAR'S OWN. Provisioning seeded the federal
        # holidays, so this closure was never typed by this fixture either —
        # `us_holidays.py` spells it *Thanksgiving Day*.
        assert today["closed_for_holiday"] == {"date": "2026-11-26", "label": "Thanksgiving Day"}
    # And the footer's holiday is the calendar's own label, not our copy.
    assert centres["Main office"]["today"]["next_holiday"]["label"] == "Thanksgiving Day"


@pytest.mark.django_db
def test_tc4_four_of_the_five_action_rows_say_no_on_the_north_counter(pine_content):
    """⚠ NEGATIVE, and the point of the screen: *"a list that also shows what it
    cannot do is an answer, and it is the difference between one journey and
    two."*"""
    with _pin("2026-11-18T10:00:00"), tenant_context(pine_content.id):
        centre = published_content.public_centre(pine_content.id, "north-counter")
    assert centre["allowed_actions"] == ["pay_a_bill"]
    assert len(centre["cannot_do"]) == 4
    assert "open_or_close_an_account" in centre["cannot_do"]
    assert len(centre["all_actions"]) == 5


@pytest.mark.django_db
def test_tc5_hiding_every_centre_removes_the_page_the_link_and_the_route(pine_content, sarah):
    """⚠ NEGATIVE. Not an empty list rendered as a page with a heading — a 404,
    so the link cannot exist either (`BR-CWP-093`)."""
    with tenant_context(pine_content.id):
        assert published_content.shown_centre_count(pine_content.id) == 2
        for row in published_content.back_office_centres(pine_content.id):
            published_content.update_centre(
                sarah, pine_content.id, row["slug"], {"is_shown_to_customers": False}
            )
        assert published_content.shown_centre_count(pine_content.id) == 0
        with pytest.raises(errors.NotFoundError):
            published_content.public_centres(pine_content.id)
        with pytest.raises(errors.NotFoundError):
            published_content.public_centre(pine_content.id, "main-office")
        # ⚠ AND ALL THREE ARE STILL IN THE CLERK'S LIST.
        assert len(published_content.back_office_centres(pine_content.id)) == 3


@pytest.mark.django_db
def test_tc6_what_each_centre_takes_and_the_one_that_has_no_card_machine(pine_content):
    with _pin("2026-11-18T10:00:00"), tenant_context(pine_content.id):
        rows = {row["name"]: row for row in published_content.public_centres(pine_content.id)}
    assert rows["Main office"]["payment_methods_accepted"] == [
        "cash",
        "cheque",
        "card",
        "money_order",
    ]
    assert rows["North counter"]["payment_methods_accepted"] == ["cash", "cheque"]
    assert "card" not in rows["North counter"]["payment_methods_accepted"]


@pytest.mark.django_db
def test_tc7_isolation_oak_ridge_sees_only_its_own_centres(pine_content, oak_ridge, elena):
    with tenant_context(oak_ridge.id):
        published_content_sample.seed_oak_ridge_content(oak_ridge.id)
        rows = published_content.back_office_centres(oak_ridge.id)
    assert [row["name"] for row in rows] == ["Ridge office"]
    assert "Palm Ct" not in str(rows) and "Cedar St" not in str(rows)


@pytest.mark.django_db
def test_tc8_the_public_page_follows_the_back_office_position(pine_content, sarah):
    with _pin("2026-11-18T10:00:00"), tenant_context(pine_content.id):
        assert [row["name"] for row in published_content.public_centres(pine_content.id)] == [
            "Main office",
            "North counter",
        ]
        published_content.update_centre(sarah, pine_content.id, "north-counter", {"position": 0})
        assert [row["name"] for row in published_content.public_centres(pine_content.id)] == [
            "North counter",
            "Main office",
        ]


@pytest.mark.django_db
def test_tc9_removing_a_centre_is_possible_and_hiding_is_what_leaves_it_findable(
    pine_content, sarah
):
    """⚠ NEGATIVE in spirit: the point is that hiding and removing are DIFFERENT
    acts. Hiding leaves the row; removing takes it away, and the screen's
    danger-tier warning about printed addresses is why a clerk should hide."""
    with tenant_context(pine_content.id):
        published_content.update_centre(
            sarah, pine_content.id, "depot", {"is_shown_to_customers": False}
        )
        assert len(published_content.back_office_centres(pine_content.id)) == 3
        published_content.delete_centre(sarah, pine_content.id, "depot")
        assert len(published_content.back_office_centres(pine_content.id)) == 2
        with pytest.raises(errors.NotFoundError):
            published_content.back_office_centre(pine_content.id, "depot")


@pytest.mark.django_db
def test_the_guest_route_404s_for_a_hidden_centre_by_its_own_slug(pine_content):
    """A depot's address is not a secret, but a page the utility took off the
    portal must not be reachable by typing its name."""
    with tenant_context(pine_content.id):
        with pytest.raises(errors.NotFoundError):
            published_content.public_centre(pine_content.id, "depot")


@pytest.mark.django_db
def test_the_back_office_centre_list_refuses_a_billing_clerk(pine_content, pine_clerk):
    refused = api_call(
        published_content_api.service_centres,
        "get",
        f"/api/{pine_content.subdomain}/settings/reference-data/service-centres",
        user=pine_clerk.user,
        role=pine_clerk.role,
        tenant=pine_content,
    )
    assert refused.status_code == 403
