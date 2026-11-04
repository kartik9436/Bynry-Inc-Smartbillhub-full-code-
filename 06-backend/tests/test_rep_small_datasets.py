# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · lane DS-SMALL — the last three dataset queries.
# Covers:   apps/work/work_orders_dataset.py · apps/assets/assets_dataset.py ·
#           apps/rating/rate_schedules_dataset.py
# Rules:    NFR-3 (the page is cut in SQL) · NFR-5 (no cap on the export path)
#           · hard rule 3 (a quantity carries its unit) · hard rule 8 (an
#           address is walked to `premises`) · brief §7.2 (a dataset states ONE
#           grain) · §7.2.2 (additivity) · BR-REP-024 (never a 0 where a figure
#           could not be computed) · BR-AST-031 (filters key off the behaviour
#           class, never the tenant's label)
# ───────────────────────────────────────────────────────
"""THE THREE SMALL DATASETS, AND THE TWO REPORTS THEY REFUSE BY NAME.

⚠ **EVERY CASE ASSERTS A KNOWN NON-ZERO COUNT.** A query returning nothing
reads as *no error*: `len(rows) == 0` passes on a working query with an empty
fixture and on a broken one alike. So each fixture seeds a stated number and
each assertion names it, with a positive case beside every zero.

⚠ **NOTHING HERE IS SKIPPED.** A `pytest.skip` that fires when a fixture lacks
something is a false pass wearing a green tick — a sibling's skipped silently
and its file reported green over the one assertion that mattered. If a fixture
cannot be built, this file fails.

⚠ **THE PAGING AND SAVEPOINT PROOFS RUN ON REAL PostgreSQL SEPARATELY.**
`config/settings/test.py` hardcodes in-memory SQLite (hard-won law 14), so the
cost measurement is `10-scripts/ds_small_datasets_cost.py` and the figures it
prints are quoted in the lane report rather than asserted here.
"""

from __future__ import annotations

import inspect
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from apps.assets import assets_dataset
from apps.rating import rate_schedules_dataset
from apps.reports import datasets
from apps.work import work_orders_dataset

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import make_asset, make_premises, make_unit
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

UTC = timezone.utc

#: The fixture's stated sizes. Every assertion below names one of these rather
#: than a shape, so a query that silently returns nothing cannot pass.
ORDERS_RAISED = 7
ORDERS_COMPLETED = 4
ORDERS_OPEN = 2
ORDERS_CANCELLED = 1
METERS = 5
SPARES = 2


# ── fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def a_fleet(brazos, dana):
    """FIVE meters: three fitted to a premises, TWO spare in the store room.

    The two spares are the drawn warning's own case (p064): *"a spare meter has
    no premises and no read, and both cells show an em-dash rather than a
    blank."* They are created without a unit, so they carry no service point,
    so they reach no premises — which is `not_applicable`, not a data gap.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="4400 Industrial Pkwy")
        unit = make_unit(dana, premises["id"])
        # ⚠ **THE KEYWORD IS `unit_id`, AND `unit` IS THE UNIT OF MEASURE.**
        # The first draft passed `unit=unit["id"]`, which is `create_asset`'s
        # UoM field, so no service point was raised and ALL FIVE meters came
        # back spare — five `not_applicable` premises cells over a fixture that
        # was supposed to hold three fitted meters. The test caught it because
        # it asserts BOTH sides of the absence rule and not only the spares;
        # an assertion that had checked spares alone would have passed on a
        # fixture with no fitted meter in it at all.
        # ⚠ `install_date` IS REQUIRED WHEN AN ASSET IS ASSIGNED (BR-AST-011),
        # and the spares below deliberately carry none — a meter in the store
        # room has not been installed anywhere. That asymmetry is the fixture
        # exercising R31's AGE column too: three meters have an age and two do
        # not, which is the same `not_applicable` rule as the premises cell.
        fitted = [
            make_asset(
                dana,
                asset_no=f"MTR-00{n}",
                service="water",
                unit_id=unit["id"],
                install_date="2019-01-04",
            )
            for n in (4182, 2044, 3011)
        ]
        spares = [make_asset(dana, asset_no=f"MTR-00{n}", service="water") for n in (5010, 5011)]
    return {"tenant": brazos, "actor": dana, "fitted": fitted, "spares": spares}


@pytest.fixture()
def some_orders(brazos, dana):
    """SEVEN work orders in one window: 4 completed, 2 open, 1 cancelled.

    ⚠ **THE CANCELLED ONE IS THE WHOLE FIXTURE.** R33's drawn tiles are
    `Raised 148 · Completed 132 · Open 16`, and 148 − 132 = 16 only because the
    illustration has no cancellation in it (B14 rule 37 — a drawn figure is an
    illustration). With one cancellation, `raised − completed` is 3 and `open`
    is 2, so a query computing the subtraction goes RED here and a query
    counting the open states passes.
    """
    from apps.work import connection_models as work_tables

    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="118 Cedar St")
        raised = datetime(2026, 9, 2, 8, 0, tzinfo=UTC)
        made = []
        for index in range(ORDERS_RAISED):
            if index < ORDERS_COMPLETED:
                state, completed = work_tables.WO_COMPLETED, raised + timedelta(days=index + 1)
            elif index < ORDERS_COMPLETED + ORDERS_OPEN:
                state, completed = work_tables.WO_PLANNED, None
            else:
                state, completed = work_tables.WO_CANCELLED, None
            order = work_tables.WorkOrder.objects.create(
                tenant_id=brazos.id,
                order_no=f"WO-2609-04{index:02d}",
                premises_id=premises["id"],
                type="Meter change",
                state=state,
                completed_at=completed,
                minutes_on_site=90 if completed else None,
            )
            # `created_at` is `auto_now_add`, so the window has to be stamped
            # after the insert. A filter on the raise date is the seeded basis
            # and a fixture that left them all at "now" could not test it.
            work_tables.WorkOrder.objects.filter(pk=order.pk).update(created_at=raised)
            order.refresh_from_db()
            made.append(order)
    return {"tenant": brazos, "orders": made}


# ── §7.2 — a dataset states ONE grain, and two reports do not share it ───────


def test_work_orders_refuses_r34_by_name_carrying_its_real_grain(brazos, some_orders):
    """R34 Disconnect & Reconnect is ONE ACCOUNT, not one work order.

    Its drawing (p065) is dated *work orders + accounts* and every drawn row is
    an account carrying the whole five-state sequence. The refusal must NAME
    the grain and the reads it needs, or it is an empty report with a footing
    total and no explanation.
    """
    with tenant_ctx(brazos):
        result = work_orders_dataset.work_orders_dataset(per=50)

    assert result["grain"] == "one work order"
    assert result["total"] == ORDERS_RAISED
    codes = [problem["code"] for problem in result["problems"]]
    assert "disconnect_and_reconnect_is_one_account_not_one_work_order" in codes
    refusal = next(p for p in result["problems"] if p["code"].startswith("disconnect"))
    assert "ACCOUNT" in refusal["detail"]
    assert refusal["wanted_reads"], "a refusal with no wanted read is a shrug"


def test_rate_schedules_refuses_r37_by_name_carrying_its_real_grain(brazos):
    """R37 Rate Change History is ONE COMPONENT CHANGE, not one version.

    A version owns many priced components and the dataset declares a single
    `unit_rate` column, so serving R37 here would name one of several rates
    under an unqualified heading on a compliance report.
    """
    with tenant_ctx(brazos):
        result = rate_schedules_dataset.rate_schedules_dataset(per=50)

    assert result["grain"] == "one rate-schedule version"
    codes = [problem["code"] for problem in result["problems"]]
    assert "rate_change_history_is_one_component_change_not_one_version" in codes
    refusal = next(p for p in result["problems"] if p["code"].startswith("rate_change"))
    # The `audit` half of the drawn source must be refused BY NAME, because
    # `audit_log` is pruned with no row type exempt (`OQ-1340`).
    assert "audit_log" in refusal["detail"]
    assert refusal["wanted_reads"]


def test_assets_serves_r31_because_the_grains_agree(brazos, a_fleet):
    """R31 Meter Fleet IS one row per meter — the one of the four that is served."""
    with tenant_ctx(brazos):
        result = assets_dataset.assets_dataset(per=50)

    assert result["grain"] == "one asset"
    assert result["total"] == METERS
    assert len(result["rows"]) == METERS
    assert result["totals"]["assets"] == METERS
    # A positive case beside the zero: some meters are spare and some are not.
    assert result["totals"]["spare"] == SPARES
    assert result["totals"]["assets"] > result["totals"]["spare"] > 0


# ── the drawn warning: an em-dash is not a blank (p064) ─────────────────────


def test_a_spare_meter_states_not_applicable_and_a_fitted_one_does_not(brazos, a_fleet):
    """*"Blank reads as missing data; the dash reads as not applicable."*

    A `None` alone cannot carry that difference, so the absence says which kind
    it is. Both sides are asserted: two spares say `not_applicable` and three
    fitted meters say nothing at all.
    """
    with tenant_ctx(brazos):
        rows = assets_dataset.assets_dataset(per=50)["rows"]

    spare_rows = [row for row in rows if row.premises_absence == "not_applicable"]
    fitted_rows = [row for row in rows if row.premises_absence is None]
    assert len(spare_rows) == SPARES
    assert len(fitted_rows) == METERS - SPARES
    assert all(row.premises_no is None for row in spare_rows)
    assert all(row.premises_no is not None for row in fitted_rows)


# ── hard rule 3 — a quantity carries its unit, and a size is never summed ───


def test_a_size_carries_its_unit_and_no_total_is_published_for_it(brazos, a_fleet):
    with tenant_ctx(brazos):
        result = assets_dataset.assets_dataset(per=50)

    assert result["additivity"]["size"] == "not_summable"
    assert "size" not in result["totals"]
    assert all(row.size_unit is not None for row in result["rows"] if row.size is not None)


def test_a_duration_is_hours_and_says_so(brazos, some_orders):
    with tenant_ctx(brazos):
        result = work_orders_dataset.work_orders_dataset(per=50)

    assert result["totals"]["duration_unit"] == "hours"
    # 4 completed orders × 90 minutes = 6.0 hours. A NUMBER, not a shape.
    assert result["totals"]["duration"] == Decimal("6.0000")
    assert all(row.duration_unit == "hours" for row in result["rows"])


# ── §7.2.2 — additivity is declared, and a count of meters is SEMI ──────────


def test_the_declared_additivity_matches_the_registry(brazos, a_fleet, some_orders):
    """A measure declaring one thing in `datasets.py` and another in its query
    is a declaration that reads correct and enforces nothing."""
    with tenant_ctx(brazos):
        fleet = assets_dataset.assets_dataset(per=50)
        orders = work_orders_dataset.work_orders_dataset(per=50)

    # A count of meters is a BALANCE AS AT A DATE — semi-additive, never
    # summable across time.
    assert datasets.ASSETS.measure("assets").additivity == "semi"
    assert fleet["additivity"]["assets"] == "semi"
    assert datasets.DIM_TIME in datasets.ASSETS.measure("assets").forbidden_across

    # An order raised is an EVENT — fully additive.
    assert datasets.WORK_ORDERS.measure("orders").additivity == "full"
    assert orders["additivity"]["orders"] == "full"
    # A percentage is recomputed from its components, never averaged.
    assert datasets.WORK_ORDERS.measure("on_time_pct").additivity == "non"
    assert orders["additivity"]["on_time_pct"] == "non"


def test_a_rate_is_never_totalled(brazos):
    with tenant_ctx(brazos):
        result = rate_schedules_dataset.rate_schedules_dataset(per=50)

    assert result["additivity"]["unit_rate"] == "not_summable"
    assert result["additivity"]["base_charge"] == "not_summable"
    for forbidden in ("unit_rate", "base_charge", "percentage"):
        assert forbidden not in result["totals"]
    # A version IS additive — the positive case beside the three refusals.
    assert result["additivity"]["versions"] == "full"


# ── the tile arithmetic the drawing gets away with and we cannot ────────────


def test_open_is_counted_and_never_raised_minus_completed(brazos, some_orders):
    """A CANCELLED order is neither completed nor open.

    `raised − completed` is 3 here and `open` is 2. The drawn subtraction is an
    illustration (B14 rule 37) and a query that copied it goes red on this line.
    """
    with tenant_ctx(brazos):
        totals = work_orders_dataset.work_orders_dataset(per=50)["totals"]

    assert totals["raised"] == ORDERS_RAISED
    assert totals["completed"] == ORDERS_COMPLETED
    assert totals["open"] == ORDERS_OPEN
    assert totals["raised"] - totals["completed"] == ORDERS_OPEN + ORDERS_CANCELLED
    assert totals["open"] != totals["raised"] - totals["completed"]


def test_totals_are_over_the_whole_filtered_set_not_over_the_page(brazos, some_orders):
    """The KPI tiles must foot to the report whether a page is cut or not."""
    with tenant_ctx(brazos):
        page = work_orders_dataset.work_orders_dataset(page=1, per=2)

    assert len(page["rows"]) == 2
    assert page["total"] == ORDERS_RAISED
    assert page["totals"]["raised"] == ORDERS_RAISED
    assert page["totals"]["completed"] == ORDERS_COMPLETED
    assert page["pages"] == 4


# ── NFR-3 / NFR-5 — the page is cut in SQL and the export cannot inherit it ──


@pytest.mark.parametrize(
    "module,page_fn,stream_fn",
    [
        ("work_orders", "work_orders_dataset", "work_orders_dataset_stream"),
        ("assets", "assets_dataset", "assets_dataset_stream"),
        ("rate_schedules", "rate_schedules_dataset", "rate_schedules_dataset_stream"),
    ],
)
def test_the_export_takes_no_page_and_no_per(module, page_fn, stream_fn):
    """TWO FUNCTIONS, NOT A FLAG.

    A flag would have had the bug a missing parameter cannot: when the billing
    register started paging, its export inherited the screen's page and shipped
    a valid-looking file of 50 rows from a 38,000-row report.
    """
    source = {
        "work_orders": work_orders_dataset,
        "assets": assets_dataset,
        "rate_schedules": rate_schedules_dataset,
    }[module]
    paged = inspect.signature(getattr(source, page_fn)).parameters
    streamed = inspect.signature(getattr(source, stream_fn)).parameters

    assert "page" in paged and "per" in paged
    assert "page" not in streamed, f"{stream_fn} can inherit a screen's page"
    assert "per" not in streamed, f"{stream_fn} can inherit a screen's page size"
    # NFR-5 — the stream is a generator with no ceiling, not a list.
    assert inspect.isgeneratorfunction(getattr(source, stream_fn))


def test_the_page_is_cut_in_sql_and_not_in_python(brazos, some_orders):
    """`LIMIT`/`OFFSET` reach the database, and every page holds distinct rows."""
    from django.db import connection

    with tenant_ctx(brazos):
        with connection.execute_wrapper(_captured := _SqlCapture()):
            first = work_orders_dataset.work_orders_dataset(
                page=1, per=3, sort="order_no", direction="asc"
            )
        # ⚠ `direction` DEFAULTS TO `desc`, which is what a report opens on, so
        # an ascending assertion has to say so. The first draft did not and the
        # test failed on its own omission — which is the check working: a page
        # walk that asserted only row COUNTS would have passed either way.
        second = work_orders_dataset.work_orders_dataset(
            page=2, per=3, sort="order_no", direction="asc"
        )
        third = work_orders_dataset.work_orders_dataset(
            page=3, per=3, sort="order_no", direction="asc"
        )

    assert [len(p["rows"]) for p in (first, second, third)] == [3, 3, 1]
    assert any("LIMIT" in sql.upper() for sql in _captured.statements), _captured.statements
    seen = [row.order_no for p in (first, second, third) for row in p["rows"]]
    assert len(set(seen)) == ORDERS_RAISED, "a non-total order shows one row twice"
    assert seen == sorted(seen), "the sort was not applied"


def test_the_stream_returns_every_row_and_the_page_returns_a_page(brazos, some_orders):
    with tenant_ctx(brazos):
        paged = work_orders_dataset.work_orders_dataset(page=1, per=2)
        streamed = list(work_orders_dataset.work_orders_dataset_stream())

    assert len(paged["rows"]) == 2
    assert len(streamed) == ORDERS_RAISED
    assert len({row.order_id for row in streamed}) == ORDERS_RAISED


# ── hard rule 8 — an address is WALKED, never a column of its own ───────────


def test_a_work_order_walks_to_its_premises(brazos, some_orders):
    """*"The premises column walks to premises like every other address in the
    product — the work order declares no address of its own."*"""
    with tenant_ctx(brazos):
        rows = work_orders_dataset.work_orders_dataset(per=50)["rows"]

    assert len(rows) == ORDERS_RAISED
    assert all(row.premises_address == "118 Cedar St" for row in rows)
    assert all(row.premises_no is not None for row in rows)


# ── BR-AST-031 — a filter keys off the behaviour class, never the label ─────


def test_the_spare_filter_survives_a_tenant_renaming_the_stage(brazos, a_fleet):
    """A tenant renaming *Inventory/Spare* to *Store room* must not empty the tile."""
    from apps.assets import models as asset_models

    with tenant_ctx(brazos):
        renamed = asset_models.AssetLifecycleStage.objects.filter(
            tenant_id=brazos.id, behavior_class=assets_dataset.CLASS_AVAILABLE
        ).update(name="Store room")
        assert renamed >= 1, "the fixture has no available stage to rename"
        result = assets_dataset.assets_dataset(status="available", per=50)

    assert result["total"] == SPARES
    assert all(row.status == "Store room" for row in result["rows"])


# ── BR-REP-024 — never a 0 where a figure could not be computed ─────────────


def test_on_time_is_null_and_not_zero_when_nothing_was_promised(brazos, some_orders):
    """No order in the fixture carries a `due_at`, so nothing was promised.

    `0.0%` on time and *nobody promised a date* are opposite facts.
    """
    with tenant_ctx(brazos):
        result = work_orders_dataset.work_orders_dataset(per=50)

    assert result["totals"]["on_time_pct"] is None
    assert result["totals"]["promised"] == 0
    # A positive figure in the same result, so a query returning nothing at all
    # cannot pass this case.
    assert result["totals"]["completed"] == ORDERS_COMPLETED
    codes = [problem["code"] for problem in result["problems"]]
    assert "on_time_is_undefined_for_an_order_with_no_due_date" in codes


def test_days_to_close_is_none_on_an_open_order_and_a_number_on_a_closed_one(
    brazos, some_orders
):
    with tenant_ctx(brazos):
        rows = work_orders_dataset.work_orders_dataset(per=50)["rows"]

    closed = [row for row in rows if row.completed_on is not None]
    still_open = [row for row in rows if row.status == "planned"]
    assert len(closed) == ORDERS_COMPLETED
    assert len(still_open) == ORDERS_OPEN
    assert all(row.days_to_close is not None and row.days_to_close > 0 for row in closed)
    assert all(row.days_to_close is None for row in still_open)


def test_the_due_for_change_tile_and_its_rows_are_struck_with_one_rule(brazos, a_fleet):
    """A row reading *due* under a tile that does not count it is a footing
    failure, and it is invisible: both numbers look like numbers.

    Measured on the PostgreSQL fixture before this was fixed: the tile said 1
    over 30,055 meters whose rows said otherwise, because the tile counted
    `certification_due` in SQL and the row fell back to `last_test_date` plus
    its interval. One rule now, and this asserts the two agree.
    """
    from apps.assets import models as asset_models

    with tenant_ctx(brazos):
        # Two meters carry a TEST cadence and no stated change date — the exact
        # shape that used to make the row and the tile disagree.
        asset_models.Asset.objects.filter(tenant_id=brazos.id).update(
            certification_due=None,
            last_test_date=date(2016, 1, 1),
            test_interval_months=12,
        )
        result = assets_dataset.assets_dataset(as_of=date(2026, 9, 25), per=50)

    rows_due = [row for row in result["rows"] if row.is_due_for_change]
    assert len(result["rows"]) == METERS
    assert result["totals"]["due_for_change"] == len(rows_due) == 0
    # The test cadence is still served, under its own name and its own question.
    assert result["totals"]["test_cadence_only"] == METERS
    assert all(row.is_test_due for row in result["rows"])
    # BR-REP-024 — null, never 0.0, when no meter states a change date at all.
    assert result["totals"]["due_for_change_pct"] is None


def test_the_as_of_basis_says_the_stage_is_as_is_and_not_as_was(brazos, a_fleet):
    """§7.2.4's fault line, stated rather than assumed."""
    with tenant_ctx(brazos):
        result = assets_dataset.assets_dataset(as_of=date(2026, 9, 25), per=50)

    assert result["as_of"] == date(2026, 9, 25)
    codes = [problem["code"] for problem in result["problems"]]
    assert "lifecycle_stage_is_today_s_even_when_as_of_is_not" in codes


# ── hard rule 2 — nothing here rounds a signed rate ─────────────────────────


def test_the_stored_scales_are_published_and_nothing_is_rounded(brazos):
    """`OQ-620(a)`: a rate is four decimals. Hard rule 2: a percentage stores
    six and DISPLAYS two, which is `DEF-REP-6829` against the drawing.

    This module displays nothing, so it records the scales rather than applying
    them — a rounding struck here would be a rate change nobody signed.
    """
    with tenant_ctx(brazos):
        result = rate_schedules_dataset.rate_schedules_dataset(per=50)

    assert result["precision"]["rate_scale"] == 4
    assert result["precision"]["percent_scale"] == 6
    assert datasets.RATE_SCHEDULES.column("unit_rate").scale == 4
    assert datasets.RATE_SCHEDULES.column("percentage").scale == 6


# ── hard rule 4 / the module boundary — these queries write nothing ─────────


@pytest.mark.parametrize(
    "path",
    [
        "apps/work/work_orders_dataset.py",
        "apps/assets/assets_dataset.py",
        "apps/rating/rate_schedules_dataset.py",
    ],
)
def test_a_dataset_query_writes_nothing(path):
    """`G78` is the gate for `work`; this is the same claim for all three, made
    against the source rather than against a comment that claims it."""
    from pathlib import Path

    source = Path(__file__).resolve().parents[1].joinpath(path).read_text()
    for verb in (".save(", ".create(", ".update(", ".delete(", ".bulk_create("):
        assert verb not in source, f"{path} calls {verb}"


class _SqlCapture:
    """Every statement the block issued, so `LIMIT` can be asserted rather than
    assumed. A page built with a Python slice would pass an assertion about row
    counts and fail this one, which is the only assertion that separates them."""

    def __init__(self) -> None:
        self.statements: list[str] = []

    def __call__(self, execute, sql, params, many, context):
        self.statements.append(sql)
        return execute(sql, params, many, context)
