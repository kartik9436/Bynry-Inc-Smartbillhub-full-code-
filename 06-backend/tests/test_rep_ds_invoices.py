# ── Trace ──────────────────────────────────────────────
# Change:   DS-INVOICES — the `invoices` DATASET query (brief §05 p75, §7.2
#           p83–86 and §08 p90–92, all read as IMAGES per B14 rule 42), and the
#           eight definitions `reports/0003` seeds onto it (drawings p49–p73).
# Rules:    `NFR-3` (universal server pagination) · `NFR-5` (no hard caps) ·
#           `BR-SHL-011` (invalid values fall back or clamp, NEVER error) ·
#           `BR-REP-001` (a money report names its date basis) · `BR-REP-024`
#           (name what you cannot answer — never 0) · CLAUDE.md hard rule 1
#           (tenant scoping) · hard rule 2 (money 4 dp, never a float) ·
#           hard rule 3 (a quantity carries its unit) · hard rule 4 (issued
#           invoices take no UPDATE and no DELETE) · hard rule 8 (an address
#           lives on premises and every other entity walks to it) ·
#           §7.2.2 (additivity — a total that cannot be trusted is refused).
# Impacts:  apps/billing/reporting.py · apps/reports/queries.py ·
#           apps/reports/runner.py · apps/reports/datasets.py ·
#           apps/reports/report_seams.py
# ───────────────────────────────────────────────────────
"""THE `invoices` DATASET'S CONTRACT — the parts a fixture can decide.

⚠ **THIS FILE IS NOT THE PERFORMANCE PROOF.** `config/settings/test.py`
hardcodes in-memory SQLite (hard-won law 14), and on twenty rows a `LIMIT` and
a Python slice are the same two numbers. The measurement is
`10-scripts/ds_invoices_cost.py`, run against a real PostgreSQL 16 clone, and
its figures are quoted in the decision-log row.

**What this file decides, which a benchmark cannot:**

  * the page is the right ROWS and the totals are the whole FILTERED set;
  * the EXPORT does not inherit the screen's page — the defect caught on the
    billing register on 2026-09-26, where a 38,000-row file would have been
    written as a valid-looking fifty rows;
  * `cycle` is a parameter, which is R5's drawing's own warning;
  * the portal scope is a PRIVACY boundary and a landlord reads their own
    account and not their tenant's;
  * the seven definitions this dataset cannot serve are refused BY NAME, with
    a reason naming what each one actually draws;
  * `usage` has no footer total, because gallons plus kilowatt-hours is not a
    number and §7.2.2 says a total that cannot be trusted is refused.

⚠ **EVERY CASE ASSERTS A KNOWN NON-ZERO COUNT.** A query returning nothing
reads as *no error*, and a suite of assertions about an empty result passes
perfectly while the dataset is broken. Where a zero is the point — the portal
sentinel, the cycle that matches nothing — it sits BESIDE a positive case in
the same fixture, so the fixture itself proves the zero is a finding and not an
empty database.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from apps.billing import models as billing_models, reporting as billing_reporting
from apps.reports import datasets, queries, runner

from tests.test_us_bil_025_026_bills_read import a_line, an_account, an_invoice
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

UTC = timezone.utc
WINDOW_START = date(2026, 7, 1)
WINDOW_END = date(2026, 7, 31)


def a_billed_book(tenant, account, *, count: int, cycle=None, prefix: str = "BL-2607"):
    """`count` ISSUED bills in July, one per day, each with three LINES.

    Every bill carries a `base`, a `usage` and a `tax` line, because the three
    money columns of this dataset ARE the line kinds and a fixture whose bills
    have one line cannot tell a correct split from a total copied three times.

    Amounts ASCEND, so a sort by amount and a sort by number are DIFFERENT
    orders — a fixture where every bill costs the same cannot tell a working
    sort from an ignored one.

    ⚠ **`prefix` IS NOT DECORATION.** `invoices` carries a UNIQUE constraint on
    (tenant, invoice_no), which is that rule doing its job — so a fixture that
    bills TWO accounts in one window must number them apart. The first draft
    did not; `test_the_scope_survives_the_stream_too` failed with `UNIQUE
    constraint failed: invoices.tenant_id, invoices.invoice_no`, and the
    CONSTRAINT is what found it rather than a reviewer.
    """
    bills = []
    for index in range(count):
        base = Decimal(f"{10 + index}.0000")
        usage = Decimal(f"{20 + index}.0000")
        tax = Decimal("2.0000")
        invoice = an_invoice(
            tenant,
            account,
            invoice_no=f"{prefix}-{index + 1:06d}",
            issued_at=datetime(2026, 7, 1, 9, 0, tzinfo=UTC) + timedelta(days=index),
            due_date=date(2026, 8, 25),
            subtotal=base + usage,
            tax_total=tax,
            total=base + usage + tax,
            bill_run=cycle,
        )
        a_line(tenant, invoice, account, kind="base", quantity=None, unit=None, amount=base)
        a_line(
            tenant,
            invoice,
            account,
            kind="usage",
            quantity=Decimal("684"),
            unit="kWh",
            amount=usage,
        )
        a_line(tenant, invoice, account, kind="tax", quantity=None, unit=None, amount=tax)
        bills.append(invoice)
    return bills


# ═══════════════════════════════════════════════════════════════════════════
# THE DECLARATION — a grain is a claim about a query, and the query decides
# ═══════════════════════════════════════════════════════════════════════════
def test_the_dataset_states_one_bill_and_says_it_pages():
    """`DEF-REP-6834`. The declaration said *one invoice line* while every one
    of its own columns was a roll-up of lines onto one bill, and R5's drawing
    (p50) puts one row per `BL-…` number on the page. Nothing in this repo read
    the string except the line under a report title, which is how it stayed
    wrong."""
    invoices = datasets.BY_CODE["invoices"]
    assert invoices.grain == "one bill"
    # `P2.12` reads this FIELD rather than a paragraph, so it moved in the same
    # commit as the query and not before it.
    assert invoices.paginates is True
    for name in ("cycle", "status"):
        assert invoices.column(name) is not None, name
    assert "cycle" in invoices.filters


def test_usage_may_not_be_summed_across_services_and_the_declaration_says_so():
    """§7.2.2: *gallons plus kilowatt-hours is not a number*. The declaration is
    what the footer's refusal reads, so papering over it here would make the
    em-dash impossible to render."""
    invoices = datasets.BY_CODE["invoices"]
    usage = invoices.measure("usage")
    assert usage is not None
    assert usage.additivity == datasets.ADD_WITHIN_SERVICE
    assert datasets.DIM_SERVICE in usage.forbidden_across


# ═══════════════════════════════════════════════════════════════════════════
# THE PAGE, AND THE TOTALS THAT DO NOT PAGE WITH IT
# ═══════════════════════════════════════════════════════════════════════════
def test_the_dataset_serves_a_page_and_says_which_one(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_billed_book(brazos, account, count=12)

        first = billing_reporting.invoices_dataset(
            start=WINDOW_START, end=WINDOW_END, page=1, per=5
        )
        last = billing_reporting.invoices_dataset(
            start=WINDOW_START, end=WINDOW_END, page=3, per=5
        )

        assert [row.invoice_no for row in first["rows"]] == [
            f"BL-2607-{n:06d}" for n in range(1, 6)
        ]
        # The LAST page is short and is still a page — 12 rows, 5 to a page.
        assert [row.invoice_no for row in last["rows"]] == ["BL-2607-000011", "BL-2607-000012"]
        assert last["page"] == 3 and last["per"] == 5
        assert first["total"] == last["total"] == 12


def test_the_totals_are_the_whole_filtered_set_and_never_the_page(brazos, dana):
    """CLAUDE.md's own resolution of `DEF-PAY-4221`, as a case: *"the tiles are
    a SQL aggregate over the whole filtered set whether a page is cut or not"*.

    Twelve bills of base 10..21, usage 20..31 and tax 2 each. Every page says
    the same four figures."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_billed_book(brazos, account, count=12)
        base = sum(Decimal(f"{10 + i}.0000") for i in range(12))
        usage = sum(Decimal(f"{20 + i}.0000") for i in range(12))
        tax = Decimal("24.0000")

        for page in (1, 2, 3):
            view = billing_reporting.invoices_dataset(
                start=WINDOW_START, end=WINDOW_END, page=page, per=5
            )
            totals = view["totals"]
            assert totals["bills"] == 12, page
            assert totals["billed"] == base + usage + tax, page
            assert totals["base"] == base, page
            assert totals["usage_revenue"] == usage, page
            assert totals["tax"] == tax, page


def test_a_page_beyond_the_last_clamps_and_never_errors(brazos, dana):
    """`BR-SHL-011` — a saved link on page 9,999 of a three-page report opens
    on the last page and is told which page it got."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_billed_book(brazos, account, count=12)
        view = billing_reporting.invoices_dataset(
            start=WINDOW_START, end=WINDOW_END, page=9999, per=5
        )
        assert view["page"] == 3
        assert len(view["rows"]) == 2


def test_an_unknown_sort_falls_back_and_the_order_is_still_total(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_billed_book(brazos, account, count=6)
        fallback = billing_reporting.invoices_dataset(
            start=WINDOW_START, end=WINDOW_END, sort="frog", per=6
        )
        default = billing_reporting.invoices_dataset(
            start=WINDOW_START, end=WINDOW_END, per=6
        )
        assert len(fallback["rows"]) == 6
        assert [r.invoice_no for r in fallback["rows"]] == [
            r.invoice_no for r in default["rows"]
        ]


def test_amount_descending_is_a_different_order_from_the_default(brazos, dana):
    """A fixture whose bills all cost the same cannot tell a working sort from
    an ignored one, which is why `a_billed_book` ascends."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_billed_book(brazos, account, count=6)
        view = billing_reporting.invoices_dataset(
            start=WINDOW_START, end=WINDOW_END, sort="amount", direction="desc", per=6
        )
        assert [r.invoice_no for r in view["rows"]] == [
            f"BL-2607-{n:06d}" for n in range(6, 0, -1)
        ]


# ═══════════════════════════════════════════════════════════════════════════
# THE EXPORT DOOR — §8.2 p91, and the defect it exists to prevent
# ═══════════════════════════════════════════════════════════════════════════
def test_the_stream_yields_every_row_and_cannot_be_handed_a_page_size(brazos, dana):
    """⚠ **THE REGRESSION.** On 2026-09-26 the billing register started paging
    and its export silently inherited the screen's fifty rows: a clerk would
    have exported a 38,000-row register and received a valid-looking file of
    fifty. `invoices_dataset_stream` takes NO `page` and NO `per`, so there is
    no argument to inherit."""
    import inspect

    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_billed_book(brazos, account, count=12)

        page = billing_reporting.invoices_dataset(
            start=WINDOW_START, end=WINDOW_END, page=1, per=5
        )
        streamed = list(
            billing_reporting.invoices_dataset_stream(start=WINDOW_START, end=WINDOW_END)
        )

        assert len(page["rows"]) == 5
        assert len(streamed) == 12
        assert [r.invoice_no for r in streamed] == [f"BL-2607-{n:06d}" for n in range(1, 13)]

        parameters = inspect.signature(billing_reporting.invoices_dataset_stream).parameters
        assert "page" not in parameters and "per" not in parameters


def test_the_stream_crosses_its_chunk_boundary_without_repeating_or_skipping(brazos, dana):
    """The order ends in `id ASC`, so the sequence is TOTAL and a chunk boundary
    cannot repeat or skip a row the way an ambiguous order can. Five bills over
    a chunk of two is three chunks and two boundaries."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_billed_book(brazos, account, count=5)
        numbers = [
            row.invoice_no
            for row in billing_reporting.invoices_dataset_stream(
                start=WINDOW_START, end=WINDOW_END, chunk=2
            )
        ]
        assert numbers == [f"BL-2607-{n:06d}" for n in range(1, 6)]
        assert len(numbers) == len(set(numbers)) == 5


def test_the_stream_is_a_generator_and_not_a_list(brazos, dana):
    """*"never in memory"* is a property of the RETURN TYPE. A function that
    built a list and returned it would satisfy every assertion above and none
    of the brief's right-hand path."""
    import types

    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_billed_book(brazos, account, count=3)
        stream = billing_reporting.invoices_dataset_stream(
            start=WINDOW_START, end=WINDOW_END
        )
        assert isinstance(stream, types.GeneratorType)
        assert len(list(stream)) == 3


# ═══════════════════════════════════════════════════════════════════════════
# `cycle` — R5's drawing's own warning, built
# ═══════════════════════════════════════════════════════════════════════════
def test_cycle_is_a_parameter_and_a_cycle_that_matches_nothing_returns_nothing(
    brazos, dana
):
    """R5, p50, verbatim: *"The one report where cycle must be a parameter, not
    a date range. Today it runs on a date range only."*

    The zero sits BESIDE the positive case in one fixture, so an empty result
    proves the filter bit rather than proving the database was empty."""
    from apps.metering import models as metering_models

    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        # ⚠ **CREATED, NEVER SKIPPED.** The first draft skipped when the tenant
        # seeded no cycle — and it DID, so the one case proving R5's own drawn
        # warning never ran and the file reported a pass. A skip that depends on
        # fixture data is a check that cannot fail (hard-won law 7).
        cycle, _ = metering_models.Cycle.objects.get_or_create(
            tenant=brazos, code="CY-09B", defaults={"name": "September B"}
        )
        run = billing_models.BillRun.objects.create(
            tenant=brazos,
            cycle=cycle,
            period_start=WINDOW_START,
            period_end=WINDOW_END,
        )
        a_billed_book(brazos, account, count=4, cycle=run)

        matched = billing_reporting.invoices_dataset(
            start=WINDOW_START, end=WINDOW_END, cycle=cycle.code, per=50
        )
        missed = billing_reporting.invoices_dataset(
            start=WINDOW_START, end=WINDOW_END, cycle="CY-NOT-A-CYCLE", per=50
        )

        assert matched["total"] == 4
        assert all(row.cycle_code == cycle.code for row in matched["rows"])
        assert missed["total"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# THE PORTAL SCOPE — a privacy boundary, not a filter
# ═══════════════════════════════════════════════════════════════════════════
def test_a_landlord_reads_their_own_account_and_not_their_tenants(brazos, dana):
    """PO ruling, option (a): at 1408 Elm Street the owner sees their own
    common-area charges and NOT Unit 3's. The query must not be the thing that
    leaks a balance belonging to somebody else.

    Both accounts are billed in the same window, so a scope that did nothing
    would return six rows and pass every other assertion in this file."""
    with tenant_ctx(brazos):
        owner = an_account(brazos, dana, account_no="A-OWNER", label="Common")
        tenant_account = an_account(brazos, dana, account_no="A-UNIT-3", label="Unit 3")
        a_billed_book(brazos, owner, count=2)
        for index in range(4):
            an_invoice(
                brazos,
                tenant_account,
                invoice_no=f"BL-2607-9000{index}",
                issued_at=datetime(2026, 7, 5, 9, 0, tzinfo=UTC),
                total=Decimal("100.0000"),
            )

        everyone = billing_reporting.invoices_dataset(
            start=WINDOW_START, end=WINDOW_END, per=50
        )
        theirs = billing_reporting.invoices_dataset(
            start=WINDOW_START, end=WINDOW_END, account_ids=[owner.id], per=50
        )

        assert everyone["total"] == 6
        assert theirs["total"] == 2
        assert {row.account_no for row in theirs["rows"]} == {"A-OWNER"}
        # And the total FOOTS TO THE SCOPE, not to the building: a scoped page
        # whose footer still counted six would leak the figure without leaking
        # a row.
        assert theirs["totals"]["bills"] == 2


def test_holding_no_accounts_returns_nothing_and_never_everything(brazos, dana):
    """`PORTAL_NOTHING` versus `None` is one keystroke and the opposite meaning.
    The positive case in the same fixture is what proves the zero is a refusal
    and not an empty book."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_billed_book(brazos, account, count=3)

        unscoped = billing_reporting.invoices_dataset(
            start=WINDOW_START, end=WINDOW_END, per=50
        )
        nobody = billing_reporting.invoices_dataset(
            start=WINDOW_START,
            end=WINDOW_END,
            account_ids=billing_reporting.PORTAL_NOTHING,
            per=50,
        )

        assert unscoped["total"] == 3
        assert nobody["total"] == 0
        assert nobody["rows"] == ()


def test_the_scope_survives_the_stream_too(brazos, dana):
    """A privacy boundary applied on the page path and not on the export path
    is a boundary that holds until somebody presses Download."""
    with tenant_ctx(brazos):
        owner = an_account(brazos, dana, account_no="A-OWNER", label="Common")
        other = an_account(brazos, dana, account_no="A-UNIT-3", label="Unit 3")
        a_billed_book(brazos, owner, count=2, prefix="BL-OWNER")
        a_billed_book(brazos, other, count=3, prefix="BL-UNIT3")

        everyone = list(
            billing_reporting.invoices_dataset_stream(start=WINDOW_START, end=WINDOW_END)
        )
        theirs = list(
            billing_reporting.invoices_dataset_stream(
                start=WINDOW_START, end=WINDOW_END, account_ids=[owner.id]
            )
        )
        assert len(everyone) == 5
        assert len(theirs) == 2
        assert {row.account_no for row in theirs} == {"A-OWNER"}


# ═══════════════════════════════════════════════════════════════════════════
# HARD RULES 2 AND 3 — money at its stored precision, a quantity with its unit
# ═══════════════════════════════════════════════════════════════════════════
def test_the_three_money_columns_foot_to_the_bill(brazos, dana):
    """`base` is everything that is neither consumption nor tax, so Σ of the
    three IS Σ of the lines and no line can fall between the columns
    unnoticed."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_billed_book(brazos, account, count=4)
        view = billing_reporting.invoices_dataset(
            start=WINDOW_START, end=WINDOW_END, per=50
        )
        assert len(view["rows"]) == 4
        for row in view["rows"]:
            assert isinstance(row.amount, Decimal)
            assert row.base + row.usage_revenue + row.tax == row.amount
        totals = view["totals"]
        assert totals["base"] + totals["usage_revenue"] + totals["tax"] == totals["billed"]


def test_money_leaves_as_an_exact_decimal_string_and_never_a_float(brazos, dana):
    """Hard rule 2 — stored to 4 decimals, DISPLAY 2, never a float and never
    cents. B4 rounds at finalization and display, and a read model is neither."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_billed_book(brazos, account, count=3)
        payload = queries.invoices_dataset({"from": "2026-07-01", "to": "2026-07-31"})
        assert len(payload["rows"]) == 3
        for row in payload["rows"]:
            for column in ("base", "usage_revenue", "tax", "amount"):
                assert isinstance(row[column], str), column
                assert Decimal(row[column]) == Decimal(row[column])


def test_a_quantity_never_travels_without_its_unit(brazos, dana):
    """Hard rule 3. A read of `684` is not a number anybody can bill or
    compare; `684 kWh` is."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_billed_book(brazos, account, count=2)
        payload = queries.invoices_dataset({"from": "2026-07-01", "to": "2026-07-31"})
        assert len(payload["rows"]) == 2
        for row in payload["rows"]:
            assert row["usage"], row
            for entry in row["usage"]:
                assert set(entry) == {"quantity", "unit"}
                assert entry["unit"] == "kWh"


def test_the_footer_carries_no_usage_total(brazos, dana):
    """§7.2.2 — `usage` is additive WITHIN ONE SERVICE and across nothing else.
    A number here would defeat the em-dash-and-reason refusal before the footer
    ever reached it."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_billed_book(brazos, account, count=2)
        payload = queries.invoices_dataset({"from": "2026-07-01", "to": "2026-07-31"})
        assert len(payload["rows"]) == 2
        assert "usage" not in payload["totals"]
        assert payload["totals"]["billed"] is not None


def test_the_payload_names_its_basis(brazos, dana):
    """`BR-REP-001` — an unlabeled money render is a defect by contract."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_billed_book(brazos, account, count=2)
        payload = queries.invoices_dataset({"from": "2026-07-01", "to": "2026-07-31"})
        assert payload["basis"] == "posting"
        assert len(payload["rows"]) == 2


def test_the_dataset_declares_no_address_column(brazos, dana):
    """Hard rule 8 — an address is stored on `premises` and every other entity
    walks to it. This dataset holds no copy, which is why R8's drawing can say
    *nothing here holds its own copy* about the report built on it."""
    invoices = datasets.BY_CODE["invoices"]
    names = {column.name for column in invoices.columns}
    assert not (names & {"address", "service_address", "city", "postal_code", "locality"})
    # And the premises DIMENSION is how a report reaches one.
    assert "premises" in invoices.dimension_names()


# ═══════════════════════════════════════════════════════════════════════════
# HARD RULE 4 — a correction is a NEW ROW and the register shows both
# ═══════════════════════════════════════════════════════════════════════════
def test_a_corrected_bill_appears_as_two_rows_and_never_as_one_edited_row(brazos, dana):
    """R6's warning, verbatim: *"An adjustment is a new row, never an edit.
    Issued invoices take no UPDATE and no DELETE."*

    The corrected original and the replacement are BOTH issued documents and
    both are in the register, typed as themselves. A dataset that showed one
    edited row would be describing a history this product cannot produce."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        original = an_invoice(
            brazos,
            account,
            invoice_no="BL-2607-000500",
            issued_at=datetime(2026, 7, 10, 9, 0, tzinfo=UTC),
            total=Decimal("247.8700"),
            status=billing_models.INVOICE_CORRECTED,
        )
        replacement = an_invoice(
            brazos,
            account,
            invoice_no="BL-2607-000501",
            issued_at=datetime(2026, 7, 11, 9, 0, tzinfo=UTC),
            total=Decimal("222.3000"),
            bill_type="rebill",
        )

        view = billing_reporting.invoices_dataset(
            start=WINDOW_START, end=WINDOW_END, per=50
        )
        numbers = [row.invoice_no for row in view["rows"]]
        assert view["total"] == 2
        assert numbers == [original.invoice_no, replacement.invoice_no]
        by_number = {row.invoice_no: row for row in view["rows"]}
        assert by_number["BL-2607-000500"].status == billing_models.INVOICE_CORRECTED
        assert by_number["BL-2607-000500"].amount == Decimal("247.8700")
        assert by_number["BL-2607-000501"].amount == Decimal("222.3000")


def test_a_draft_is_never_in_the_dataset(brazos, dana):
    """US-REP-006 TC-6 — a draft is replaceable, so a dataset that counted
    drafts would change its own history between two runs of one report."""
    from tests.test_us_bil_025_026_bills_read import a_draft

    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_billed_book(brazos, account, count=3)
        a_draft(brazos, account)
        view = billing_reporting.invoices_dataset(
            start=WINDOW_START, end=WINDOW_END, per=50
        )
        assert view["total"] == 3


# ═══════════════════════════════════════════════════════════════════════════
# THE SEVEN REFUSALS — and why a refusal beats a plausible report
# ═══════════════════════════════════════════════════════════════════════════
def test_every_invoices_definition_is_either_served_or_refused_by_name():
    """`reports/0003` seeds EIGHT definitions onto this dataset and only one of
    them is a report about bills. The other seven are listed with the source
    and the grain they actually draw, so a refusal sends the next reader to the
    right question instead of to a query that already exists."""
    seeded = {
        "bill_run_readiness",
        "billing_register",
        "bill_adjustments",
        "bill_print_file",
        "write_offs_and_late_fees",
        "statement",
        "my_bills_and_payments",
        "adjustment_register",
    }
    refused = set(queries.INVOICES_DEFINITIONS_NOT_SERVED)
    assert refused < seeded
    assert seeded - refused == {"billing_register"}
    for key, reason in queries.INVOICES_DEFINITIONS_NOT_SERVED.items():
        # A refusal with no reason is a 501 wearing a message key.
        assert len(reason) > 80, key
        assert "invoices dataset" in reason, key


@pytest.mark.parametrize(
    "key",
    sorted(
        {
            "bill_run_readiness",
            "bill_adjustments",
            "bill_print_file",
            "write_offs_and_late_fees",
            "statement",
            "my_bills_and_payments",
            "adjustment_register",
        }
    ),
)
def test_a_definition_this_dataset_cannot_serve_refuses_rather_than_renders(
    key, brazos, dana
):
    """⚠ **THE POINT OF THE WHOLE FILE.** Rendering a bill register under the
    title *Bill Print File* gives real rows, a footing total and an answer to a
    question nobody asked — and it is invisible, because nothing on the screen
    says which report you are looking at the data of."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_billed_book(brazos, account, count=3)
        with pytest.raises(queries.DatasetCannotServe) as raised:
            queries.invoices_dataset(
                {"from": "2026-07-01", "to": "2026-07-31"}, key=key
            )
        assert raised.value.key == key
        assert raised.value.reason


def test_the_refusal_is_a_different_one_from_having_no_query_at_all():
    """The two need opposite work: one waits for a dataset lane, the other for
    a ruling about which dataset a definition belongs on. A single refusal
    covering both sends the next reader to build a query that exists."""
    assert not issubclass(queries.DatasetCannotServe, runner.DatasetNotExecutable)
    assert issubclass(queries.DatasetCannotServe, NotImplementedError)


# ═══════════════════════════════════════════════════════════════════════════
# THE RUNNER REACHES THE DATASET, WHICH IS WHAT MAKES A DATASET WORTH BUILDING
# ═══════════════════════════════════════════════════════════════════════════
def test_the_runner_falls_back_to_the_dataset_query_when_a_key_has_no_viewer():
    """*"46 reports sit on 9 datasets"* — so a dataset landing turns on every
    definition built upon it, rather than one card at a time. Before this the
    lookup was by KEY alone and a dataset query had nowhere to be reached
    from."""
    # A key with its own viewer keeps it — moving a shipped, measured read onto
    # a new path is a behaviour change wearing a refactor's clothes.
    assert runner.queries_for("billing_register", "invoices") is queries.billing_register
    # A key with none reaches the dataset.
    reached = runner.queries_for("a_definition_with_no_viewer", "invoices")
    assert reached is not None
    # And a dataset with no query still answers None, so the caller can raise
    # `DatasetNotExecutable` naming which one is missing.
    #
    # ⚠ **THIS NAMED `journal_lines` AND WENT RED THE NEXT DAY (`DEF-REP-6896`,
    # fixed by lane REP-WIRE 2026-09-27).** It was an assertion with a CLOCK in
    # it: `journal_lines` had no query on 2026-09-26 and acquired one in
    # `72d259e89` on 2026-09-27, so the case then claimed a dataset was dark
    # that was registered, measured and serving four reports. It names
    # `notifications` instead — the one dataset this repository holds a built
    # query for and `datasets.BY_CODE` does not declare (`DEF-REP-6895`), so
    # the assertion is about a real absence again rather than a stale one.
    assert runner.queries_for("a_definition_with_no_viewer", "notifications") is None


def test_the_streaming_lookup_is_a_separate_door():
    """§8.2 p91 — *"the left path never fetches more than a page; the right
    path never holds one."* One lookup returning both is how an export reaches
    a paging function and inherits a page size."""
    assert runner.stream_for("billing_register", "invoices") is not None
    assert runner.stream_for("billing_register", "journal_lines") is None


def test_the_viewer_and_the_export_read_the_same_rows(brazos, dana):
    """`P0.5`'s discipline one layer down: a report rendered on screen and the
    same report exported produce the same rows. Proved against the WHOLE set
    rather than against a page, because the page is the thing that could
    differ."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_billed_book(brazos, account, count=9)
        params = {"from": "2026-07-01", "to": "2026-07-31"}
        on_screen = queries.invoices_dataset({**params, "per": "all"})["rows"]
        in_the_file = list(queries.invoices_dataset_rows(params))
        assert len(on_screen) == 9
        assert on_screen == in_the_file


# ── Lifecycle ─────────────────────────────────────────────
# packet: DS-INVOICES · 05-prototype/09 Reports Build Brief.pdf p49-p73 (the eight drawings), p83-p86 (§7.2 additivity), p90-p92 (§08 architecture) — all read as IMAGES per B14 rule 42
# screens: none — this lane writes a dataset query and touches no screen
# generated: 2026-09-26 by lane DS-INVOICES
# checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST, through pytest — every case failed with `AttributeError: module 'apps.billing.reporting' has no attribute 'invoices_dataset'` / `module 'apps.reports.queries' has no attribute 'DatasetCannotServe'` before the query existed
# exceptions: (1) this file decides CONTRACT, never cost — the PostgreSQL measurement is 10-scripts/ds_invoices_cost.py (hard-won law 14: the suite is in-memory SQLite and cannot see a LIMIT) · (2) the seven refusals are asserted as refusals and not as reports, deliberately
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
