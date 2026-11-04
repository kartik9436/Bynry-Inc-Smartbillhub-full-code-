# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 `P2.12` (the three read models accept limit, offset
#           and sort) · `P2.1` (paging in SQL) · `P2.2` (sort in SQL, with a
#           stable secondary term; the account ledger DECLINES sort) ·
#           `P2.3` (search against DECLARED columns) · `P2.4` (the row cap and
#           the pre-count are deleted).
# Rules:    `NFR-3` (universal server pagination) · `NFR-5` (no hard caps
#           anywhere) · `BR-SHL-011` (invalid values fall back or clamp, NEVER
#           error) · `BR-REP-024` (render the owner's figure or name what you
#           cannot answer — never 0) · CLAUDE.md hard rule 1 (tenant scoping) ·
#           hard rule 3 (a quantity never travels without its unit) ·
#           hard-won law 2's mirror (a control the server declines).
# Impacts:  apps/billing/reporting.py · apps/ledger/reporting.py ·
#           apps/reports/queries.py · apps/tenancy/exports.py + services.py
# ───────────────────────────────────────────────────────
"""THE READ PATH'S CONTRACT — the parts a fixture can decide, on any backend.

⚠ **THIS FILE IS NOT THE PERFORMANCE PROOF AND MUST NOT BE READ AS ONE.**
`config/settings/test.py` hardcodes in-memory SQLite, and on twenty rows a
`LIMIT` and a Python slice are the same two numbers. `P2.9` says so in the
brief: *"Postgres only. Seed 40,000 rows and assert the page-two query reads
50, not 40,000"* — that is
`10-scripts/cr142_p2_read_path_cost.py`, run on a real PostgreSQL 16 clone, and
its measured figures are quoted in the decision-log row.

**What THIS file decides, which a benchmark cannot:** that the page is the
right ROWS, that the tiles foot to the whole filtered set rather than to the
page, that a cumulative column survives being cut, that the declared
vocabularies and the served behaviour are the same thing, and that the two
deleted names stay deleted.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from apps.billing import reporting as billing_reporting
from apps.ledger import reporting as ledger_reporting
from apps.reports import catalog, queries
from apps.tenancy import exports as export_kernel

from tests.test_us_bil_025_026_bills_read import an_account, an_invoice
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

UTC = timezone.utc
WINDOW_START = date(2026, 7, 1)
WINDOW_END = date(2026, 7, 31)


def a_register(tenant, account, *, count: int, amount_of=None) -> list:
    """`count` ISSUED bills in July, numbered in order, one per day.

    Amounts ASCEND unless `amount_of` says otherwise, so a sort by amount and a
    sort by number are DIFFERENT orders — a fixture where every bill costs the
    same cannot tell a working sort from an ignored one.
    """
    bills = []
    for index in range(count):
        bills.append(
            an_invoice(
                tenant,
                account,
                invoice_no=f"BL-2607-{index + 1:06d}",
                issued_at=datetime(2026, 7, 1, 9, 0, tzinfo=UTC) + timedelta(days=index),
                due_date=date(2026, 8, 25),
                subtotal=Decimal("10.00"),
                tax_total=Decimal("0.00"),
                total=(
                    Decimal(f"{10 + index}.0000")
                    if amount_of is None
                    else amount_of(index)
                ),
            )
        )
    return bills


# ═══════════════════════════════════════════════════════════════════════════
# `P2.12` · `P2.1` — the register pages, and the tiles do not page with it
# ═══════════════════════════════════════════════════════════════════════════
def test_p2_1__the_register_serves_a_page_and_says_which_one(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_register(brazos, account, count=12)

        page_one = billing_reporting.billing_register(
            start=WINDOW_START, end=WINDOW_END, page=1, per=5
        )
        page_three = billing_reporting.billing_register(
            start=WINDOW_START, end=WINDOW_END, page=3, per=5
        )

        assert [row.invoice_no for row in page_one["rows"]] == [
            "BL-2607-000001",
            "BL-2607-000002",
            "BL-2607-000003",
            "BL-2607-000004",
            "BL-2607-000005",
        ]
        # The LAST page is short and is still a page — 12 rows, 5 to a page.
        assert [row.invoice_no for row in page_three["rows"]] == [
            "BL-2607-000011",
            "BL-2607-000012",
        ]
        assert page_three["page"] == 3 and page_three["per"] == 5
        assert page_one["total"] == page_three["total"] == 12


def test_p2_1__the_kpis_are_the_whole_filtered_set_and_never_the_page(brazos, dana):
    """⚠ **THE ARGUMENT `P2.12` HAD TO ANSWER BEFORE IT COULD BE BUILT.**

    CLAUDE.md records the premise that kept `/outstandings` unpaginated — that
    cutting a page would make the tiles describe a page instead of the debt —
    and records it as WRONG: *"the tiles are a SQL aggregate over the whole
    filtered set whether a page is cut or not"*. This is that sentence as a
    case: bills 1..12 total 186.00, and every page says so.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_register(brazos, account, count=12)
        whole = sum(Decimal(f"{10 + index}.0000") for index in range(12))

        for page in (1, 2, 3):
            view = billing_reporting.billing_register(
                start=WINDOW_START, end=WINDOW_END, page=page, per=5
            )
            assert view["kpis"]["bills"] == 12, page
            assert view["kpis"]["billed"] == whole, page
            assert view["kpis"]["average_bill"] == whole / 12, page


def test_p2_1__per_none_is_the_whole_set_so_every_caller_that_predates_this_is_unchanged(
    brazos, dana
):
    """`per=None` is the DEFAULT and it is the export's door, not a cap lifted.

    A read-signature change to another module's published model must leave
    every existing caller byte-identical — including the order, which is why
    the default sort is `invoice_no` ASC and not "newest first".
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_register(brazos, account, count=12)

        view = billing_reporting.billing_register(start=WINDOW_START, end=WINDOW_END)
        assert len(view["rows"]) == 12
        assert view["per"] is None and view["page"] == 1
        assert [row.invoice_no for row in view["rows"]] == [
            f"BL-2607-{index + 1:06d}" for index in range(12)
        ]


def test_p2_1__a_page_beyond_the_end_clamps_and_says_which_page_it_gave(brazos, dana):
    """`BR-SHL-011` — invalid values fall back or clamp, NEVER error. A saved
    link to page 9,999 of a three-page register opens on the last page."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_register(brazos, account, count=12)

        view = billing_reporting.billing_register(
            start=WINDOW_START, end=WINDOW_END, page=9999, per=5
        )
        assert view["page"] == 3
        assert [row.invoice_no for row in view["rows"]] == [
            "BL-2607-000011",
            "BL-2607-000012",
        ]


# ═══════════════════════════════════════════════════════════════════════════
# `P2.2` — sort, in SQL, with a stable secondary term
# ═══════════════════════════════════════════════════════════════════════════
def test_p2_2__each_declared_sort_orders_the_page_and_both_directions_differ(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_register(brazos, account, count=12)

        for sort in billing_reporting.REGISTER_SORTS:
            ascending = billing_reporting.billing_register(
                start=WINDOW_START, end=WINDOW_END, per=5, sort=sort, direction="asc"
            )
            descending = billing_reporting.billing_register(
                start=WINDOW_START, end=WINDOW_END, per=5, sort=sort, direction="desc"
            )
            first_asc = [row.invoice_id for row in ascending["rows"]]
            first_desc = [row.invoice_id for row in descending["rows"]]
            assert len(first_asc) == len(first_desc) == 5, sort
            if sort == "account_no":
                # Every bill here is on ONE account, so this sort is a TIE from
                # end to end — which is exactly what the secondary term is for
                # and is asserted as stability below rather than as a reversal.
                continue
            assert first_asc != first_desc, f"{sort} ordered the same both ways"


def test_p2_2__a_total_tie_still_pages_without_showing_a_row_twice(brazos, dana):
    """⚠ **THE SECOND TERM IS WHY A PAGE BOUNDARY IS SAFE.** Twelve bills at
    the SAME amount is a total tie on `amount`; without `id` as a second term
    PostgreSQL may return them in any order per statement, so a row can appear
    on page 1 and again on page 2 — and **a row a clerk sees twice is a row
    they never see.**"""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_register(
            brazos, account, count=12, amount_of=lambda index: Decimal("42.0000")
        )

        seen: list[str] = []
        for page in (1, 2, 3):
            view = billing_reporting.billing_register(
                start=WINDOW_START, end=WINDOW_END, page=page, per=5, sort="amount"
            )
            seen.extend(row.invoice_id for row in view["rows"])
        assert len(seen) == 12
        assert len(set(seen)) == 12, "a bill was served on two different pages"


def test_p2_2__an_unknown_sort_falls_back_and_does_not_error(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_register(brazos, account, count=4)

        view = billing_reporting.billing_register(
            start=WINDOW_START, end=WINDOW_END, sort="favourite_colour"
        )
        assert [row.invoice_no for row in view["rows"]] == [
            f"BL-2607-{index + 1:06d}" for index in range(4)
        ]


def test_p2_2__the_screens_sort_vocabulary_is_the_read_models_own(brazos, dana):
    """`BR-REP-006`, and hard-won law 2's mirror: a caret the server silently
    ignores is a live control over a dead one. The reports module reads
    billing's tuple through the seam rather than keeping a copy."""
    assert queries._register_sorts() == billing_reporting.REGISTER_SORTS
    assert queries._register_default_sort() == billing_reporting.REGISTER_DEFAULT_SORT
    assert "customer_name" not in billing_reporting.REGISTER_SORTS


def test_p2_2__the_account_ledger_declines_sort_and_says_so(brazos, dana):
    """⚠ **SORT IS PER-DATASET, NOT UNIVERSAL.** A running balance is defined
    BY the row order, so ordering it by amount does not re-sort the column, it
    destroys it. The dataset answers an EMPTY TUPLE — a fact a screen can read
    and draw no carets from — rather than omitting the key."""
    assert ledger_reporting.ACCOUNT_LEDGER_SORTS == ()
    import inspect

    parameters = inspect.signature(ledger_reporting.account_ledger).parameters
    assert "page" in parameters and "per" in parameters
    assert "sort" not in parameters, (
        "the account ledger grew a sort parameter. Sorting a running balance by "
        "amount prints a column of wrong money — see P2.2."
    )


# ═══════════════════════════════════════════════════════════════════════════
# `P2.3` — search, against DECLARED columns, on the server
# ═══════════════════════════════════════════════════════════════════════════
def test_p2_3__q_narrows_the_register_on_the_server_and_the_tiles_follow(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_register(brazos, account, count=12)

        view = billing_reporting.billing_register(
            start=WINDOW_START, end=WINDOW_END, search="000007"
        )
        assert [row.invoice_no for row in view["rows"]] == ["BL-2607-000007"]
        # The tiles are the FILTERED set — one bill, not twelve. A search that
        # only trimmed the rows would leave a header describing a report the
        # clerk is not looking at.
        assert view["kpis"]["bills"] == 1
        assert view["total"] == 1


def test_p2_3__q_reaches_the_customers_name_through_their_own_published_read(
    brazos, dana
):
    """B1/BR-TEN-013: billing does not join customers' tables. The name leg is
    customers' own `account_ids_matching_debtor_search`, resolved by name."""
    with tenant_ctx(brazos):
        hers = an_account(brazos, dana, account_no="A-77001", contact_name="Okonkwo, Ada")
        his = an_account(
            brazos,
            dana,
            account_no="A-77002",
            contact_name="Petrov, Dmitri",
            label="Unit B",
        )
        an_invoice(
            brazos,
            hers,
            invoice_no="BL-2607-000100",
            issued_at=datetime(2026, 7, 4, 9, 0, tzinfo=UTC),
            total=Decimal("10.0000"),
        )
        an_invoice(
            brazos,
            his,
            invoice_no="BL-2607-000200",
            issued_at=datetime(2026, 7, 5, 9, 0, tzinfo=UTC),
            total=Decimal("20.0000"),
        )

        view = billing_reporting.billing_register(
            start=WINDOW_START, end=WINDOW_END, search="Okonkwo"
        )
        assert [row.invoice_no for row in view["rows"]] == ["BL-2607-000100"]


def test_p2_3__the_searchable_columns_are_declared(brazos, dana):
    assert billing_reporting.REGISTER_SEARCH_COLUMNS == (
        "invoice_no",
        "account_no",
        "customer_name",
    )


def test_p2_3__an_empty_q_is_not_a_filter(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(brazos, dana)
        a_register(brazos, account, count=4)
        for blank in (None, "", "   "):
            view = billing_reporting.billing_register(
                start=WINDOW_START, end=WINDOW_END, search=blank
            )
            assert len(view["rows"]) == 4, blank


# ═══════════════════════════════════════════════════════════════════════════
# `P2.12` — the account ledger pages, and the running balance survives it
# ═══════════════════════════════════════════════════════════════════════════
def _ledger_rows(account_id, start, end, **kwargs):
    return ledger_reporting.account_ledger(account_id, start=start, end=end, **kwargs)


def test_p2_12__the_account_ledgers_running_balance_survives_the_page(brazos, dana):
    """⚠ **THE ONE THING PAGING A CUMULATIVE COLUMN CAN GET WRONG.**

    `r_n = r_{n-1} + charge_n − payment_n` (US-LED-009 §7, CONFIRMED). Page two
    cannot start at the window's opening balance — it starts where page one
    left off. So the first row of page two must carry the SAME running balance
    it carries in an unpaged read, and the window's totals must not move at all.

    ACC-1042's July is US-LED-009 TC-1's own month: opening **45.00** → bill
    **+247.87** → running **292.87** → payment **−292.87** → running **0.00**.
    Cut at one row a page, page two opens at **292.87**, not at 45.00 — and
    45.00 is exactly what a naive page would print.
    """
    from tests.ledger_le_fixtures import (  # noqa: PLC0415
        JULY_END,
        JULY_START,
        make_accounts,
        post_le1_month,
    )

    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        post_le1_month(brazos, accounts)
        account_id = accounts["ACC-1042"].id

        whole = _ledger_rows(account_id, JULY_START, JULY_END)
        assert len(whole["rows"]) == 2, "TC-1's month is two AR rows; the fixture moved"

        page_two = _ledger_rows(account_id, JULY_START, JULY_END, page=2, per=1)
        assert len(page_two["rows"]) == 1
        assert page_two["rows"][0].running_balance == whole["rows"][1].running_balance
        # Where the page OPENS — 292.87, the first row's closing — and NOT the
        # window's 45.00, which is what a page that forgot to carry forward
        # would print.
        assert page_two["page_opening_balance"] == whole["rows"][0].running_balance
        assert page_two["page_opening_balance"] != whole["opening_balance"]
        # The WINDOW's totals, never the page's.
        assert page_two["totals"] == whole["totals"]
        assert page_two["total"] == 2 and page_two["page"] == 2 and page_two["per"] == 1


def test_p2_12__page_one_opens_where_the_unpaged_report_does(brazos, dana):
    from tests.ledger_le_fixtures import (  # noqa: PLC0415
        JULY_END,
        JULY_START,
        make_accounts,
        post_le1_month,
    )

    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        post_le1_month(brazos, accounts)
        account_id = accounts["ACC-1042"].id

        whole = _ledger_rows(account_id, JULY_START, JULY_END)
        page_one = _ledger_rows(account_id, JULY_START, JULY_END, page=1, per=1)
        assert page_one["page_opening_balance"] == whole["opening_balance"]
        assert page_one["rows"][0].running_balance == whole["rows"][0].running_balance
        # `per=None` — the default — is the whole report and the old behaviour.
        assert whole["per"] is None and whole["page"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# `P2.4` — the cap and the pre-count are DELETED, and stay deleted
# ═══════════════════════════════════════════════════════════════════════════
def test_p2_4__the_export_kernel_carries_no_row_cap_and_no_pre_count():
    """⚠ **A NAMED ABSENCE CAN FAIL FOR EXACTLY ONE REASON: SOMEBODY PUT IT
    BACK.** That is why this asserts the names are gone rather than asserting
    some large number is allowed — `test_us_rep_003_downloads.py` records what
    a pinned literal cost (`DEF-REP-6674`, red for five days) and what
    loosening it to *"an int, and positive"* cost after that (a check that
    cannot fail for the right reason).

    `NFR-5`: no hard cap anywhere, **including one a tenant can raise on a
    Settings screen**. Killeen at 57,066 accounts × 14 cycles is ~685,000 bill
    rows a year; the old ceiling was 100,000.
    """
    assert not hasattr(export_kernel, "EXPORT_ROW_CAP")
    assert not hasattr(export_kernel, "selection_count")
    # The streaming writer is what made the cap unnecessary, and it is still
    # the thing the file is written from.
    assert hasattr(export_kernel, "selection_iter")


def test_p2_4__the_report_export_takes_the_WHOLE_filtered_set_not_a_page():
    """⚠ **THE TRAP `P2.12` CREATED AND THIS CLOSES.** The moment a report
    pages, an export resource that calls the viewer without `whole=True`
    writes the SCREEN's fifty rows into a file that looks perfectly valid.
    Every paged report's resource must ask for the whole set."""
    from apps.reports import exports as report_exports

    paged = {catalog.KEY_AR_AGING, catalog.KEY_BILLING_REGISTER}
    for resource in report_exports.RESOURCES:
        if resource.name not in paged:
            continue
        rows = resource.select.__code__.co_consts
        assert True in rows, (
            f"{resource.name} exports without `whole=True`, so its file is one "
            "page of the report — see P2.4 / P2.12."
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 §4 P2.1 · P2.2 · P2.3 · P2.4 · P2.12 (05-prototype/09 Reports Build Brief.pdf p010-p011 · p085 · p087)
# screens: S46 (the viewer these read models serve)
# generated: 2026-09-26 by lane REP-P2A
# gates: RED PROVED FIRST — every case in this file was run against the pre-change read models and named its own failure; the P2.4 pair failed on `hasattr(...) is True`, the paging cases on `TypeError: billing_register() got an unexpected keyword argument 'page'`.
# exceptions: this file decides CORRECTNESS on SQLite and decides NOTHING about cost — P2.9's Postgres-only proof is `10-scripts/cr142_p2_read_path_cost.py` and its figures are in the decision log · DEF-REP-6816 (payments_by_method is still unbounded) is filed, not fixed here
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
