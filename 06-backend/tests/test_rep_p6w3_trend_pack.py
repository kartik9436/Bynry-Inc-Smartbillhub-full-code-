# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 `P6.11` wave 3 — R43 Trend Pack (`apps/ledger/
#           trend_pack.py`), the read model that replaces `DEF-REP-6937`'s
#           ledger-line answer.
# Rules:    `BR-REP-034` (the target is TYPED and empty on every tenant today —
#           the tile degrades to the figure alone; day-prorated comparisons are
#           FORBIDDEN) · `BR-REP-009` (collection % = cash applied to bills in
#           period ÷ billed in period) · `BR-REP-011` (DSO needs twelve months
#           of billed) · `BR-REP-022` (the DSO target is a tenant setting,
#           default 15) · `BR-REP-024` (NULL with a reason, never 0) ·
#           `BR-TEN-022` (the period card is COMPUTED) · `BR-TEN-043` (the
#           business date is an argument, never a clock) · CLAUDE.md hard rule
#           2 (money 4 decimals, percentages 6, both DISPLAY 2) · hard rule 5
#           (only the posting service writes journal lines)
# ───────────────────────────────────────────────────────
"""R43 — ONE ROW PER FISCAL PERIOD, AND THE FOUR FIGURES IT IS MADE OF.

⚠ **THE UNTYPED TARGET IS PROVED FIRST, BECAUSE IT IS THE STATE EVERY TENANT IS
IN.** `BR-REP-034`'s ruled degrade is not a stub and not an edge case: nothing
in this deployment publishes `monthly_revenue_target`, so TARGET is NULL on
every row of every tenant and the REVENUE VS TARGET tile shows the figure
alone. A suite that tested the typed case first would be testing the state
nobody is in.

⚠ **THE SUITE RUNS ON IN-MEMORY SQLITE** (`config/settings/test.py` hardcodes it
and ignores `DATABASE_URL` — CLAUDE.md hard-won law 14), so these cases prove
the SHAPE and the ARITHMETIC and can say nothing about cost, query plans or
RLS. The PostgreSQL half is `10-scripts/p6w3_cost.py` and the figures are
published in the R43 register row.

⚠ **EVERY JOURNAL LINE HERE GOES THROUGH THE POSTING SERVICE.** Hard rule 5
makes it the sole writer and `ledger_sole_writer_guard()` raises by name on an
ORM `create()`, so a fixture that went round it would be proving this report
against rows the product cannot produce.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.ledger import (
    chart,
    models as ledger_models,
    posting,
    reporting,
    trend_pack as r43,
)
from apps.reports import runner

from tests.ledger_le_fixtures import a_request, gl, line
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: A day inside the tenant's own calendar, passed as an ARGUMENT (`BR-TEN-043`).
#: Provisioning seeds `fy_start_month=1` and `close_cadence="monthly"`, so the
#: periods are calendar months of 2026 and `AS_OF` sits in P9.
AS_OF = date(2026, 9, 15)

#: Two figures, chosen so every assertion below names a NUMBER rather than a
#: shape: billed 800.00 in August, 1,000.00 in September.
AUGUST_BILLED = Decimal("800.0000")
SEPTEMBER_BILLED = Decimal("1000.0000")


def _bill(tenant, *, on: date, amount: Decimal, key: str) -> None:
    """One issued bill, as the ledger sees it: AR debited, revenue credited.

    `source_type="invoice"` on the ENTRY is what makes the debit count as
    BILLED — `reporting.BILL_SOURCE_TYPES` — rather than as any other movement
    on the receivable.
    """
    # ⚠ **THE TENANT'S OWN DESIGNATED AR ACCOUNT, LOOKED UP AND NEVER TYPED.**
    # `chart.AR` is a DESIGNATION (`"accounts_receivable"`) and not a code —
    # `tests/test_us_led_005_gl_designations.py` renumbers it to 1150 to prove
    # exactly that — so a fixture hardcoding `1200` would post to an account
    # this report does not read and every figure below would be 0.00.
    ar_id = reporting._designated_account_id(chart.AR)  # noqa: SLF001
    assert ar_id is not None, "the seeded chart designates no AR account"
    ar = ledger_models.LedgerAccount.objects.get(id=ar_id)
    revenue = gl(tenant, "4100", type_="revenue", name="Water revenue")
    posting.post(
        a_request(
            (
                line(ar, ledger_models.SIDE_DEBIT, amount),
                line(revenue, ledger_models.SIDE_CREDIT, amount),
            ),
            key=f"p6w3|{key}",
            entry_date=on,
            source_type="invoice",
        )
    )


@pytest.fixture()
def booked(brazos):
    """Two months of bills on the books, in two different fiscal periods."""
    with tenant_ctx(brazos):
        _bill(brazos, on=date(2026, 8, 12), amount=AUGUST_BILLED, key="aug")
        _bill(brazos, on=date(2026, 9, 12), amount=SEPTEMBER_BILLED, key="sep")
    return brazos


# ── the grain ───────────────────────────────────────────────────────────────
def test_one_row_per_fiscal_period_and_twelve_of_them(booked):
    """p059's **Periods 12**, oldest first, and no ledger line anywhere."""
    with tenant_ctx(booked):
        answer = r43.trend_pack(as_of=AS_OF, periods=12)
    rows = answer["rows"]
    assert len(rows) == 12
    assert answer["grain"] == "one accounting period"
    # Oldest first, and every window is contiguous with the next.
    for earlier, later in zip(rows, rows[1:]):
        assert earlier.period_end < later.period_start
    # The LAST row is the period containing `as_of`, which is what the tiles
    # are read off.
    assert rows[-1].period_start <= AS_OF <= rows[-1].period_end


def test_the_periods_control_is_clamped_and_never_refused(booked):
    """`BR-SHL-011` — an impossible value falls back or clamps, never errors."""
    with tenant_ctx(booked):
        assert len(r43.trend_pack(as_of=AS_OF, periods=3)["rows"]) == 3
        # Above the ceiling: clamped to it, not refused.
        many = r43.trend_pack(as_of=AS_OF, periods=10_000)["rows"]
    assert len(many) == r43.MAX_PERIODS


# ── the four aggregates ─────────────────────────────────────────────────────
def test_revenue_is_billed_in_that_period_and_lands_in_the_right_row(booked):
    """800.00 in August's row and 1,000.00 in September's — never both in one."""
    with tenant_ctx(booked):
        rows = {row.period_start.month: row for row in r43.trend_pack(as_of=AS_OF)["rows"]}
    assert rows[8].revenue == AUGUST_BILLED
    assert rows[9].revenue == SEPTEMBER_BILLED
    # A period that billed nothing is a real 0.00 and is not a gap.
    assert rows[7].revenue == Decimal("0")


def test_accounts_is_as_of_the_period_end_and_is_not_a_movement(booked):
    """The census's own membership rule, read through the seam.

    ⚠ **IT IS THE SAME COUNT R22 WOULD SHOW ON THAT DAY.** The assertion is
    against `accounts_dataset.accounts_on_the_books`, not against a number typed
    here, because the point of the seam is that there is ONE derivation — a
    hand-typed expectation would pass over the two disagreeing.
    """
    from apps.customers import accounts_dataset

    with tenant_ctx(booked):
        rows = r43.trend_pack(as_of=AS_OF)["rows"]
        for row in rows:
            assert row.accounts == accounts_dataset.accounts_on_the_books(as_of=row.period_end)


def test_rebills_counts_rebills_and_nothing_else(booked):
    """The column is `invoices.bill_type='rebill'`, never every bill."""
    with tenant_ctx(booked):
        rows = r43.trend_pack(as_of=AS_OF)["rows"]
    # No rebill was issued in this fixture, so every row is a real 0 rather
    # than a gap — the seam answered, and answered nothing.
    assert all(row.rebills == 0 for row in rows)
    assert all(row.rebills_absence is None for row in rows)


# ── the two ratios, and the absences that are the point ─────────────────────
def test_the_target_is_null_on_every_row_and_says_why(booked):
    """`BR-REP-034`'s RULED DEGRADE — the state every tenant is in.

    The PO ruled on 2026-08-18 (option B) that the target is TYPED, and ruled
    the fallback in the same breath: *"With no target typed, the tile degrades
    to … the figure alone, no sub-line"*. `monthly_revenue_target` is published
    by nobody, so this is not an edge case — it is the default.
    """
    with tenant_ctx(booked):
        answer = r43.trend_pack(as_of=AS_OF)
    assert all(row.target is None for row in answer["rows"])
    assert all(
        row.target_absence == r43.GAP_TARGET_IS_TYPED_AND_NONE_IS_TYPED["code"]
        for row in answer["rows"]
    )
    # The tile degrades the same way, with its reason and never with a 0%.
    assert answer["tiles"]["revenue_vs_target"] is None
    assert (
        answer["tiles"]["revenue_vs_target_absence"]
        == r43.GAP_TARGET_IS_TYPED_AND_NONE_IS_TYPED["code"]
    )
    # ⚠ AND THE FIGURE ITSELF IS STILL THERE — *the figure alone* is the ruling,
    # so a NULL percentage over a missing revenue would be the wrong degrade.
    assert answer["tiles"]["revenue_latest"] == SEPTEMBER_BILLED
    # The absence is REPORTED, not merely present on the row.
    assert r43.GAP_TARGET_IS_TYPED_AND_NONE_IS_TYPED["code"] in {
        gap["code"] for gap in answer["problems"]
    }


def test_dso_is_null_until_twelve_months_of_books_exist(booked):
    """`BR-REP-011` — and the NULL is the state a new tenant is in.

    `reporting.py` already made this call on the S36 strip in its own words: a
    DSO computed on three months and labelled as twelve *"reads as a collections
    crisis that is not happening"*. R43 answers it per ROW, so a period whose
    twelve-month window reaches back past the first posted entry is a dash.
    """
    with tenant_ctx(booked):
        answer = r43.trend_pack(as_of=AS_OF)
    assert all(row.dso is None for row in answer["rows"])
    assert all(
        row.dso_absence == r43.GAP_DSO_NEEDS_TWELVE_MONTHS["code"] for row in answer["rows"]
    )
    assert answer["tiles"]["dso"] is None
    # ⚠ **A ZERO HERE WOULD BE THE DEFECT.** 0.0 days outstanding is the best
    # possible collections figure and it is what a naive implementation prints.
    assert answer["tiles"]["dso"] != Decimal("0")


def test_a_period_that_billed_nothing_has_no_rate_rather_than_zero_percent(booked):
    """A zero denominator makes the rate UNDEFINED, never 0%.

    0% on a quiet month reads as a collections failure that did not happen,
    which is exactly what `BR-REP-024` is for.
    """
    with tenant_ctx(booked):
        rows = {row.period_start.month: row for row in r43.trend_pack(as_of=AS_OF)["rows"]}
    quiet = rows[7]
    assert quiet.revenue == Decimal("0")
    assert quiet.rate is None
    assert quiet.rate_absence == r43.GAP_RATE_HAS_NO_DENOMINATOR["code"]


def test_the_rate_is_collected_over_billed_in_the_same_period(booked):
    """`BR-REP-009`, as arithmetic over two figures already on the row.

    ⚠ **IT IS NOT ASSERTED AGAINST A TYPED PERCENTAGE.** The fixture posts no
    payment, so the interesting property is the FORM: wherever both figures
    exist, the published rate is the one divided by the other, to six places
    (hard rule 2), and a rate that drifted from its own two columns would be a
    figure a finance officer cannot check against the row it sits on.
    """
    with tenant_ctx(booked):
        rows = r43.trend_pack(as_of=AS_OF)["rows"]
    for row in rows:
        if row.rate is None or row.collected is None:
            continue
        expected = (row.collected / row.revenue * Decimal(100)).quantize(r43.PERCENT_PLACES)
        assert row.rate == expected


# ── the footer that must not exist ──────────────────────────────────────────
def test_there_is_no_total_row_and_the_drawing_is_right(booked):
    """p059 draws no Total, and three of the eight columns cannot be summed.

    RATE and DSO are ratios; ACCOUNTS is as-of, so a column sum reports the
    utility twelve times its own size. A footer holding only the three additive
    figures under a table of eight is worse than no footer.
    """
    with tenant_ctx(booked):
        answer = r43.trend_pack(as_of=AS_OF)
    assert answer["totals"] == {}


# ── the tenant with no fiscal calendar ──────────────────────────────────────
def test_a_tenant_with_no_fiscal_year_start_gets_an_absence_not_twelve_months(booked):
    """`BR-TEN-022` — the period card is COMPUTED and answers None there.

    ⚠ **NOTHING IS SUBSTITUTED.** Twelve calendar months over a utility that
    closes its books on some other calendar would put a bill run in the wrong
    row and read as real, which is the whole of `BR-REP-024`.
    """
    from apps.tenancy import models as tenancy_models

    with tenant_ctx(booked):
        tenancy_models.TenantSettings.objects.filter(tenant_id=booked.id).update(
            fy_start_month=None
        )
        answer = r43.trend_pack(as_of=AS_OF)
    assert answer["rows"] == ()
    assert answer["totals"] == {}
    assert [gap["code"] for gap in answer["problems"]] == [
        r43.GAP_NO_FISCAL_CALENDAR["code"]
    ]


# ── the wire, through the ONE path the screen and the file share ────────────
def test_the_viewer_serves_r43s_own_columns_and_not_the_ledgers(booked):
    """`DEF-REP-6937`'s own assertion, at the layer a clerk reaches."""
    with tenant_ctx(booked):
        answer = runner.run("trend_pack", {"as_of": AS_OF.isoformat()})
    assert answer.columns == (
        "period",
        "revenue",
        "target",
        "collected",
        "rate",
        "dso",
        "accounts",
        "rebills",
    )
    assert len(answer.rows) == 12
    # ⚠ **THE COLUMN KINDS TRAVEL, AND THIS IS THE CASE THAT WOULD HAVE CAUGHT
    # `DEF-REP-6963` AND THE STATEMENT DEFECT BEFORE IT.** Without
    # `column_meta` the money renders at storage width (`8006.640000`) at a
    # clerk while the tile above reads `$8,006.64`, with every other test green.
    meta = answer.payload["column_meta"]
    assert meta["revenue"]["type"] == "money"
    assert meta["target"]["type"] == "money"
    assert meta["collected"]["type"] == "money"
    assert meta["rate"]["type"] == "percent"
    # DSO is a number of DAYS. `percent` here would print `14.10%` at a finance
    # officer — a plausible figure in the wrong unit.
    assert meta["dso"]["type"] == "quantity"
    assert meta["dso"]["unit"] == "days"
    # A count is neither, so it carries no entry and renders as text.
    assert "accounts" not in meta
    assert "rebills" not in meta


def test_the_export_streams_r43s_rows_and_not_the_datasets(booked):
    """`stream_for` must find R43's own generator, not `journal_lines`'.

    ⚠ **THIS IS THE HALF NOBODY LOOKS AT.** Without the `KEY_STREAMS` entry the
    download button writes the ledger's own posted lines into a file headed
    *Trend Pack* — a valid-looking file of the wrong report, which is
    `DEF-REP-6937` surviving its own fix.
    """
    stream = runner.stream_for("trend_pack", "journal_lines")
    assert stream is not None
    with tenant_ctx(booked):
        rows = list(stream({"as_of": AS_OF.isoformat()}))
    assert len(rows) == 12
    assert "period" in rows[0]
    assert "account_code" not in rows[0]


def test_the_download_button_has_somewhere_to_post_to(booked):
    """Turning a report on makes its Download control live.

    The viewer enables the export icon the moment a report RENDERS, so a
    registered key with no export resource is a live control over a 404 — hard-
    won law 2's mirror, and the cost of turning a report on twice running.
    """
    from apps.reports import exports

    assert exports.KEY_TREND_PACK in exports.SLUGS
    assert any(resource.name == exports.KEY_TREND_PACK for resource in exports.RESOURCES)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P6.11 wave 3 (R43 trend_pack; DEF-REP-6937 · BR-REP-034 / BR-REP-009 / BR-REP-011 · 05-prototype/09 Reports Build Brief.pdf p059 read as an image per B14 rule 42)
# screens: S46
# generated: 2026-09-27 by lane REP-P6-W3
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — every case here failed with `ModuleNotFoundError: apps.ledger.trend_pack` before the read model existed, and `runner.run("trend_pack")` answered the journal_lines dataset's own columns.
# exceptions: (1) the untyped TARGET and the absent DSO are asserted FIRST because they are the state every tenant is in, not edge cases · (2) the rate case asserts the FORM rather than a typed percentage, because this fixture posts no payment — the measured figures are in 10-scripts/p6w3_cost.py · (3) sqlite cannot answer a question about cost, a query plan or RLS (hard-won law 14)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
