# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-014 (bounces + returned mail)   Screens: S8 (Settings →
#           Notifications → Blocked addresses)
# Rules:    B14 rule 31 (no database id is the visible value of a field — the
#           list still SERVES `id`, because Release needs it; what is refused is
#           a screen putting it in a cell) · `NFR-3` (universal server
#           pagination) · hard-won law 7 (a check that reports zero over a scope
#           it silently excludes)
# Change:   DEF-NOT-5637, 2026-09-17 — the blocked-addresses SCREEN, and the one
#           filter the served list was missing for it.
# Impacts:  apps/notifications/suppression.py (`listing(reason=…)`) ·
#           apps/notifications/api.py (`f.reason`)
# ───────────────────────────────────────────────────────
"""The server half of the blocked-addresses screen: can it FILTER BY REASON?

⚠ **WHY THIS IS A SERVER FILTER AND NOT THREE LINES OF JAVASCRIPT.** The screen
offers the four reasons because `suppression_models.py` argues they are not
interchangeable — a hard bounce is a typo a clerk can fix, a complaint is a
person who does not want the mail, an unsubscribe is a button we gave them. The
list is PAGINATED in the database (`NFR-3`), so a front end that narrowed the
page it was handed would answer *no complaints* for a utility whose complaints
are all on page two. That is hard-won law 7's *reporting zero over a scope it
silently excludes*, wearing a filter chip — and it is invisible to every check
this repo has, because the browser's arithmetic over the rows it holds is
correct.

The rest of the suppression contract is `test_def_not_5632_suppression.py`'s and
is not restated here.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone as dt_timezone

import pytest

from apps.notifications import api as notifications_api
from apps.notifications import models, suppression, suppression_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 9, 17, 15, 0, tzinfo=dt_timezone.utc)

#: One address per reason, so a filter that quietly ignores its argument returns
#: four rows where the test demands one and cannot pass by luck.
BY_REASON = {
    suppression_models.REASON_HARD_BOUNCE: "typo@exmaple.com",
    suppression_models.REASON_COMPLAINT: "annoyed@example.com",
    suppression_models.REASON_UNSUBSCRIBED: "left@example.com",
    suppression_models.REASON_MANUAL: "byhand@example.com",
}


def call(view, method, tenant, actor, *, role="system_admin", **kwargs):
    return api_call(view, method, user=actor.user, role=role, tenant=tenant, **kwargs)


def seed_one_per_reason(tenant, actor):
    for reason, address in BY_REASON.items():
        suppression.suppress(
            channel=models.CHANNEL_EMAIL,
            address=address,
            reason=reason,
            at=NOW,
            actor=actor,
        )


# ══════════════════════════════════════════════════════════════════════════
# THE case this file exists for
# ══════════════════════════════════════════════════════════════════════════
def test_the_list_narrows_by_reason_in_sql_not_in_the_browser(brazos, dana):
    """Each of the four reasons returns ITS row and only its row.

    Asserted through `listing()` — the queryset the view pages — rather than
    through a materialised list, because the whole point is that the narrowing
    happens before the page is taken.
    """
    with tenant_ctx(brazos):
        seed_one_per_reason(brazos, dana)

        for reason, address in BY_REASON.items():
            rows = suppression.listing(reason=reason)
            assert hasattr(rows, "query"), "still a queryset — the page is taken in the DATABASE"
            assert [one.address for one in rows] == [address], reason


def test_an_unknown_reason_narrows_to_nothing_rather_than_widening_to_all(brazos, dana):
    """⚠ THE OPPOSITE OF `state`, ON PURPOSE.

    `state` falls back to ACTIVE for a word this product does not have, because
    a list has to show a clerk their work. `reason` has no default to fall back
    TO, and falling back to *every reason* would show a clerk four rows over a
    chip that says one — a filter that silently does nothing is worse than one
    that returns nothing, because nothing is visible and doing nothing is not.
    """
    with tenant_ctx(brazos):
        seed_one_per_reason(brazos, dana)

        assert list(suppression.listing(reason="spam_probably")) == []
        assert len(list(suppression.listing())) == 4, "and the unfiltered list is untouched"


def test_reason_and_state_narrow_together_over_http(brazos, dana):
    """The two chips a clerk actually combines: *complaints, including released*.

    Over the view, because `f.reason` reaching `listing()` is a separate claim
    from `listing()` honouring it — the defect this closes was that the
    parameter had nowhere to go.
    """
    with tenant_ctx(brazos):
        seed_one_per_reason(brazos, dana)
        released = suppression.suppress(
            channel=models.CHANNEL_EMAIL,
            address="was.a.typo@example.com",
            reason=suppression_models.REASON_HARD_BOUNCE,
            at=NOW,
            actor=dana,
        )
        suppression.release(suppression_id=released.id, actor=dana, at=NOW, note="typo, fixed")

    response = call(
        notifications_api.suppressions,
        "get",
        brazos,
        dana,
        query={"f.reason": suppression_models.REASON_HARD_BOUNCE, "f.state": suppression.STATE_ALL},
    )

    assert response.status_code == 200
    addresses = [row["address"] for row in response.data["results"]]
    assert addresses == ["typo@exmaple.com", "was.a.typo@example.com"], (
        "both hard bounces, active before released — and neither the complaint nor the "
        "unsubscribe nor the manual row"
    )
    states = {row["state"] for row in response.data["results"]}
    assert states == {"active", "released"}


def test_the_vocabulary_the_screen_builds_its_chips_from_is_served_with_the_list(brazos, dana):
    """A dropdown built from a hard-coded copy of these tuples is a second home
    for the reason set — the view says so in its own words, and the screen
    depends on it being true."""
    with tenant_ctx(brazos):
        seed_one_per_reason(brazos, dana)

    response = call(notifications_api.suppressions, "get", brazos, dana)

    vocabulary = response.data["vocabulary"]
    assert vocabulary["reasons"] == list(suppression_models.REASONS)
    assert vocabulary["states"] == list(suppression.STATES)
    assert "soft_bounce" not in vocabulary["reasons"], (
        "a soft bounce can never produce a suppression, so it can never be a filter on the "
        "list of them"
    )


def test_a_released_row_carries_the_history_the_screen_shows(brazos, dana):
    """The row is KEPT and stamped, and the screen shows that rather than hiding
    it — which is the whole reason a release is not a delete.

    `released_note` is the one field in the table that is a person's own words,
    and a screen that dropped it would leave the durable record answering *when*
    without *why*.
    """
    with tenant_ctx(brazos):
        row = suppression.suppress(
            channel=models.CHANNEL_EMAIL,
            address="marta.whitfeild@example.com",
            reason=suppression_models.REASON_HARD_BOUNCE,
            at=NOW,
            actor=dana,
        )
        suppression.release(
            suppression_id=row.id, actor=dana, at=NOW, note="typo, corrected on the account"
        )

    response = call(
        notifications_api.suppressions,
        "get",
        brazos,
        dana,
        query={"f.state": suppression.STATE_RELEASED},
    )

    served = response.data["results"][0]
    assert served["state"] == "released"
    assert served["released_at"] is not None
    assert served["released_note"] == "typo, corrected on the account"
    assert served["suppressed_at"] is not None
    assert served["reason"] == suppression_models.REASON_HARD_BOUNCE
    assert uuid.UUID(served["id"]), (
        "the id TRAVELS because Release needs it — B14 rule 31 governs what a screen "
        "renders, not what an API serves"
    )


def test_the_route_the_screen_calls_is_actually_mounted(brazos):
    """HARD-WON LAW 2 at the routing layer, for the two paths this screen uses.

    Resolved through the REAL root URLconf, not by reading `urlpatterns` — a
    module exporting a pattern is not an endpoint until `config/urls.py`
    includes it.
    """
    from django.urls import resolve

    suppression_id = uuid.uuid4()
    assert resolve("/api/brazosbend/suppressions").func == notifications_api.suppressions
    assert (
        resolve(f"/api/brazosbend/suppressions/{suppression_id}/release").func
        == notifications_api.suppression_release
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-NOT-5637 (12-governance/10-defect-log.csv) · apps/notifications/suppression.py + suppression_models.py · apps/notifications/api.py (`suppressions`, `suppression_release`) · tests/test_def_not_5632_suppression.py (the contract this does not restate) · 04-docs/02-decisions/14-ui-conventions.md rules 21/31/33/35
# generated: 2026-09-17 by an AI lane (the blocked-addresses screen)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: every case proved RED FIRST through pytest — the harness that runs it, never `python3 <file>` (law 7). The sabotage for the first three was removing `if reason:` from `suppression.listing`; for the fourth, removing `reasons` from the served vocabulary; for the fifth, `released_note` from the serialiser; for the sixth, deleting the two `path(...)` lines. Each failure is quoted in the lane report.
# exceptions: (1) RLS IS NOT PROVED HERE — sqlite has no row-level security, and `test_def_not_5632_suppression.py` already owns the tenant-scoping SHAPE case and says the same thing. (2) NOTHING WRITES A SUPPRESSION AUTOMATICALLY ON THIS DEPLOYMENT (BR-NOT-013 holds, no provider adapter exists), so every row these cases read was written by `suppress()` directly — said out loud rather than implied (law 2).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
