# ── Trace ──────────────────────────────────────────────
# Change:   CR-092-BRC01 step 2 wave C lane 3 — `AST-B-24`, SERVER-SIDE PAGING
#           INSIDE AN ASSET, and the three registry reads that took no page
#           parameter at all.
# Defects:  DEF-MET-4995 (the three in-asset lists answer the whole history —
#           filed by this lane BEFORE it was fixed) · DEF-MET-4962 remainder
#           (/assets/stock, /assets/lifecycle, /assets/geo) · DEF-MET-4951 and
#           DEF-PAY-4221 (the shape both record: an honest envelope over an
#           unbounded query, and a sort that happens in Python)
# Rules:    NFR-3 (universal server pagination) · NFR-5 (no hard caps) ·
#           BR-SHL-011 (a list URL can never 4xx over its params) ·
#           BR-AST-017 (assignments append-only) · BR-AST-018 (maintenance
#           append-only) · BR-AST-029 (the typed pair folds per read date) ·
#           hard rule 2 (money 4 dp stored, 2 displayed)
# Tests:    this file
# Impacts:  apps/assets/api.py · apps/assets/selectors.py · apps/assets/seams.py
#           · apps/metering/selectors.py
# ───────────────────────────────────────────────────────
"""CR-092 wave C lane 3 — paging inside an asset, and the last three unpaged reads.

RED-FIRST PROOF (hard-won law 7, and in the harness that runs it — `pytest`,
not a `__main__`): every case below was run with `pytest` against a second
worktree pinned at `404ae10c0`, the tip this lane started from, and the failures
are quoted in the lane report. The envelope cases failed on
`AttributeError: module 'apps.assets.selectors' has no attribute
'assignments_page'`; `test_assignment_rows_do_not_cost_a_query_each` failed on
the measured counts; `test_sql_aged_matches_python` failed on `_aged_q` not
existing.

⚠ **THE COUNT CASES ARE WRITTEN AS *THE COST DID NOT MOVE*, NEVER AS A NUMBER.**
An equality against a literal goes red when an unrelated lane adds a
`select_related`, which teaches the next reader to edit the number rather than
to look. What `NFR-3` actually promises is that the cost is INDEPENDENT of how
big the tenant is, so each case builds a second, larger population and asserts
the count did not follow it. That is also the only form of this test that could
ever have caught the defect: the largest in-asset list on any seeded tenant is
26 rows, so a case that measured once would pass forever.
"""

from datetime import date

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    commit_read,
    seed_config,
    tenant_ctx,
)
from tests.test_us_met_helpers import make_asset, make_premises, make_unit  # noqa: F401

from apps.assets import models, selectors  # noqa: E402

pytestmark = pytest.mark.django_db

TODAY = date(2026, 8, 16)


# ── fixtures: a history worth paging ───────────────────────────────────────
def _reads(actor, asset_id, count, *, start_day=1):
    """`count` committed reads on distinct dates — the Reads tab's paging unit."""
    for i in range(count):
        month = 1 + (start_day + i) // 28
        day = 1 + (start_day + i) % 28
        commit_read(
            actor,
            asset_id,
            day=f"2025-{month:02d}-{day:02d}",
            value=str(1000 + i * 10),
            consumption="10",
        )


def _seats(asset_id, unit_id, count):
    """`count` CLOSED assignment seats. `to_date` is always set: the partial
    unique index permits exactly one open seat per asset (BR-AST-017)."""
    tenant_id = models.Asset.objects.get(pk=asset_id).tenant_id
    models.AssetAssignment.objects.bulk_create(
        [
            models.AssetAssignment(
                tenant_id=tenant_id,
                asset_id=asset_id,
                unit_id=unit_id,
                from_date=date(2020, 1, 1) + __import__("datetime").timedelta(days=i * 30),
                to_date=date(2020, 1, 1) + __import__("datetime").timedelta(days=i * 30 + 20),
            )
            for i in range(count)
        ]
    )


def _repairs(asset_id, count):
    tenant_id = models.Asset.objects.get(pk=asset_id).tenant_id
    models.AssetMaintenance.objects.bulk_create(
        [
            models.AssetMaintenance(
                tenant_id=tenant_id,
                asset_id=asset_id,
                kind="repair",
                date=date(2026, 1, 1) + __import__("datetime").timedelta(days=i),
                detail=f"row {i}",
                cost=None if i % 5 else "10.0000",
            )
            for i in range(count)
        ]
    )


# ══════════════════════════════════════════════════════════════════════════
# NFR-3 · the page reaches SQL, on all three lists inside an asset
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("name", ["assignments_page", "maintenance_page", "asset_read_dates_page"])
def test_the_in_asset_lists_are_lazy_and_the_slice_reaches_sql(brazos, marcus, name):
    """`DEF-MET-4995`. Each of the three used to build a Python list, so a
    paginator could only ever slice in memory — the honest-envelope shape
    `DEF-MET-4951` filed on the registry, one screen further in."""
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus)
        page = getattr(selectors, name)(asset["id"])
        assert not isinstance(page, list), (
            f"{name} must stay lazy — a list here means the paginator slices in "
            "Python and no LIMIT ever reaches the database (NFR-3)"
        )
        sql, _params = page[2:5].query.sql_with_params()
        assert "LIMIT" in sql.upper()


def test_the_order_by_is_sql_and_not_python(brazos, marcus):
    """`DEF-PAY-4221`'s other half: `GET /outstandings` sorts in Python and is
    cited in CLAUDE.md as a live NFR-3 breach. A sort applied after the slice
    means page 2 can hold a row that belongs on page 1 — so the ORDER BY has to
    be IN the statement the LIMIT is on."""
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus)
        for name in ("assignments_page", "maintenance_page", "asset_read_dates_page"):
            sql, _params = getattr(selectors, name)(asset["id"]).query.sql_with_params()
            assert "ORDER BY" in sql.upper(), f"{name} has no ORDER BY in SQL"


# ══════════════════════════════════════════════════════════════════════════
# NFR-3 · no list costs a query per row
# ══════════════════════════════════════════════════════════════════════════
def test_assignment_rows_do_not_cost_a_query_each(brazos, marcus):
    """⚠ **THIS IS THE ONE THE SEEDED DATA FOUND AND NO FIXTURE COULD.**

    `assignments` called `seams.unit_ref` inside its row loop. Measured on
    pine-hill meter `M-88402` after seeding a history: **64 queries for 61
    seats** — one per row, exactly `DEF-MET-4951`'s shape inside the asset.
    Every asset on every seeded tenant had exactly ONE seat, so the loop had
    never executed twice in this product's life and nothing had ever paid it.
    """
    with tenant_ctx(brazos):
        seed_config()
        prem = make_premises(marcus, address_line="1 Paging Row")
        unit = make_unit(marcus, prem["id"], label="Unit A")
        asset = a_meter(marcus, unit_id=unit["id"])
        _seats(asset["id"], unit["id"], 4)
        with CaptureQueriesContext(connection) as ctx:
            selectors.assignment_rows(selectors.assignments_page(asset["id"])[:50])
        few = len(ctx)
        _seats(asset["id"], unit["id"], 40)
        with CaptureQueriesContext(connection) as ctx:
            rows = selectors.assignment_rows(selectors.assignments_page(asset["id"])[:50])
        lots = len(ctx)
    assert len(rows) == 45, "the page should hold the seats, not a subset"
    assert lots == few, (
        f"assignment_rows cost moved with the rows ({few} → {lots} for 5 → 45 "
        "seats): a lookup is running per row instead of once for the page"
    )


def test_maintenance_rows_do_not_cost_a_query_each(brazos, marcus):
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus)
        _repairs(asset["id"], 4)
        with CaptureQueriesContext(connection) as ctx:
            selectors.maintenance_rows(selectors.maintenance_page(asset["id"])[:50])
        few = len(ctx)
        _repairs(asset["id"], 40)
        with CaptureQueriesContext(connection) as ctx:
            selectors.maintenance_rows(selectors.maintenance_page(asset["id"])[:50])
        lots = len(ctx)
    assert lots == few, f"maintenance_rows cost moved with the rows ({few} → {lots})"


def _spares_with_a_service_point(actor, unit_id, prefix, count):
    """`count` spares that have STOOD somewhere — so `_service_of` has something
    to resolve.

    ⚠ **THIS EXISTS BECAUSE THE FIRST DRAFT OF THE CASE BELOW WAS INCAPABLE OF
    FAILING, AND IT IS WORTH THE LINES.** `make_asset` leaves a spare in
    inventory with `service_point_id` NULL, and `_service_of` returns `None` on
    that column before it reaches the seam at all. So a stock population built
    the obvious way costs the OLD code zero seam calls, the query counts match,
    and the case passes green over the very defect it names — law 7's *ask what
    would make this check pass wrongly*, met by asking it.

    A spare that carries a service point is not contrived: `service_point_id`
    survives a reassign back to inventory, so every meter a utility has ever
    pulled off a connection is one.
    """
    from apps.assets import seams as asset_seams

    point = asset_seams.ensure_service_point(unit_id, "electric")
    point_id = getattr(point, "id", point)
    made = [make_asset(actor, asset_no=f"{prefix}{i:05d}") for i in range(count)]
    models.Asset.objects.filter(id__in=[a["id"] for a in made]).update(service_point_id=point_id)
    return made


def test_stock_view_does_not_pay_a_seam_call_per_spare(brazos, marcus):
    """`stock_view`'s `services` cell called `_service_of` per asset — a
    metering seam read inside a comprehension, the same shape wave B took out
    of the registry list and the map, still standing here because a demo tenant
    holds eight spares and every one of them has a null service point."""
    with tenant_ctx(brazos):
        seed_config()
        prem = make_premises(marcus, address_line="5 Depot Row")
        unit = make_unit(marcus, prem["id"], label="Unit E")
        _spares_with_a_service_point(marcus, unit["id"], "S-", 4)
        with CaptureQueriesContext(connection) as ctx:
            small = selectors.stock_view(today=TODAY)
        few = len(ctx)
        _spares_with_a_service_point(marcus, unit["id"], "S-1", 20)
        with CaptureQueriesContext(connection) as ctx:
            large = selectors.stock_view(today=TODAY)
        lots = len(ctx)
    # The guard on the guard: if `services` is empty the case proves nothing,
    # because the per-row call short-circuits before the seam.
    assert any(row["services"] for row in small["rows"]), (
        "no stock row resolved a service — this case cannot see the defect it names"
    )
    assert lots == few, f"stock_view cost moved with the stock ({few} → {lots} for 4 → 24)"
    assert large["kpis"]["uninstalled"] >= 24


# ══════════════════════════════════════════════════════════════════════════
# The envelope, and page 2 is a DIFFERENT page
# ══════════════════════════════════════════════════════════════════════════
ENVELOPE = {"count", "next", "previous", "results"}


def _request(tenant, actor, **params):
    """A real DRF request for the view, not a call to the selector underneath it.

    ⚠ **THE VIEW IS THE THING UNDER TEST HERE AND THE SELECTOR IS NOT.** The
    envelope is built by `StandardPagination`, in the view; a case that called
    `selectors.maintenance_page` directly would pass identically whether the
    route serves the envelope or still serves a bare list — which is exactly the
    blind spot `DEF-AST-4120` fell into, where the shape on the wire was the
    only thing nobody was checking.

    `force_authenticate` rather than `request.user = …`: DRF's `Request.user`
    re-runs the authenticators and overwrites whatever the underlying Django
    request carried, so the direct assignment silently 401s.
    """
    from rest_framework.test import APIRequestFactory, force_authenticate

    request = APIRequestFactory().get("/api/v1/assets/x/reads", params)
    force_authenticate(request, user=actor.user)
    request.tenant_role = "system_admin"
    request.tenant_id = tenant.id
    return request


def test_reads_assignments_and_maintenance_answer_the_one_envelope(brazos, marcus):
    """One asset detail screen, ONE convention. `GET /assets` and
    `GET /assets/{id}/work-orders` already answer `{count, next, previous,
    results}`; these three answered a bare list and a `rows` key, so the screen
    had three descriptions of one idea — which is precisely what
    `07-frontend/src/api/paginated.ts` and `G114` exist to stop."""
    from apps.assets import api as assets_api

    with tenant_ctx(brazos):
        seed_config()
        prem = make_premises(marcus, address_line="2 Envelope Way")
        unit = make_unit(marcus, prem["id"], label="Unit B")
        asset = a_meter(marcus, unit_id=unit["id"])
        _reads(marcus, asset["id"], 60)
        _seats(asset["id"], unit["id"], 60)
        _repairs(asset["id"], 60)

        for view in (assets_api.asset_reads, assets_api.asset_assignments):
            first = view(_request(brazos, marcus, page=1), asset["id"]).data
            second = view(_request(brazos, marcus, page=2), asset["id"]).data
            assert ENVELOPE <= set(first), f"{view.__name__} is not in the envelope"
            assert first["count"] >= 60
            assert len(first["results"]) == 50
            assert first["results"] != second["results"], (
                f"{view.__name__} page 2 is page 1 — the page is not reaching SQL"
            )
            assert first["next"] and not first["previous"]
            assert second["previous"]

        first = assets_api.asset_maintenance(_request(brazos, marcus, page=1), asset["id"]).data
        second = assets_api.asset_maintenance(_request(brazos, marcus, page=2), asset["id"]).data
        assert ENVELOPE <= set(first)
        assert first["count"] == 60 and len(first["results"]) == 50
        assert first["results"] != second["results"]


def test_the_maintenance_total_is_over_every_entry_and_not_over_the_page(brazos, marcus):
    """⚠ **SPREAD, DO NOT PASS** (`DEF-AST-4120`): `get_paginated_response`
    builds a fresh four-key body and copies nothing else, which is how
    `maintenance_index` never left the server and every WORK ORDER cell on this
    same screen became a dash. And the total itself must not follow the page —
    a lifetime cost that changed when you turned the page would be a different,
    wrong number every time."""
    from apps.assets import api as assets_api

    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus)
        # `cost=None if i % 5 else "10.0000"` — so every FIFTH row carries a
        # cost: 12 of 60 at 10.0000 is 120.0000. (This comment said *48 of the
        # 60* on the first draft and the case went red on `120.0000 !=
        # 480.0000`. The CODE was right and the EXPECTATION was wrong, which is
        # the good direction for a test to fail in and worth leaving the note
        # for: a fixture whose arithmetic you have not done by hand is a
        # constant you will later "correct" the product to match.)
        _repairs(asset["id"], 60)
        page1 = assets_api.asset_maintenance(_request(brazos, marcus, page=1), asset["id"]).data
        page2 = assets_api.asset_maintenance(_request(brazos, marcus, page=2), asset["id"]).data
    assert "lifetime_cost" in page1 and "currency" in page1, (
        "the two siblings of the envelope were dropped — the DEF-AST-4120 shape"
    )
    assert page1["lifetime_cost"] == page2["lifetime_cost"]
    assert page1["lifetime_cost"] == "120.0000"


def test_a_paged_read_answer_is_the_whole_answer_sliced(brazos, marcus):
    """The fold runs on both paths, so the two must not be able to disagree
    about what a read looks like. This is the assertion that would go red if a
    later lane 'simplified' one of them."""
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus)
        _reads(marcus, asset["id"], 60)
        whole = selectors.asset_reads(asset["id"])
        dates = list(selectors.asset_read_dates_page(asset["id"])[:50])
        paged = selectors.asset_reads_on(asset["id"], dates)
    assert len(dates) == 50
    assert paged == whole[: len(paged)]


def test_an_empty_page_asks_for_nothing_rather_than_everything(brazos, marcus):
    """An empty `__in` spelled as *no filter* is a valid query that returns the
    asset's ENTIRE history — the defect, wearing the fix's clothes."""
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus)
        _reads(marcus, asset["id"], 5)
        assert selectors.asset_reads_on(asset["id"], []) == []


# ══════════════════════════════════════════════════════════════════════════
# The three composite registry reads carry a WINDOW
# ══════════════════════════════════════════════════════════════════════════
def test_the_map_answers_a_page_and_says_how_many_it_left_outside(brazos, marcus):
    """`DEF-MET-4962`'s remainder. Measured on pine-hill: 123 markers in ONE
    66,104-byte response with no page parameter of any kind; at the top of the
    stated market (40,000) that is one response of about 21 MB and a browser
    drawing a DOM element for every row of it."""
    from decimal import Decimal

    from apps.metering import models as met_models

    with tenant_ctx(brazos):
        seed_config()
        prem = make_premises(marcus, address_line="3 Marker Ln")
        met_models.Premises.objects.filter(pk=prem["id"]).update(
            lat=Decimal("30.245200"), lng=Decimal("-97.765100")
        )
        unit = make_unit(marcus, prem["id"], label="Unit C")
        for i in range(7):
            make_asset(marcus, asset_no=f"G-{i:05d}", unit_id=unit["id"], install_date="2026-01-05")
        first = selectors.geo_view(page=1, per=5)
        second = selectors.geo_view(page=2, per=5)
    assert first["assets_window"] == {"total": 7, "page": 1, "per": 5, "pages": 2}
    assert len(first["assets"]) == 5 and len(second["assets"]) == 2
    assert first["assets"][0]["id"] != second["assets"][0]["id"]


def test_the_map_does_not_pay_per_marker_for_the_markers_it_is_not_serving(brazos, marcus):
    """The page bounds the WORK, not only the payload: the sub-meter roll-up
    used to walk every parented asset in the tenant to answer a question about
    fifty, and the geo index built a dict for every placed unit before it knew
    which ones it would answer with."""
    from decimal import Decimal

    from apps.metering import models as met_models

    with tenant_ctx(brazos):
        seed_config()
        prem = make_premises(marcus, address_line="4 Marker Ln")
        met_models.Premises.objects.filter(pk=prem["id"]).update(
            lat=Decimal("30.245200"), lng=Decimal("-97.765100")
        )
        unit = make_unit(marcus, prem["id"], label="Unit D")
        for i in range(3):
            make_asset(marcus, asset_no=f"H-{i:05d}", unit_id=unit["id"], install_date="2026-01-05")
        with CaptureQueriesContext(connection) as ctx:
            selectors.geo_view(page=1, per=3)
        few = len(ctx)
        for i in range(12):
            make_asset(
                marcus, asset_no=f"H-1{i:04d}", unit_id=unit["id"], install_date="2026-01-05"
            )
        with CaptureQueriesContext(connection) as ctx:
            selectors.geo_view(page=1, per=3)
        lots = len(ctx)
    assert lots == few, f"geo_view cost moved with markers it did not serve ({few} → {lots})"


def test_stock_and_lifecycle_carry_a_window_and_their_figures_do_not_follow_it(brazos, marcus):
    """A KPI counts the whole tenant; a window describes the rows you hold. If
    the KPI followed the page it would be a different number on every page,
    which is the mistake the registry's own KPI strip documents by name."""
    with tenant_ctx(brazos):
        seed_config()
        for i in range(6):
            make_asset(marcus, asset_no=f"K-{i:05d}", purchase_cost="100.0000")
        stock_all = selectors.stock_view(today=TODAY)
        stock_page = selectors.stock_view(today=TODAY, page=1, per=1)
        lifecycle = selectors.lifecycle_view(today=TODAY, page=1, per=1)
    assert "rows_window" in stock_all and "certifications_window" in lifecycle
    assert stock_page["kpis"] == stock_all["kpis"], "a KPI followed the page"
    assert stock_page["rows_window"]["total"] == stock_all["rows_window"]["total"]
    assert len(stock_page["rows"]) <= 1


def test_a_page_parameter_can_never_4xx_or_run_off_the_end(brazos, marcus):
    """`BR-SHL-011`: invalid values fall back or clamp, NEVER error — and an
    out-of-range page clamps to the LAST one rather than answering an empty
    list a client would read as *nothing here*."""
    with tenant_ctx(brazos):
        seed_config()
        for i in range(3):
            make_asset(marcus, asset_no=f"P-{i:05d}")
        assert selectors.stock_view(today=TODAY, page="banana", per="x")["rows_window"]["page"] == 1
        far = selectors.stock_view(today=TODAY, page=99, per=1)
        assert far["rows_window"]["page"] == far["rows_window"]["pages"]
        assert far["rows"], "an out-of-range page answered nothing instead of clamping"


# ══════════════════════════════════════════════════════════════════════════
# The SQL predicate is the SAME answer as the Python derivation
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("day", [1, 15, 28, 29, 30, 31])
@pytest.mark.parametrize("month", [1, 2, 3, 8, 12])
def test_sql_aged_matches_python(brazos, marcus, month, day):
    """⚠ **A CORRECT APPROXIMATION WITH AN EXHAUSTIVE TEST BEATS A WRONG EXACT
    ONE, AND THIS IS THE EXHAUSTIVE TEST.**

    `add_months` CLAMPS the day to the target month's length and no portable ORM
    expression does — a `timedelta` of 365 days is a different answer, and
    `INTERVAL` differs between PostgreSQL and the SQLite this suite runs on,
    which is hard-won law 14's exact shape. `_aged_q` therefore compares whole
    months, and a predicate that silently diverged from `add_months` would count
    the wrong assets with every check green. So it is not assumed to agree: it
    is walked row by row against the derivation across 30 simulated purchase
    dates.
    """
    import calendar

    purchase = date(2025, month, min(day, calendar.monthrange(2025, month)[1]))
    with tenant_ctx(brazos):
        seed_config()
        asset = make_asset(marcus, asset_no="A-00001", purchase_date=purchase.isoformat())
        row = models.Asset.objects.get(pk=asset["id"])
        for offset in range(0, 400, 13):
            when = purchase + __import__("datetime").timedelta(days=offset)
            expected = selectors.add_months(purchase, 12) <= when
            annotations, predicate = selectors._aged_q(when, months=12)
            got = (
                models.Asset.objects.filter(pk=row.pk)
                .annotate(**annotations)
                .filter(predicate)
                .exists()
            )
            assert got == expected, (
                f"purchase {purchase} seen on {when}: SQL said {got}, "
                f"add_months said {expected}"
            )
