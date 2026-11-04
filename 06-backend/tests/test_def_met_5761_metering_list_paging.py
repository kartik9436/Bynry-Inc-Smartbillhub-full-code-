# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-MET-5761 — `_page()` in apps/metering/api.py called `list(rows)`,
#           so premises, units, premises-owners and reads built EVERY row the
#           tenant has before the paginator kept fifty; and
#           `selectors.premises_rollup` derived vacancy with one account read per
#           unit in the tenant, on the header of `GET /premises`.
# Rules:    NFR-3 (universal server pagination) · NFR-5 (no hard caps) ·
#           BR-SHL-011 (an out-of-range page CLAMPS and never errors) ·
#           BR-MET-036 (occupancy is DERIVED — no stored column) ·
#           DEF-650 / DEF-324 (the premises LIST does not expand the owner's
#           account: `premises_detail_dict(row, with_owner_account=False)`)
# Tests:    this file
# Impacts:  apps/metering/api.py (_page, _parsed, _prepaged, units) ·
#           apps/metering/selectors.py (units_queryset, units_list_is_sql_pageable,
#           units_page, premises_rollup)
# ───────────────────────────────────────────────────────
"""DEF-MET-5761 — the metering lists take their page in SQL.

RED-FIRST PROOF (hard-won law 7, and in the harness that runs it — `pytest`,
not a `__main__`). Every case below was run against a second worktree pinned at
the tip this lane started from. The before/after numbers are in the lane report.

⚠ **A TEST THAT COUNTS RETURNED ROWS CANNOT SEE THIS DEFECT AND THAT IS WHY IT
SURVIVED.** A Python slice of a fully-built list returns exactly the same fifty
rows as a `LIMIT`, so every existing assertion in the metering suite passes on
both. There are therefore only two honest questions, and each case asks one:

  * **does the database do the slicing?** — asserted on the SQL, because that is
    the only place the difference is visible. A list read whose `SELECT` from
    its own table carries no `LIMIT` has fetched the whole table, whatever the
    response envelope then says.
  * **does the cost follow the size of the tenant?** — asserted as *the count
    did not move*, never as a literal. An equality against a number goes red
    when an unrelated lane adds a `select_related`, which teaches the next
    reader to edit the number rather than to look; and a count measured once
    would pass forever on a seeded tenant of 79 properties. What `NFR-3`
    promises is that the cost is INDEPENDENT of how big the tenant is, so each
    case builds a bigger population and asserts the count did not follow it.

⚠ **ONE CASE HERE WAS ALREADY GREEN BEFORE THIS LANE, DELIBERATELY.** The
address picker (`GET /premises/picker`) has handed the paginator an unevaluated
queryset since `fe08a6c3c` (2026-09-16) and says so in its own docstring — in
PROSE, which nothing re-checks. `test_address_picker_slices_in_sql` is that
sentence turned into a check, so the next lane that reaches for `_page` there
finds out at merge instead of at 40,000 properties.
"""

from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.metering import api, selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    api_call,
    make_asset,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


# ── reading the SQL ─────────────────────────────────────────────────────────
def _selects_from(captured, table):
    """Every SELECT in `captured` that reads `table` as a table, not as a join
    target — enough to tell the list's own read from the per-row ones."""
    needle = f'FROM "{table}"'
    return [q["sql"] for q in captured.captured_queries if needle in q["sql"]]


def _has_limited_select(captured, table):
    """Did the DATABASE take the page for `table`?

    A `COUNT(*)` is excluded: the paginator issues one, it legitimately reads
    the whole table, and counting it as the page read would make this assertion
    pass over the exact defect it exists for.
    """
    return any(
        "LIMIT" in sql and "COUNT(" not in sql.upper() for sql in _selects_from(captured, table)
    )


def _call(view, tenant, **kwargs):
    return api_call(
        view, "get", user=FakeUser(), role="system_admin", tenant=tenant, **kwargs
    )


# ── population ──────────────────────────────────────────────────────────────
def _premises(actor, count, *, start=0):
    return [
        make_premises(
            actor,
            address_line=f"{100 + start + i} Paging Way",
            owner_manager=f"Paging Owner {start + i}",
        )
        for i in range(count)
    ]


# ── 1 · the four list reads slice in SQL ────────────────────────────────────
def test_premises_list_slices_in_sql(brazos, dana):
    """`GET /premises` — RED before this lane: the only SELECT from `premises`
    was the unbounded one `list(rows)` forced."""
    with tenant_ctx(brazos):
        _premises(dana, 3)
    _call(api.premises, brazos)  # warm any lazily-resolved seam/catalog read
    with CaptureQueriesContext(connection) as captured:
        response = _call(api.premises, brazos)
    assert response.status_code == 200
    assert _has_limited_select(captured, "premises"), _selects_from(captured, "premises")


def test_units_list_slices_in_sql(brazos, dana):
    """`GET /units` — RED before this lane: `list(selectors.units_list(...))`."""
    with tenant_ctx(brazos):
        premise = _premises(dana, 1)[0]
        for i in range(3):
            make_unit(dana, premise["id"], label=f"Unit {i}")
    with CaptureQueriesContext(connection) as captured:
        response = _call(api.units, brazos)
    assert response.status_code == 200
    assert _has_limited_select(captured, "units"), _selects_from(captured, "units")


def test_premises_owners_list_slices_in_sql(brazos, dana):
    """`GET /premises-owners` — the picker serves this 200 at a time."""
    with tenant_ctx(brazos):
        _premises(dana, 3)
    with CaptureQueriesContext(connection) as captured:
        response = _call(api.premises_owners, brazos)
    assert response.status_code == 200
    assert _has_limited_select(captured, "premises_owners"), _selects_from(
        captured, "premises_owners"
    )


def test_reads_list_slices_in_sql(brazos, dana):
    """`GET /reads` — the hot window is BOUNDED (`BR-MET-055`) and was fetched
    whole inside that bound.

    ⚠ **A ROW HAS TO EXIST FOR THIS CASE TO MEAN ANYTHING, AND FINDING THAT OUT
    IS WORTH THE LINE.** Written against an empty table it PASSED on the fixed
    code and could never have failed on the broken one: Django's paginator
    collapses `top` to `self.count`, so a count of zero makes the page slice
    `[0:0]`, the compiler raises `EmptyResultSet` and **no second query is
    issued at all**. The assertion was then reading a `COUNT(*)` and an absence
    — hard-won law 7's *structurally incapable of failing*, met while writing a
    test for law 7.

    ⚠ **THE COLD PATH IS WHERE THIS COST THE MOST.**
    `selectors.ReadArchiveResultSet` was built with `count()` and `__getitem__`
    precisely so the paginator could page a detached partition; `list(rows)`
    reached its `__iter__` instead, which is `self[0:None]` — a union SELECT
    over every archived partition with no `LIMIT` clause at all.
    """
    from apps.metering import models as met_models

    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="M-PAGE-1")
        met_models.MeterRead.objects.create(
            tenant_id=brazos.id,
            asset_id=asset["id"],
            read_at=timezone.now(),
            current_value=Decimal("100"),
        )
    with CaptureQueriesContext(connection) as captured:
        response = _call(api.reads, brazos)
    assert response.status_code == 200
    assert response.data["count"] == 1
    assert _has_limited_select(captured, "meter_reads"), _selects_from(captured, "meter_reads")


def test_address_picker_slices_in_sql(brazos, dana):
    """`GET /premises/picker` — GREEN BEFORE THIS LANE, ON PURPOSE.

    This is a regression lock, not a fix: the endpoint has handed the paginator
    an unevaluated queryset since `fe08a6c3c` and explains why in its docstring.
    A warning in prose is not a check (hard-won law 1), and the whole point of
    `_page`'s defect is that reaching for the helper here would have been the
    obvious tidy-up.
    """
    with tenant_ctx(brazos):
        _premises(dana, 3)
    with CaptureQueriesContext(connection) as captured:
        response = _call(api.premises_picker, brazos)
    assert response.status_code == 200
    assert _has_limited_select(captured, "premises"), _selects_from(captured, "premises")


# ── 2 · the cost does not follow the tenant ─────────────────────────────────
def test_premises_rollup_cost_does_not_follow_the_unit_count(brazos, dana):
    """The S14 header roll-up — RED before this lane, and by the widest margin.

    `vacant` was `sum(1 for unit in units if occupancy_of(unit) == "vacant")`,
    and `occupancy_of` asks the customers seam PER UNIT. The population grown
    here is UNITS on ONE premises, so the page stays one row and the only thing
    that can move the count is the roll-up.
    """
    with tenant_ctx(brazos):
        premise = _premises(dana, 1)[0]
        for i in range(4):
            make_unit(dana, premise["id"], label=f"Small {i}")
    _call(api.premises, brazos)  # warm any lazily-resolved seam/catalog read
    with CaptureQueriesContext(connection) as small:
        _call(api.premises, brazos)
    with tenant_ctx(brazos):
        for i in range(16):
            make_unit(dana, premise["id"], label=f"Large {i}")
    with CaptureQueriesContext(connection) as large:
        _call(api.premises, brazos)
    assert len(large.captured_queries) == len(small.captured_queries), (
        f"the roll-up followed the tenant: {len(small.captured_queries)} queries over 4 units, "
        f"{len(large.captured_queries)} over 20"
    )


def test_units_list_page_carries_the_limit_and_the_offset(brazos, dana):
    """`GET /units` — the DATABASE takes the page, and `?page=` moves the OFFSET.

    RED before this lane in both halves: there was no `LIMIT` anywhere, so
    there was nothing for an offset to move either. This is the case that tells
    SQL paging from Python paging, and a test counting returned rows cannot:
    both spellings hand back the same fifty.
    """
    with tenant_ctx(brazos):
        premise = _premises(dana, 1)[0]
        for i in range(60):
            make_unit(dana, premise["id"], label=f"Unit {i:03d}")
    with CaptureQueriesContext(connection) as first:
        page_one = _call(api.units, brazos)
    with CaptureQueriesContext(connection) as second:
        page_two = _call(api.units, brazos, query={"page": "2"})

    assert page_one.data["count"] == 60
    assert len(page_one.data["results"]) == 50  # the IS-2 default page size
    assert page_two.data["count"] == 60
    assert len(page_two.data["results"]) == 10

    limited_one = [
        sql for sql in _selects_from(first, "units") if "LIMIT" in sql and "COUNT(" not in sql
    ]
    limited_two = [
        sql for sql in _selects_from(second, "units") if "LIMIT" in sql and "COUNT(" not in sql
    ]
    assert limited_one, _selects_from(first, "units")
    assert limited_two, _selects_from(second, "units")
    assert "LIMIT 50" in limited_one[0]
    assert "OFFSET" not in limited_one[0]  # page 1 needs none
    assert "LIMIT 50" in limited_two[0]
    assert "OFFSET 50" in limited_two[0]

    # The two pages are disjoint and together are the whole set — a page is a
    # window over a TOTAL order, so no row is served twice and none is lost.
    ids_one = [row["id"] for row in page_one.data["results"]]
    ids_two = [row["id"] for row in page_two.data["results"]]
    assert set(ids_one).isdisjoint(ids_two)
    assert len(set(ids_one) | set(ids_two)) == 60


def test_units_list_cost_is_bounded_by_the_page_not_the_tenant(brazos, dana):
    """A BOUND-LOCK, and it is GREEN ON THE OLD CODE — said plainly, because a
    case that cannot fail on the defect it sits beside is worth nothing unless
    the reader knows which job it is doing (hard-won law 7).

    The old reading BUILT every unit and then kept fifty, which is memory and
    row construction rather than round trips, and no query count can see it.
    What this holds is the property that matters once a tenant is past one
    page: doubling the tenant must not move the cost of page 1.

    ⚠ **AND IT RECORDS A RESIDUE THIS LANE DID NOT FIX.** `GET /units` pays
    about THREE queries per served row — `service_points` and its neighbours,
    read once per unit in `unit_list_dict`. Measured on this fixture before the
    page bound applied: **15 queries over 4 units, 63 over 20.** Bounded by the
    page (≈150 for fifty rows) and therefore not `NFR-3`, but it is the shape
    `DEF-2723` recorded on the accounts list and `DEF-5745` records on
    `GET /assets`. Filed separately rather than fixed here, because
    `unit_list_dict` is also every single-row reader's shape.
    """
    with tenant_ctx(brazos):
        premise = _premises(dana, 1)[0]
        for i in range(60):
            make_unit(dana, premise["id"], label=f"Small {i:03d}")
    _call(api.units, brazos)  # warm any lazily-resolved seam/catalog read
    with CaptureQueriesContext(connection) as small:
        first = _call(api.units, brazos)
    with tenant_ctx(brazos):
        for i in range(60):
            make_unit(dana, premise["id"], label=f"Large {i:03d}")
    with CaptureQueriesContext(connection) as large:
        second = _call(api.units, brazos)

    assert first.data["count"] == 60
    assert second.data["count"] == 120
    assert len(first.data["results"]) == 50
    assert len(second.data["results"]) == 50
    assert len(large.captured_queries) == len(small.captured_queries), (
        f"page 1 cost followed the tenant: {len(small.captured_queries)} queries at 60 units, "
        f"{len(large.captured_queries)} at 120"
    )


# ── 3 · the envelope and the clamp did not move ─────────────────────────────
def test_units_envelope_is_the_one_every_other_list_serves(brazos, dana):
    """`_prepaged` serves DRF's four keys (`NFR-3`'s fix must not become a
    client-side special case) — plus ONE named sibling on this list only.

    ⚠ **`service_gap_count` IS THE FIFTH KEY BY PO RULING 2026-09-28**
    (*"the Units 'Missing services' block — filter or leave it. - filter"*,
    shipped in `7ac6768f6`, 2.387.0): the toolbar's shortfall count rides THIS
    envelope on every read. This case asserted "no fifth" and went red that
    commit (green at `ef2bdcf3d`). The four DRF keys are still asserted
    exactly; the fifth is named, so any OTHER extra key still goes red."""
    with tenant_ctx(brazos):
        premise = _premises(dana, 1)[0]
        make_unit(dana, premise["id"], label="Only")
    response = _call(api.units, brazos)
    assert set(response.data) == {"count", "next", "previous", "results", "service_gap_count"}
    assert response.data["count"] == 1
    assert response.data["next"] is None
    assert response.data["previous"] is None
    assert len(response.data["results"]) == 1


def test_units_out_of_range_page_clamps_and_never_errors(brazos, dana):
    """`BR-SHL-011` — a list URL can never 4xx over its params, and an
    out-of-range page CLAMPS.

    ⚠ **THIS IS THE ONE THING `_prepaged` HAD TO RE-IMPLEMENT.**
    `parse_list_params` clamps `page` to ≥ 1 and cannot know the LAST page — it
    has counted nothing. `StandardPagination.get_page_number` does that clamp
    for the paginator path, and a selector that takes its own page has to do it
    itself or `?page=999` serves a blank table with a `previous` link pointing
    at page 998.
    """
    with tenant_ctx(brazos):
        premise = _premises(dana, 1)[0]
        for i in range(3):
            make_unit(dana, premise["id"], label=f"Unit {i}")
    response = _call(api.units, brazos, query={"page": "999"})
    assert response.status_code == 200
    assert response.data["count"] == 3
    assert len(response.data["results"]) == 3  # the LAST page, not an empty one
    assert response.data["next"] is None
    assert response.data["previous"] is None  # page 1 IS the last page here


def test_units_garbage_page_clamps_too(brazos, dana):
    with tenant_ctx(brazos):
        premise = _premises(dana, 1)[0]
        make_unit(dana, premise["id"], label="Only")
    response = _call(api.units, brazos, query={"page": "not-a-number"})
    assert response.status_code == 200
    assert response.data["count"] == 1
    assert len(response.data["results"]) == 1


# ── 4 · the derived filters still answer the same rows ──────────────────────
def test_units_derived_filters_still_take_the_python_path(brazos, dana):
    """`occupancy`, `sub_metered` and `service` partition on values no column
    holds, so `units_page` must fall back to building the set — and must return
    what `units_list` returns, not a SQL approximation of it."""
    with tenant_ctx(brazos):
        premise = _premises(dana, 1)[0]
        for i in range(3):
            make_unit(dana, premise["id"], label=f"Unit {i}")

        assert selectors.units_list_is_sql_pageable({}) is True
        assert selectors.units_list_is_sql_pageable({"premises_id": premise["id"]}) is True
        assert selectors.units_list_is_sql_pageable({"occupancy": "vacant"}) is False
        assert selectors.units_list_is_sql_pageable({"occupancy": "occupied"}) is False
        assert selectors.units_list_is_sql_pageable({"occupancy": "sub_metered"}) is False
        assert selectors.units_list_is_sql_pageable({"service": "water"}) is False
        # `sub_metered` is tested for TRUTHINESS in `units_list`, so the string
        # "false" narrows there — the predicate reproduces that rather than
        # tidying it, or the page and the count would disagree.
        assert selectors.units_list_is_sql_pageable({"sub_metered": "false"}) is False
        # An unrecognised occupancy filters NOTHING in `units_list`, so it is
        # SQL-pageable — the loose reading, reproduced.
        assert selectors.units_list_is_sql_pageable({"occupancy": "nonsense"}) is True

        # No account exists in these fixtures, so BR-MET-036 makes every unit
        # vacant — derived, never stored.
    vacant = _call(api.units, brazos, query={"f.occupancy": "vacant"})
    occupied = _call(api.units, brazos, query={"f.occupancy": "occupied"})
    assert vacant.data["count"] == 3
    assert len(vacant.data["results"]) == 3
    assert occupied.data["count"] == 0
    assert occupied.data["results"] == []


def test_units_derived_page_matches_units_list_order(brazos, dana):
    """The derived branch slices `units_list`'s own ordered output, so page 1
    is its first `per` rows and the count is its length."""
    with tenant_ctx(brazos):
        premise = _premises(dana, 1)[0]
        for i in range(5):
            make_unit(dana, premise["id"], label=f"Unit {i}")
        expected = selectors.units_list(filters={"occupancy": "vacant"})
    response = _call(api.units, brazos, query={"f.occupancy": "vacant"})
    assert response.data["count"] == len(expected)
    assert [row["id"] for row in response.data["results"]] == [str(u.id) for u in expected]


def test_units_sql_page_matches_units_list_order(brazos, dana):
    """And the SQL branch answers the same rows, in the same order, as the
    function every other caller still reads."""
    with tenant_ctx(brazos):
        premise = _premises(dana, 1)[0]
        for i in range(5):
            make_unit(dana, premise["id"], label=f"Unit {i}")
        expected = selectors.units_list()
    response = _call(api.units, brazos)
    assert response.data["count"] == len(expected)
    assert [row["id"] for row in response.data["results"]] == [str(u.id) for u in expected]
