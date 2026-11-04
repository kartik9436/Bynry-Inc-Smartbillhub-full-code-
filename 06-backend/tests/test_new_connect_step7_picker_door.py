# ── Trace ──────────────────────────────────────────────
# Story:   New Connect step 7 — `Choosing a template` (S87 step 7)
#          Screens: 05-prototype/02 Accounts Menu Blueprint.pdf p091, read AS AN
#          IMAGE at scale 2 (B14 rule 42)
# Rules:   BR-MET-112 (nothing is written until the last button — so this door
#          is a READ and takes no connection id) · BR-NOT-013 (nothing is sent) ·
#          B14 rule 31 (a clerk searches the name a human gave it, never a code)
# Laws:    hard-won law 2 (built is not wired) — `connection_messages.
#          template_choices` and `notifications.connection_events` were both
#          built, proved and reachable from no URL, so the drawn picker had
#          nowhere to get a row.
# ───────────────────────────────────────────────────────
"""**Can the drawn template picker actually be reached from a browser?**

`connection_events.py` records its own gap in its lifecycle block —
*"D=deferred(reached through metering's seam, no HTTP surface of its own)"* —
and the step-7 screen is the wave that needs it. A picker whose rows come from
an unmounted address is the dead control hard-won law 2 is about: `tsc` passes,
every backend case passes, and the clerk sees an empty table forever.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY.** `resolve()` raises `Resolver404` on an
unmounted path, so case 1 cannot pass over a missing route — but it would pass
over a route pointed at the wrong view, so it asserts the view by name as well.
Case 2 could pass wrongly by asserting only that a dict came back, so it asks
for the KEYS the screen actually reads. Case 3 could pass wrongly if the search
were ignored, so it searches for something no class name contains and requires
the row count to MOVE.
"""

import pytest
from django.urls import Resolver404, resolve

from apps.metering import api as metering_api
from apps.metering import connection_messages

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def test_the_picker_address_is_served_and_by_the_right_view():
    """The address the step-7 screen reads resolves, onto the view that answers it."""
    try:
        match = resolve("/api/v1/connections/message-templates")
    except Resolver404:  # pragma: no cover - the failure this test exists for
        pytest.fail(
            "GET /connections/message-templates is not mounted — the drawn "
            "template picker has no address to read rows from."
        )
    assert match.func is metering_api.connection_message_templates


def test_the_door_answers_the_keys_the_screen_reads(brazos, dana):
    """`rows` and `unavailable`, because the screen renders both."""
    with tenant_ctx(brazos):
        answer = connection_messages.template_choices()
    assert set(answer) == {"rows", "unavailable"}
    for row in answer["rows"]:
        # The drawn columns, plus the thing that decides the radio. `VARIANT` is
        # the `(category, language)` pair BR-BIL-025 resolves on, which the
        # SCREEN renders as *Default · English* in its own catalogue (B14 rule
        # 35) — there is no `variant` key and there must not be one.
        assert {
            "name",
            "group",
            "channel",
            "category",
            "language",
            "version",
            "status",
            "pickable",
        } <= set(row)
        # B14 rule 31 — the id travels so the screen can key a row, and `name`
        # is the only thing a clerk may read.
        assert row["name"]


def test_a_seeded_utility_gets_two_rows_and_the_contract_is_not_one_of_them(brazos, dana):
    """**The picker is not empty, and message two has no row — that is the rule.**

    ⚠ **THIS IS WHAT STOPS THE TWO CASES EITHER SIDE PASSING VACUOUSLY.** A
    key-shape loop over an empty tuple asserts nothing, and a search that
    clears an already-empty table proves nothing. So the count is pinned here.

    ⚠ **AND THE ABSENCE IS THE POINT RATHER THAN A GAP.** `BR-NOT-002` makes a
    contract version effective-dated and `seed_notice_templates` REFUSES to seed
    one — there is no human in a provisioning transaction to choose that date.
    A lane "fixing" this by adding `contract_service_agreement` to `SEEDABLE`
    would publish an undated agreement on every tenant. The step-7 screen must
    say so where the row would have been.
    """
    with tenant_ctx(brazos):
        rows = connection_messages.template_choices()["rows"]
    assert len(rows) == 2
    assert {row["code"] for row in rows} == {"new_connect_confirmed", "new_connect_quote"}
    assert all(row["pickable"] for row in rows)
    assert connection_messages.CLASS_CONTRACT not in {row["code"] for row in rows}


def test_a_search_that_matches_nothing_returns_nothing(brazos, dana):
    """The search is applied server-side, not ignored (B14 rule 31 — it matches
    the name a human gave it, so a nonsense term must clear the table)."""
    with tenant_ctx(brazos):
        everything = connection_messages.template_choices()
        nothing = connection_messages.template_choices(search="zzz-no-such-template")
    assert len(nothing["rows"]) < len(everything["rows"]) or len(everything["rows"]) == 0
    assert len(nothing["rows"]) == 0
