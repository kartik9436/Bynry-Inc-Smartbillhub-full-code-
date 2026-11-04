# ── Trace ──────────────────────────────────────────────
# Defects: DEF-5744 (f.status=unassigned and the address search build every
#          matching asset id in Python and send one bind parameter per asset) ·
#          DEF-5745 (filed, NOT fixed here — asset_dict costs five queries per
#          SERVED row; bounded by the page, so a different defect and a
#          different wave)
# Rules:   NFR-3 (universal server pagination) · NFR-5 (no hard caps anywhere —
#          a statement that fails above 32,766 assigned assets IS a cap) ·
#          BR-AST-005 (status semantics: Unassigned = no CURRENT assignment
#          row, and it excludes the terminal stage) · BR-AST-041 (search covers
#          the premises/unit address) · hard rule 1 (tenant scoping)
# Tests:   this file
# Impacts: apps/assets/selectors.py asset_list()
# ───────────────────────────────────────────────────────
"""DEF-5744 — the two branches of `asset_list` that still materialise ids.

⚠ **WHY THIS FILE EXISTS WHEN `test_cr092_registry_paging.py` ALREADY PASSES.**
That file is right about what it measures. `asset_list` IS lazy, its slice does
carry a `LIMIT`, and its cost does NOT move with the population — all three
re-measured on 2026-09-18 and all three green. What it cannot see is a filter
that materialises ids, because **an `IN` clause holding forty thousand literals
is still exactly ONE query**. A query-count test is true and blind at the same
time here, which is hard-won law 7's *ask what would make this check pass
wrongly*, asked and answered.

So these cases count **BIND PARAMETERS**, not queries. With the ids materialised
the parameter count follows the tenant; with the subquery left lazy it is a
constant, because the ids never leave the database.

RED-FIRST PROOF (law 7, in the harness that runs it — `pytest`, not a
`__main__`). Run against `bfaeb4120` — the tip this lane started from, with the
`list(...)` calls still in place:

    test_unassigned_does_not_send_a_parameter_per_assigned_asset
        AssertionError: f.status=unassigned sent 6 -> 36 parameters for
        5 -> 35 assigned assets: the ids are being built in Python ...
    test_address_search_does_not_send_a_parameter_per_matching_asset
        AssertionError: the address search sent 9 -> 39 parameters ...

Both pass after the change. The three semantic cases below were green BEFORE and
after — they exist to prove the rewrite did not change WHICH rows come back,
which is the only thing that could make this a regression rather than a fix.

⚠ **AND PROVED ON REAL POSTGRESQL, NOT ONLY ON THE SQLITE SUITE — 7 passed
under `--ds=config.settings.pgtest`.** That is not ceremony here. The change
replaces an `IN (<literals>)` with `NOT IN (<subselect>)`, and **on PostgreSQL a
`NOT IN` whose subquery yields a single NULL matches NOTHING AT ALL** — the
Unassigned tab would have gone silently empty on every tenant, with the default
suite green, which is hard-won law 14's exact shape one column over. It is safe
because `AssetAssignment.asset` is a non-nullable FK — but *"the model file says
NOT NULL"* is a claim about a file, and the law asks for a claim about the
database. So it was run against the database.
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

from apps.assets import models, selectors  # noqa: E402

pytestmark = pytest.mark.django_db


def _params(**kwargs) -> int:
    """How many bind parameters the registry's own statement carries.

    ⚠ **THE SLICE IS DELIBERATE AND IT IS `[:50]`.** `sql_with_params()` on the
    unsliced queryset would answer the same question, but the thing actually
    served is a page — measuring anything else would be measuring a statement
    this product never issues.
    """
    _sql, params = selectors.asset_list(**kwargs)[:50].query.sql_with_params()
    return len(params)


def _assign(actor, unit_id, prefix, count):
    """`count` assets standing on `unit_id` — i.e. `count` CURRENT assignments.

    `install_date` is required whenever `unit_id` is given (BR-AST-011
    assign-on-create) and `create_asset` refuses without it.
    """
    return [
        make_asset(actor, asset_no=f"{prefix}{i:05d}", unit_id=unit_id, install_date="2026-01-05")
        for i in range(count)
    ]


# ══════════════════════════════════════════════════════════════════════════
# NFR-3 / NFR-5 · the ids stay in the database
# ══════════════════════════════════════════════════════════════════════════
def test_unassigned_does_not_send_a_parameter_per_assigned_asset(brazos, dana):
    """`DEF-5744`. The branch read every CURRENT assignment's `asset_id` into a
    Python list and handed it to `exclude(id__in=…)`, so the statement carried
    one uuid literal per assigned asset in the tenant.

    Measured on `brazosbend` before the fix: the statement grew 4,797 → 6,417 →
    10,017 characters for 5 → 50 → 150 assigned assets, about 36 characters
    each. At the top of T5 (40,000, ruled 2026-09-06) that is a statement of
    roughly 1.4 MB carrying 40,000 parameters — **past SQLite's 32,766 variable
    limit outright**, which makes it an `NFR-5` hard cap as well as an `NFR-3`
    cost: the list would stop answering at all rather than merely answer slowly.
    """
    with tenant_ctx(brazos):
        prem = make_premises(dana, address_line="11 Subquery Row")
        unit = make_unit(dana, prem["id"], label="Unit A")
        _assign(dana, unit["id"], "V-", 5)
        few = _params(filters={"status": "unassigned"})
        _assign(dana, unit["id"], "W-", 30)
        lots = _params(filters={"status": "unassigned"})
    assert lots == few, (
        f"f.status=unassigned sent {few} → {lots} parameters for 5 → 35 assigned "
        "assets: the ids are being built in Python and inlined into the statement. "
        "One query, and one bind parameter per row of the tenant — which is why a "
        "query count cannot see this."
    )


def test_address_search_does_not_send_a_parameter_per_matching_asset(brazos, dana):
    """The same shape in `q=`'s address arm (`BR-AST-041`).

    ⚠ **THE ASSET IDS ARE THIS MODULE'S TO KEEP LAZY; THE UNIT IDS ARE NOT.**
    `_unit_ids_matching_address` crosses into metering through a seam that
    answers a `list`, so those ids are materialised by a contract this lane does
    not own and does not touch. What is fixed is the ASSET id list built on top
    of them — the larger of the two, since a unit holds several assets.
    """
    with tenant_ctx(brazos):
        prem = make_premises(dana, address_line="12 Subquery Row")
        unit = make_unit(dana, prem["id"], label="Unit B")
        _assign(dana, unit["id"], "X-", 5)
        few = _params(q="12 Subquery Row")
        _assign(dana, unit["id"], "Y-", 30)
        lots = _params(q="12 Subquery Row")
    assert lots == few, (
        f"the address search sent {few} → {lots} parameters for 5 → 35 assets on "
        "the matching unit: the asset ids are being built in Python"
    )


def test_the_statement_names_the_assignments_table_as_a_subselect(brazos, dana):
    """⚠ **THE COUNT CASES ABOVE PASS ON A FILTER THAT STOPPED WORKING.**

    A branch deleted outright sends no parameters either, and both cases would
    go green over a registry that had quietly forgotten how to filter. So this
    asserts the mechanism as well as the cost: the assignments table must appear
    INSIDE the statement, which is what *the database did the work* looks like.
    """
    with tenant_ctx(brazos):
        prem = make_premises(dana, address_line="13 Subquery Row")
        unit = make_unit(dana, prem["id"], label="Unit C")
        _assign(dana, unit["id"], "Z-", 3)
        page = selectors.asset_list(filters={"status": "unassigned"})[:50]
        sql, _p = page.query.sql_with_params()
    upper = sql.upper()
    assert "ASSET_ASSIGNMENTS" in upper, (
        "the unassigned filter no longer mentions asset_assignments — it is not "
        "filtering in SQL, it is not filtering at all"
    )
    assert "SELECT" in upper.split("ASSET_ASSIGNMENTS")[0], "not a subselect"
    assert "LIMIT" in upper, "the page stopped reaching SQL (NFR-3)"


# ══════════════════════════════════════════════════════════════════════════
# BR-AST-005 · the ANSWER did not move
# ══════════════════════════════════════════════════════════════════════════
def test_unassigned_returns_exactly_what_it_returned_before(brazos, dana):
    """A subquery is only a fix if it selects the same rows. `Unassigned` is
    BR-AST-005's *no CURRENT assignment row*, and it excludes the terminal
    stage — so it must be the complement of `f.assigned=true` within the
    non-terminal fleet, exactly, with no row in both and none in neither."""
    with tenant_ctx(brazos):
        prem = make_premises(dana, address_line="14 Subquery Row")
        unit = make_unit(dana, prem["id"], label="Unit D")
        _assign(dana, unit["id"], "P-", 6)
        for i in range(4):
            make_asset(dana, asset_no=f"Q-{i:05d}")  # spares, never assigned
        unassigned = {a.asset_no for a in selectors.asset_list(filters={"status": "unassigned"})}
        assigned = {a.asset_no for a in selectors.asset_list(filters={"assigned": "true"})}
        every = {a.asset_no for a in selectors.asset_list()}  # default = non-terminal
    assert unassigned & assigned == set(), "a row is both assigned and unassigned"
    assert unassigned | assigned == every, "a non-terminal row is in neither half"
    assert {f"Q-{i:05d}" for i in range(4)} <= unassigned
    assert {f"P-{i:05d}" for i in range(6)} <= assigned


def test_a_closed_seat_leaves_the_asset_unassigned(brazos, dana):
    """`to_date__isnull=True` is the whole of *current* (BR-AST-017). An asset
    whose only seat has ended is unassigned — the case a subquery written
    against the wrong predicate would get backwards, and the one a fixture of
    freshly-created assets can never reach."""
    with tenant_ctx(brazos):
        prem = make_premises(dana, address_line="15 Subquery Row")
        unit = make_unit(dana, prem["id"], label="Unit E")
        kept, released = _assign(dana, unit["id"], "R-", 2)
        models.AssetAssignment.objects.filter(asset_id=released["id"]).update(to_date="2026-06-30")
        unassigned = {a.asset_no for a in selectors.asset_list(filters={"status": "unassigned"})}
    assert released["asset_no"] in unassigned, "a closed seat still counted as current"
    assert kept["asset_no"] not in unassigned, "an open seat stopped counting"


def test_the_address_search_still_finds_the_assets_on_that_address(brazos, dana):
    """`BR-AST-041`: the search covers the premises/unit address. The subquery
    must find the same assets the materialised list did — and must not sweep in
    the ones standing somewhere else."""
    with tenant_ctx(brazos):
        here = make_premises(dana, address_line="16 Subquery Row")
        there = make_premises(dana, address_line="99 Elsewhere Ave")
        unit_here = make_unit(dana, here["id"], label="Unit F")
        unit_there = make_unit(dana, there["id"], label="Unit G")
        _assign(dana, unit_here["id"], "S-", 3)
        _assign(dana, unit_there["id"], "T-", 2)
        found = {a.asset_no for a in selectors.asset_list(q="16 Subquery Row")}
    assert {f"S-{i:05d}" for i in range(3)} <= found, "the address arm found nothing"
    assert found & {f"T-{i:05d}" for i in range(2)} == set(), "it swept in another address"


# ══════════════════════════════════════════════════════════════════════════
# The cost did not move either (the CR-092 contract, re-asserted on both arms)
# ══════════════════════════════════════════════════════════════════════════
def test_neither_branch_costs_a_query_per_row(brazos, dana):
    """The subquery must not buy back in queries what it saved in parameters.
    Written as *the cost did not move with the population*, which is what
    `NFR-3` actually promises, rather than as an equality against a literal."""
    with tenant_ctx(brazos):
        prem = make_premises(dana, address_line="17 Subquery Row")
        unit = make_unit(dana, prem["id"], label="Unit H")
        _assign(dana, unit["id"], "U-", 4)
        before = {}
        for label, kwargs in (
            ("unassigned", {"filters": {"status": "unassigned"}}),
            ("address", {"q": "17 Subquery Row"}),
        ):
            with CaptureQueriesContext(connection) as ctx:
                list(selectors.asset_list(**kwargs)[:50])
            before[label] = len(ctx)
        _assign(dana, unit["id"], "N-", 26)
        for label, kwargs in (
            ("unassigned", {"filters": {"status": "unassigned"}}),
            ("address", {"q": "17 Subquery Row"}),
        ):
            with CaptureQueriesContext(connection) as ctx:
                list(selectors.asset_list(**kwargs)[:50])
            assert len(ctx) == before[label], (
                f"{label} cost moved with the population ({before[label]} → "
                f"{len(ctx)} queries for 4 → 30 rows)"
            )
