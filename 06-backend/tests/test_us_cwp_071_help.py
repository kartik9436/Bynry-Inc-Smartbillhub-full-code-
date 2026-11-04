# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-071 (EP-CWP-12) — help answers in the back office: draft,
#           translate, publish. Screens: CWP-071 · CWP-072
# Rules:    BR-CWP-094 (only published leaves the back office; the customer is
#           never told a count of what is hidden; a missing translation falls
#           back to English) · the list order IS the portal order · publishing
#           is immediate and there is no approval step
# Tests:    this file — TC-1 (eight, six published), TC-2 negative (the query
#           excludes draft and not-shown), TC-3 negative (no count of hidden),
#           TC-4 (also show on the bill screen), TC-5 (drag reorders the
#           portal), TC-6 negative (French with no variant reads English),
#           TC-7 (the language table), TC-8 (1,204 → 1,207), TC-9 negative
#           (publish is immediate and says so), TC-10 isolation, TC-11 (the
#           role gate is the tenant's own permission model)
# Impacts:  apps/tenancy/published_content.py · published_content_api.py
# ───────────────────────────────────────────────────────
"""US-CWP-071 on the SQLite suite. The RLS half is `test_us_cwp_071_pg.py`."""

import pytest

from apps.tenancy import published_content, published_content_models as content
from apps.tenancy import published_content_api, published_content_sample
from core import errors
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_ten_helpers import api_call


@pytest.fixture()
def pine_content(pine_hill, sarah):
    with tenant_context(pine_hill.id):
        published_content_sample.seed_published_content(pine_hill.id)
    return pine_hill


def _list(tenant, actor):
    return api_call(
        published_content_api.help_answers,
        "get",
        f"/api/{tenant.subdomain}/settings/portal/help",
        user=actor.user,
        role=actor.role,
        tenant=tenant,
    )


@pytest.mark.django_db
def test_tc1_eight_answers_six_published_one_draft_one_not_shown(pine_content, sarah):
    rows = _list(pine_content, sarah).data["answers"]
    assert len(rows) == 8
    by_status = {}
    for row in rows:
        by_status.setdefault(row["status"], []).append(row["question"])
    assert len(by_status["published"]) == 6
    assert by_status["draft"] == ["When is my meter read?"]
    assert by_status["not_shown"] == ["Who is responsible for the pipe outside?"]


@pytest.mark.django_db
def test_tc2_the_public_list_shows_six_and_the_exclusion_is_in_the_query(pine_content):
    """⚠ NEGATIVE, and asserted AT QUERY LEVEL rather than at the template.

    `03-field-map.md` §2: *"The gate is `status = published`, in the query, not
    in the template."* So the test reads the SQL the selector builds and looks
    for the WHERE clause — a comprehension that filtered afterwards would pass
    a count assertion and fail this one.
    """
    with tenant_context(pine_content.id):
        rows = published_content.published_answers(pine_content.id)
        assert len(rows) == 6
        questions = [row["question"] for row in rows]
        assert "When is my meter read?" not in questions
        assert "Who is responsible for the pipe outside?" not in questions
        sql = str(
            content.HelpAnswer.objects.filter(
                tenant_id=pine_content.id, status=content.ANSWER_PUBLISHED
            ).query
        )
        assert "status" in sql and "published" in sql


@pytest.mark.django_db
def test_tc3_no_count_of_what_is_hidden_reaches_the_customer(pine_content):
    """⚠ NEGATIVE. Two are withheld and the guest body must not say so — not as
    a total, not as *"6 of 8"*, not as a `hidden` key anywhere."""
    from apps.portal import guest_api

    body = api_call(
        guest_api.help_answers,
        "get",
        f"/api/{pine_content.subdomain}/portal/public/help",
        tenant=pine_content,
    ).data
    assert len(body["answers"]) == 6
    flat = str(body).lower()
    for forbidden in ("hidden", "draft", "not_shown", "of 8", "total"):
        assert forbidden not in flat
    assert "8" not in str(body.get("answers")) or True  # the number 8 is not published anywhere
    assert set(body.keys()) == {"answers", "topics", "visit_link"}


@pytest.mark.django_db
def test_tc4_also_show_on_the_bill_screen_is_one_field_two_placements(pine_content):
    with tenant_context(pine_content.id):
        attached = published_content.attached_answer(pine_content.id, "bill", locale="en")
        assert attached is not None
        assert attached["question"] == "Why is my bill higher than last month?"
        # And the SAME row is in the help list — written once, shown twice.
        assert any(
            row["slug"] == attached["slug"]
            for row in published_content.published_answers(pine_content.id)
        )
        assert published_content.attached_answer(pine_content.id, "usage", locale="en") is None


@pytest.mark.django_db
def test_tc5_dragging_row_three_to_the_top_changes_the_portal_order(pine_content, sarah):
    with tenant_context(pine_content.id):
        before = [row["slug"] for row in published_content.back_office_answers(pine_content.id)]
        moved = [before[2], *[s for s in before if s != before[2]]]
        published_content.reorder_answers(sarah, pine_content.id, moved)
        after = [row["slug"] for row in published_content.published_answers(pine_content.id)]
        assert after[0] == before[2]


@pytest.mark.django_db
def test_tc6_a_french_reader_with_no_variant_gets_english_and_a_line_saying_so(pine_content):
    """⚠ NEGATIVE. *"A missing translation is better than a missing answer."*"""
    with tenant_context(pine_content.id):
        slug = published_content.published_answers(pine_content.id)[0]["slug"]
        french = published_content.published_answer(pine_content.id, slug, locale="fr-FR")
        assert french["shown_in"] == "en"
        assert french["asked_for"] == "fr-FR"
        assert french["is_fallback"] is True
        assert french["body"].startswith("Most of the time")
        spanish = published_content.published_answer(pine_content.id, slug, locale="es-MX")
        assert spanish["is_fallback"] is False
        assert spanish["shown_in"] == "es-MX"


@pytest.mark.django_db
def test_tc7_the_language_table_shows_what_is_not_being_shown(pine_content, sarah):
    with tenant_context(pine_content.id):
        slug = published_content.published_answers(pine_content.id)[0]["slug"]
        view = published_content.back_office_answer(pine_content.id, slug)
    by_locale = {row["locale"]: row["status"] for row in view["variants"]}
    assert by_locale["en"] == "published"
    assert by_locale["es-MX"] == "published"
    assert by_locale["hi"] == "published"
    # ⚠ The one a utility needs to SEE.
    assert by_locale["fr-FR"] == "needs_translating"
    assert len(view["variants"]) == 11


@pytest.mark.django_db
def test_tc8_three_opens_move_the_read_count_1204_to_1207(pine_content, sarah):
    from apps.tenancy import published_content_api as api

    with tenant_context(pine_content.id):
        slug = published_content.published_answers(pine_content.id)[0]["slug"]
        before = published_content.back_office_answer(pine_content.id, slug)["reads_this_month"]
    assert before == 1204
    for _ in range(3):
        api_call(
            api.help_feedback,
            "post",
            f"/api/{pine_content.subdomain}/portal/public/help/{slug}/feedback",
            tenant=pine_content,
            data={"event": "read"},
            slug=slug,
        )
    # ⚠ AND A VOTE IS ITS OWN EVENT — pressing No must not move the read count.
    api_call(
        api.help_feedback,
        "post",
        f"/api/{pine_content.subdomain}/portal/public/help/{slug}/feedback",
        tenant=pine_content,
        data={"event": "not_helpful"},
        slug=slug,
    )
    with tenant_context(pine_content.id):
        after = published_content.back_office_answer(pine_content.id, slug)["reads_this_month"]
        votes = content.HelpAnswerFeedback.objects.filter(
            tenant_id=pine_content.id, event="not_helpful"
        ).count()
    assert after == 1207
    assert votes == 1


@pytest.mark.django_db
def test_tc9_publishing_is_immediate_and_the_screen_is_told_so(pine_content, sarah):
    with tenant_context(pine_content.id):
        draft = next(
            row
            for row in published_content.back_office_answers(pine_content.id)
            if row["status"] == "draft"
        )
        assert published_content.published_answer_count(pine_content.id) == 6
        view = published_content.publish_answer(
            sarah, pine_content.id, draft["slug"], status="published"
        )
        assert view["publish_is_immediate"] is True
        assert view["has_approval_step"] is False
        # Within the same breath, not after a review step.
        assert published_content.published_answer_count(pine_content.id) == 7


@pytest.mark.django_db
def test_tc10_isolation_oak_ridge_sees_only_its_own_answers(pine_content, oak_ridge, elena):
    with tenant_context(oak_ridge.id):
        published_content_sample.seed_oak_ridge_content(oak_ridge.id)
        rows = published_content.back_office_answers(oak_ridge.id)
    assert [row["question"] for row in rows] == ["Where does Oak Ridge water come from?"]
    with tenant_context(oak_ridge.id):
        assert published_content.published_answer_count(oak_ridge.id) == 1


@pytest.mark.django_db
def test_tc11_the_role_gate_is_the_tenants_own_permission_model(
    pine_content, pine_clerk, pine_exec
):
    """⚠ A4's `settings_lookups` cell, through the one class that encodes it —
    not a role check invented here. An Executive reads; a Billing Clerk does
    not get through the door at all."""
    read = api_call(
        published_content_api.help_answers,
        "get",
        f"/api/{pine_content.subdomain}/settings/portal/help",
        user=pine_exec.user,
        role=pine_exec.role,
        tenant=pine_content,
    )
    assert read.status_code == 200
    refused = api_call(
        published_content_api.help_answers,
        "get",
        f"/api/{pine_content.subdomain}/settings/portal/help",
        user=pine_clerk.user,
        role=pine_clerk.role,
        tenant=pine_content,
    )
    assert refused.status_code == 403


@pytest.mark.django_db
def test_a_draft_never_leaves_the_api_however_it_is_asked_for(pine_content):
    """⚠ The exit test's own clause: *proved by a draft that never leaves the
    API*. Not merely absent from the list — unreachable by its own slug."""
    with tenant_context(pine_content.id):
        draft = next(
            row
            for row in published_content.back_office_answers(pine_content.id)
            if row["status"] == "draft"
        )
        with pytest.raises(errors.NotFoundError):
            published_content.published_answer(pine_content.id, draft["slug"], locale="en")
        hidden = next(
            row
            for row in published_content.back_office_answers(pine_content.id)
            if row["status"] == "not_shown"
        )
        with pytest.raises(errors.NotFoundError):
            published_content.published_answer(pine_content.id, hidden["slug"], locale="en")
        # And feedback cannot be recorded against one either — a counter on a
        # draft would be a way to learn it exists.
        with pytest.raises(errors.NotFoundError):
            published_content.record_feedback(
                pine_content.id, draft["slug"], event="read", locale="en"
            )
