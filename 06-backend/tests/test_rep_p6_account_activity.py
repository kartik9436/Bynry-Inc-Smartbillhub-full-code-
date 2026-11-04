# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · `P6.11` — R23 Account Activity, the joining read.
#           Drawings read as IMAGES (B14 rule 42): p059 (the eyebrow) and p060
#           (the table, the tiles and the two-dates warning).
# Rules:    NFR-3 (pagination in SQL — a UNION ordered and sliced by the
#           database) · NFR-5 (no hard caps) · BR-CUS-054 (the customer is read
#           from `customer_accounts`) · BR-REP-024 (never a 0 where a figure is
#           not derivable) · CLAUDE.md hard rule 1 (tenant scoping) · hard rule
#           8 (the address is WALKED to premises) · B14 rule 31 (no uuid on
#           screen)
# ───────────────────────────────────────────────────────
"""**R23 ACCOUNT ACTIVITY** — one row per account-lifecycle event.

⚠ **THE COUNTS ARE CHOSEN SO NO TWO SUBSETS SHARE A SUM** — three opened, two
closed, one transferred. `net` is `+1`, which no pair of the other three
produces, so a test that passed on the wrong arithmetic would have to be wrong
in two places at once.

⚠ **ONE ACCOUNT PRODUCES TWO ROWS ON PURPOSE.** That is the whole reason this
is not the `accounts` dataset, and a fixture in which every account had exactly
one event could not tell the two grains apart.

⚠ **NOTHING HERE SKIPS.** ⚠ **THE SUITE RUNS ON IN-MEMORY SQLITE**, so these
cases prove the SHAPE and the ARITHMETIC and nothing about cost or the query
plan (hard-won law 14). The PostgreSQL half is `10-scripts/p6_join_cost.py`.
"""

from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.customers import account_activity as report
from apps.customers.moves import KIND_MOVE_IN, KIND_MOVE_OUT, MoveRecord
from apps.customers.transfers import Transfer
from apps.reports import datasets, queries, runner

from tests.test_us_bil_025_026_bills_read import an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

OPENED = 3
CLOSED = 2
TRANSFERRED = 1
NET = OPENED - CLOSED  # +1 — a number no pair of the others produces
EVENTS = OPENED + CLOSED + TRANSFERRED


def _baseline():
    """What this tenant already holds, before the fixture adds anything.

    ⚠ **THE `brazos` FIXTURE PROVISIONS A REAL UTILITY**, and a provisioned
    utility may already carry moves. Every case reads this first and asserts
    the MOVEMENT — and also asserts the absolute is non-zero, so an empty
    answer still fails.
    """
    return report.account_activity(per=None)["totals"]


def _move(tenant, actor, account, *, kind, days_ago, effective):
    return MoveRecord.objects.create(
        tenant=tenant,
        account=account,
        kind=kind,
        effective_on=effective,
        # `dana` is a namespace carrying the membership AND the user; the FK
        # wants the user.
        performed_by=getattr(actor, "user", actor),
        performed_at=timezone.now() - timedelta(days=days_ago),
    )


def _transfer(tenant, from_account, to_account, *, days_ago):
    """ONE committed transfer — the third drawn word, from its own table.

    ⚠ **THIS FIXTURE ROW EXISTS BECAUSE ITS ABSENCE MADE A CHECK THAT COULD NOT
    FAIL, AND THE MUTATION FOUND IT.** The first draft seeded only moves, so
    `transferred` was 0 — and a mutation folding a transfer into BOTH `opened`
    and `closed` (which would inflate two tiles by the transfer count and move
    `net` by zero) **passed every case in this file.** Hard-won law 7: a guard
    proved red at birth is the only kind worth having, and this one was not.
    """
    return Transfer.objects.create(
        tenant=tenant,
        transfer_no=f"TRF-TEST-{days_ago:04d}",
        from_account=from_account,
        to_account=to_account,
        state=Transfer.STATE_DONE,
        step=5,
        committed_at=timezone.now() - timedelta(days=days_ago),
        in_date=date.today(),
        out_date=date.today(),
    )


def _activity(tenant, actor):
    """Three accounts, five move events AND one committed transfer.

    The account opened in March and closed in September is the case that
    separates this grain from the `accounts` dataset's: two rows here, one row
    there, and both are right about their own question. The transfer is the
    case that makes the `opened`/`closed`/`transferred` split testable at all.
    """
    first = an_account(tenant, actor, account_no="A-100244", label="Unit A")
    second = an_account(tenant, actor, account_no="A-100512", label="Unit B")
    third = an_account(tenant, actor, account_no="A-100907", label="Unit C")
    _move(tenant, actor, first, kind=KIND_MOVE_IN, days_ago=20, effective=date(2026, 9, 4))
    _move(tenant, actor, second, kind=KIND_MOVE_IN, days_ago=18, effective=date(2026, 9, 6))
    _move(tenant, actor, third, kind=KIND_MOVE_IN, days_ago=16, effective=date(2026, 9, 8))
    # ⚠ the SAME account, closed later — two events, one account.
    _move(tenant, actor, third, kind=KIND_MOVE_OUT, days_ago=5, effective=date(2026, 9, 9))
    _move(tenant, actor, second, kind=KIND_MOVE_OUT, days_ago=3, effective=date(2026, 9, 11))
    _transfer(tenant, first, second, days_ago=1)
    return first, second, third


def test_one_row_is_one_EVENT_and_one_account_can_produce_two_of_them(brazos, dana):
    """⚠ **THE CASE THE `accounts` DATASET REFUSES R23 FOR.**

    Its refusal says it exactly: *"one account can produce several. Serving it
    from account rows would report the accounts that exist, not the moves that
    happened."* Three accounts, five events.
    """
    with tenant_ctx(brazos):
        before = _baseline()
        _first, _second, third = _activity(brazos, dana)
        result = report.account_activity(per=None)

    assert result["grain"] == "one account-lifecycle event"
    assert result["total"] - before["events"] == EVENTS
    assert result["total"] > 0
    for_third = [row for row in result["rows"] if row.account_no == "A-100907"]
    assert len(for_third) == 2
    assert {row.event for row in for_third} == {report.EVENT_OPENED, report.EVENT_CLOSED}


def test_the_four_tiles_foot_and_NET_is_derived_rather_than_summed(brazos, dana):
    """`OPENED · CLOSED · TRANSFERRED · NET` — and `net` is declared
    non-additive, because a renderer totalling a column of group subtotals
    would be right by accident and wrong the first time a group was filtered."""
    with tenant_ctx(brazos):
        before = _baseline()
        _activity(brazos, dana)
        result = report.account_activity(per=2, page=1)

    totals = result["totals"]
    assert totals["opened"] - before["opened"] == OPENED
    assert totals["closed"] - before["closed"] == CLOSED
    assert totals["transferred"] - before["transferred"] == TRANSFERRED
    assert totals["net"] - before["net"] == NET
    assert totals["events"] - before["events"] == EVENTS
    # ⚠ **THE CASE A MUTATION CAUGHT.** A transfer is ONE job and ONE event, so
    # it is counted in `transferred` and in NEITHER `opened` NOR `closed`.
    # Folding it into both would move `net` by zero while inflating two tiles —
    # and with no transfer in the fixture this assertion could not fail, which
    # is what the first draft did.
    assert totals["transferred"] > 0
    assert totals["events"] == totals["opened"] + totals["closed"] + totals["transferred"]
    # ⚠ `net` IS `opened − closed` ON THE WHOLE SET, not only on the movement.
    assert totals["net"] == totals["opened"] - totals["closed"]
    # ⚠ The tiles do not move when a page is cut — §7.2's whole argument.
    assert len(result["rows"]) == 2
    assert result["total"] > len(result["rows"])
    assert result["total"] == totals["events"]
    assert result["additivity"]["net"] == "non"
    assert result["additivity"]["opened"] == "full"


def test_TWO_DATE_COLUMNS_because_two_dates_exist_and_the_window_is_the_first(brazos, dana):
    """p060, verbatim: *"Two date columns because two dates exist — when the
    clerk did it, and when it takes effect."*

    The window is struck on `occurred_at`. A move performed inside the window
    with an effective date outside it IS in this report, which is the drawing's
    own *"a move-in dated 1 October appears in September's activity and in
    October's census, and both are right."*
    """
    with tenant_ctx(brazos):
        first = an_account(brazos, dana, account_no="A-200001", label="Unit Z")
        _move(
            brazos,
            dana,
            first,
            kind=KIND_MOVE_IN,
            days_ago=2,
            effective=date.today() + timedelta(days=30),
        )
        today = date.today()
        result = report.account_activity(start=today - timedelta(days=5), end=today, per=None)

    assert result["total"] >= 1
    row = next(r for r in result["rows"] if r.account_no == "A-200001")
    assert row.occurred_at is not None
    assert row.effective_on is not None
    assert row.effective_on > today  # effective LATER, counted HERE
    assert row.occurred_at.date() <= today


def test_the_union_is_ORDERED_AND_SLICED_and_paging_repeats_nothing(brazos, dana):
    """A `UNION` cut by the database — the order is total (every tuple ends in
    `event_id`), so consecutive pages cannot repeat or skip a row."""
    with tenant_ctx(brazos):
        _activity(brazos, dana)
        whole = report.account_activity(per=None)
        # ⚠ **`ceil`, NOT `// + 2`, AND THE FIRST DRAFT USED THE SECOND.**
        # `BR-SHL-011` says a page past the end CLAMPS rather than erroring, so
        # asking for one more page than exists returns the LAST page AGAIN —
        # and the test then counted six rows twice and called it eight. The
        # over-run was in the test, not in the read model; the clamp is
        # asserted on its own below rather than tripped over here.
        last_page = max(1, -(-whole["total"] // 2))
        pages = [
            report.account_activity(per=2, page=page, sort="occurred_at", direction="desc")
            for page in range(1, last_page + 1)
        ]

    total = whole["total"]
    assert total > 2  # or there is one page and this case proves nothing
    seen = [row.event_id for page in pages for row in page["rows"]]
    assert len(seen) == total
    assert len(set(seen)) == total  # nothing repeated, nothing skipped
    assert pages[0]["pages"] == max(1, -(-total // 2))


def test_a_page_past_the_end_CLAMPS_to_the_last_one_and_never_errors(brazos, dana):
    """`BR-SHL-011` — *invalid values fall back or clamp, NEVER error*.

    ⚠ **THIS CASE EXISTS BECAUSE THE PAGING TEST ABOVE TRIPPED OVER IT.** Its
    first draft walked one page further than existed, got the last page again
    and counted six rows as eight. The clamp is correct — a saved bookmark on
    page 40 of a report that has since shrunk must open, not 500 — and it is
    asserted here, by name, rather than left as a surprise in another case.
    """
    with tenant_ctx(brazos):
        _activity(brazos, dana)
        whole = report.account_activity(per=None)
        last_page = max(1, -(-whole["total"] // 2))
        beyond = report.account_activity(per=2, page=last_page + 40)
        last = report.account_activity(per=2, page=last_page)

    assert beyond["page"] == last_page
    assert [row.event_id for row in beyond["rows"]] == [row.event_id for row in last["rows"]]
    assert len(beyond["rows"]) > 0


def test_it_sorts_by_the_UNION_S_OWN_ALIASES_and_an_unknown_sort_falls_back(brazos, dana):
    """`BR-SHL-011` — an invalid value falls back and NEVER errors, so a saved
    link carrying a retired sort still opens. A combined queryset can only be
    ordered by its own output aliases, which is why the fallback lives in the
    read model rather than in `core.pagination.order_terms`."""
    with tenant_ctx(brazos):
        _activity(brazos, dana)
        ascending = report.account_activity(sort="occurred_at", direction="asc", per=None)
        descending = report.account_activity(sort="occurred_at", direction="desc", per=None)
        nonsense = report.account_activity(sort="frog", direction="asc", per=None)

    assert [row.event_id for row in ascending["rows"]] == list(
        reversed([row.event_id for row in descending["rows"]])
    )
    # ⚠ THE ENDS MUST REVERSE — equal firsts mean `direction` was ignored.
    assert ascending["rows"][0].event_id != descending["rows"][0].event_id
    assert nonsense["total"] == ascending["total"]  # fell back, did not raise


def test_the_event_filter_is_HONOURED_and_narrows_the_page_count_too(brazos, dana):
    """A chip that changes the URL and nothing else is hard-won law 2's mirror
    — and a filter that narrows the ROWS but not the TOTAL is the same bug one
    layer down, because the pager would offer pages that do not exist."""
    with tenant_ctx(brazos):
        before = _baseline()
        _activity(brazos, dana)
        unfiltered = report.account_activity(per=None)
        opened = report.account_activity(event=report.EVENT_OPENED, per=None)
        closed = report.account_activity(event=report.EVENT_CLOSED, per=None)

    assert opened["total"] - before["opened"] == OPENED
    assert len(opened["rows"]) == opened["total"]
    assert {row.event for row in opened["rows"]} == {report.EVENT_OPENED}
    assert closed["total"] - before["closed"] == CLOSED
    # ⚠ EACH NARROWS — a chip that changes nothing is the mirror of dead UI.
    assert opened["total"] < unfiltered["total"]
    assert closed["total"] < unfiltered["total"]
    # The tiles still describe the WHOLE window, not the filtered slice — they
    # are a statement about the period and a filter is a statement about the
    # rows. Both are drawn, and they answer different questions.
    assert opened["totals"]["closed"] == unfiltered["totals"]["closed"]


def test_the_premises_is_WALKED_and_this_report_declares_no_address_column(brazos, dana):
    """Hard rule 8. The address comes from the premises through the seam; no
    field on any row here holds a copy of one."""
    with tenant_ctx(brazos):
        _activity(brazos, dana)
        result = report.account_activity(per=None)

    row = next(r for r in result["rows"] if r.account_no == "A-100244")
    assert row.premises_address == "1901 Bluestem Ln"
    assert row.unit_label in {"Unit A", "Unit B", "Unit C"}
    fields = set(vars(row))
    assert "address_line" not in fields
    assert "city" not in fields
    assert "postcode" not in fields


def test_a_transfer_is_ONE_event_and_carries_the_drawn_third_word(brazos, dana):
    """p060's `Transferred in` row is NOT a `MoveRecord`.

    `moves.KINDS` is a two-tuple, so the third drawn word comes from
    `apps/customers/transfers.py`'s own table — *"one job, not a move-out
    followed by a move-in"* (B18 §5.7). This case exists so the union has both
    legs exercised; without it the `transfers` leg could be deleted entirely
    and every other case here would still pass.
    """
    with tenant_ctx(brazos):
        _activity(brazos, dana)
        result = report.account_activity(per=None)

    transfers = [row for row in result["rows"] if row.event == report.EVENT_TRANSFERRED_IN]
    assert len(transfers) == TRANSFERRED
    row = transfers[0]
    assert row.reference == "TRF-TEST-0001"
    # It attaches to the account that RECEIVED the service — `Transferred IN`.
    assert row.account_no == "A-100512"
    # ⚠ AND IT RECORDS NOBODY. `transfers` has no performed-by column at all.
    assert row.actor is None
    assert row.actor_absence == report.ABSENCE_UNKNOWN
    codes = {problem["code"] for problem in result["problems"]}
    assert "a_transfer_records_nobody_who_performed_it" in codes


def test_an_actor_that_was_never_recorded_is_UNKNOWN_and_never_a_blank(brazos, dana):
    """`GAP_TRANSFER_HAS_NO_ACTOR`'s posture, exercised on a move whose
    performer is null: a blank BY cell reads as *nobody did this*, which is a
    different and worse claim than *we did not record who*."""
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="A-300001", label="Unit Q")
        move = _move(brazos, dana, account, kind=KIND_MOVE_IN, days_ago=1, effective=date.today())
        MoveRecord.objects.filter(pk=move.pk).update(performed_by=None)
        result = report.account_activity(per=None)

    row = next(r for r in result["rows"] if r.account_no == "A-300001")
    assert row.actor is None
    assert row.actor_absence == report.ABSENCE_UNKNOWN


def test_the_export_stream_takes_no_page_and_no_per_at_all(brazos, dana):
    import inspect

    signature = inspect.signature(report.account_activity_stream)
    assert "page" not in signature.parameters
    assert "per" not in signature.parameters

    with tenant_ctx(brazos):
        _activity(brazos, dana)
        paged = report.account_activity(per=2, page=1)
        streamed = list(report.account_activity_stream())
    assert len(streamed) == paged["total"]
    assert len(streamed) > len(paged["rows"])
    assert len({row.event_id for row in streamed}) == paged["total"]


def test_the_drawn_controls_are_DECLARED_on_the_dataset_so_bind_cannot_drop_them(brazos):
    accounts = datasets.BY_CODE["accounts"]
    assert "event" in accounts.filters
    assert "account" in accounts.filters
    definition = runner.resolve("account_activity")
    bound = runner.bind(definition, {"event": "opened", "from": "2026-09-01"})
    assert bound["event"] == "opened"
    assert bound["from"] == "2026-09-01"


def test_the_per_key_viewer_wins_over_the_dataset_that_refuses_this_report(brazos):
    assert queries.VIEWERS["account_activity"] is queries.account_activity
    assert runner.queries_for("account_activity", "accounts") is queries.account_activity
    assert queries.definition_refusal("account_activity", "accounts") is None
    # The accounts dataset's own refusal is UNCHANGED and still names this
    # module as the read model it was asking for.
    from apps.customers import accounts_dataset

    reason = accounts_dataset.unservable_reason("account_activity")
    assert reason["drawn_grain"] == "one account-lifecycle EVENT"
    assert "apps.customers.moves.MoveRecord" in reason["needs_read_model"]


def test_the_export_reaches_the_per_key_STREAM_and_not_the_dataset_generator(brazos):
    assert runner.stream_for("account_activity", "accounts") is queries.account_activity_rows


def test_no_uuid_is_a_drawn_column(brazos):
    """B14 rule 31 — `event_id` and `account_id` travel for drill-through."""
    assert "event_id" not in queries.ACTIVITY_COLUMNS
    assert "account_id" not in queries.ACTIVITY_COLUMNS
    assert "account_no" in queries.ACTIVITY_COLUMNS
