# ── Trace ──────────────────────────────────────────────
# Defects: DEF-5745 (`asset_dict` walks the current assignment, its unit, the
#          service point, the service code and a sub-meter COUNT(*) once per
#          SERVED row, so a page of 40 costs about 201 queries and a page of
#          1,000 about 5,001)
# Rules:   NFR-3 (universal server pagination — the cost follows the PAGE, and
#          a page's cost may not follow its SIZE) · NFR-5 (no hard caps: an id
#          list inlined into one statement is a bind-parameter ceiling) ·
#          hard rule 1 (tenant scoping; every batched read carries tenant_id) ·
#          B1/B8 (assets READS metering through `apps/assets/seams.py`, never a
#          join) · BR-AST-004 (one tab per asset) · BR-AST-026 (the uuid
#          addresses, `asset_no` is what a clerk sees)
# Tests:   this file
# Impacts: apps/assets/selectors.py (`asset_page_rows` · `asset_dict` ·
#          `_current_assignment` · `_service_of` · `_tab_columns` ·
#          `_parent_premises`) · apps/assets/seams.py (`unit_refs`)
# ───────────────────────────────────────────────────────
"""DEF-5745 — one page of registry rows, a FLAT number of reads.

⚠ **THE ROW-SHAPE CASES COME FIRST AND THEY ARE THE POINT.** `asset_dict` is
not only the list row: `apps/assets/services.py` calls it for the `before`/
`after` of every audited write and `asset_detail` builds the S50 header on top
of it. The lane that filed this defect named that as the reason not to touch it
— *"it changes `asset_dict`'s contract and every consumer of a registry row"*.
A pin turns that from a blocker into a managed risk, which is exactly what
`test_def_met_5743_route_setup_paging.py::test_the_row_shape_is_exactly_what_it_was`
did for the route picker, so the same guard is written here FIRST and the batch
is built underneath it.

Two pins, because they fail on different things:

  * the KEY SET per tab, written out as literals — a batch that pays for itself
    by widening the row is not a fix (`DEF-650`/`DEF-324` run that way round);
  * the VALUES, key for key, against `asset_dict(asset)` called one row at a
    time — the un-batched path, which every single-row consumer still uses. A
    literal expectation can be edited to match a regression; this one recomputes
    both sides, so it cannot be.

⚠ **AND THE BUDGET CASES VARY THE PAGE SIZE, NEVER THE POPULATION.** That is
this defect's whole escape route, quoted from its own register row: the NFR-3
case in `test_cr092_registry_paging.py` measures `asset_list` — the QUERYSET —
and asserts *the cost did not move with the population*, which is TRUE here and
always will be, because this cost follows the PAGE. Two correct checks with one
uncovered step between them. So these serve a small page and a large one from
the SAME population and assert the count did not follow.

WHAT WOULD MAKE THESE PASS WRONGLY (hard-won law 7 habit 2), and what stops it:
  * a fixture whose two pages are the same size — asserted unequal, explicitly;
  * a fixture with nothing ASSIGNED, so no unit or service read ever happens —
    asserted: the rows carry a real address and a real service code;
  * an unwired metering seam answering `{}` for everything, which is cheap and
    wrong — the same value assertions catch it;
  * counting outside the work — every count is taken inside
    `CaptureQueriesContext` around the call being measured.

RED-FIRST PROOF (law 7, in the harness that runs it — `pytest`, not a
`__main__`). Against `a402238a2`, the tip this lane started from, with the
per-row reads still in place:

    test_the_page_cost_does_not_follow_the_page_size
        AssertionError: a page of 10 cost 55 queries and a page of 40 cost
        205 — 150 more reads for 30 more rows ...
    test_the_sub_meter_page_does_not_follow_the_page_size
        AssertionError: ... (the sub-meter row pays SEVEN, not five)
    test_the_registry_page_batches_its_cross_row_reads
        AssertionError: 205 queries for 40 rows ...

The three row-shape cases were GREEN before and after: they exist to prove the
batch did not change WHAT the row says, which is the only thing that could make
this a regression rather than a fix.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    make_asset,
    make_premises,
    make_unit,
    tenant_ctx,
)

from apps.assets import selectors  # noqa: E402

pytestmark = pytest.mark.django_db


# ── The row, as it stands on 2026-09-19 ─────────────────────────────────────
#
# Captured from the running selector at `a402238a2` and written out as literals
# on purpose: a set derived from the code under test would agree with any change
# that code ever makes, which is a check that cannot fail.
BASE_KEYS = {
    "actions",
    # ⚠ **ADDED 2026-10-17 BY `DEF-AST-10178`, DELIBERATELY** (PO: *"this is
    # all corect"* — Age on the three asset lists). Where the age starts, which
    # date that was, where it stops, and the life it is measured against. All
    # four are columns already on the row; the record-date case reads the
    # tenant's clock once per PAGE (`_PageReads.tz`), never per row.
    "age_end",
    "age_start",
    "age_start_source",
    "expected_life_years",
    "asset_no",
    "assigned",
    "assigned_address",
    # ⚠ **ADDED 2026-09-19 BY `DEF-MET-5861`, AND THIS LOCK IS WHY IT IS A
    # DELIBERATE LINE RATHER THAN A SILENT WIDENING.** The unit's Assets tab
    # draws a column headed `On since`, which asks when a thing arrived at THIS
    # unit — the current assignment's `from_date`. It was rendering
    # `install_date`, which is a different fact (the depreciation age base and
    # the registry's own `Installed` column) and is null outright on anything
    # assigned from stock, so the column drew a dash on every meter a clerk had
    # just assigned. Costs no query: `asset_dict` already reads the current
    # assignment for `assigned_unit_id`, on both paths.
    "assigned_from",
    "assigned_to",
    "assigned_unit_id",
    "behavior_class",
    # ⚠ **ADDED 2026-10-02 BY `CR-161-BRC10` W3 (`DEF-AST-9171`), DELIBERATELY.**
    # The tenant's own answers, which the Assets list's optional column and
    # Asset detail read. A column already on the row, so it costs no query on
    # either path.
    "custom_data",
    "export_capacity_kw",
    "external_ref",
    "has_test_cadence",
    "id",
    "install_date",
    "manufacturer",
    "meter_type",
    "meter_type_name",
    "model",
    "multiplier",
    "net_metering",
    "next_test",
    "parent_asset_id",
    "parent_asset_no",
    "read_method",
    "read_method_name",
    "replaced_by",
    "retire_date",
    "retire_reason",
    "serial_no",
    "service",
    "service_point_id",
    "size_class",
    "status",
    "status_name",
    "tab",
    "test_due",
    "type",
    "type_name",
    "unit",
    "warranty_end",
}
#: `CR-028` AST-W1 + `CR-089` wave C task C4 — the per-tab extras.
TAB_KEYS = {
    "meters": BASE_KEYS | {"sub_count", "last_read"},
    "sub_meters": BASE_KEYS | {"last_read", "parent_premises"},
    "behind_the_meter": BASE_KEYS,
}


def _registry(actor, unit_id, prefix, count, start=0):
    """`count` meters standing on `unit_id`. `install_date` is required
    whenever `unit_id` is given (BR-AST-011 assign-on-create)."""
    return [
        make_asset(
            actor,
            asset_no=f"{prefix}{start + i:05d}",
            unit_id=unit_id,
            install_date="2026-01-05",
        )
        for i in range(count)
    ]


def _page(per, **kwargs):
    """One PAGE of assets, fetched exactly as `api.assets` fetches it — the
    queryset sliced, then handed to `asset_page_rows` as a list."""
    return list(selectors.asset_list(**kwargs)[:per])


def _cost(per, **kwargs):
    """Queries paid to SHAPE one page of `per` rows, and the rows shaped.

    The fetch is deliberately OUTSIDE the counted block: `asset_list`'s own cost
    is `test_cr092_registry_paging.py`'s subject and is already flat. What this
    measures is the step between that queryset and the served payload, which is
    the step nothing was measuring.

    ⚠ **THE LOG IS CLEARED FIRST, AND THAT IS NOT TIDINESS — IT IS WHAT STOPS
    THIS COUNT UNDER-REPORTING.** `connection.queries_log` is a `deque` capped
    at `queries_limit` (9,000). `CaptureQueriesContext` records `len(log)` on
    entry and subtracts, so once the deque is SATURATED it evicts from the left
    and the subtraction returns a number SMALLER than the queries that actually
    ran — with no warning and no error. A fixture big enough to saturate it
    would therefore make a per-row cost look flat, which is the exact direction
    that would make these cases pass wrongly. Found while measuring this defect:
    a scratch run that had already issued ~10,400 queries reported **3,541** for
    a page that truly cost over 5,000.
    """
    rows = _page(per, **kwargs)
    connection.queries_log.clear()
    with CaptureQueriesContext(connection) as ctx:
        shaped = selectors.asset_page_rows(rows)
    return len(ctx.captured_queries), shaped


# ══════════════════════════════════════════════════════════════════════════
# THE ROW STILL SAYS EXACTLY WHAT IT SAID
# ══════════════════════════════════════════════════════════════════════════
def test_the_registry_row_shape_is_exactly_what_it_was(brazos, dana):
    """One row per tab, keys pinned as literals. A batch that widened the row to
    make itself worthwhile would be `DEF-650`/`DEF-324` in reverse."""
    with tenant_ctx(brazos):
        prem = make_premises(dana, address_line="1 Shape Way")
        unit = make_unit(dana, prem["id"], label="Unit A")
        make_asset(dana, asset_no="M-00001", unit_id=unit["id"], install_date="2026-01-05")
        make_asset(
            dana,
            asset_no="S-00001",
            type="sub_meter",
            service="electric",
            unit_id=unit["id"],
            install_date="2026-01-05",
            parent_asset_no="M-00001",
        )
        make_asset(
            dana,
            asset_no="B-00001",
            type="fire_line",
            service="electric",
            unit="line",
            unit_id=unit["id"],
            install_date="2026-01-05",
        )
        rows = selectors.asset_page_rows(_page(50))
    assert len(rows) == 3, "fixture produced no row for one of the three tabs"
    seen = {row["tab"] for row in rows}
    assert seen == set(TAB_KEYS), f"the fixture did not cover every tab: {seen}"
    for row in rows:
        expected = TAB_KEYS[row["tab"]]
        assert set(row) == expected, (
            f"the {row['tab']} row changed shape: {set(row) ^ expected}"
        )


def test_a_page_row_says_exactly_what_the_single_row_read_says(brazos, dana):
    """⚠ **THE PIN THAT CANNOT BE EDITED INTO AGREEMENT.** `asset_dict(asset)`
    called one row at a time is what `services.py` audits every write with and
    what `asset_detail` builds the S50 header on; the page path must answer the
    same thing. Both sides are recomputed here, so a regression cannot be
    absorbed by changing an expected value.

    ⚠ **THE UNASSIGNED ROW IS IN THIS FIXTURE ON PURPOSE, AND IT WAS MISSING
    WHEN THIS FILE WAS FIRST WRITTEN.** The batched path answers *this asset has
    no seat* with `page.seats.get(id)` returning `None` — a DIFFERENT branch
    from the per-row `.first()` returning `None`, and the branch that decides
    `assigned`, `assigned_to`, `assigned_address` and `assigned_unit_id` on
    every spare in inventory. A parity test built only from assigned rows cannot
    see a regression in it, which is this file's own *what would make this pass
    wrongly* question asked of the file itself.
    """
    with tenant_ctx(brazos):
        prem = make_premises(dana, address_line="2 Parity Row")
        unit = make_unit(dana, prem["id"], label="Unit B")
        master = _registry(dana, unit["id"], "P-", 3)[0]
        make_asset(
            dana,
            asset_no="PS-00001",
            type="sub_meter",
            service="electric",
            unit_id=unit["id"],
            install_date="2026-01-05",
            parent_asset_no=master["asset_no"],
        )
        # A spare left in inventory — no `unit_id`, so no current assignment.
        make_asset(dana, asset_no="PU-00001")
        page = _page(50)
        batched = selectors.asset_page_rows(page)
        one_at_a_time = [selectors.asset_dict(asset) for asset in page]
    assert len(batched) == 5, "fixture produced nothing to compare"
    assert any(row["assigned_address"] for row in batched), (
        "no row carries an address — the unit read never happened and this "
        "case would pass over an unwired seam"
    )
    spare = next(row for row in batched if row["asset_no"] == "PU-00001")
    assert spare["assigned"] is False and spare["assigned_unit_id"] is None, (
        "the unassigned row lost its null seat — the batched path's `None` "
        "branch is what this row is here to pin"
    )
    assert spare["assigned_to"] is None and spare["assigned_address"] is None
    for shaped, alone in zip(batched, one_at_a_time, strict=True):
        for key, value in alone.items():
            assert shaped[key] == value, (
                f"{shaped['asset_no']}.{key}: the page says {shaped[key]!r} and "
                f"the single-row read says {value!r}"
            )


def test_the_page_still_carries_the_facts_the_batched_reads_answer(brazos, dana):
    """The values the four batched reads produce, asserted BY VALUE. Without
    this, every count below would be satisfied by a page that read nothing."""
    with tenant_ctx(brazos):
        prem = make_premises(dana, address_line="3 Fact Lane")
        unit = make_unit(dana, prem["id"], label="Unit C")
        master = _registry(dana, unit["id"], "F-", 1)[0]
        make_asset(
            dana,
            asset_no="FS-00001",
            type="sub_meter",
            service="electric",
            unit_id=unit["id"],
            install_date="2026-01-05",
            parent_asset_no=master["asset_no"],
        )
        rows = {row["asset_no"]: row for row in selectors.asset_page_rows(_page(50))}
    meter = rows["F-00000"]
    sub = rows["FS-00001"]
    assert meter["assigned_to"] == "Unit C", "the unit read (label) did not happen"
    assert meter["assigned_address"] == "3 Fact Lane", "the unit read (address) did not happen"
    assert meter["service"] == "electric", "the service-code read did not happen"
    assert meter["sub_count"] == 1, "the sub-meter COUNT did not happen"
    assert sub["parent_premises"] == "3 Fact Lane", "the parent's premises walk did not happen"
    assert "last_read" in sub, "the sub-meter row lost its last-read key"


# ══════════════════════════════════════════════════════════════════════════
# NFR-3 · the cost follows the page, and NOT the page's SIZE
# ══════════════════════════════════════════════════════════════════════════
def test_the_page_cost_does_not_follow_the_page_size(brazos, dana):
    """⚠ **THE CASE THE REGISTER ASKED FOR, IN ITS OWN WORDS:** *"vary the PAGE
    SIZE rather than the population"*. Measured on `brazosbend` before this
    lane: **201 queries for 40 rows and 1,001 for 200** — five per served row,
    from ONE population, which is why growing the tenant could never reveal it.
    """
    with tenant_ctx(brazos):
        prem = make_premises(dana, address_line="4 Budget Way")
        units = [make_unit(dana, prem["id"], label=f"Unit {i}") for i in range(4)]
        for i in range(40):
            make_asset(
                dana,
                asset_no=f"Q-{i:05d}",
                unit_id=units[i % 4]["id"],
                install_date="2026-01-05",
            )
        small, small_rows = _cost(10, filters={"tab": "meters"})
        large, large_rows = _cost(40, filters={"tab": "meters"})
    assert len(small_rows) == 10 and len(large_rows) == 40, (
        "the two pages must differ in size or this case proves nothing "
        f"({len(small_rows)} and {len(large_rows)} rows)"
    )
    assert large == small, (
        f"a page of 10 cost {small} queries and a page of 40 cost {large} — "
        f"{large - small} more reads for 30 more rows. The row is being shaped "
        "one read at a time (DEF-5745)."
    )


def test_the_sub_meter_page_does_not_follow_the_page_size(brazos, dana):
    """The sub-meter row is the EXPENSIVE one and the register's figure of five
    does not cover it: it pays the master's seat and the master's unit on top,
    through `_parent_premises`. Measured before this lane: **seven** per row."""
    with tenant_ctx(brazos):
        prem = make_premises(dana, address_line="5 Child Street")
        unit = make_unit(dana, prem["id"], label="Unit D")
        masters = _registry(dana, unit["id"], "MM-", 4)
        for i in range(20):
            make_asset(
                dana,
                asset_no=f"SS-{i:05d}",
                type="sub_meter",
                service="electric",
                unit_id=unit["id"],
                install_date="2026-01-05",
                parent_asset_no=masters[i % 4]["asset_no"],
            )
        small, small_rows = _cost(5, filters={"tab": "sub_meters"})
        large, large_rows = _cost(20, filters={"tab": "sub_meters"})
    assert len(small_rows) == 5 and len(large_rows) == 20, "the pages must differ in size"
    assert all(row["parent_premises"] == "5 Child Street" for row in large_rows), (
        "the parent walk produced nothing — the count below would be flat and wrong"
    )
    assert large == small, (
        f"a sub-meter page of 5 cost {small} queries and one of 20 cost {large}"
    )


def test_the_registry_page_batches_its_cross_row_reads(brazos, dana):
    """A CEILING, so an unrelated `select_related` does not teach anybody to
    edit a number. Five batched reads is the shape: the seats, the units, the
    service codes (metering answers those in two), the sub-meter counts and the
    last reads."""
    with tenant_ctx(brazos):
        prem = make_premises(dana, address_line="6 Ceiling Court")
        unit = make_unit(dana, prem["id"], label="Unit E")
        _registry(dana, unit["id"], "C-", 40)
        cost, rows = _cost(40, filters={"tab": "meters"})
    assert len(rows) == 40
    assert cost <= 12, (
        f"{cost} queries for 40 rows: one page of registry rows may not cost a "
        "read per row (NFR-3)"
    )


def test_the_id_lists_are_chunked_so_a_page_cannot_blow_the_bind_limit(brazos, dana):
    """⚠ **A QUERY COUNT CANNOT SEE THIS AND THAT IS WHY IT HAS ITS OWN CASE**
    (`DEF-5744`'s lesson, one function along): an `IN` clause holding forty
    thousand literals is still exactly ONE query. `per` clamps to 1,000 today,
    so this is not a live breach — it is the ceiling that stops the batch from
    BECOMING one the day a page size moves, and it is asserted on the helper
    because a fixture of 32,767 assets is not a test."""
    assert selectors._ID_CHUNK <= 900, "the chunk must stay well under SQLite's 32,766"
    got = list(selectors._chunked(range(2001)))
    assert [len(part) for part in got] == [900, 900, 201]
    assert sum(len(part) for part in got) == 2001, "chunking dropped ids"


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-5745 (GET /assets pays five queries per served row)
# generated: 2026-09-19 by the assets registry batching lane
# gates: pytest
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
