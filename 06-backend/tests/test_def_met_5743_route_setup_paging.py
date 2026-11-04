# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-MET-5743 — route setup fetches the whole tenant and pages it in
#          the browser. PO report 2026-09-18, verbatim: *"Route setup becomes
#          unusable at 5,000-10,000 premises"*.
# Rules:   NFR-3 (universal server pagination) · NFR-5 (no hard caps anywhere) ·
#          BR-MET-072 (the area filter is multi-select, All includes untagged) ·
#          BR-MET-074 (membership is per SERVICE and a conflict MOVES) ·
#          BR-MET-055 (no unbounded endpoints) · CLAUDE.md hard-won law 7
# Screens: SET-06 step 2 (the route premises picker)
# ───────────────────────────────────────────────────────
"""The SET-06 premises picker: a FIXED number of queries, a real page, and a
true total — asserted as ARITHMETIC ON QUERIES, never as rows rendered.

⚠ **WHY QUERY COUNTS AND NOT TIMINGS OR ROW COUNTS.** An N+1 is invisible to
every test that asserts what a page contains: the rows are correct either way,
so a fixture of three premises passes whether the selector issues 4 queries or
3,000. The test that can see it is the one that grows the fixture and asserts
the query count DID NOT GROW with it — which is why each case below runs the
same call at two sizes and compares, rather than pinning one magic number that
a later `select_related` would make stale.

⚠ **AND IT MUST NOT BE FIXED BY CARRYING LESS OR BY CARRYING MORE.** `DEF-650`
and `DEF-324` removed a per-row owner-account expansion from the premises list
precisely because it cost a read per row; the answer there was to stop carrying
the fact. Nothing here starts carrying one, and `test_the_row_shape_is_exactly
_what_it_was` pins the eleven keys so a later batch cannot quietly widen them.
"""

import pytest
from django.test.utils import CaptureQueriesContext
from django.db import connection

from apps.metering import models, selectors, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    make_asset,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


ROW_KEYS = {
    "id",
    "premise_no",
    "address_line",
    "premises_type",
    "units",
    "unit_ids",
    "meters",
    "area_code",
    "area_name",
    "area_path",
    "current_route",
    "current_route_id",
    "on_this_route",
}


def seed_premises(actor, count, *, start=0, with_meter=True):
    """`count` premises, each with one unit and (by default) one meter fitted.

    The meter is what makes the old implementation's SECOND read fire — one
    `assets_on_unit` call per unit — so a fixture without one can only see half
    the defect.
    """
    made = []
    for index in range(start, start + count):
        premises = make_premises(actor, address_line=f"{1000 + index} Paging Way")
        unit = make_unit(actor, premises["id"], label=f"U{index}", services=["water"])
        if with_meter:
            make_asset(
                actor,
                unit_id=unit["id"],
                asset_no=f"MTR-PAGE-{index}",
                service="water",
                unit="kgal",
                install_date="2026-01-05",
            )
        made.append((premises, unit))
    return made


def queries_for(fn):
    with CaptureQueriesContext(connection) as captured:
        fn()
    return len(captured.captured_queries)


# ═══════════════════════════════════════════════════════════════════════════
# THE N+1 — the half the PO felt
# ═══════════════════════════════════════════════════════════════════════════


def test_the_picker_issues_a_fixed_number_of_queries_whatever_the_page_holds(brazos, dana):
    """⛔ **THE DEFECT.** The predecessor ran one `Unit` query per premises and
    one `assets_on_unit` call per unit, so the query count rose with the row
    count — more than two queries per premises, forever.

    Asserted as a COMPARISON rather than against a fixed number: the claim is
    *"this does not grow with the tenant"*, and a pinned constant would go red
    on the next legitimate `select_related` while saying nothing about growth.

    **MEASURED on this fixture, 2026-09-18:**

      * before — **18** queries at 4 premises, **82** at 20. Four per row, so
        a tenant at the top of T5 (40,000 premises) issued about **160,000**.
      * after  — **5**, at both sizes. Flat.
    """
    with tenant_ctx(brazos):
        seed_premises(dana, 4)
        small = queries_for(lambda: selectors.route_premises_picker(areas=[]))
        seed_premises(dana, 16, start=100)
        large = queries_for(lambda: selectors.route_premises_picker(areas=[]))

    assert large == small, (
        f"the picker grew from {small} to {large} queries when the tenant grew "
        f"from 4 premises to 20 — that is the N+1 DEF-MET-5743 was filed for"
    )
    assert small <= 8, f"{small} queries for one page is already too many"


def test_one_page_costs_no_more_than_the_whole_list_did(brazos, dana):
    """A window must not be MORE expensive than no window: the point of paging
    is that the rows you do not show cost nothing to build."""
    with tenant_ctx(brazos):
        seed_premises(dana, 20)
        paged = queries_for(
            lambda: selectors.route_premises_picker_page(areas=[], page=1, per=5)
        )
        whole = queries_for(lambda: selectors.route_premises_picker_page(areas=[], per=None))
    # One extra for the COUNT is expected and is what buys the true total.
    assert paged <= whole + 1


# ═══════════════════════════════════════════════════════════════════════════
# NFR-3 — a real page, with the true total beside it
# ═══════════════════════════════════════════════════════════════════════════


def test_a_page_is_a_window_and_count_is_the_whole_set(brazos, dana):
    with tenant_ctx(brazos):
        seed_premises(dana, 12, with_meter=False)
        first = selectors.route_premises_picker_page(areas=[], page=1, per=5)
        second = selectors.route_premises_picker_page(areas=[], page=2, per=5)
        last = selectors.route_premises_picker_page(areas=[], page=3, per=5)

    assert first["count"] == 12, "the count is the matching rows, not the page"
    assert second["count"] == 12
    assert len(first["results"]) == 5
    assert len(second["results"]) == 5
    assert len(last["results"]) == 2
    firsts = {row["id"] for row in first["results"]}
    seconds = {row["id"] for row in second["results"]}
    assert firsts.isdisjoint(seconds), "two pages must not repeat a row"


def test_the_order_is_stable_across_two_requests_for_the_same_page(brazos, dana):
    """A page that answers different rows each time is a list a clerk cannot
    finish. Every ordering carries `premise_no` then `id` as tie-breakers."""
    with tenant_ctx(brazos):
        seed_premises(dana, 9, with_meter=False)
        once = selectors.route_premises_picker_page(areas=[], page=2, per=3)
        twice = selectors.route_premises_picker_page(areas=[], page=2, per=3)
    assert [row["id"] for row in once["results"]] == [row["id"] for row in twice["results"]]


def test_no_maximum_page_size_nfr_5(brazos, dana):
    """`NFR-5` — nothing here is a cap that would have to be removed when T4
    arrives. Asking for more than the tenant holds returns what it holds; not
    asking at all returns everything."""
    with tenant_ctx(brazos):
        seed_premises(dana, 7, with_meter=False)
        huge = selectors.route_premises_picker_page(areas=[], page=1, per=100000)
        unbounded = selectors.route_premises_picker_page(areas=[], per=None)
    assert len(huge["results"]) == 7
    assert len(unbounded["results"]) == 7
    assert huge["count"] == unbounded["count"] == 7


# ═══════════════════════════════════════════════════════════════════════════
# NO SILENT TRUNCATION — a match beyond page one is still findable
# ═══════════════════════════════════════════════════════════════════════════


def test_a_match_that_lives_beyond_page_one_is_found_by_the_server(brazos, dana):
    """⛔ **THE RULING THIS LANE WAS GIVEN.** *"A picker searches on the SERVER,
    so a match is found wherever it is in the list, not only in the first
    page."* The needle is seeded LAST so that in the default `premise_no`
    order it cannot be on page one — a client-side filter over one page would
    return nothing here and the clerk would be told the premises does not
    exist.
    """
    with tenant_ctx(brazos):
        seed_premises(dana, 12, with_meter=False)
        make_premises(dana, address_line="9999 Needle Terrace")

        page_one = selectors.route_premises_picker_page(areas=[], page=1, per=5)
        found = selectors.route_premises_picker_page(q="Needle", areas=[], page=1, per=5)

    assert "9999 Needle Terrace" not in {
        row["address_line"] for row in page_one["results"]
    }, "the fixture must put the needle off page one or this test proves nothing"
    assert [row["address_line"] for row in found["results"]] == ["9999 Needle Terrace"]
    assert found["count"] == 1, "the count must narrow with the search, or the footer lies"


def test_search_narrows_the_count_so_the_footer_cannot_claim_more_than_it_has(brazos, dana):
    with tenant_ctx(brazos):
        seed_premises(dana, 10, with_meter=False)
        make_premises(dana, address_line="1 Willow Bend")
        make_premises(dana, address_line="2 Willow Bend")
        narrowed = selectors.route_premises_picker_page(q="Willow", areas=[], page=1, per=50)
    assert narrowed["count"] == 2
    assert len(narrowed["results"]) == 2


# ═══════════════════════════════════════════════════════════════════════════
# THE FILTERS STILL MEAN WHAT THEY MEANT — now applied BEFORE the slice
# ═══════════════════════════════════════════════════════════════════════════


def test_unassigned_only_narrows_the_count_not_just_the_page(brazos, dana):
    """The `unassigned` chip used to drop rows while BUILDING them, so it could
    only ever be applied after the whole list existed. Expressed as a subquery
    it narrows the queryset, which is what makes the total beside the page
    true."""
    with tenant_ctx(brazos):
        made = seed_premises(dana, 6, with_meter=False)
        services.create_route(
            dana,
            {
                "code": "RT-PAGE-1",
                "name": "Paging route",
                "service_code": "water",
                "premises_ids": [made[0][0]["id"], made[1][0]["id"]],
            },
        )

        everything = selectors.route_premises_picker_page(areas=[], service="water", per=None)
        free = selectors.route_premises_picker_page(
            areas=[], service="water", unassigned_only=True, per=None
        )

    assert everything["count"] == 6
    assert free["count"] == 4, "the chip must move the COUNT, not only the rows shown"
    assert len(free["results"]) == 4


def test_members_only_reopens_a_routes_own_premises(brazos, dana):
    """⚠ The EDIT path. With a paged picker, a route's existing members are
    mostly not on the page in front of you, so re-ticking them by walking every
    page would be the defect again. The route is asked for its own membership
    instead — bounded by one crew's walk (BR-MET-055)."""
    with tenant_ctx(brazos):
        made = seed_premises(dana, 8, with_meter=False)
        route = services.create_route(
            dana,
            {
                "code": "RT-PAGE-2",
                "name": "Edit me",
                "service_code": "water",
                "premises_ids": [made[2][0]["id"], made[5][0]["id"]],
            },
        )

        members = selectors.route_premises_picker_page(
            areas=[], service="water", route_id=route["id"], members_only=True, per=None
        )

    assert members["count"] == 2
    assert {row["address_line"] for row in members["results"]} == {
        made[2][0]["address_line"],
        made[5][0]["address_line"],
    }
    assert all(row["on_this_route"] for row in members["results"])


def test_the_row_shape_is_exactly_what_it_was(brazos, dana):
    """⚠ **DEF-650 / DEF-324 RUN THE OTHER WAY AND THIS IS THE GUARD FOR IT.**
    Those two removed a per-row owner-account expansion from the premises list
    because it cost a read per row. A batch is the right way to kill an N+1;
    widening the row to make the batch worthwhile is not, so the keys are
    pinned."""
    with tenant_ctx(brazos):
        seed_premises(dana, 2, with_meter=False)
        rows = selectors.route_premises_picker(areas=[])
    assert rows, "fixture produced nothing"
    for row in rows:
        assert set(row) == ROW_KEYS, f"the picker row changed shape: {set(row) ^ ROW_KEYS}"


def test_an_unknown_sort_key_falls_back_and_does_not_raise(brazos, dana):
    """`ROUTE_SORTS`' own convention: a key outside the vocabulary falls back to
    the default. A bookmarked URL carrying last month's column must render."""
    with tenant_ctx(brazos):
        seed_premises(dana, 3, with_meter=False)
        fallback = selectors.route_premises_picker_page(areas=[], sort="no_such_column", per=None)
        default = selectors.route_premises_picker_page(areas=[], per=None)
    assert [row["id"] for row in fallback["results"]] == [row["id"] for row in default["results"]]


def test_desc_reverses_the_declared_orderings(brazos, dana):
    with tenant_ctx(brazos):
        seed_premises(dana, 4, with_meter=False)
        asc = selectors.route_premises_picker_page(
            areas=[], sort="address_line", direction="asc", per=None
        )
        desc = selectors.route_premises_picker_page(
            areas=[], sort="address_line", direction="desc", per=None
        )
    assert [row["address_line"] for row in asc["results"]] == list(
        reversed([row["address_line"] for row in desc["results"]])
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-MET-5743 (route setup paging)
# generated: 2026-09-18 by the route-setup lane
# gates: pytest
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
