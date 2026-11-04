# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-001 (EP-CWP-01) — the public front page, with sign-in as
#           one card among six. Screens: CWP-001
# Rules:    BR-CWP-005 · BR-CWP-007 · BR-CWP-021 · BR-CWP-022 · BR-CWP-093 ·
#           CR-068 R8 · R9 · hard-won law 3
# Tests:    this file — TC-1 (ALL SIX cards, each with whether it may be used),
#           TC-2 (quick pay off → the card is SENT and unavailable, and the
#           lookup door still refuses), TC-3 (off → holding data, no
#           notification row changes), TC-4 (no Help / Visit link when nothing
#           is published, and the card says why), TC-5 (Oak Ridge carries no
#           Pine Hill string), TC-6 (a reserved or unknown first segment 404s,
#           never 500s), plus the two HOLD-EXPIRY cases: publishing one answer
#           turns Help & answers on, and Check my area stays off under every
#           switch until R9 is reversed
# Impacts:  apps/portal/guest_api.py · selectors.py · config/urls.py
# ───────────────────────────────────────────────────────
"""US-CWP-001 — `GET /portal/public/front` on the SQLite suite. The RLS half
of TC-5 is `test_us_cwp_001_pg.py` (hard-won law 14)."""

import pytest
from django.urls import Resolver404, resolve

from apps.notifications import models as notifications_models
from apps.portal import guest_api, models, sample_data, selectors
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import brand_fully, switch_on
from tests.test_us_ten_helpers import api_call


def _front(tenant):
    """The guest call: NO user, NO role — a visitor holding nothing."""
    return api_call(guest_api.front, "get", f"/api/{tenant.subdomain}/portal/public/front", tenant=tenant)


@pytest.mark.django_db
def test_us_cwp_001_tc1_a_live_portal_offers_the_errand_cards_and_no_password_field(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    brand_fully(pine_hill, sarah)
    body = _front(pine_hill).data
    assert body["is_live"] is True
    # ⚠ **ALL SIX, AND FOUR OF THEM USABLE.** This asserted a four-item list of
    # keys until 2026-09-05; the PO looked at the live page beside the
    # blueprint and ruled *"Yoi ahev these cards - may be disable them, but for
    # completess have them on screen"*. So the shape carries the reason too,
    # and the two that cannot be used carry reasons that are DIFFERENT IN KIND
    # — which is the thing `DEF-CWP-3953` says the utility could never see.
    assert body["cards"] == [
        {"key": "pay_bill", "available": True, "reason_code": None},
        {"key": "report_problem", "available": True, "reason_code": None},
        {"key": "check_my_area", "available": False, "reason_code": "status_page_not_offered"},
        {"key": "start_service", "available": True, "reason_code": None},
        {"key": "what_things_cost", "available": True, "reason_code": None},
        {"key": "help_answers", "available": False, "reason_code": "nothing_published_yet"},
    ]
    # The order is `CARD_ORDER`'s, which is the wireframe's, and the ruling did
    # not touch it: a disabled card holds its PLACE, which is what *for
    # completeness* means on a grid of six.
    assert [card["key"] for card in body["cards"]] == list(selectors.CARD_ORDER)
    assert body["tenant"]["name"] == "Pine Hill Water & Power"
    assert body["tenant"]["brand_primary_hex"] == "#EC3013"
    assert body["strapline"] == sample_data.PINE_HILL["branding"]["strapline"]
    assert [chip["code"] for chip in body["services"]] == ["water", "sewer", "trash", "electric"]
    # BR-CWP-021 and B14 rule 31: no person, no id, anywhere in the body.
    flat = str(body)
    assert "sarah" not in flat.lower() and "Miller" not in flat
    assert "id" not in body["tenant"] and all("id" not in chip for chip in body["services"])
    # A guest surface has no password field to meet: the payload names no
    # credential, no session and no sign-in door.
    assert "password" not in flat.lower()


@pytest.mark.django_db
def test_us_cwp_001_tc2_quick_pay_off_disables_the_card_and_the_lookup_door_still_refuses(pine_hill, sarah):
    switch_on(pine_hill, sarah, quick_pay_enabled=False)
    body = _front(pine_hill).data
    # ⚠ **AMENDED 2026-09-05 WITH THE CODE IT DESCRIBES.** TC-2 read *absent,
    # not greyed* from the story's first draft until the PO ruled the opposite:
    # *"Yoi ahev these cards - may be disable them, but for completess have
    # them on screen"*. The card is SENT, unavailable, and says which of the
    # three conditions holds — here the one the utility can reverse itself.
    pay = next(card for card in body["cards"] if card["key"] == "pay_bill")
    assert pay == {
        "key": "pay_bill",
        "available": False,
        "reason_code": "switched_off_by_the_utility",
    }
    assert body["switches"]["quick_pay_enabled"] is False
    # ⚠ **REWRITTEN 2026-09-05, EXACTLY AS THE VERSION IT REPLACES INSTRUCTED.**
    # This case used to assert `Resolver404` — *"the door does not exist at all
    # … so the day it is mounted this case is rewritten to assert the refusal
    # rather than left quietly true"*. It is mounted (`US-CWP-003`), and a
    # `Resolver404` assertion left standing would have gone RED on the wave that
    # built it, which is what it was for.
    #
    # **THE REFUSAL IS AT THE EDGE, NOT AT THE SCREEN** (`BR-CWP-002`), AND
    # THAT HALF IS WHY THE 2026-09-05 RULING CHANGED NOTHING HERE. A drawn card
    # is not a mounted door: the *Pay a bill* card is now on screen and
    # disabled, and the lookup behind it refuses exactly as it did when the
    # card was hidden. A form nobody can see is still a form somebody can POST
    # to — and now so is one they can see and not press.
    assert resolve(f"/api/{pine_hill.subdomain}/portal/public/bills/lookup")
    refused = api_call(
        guest_api.bill_lookup,
        "post",
        f"/api/{pine_hill.subdomain}/portal/public/bills/lookup",
        tenant=pine_hill,
        data={"bill_number": "BL-2608-0141", "postcode": "78702"},
        headers={"X-Forwarded-For": "198.51.100.10"},
    )
    assert refused.status_code != 200, refused.data


@pytest.mark.django_db
def test_us_cwp_001_tc3_off_shows_the_holding_page_and_touches_no_notification(pine_hill):
    before = notifications_models.OutboundMessage.objects.count()
    body = _front(pine_hill).data
    # A fresh tenant has no row and reads OFF (law 3): the holding page's data.
    assert models.PortalSettings.objects.filter(tenant=pine_hill).exists() is False
    assert body["is_live"] is False
    # ⚠ **STILL EMPTY, AND THE 2026-09-05 RULING DOES NOT REACH HERE.** *"Have
    # them on screen"* is about the front page's grid of six; a holding page
    # has no grid to disable, no nav and no switches — six greyed cards over a
    # portal that is not live would be a catalogue of a shop that is shut.
    assert body["cards"] == []
    assert body["links"] == {"help": False, "visit": False}
    assert body["strapline"] is None and body["services"] == []
    assert "switches" not in body
    assert body["tenant"]["name"] == "Pine Hill Water & Power"  # whose holding page it is
    assert notifications_models.OutboundMessage.objects.count() == before


@pytest.mark.django_db
def test_us_cwp_001_tc4_nothing_published_disables_the_help_card_and_drops_the_links(pine_hill, sarah):
    """⚠ **THE CARD AND THE NAV WORD PART COMPANY HERE, AND THAT IS THE POINT.**
    One publish condition, two answers: the CARD is drawn and disabled because
    a catalogue of six is a promise about what this product does, and the nav
    WORDS stay absent because a nav word is a destination and a disabled word
    in a top bar is hard-won law 2's dead control."""
    switch_on(pine_hill, sarah)
    body = _front(pine_hill).data
    help_card = next(card for card in body["cards"] if card["key"] == "help_answers")
    assert help_card == {
        "key": "help_answers",
        "available": False,
        "reason_code": "nothing_published_yet",
    }
    assert body["links"] == {"help": False, "visit": False}
    # BR-CWP-093 for the CONTENT half, unchanged: the payload carries no empty
    # "answers" or "centres" list a screen could draw a frame around.
    assert "answers" not in body and "centres" not in body


# ═══════════════════════════════════════════════════════════════════════════
# THE HOLDS, AND THE CASES THAT FIRE WHEN EACH ONE EXPIRES
#
# ⚠ **`DEF-CWP-3925` IS WHAT THESE ARE FOR.** A rule of the form *held until X*
# rots on the day X arrives, because landing X and releasing the thing that
# pointed at it are two acts and only the first feels like the work. Five
# `Start →` controls and three nav words on this very page refused over live
# screens for a week for exactly that reason. So each hold below is written
# WITH the case that goes red the day it stops being true, and each case names
# the card in its own failure message.
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_us_cwp_001_publishing_one_answer_turns_the_help_card_on_the_same_day(pine_hill, sarah):
    """**THE HOLD ON *Help & answers* EXPIRES PER TENANT, AT RUNTIME, WITH NO
    RELEASE COMMIT** — one published answer is the whole of it (`BR-CWP-093`).
    That is precisely the fact `DEF-CWP-3953` says no utility could learn,
    because the card was not there to carry it. This case is the proof that the
    reason it now carries is TRUE: the same tenant, one publish apart.
    """
    from apps.tenancy import published_content_sample
    from core.tenancy import tenant_context

    switch_on(pine_hill, sarah)

    def help_card():
        cards = _front(pine_hill).data["cards"]
        return next(card for card in cards if card["key"] == "help_answers")

    before = help_card()
    assert before["available"] is False, "Help & answers is offered with nothing published"
    assert before["reason_code"] == "nothing_published_yet"

    with tenant_context(pine_hill.id):
        published_content_sample.seed_published_content(pine_hill.id)

    after = help_card()
    assert after == {"key": "help_answers", "available": True, "reason_code": None}, (
        "Help & answers is still refusing after this tenant published an answer — "
        "the hold outlived the condition (DEF-CWP-3925's shape)"
    )
    # And the nav word arrives with it, by the same condition and not by a
    # second one: the CARD and the WORD differ only while nothing is published.
    assert _front(pine_hill).data["links"]["help"] is True


@pytest.mark.django_db
def test_us_cwp_001_r9_check_my_area_is_off_by_the_ruling_under_every_switch(pine_hill, sarah):
    """**THE HOLD ON *Check my area* EXPIRES ONLY WHEN `CR-068` R9 IS REVERSED**
    — the public status page waits until somebody owns keeping it current out
    of hours, and NO switch a utility owns touches it. This case is what makes
    the difference machine-checkable: sweep every switch to both positions and
    the card never moves, and never borrows the reason the utility CAN act on.

    ⚠ Its other half is on the client — `FrontPage.test.tsx` refuses a
    `CWP-005` row in `PORTAL_SCREENS`, so the day somebody builds the status
    page the suite goes red there and names this card.
    """
    for switches in ({}, dict.fromkeys(models.SWITCH_FIELDS, False), dict.fromkeys(models.SWITCH_FIELDS, True)):
        switch_on(pine_hill, sarah, **switches)
        cards = _front(pine_hill).data["cards"]
        area = next(card for card in cards if card["key"] == "check_my_area")
        assert area == {
            "key": "check_my_area",
            "available": False,
            "reason_code": "status_page_not_offered",
        }, f"Check my area moved on switches {switches} — R9 is a ruling, not a switch"


@pytest.mark.django_db
def test_us_cwp_001_every_card_says_exactly_one_true_thing_about_itself(pine_hill, sarah):
    """**THE VOCABULARY IS CLOSED, AND THIS IS THE GUARD THAT KEEPS IT CLOSED.**
    A reason code with no sentence behind it renders as its own key, which is an
    internal code on a customer's screen — B14 rule 31, and `DEF-CWP-3952`'s
    shape one surface over. So a fourth code cannot arrive here without this
    case naming it, and the wording that must ship in the same commit is eleven
    catalogue lines (rule 35), six words or fewer each (rule 33).
    """
    known = {
        selectors.REASON_SWITCHED_OFF,
        selectors.REASON_STATUS_PAGE_NOT_OFFERED,
        selectors.REASON_NOTHING_PUBLISHED,
    }
    assert known == {"switched_off_by_the_utility", "status_page_not_offered", "nothing_published_yet"}
    for switches in ({}, dict.fromkeys(models.SWITCH_FIELDS, False)):
        switch_on(pine_hill, sarah, **switches)
        cards = _front(pine_hill).data["cards"]
        assert len(cards) == 6 and {card["key"] for card in cards} == set(selectors.CARD_ORDER)
        for card in cards:
            assert set(card) == {"key", "available", "reason_code"}
            if card["available"]:
                assert card["reason_code"] is None, f"{card['key']} is usable and excusing itself"
            else:
                assert card["reason_code"] in known, (
                    f"{card['key']} sends {card['reason_code']!r}, which no catalogue has a "
                    "sentence for — a screen would print the code itself (B14 rule 31)"
                )


@pytest.mark.django_db
def test_us_cwp_001_tc5_oak_ridge_carries_nothing_of_pine_hill(pine_hill, sarah, oak_ridge, elena):
    switch_on(pine_hill, sarah)
    brand_fully(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    brand_fully(oak_ridge, elena, sample_data.OAK_RIDGE)
    oak = _front(oak_ridge).data
    pine = _front(pine_hill).data
    assert oak["tenant"]["name"] == "Oak Ridge Water"
    assert oak["tenant"]["brand_primary_hex"] == "#0B6E4F"
    assert oak["strapline"] == sample_data.OAK_RIDGE["branding"]["strapline"]
    assert [chip["code"] for chip in oak["services"]] == ["water"]
    flat = str(oak)
    for pine_string in ("Pine Hill", "#EC3013", "#E15B47", pine["strapline"], "(512) 555-0100"):
        assert pine_string not in flat, pine_string


@pytest.mark.django_db
def test_us_cwp_001_tc6_a_first_segment_that_is_no_tenant_404s_and_never_500s(pine_hill):
    """`/portal/portal/…` — a utility named `portal` does not exist, so the
    slug resolves to nothing: BE-01 leaves `tenant_id` None with the slug set,
    and `require_tenant` answers 404, byte-identical to a foreign tenant."""
    from rest_framework.test import APIRequestFactory

    request = APIRequestFactory().get("/api/portal/portal/public/front")
    request.tenant_slug = "portal"
    request.tenant_id = None
    response = guest_api.front(request)
    assert response.status_code == 404
    assert response.data["code"] is None  # 404 carries no catalogue code (core.errors)


@pytest.mark.django_db
def test_us_cwp_001_the_guest_route_is_mounted_under_the_tenant_prefix(pine_hill):
    match = resolve(f"/api/{pine_hill.subdomain}/portal/public/front")
    assert match.func is guest_api.front
    # BR-CWP-022: the throttle is the product's own, reused and not copied.
    from apps.tenancy.api import PublicOnboardingThrottle

    assert PublicOnboardingThrottle in guest_api.front.cls.throttle_classes
    assert guest_api.front.cls.authentication_classes == []
