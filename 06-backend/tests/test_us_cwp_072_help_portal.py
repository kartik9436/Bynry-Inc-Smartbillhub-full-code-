# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-072 (EP-CWP-12) — help on the portal: the list, one answer,
#           and the same answer under a bill. Screens: CWP-011 · CWP-060
# Rules:    BR-CWP-094 (only published; English fallback) · BR-CWP-093 (no
#           published answers ⇒ no page and no link) · a read and a vote are
#           counted separately · every answer ends in a route to a person
# Tests:    this file — TC-1 (six, each opening its own page), TC-3 (three
#           opens move the count), TC-4 negative (a vote is its own event),
#           TC-6 (the same answer under a bill, written once), TC-7 negative
#           (nothing published ⇒ the page, the link and the panels are absent),
#           TC-8 negative (a locale with no variant reads English and says so),
#           TC-9 isolation, TC-10 (the walk-in route is absent when no centre
#           is shown)
# Impacts:  apps/portal/guest_api.py · apps/portal/seams/tenancy_seam.py
# ───────────────────────────────────────────────────────
"""US-CWP-072 — the guest half of the help store, over the wire."""

import pytest

from apps.portal import guest_api
from apps.tenancy import published_content, published_content_api, published_content_sample
from core import errors
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import brand_fully, switch_on
from tests.test_us_ten_helpers import api_call


@pytest.fixture()
def pine_content(pine_hill, sarah):
    with tenant_context(pine_hill.id):
        published_content_sample.seed_published_content(pine_hill.id)
    return pine_hill


def _help(tenant, **query):
    return api_call(
        guest_api.help_answers,
        "get",
        f"/api/{tenant.subdomain}/portal/public/help",
        tenant=tenant,
        query=query or None,
    ).data


def _answer(tenant, slug, **query):
    return api_call(
        guest_api.help_answer,
        "get",
        f"/api/{tenant.subdomain}/portal/public/help/{slug}",
        tenant=tenant,
        query=query or None,
        slug=slug,
    ).data


@pytest.mark.django_db
def test_tc1_the_public_list_shows_six_each_with_its_own_door(pine_content):
    body = _help(pine_content)
    assert len(body["answers"]) == 6
    for row in body["answers"]:
        opened = _answer(pine_content, row["slug"])
        assert opened["question"] == row["question"]
        assert opened["body"].strip()
    # ⚠ The chips are DERIVED — a topic chip that filters to nothing would be a
    # container with nothing in it (BR-CWP-093).
    assert set(body["topics"]) == {row["topic"] for row in body["answers"]}


@pytest.mark.django_db
def test_tc3_and_tc4_a_read_and_a_vote_are_two_events(pine_content):
    slug = _help(pine_content)["answers"][0]["slug"]
    with tenant_context(pine_content.id):
        before = published_content.back_office_answer(pine_content.id, slug)["reads_this_month"]
    for _ in range(3):
        api_call(
            published_content_api.help_feedback,
            "post",
            f"/api/{pine_content.subdomain}/portal/public/help/{slug}/feedback",
            tenant=pine_content,
            data={"event": "read", "locale": "en"},
            slug=slug,
        )
    api_call(
        published_content_api.help_feedback,
        "post",
        f"/api/{pine_content.subdomain}/portal/public/help/{slug}/feedback",
        tenant=pine_content,
        data={"event": "not_helpful", "locale": "en"},
        slug=slug,
    )
    with tenant_context(pine_content.id):
        after = published_content.back_office_answer(pine_content.id, slug)["reads_this_month"]
    assert after == before + 3  # ⚠ THE VOTE DID NOT MOVE IT


@pytest.mark.django_db
def test_the_feedback_row_names_nobody(pine_content):
    """⚠ BR-CWP-021 the other way round: the utility learns that an answer was
    read, never by whom. The row has no customer, no account, no session."""
    from apps.tenancy import published_content_models as content

    slug = _help(pine_content)["answers"][0]["slug"]
    api_call(
        published_content_api.help_feedback,
        "post",
        f"/api/{pine_content.subdomain}/portal/public/help/{slug}/feedback",
        tenant=pine_content,
        data={"event": "helpful"},
        slug=slug,
    )
    fields = {f.name for f in content.HelpAnswerFeedback._meta.get_fields()}
    assert fields == {"id", "tenant", "answer", "locale", "event", "occurred_on", "created_at"}


@pytest.mark.django_db
def test_tc6_the_same_answer_under_a_bill_and_the_utility_wrote_it_once(pine_content):
    with tenant_context(pine_content.id):
        under_bill = published_content.attached_answer(pine_content.id, "bill", locale="en")
    listed = _help(pine_content)["answers"]
    assert under_bill["slug"] in [row["slug"] for row in listed]
    assert under_bill["question"] == "Why is my bill higher than last month?"


@pytest.mark.django_db
def test_tc7_with_nothing_published_the_page_the_link_and_the_card_are_absent(pine_hill, sarah):
    """⚠ NEGATIVE, and it is the state a brand-new utility is in. No fixture
    content here on purpose."""
    switch_on(pine_hill, sarah)
    brand_fully(pine_hill, sarah)
    front = api_call(
        guest_api.front, "get", f"/api/{pine_hill.subdomain}/portal/public/front", tenant=pine_hill
    ).data
    assert front["links"]["help"] is False
    assert front["links"]["visit"] is False
    # ⚠ **THIS READ `"help_answers" not in front["cards"]` AND WOULD NOW HAVE
    # PASSED FOR THE WRONG REASON.** Since 2026-09-05 `cards` is a list of
    # OBJECTS, and a string is never equal to a dict — so the old line was
    # green over any payload at all, including one that offered the card.
    # A check whose output cannot distinguish pass from fail is worse than no
    # check (`DEF-182`), so it asks the question the ruling left it:
    # the card is SENT, and it is not usable.
    help_card = next(card for card in front["cards"] if card["key"] == "help_answers")
    assert help_card["available"] is False
    assert help_card["reason_code"] == "nothing_published_yet"
    body = _help(pine_hill)
    assert body["answers"] == [] and body["topics"] == []


@pytest.mark.django_db
def test_tc8_a_locale_with_no_variant_reads_english_and_says_so(pine_content):
    slug = _help(pine_content)["answers"][0]["slug"]
    french = _answer(pine_content, slug, locale="fr-FR")
    assert french["is_fallback"] is True
    assert french["shown_in"] == "en"
    assert french["asked_for"] == "fr-FR"
    # ⚠ A REGIONAL VARIANT FALLS BACK TO ITS OWN LANGUAGE FIRST: fr-CA reads
    # the French we have; es-AR reads the Spanish we have, not English.
    spanish = _answer(pine_content, slug, locale="es-AR")
    assert spanish["shown_in"].startswith("es")
    assert spanish["is_fallback"] is True


@pytest.mark.django_db
def test_tc9_isolation_a_pine_hill_read_gets_pine_hill_answers(pine_content, oak_ridge, elena):
    with tenant_context(oak_ridge.id):
        published_content_sample.seed_oak_ridge_content(oak_ridge.id)
    oak = _help(oak_ridge)
    assert [row["question"] for row in oak["answers"]] == ["Where does Oak Ridge water come from?"]
    assert "bill higher" not in str(oak)
    pine = _help(pine_content)
    assert "Oak Ridge" not in str(pine)


@pytest.mark.django_db
def test_tc10_the_walk_in_route_is_absent_when_no_centre_is_shown(pine_content, sarah):
    assert _help(pine_content)["visit_link"] is True
    with tenant_context(pine_content.id):
        for row in published_content.back_office_centres(pine_content.id):
            published_content.update_centre(
                sarah, pine_content.id, row["slug"], {"is_shown_to_customers": False}
            )
    assert _help(pine_content)["visit_link"] is False


@pytest.mark.django_db
def test_an_answer_published_with_no_body_in_any_language_is_not_a_door(pine_hill, sarah):
    """⚠ BR-CWP-093 at its sharpest: a published answer whose every language is
    empty would list a question that opens onto nothing."""
    with tenant_context(pine_hill.id):
        view = published_content.create_answer(
            sarah, pine_hill.id, {"question": "Is the water safe to drink?", "topic": "water"}
        )
        published_content.publish_answer(sarah, pine_hill.id, view["slug"], status="published")
        with pytest.raises(errors.NotFoundError):
            published_content.published_answer(pine_hill.id, view["slug"], locale="en")
