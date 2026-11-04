# ── Trace ──────────────────────────────────────────────
# Change:  Meter Reads blueprint entry 15 — *Read cycles — the list*, drawn
#          2026-09-12/13, built 2026-09-14. Callout ② (search covers the cycle
#          code AND the route code) and the two ⇅ the drawing adds to columns
#          that had no sort key (Read window · Bill date).
# Rules:   BR-MET-010 (a cycle's route list is exactly the routes assigned to
#          it) · BR-MET-011 CONFIRMED-AS-NARROWED (the operational view writes
#          no definition) · BR-SHL-011 (the `q` / `sort` / `dir` grammar, applied
#          ON THE SERVER) · NFR-3 (universal server pagination) · NFR-5 (no hard
#          caps) · B14 rules 12 · 13 · 19 · CLAUDE.md hard rule 1
# ───────────────────────────────────────────────────────
"""**THE SERVER DOES THE SEARCHING AND THE SORTING, OR ENTRY 15 IS A LIE.**

Entry 15 replaces a table with no toolbar at all and a pager that ran in the
browser over a fetch-everything read — the `NFR-3` breach the blueprint names.
The whole value of the change is that the four controls narrow and order the
WHOLE result set, so every case here asserts on what `cycles_page` returns for
the whole set rather than on a page of it.

**FOUR PROPERTIES, AND EACH ONE IS A DIFFERENT WAY TO BE WRONG:**

  1. the search matches a ROUTE code — callout ②'s own words, and the identifier
     a reader actually carries in their hand;
  2. it matches it ONCE — a cycle with three matching routes is one row, not
     three, because `_page` paginates what this returns;
  3. `read_window` orders by the window's start — the alias exists so a column
     headed *Read window* does not have to send `sort=start_day`;
  4. `bill_date` orders by a DERIVED value and puts the cycles that have none
     LAST, in a list where `None` beside a date string is a `TypeError` and a
     500 rather than a bad order.

⚠ **RED PROVED FIRST, IN THE HARNESS THAT RUNS IT (hard-won law 7).** Every case
was run against the pinned tip `ab939d32` in a private worktree, through
`python3.12 -m pytest`, which is the command the lane runs — not through an
ad-hoc import. The failures are quoted in the lane report; the interesting one
is case 4, which did not assert-fail at all but raised
`TypeError: '<' not supported between instances of 'NoneType' and 'str'`, which
is what the production list would have answered.
"""

from datetime import date

import pytest

from apps.metering import models as metering_models
from apps.metering import selectors as metering_selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    lonestar,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _cycle(tenant, *, code, **kwargs):
    return metering_models.Cycle.objects.create(
        tenant=tenant, code=code, name=kwargs.pop("name", f"Cycle {code}"), **kwargs
    )


def _route(tenant, *, code, cycle):
    return metering_models.Route.objects.create(
        tenant=tenant, code=code, name=f"Walk {code}", route_type="walk", cycle=cycle
    )


# ════════════════════════════════════════════════════════════════════════════
# ② · THE SEARCH COVERS THE ROUTE CODE
# ════════════════════════════════════════════════════════════════════════════
def test_the_cycles_search_finds_a_cycle_by_its_ROUTE_code(brazos, marcus):
    """Entry 15 callout ②, verbatim: *"Search · cycle code and route code"*.

    A clerk holding a route sheet knows `RT-004`. Before this the box matched
    the cycle code and the cycle name and nothing else, so the one identifier
    on the row that a person carries around was the one thing it could not find.
    """
    with tenant_ctx(brazos):
        owner = _cycle(brazos, code="CY-001", frequency="Monthly")
        other = _cycle(brazos, code="CY-003", frequency="Quarterly")
        _route(brazos, code="RT-004", cycle=owner)
        _route(brazos, code="RT-009", cycle=other)

        rows = metering_selectors.cycles_page(q="RT-004")
        assert [row["code"] for row in rows] == ["CY-001"]
        # …and the row carries the route it was found by, so the answer is
        # legible rather than mysterious (BR-MET-010 — derived, never stored).
        assert rows[0]["routes"] == ["RT-004"]


def test_the_route_search_still_finds_a_cycle_by_its_OWN_code_and_name(brazos, marcus):
    """A widened search that lost its original two legs would be a worse box
    than the one it replaces. Both survive."""
    with tenant_ctx(brazos):
        _cycle(brazos, code="CY-001", name="North monthly", frequency="Monthly")
        _cycle(brazos, code="CY-003", name="South quarterly", frequency="Quarterly")

        assert [r["code"] for r in metering_selectors.cycles_page(q="CY-003")] == ["CY-003"]
        assert [r["code"] for r in metering_selectors.cycles_page(q="North")] == ["CY-001"]


def test_a_cycle_with_THREE_matching_routes_is_ONE_row(brazos, marcus):
    """⚠ **THE JOIN DUPLICATES AND `_page` PAGINATES WHAT THIS RETURNS.**

    Without `.distinct()` a cycle whose routes all share a prefix comes back
    once per matching route — real rows on a real page, under a `count` that
    agrees with them, so nothing anywhere looks wrong. `RT-0` matches all three
    routes of CY-001; the list is one row long.
    """
    with tenant_ctx(brazos):
        owner = _cycle(brazos, code="CY-001", frequency="Monthly")
        _route(brazos, code="RT-001", cycle=owner)
        _route(brazos, code="RT-002", cycle=owner)
        _route(brazos, code="RT-003", cycle=owner)

        rows = metering_selectors.cycles_page(q="RT-0")
        assert [row["code"] for row in rows] == ["CY-001"]


def test_the_route_search_cannot_see_another_tenants_routes(brazos, lonestar, marcus):
    """Hard rule 1, restated over the new leg: a wider search is not a way
    around RLS. The join reaches `routes`, which is tenant-scoped too."""
    with tenant_ctx(brazos):
        owner = _cycle(brazos, code="CY-001", frequency="Monthly")
        _route(brazos, code="RT-004", cycle=owner)
    with tenant_ctx(lonestar):
        assert metering_selectors.cycles_page(q="RT-004") == []


# ════════════════════════════════════════════════════════════════════════════
# THE TWO ⇅ THE DRAWING ADDS — `read_window` AND `bill_date`
# ════════════════════════════════════════════════════════════════════════════
def test_read_window_sorts_by_the_windows_start(brazos, marcus):
    """The drawing puts a ⇅ on **Read window**, and the window IS start day +
    days-to-complete (B17 §2). The key exists under the screen's own word so a
    column headed *Read window* does not send `sort=start_day` — the silent
    mismatch `SET-05.cycles` already had to write a paragraph about.

    ⚠ **THE CODES ARE DELIBERATELY IN THE OPPOSITE ORDER TO THE WINDOWS.**
    `parse_list_params` drops an unknown sort and `cycles_page` falls back to
    `code`, so a fixture whose alphabetical order happened to agree with its
    window order would have PASSED on a server that never heard of this key —
    which is what the first draft of this case did, at the pinned tip.
    """
    with tenant_ctx(brazos):
        _cycle(brazos, code="CY-AAA", frequency="Monthly", start_day=20, days_to_complete=4)
        _cycle(brazos, code="CY-ZZZ", frequency="Monthly", start_day=1, days_to_complete=3)

        asc = metering_selectors.cycles_page(sort="read_window", direction="asc")
        assert [row["code"] for row in asc] == ["CY-ZZZ", "CY-AAA"]

        desc = metering_selectors.cycles_page(sort="read_window", direction="desc")
        assert [row["code"] for row in desc] == ["CY-AAA", "CY-ZZZ"]


def test_bill_date_sorts_on_a_DERIVED_value(brazos, marcus):
    """**`bill_date` is not a column.** It is derived from the cycle's bill DAY
    and the period its next window covers (OQ-344), so it sorts on the built
    page exactly as `accounts` does — and that is still a sort of the WHOLE
    list, because `cycles_page` builds every row before `_page` slices one.

    ⚠ **CODES OPPOSITE TO BILL DATES, for the reason the case above gives:** an
    unknown sort falls back to `code`, so agreeing fixtures would pass on a
    server that cannot do this at all.
    """
    with tenant_ctx(brazos):
        _cycle(
            brazos,
            code="CY-AAA",
            frequency="Monthly",
            start_day=1,
            days_to_complete=3,
            bill_day=25,
            first_run_date=date(2026, 9, 1),
        )
        _cycle(
            brazos,
            code="CY-ZZZ",
            frequency="Monthly",
            start_day=1,
            days_to_complete=3,
            bill_day=5,
            first_run_date=date(2026, 9, 1),
        )

        rows = metering_selectors.cycles_page(sort="bill_date", direction="asc")
        dates = [row["bill_date"] for row in rows]
        assert all(value is not None for value in dates), dates
        assert dates == sorted(dates)
        assert [row["code"] for row in rows] == ["CY-ZZZ", "CY-AAA"]


def test_a_cycle_with_NO_bill_date_sorts_last_and_never_raises(brazos, marcus):
    """⚠ **THIS CASE HAS TWO RED PROOFS BECAUSE IT GUARDS TWO THINGS, AND ONLY
    THE SECOND ONE IS A 500.**

    A cycle with no bill day, or none with a next period, has `bill_date: None`.

      * **At the pinned tip** `ab939d32` it fails on the ORDER: `bill_date` is
        not a sort key, `parse_list_params` drops it, the list falls back to
        `code` and answers `['CY-BARE', 'CY-DATED']`.
      * **With the key added and the one-term sort still in place** it raises
        `TypeError: '<' not supported between instances of 'NoneType' and
        'str'` — a 500 on the list rather than a bad order. That term is total
        over `accounts`, which is always an int, and it stops being total the
        moment a derived key can be absent. Proved in the worktree by adding
        only `"bill_date": None` to `CYCLE_SORTS`.
    """
    with tenant_ctx(brazos):
        _cycle(
            brazos,
            code="CY-DATED",
            frequency="Monthly",
            start_day=1,
            days_to_complete=3,
            bill_day=5,
            first_run_date=date(2026, 9, 1),
        )
        # No bill day and no first run — nothing to derive a bill date from.
        _cycle(brazos, code="CY-BARE", frequency="Monthly")

        rows = metering_selectors.cycles_page(sort="bill_date", direction="asc")
        assert [row["code"] for row in rows] == ["CY-DATED", "CY-BARE"]
        assert rows[-1]["bill_date"] is None


def test_the_sort_vocabulary_carries_both_new_keys_and_nothing_is_dropped(brazos, marcus):
    """BR-SHL-010 — a screen may only declare a sort the server answers, so the
    vocabulary is asserted by name. The six that were here keep their places:
    this widens the set, it does not rewrite it."""
    assert "read_window" in metering_selectors.CYCLE_SORTS
    assert "bill_date" in metering_selectors.CYCLE_SORTS
    for existing in (
        "code",
        "name",
        "frequency",
        "start_day",
        "days_to_complete",
        "lifecycle_status",
        "accounts",
    ):
        assert existing in metering_selectors.CYCLE_SORTS, existing
    assert metering_selectors.CYCLE_DEFAULT_SORT == "code"


# ── Lifecycle ─────────────────────────────────────────────
# packet: Meter Reads blueprint entries 14 + 15 (the Read cycles lane)
# generated: 2026-09-14 by the reads routes/cycles lane
# gates: pytest (python3.12, JOBS_EAGER=false --reuse-db)
# exceptions: E3 nothing here exercises entry 15's callouts ④ and ⑤ — the
#   Registers-collected figure and the Window pill are NOT BUILT, under
#   DEF-MET-5206 and the PO's ruling of 2026-09-14 ("Settle first."), because
#   both derive from a cycle's current window and two derivations of that
#   disagree. A test written against either derivation today would pin the fork
#   rather than measure it.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
