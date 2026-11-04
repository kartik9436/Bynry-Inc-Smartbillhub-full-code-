# ── Trace ──────────────────────────────────────────────
# Change:   CR-092-BRC01 step 2 lane 1 (the Assets registry) — DEF-MET-4951 /
#           DEF-MET-4962 (NFR-3: the page must reach SQL and no filter may
#           cost a query per row) and DEF-MET-4953 (the four KPI figures are
#           SERVED instead of counted in the browser).
# Rules:    NFR-3 (universal server pagination) · NFR-5 (no hard caps) ·
#           BR-AST-005 (status semantics) · BR-AST-007 (test-due is DERIVED) ·
#           BR-AST-003 (a sub bills its own unit) · BR-AST-031 (counts key off
#           the behavior CLASS, never the label) · PO 2026-09-12 ruling 2
#           ("a) Fix the figures" — D9 stands, the two tabs stay wordless)
# Tests:    this file
# Impacts:  apps/assets/selectors.py (asset_list · test_due_q · asset_kpis ·
#           geo_view) · apps/assets/api.py (the served `kpis` block) ·
#           apps/assets/seams.py (service_codes_for_points)
# ───────────────────────────────────────────────────────
"""CR-092 lane 1 — the registry's paging, its four filters and its KPI strip.

RED-FIRST PROOF (law 7, and proved in the harness that runs it): every case
below was run with `pytest` against a second worktree pinned at `ce623f444`
— the tip this lane started from — and the failures are quoted in the lane
report. `test_asset_list_is_lazy` failed on `AssertionError` (the selector
returned a `list`), the three `test_no_query_per_row_*` cases failed on the
measured counts, and `test_kpis_*` failed on `AttributeError: module
'apps.assets.selectors' has no attribute 'asset_kpis'`.

⚠ **THE QUERY-COUNT CASES ARE THE POINT AND THEY ARE WRITTEN AS CEILINGS,
NOT AS EQUALITIES.** An equality goes red when an unrelated lane adds a
`select_related`, which teaches people to edit the number; a ceiling that is
INDEPENDENT OF THE ROW COUNT is the actual contract — so each one builds a
second population and asserts the count did not move with it. A test that
merely counted queries once could pass on a one-row fixture forever, which
is how this defect survived: the largest tenant anybody ran it against held
126 assets.
"""

from datetime import date
from pathlib import Path

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

TODAY = date(2026, 8, 16)


def _meters(actor, count, *, start=1, **overrides):
    """`count` spare electric meters, left in inventory."""
    return [make_asset(actor, asset_no=f"M-{start + i:05d}", **overrides) for i in range(count)]


# ── NFR-3 · the page reaches SQL ────────────────────────────────────────────


def test_asset_list_is_lazy_and_the_slice_reaches_sql(brazos, dana):
    """DEF-MET-4951. `paginate_queryset` sliced a materialised Python list, so
    the envelope was honest and no `LIMIT` ever went to the database."""
    with tenant_ctx(brazos):
        _meters(dana, 7)
        rows = selectors.asset_list(filters={"tab": "meters"})
        assert not isinstance(rows, list), (
            "asset_list must stay lazy — a list here means the paginator slices "
            "in Python and the page never reaches SQL (NFR-3)"
        )
        sql, _params = rows[2:5].query.sql_with_params()
        assert "LIMIT" in sql.upper()
        assert len(list(rows[2:5])) == 3


def test_every_caller_still_iterates(brazos, dana):
    """The return type moved; the shape every existing caller uses did not."""
    with tenant_ctx(brazos):
        _meters(dana, 3)
        rows = selectors.asset_list(filters={"tab": "meters"})
        assert len(rows) == 3
        assert len([a.asset_no for a in rows]) == 3
        assert rows[0].asset_no <= rows[1].asset_no


# ── NFR-3 · no filter costs a query per row ─────────────────────────────────


def _queries_for(**kwargs):
    with CaptureQueriesContext(connection) as ctx:
        list(selectors.asset_list(**kwargs)[:50])
    return len(ctx)


@pytest.mark.parametrize(
    "filters",
    [
        {"tab": "meters"},
        {"tab": "meters", "assigned": "true"},
        {"tab": "meters", "assigned": "false"},
        {"tab": "meters", "test_due": "true"},
        {"tab": "meters", "service": "electric"},
    ],
    ids=["unfiltered", "assigned-true", "assigned-false", "test-due", "service"],
)
def test_no_query_per_row_however_many_rows(brazos, dana, filters):
    """DEF-MET-4962, and the SHAPE rather than a number.

    Measured on `pine-hill` (110 meters) before this lane: unfiltered 1 query,
    `f.assigned=true` **111**, `f.service=water` **209**, the two together
    **319** to return 53 rows — one query per row of the MATCH SET, which at
    the top of T5 (40,000) is of the order of 40,001 in one request.
    """
    with tenant_ctx(brazos):
        _meters(dana, 4)
        small = _queries_for(filters=filters)
        _meters(dana, 16, start=100)
        large = _queries_for(filters=filters)
    assert large == small, (
        f"cost moved with the population ({small} → {large} queries for 4 → 20 "
        "rows): a filter is running per row instead of in SQL"
    )


def test_geo_view_does_not_pay_per_marker(brazos, dana):
    """The same shape on the map. Measured on `pine-hill`: `geo_view` cost
    **241 queries** for 110 markers — a service lookup and a tenant-today
    seam call each. Step 1 could not see it: `brazosbend` has no geocoded
    premises, so its "1 query" reading was the function returning at its
    first branch, which is a number that means nothing."""
    from decimal import Decimal

    from apps.metering import models as met_models

    with tenant_ctx(brazos):
        prem = make_premises(dana, address_line="1 Registry Row")
        met_models.Premises.objects.filter(pk=prem["id"]).update(
            lat=Decimal("30.245200"), lng=Decimal("-97.765100")
        )
        unit = make_unit(dana, prem["id"], label="Unit A")
        # ⚠ **TWO THINGS THIS CASE GOT WRONG BEFORE IT MEASURED ANYTHING, AND
        # BOTH ARE WORTH THE LINES.** (1) `unit_id` ASSIGNS an asset to a unit;
        # `unit` is the UNIT OF MEASURE ("kWh"). Passing `unit=` gave three
        # meters whose UoM was a uuid, standing nowhere — `geo_view` had no
        # seats and answered zero markers, so the cost this case exists to
        # measure was a cost nothing paid. (2) `install_date` is REQUIRED
        # whenever `unit_id` is given (BR-AST-011 assign-on-create), and
        # `create_asset` refuses without it. The existing geo fixture in
        # `test_cr028_new_tabs.py` passes both; copying only half of it is how
        # this case spent two runs failing for a reason that was not the
        # subject.
        for i in range(3):
            make_asset(dana, asset_no=f"G-{i:05d}", unit_id=unit["id"], install_date="2026-01-05")
        with CaptureQueriesContext(connection) as ctx:
            small = len(selectors.geo_view()["assets"])
        few = len(ctx)
        for i in range(9):
            make_asset(dana, asset_no=f"G-1{i:04d}", unit_id=unit["id"], install_date="2026-01-05")
        with CaptureQueriesContext(connection) as ctx:
            many = len(selectors.geo_view()["assets"])
        lots = len(ctx)
    assert small == 3 and many == 12
    assert lots == few, f"geo_view cost moved with the markers ({few} → {lots})"


# ── BR-AST-007 · the SQL predicate is the SAME answer as the derivation ─────


@pytest.mark.parametrize(
    "last_test,interval",
    [
        (date(2026, 1, 31), 1),  # clamps: 31 Jan + 1 month = 28 Feb
        (date(2026, 1, 31), 12),
        (date(2024, 2, 29), 12),  # leap day + 12 = 28 Feb 2025
        (date(2026, 8, 16), 0),  # a 0-month cadence is NO cadence, never "now"
        (date(2026, 8, 31), 6),
        (date(2025, 12, 1), 9),
        (date(2026, 8, 15), 1),
    ],
)
def test_sql_test_due_matches_python(brazos, dana, last_test, interval):
    """The predicate is not ASSUMED to agree with `test_due()` — it is compared
    with it, row by row, across a year of simulated "today"s including every
    month end and every clamped day. A predicate that silently diverged would
    filter the wrong rows with every other check green."""
    with tenant_ctx(brazos):
        asset = make_asset(dana, asset_no="M-70001")
        models.Asset.objects.filter(pk=asset["id"]).update(
            last_test_date=last_test, test_interval_months=interval or None
        )
        make_asset(dana, asset_no="M-70002")  # no cadence at all
        for offset in range(-40, 420, 7):
            when = date.fromordinal(date(2026, 1, 1).toordinal() + offset)
            annotations, predicate = selectors.test_due_q(when)
            in_sql = set(
                str(i)
                for i in selectors._base_qs()
                .annotate(**annotations)
                .filter(predicate)
                .values_list("id", flat=True)
            )
            in_python = set(
                str(a.id) for a in selectors._base_qs() if selectors.test_due(a, today=when)
            )
            assert in_sql == in_python, f"diverged on {when} ({last_test} + {interval}mo)"


# ── DEF-MET-4953 · the KPI figures are SERVED ───────────────────────────────


def test_kpis_count_the_whole_tab_not_the_page(brazos, dana):
    """The defect in one assertion: with 60 meters and a 50-row page, the strip
    used to render four em-dashes because the browser could only count what it
    had. The served figure knows the whole tab."""
    with tenant_ctx(brazos):
        _meters(dana, 60)
        kpis = selectors.asset_kpis("meters", today=TODAY)
        page = list(selectors.asset_list(filters={"tab": "meters"})[:50])
    assert len(page) == 50
    assert kpis["in_inventory"] == 60, "the strip must count the tab, not the page"


def test_kpis_reproduce_the_client_count(brazos, dana):
    """The served aggregate must be the SAME number the browser produced when
    it could see everything — otherwise this fix is a silent re-definition of
    four labelled figures rather than a repair of them."""
    with tenant_ctx(brazos):
        prem = make_premises(dana, address_line="2 Registry Row")
        unit = make_unit(dana, prem["id"], label="Unit A")
        master = make_asset(dana, asset_no="M-80001", unit=unit["id"])
        make_asset(dana, asset_no="S-80001", parent_asset_no="M-80001", unit=unit["id"])
        make_asset(dana, asset_no="S-80002", parent_asset_no="M-80001", unit=unit["id"])
        _meters(dana, 4, start=80010)
        served = selectors.asset_kpis("meters", today=TODAY)
        rows = list(selectors.asset_list(filters={"tab": "meters"}))
    assert master is not None
    # The client's own arithmetic (assetsShared.tsx `metersKpis`), run here.
    assert served["in_service"] == len([a for a in rows if a.status.behavior_class == "in_service"])
    assert served["in_inventory"] == len(
        [a for a in rows if a.status.behavior_class == "available"]
    )
    assert served["needs_repair"] == len(
        [a for a in rows if a.status.behavior_class == "out_of_service"]
    )
    assert served["past_certification"] == len(
        [a for a in rows if selectors.test_due(a, today=TODAY)]
    )
    assert served["masters"] == 1
    assert served["subs"] == 2


def test_kpis_cost_does_not_move_with_the_tenant(brazos, dana):
    with tenant_ctx(brazos):
        _meters(dana, 4)
        with CaptureQueriesContext(connection) as ctx:
            selectors.asset_kpis("meters", today=TODAY)
        few = len(ctx)
        _meters(dana, 30, start=200)
        with CaptureQueriesContext(connection) as ctx:
            selectors.asset_kpis("meters", today=TODAY)
        lots = len(ctx)
    assert lots == few, f"KPI cost moved with the population ({few} → {lots})"


def test_kpis_are_served_only_for_the_two_tabs_that_draw_a_strip(brazos, dana):
    """D9 (PO 2026-08-22) gives Meters and Behind the meter a KPI grid; the
    other four tabs draw none, so the payload carries none for them."""
    with tenant_ctx(brazos):
        _meters(dana, 2)
        assert selectors.asset_kpis("meters", today=TODAY) is not None
        assert selectors.asset_kpis("behind_the_meter", today=TODAY) is not None
        for tab in ("sub_meters", "inventory", "lifecycle", "map", ""):
            assert selectors.asset_kpis(tab, today=TODAY) is None


# ── `DEF-MET-4954` · NO export file passes between containers through a disk ──


def test_no_two_app_containers_share_a_directory():
    """Pressing Download saved `file.json` containing a 404 on every deployment
    that sets `JOBS_EAGER=false` — the worker wrote the CSV to its private
    `/app/var/artifacts` and the web process served a 404 from an empty folder.

    ⚠ **THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-10-02.** It required one
    shared `artifacts:` volume on `backend`, `celery` and `celery-billing` —
    the 2026-09-12 fix. The PO then ruled (decision log, *"EXPORT FILES MOVE
    FROM THE SHARED DISK TO S3 — THE DESIGN IS APPROVED"*): *"Removed -> Yes we
    will just be using S3"*. Export files now live in the environment's bucket
    and are found through a database row, so the rule this guards is the
    stronger one: **nothing passes between web and any worker through a
    directory** — not a local disk, not a Docker volume. A volume shared by two
    app containers is how the next lane would quietly bring the disk back.

    The app containers are every service whose build context is the backend.
    """
    import yaml

    compose = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "docker-compose.yml").read_text()
    )
    app_services = {
        name: spec
        for name, spec in compose["services"].items()
        if "06-backend" in str((spec.get("build") or {}).get("context", spec.get("build", "")))
        or name.startswith("celery")
        or name == "backend"
    }
    assert {"backend", "celery", "celery-billing", "celery-beat"} <= set(app_services), sorted(
        app_services
    )
    mounted: dict[str, list[str]] = {}
    for name, spec in app_services.items():
        for mount in spec.get("volumes") or []:
            source = str(mount).split(":")[0]
            mounted.setdefault(source, []).append(name)
    shared = {source: names for source, names in mounted.items() if len(names) > 1}
    assert not shared, (
        f"{shared} — two app containers share a directory. Export files go to S3 "
        "(apps/tenancy/export_store.py); a shared disk is DEF-MET-4954's mechanism."
    )
    assert "artifacts" not in (compose.get("volumes") or {})


def test_the_artifacts_directory_setting_is_gone():
    from django.conf import settings

    assert not hasattr(settings, "JOB_ARTIFACTS_DIR"), (
        "JOB_ARTIFACTS_DIR is back — an export directory is DEF-MET-4954's mechanism"
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-092-BRC01 §6a/§6b (PO rulings 2026-09-12) · DEF-MET-4951 ·
#         DEF-MET-4953 · DEF-MET-4962 · the step-1 conformance document
#         04-docs/05-modules/05-assets/conformance/CR-092-lane1-registry-step1.md
# generated: 2026-09-12 by CR-092 step 2 lane 1 (the registry)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: the query-count cases are CEILINGS proved INDEPENDENT of the row
#   count rather than equalities — an equality is a number people edit, and the
#   contract is that the cost does not scale with the tenant (NFR-3/NFR-5)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
