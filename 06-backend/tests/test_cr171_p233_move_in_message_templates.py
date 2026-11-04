# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 (move-in redesign) · lane MVI-WIZ-REV · P2.33
# Rules:    images 45, 46 (the Messaging table's *+ Add message* row picks a
#           message by NAME) · B14 rule 31 (the code is the value, the name is
#           what is shown) · §9.FLOW P1.20 (the two defaults are never a row)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**`GET /move-ins/message-templates` — what *+ Add message* may pick.**

RED-FIRST (law 7): run before the route existed —
``django.urls.exceptions.Resolver404`` on ``/api/v1/move-ins/message-templates``,
and ``AttributeError: module 'apps.customers.move_in_complete' has no attribute
'template_choices'``.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):

  * **An empty list read as success.** The default-exclusion case only means
    something when the tenant publishes at least one other template, so it
    skips — loudly — when it publishes none, rather than asserting over nothing.
  * **A list that differs from what Complete queues from.** The rows are
    compared with `notifications_seam.message_templates()` itself, the call
    `move_in_complete.queue` reads the wording through.
"""

import pytest
from django.urls import resolve

from apps.customers import move_in_complete, move_in_flow_api, notifications_seam

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def test_the_route_resolves_to_the_view():
    match = resolve("/api/v1/move-ins/message-templates")
    assert match.func is move_in_flow_api.move_in_message_templates


def test_every_choice_is_a_published_template_and_never_a_default(brazos):
    with tenant_ctx(brazos):
        answer = move_in_complete.template_choices()
        published = {row["code"] for row in notifications_seam.message_templates()}
    assert answer["served"] is (len(published) > 0)
    codes = [row["code"] for row in answer["results"]]
    assert set(codes) <= published
    assert not set(codes) & set(move_in_complete.DEFAULT_TEMPLATES)
    if not codes:
        pytest.skip("this tenant publishes no template besides the defaults")
    for row in answer["results"]:
        assert set(row) == {"code", "name"}
        assert row["name"].strip() != ""


def test_a_search_narrows_by_the_name_a_person_gave_it(brazos):
    with tenant_ctx(brazos):
        every = move_in_complete.template_choices()["results"]
        if not every:
            pytest.skip("this tenant publishes no template besides the defaults")
        word = every[0]["name"].split()[0]
        narrowed = move_in_complete.template_choices(search=word.upper())["results"]
    assert narrowed and all(word.lower() in row["name"].lower() for row in narrowed)
