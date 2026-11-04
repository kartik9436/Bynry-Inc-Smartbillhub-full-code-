# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · `P6.11` wave 2 — R34 Disconnect & Reconnect, the
#           joining read. Drawing read as an IMAGE (B14 rule 42): p065.
# Rules:    `BR-REP-039` (PO ruling 2026-09-27 option (a) — ONE ROW PER
#           ACCOUNT, latest case) · NFR-3 (pagination in SQL) · NFR-5 (no
#           caps) · BR-REP-024 (never a 0 where a figure is not derivable) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2 (money stored
#           4dp) · B14 rule 31 (no uuid on screen)
# ───────────────────────────────────────────────────────
"""**R34 DISCONNECT & RECONNECT** — one row per ACCOUNT, showing its latest case.

⚠ **THE FIRST CASE IN THIS FILE IS THE PO'S OWN WORKED EXAMPLE, NUMBER FOR
NUMBER.** `BR-REP-039` was ruled on this sentence:

    *"Alia is cut off on 3 June for `$210` owed and restored on 11 June when
    she pays. She falls behind again and is cut off on 9 September for `$185`.
    … Under one row per case she is two lines, and the total at the bottom
    reads `$395` owed — money she never owed all at once."*

So the test asserts **`$185.00`, and asserts `!= $395.00` by name.** A test that
only asserted the first would pass on a read model that served two rows and
happened to put the September one first.

⚠ **NOTHING HERE SKIPS.** ⚠ **THE SUITE RUNS ON IN-MEMORY SQLITE**, so these
cases prove the SHAPE and the ARITHMETIC and nothing about cost or the query
plan (hard-won law 14). The PostgreSQL half is `10-scripts/p6w2_cost.py`.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from apps.customers import disconnect_reconnect as report
from core.pagination import ListParams
from apps.customers import disconnects
from apps.reports import queries, runner

from tests.test_us_bil_025_026_bills_read import an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: The PO's own figures. ⚠ **`ALIA_JUNE + ALIA_SEPTEMBER` IS THE NUMBER THAT
#: MUST NOT APPEAR**, and it is spelled out so a reader of a failure sees the
#: ruling rather than an arithmetic surprise.
ALIA_JUNE = D("210.0000")
ALIA_SEPTEMBER = D("185.0000")
MONEY_SHE_NEVER_OWED_AT_ONCE = ALIA_JUNE + ALIA_SEPTEMBER  # $395.00
#: What a cut row must record beside the cut, per
#: `ck_cut_records_the_price_of_coming_back`. The AMOUNT is arbitrary and is
#: never asserted: the report does not read it, and pinning a figure a rule
#: does not fix would be a fixture asserting a price nobody signed.
RECONNECTION_FEE = D("35.0000")


def _case(
    tenant,
    account,
    *,
    opened_on,
    owed,
    state,
    cut_on=None,
    reconnected_on=None,
    reason=None,
):
    return disconnects.DisconnectCase.objects.create(
        tenant=tenant,
        account=account,
        sequence=disconnects.SEQ_SERVICE,
        state=state,
        amount_owed_at_open=owed,
        currency="USD",
        opened_on=opened_on,
        cut_on=cut_on,
        reconnected_on=reconnected_on,
        cut_reason=reason,
        # ⚠ **A CUT ROW CARRIES THE PRICE OF COMING BACK, AND THE DATABASE
        # ENFORCES IT** — `ck_cut_records_the_price_of_coming_back`
        # (`customers/0024`): a row with `cut_on` set and no reconnection fee,
        # no fee code and no deposit election beside it cannot answer the
        # question the customer asks first, so the constraint refuses it.
        # A fixture that omitted these three failed the CHECK and the test then
        # failed for a reason that is not the report's — which is a test that
        # cannot fail for the right one.
        reconnection_fee_amount=(RECONNECTION_FEE if cut_on is not None else None),
        reconnection_fee_code=(disconnects.RECONNECT_CHARGE_CODE if cut_on is not None else None),
        deposit_disposition=(disconnects.DEPOSIT_HELD if cut_on is not None else None),
    )


def _alia(tenant, actor):
    """The PO's account, with BOTH of her cases — June restored, September cut.

    ⚠ **THE JUNE CASE MUST BE `restored` AND NOT MERELY OLDER.**
    `uq_one_open_disconnect_case_per_account` permits exactly one open case per
    account, so a fixture leaving both open would be refused by the database
    and the test would fail for the wrong reason — which is a test that cannot
    fail for the right one.
    """
    account = an_account(tenant, actor, account_no="A-ALIA-01", label="Unit A")
    _case(
        tenant,
        account,
        opened_on=date(2026, 5, 28),
        owed=ALIA_JUNE,
        state=disconnects.STATE_RESTORED,
        cut_on=date(2026, 6, 3),
        reconnected_on=date(2026, 6, 11),
    )
    _case(
        tenant,
        account,
        opened_on=date(2026, 9, 2),
        owed=ALIA_SEPTEMBER,
        state=disconnects.STATE_CUT,
        cut_on=date(2026, 9, 9),
    )
    return account


def _baseline(**kwargs):
    """What this tenant already holds. The `brazos` fixture provisions a REAL
    utility, which may already carry cases; every case asserts the MOVEMENT and
    also asserts the absolute is non-zero, so an empty answer still fails."""
    return report.disconnect_reconnect(per=None, **kwargs)["totals"]


def test_ALIA_IS_ONE_ROW_AND_THE_BALANCE_IS_185_AND_NEVER_395(brazos, dana):
    """⚠ **THE RULING, ASSERTED AS ARITHMETIC** — `BR-REP-039`.

    One row per account showing the LATEST case. Two cases on one account
    contribute the September figure once, and the June figure is not in the
    total at all.
    """
    with tenant_ctx(brazos):
        before = _baseline()
        _alia(brazos, dana)
        result = report.disconnect_reconnect(per=None)

    assert result["grain"] == "one account, showing its latest disconnect case"
    rows = [row for row in result["rows"] if row.account_no == "A-ALIA-01"]
    # ONE ROW. Not two.
    assert len(rows) == 1
    row = rows[0]
    assert row.balance == ALIA_SEPTEMBER
    assert row.cut_on == date(2026, 9, 9)
    assert row.reconnected_on is None
    # ⚠ **THE EARLIER CASE IS COUNTED AND NOT SERVED** — `BR-REP-039`.
    assert row.earlier_cases == 1

    moved = result["totals"]["owed"] - before["owed"]
    assert moved == ALIA_SEPTEMBER
    # ⚠ The number the PO was shown and ruled against, by name.
    assert moved != MONEY_SHE_NEVER_OWED_AT_ONCE
    assert result["totals"]["accounts"] - before["accounts"] == 1


def test_the_tile_foots_to_the_rows_even_when_a_page_is_cut(brazos, dana):
    """`owed` is a SQL aggregate over the whole filtered set, never the page.

    ⚠ **THE FIXTURE MUST HOLD MORE ACCOUNTS THAN THE PAGE**, or a totals check
    passes on a read model that sums the page — which is the exact defect the
    tile/row agreement exists to prevent.
    """
    with tenant_ctx(brazos):
        before = _baseline()
        _alia(brazos, dana)
        for index in range(3):
            account = an_account(brazos, dana, account_no=f"A-OTHER-{index}", label=f"U{index}")
            _case(
                brazos,
                account,
                opened_on=date(2026, 9, 3 + index),
                owed=D("100.0000"),
                state=disconnects.STATE_NOTICE_SENT,
            )
        page = report.disconnect_reconnect(per=2, page=1)

    assert len(page["rows"]) == 2
    assert page["total"] - before["accounts"] == 4
    assert page["total"] > len(page["rows"])
    # The tile is over FOUR accounts although two rows were served.
    assert page["totals"]["owed"] - before["owed"] == ALIA_SEPTEMBER + D("300.0000")
    assert page["totals"]["accounts"] == page["total"]


def test_ELIGIBLE_and_PAID_are_NULL_with_their_reasons_and_never_zero(brazos, dana):
    """`BR-REP-024`. A supervisor reading `ELIGIBLE 0` would conclude nobody is
    due to be cut off; the truth is that nothing in this product evaluates the
    rule at all, and those are opposite facts."""
    with tenant_ctx(brazos):
        _alia(brazos, dana)
        result = report.disconnect_reconnect(per=None)

    totals = result["totals"]
    assert totals["eligible"] is None
    assert totals["eligible_value"] is None
    assert totals["collected"] is None
    codes = {problem["code"] for problem in result["problems"]}
    assert report.GAP_ELIGIBLE_IS_NOT_EVALUATED_ANYWHERE["code"] in codes
    assert report.GAP_PAID_IS_PAYMENTS_AND_NOT_A_CASE_COLUMN["code"] in codes
    # Every row carries the same absence, so the column renders as a dash with
    # a reason rather than disappearing from a drawn table.
    assert all(row.paid is None for row in result["rows"])
    assert all(row.paid_absence for row in result["rows"])
    assert result["additivity"]["eligible"] == "unavailable"
    assert result["additivity"]["earlier_cases"] == "non"


def test_the_page_and_the_stream_serve_the_same_rows_in_the_same_order(brazos, dana):
    """Viewing fetches a page and exporting streams the whole filtered set —
    **two functions, never a flag.** They must agree, or a clerk's file
    disagrees with the screen it was downloaded from."""
    with tenant_ctx(brazos):
        _alia(brazos, dana)
        for index in range(4):
            account = an_account(brazos, dana, account_no=f"A-STREAM-{index}", label=f"S{index}")
            _case(
                brazos,
                account,
                opened_on=date(2026, 9, 10 + index),
                owed=D("50.0000"),
                state=disconnects.STATE_NOTICE_SENT,
            )
        whole = report.disconnect_reconnect(per=None)
        streamed = list(report.disconnect_reconnect_stream())

    assert [row.case_id for row in streamed] == [row.case_id for row in whole["rows"]]
    assert len(streamed) == whole["total"]


def test_the_sort_reverses_at_BOTH_ends_so_it_cannot_be_a_python_sort_of_a_page(brazos, dana):
    """⚠ **EQUAL FIRSTS WOULD MEAN `direction` WAS IGNORED**, so the comparison
    is `!=` and never `<=`. A page sorted in Python after the slice reverses
    within the page and not across the set."""
    with tenant_ctx(brazos):
        for index in range(6):
            account = an_account(brazos, dana, account_no=f"A-SORT-{index}", label=f"T{index}")
            _case(
                brazos,
                account,
                opened_on=date(2026, 9, 1 + index),
                owed=D("10.0000") * (index + 1),
                state=disconnects.STATE_NOTICE_SENT,
            )
        ascending = report.disconnect_reconnect(per=2, page=1, sort="notice_on", direction="asc")
        descending = report.disconnect_reconnect(
            per=2, page=1, sort="notice_on", direction="desc"
        )

    assert ascending["rows"][0].case_id != descending["rows"][0].case_id
    assert ascending["rows"][0].notice_on < descending["rows"][0].notice_on


def test_the_report_is_served_by_a_PER_KEY_VIEWER_and_the_work_orders_refusal_STAYS(
    brazos, dana
):
    """⚠ **BOTH HALVES, IN ONE CASE.**

    `runner.queries_for` must resolve R34 to this lane's viewer — otherwise the
    read model is dead code (hard-won law 2) — **and** `work_orders`' own
    refusal must still be there, because `BR-REP-039` supersedes it as a
    statement about the REPORT and leaves it standing as a statement about the
    DATASET. A refusal deleted the day its read model lands is a refusal nobody
    can read when the wiring rots.
    """
    from apps.work import work_orders_dataset

    assert runner.queries_for("disconnect_reconnect", "work_orders") is queries.disconnect_reconnect
    assert runner.stream_for("disconnect_reconnect", "work_orders") is (
        queries.disconnect_reconnect_rows
    )
    assert work_orders_dataset.GAP_R34_IS_A_DIFFERENT_GRAIN is not None
    # …and it still refuses, from the dataset's own entry point.
    with tenant_ctx(brazos):
        with pytest.raises(queries.DatasetCannotServe):
            queries.work_orders_dataset({}, key="disconnect_reconnect")


def test_the_DOWNLOAD_BUTTON_has_something_to_post_to(brazos, dana):
    """⚠ **HARD-WON LAW 2'S MIRROR.** `ReportViewerPage` enables the export
    icon whenever a report renders, so the moment R34 stops refusing, a live
    control starts posting a `resource` the server must hold. Registered in the
    same commit that could have created the 404."""
    from apps.reports import exports

    names = {resource.name for resource in exports.RESOURCES}
    assert "disconnect_reconnect" in names
    resource = next(r for r in exports.RESOURCES if r.name == "disconnect_reconnect")
    assert resource.slug == "disconnect-reconnect"
    # ⚠ **`whole=True` IS PROVED BY COUNTING ROWS, NOT BY READING THE SOURCE.**
    # A first draft asserted `"whole=True" in <the lambda's constants>` and ORed
    # it with True — a check that could not fail, which is worse than none
    # because it is trusted (hard-won law 7). The real question is whether the
    # file is longer than a page, so the fixture makes it so and the count
    # answers it.
    with tenant_ctx(brazos):
        for index in range(5):
            account = an_account(brazos, dana, account_no=f"A-DL-{index}", label=f"D{index}")
            _case(
                brazos,
                account,
                opened_on=date(2026, 9, 1 + index),
                owed=D("20.0000"),
                state=disconnects.STATE_NOTICE_SENT,
            )
        paged = report.disconnect_reconnect(per=2, page=1)
        # ⚠ **A `ListParams`, NOT A DICT.** `exports._rows_for` reads
        # `params.filters`, so a plain mapping raises `AttributeError` inside
        # the lambda — which is how this assertion failed the first time it ran
        # and is exactly what the test exists to catch on the real path.
        exported = list(resource.select(ListParams(per=2, page=1)))

    assert len(paged["rows"]) == 2
    assert len(exported) == paged["total"]
    assert len(exported) > len(paged["rows"])


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P6.11 wave 2 (R34; BR-REP-039 · 12-governance/02-decision-log.md 2026-09-27 §1 · 05-prototype/09 Reports Build Brief.pdf p065 as an image per B14 rule 42)
# screens: S46
# generated: 2026-09-27 by lane REP-P6-W2
# gates: RED PROVED FIRST — before `apps/customers/disconnect_reconnect.py` existed this file could not import, and `runner.queries_for('disconnect_reconnect','work_orders')` resolved to the dataset query, which raised `DatasetCannotServe` naming p065.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
