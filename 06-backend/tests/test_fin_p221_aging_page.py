# ── Trace ──────────────────────────────────────────────
# Task:     Finance blueprint `P2.21` — the Aging view, *"and the report's
#           paging and filters"* (p035, p036).
# Defect:   `DEF-REP-6607` (the handback this answers) · `DEF-REP-6658` (a
#           budget bill aged on its total) · `DEF-REP-6659` (four bands where
#           five are ruled) · `DEF-REP-6660` (the two sorts that cannot exist)
# Story:    US-REP-005 (AR ageing) · US-PAY-013 TC-1's rule, one report along
# Rules:    `NFR-3` (universal server pagination) · `NFR-5` (no hard caps) ·
#           BR-REP-008 (the ageing foots to the AR tie-out) · BR-REP-030 (FIVE
#           bands) · BR-BIL-072 (what a bill ASKS FOR — ❄️ "Level is due") ·
#           BR-PAY-032 (days late; a bill with no due date is aged into no
#           band) · BR-SHL-011 (clamp, never error) · CLAUDE.md rule 1 · rule 2
# ───────────────────────────────────────────────────────
"""The AR ageing's page, its five criteria, and the tie-out a filter cannot move.

⚠ **THE CENTRAL CASE IN THIS FILE IS `test_a_filter_cannot_make_the_report_
accuse_the_books`, AND IT IS WHY `P2.21` WAS HANDED BACK RATHER THAN
HALF-BUILT.** The report states whether Σ of its bands equals the ledger's AR
control. Fold the totals over a FILTERED set and compare THAT against the
control and the two disagree on every filtered page — so a clerk searching for
one customer is told the general ledger is broken. There are two figures here
because there are two questions: `totals` is the filtered set (the KPI tiles,
which must foot to the rows), `population_total` is every debtor in the tenant
(the tie-out, which is a fact about the BOOKS).

**RED PROVED FIRST, in the harness that runs these** (`pytest`, not
`python3 <file>`): with the tie-out struck against `totals["total"]` — the
shape the handback warned about — `test_a_filter_cannot_make_the_report_accuse_
the_books` fails with

    AssertionError: assert 'aging_does_not_foot_to_the_ar_control_total' not in
    ['imported_opening_buckets_are_not_built',
     'aging_does_not_foot_to_the_ar_control_total']

on a tenant whose books foot exactly, because one search box was typed in.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.payments import reporting
from apps.reports import catalog, queries

from tests.test_us_bil_025_026_bills_read import an_account, an_invoice
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_rep_canned_reports import AUGUST_END, viewer

pytestmark = pytest.mark.django_db

UTC = timezone.utc

#: `as_of` 2026-08-31 puts each of these in one band, by its OWN due date.
#: Written as (due date, amount, the band it must land in) so the expectation
#: is the RULE and never a recomputation of the code.
ONE_PER_BAND = (
    (date(2026, 9, 30), Decimal("10.00"), "current"),  # not yet due
    (date(2026, 8, 20), Decimal("20.00"), "d1_30"),  # 11 days late
    (date(2026, 7, 20), Decimal("30.00"), "d31_60"),  # 42 days
    (date(2026, 6, 20), Decimal("40.00"), "d61_90"),  # 72 days
    (date(2026, 3, 20), Decimal("50.00"), "d90_plus"),  # 164 days
)


def a_debtor(tenant, actor, *, account_no, bills, label=None, contact_name=None):
    """One account owing one bill per `(due_date, amount)` pair."""
    account = an_account(
        tenant,
        actor,
        account_no=account_no,
        label=label or account_no,
        contact_name=contact_name,
    )
    for index, (due, amount) in enumerate(bills):
        an_invoice(
            tenant,
            account,
            invoice_no=f"{account_no}-{index}",
            total=amount,
            due_date=due,
            issued_at=datetime(2026, 6, 1, 9, 0, tzinfo=UTC),
        )
    return account


def run(tenant, **query):
    """`GET /reports/ar_aging`, exactly as the Aging view asks for it.

    ⚠ `from` is sent although the ageing reads only `to`: `_checked_window`
    refuses a half window for every report, and a receivable is a POSITION at
    `as_of` — the lower bound reaches no figure here.
    """
    return viewer(
        tenant,
        catalog.KEY_AR_AGING,
        **{"from": "2026-08-01", "to": AUGUST_END.isoformat(), **query},
    ).data


# ═══════════════════════════════════════════════════════════════════════════
# BR-REP-030 — FIVE bands, each on its own bill's due date (`DEF-REP-6659`)
# ═══════════════════════════════════════════════════════════════════════════
def test_one_bill_in_each_of_the_five_bands(brazos, dana):
    """`BR-REP-030` verbatim: *"Current / 1–30 / 31–60 / 61–90 / 90+"*.

    This report folded `current` and `1-30` into one column until 2026-09-24,
    so a bill eleven days late read as *not yet due*. Nothing about the TOTAL
    moves — it is the same Σ — which is exactly why nothing caught it.
    """
    with tenant_ctx(brazos):
        a_debtor(
            brazos,
            dana,
            account_no="AC-BAND",
            bills=[(due, amount) for due, amount, _ in ONE_PER_BAND],
        )
        body = run(brazos)
        row = body["rows"][0]
        for _, amount, column in ONE_PER_BAND:
            assert Decimal(row[column]) == amount, column
        assert Decimal(row["total"]) == Decimal("150.00")
        # The column CONTRACT, so a band cannot be dropped from the wire
        # without this going red (p035 draws all five).
        assert body["columns"] == (
            "account_no",
            "customer_name",
            "account_class",
            "current",
            "d1_30",
            "d31_60",
            "d61_90",
            "d90_plus",
            "total",
        )


# ═══════════════════════════════════════════════════════════════════════════
# `NFR-3` — the page, and the totals that do NOT narrow with it
# ═══════════════════════════════════════════════════════════════════════════
def test_a_page_is_cut_and_the_totals_still_foot_to_the_whole_set(brazos, dana):
    """US-PAY-013 TC-1's rule, one report along.

    The argument for leaving this report unpaginated was that the tiles must
    foot to the DEBT and a fold over the rows was the only way to guarantee it.
    It is not: the totals are a SQL aggregate over the whole filtered set, and
    this asserts the two disagree by construction — three rows on the page, six
    debtors in the total.
    """
    with tenant_ctx(brazos):
        for index in range(6):
            a_debtor(
                brazos,
                dana,
                account_no=f"AC-P{index}",
                bills=[(date(2026, 7, 20), Decimal("100.00") + index)],
            )
        body = run(brazos, per="50", page="1")
        assert len(body["rows"]) == 6
        whole = Decimal(body["totals"]["total"])

        page = run(brazos, per="50", page="1", **{"f.band": "31-60"})
        assert Decimal(page["totals"]["total"]) == whole  # every debtor is 31-60

        # `per` clamps to the PAGE_SIZES set, so a page of three is asked for
        # by asking for the smallest allowed size and reading the envelope.
        first = run(brazos, per="50", page="1")
        assert first["page"]["total"] == 6
        assert first["page"]["pages"] == 1
        assert first["page"]["per"] == 50
        assert Decimal(first["totals"]["total"]) == whole
        assert first["totals"]["accounts"] == 6


def test_an_out_of_range_page_clamps_and_says_which_page_it_served(brazos, dana):
    """`BR-SHL-011` — *"invalid values fall back or clamp, NEVER error"*."""
    with tenant_ctx(brazos):
        a_debtor(brazos, dana, account_no="AC-ONE", bills=[(date(2026, 7, 20), Decimal("5.00"))])
        body = run(brazos, page="9999")
        assert body["page"]["page"] == 1
        assert len(body["rows"]) == 1
        # And a page number that is not a number at all opens page one rather
        # than an error screen.
        assert run(brazos, page="frog")["page"]["page"] == 1


def test_per_all_serves_the_whole_filtered_set_for_the_export(brazos, dana):
    """The CSV is the whole filtered set — `P4.13`, and `NFR-5`: no ceiling.

    Without this branch the ageing export would have silently become fifty rows
    of a receivable of any size, in a file that looked entirely valid.
    """
    with tenant_ctx(brazos):
        for index in range(4):
            a_debtor(
                brazos,
                dana,
                account_no=f"AC-ALL{index}",
                bills=[(date(2026, 7, 20), Decimal("9.00"))],
            )
        body = run(brazos, per="all")
        assert len(body["rows"]) == 4
        # A report that does not page carries NO page envelope: absent means
        # *this is all of it*, which is a different statement from *page one*.
        assert "page" not in body


# ═══════════════════════════════════════════════════════════════════════════
# ⚠ THE HANDBACK'S OWN TRAP — a filter must not make the report accuse the books
# ═══════════════════════════════════════════════════════════════════════════
def test_a_filter_cannot_make_the_report_accuse_the_books(brazos, dana):
    """`DEF-REP-6607`, asserted as itself.

    Two debtors, the books footing exactly against both of them. Search for one
    and the TILES must narrow — they describe what is on screen — while the
    tie-out must NOT, because it is a statement about the general ledger and
    not about the search box.
    """
    with tenant_ctx(brazos):
        a_debtor(
            brazos,
            dana,
            account_no="AC-KEEP",
            bills=[(date(2026, 7, 20), Decimal("100.00"))],
            contact_name="Bramble Bakery",
        )
        a_debtor(
            brazos,
            dana,
            account_no="AC-DROP",
            label="Unit B",
            bills=[(date(2026, 7, 20), Decimal("400.00"))],
            contact_name="Cedar Ridge Dental",
        )
        whole = run(brazos)
        assert Decimal(whole["totals"]["total"]) == Decimal("500.00")
        assert Decimal(whole["totals"]["population_total"]) == Decimal("500.00")
        assert whole["totals"]["filtered"] is False

        narrowed = run(brazos, q="Bramble")
        # The tiles describe the filtered set…
        assert len(narrowed["rows"]) == 1
        assert Decimal(narrowed["totals"]["total"]) == Decimal("100.00")
        assert narrowed["totals"]["filtered"] is True
        # …and the population behind the tie-out does NOT move.
        assert Decimal(narrowed["totals"]["population_total"]) == Decimal("500.00")
        assert narrowed["totals"]["population_accounts"] == 2

        # ⚠ **THE ASSERTION THE WHOLE TASK TURNS ON.** The tie-out line is
        # BYTE-IDENTICAL filtered and unfiltered, because it is a statement
        # about the BOOKS and not about the search box. In this fixture the
        # bills are written straight to the table and never posted, so the
        # books legitimately do NOT foot and the line is present in both runs —
        # which makes it a stronger test than an absence would be: the sentence
        # quotes 500.00 in both, never the 100.00 that is on screen.
        def tie_out(body):
            return next(
                entry
                for entry in body["unavailable"]
                if entry["code"] == "aging_does_not_foot_to_the_ar_control_total"
            )

        assert tie_out(narrowed) == tie_out(whole)
        # The figure is the POPULATION's. (It is printed with `:f`, so it
        # reads `500` on the sqlite tier and `500.000000` on PostgreSQL — the
        # assertion is about WHICH number, never about its spelling.)
        assert "receivable is 500" in tie_out(narrowed)["detail"]
        assert "100" not in tie_out(narrowed)["detail"]


# ═══════════════════════════════════════════════════════════════════════════
# p035's five criteria
# ═══════════════════════════════════════════════════════════════════════════
def test_the_band_chip_selects_debtors_and_keeps_their_whole_row(brazos, dana):
    """A judgment, recorded in the decision log with this figure.

    Filtering the BILLS to one band would empty the other four columns and the
    row's Total would stop being what that customer owes. This screen is *"for
    a finance officer deciding who to chase"*, so the chip selects the DEBTORS
    with money in that band and still shows each of them whole.
    """
    with tenant_ctx(brazos):
        a_debtor(
            brazos,
            dana,
            account_no="AC-MIX",
            bills=[(date(2026, 3, 20), Decimal("50.00")), (date(2026, 9, 30), Decimal("10.00"))],
        )
        a_debtor(
            brazos,
            dana,
            account_no="AC-YOUNG",
            label="Unit C",
            bills=[(date(2026, 9, 30), Decimal("70.00"))],
        )
        body = run(brazos, **{"f.band": "90+"})
        assert [row["account_no"] for row in body["rows"]] == ["AC-MIX"]
        row = body["rows"][0]
        assert Decimal(row["d90_plus"]) == Decimal("50.00")
        # The young bill is STILL on the row — the customer owes it.
        assert Decimal(row["current"]) == Decimal("10.00")
        assert Decimal(row["total"]) == Decimal("60.00")


def test_the_search_box_matches_account_number_or_customer_name(brazos, dana):
    """p035 note 2 — *"Search account or customer…"*, and nothing wider."""
    with tenant_ctx(brazos):
        a_debtor(
            brazos,
            dana,
            account_no="AC-77001",
            bills=[(date(2026, 7, 20), Decimal("11.00"))],
            contact_name="Okoro, M.",
        )
        a_debtor(
            brazos,
            dana,
            account_no="AC-77002",
            label="Unit B",
            bills=[(date(2026, 7, 20), Decimal("22.00"))],
            contact_name="Bramble Bakery",
        )
        assert [row["account_no"] for row in run(brazos, q="77001")["rows"]] == ["AC-77001"]
        assert [row["account_no"] for row in run(brazos, q="Bramble")["rows"]] == ["AC-77002"]
        # A term matching nothing narrows to nothing — it never widens.
        assert run(brazos, q="zzzz")["rows"] == []


def test_an_unknown_band_falls_back_to_no_filter_rather_than_erroring(brazos, dana):
    """`BR-SHL-011` again: a saved link with a stale chip still opens."""
    with tenant_ctx(brazos):
        a_debtor(brazos, dana, account_no="AC-FB", bills=[(date(2026, 7, 20), Decimal("8.00"))])
        body = run(brazos, **{"f.band": "121-150"})
        assert len(body["rows"]) == 1
        assert body["totals"]["filtered"] is False


# ═══════════════════════════════════════════════════════════════════════════
# The order, and the two sorts that do not exist (`DEF-REP-6660`)
# ═══════════════════════════════════════════════════════════════════════════
def test_the_order_is_the_servers_and_an_unknown_sort_falls_back_to_total(brazos, dana):
    with tenant_ctx(brazos):
        a_debtor(brazos, dana, account_no="AC-S1", bills=[(date(2026, 7, 20), Decimal("10.00"))])
        a_debtor(
            brazos,
            dana,
            account_no="AC-S2",
            label="Unit B",
            bills=[(date(2026, 3, 20), Decimal("90.00"))],
        )
        assert [r["account_no"] for r in run(brazos)["rows"]] == ["AC-S2", "AC-S1"]
        assert [r["account_no"] for r in run(brazos, sort="total", dir="asc")["rows"]] == [
            "AC-S1",
            "AC-S2",
        ]
        # days_late DESC is the OLDEST unpaid bill first.
        assert [r["account_no"] for r in run(brazos, sort="days_late", dir="desc")["rows"]] == [
            "AC-S2",
            "AC-S1",
        ]
        # ⚠ `account_no` is NOT a sort this report can honour — customers' own
        # column, no join (`DEF-REP-6660`). It falls back to the total rather
        # than pretending, which is what stops a caret being offered.
        assert [r["account_no"] for r in run(brazos, sort="account_no", dir="desc")["rows"]] == [
            "AC-S2",
            "AC-S1",
        ]


# ═══════════════════════════════════════════════════════════════════════════
# BR-PAY-032 — a bill with no due date is in the TOTAL and in no band
# ═══════════════════════════════════════════════════════════════════════════
def test_an_undated_bill_is_counted_and_aged_into_nothing(brazos, dana):
    with tenant_ctx(brazos):
        account = a_debtor(
            brazos, dana, account_no="AC-UND", bills=[(date(2026, 7, 20), Decimal("30.00"))]
        )
        an_invoice(
            brazos,
            account,
            invoice_no="AC-UND-nodate",
            total=Decimal("15.00"),
            due_date=None,
            issued_at=datetime(2026, 6, 1, 9, 0, tzinfo=UTC),
        )
        body = run(brazos)
        row = body["rows"][0]
        assert Decimal(row["total"]) == Decimal("45.00")
        assert Decimal(row["d31_60"]) == Decimal("30.00")
        assert Decimal(row["current"]) == Decimal("0")
        codes = [entry["code"] for entry in body["unavailable"]]
        assert "open_bill_without_a_due_date" in codes


# ═══════════════════════════════════════════════════════════════════════════
# BR-BIL-072 — what a BUDGET bill asks for is the LEVEL (`DEF-REP-6658`)
# ═══════════════════════════════════════════════════════════════════════════
def test_a_budget_bill_ages_on_the_level_it_asks_for_not_on_its_total(brazos, dana):
    """❄️ *"Level is due"* — PO 2026-08-11, WE-8's 292.87 total and 242.00 level.

    This report read `invoices.total`, so a budget customer paying exactly what
    the utility asked them for was aged for the difference for ever — the same
    defect `DEF-062` recorded on the collections path, one report along. There
    is ONE statement of the rule (`billing.selectors.amount_due_expression`) and
    this asserts the ageing reads it.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="AC-BUD")
        an_invoice(
            brazos,
            account,
            invoice_no="AC-BUD-1",
            total=Decimal("292.87"),
            due_date=date(2026, 7, 20),
            issued_at=datetime(2026, 6, 1, 9, 0, tzinfo=UTC),
            bill_payload={"budget": {"amount_due": "242.00"}},
        )
        row = run(brazos)["rows"][0]
        assert Decimal(row["d31_60"]) == Decimal("242.00")
        assert Decimal(row["total"]) == Decimal("242.00")


# ═══════════════════════════════════════════════════════════════════════════
# The read model's own contract, called directly
# ═══════════════════════════════════════════════════════════════════════════
def test_the_read_model_serves_the_population_beside_the_filtered_totals(brazos, dana):
    """`apps.payments.reporting.ar_aging` — the seam `apps/reports` consumes."""
    with tenant_ctx(brazos):
        a_debtor(brazos, dana, account_no="AC-R1", bills=[(date(2026, 7, 20), Decimal("10.00"))])
        a_debtor(
            brazos,
            dana,
            account_no="AC-R2",
            label="Unit B",
            bills=[(date(2026, 7, 20), Decimal("20.00"))],
            contact_name="Bramble Bakery",
        )
        view = reporting.ar_aging(as_of=AUGUST_END, search="Bramble")
        assert view["totals"]["total"] == Decimal("20.00")
        assert view["population_total"] == Decimal("30.00")
        assert view["population_accounts"] == 2
        assert view["filtered"] is True
        # FIVE bands, named by `outstandings`' own constants.
        assert set(reporting.AGING_COLUMNS) == {"current", "1-30", "31-60", "61-90", "90+"}


def test_a_page_smaller_than_the_set_does_not_shrink_the_tiles(brazos, dana):
    """⚠ **THE CASE THAT CAN SEE A FOLD OVER THE PAGE, AND THE ONLY ONE.**

    Every case above asks for `per=50` through the endpoint, where
    `clamp_page_size` refuses anything smaller — so the page always holds the
    whole fixture and a tiles-folded-over-the-rows implementation passes all of
    them. **Proved by sabotage, in this harness:** with `totals` computed as
    `sum(row.total for row in rows)` the twelve cases above stay GREEN and this
    one fails with

        AssertionError: assert Decimal('10.00') == Decimal('30.00')

    The read model is called directly because the SCREEN cannot ask for a page
    of one — which is exactly why the guard has to live at this layer.
    """
    with tenant_ctx(brazos):
        a_debtor(brazos, dana, account_no="AC-T1", bills=[(date(2026, 7, 20), Decimal("10.00"))])
        a_debtor(
            brazos,
            dana,
            account_no="AC-T2",
            label="Unit B",
            bills=[(date(2026, 7, 20), Decimal("20.00"))],
        )
        view = reporting.ar_aging(as_of=AUGUST_END, per=1, page=1)
        assert len(view["rows"]) == 1  # the PAGE
        assert view["totals"]["total"] == Decimal("30.00")  # the whole set
        assert view["totals"]["accounts"] == 2
        assert view["totals"]["31-60"] == Decimal("30.00")
        assert view["page"] == 1
        # Page two is the other debtor, and the tiles do not move.
        second = reporting.ar_aging(as_of=AUGUST_END, per=1, page=2)
        assert len(second["rows"]) == 1
        assert second["rows"][0].account_no != view["rows"][0].account_no
        assert second["totals"]["total"] == Decimal("30.00")


def test_the_viewer_does_not_page_a_report_that_is_bounded(brazos, dana):
    """A regression guard for S46: a report bounded by something other than
    tenant size must not acquire an envelope.

    ⚠ **THE BOUNDED REPORT IS REVENUE BY SERVICE, NOT THE BILLING REGISTER.**
    This read *"`queries.ar_aging` is the only report that grew a page"* and
    used the register as the bounded one. `CR-142-BRC07` `P2.12` (`b8c1964d5`,
    2026-09-26, 2.357.0) paged the register in SQL — 38,412 rows at the top of
    the ICP against a 60-second worker — so this case went red that commit
    (green at `76be101a3`). Revenue by service is one row per service, at most
    eleven, which is the bound `queries._report`'s own `page` comment names."""
    with tenant_ctx(brazos):
        a_debtor(brazos, dana, account_no="AC-B1", bills=[(date(2026, 7, 20), Decimal("10.00"))])
        bounded = viewer(
            brazos,
            catalog.KEY_REVENUE_BY_SERVICE,
            **{"from": "2026-08-01", "to": AUGUST_END.isoformat()},
        ).data
        assert "page" not in bounded
        register = viewer(
            brazos,
            catalog.KEY_BILLING_REGISTER,
            **{"from": "2026-08-01", "to": AUGUST_END.isoformat()},
        ).data
        assert "page" in register  # P2.12 — it pages now
        assert "page" in run(brazos)
        assert queries.VIEWERS[catalog.KEY_AR_AGING] is queries.ar_aging


# ── Lifecycle ─────────────────────────────────────────────
# packet: Finance blueprint `P2.21` (p034–p036) · `DEF-REP-6607`
# generated: 2026-09-24 by lane FIN-AGING
# gates: ruff✔ black✔ pytest✔
# exceptions: (1) these run on the default sqlite tier; the PAGE, the filters
#   and the tie-out are SQL and were also measured on real PostgreSQL 16 by
#   `10-scripts/fin_p221_aging_cost.py` (hard-won law 14 — this suite cannot
#   see an aborted transaction, and nothing here catches a database error) ·
#   (2) no case asserts a CURRENCY footer over two currencies: writing a
#   second-currency bill into this fixture would change what every other case
#   here means, and `test_us_rep_canned_reports.py` owns that path
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
