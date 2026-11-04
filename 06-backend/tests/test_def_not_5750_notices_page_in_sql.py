# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-NOT-5750 — `GET /notices` asked payments for 2,000 rows and
#           paged them in Python, so the 2,001st notice was UNREACHABLE on
#           every page of the list and `count` was a floor rather than a total.
#           Filed 2026-09-18 by the NFR-3 sweep and deliberately left, because
#           removing the cap alone makes an unbounded read.
# Rules:    NFR-3 (universal server pagination) · NFR-5 (no hard caps anywhere
#           — the point is that no number is correct) · BR-SHL-011 (a list URL
#           clamps and never errors; `per` clamps to the ratified sizes) ·
#           BR-CUS-039 (every notice send AND skip is on the record) ·
#           B1 / BR-TEN-013 (a module never touches another module's ORM) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard-won law 7 (prove it
#           RED first, and ask what would make it pass WRONGLY)
# Tests:    this file
# Impacts:  apps/payments/notices.py (`notice_history_page` /
#           `notice_history_count` / `notice_history_row`) ·
#           apps/notifications/payments_seam.py (`NoticeHistoryWindow`) ·
#           apps/notifications/api.py (`notices`) ·
#           apps/notifications/selectors.py (`NOTICE_READ_CAP` deleted)
# ───────────────────────────────────────────────────────
"""DEF-NOT-5750 — the notice record has no last page, and that is asserted.

⚠ **A TEST THAT COUNTS RETURNED ROWS CANNOT SEE THIS DEFECT AND NEVER COULD.**
Under the 2,000-row ceiling `GET /notices` served fifty perfect rows, a correct
`next` link and an envelope byte-identical to the one it serves today. Every
assertion in `test_def_128_notifications_api.py` passed throughout. What was
wrong was not the answer but the SHAPE OF THE RECORD BEHIND IT: past row 2,000
there was nothing a clerk could open, and the response said so in a problem row
that read like honesty rather than like a breach.

So the cases below assert three things a row count cannot:

  1. **THE 2,001st NOTICE COMES BACK.** The single sentence of the defect. It
     is asserted by ID — not by a status code and not by a row count — because
     the old code answered `200` with fifty rows on that request too: it
     clamped page 41 down to page 40 and served the same fifty rows twice, and
     a clerk paging to the end of the record simply never saw the last one.
  2. **THE PAGE IS A `LIMIT`.** The bound in the SQL equals the page size the
     screen asked for, over `notice_history` itself.
  3. **THE COST DOES NOT FOLLOW THE TENANT.** Sixty notices and two thousand
     and sixty: the same statements against that table, the same bound.

⚠ **A QUERY COUNT IS THE WRONG INSTRUMENT AND IS NOT USED AS THE DISCRIMINATOR.**
Paging in SQL makes the number of statements go UP — one unbounded `SELECT`
becomes a `COUNT(*)` plus a bounded page — so a ceiling on statements would have
been satisfied by the defect and broken by the fix. What moved is how many rows
a statement fetches, which is a property of the statement.

RED-FIRST PROOF (hard-won law 7, in the harness that runs it — `pytest`, never
a `__main__`)
-------------------------------------------------------------------------------
Every case below was run with `pytest` against a second worktree pinned at
`14f7ffd59`, the tip this lane started from, holding the UNMODIFIED
`apps/payments/notices.py`, `apps/notifications/payments_seam.py`,
`apps/notifications/api.py` and `apps/notifications/selectors.py`. **8 failed,
3 passed.** The failures are quoted here rather than paraphrased, because each
one is a different half of the defect:

  * `AssertionError: count came back as a FLOOR rather than a total` ·
    `assert 2000 == (2000 + 1)` — the tenant holds 2,001 notices and the list
    reports 2,000, on the page that should hold the missing one.
  * `assert 2000 == (2000 + 60)` — the same floor, one population up.
  * `AssertionError: the statement asked the database for {2000} rows to draw
    50 (NFR-3)` · `assert {2000} == {50}` — the defect drawn in SQL. Note that
    the old statement DID carry a `LIMIT`; it was the ceiling. **A case
    asserting merely that a bound was present would have passed green
    throughout the whole life of this defect.**
  * `assert 'notice_history_truncated' not in ['certified_number_unavailable',
    'notice_history_truncated']` — the apology for the cap, still on the wire.
  * `assert not True` · `where True = hasattr(selectors, 'NOTICE_READ_CAP')`.
  * `AttributeError: module 'apps.notifications.payments_seam' has no attribute
    'notice_history_window'` — the thing that carries a page across the module
    boundary did not exist.
  * `KeyError: 'available'` — the half-published case, which on the old tree
    cannot even name the read it is unpublishing.

⚠ **THREE CASES PASS ON BOTH TREES AND THAT IS THE DESIGN, NOT A GAP.**
`test_the_window_stays_inside_its_tenant` guards a leak the FIX could introduce
— `GET /notices` gained a `COUNT(*)` today that it never issued before — and
hard rule 1 held before it too. `test_a_page_is_a_window_on_one_ordering…`
likewise: paging in Python over a list built once cannot repeat or drop a row,
and paging in SQL can. And `test_the_panel_read_is_unchanged…` is the
what-must-not-have-moved case, which is worthless unless it is green on both.
A case that goes red on the old tree proves the defect; a case that stays green
on both proves the repair did not cost something else, and this file needs both.

⚠ **AND THE FIRST TWO RUNS OF THIS FILE PROVED NOTHING AT ALL, WHICH IS WORTH
RECORDING.** Run 1: the account fixture was written from memory rather than
copied, so 10 of 11 cases died in `an_account` on BOTH trees before reaching an
assertion. Run 2: `tenant_ctx` does not nest — the inner block clears
`app.tenant_id` instead of restoring the outer one — so the window case failed
`AUTH-003` on the FIXED tree. Both are law 7's *incapable of passing* shape, and
both were invisible until the file was actually run red and green side by side.

⚠ **THE POPULATIONS ARE 60 AND 2,001 AND NEITHER IS PADDING.** `per` clamps to
the ratified vocabulary `(50, 100, 200, 500, 1000)`, so a fixture under fifty
rows cannot observe a page boundary on any tree — the sibling lane
(`DEF-SHL-5748`) lost a whole red-first run to exactly that. And a fixture under
2,001 rows cannot observe the ceiling at all, which is why no test in this repo
had ever reached it: *"no tenant in any fixture holds 2000 notices"* is the
defect row's own escape reason.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.notifications import api as notifications_api
from apps.notifications import payments_seam, selectors
from apps.payments import notices as payments_notices
from apps.payments.collections_models import NoticeHistory

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

#: The ratified default page (`core.pagination.PAGE_SIZES`). There is no smaller
#: page to ask for, so a population below it cannot see a page boundary.
PAGE = 50

#: The ceiling this defect is about. It is a LITERAL here on purpose: the point
#: of the fix is that this number no longer exists anywhere in the product, so
#: the test that proves the row beyond it is reachable has to hold its own copy.
OLD_CAP = 2000

#: Distinct business dates so the newest-first order is total rather than
#: tie-broken. A page taken in SQL over an unstable order repeats one row on two
#: pages and hides another entirely, which is a defect the fix could introduce
#: and which a same-date fixture would never show.
FIRST_NOTICE_ON = date(2021, 1, 1)


def an_account(actor, tenant, *, account_no="A-57500"):
    """One account for the notices to hang on — `test_def_128`'s own fixture, verbatim.

    ⚠ **COPIED RATHER THAN RE-INVENTED, AND THE FIRST DRAFT OF THIS FILE PROVES
    WHY.** It was written from memory — `unit=<object>`, `status="active"`,
    `opened_on=` — and every case that used it failed on the FIXTURE before it
    reached a single assertion, on both trees alike. A red-first run over a
    fixture that cannot build is not a red proof of anything.
    """
    from apps.customers import models as customer_models

    premises = make_premises(actor, address_line=f"{account_no} Route 4")
    unit = make_unit(actor, premises["id"], label=account_no, services=["electric"])
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=customer_models.AccountType.objects.first(),
        account_no=account_no,
    )


def _bulk_notices(tenant, account, count, *, start=0, notice_type="disconnect"):
    """`count` `notice_history` rows written straight to the table.

    ⚠ **THROUGH `bulk_create`, NOT THROUGH `record_notice`, AND THAT IS THE
    POINT OF THE FIXTURE.** What is under test is the cost and the reach of
    READING a record of a size no fixture in this repo has ever built — the
    defect's own escape reason. Two thousand round trips through the writer to
    prove a `LIMIT` is an hour of nobody's time; the writer itself is asserted
    by `test_def_128_notifications_api.py`, which uses the real one.

    Hard rule 1: the write happens inside the tenant context, because outside it
    `app.tenant_id` is unset and a tenant table answers nothing.

    Returns the rows in the order the LIST will serve them — newest first — so a
    case can name "the 2,001st row a clerk would page to" without arithmetic.
    """
    with tenant_ctx(tenant):
        NoticeHistory.objects.bulk_create(
            [
                NoticeHistory(
                    tenant=tenant,
                    account=account,
                    notice_type=notice_type,
                    tier="final_48_hour",
                    channel="print",
                    outcome="sent",
                    detail={"certified_mail": True, "cut_date": "2026-08-18"},
                    occurred_on=FIRST_NOTICE_ON + timedelta(days=start + index),
                )
                for index in range(count)
            ]
        )
        return list(
            NoticeHistory.objects.filter(tenant=tenant).order_by("-occurred_on", "-created_at")
        )


def _notice_statements(captured):
    """Every SELECT this request issued against `notice_history`, as SQL.

    ⚠ **IT READS THE SQL AND NOT A COUNT.** A request resolves a tenant, reads a
    role and reads the tenant's currency, so the raw number moves whenever an
    unrelated lane touches the middleware. The statements against THIS table are
    the only ones this defect is about.
    """
    rows = []
    for query in captured:
        sql = query["sql"]
        if "notice_history" in sql.lower() and sql.lstrip()[:6].upper() == "SELECT":
            rows.append(sql)
    return rows


def _page_statements(statements):
    """The row-fetching SELECTs — everything that is not the paginator's COUNT."""
    return [sql for sql in statements if "COUNT(" not in sql.upper()]


def _limits(statements):
    return {int(m.group(1)) for sql in statements for m in re.finditer(r"LIMIT\s+(\d+)", sql, re.I)}


def _get(tenant, actor, **query):
    return api_call(
        notifications_api.notices,
        "get",
        user=actor.user,
        role="system_admin",
        tenant=tenant,
        query=query or None,
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE DEFECT IN ONE CASE — the 2,001st notice
# ══════════════════════════════════════════════════════════════════════════
def test_the_two_thousand_and_first_notice_is_on_a_page_a_clerk_can_open(brazos, dana):
    """`NFR-5` — no code path imposes a maximum, and this is the one that did.

    ⚠ **ASSERTED BY ID, NEVER BY A STATUS CODE OR A ROW COUNT.** On the old tree
    this exact request answered `200` with fifty rows: `BR-SHL-011` clamps an
    out-of-range page into range, and with a `count` of 2,000 page 41 clamped to
    page 40 — so the last page of the record was served TWICE and the oldest
    notice was on neither. Nothing about the envelope looked wrong. The only
    observable difference between a product that holds this record and one that
    silently ends at 2,000 is whether that one row comes back.

    The row chosen is the OLDEST, because the list is newest-first and the
    ceiling therefore cut the record off at its far end — the end a regulator
    asking *"what did you send in 2021?"* is walking towards.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-57501")
    rows = _bulk_notices(brazos, account, OLD_CAP + 1)
    assert len(rows) == OLD_CAP + 1
    oldest = rows[-1]

    last_page = (OLD_CAP + 1 + PAGE - 1) // PAGE  # 41 at fifty a page
    response = _get(brazos, dana, page=last_page)

    assert response.status_code == 200
    assert response.data["count"] == OLD_CAP + 1, (
        "`count` came back as a FLOOR rather than a total — the read stopped at "
        "the ceiling and measured what it had built (DEF-NOT-5750)"
    )
    served = [row["id"] for row in response.data["results"]]
    assert str(oldest.pk) in served, (
        f"the {OLD_CAP + 1}th notice is unreachable: page {last_page} of the record "
        f"came back holding {len(served)} rows and not one of them is the oldest "
        "notice this utility sent"
    )


def test_the_record_no_longer_says_where_it_stopped(brazos, dana):
    """The clerk-facing sentence went WITH the cap, and both halves matter.

    `notice_history_truncated` told a clerk the read stopped at 2,000 rows and
    that `count` was a floor. That copy was honest while it was true and becomes
    a lie on screen the moment nothing truncates — which is the mirror of
    hard-won law 2 the register calls a live screen behind a dead control.

    ⚠ **THIS CASE IS HERE BECAUSE REMOVING A VALUE AND REMOVING ITS CONSUMERS
    ARE TWO ACTS** (`DEF-CUS-3653`'s lesson: an absence is invisible to every
    check this repo has). It goes red on the old tree — the code IS in
    `problems` there, at this population — and it goes red again the day anybody
    re-introduces a ceiling and its apology.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-57502")
    _bulk_notices(brazos, account, OLD_CAP + 1)

    response = _get(brazos, dana)

    codes = [problem["code"] for problem in response.data["problems"]]
    assert "notice_history_truncated" not in codes, (
        "the response still tells a clerk where the record stopped, over a record "
        "that does not stop anywhere"
    )
    assert response.data["available"] is True
    assert selectors.CERTIFIED_NUMBER_UNAVAILABLE in codes, (
        "the certified-number absence is a DIFFERENT and still-true statement and "
        "must not have been swept out with the cap"
    )


def test_no_ceiling_constant_survives_on_this_path(brazos, dana):
    """`NFR-5` — *"the point is that no number is correct"*, so there is no number.

    A lane repairing a slow list by re-introducing `NOTICE_READ_CAP = 50000`
    would satisfy every other case in this file: fifty rows, a `LIMIT`, a flat
    statement count, and a `count` that is a total right up to the new ceiling.
    This is the case that refuses it, and it is the only one that can.
    """
    assert not hasattr(selectors, "NOTICE_READ_CAP"), (
        "the notice read carries a ceiling again. NFR-5 forbids a maximum anywhere; "
        "raising one is not fixing it (DEF-NOT-5750)"
    )
    for name in ("notice_history_page", "notice_history_count"):
        published = getattr(payments_notices, name)
        assert published is not None, f"payments no longer publishes {name}"


# ══════════════════════════════════════════════════════════════════════════
# 2 · NFR-3 — the page is taken in the DATABASE
# ══════════════════════════════════════════════════════════════════════════
def test_the_page_reaches_sql_and_the_bound_is_the_screen(brazos, dana):
    """The bound in the statement equals the page the screen asked for.

    Stated as *the LIMIT equals the page* rather than *a LIMIT exists*, because
    the old code's statement carried `LIMIT 2000` — a bound, and the wrong one.
    A case asserting merely that a bound was present would have passed green
    throughout the whole life of this defect.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-57503")
    _bulk_notices(brazos, account, 60)

    with CaptureQueriesContext(connection) as ctx:
        response = _get(brazos, dana)
    assert response.status_code == 200

    statements = _notice_statements(ctx.captured_queries)
    pages = _page_statements(statements)
    assert pages, f"no SELECT reached notice_history at all: {statements}"
    assert _limits(pages) == {PAGE}, (
        f"the statement asked the database for {_limits(pages) or 'no bound'} rows to "
        f"draw {PAGE} (NFR-3)"
    )
    assert any("COUNT(" in sql.upper() for sql in statements), (
        "the paginator's COUNT(*) is missing, so `count` was computed by measuring a "
        "list that had already been built"
    )
    assert len(response.data["results"]) == PAGE
    assert response.data["count"] == 60


def test_the_largest_ratified_page_is_served_whole(brazos, dana):
    """`?per=1000` returns 1,000 rows — nothing clamps below the ratified sizes.

    The complement of the ceiling case: `NFR-5` is broken as much by a read that
    quietly serves fewer rows than were asked for as by one that hides rows past
    a line. Two thousand and one rows, the biggest page in the vocabulary, and
    the bound in the SQL is that page.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-57504")
    _bulk_notices(brazos, account, OLD_CAP + 1)

    with CaptureQueriesContext(connection) as ctx:
        response = _get(brazos, dana, per=1000)
    assert response.status_code == 200

    assert len(response.data["results"]) == 1000
    assert response.data["count"] == OLD_CAP + 1
    assert _limits(_page_statements(_notice_statements(ctx.captured_queries))) == {1000}


def test_the_cost_of_one_screen_does_not_follow_the_tenant(brazos, dana):
    """Sixty notices and 2,060: the same statements, and the same bound.

    ⚠ **WRITTEN AS *THE COST DID NOT MOVE*, NEVER AS A NUMBER.** An equality
    against a literal goes red the day an unrelated lane adds a `select_related`
    and teaches the next reader to edit the figure instead of looking at it.
    What `NFR-3` promises is that drawing ONE SCREEN costs the same whatever the
    utility holds, so the population is grown inside the case.

    On the old tree the statement COUNT was also flat — it was always one
    `SELECT` — and this case still failed, on the bound: `LIMIT 2000` at both
    populations, which is 2,000 rows fetched to draw fifty.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-57505")
    _bulk_notices(brazos, account, 60)

    with CaptureQueriesContext(connection) as small:
        assert _get(brazos, dana).status_code == 200
    small_statements = _notice_statements(small.captured_queries)

    _bulk_notices(brazos, account, OLD_CAP, start=60)
    with CaptureQueriesContext(connection) as large:
        response = _get(brazos, dana)
    assert response.status_code == 200
    large_statements = _notice_statements(large.captured_queries)

    assert response.data["count"] == OLD_CAP + 60
    assert len(large_statements) == len(small_statements), (
        f"{len(small_statements)} statements over 60 notices and "
        f"{len(large_statements)} over {OLD_CAP + 60} — the read follows the tenant"
    )
    assert _limits(_page_statements(large_statements)) == {PAGE}
    assert _limits(_page_statements(small_statements)) == {PAGE}


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE SEAM — what crosses the boundary, and what refuses to
# ══════════════════════════════════════════════════════════════════════════
def test_the_window_refuses_to_be_read_whole(brazos, dana):
    """An unbounded read is a LOUD failure, not a slow success.

    ⚠ **THIS IS THE CASE THAT GUARDS THE FIX AGAINST ITSELF.** The defect row
    says it in one sentence: *"removing the cap alone converts a bounded
    2,000-row Python build into an unbounded one, which is a worse defect than
    the one it fixes."* Without `__iter__`, Python falls back to the old sequence
    protocol and `list(window)` walks `[0]`, `[1]`, `[2]` … one query per row,
    for ever — the unbounded read wearing the costume of the fix, and every
    other case in this file green over it.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-57506")
    #: ⚠ SEEDED OUTSIDE THE CONTEXT THE WINDOW IS READ IN, BECAUSE `tenant_ctx`
    #: DOES NOT NEST: the inner block's exit clears `app.tenant_id` rather than
    #: restoring the outer one, and the next read raises `AUTH-003`. The first
    #: draft of this case nested them and failed on the FIXED tree for that and
    #: nothing else — which is the shape law 7 calls *incapable of passing*.
    _bulk_notices(brazos, account, 3)

    with tenant_ctx(brazos):
        window, problems = payments_seam.notice_history_window()

        assert problems == ()
        assert window.count() == 3
        assert len(window[0:2]) == 2

        with pytest.raises(TypeError):
            list(window)
        with pytest.raises(TypeError):
            window[0:]  # an open-ended slice is the same unbounded read
        with pytest.raises(TypeError):
            window[0]  # one row per query is the other way to get there
        with pytest.raises(TypeError):
            window[0:2:2]  # a step the OFFSET would honour and the reader would not


def test_a_half_published_payments_reports_rather_than_answering_a_wrong_total(
    brazos, dana, monkeypatch
):
    """Count without page, or page without count, is a screen at war with itself.

    DEF-075's rule one step on: *"we could not count"* and *"there is nothing"*
    must never render the same. A window that could count 4,000 but not fetch a
    page would draw an empty table under a footer saying 4,000 — which is worse
    than either honest answer, so neither half is used unless both resolve.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-57507")
    _bulk_notices(brazos, account, 3)

    real = payments_seam._resolve

    def only_the_count(module, attribute, kind="selectors"):
        if attribute == payments_seam.NOTICE_HISTORY_PAGE:
            return None
        return real(module, attribute, kind=kind)

    monkeypatch.setattr(payments_seam, "_resolve", only_the_count)

    response = _get(brazos, dana)

    assert response.data["available"] is False
    assert response.data["results"] == []
    assert response.data["count"] == 0, (
        "a total was served over a record that could not be read — a footer nobody "
        "can reconcile with the empty table above it"
    )
    codes = [problem["code"] for problem in response.data["problems"]]
    assert payments_seam.NOTICE_HISTORY_UNAVAILABLE in codes
    detail = next(
        problem["detail"]
        for problem in response.data["problems"]
        if problem["code"] == payments_seam.NOTICE_HISTORY_UNAVAILABLE
    )
    assert payments_seam.NOTICE_HISTORY_PAGE in detail, (
        "the problem row must NAME the read that is missing — a lane repairing this "
        "needs to know which half"
    )


def test_the_window_stays_inside_its_tenant(brazos, dana, lonestar, erin):
    """Hard rule 1 — a page may not reach another tenant, and nor may the count.

    ⚠ **THE COUNT IS THE HALF WORTH ASSERTING HERE.** `GET /notices` gained a
    `COUNT(*)` today that it never issued before, and a count that escaped its
    tenant would leak the SIZE of another utility's collections activity through
    a footer, with every ROW on the page correctly scoped. A row-level isolation
    case cannot see that.
    """
    with tenant_ctx(brazos):
        brazos_account = an_account(dana, brazos, account_no="A-57508")
    _bulk_notices(brazos, brazos_account, 60)

    response = api_call(
        notifications_api.notices,
        "get",
        user=erin.user,
        role="system_admin",
        tenant=lonestar,
    )

    assert response.status_code == 200
    assert (
        response.data["count"] == 0
    ), "Lone Star Ridge was told how many notices Brazos Bend has sent"
    assert response.data["results"] == []


# ══════════════════════════════════════════════════════════════════════════
# 4 · WHAT MUST NOT HAVE MOVED
# ══════════════════════════════════════════════════════════════════════════
def test_the_panel_read_is_unchanged_and_still_means_last_n_on_one_account(brazos, dana):
    """`notice_history_for` keeps its exact behaviour — `collections_read` uses it.

    It was rewritten today to stand on `notice_history_page`, which is a change
    to HOW it answers and must be no change at all to WHAT it answers. The
    account panel draws the last 100 notices beside the ladder; if that had
    silently become the first 100, or a different row shape, nothing else in
    this repo would have noticed.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-57509")
    rows = _bulk_notices(brazos, account, 120)

    with tenant_ctx(brazos):
        panel = payments_notices.notice_history_for(account_id=account.pk, limit=100)

    assert len(panel) == 100, "the panel's bound is the caller's, and it still holds"
    assert [row["id"] for row in panel] == [str(row.pk) for row in rows[:100]], (
        "newest first — *what have we told them lately* is the question a clerk on "
        "the phone is asking"
    )
    assert set(panel[0]) == {
        "id",
        "account_id",
        "notice_type",
        "tier",
        "channel",
        "outcome",
        "skip_reason",
        "outbound_message_id",
        "detail",
        "occurred_on",
        "actor_id",
    }, "the published row shape moved when the read was split"


def test_a_page_is_a_window_on_one_ordering_with_nothing_repeated_or_hidden(brazos, dana):
    """Walk the whole record a page at a time: every row once, in order.

    ⚠ **THE FAILURE THIS GUARDS IS CREATED BY THE FIX AND NOT BY THE DEFECT.**
    Paging in Python over a list that was built once cannot repeat or drop a
    row. Paging in SQL issues a fresh `LIMIT`/`OFFSET` per page, so an unstable
    `ORDER BY` shows the same notice on two pages and hides another entirely —
    on a legal record, that is a regulator being shown one letter twice and
    another never.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-57510")
    rows = _bulk_notices(brazos, account, 130)

    walked: list[str] = []
    for number in (1, 2, 3):
        response = _get(brazos, dana, page=number)
        assert response.status_code == 200
        walked.extend(row["id"] for row in response.data["results"])

    assert walked == [str(row.pk) for row in rows], (
        "the pages do not reassemble into the record: either a notice appeared twice "
        "or one is on no page at all"
    )
    assert len(set(walked)) == len(walked)
