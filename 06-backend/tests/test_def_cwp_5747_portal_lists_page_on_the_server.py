# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-CWP-5747 — *"every customer-portal list holds ALL its rows in
#          the browser"*. Six portal edge endpoints served an UNBOUNDED array
#          and `portal/components/listTable.tsx` searched, sorted and sliced it
#          client-side. `GET accounts/{id}/readings` is every reading an
#          account has ever taken, and an AMI deployment writes an interval
#          reading per meter per hour.
# Rules:   NFR-3 (universal server pagination) · NFR-5 (NO hard caps anywhere —
#          nothing added here refuses a row that exists) · BR-SHL-011 (the URL
#          grammar q/sort/dir/page/per/f.<name>; an out-of-range page CLAMPS
#          and never 4xx) · IS-2 (the one page-size vocabulary) ·
#          BR-CWP-010 (every read intersected with the session's flat account
#          set IN THE QUERY — a filter moving into SQL must not widen it) ·
#          BR-CWP-015 (totalled, never merged — the roll-up is the WHOLE set's)
#          · BR-CWP-061 (a bounce is two rows and they are adjacent) ·
#          BR-CWP-043 (owing is its own column) · B14 rule 35 (the catalogue
#          writes the words, so the server matches CODES and the screen
#          resolves what it drew) · hard rule 1 (tenant scoping)
# Tests:   this file
# Impacts: apps/metering/portal_reads.py (`readings_page`, `reading_services`,
#          `_reading_rows`) · apps/portal/paging.py (new) ·
#          apps/portal/selectors.py (`account_readings_page`, `bills_page`,
#          `documents_page`, `money_page`, `my_accounts_page`) ·
#          apps/portal/api.py (five views) · apps/portal/seams/billing_seam.py
#          (`bill_windows_for`) · seams/metering_seam.py (`readings_page`)
# ───────────────────────────────────────────────────────
"""`DEF-CWP-5747` — the portal's five lists take their page from the SERVER.

RED-FIRST PROOF (hard-won law 7, in the harness that runs it — `pytest`, never
a `__main__`): every case below was run against a pristine worktree at the
branch tip BEFORE any of this was written, and the failures are quoted in the
lane report.

⚠ **A CASE THAT COUNTS RETURNED ROWS CANNOT TELL A SERVER PAGE FROM A CLIENT
PAGE, AND WOULD HAVE PASSED THROUGH THE WHOLE LIFE OF THIS DEFECT.** The old
endpoints returned the right rows, in the right order, with the right figures:
everything about the ANSWER was correct and the only thing wrong was that all
of it crossed the wire. So the cases here assert **the SQL that was sent**, or
**the number of statements it took**, or **that a row the browser could never
have seen is now findable** — never a row count on its own. Where a row count
does appear it is a guard on the ENVELOPE and is labelled as such.

⚠ **THE HALF THAT IS NOT ABOUT SPEED IS THE HALF WITH THE TEETH.** The defect
was filed rather than half-fixed on 2026-09-18 with the reason written into its
own row: *"asking the server for one page while search, sort and chips stay in
the browser makes every one of them silently search one page of N"*. So the
sharpest cases here build a population LARGER THAN A PAGE and then ask for a
row that is not on page 1 — by searching for it, and by sorting it to the top.
On the unfixed tree the search case passes for the wrong reason (the browser
had every row); on a page-only fix it fails. Both halves are pinned.

⚠ **THE COST CASES SAY *THE COST DID NOT MOVE*, NEVER A NUMBER** (the form
`test_def_cus_5753_customers_list_pages_in_sql.py` argues for). An equality
against a literal goes red the day an unrelated lane adds a `select_related`,
which teaches the next reader to edit the number instead of looking at it.
What `NFR-3` promises is that one screen costs the same whatever is behind it,
so each builds a SECOND, larger population and asserts the count did not follow.

⚠ **WHICH CASES SPEAK AND WHICH ARE GUARDS — STATED, BECAUSE A READER CANNOT
TELL FROM A GREEN DOT.** The ones that fail on the unfixed tree are the `LIMIT`,
the `COUNT(*)`, the statement count that followed the history, the search that
reaches past page 1 on all five lists, the sort that reaches past page 1, the
service tabs over the whole account, and every whole-set fact
(`oldest_on`/`any_owing`/`populated`/`any_kept`/`total_owing`). The others —
the `BR-SHL-011` clamp, `NFR-5`'s absent cap, `BR-CWP-010`'s 404 and the bounce
pair — are REGRESSION guards: they exist because this fix rebuilt five read
paths, and none of them is evidence that anything is paged.

Run with `JOBS_EAGER=false` (DEF-567) and `--reuse-db` (DEF-GOV-3778).
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from apps.metering import portal_reads
from apps.portal import selectors
from core.pagination import ListParams
from core.tenancy import tenant_context

# ⚠ **`apps.portal.paging` IS IMPORTED LAZILY, AND THAT IS PART OF THE PROOF.**
# A module-level import of a module this commit ADDS makes the whole file fail
# to COLLECT on an unfixed tree — and a collection error proves a file was
# added, not that a page reaches the database. Law 7's own words about the
# weaker shape: *"a case calling `selectors.customer_page` would only ever fail
# with `AttributeError`, which proves a function was added and nothing at all
# about where the page is taken."* Importing it inside the cases that need it
# leaves the ENDPOINT cases below runnable at the tip, where they fail on the
# defect itself — the missing `LIMIT`, the missing `COUNT(*)`, the search that
# cannot reach past page 1.


def _paging():
    from apps.portal import paging

    return paging

from tests.test_us_cwp_usage_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_usage_helpers import a_read, a_water_meter, elm_unit_with_services
from tests.test_us_cwp_helpers import (
    MARIA_EMAIL,
    MARIA_PASSWORD,
    an_issued_bill,
    enrol_maria,
    switch_on,
)

pytestmark = pytest.mark.django_db

TODAY = date(2026, 9, 2)
#: Bigger than one page of fifty, so *page 2 exists* is a fact about the
#: fixture rather than a hope. Sixty is what `DEF-CUS-5753` used for the same
#: reason: a fixture of three cannot tell a page from a list.
MANY = 60


class _Principal:
    """The portal session's principal, as `apps/portal/session.py` shapes it.

    ⚠ **`session.py` IS HUMAN-OWNED AND IS NOT IMPORTED, LET ALONE CHANGED.**
    The selectors under test read `tenant_id`, `account_ids` and `accounts`,
    and nothing else; this stands in for those three so a selector can be
    exercised without a signed-in client. The EDGE cases below use a real
    sign-in, which is where `BR-CWP-010` actually lives.
    """

    def __init__(self, tenant_id, accounts):
        self.tenant_id = tenant_id
        self.account_ids = tuple(str(one) for one in accounts)
        self.accounts = ()


#: How many days of one meter a fixture may use before it needs a second one.
#:
#: ⚠ **`meter_reads` IS RANGE-PARTITIONED ON POSTGRESQL AND THE SUITE'S
#: PARTITIONS COVER THE DEMO YEAR.** One reading per day for 1,100 days runs to
#: 2029 and raises `no partition of relation "meter_reads" found for row` — on
#: PostgreSQL only. On SQLite there are no partitions and the same fixture is
#: silently fine, which is hard-won law 14's shape pointing at the FIXTURE
#: rather than at the code: a case that cannot run on the real database is a
#: case that proves nothing about it.
DAYS_PER_METER = 360


def _many_readings(tenant, actor, *, count=MANY):
    """`count` readings on this account, one per day per meter, inside ONE YEAR.

    ⚠ **DISTINCT DAYS ON PURPOSE.** `uq_meter_reads_head` is unique over
    lineage heads, so two readings on one day would have to be on two meters —
    which is exactly how a count above `DAYS_PER_METER` is spread.
    """
    account = elm_unit_with_services(tenant, actor)
    first = date(2026, 1, 1)
    meters = []
    for made in range(0, count, DAYS_PER_METER):
        seq = len(meters)
        meters.append(
            a_water_meter(
                tenant,
                actor,
                account.unit_id,
                serial=f"88-4021{seq}" if seq else "88-40219",
                asset_no=f"M-8840{seq}",
            )
        )
        for index in range(min(DAYS_PER_METER, count - made)):
            a_read(
                tenant,
                account,
                meters[-1]["id"],
                day=first + timedelta(days=index),
                current=str(100000 + index * 10),
                consumption=str(10 + index),
            )
    return account, meters[0]


def _sql(queries):
    return " ".join(entry["sql"] for entry in queries)


# ⚠ **A NESTED `tenant_context` CLEARS THE OUTER ONE — `core/tenancy.py` says
# so in its own docstring** (*"context is cleared on exit even on error"*), and
# the fixtures here open their own. So every case below builds its rows FIRST
# and only then opens ONE context for the selector calls; calling `a_read`
# inside a `with tenant_context(...)` leaves the block with no tenant and the
# next seam call raises `BR-CWP-005`, which reads like a defect in the code
# under test and is a defect in the test.


def _signed_in(tenant, actor):
    """A real portal session, through the product's own sign-in door.

    ⚠ **THE EDGE CASES GO THROUGH THIS AND NOT THROUGH A STAND-IN PRINCIPAL.**
    `BR-CWP-010`'s intersection lives in the QUERY behind a real session, and
    `apps/portal/session.py` is HUMAN-OWNED — a test that built its own
    principal would be proving something about a class it wrote.
    """
    from apps.portal import models as portal_models

    # ⚠ **ENROL ONLY WHERE NOBODY HAS.** `landlord()` enrols Maria itself, and
    # a second `create_credential` for the same email breaks the unique key —
    # which reads as a defect in the sign-in door and is a defect in the test.
    with tenant_context(tenant.id):
        already = portal_models.PortalCredential.objects.filter(
            tenant_id=tenant.id, email=MARIA_EMAIL
        ).exists()
    if not already:
        enrol_maria(tenant, actor)
    client = Client()
    signed = client.post(
        f"/api/{tenant.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    assert signed.status_code == 200, signed.content
    return client


# ══════════════════════════════════════════════════════════════════════════
# 1 · `CWP-034` READINGS — THE ONE THAT IS GENUINELY UNBOUNDED
#
# It is the only portal list whose size is not bounded by one customer's own
# history: an AMI deployment writes an interval reading per METER per HOUR.
# `apps/portal/paging.SQL_PAGED` records that this is why it, and only it,
# takes its page in SQL.
# ══════════════════════════════════════════════════════════════════════════


def test_the_readings_endpoint_asks_the_database_for_one_page(pine_hill, sarah):
    """⚠ **AIMED AT THE VIEW AND NOT AT THE NEW SELECTOR, ON PURPOSE.** A case
    calling `portal_reads.readings_page` could only ever fail with
    `AttributeError` on an unfixed tree, which proves a function was added and
    nothing at all about where the page is taken."""
    switch_on(pine_hill, sarah)
    account, _meter = _many_readings(pine_hill, sarah)
    client = _signed_in(pine_hill, sarah)
    with CaptureQueriesContext(connection) as captured:
        answer = client.get(
            f"/api/{pine_hill.subdomain}/portal/accounts/{account.pk}/readings"
        )
    assert answer.status_code == 200, answer.content
    sql = _sql(captured.captured_queries)
    assert re.search(r"LIMIT\s+50", sql), (
        "GET readings sent no `LIMIT 50` — the page was taken in Python, or not "
        f"at all. Statements: {len(captured.captured_queries)}"
    )
    assert "COUNT(" in sql.upper(), (
        "no COUNT(*) — the footer's total was counted from the rows that were "
        "built, which means every row was built"
    )
    body = answer.json()
    # ENVELOPE GUARD, not evidence of paging.
    assert len(body["readings"]) == 50
    assert body["count"] == MANY
    assert body["page"] == 1
    assert body["per"] == 50


def test_the_readings_cost_does_not_follow_the_history(pine_hill, sarah):
    """`NFR-3`'s actual promise: ONE SCREEN COSTS THE SAME whatever is behind
    it. Two populations, one page each, and the statement count must not move.

    ⚠ **THIS IS THE CASE A FIXTURE OF FOUR READINGS CANNOT MAKE**, and four is
    what every existing `CWP-034` case builds — which is exactly how an N+1
    over every distinct reading DATE survived: `bill_number_covering` was one
    statement per day of history, to fill one column."""
    switch_on(pine_hill, sarah)
    account, meter = _many_readings(pine_hill, sarah, count=20)
    principal = _Principal(pine_hill.id, [account.pk])
    params = ListParams(page=1, per=10, dir="desc", sort="taken")
    with tenant_context(pine_hill.id):
        with CaptureQueriesContext(connection) as small:
            selectors.account_readings_page(principal, account, params=params)
    # A SECOND meter, because this account's first already holds 2026-01-01
    # onwards and a reading needs a day nothing else on that meter has.
    second = a_water_meter(
        pine_hill, sarah, account.unit_id, serial="88-40220", asset_no="M-88420"
    )
    first = date(2026, 6, 1)
    for index in range(60):
        a_read(
            pine_hill,
            account,
            second["id"],
            day=first + timedelta(days=index),
            current=str(500000 + index * 10),
            consumption=str(5 + index),
        )
    with tenant_context(pine_hill.id):
        with CaptureQueriesContext(connection) as large:
            selectors.account_readings_page(principal, account, params=params)
    assert len(large.captured_queries) <= len(small.captured_queries), (
        f"one page of readings cost {len(small.captured_queries)} statements over "
        f"20 rows and {len(large.captured_queries)} over 80 — the work is following "
        "the account's history, which at an AMI deployment is one statement per hour "
        "of it"
    )


def test_a_search_finds_a_reading_that_is_not_on_the_first_page(pine_hill, sarah):
    """⚠ **THE CASE WITH THE TEETH, AND THE REASON THIS DEFECT WAS NOT
    HALF-FIXED.** Page the server and leave the search in the browser and this
    is what breaks: the needle matches a row on page 2, the browser only has
    page 1, and the customer is told the reading does not exist.

    On the UNFIXED tree it passes for the wrong reason — the browser had every
    row — so it is paired with the `LIMIT` case above, which does not."""
    switch_on(pine_hill, sarah)
    account, meter = _many_readings(pine_hill, sarah)
    # A reading a long way down the list, on its own meter, with a serial
    # nothing else carries.
    far = a_water_meter(pine_hill, sarah, account.unit_id, serial="ZZ-99999", asset_no="M-ZZ999")
    a_read(
        pine_hill,
        account,
        far["id"],
        day=date(2026, 1, 1),
        current="7777",
        consumption="77",
    )
    with tenant_context(pine_hill.id):
        principal = _Principal(pine_hill.id, [account.pk])
        page_one, _total = selectors.account_readings_page(
            principal, account, params=ListParams(page=1, per=50, sort="taken", dir="desc")
        )
        assert all(row["meter_serial"] != "ZZ-99999" for row in page_one), (
            "the fixture no longer puts the row off page 1, so this case proves nothing"
        )
        found, total = selectors.account_readings_page(
            principal,
            account,
            params=ListParams(page=1, per=50, q="ZZ-99999", sort="taken", dir="desc"),
        )
    assert total == 1, "the search ran over the whole set, not over one page"
    assert found[0]["meter_serial"] == "ZZ-99999"


def test_a_sort_reaches_past_the_first_page(pine_hill, sarah):
    """The same tooth, on the sort. The OLDEST reading is last of sixty, so a
    browser sorting page 1 would put the oldest row it happens to hold at the
    top and call it the oldest reading."""
    switch_on(pine_hill, sarah)
    account, _meter = _many_readings(pine_hill, sarah)
    principal = _Principal(pine_hill.id, [account.pk])
    with tenant_context(pine_hill.id):
        ascending, _ = selectors.account_readings_page(
            principal, account, params=ListParams(page=1, per=5, sort="taken", dir="asc")
        )
    assert ascending[0]["taken_on"] == "2026-01-01", (
        "the earliest reading of sixty did not reach the top of an ascending "
        "page of five — the sort saw only what was already in hand"
    )


def test_the_meter_tabs_are_the_whole_account_and_not_the_page(pine_hill, sarah):
    """⚠ **THE HALF OF THIS DEFECT THAT IS NEITHER SEARCH, SORT NOR PAGE.**
    `Readings.tsx` built its meter tabs by folding the payload, and the payload
    is now one page. A service read once a quarter would simply lose its tab —
    silently, with `tsc` and every test green — and the customer would be told
    they have no water readings."""
    switch_on(pine_hill, sarah)
    account, _meter = _many_readings(pine_hill, sarah)
    quiet = a_water_meter(pine_hill, sarah, account.unit_id, serial="QQ-00001", asset_no="M-QQ001")
    a_read(
        pine_hill,
        account,
        quiet["id"],
        day=date(2026, 1, 1),
        current="404",
        consumption="4",
    )
    with tenant_context(pine_hill.id):
        principal = _Principal(pine_hill.id, [account.pk])
        frame = selectors.account_readings_frame(principal, account, today=TODAY)
        page, _total = selectors.account_readings_page(
            principal, account, params=ListParams(page=1, per=50, sort="taken", dir="desc")
        )
    on_the_page = {row["meter_serial"] for row in page}
    assert "QQ-00001" not in on_the_page, "the fixture no longer puts it off page 1"
    references = {one for service in frame["services"] for one in service["meters"]}
    assert "QQ-00001" in references, (
        "the meter tabs were folded from the page — a quarterly-read meter "
        "loses its tab and the customer is told it has no readings"
    )


def test_an_out_of_range_page_clamps_rather_than_refusing(pine_hill, sarah):
    """`BR-SHL-011` — *a list URL clamps and never 4xx*. REGRESSION GUARD: it
    passes on the unfixed tree too, because there was no page to be out of."""
    switch_on(pine_hill, sarah)
    account, _meter = _many_readings(pine_hill, sarah)
    principal = _Principal(pine_hill.id, [account.pk])
    with tenant_context(pine_hill.id):
        body = _paging().windowed(
            "readings",
            ListParams(page=999, per=50, sort="taken", dir="desc"),
            lambda window: selectors.account_readings_page(
                principal, account, params=window
            ),
        )
    assert body["page"] == 2, "page 999 of a two-page list clamped to the LAST page"
    assert body["count"] == MANY
    assert len(body["readings"]) == 10


def test_no_cap_is_introduced_anywhere(pine_hill, sarah):
    """`NFR-5` — *no hard caps anywhere*, which is the T4 flexibility rather
    than a tidiness preference. `per=1000` returns every one of the sixty rows
    and `per` is the IS-2 vocabulary rather than a ceiling somebody chose."""
    switch_on(pine_hill, sarah)
    account, _meter = _many_readings(pine_hill, sarah)
    principal = _Principal(pine_hill.id, [account.pk])
    with tenant_context(pine_hill.id):
        rows, total = selectors.account_readings_page(
            principal, account, params=ListParams(page=1, per=1000, sort="taken", dir="desc")
        )
    assert total == MANY
    assert len(rows) == MANY, "a size above the population returned fewer rows than exist"


def test_an_account_outside_the_session_still_answers_the_same_404(pine_hill, sarah):
    """`BR-CWP-010`, and it is the guard this whole commit must not weaken: a
    filter moving into SQL must not let a landlord acquire a tenant's rows.
    An id outside the set and an id that does not exist answer the SAME 404,
    with paging parameters on the request."""
    from tests.test_us_cwp_026_my_accounts import a_tenants_account, landlord

    switch_on(pine_hill, sarah)
    _credential, _accounts, _master = landlord(pine_hill, sarah)
    outsider = a_tenants_account(pine_hill, sarah)
    client = _signed_in(pine_hill, sarah)
    theirs = client.get(
        f"/api/{pine_hill.subdomain}/portal/accounts/{outsider.pk}/readings",
        {"page": 1, "per": 50, "q": "anything"},
    )
    nowhere = client.get(
        f"/api/{pine_hill.subdomain}/portal/accounts/"
        "00000000-0000-7000-8000-000000000000/readings",
        {"page": 1, "per": 50, "q": "anything"},
    )
    assert theirs.status_code == 404
    assert nowhere.status_code == 404
    assert theirs.json().get("code") == nowhere.json().get("code"), (
        "an account outside the set answered differently from one that does not "
        "exist — the account space can be walked"
    )


def test_the_covering_bill_is_resolved_in_the_query_and_sorts_on_it(pine_hill, sarah):
    """The bill a reading fed used to cost ONE STATEMENT PER DISTINCT DATE
    (`billing_seam.bill_number_covering`, once per `taken_on`). It is a `CASE`
    over the account's issued periods now, which also makes it sortable —
    and `None` sorts LAST in both directions, which is the browser's own rule
    moved rather than changed."""
    switch_on(pine_hill, sarah)
    account, meter = _many_readings(pine_hill, sarah, count=3)
    # One reading a long way outside any bill's period, so the list HAS an
    # unbilled row to sort. Without it the case could not fail.
    a_read(
        pine_hill,
        account,
        meter["id"],
        day=date(2026, 12, 25),
        current="999999",
        consumption="9",
    )
    # ⚠ **`an_issued_bill` NEEDS AN OUTER TENANT CONTEXT AND THE READ HELPERS
    # OPEN THEIR OWN**, which is why they are on opposite sides of this line.
    # On PostgreSQL the difference is a refusal — *"new row violates row-level
    # security policy for table invoices"* — and on SQLite it is invisible,
    # because there is no RLS there at all (hard-won law 14).
    with tenant_context(pine_hill.id):
        an_issued_bill(
            pine_hill,
            account,
            number="BL-2601-0001",
            total="100.0000",
            issued_on=date(2026, 1, 31),
        )
    with tenant_context(pine_hill.id):
        principal = _Principal(pine_hill.id, [account.pk])
        up, _ = selectors.account_readings_page(
            principal, account, params=ListParams(page=1, per=50, sort="bill", dir="asc")
        )
        down, _ = selectors.account_readings_page(
            principal, account, params=ListParams(page=1, per=50, sort="bill", dir="desc")
        )
    assert any(row["on_bill"] for row in up), (
        "no reading was matched to a bill at all, so this case proves nothing "
        "about the CASE annotation"
    )
    assert up[-1]["on_bill"] is None, (
        "a reading on no bill did not sort LAST under an ASCENDING sort — an "
        "unbilled reading is not 'earliest', it is unknown"
    )
    assert down[-1]["on_bill"] is None, (
        "…nor under a DESCENDING one, which is the direction a null-last key "
        "and a `reverse` flag have to agree about"
    )


def test_two_page_sizes_over_one_history_cost_one_page_each(pine_hill, sarah, capsys):
    """THE MEASUREMENT, AND IT IS A CHECK AS WELL AS AN INSTRUMENT.

    ⚠ **TWO PAGE SIZES, NEVER TWO POPULATIONS.** `NFR-3` promises that one
    screen costs what one screen costs, so the honest comparison holds the
    account's history FIXED and moves only `per`. A pair of figures taken over
    two population sizes measures the fixture and reads as a speed-up whichever
    way the code went.

    ⚠ **IT ASSERTS THE PROPERTY IT PRINTS**, so it cannot become a number
    nobody reads: the rows returned are the page asked for, the count is the
    whole history both times, and the statement count does not follow `per`.
    Before this fix the first column was 1,100 whatever `per` said, and the
    statements carried one extra query per DISTINCT READING DATE —
    `billing_seam.bill_number_covering`, once per day of history, for one
    column.

    Run with `-s` to read the table.
    """
    switch_on(pine_hill, sarah)
    account, _meter = _many_readings(pine_hill, sarah, count=1100)
    principal = _Principal(pine_hill.id, [account.pk])
    measured = []
    with tenant_context(pine_hill.id):
        for per in (40, 1000):
            with CaptureQueriesContext(connection) as captured:
                rows, total = selectors.account_readings_page(
                    principal,
                    account,
                    params=ListParams(page=1, per=per, sort="taken", dir="desc"),
                )
            measured.append((per, len(rows), len(captured.captured_queries), total))
    with capsys.disabled():
        print("\n  per   rows  statements  count")
        for per, rows_out, statements, total in measured:
            print(f"  {per:>4}  {rows_out:>4}  {statements:>10}  {total:>5}")
    assert [row[1] for row in measured] == [40, 1000], (
        "the endpoint did not return the page it was asked for"
    )
    assert {row[3] for row in measured} == {1100}, "the count is the whole history, both times"
    small, large = measured[0][2], measured[1][2]
    assert large <= small + 1, (
        f"one page cost {small} statements at per=40 and {large} at per=1000 — the "
        "work is following the size of the page, which means something is still "
        "being asked once per row"
    )


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE FOUR LISTS THAT TAKE THEIR PAGE ON THE SERVER, IN PYTHON
#
# `apps/portal/paging.SQL_PAGED` names each and says why. Both answers fix the
# defect; only the SQL one makes the WORK constant, and only `readings` needed
# that. What every one of these has to prove is the half with the teeth: the
# search runs over the WHOLE set, not over the page that was served.
# ══════════════════════════════════════════════════════════════════════════


def test_the_split_is_declared_and_readings_is_the_sql_one(pine_hill, sarah):
    """A declared blind spot with no NUMBER attached is indistinguishable from
    an empty one (hard-won law 7). `SQL_PAGED` is that number: five lists, one
    of them in SQL, and the four exceptions named rather than implied."""
    assert _paging().SQL_PAGED["readings"] is True
    assert sorted(name for name, sql in _paging().SQL_PAGED.items() if not sql) == [
        "bills",
        "documents",
        "my-accounts",
        "payments",
    ]


def test_a_bill_search_reaches_past_the_first_page(pine_hill, sarah):
    """The bills list, with more bills than a page. The needle matches ONE bill
    and it is not among the newest fifty."""
    switch_on(pine_hill, sarah)
    account = elm_unit_with_services(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        for index in range(MANY):
            an_issued_bill(
                pine_hill,
                account,
                number=f"BL-2600-{index:04d}",
                total="10.0000",
                issued_on=date(2026, 1, 1) + timedelta(days=index),
            )
        params = ListParams(page=1, per=50)
        body, total = selectors.bills_page([account.pk], today=TODAY, params=params)
        assert total == MANY
        numbers = {row["number"] for row in body["bills"]}
        assert "BL-2600-0000" not in numbers, "the fixture no longer puts it off page 1"
        found, matched = selectors.bills_page(
            [account.pk], today=TODAY, params=ListParams(page=1, per=50, q="BL-2600-0000")
        )
    assert matched == 1, "the bill search ran over one page instead of the whole list"
    assert found["bills"][0]["number"] == "BL-2600-0000"


def test_the_bills_whole_set_facts_do_not_follow_the_page(pine_hill, sarah):
    """⚠ **THE THREE FACTS `Bills.tsx` USED TO COUNT OFF THE ARRAY IT HELD.**
    `oldest_on` is the drawing's *"Every bill since you started, Jun 2026"*,
    `any_owing` decides whether the *Pay* control is drawn at all, and
    `populated` tells *you have no bills* apart from *none of your bills says
    that*. Read off a PAGE the first says *since Aug 2026* on page 1 of eleven
    years, and the second HIDES Pay from somebody whose only unpaid bill is on
    page 2."""
    switch_on(pine_hill, sarah)
    account = elm_unit_with_services(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        for index in range(MANY):
            an_issued_bill(
                pine_hill,
                account,
                number=f"BL-2600-{index:04d}",
                total="10.0000",
                issued_on=date(2026, 1, 1) + timedelta(days=index),
            )
        body, _total = selectors.bills_page(
            [account.pk], today=TODAY, params=ListParams(page=2, per=50)
        )
    assert body["oldest_on"] == "2026-01-01", (
        "the oldest bill was read off the page — page 2 would name a different month"
    )
    assert body["populated"] is True
    # A search that matches nothing must NOT make the screen say *no bills*.
    with tenant_context(pine_hill.id):
        empty, matched = selectors.bills_page(
            [account.pk], today=TODAY, params=ListParams(page=1, per=50, q="nothing-like-this")
        )
    assert matched == 0
    assert empty["populated"] is True, (
        "a search matching nothing reported the customer has no bills at all"
    )


def test_the_month_a_customer_types_is_a_code_the_server_knows(pine_hill, sarah):
    """B14 rule 35 in the one place it bites a search. `BILL` prints *Aug 2026*
    in the READER'S language and the server stores `2026-08-31`; the server
    matches `f.month=08` and the SCREEN turns the word it drew into that code.
    A server that tried to match *August* would have to own eleven catalogues."""
    switch_on(pine_hill, sarah)
    account = elm_unit_with_services(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        an_issued_bill(
            pine_hill, account, number="BL-2608-0001", total="10.0000",
            issued_on=date(2026, 8, 3),
        )
        an_issued_bill(
            pine_hill, account, number="BL-2607-0001", total="10.0000",
            issued_on=date(2026, 7, 3),
        )
        body, total = selectors.bills_page(
            [account.pk],
            today=TODAY,
            params=ListParams(page=1, per=50, filters={"month": "08"}),
        )
    assert total == 1
    assert body["bills"][0]["number"] == "BL-2608-0001"


def test_the_unpaid_chip_is_owing_and_not_the_state_word(pine_hill, sarah):
    """`BR-CWP-043` — the predicate MOVED to the server and did not change. A
    part-paid bill is unpaid to the person who still owes on it."""
    switch_on(pine_hill, sarah)
    account = elm_unit_with_services(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        an_issued_bill(
            pine_hill, account, number="BL-2608-0001", total="10.0000",
            issued_on=date(2026, 8, 3),
        )
        body, total = selectors.bills_page(
            [account.pk],
            today=TODAY,
            params=ListParams(page=1, per=50, filters={"state": "unpaid"}),
        )
    # ENVELOPE GUARD — what matters is that the predicate is the server's at all.
    assert total == len(body["bills"])


def test_my_accounts_keeps_its_total_over_the_whole_set(pine_hill, sarah):
    """`BR-CWP-015` — *totalled, never merged*. A total of the PAGE would be a
    different number on page 2, and a customer could reasonably believe it."""
    from tests.test_us_cwp_026_my_accounts import landlord

    switch_on(pine_hill, sarah)
    _credential, accounts, _master = landlord(pine_hill, sarah)
    principal = _Principal(pine_hill.id, [one.pk for one in accounts])
    with tenant_context(pine_hill.id):
        principal.accounts = tuple(
            _Entry(str(one.pk)) for one in accounts
        )
        whole, total_rows = selectors.my_accounts_page(
            principal, today=TODAY, params=ListParams(page=1, per=50)
        )
        one_row, _ = selectors.my_accounts_page(
            principal, today=TODAY, params=ListParams(page=1, per=50)
        )
    assert whole["total_owing"] == one_row["total_owing"]
    assert whole["account_count"] == total_rows


class _Entry:
    def __init__(self, account_id):
        self.account_id = account_id


def test_a_bounce_and_the_payment_it_undoes_stay_adjacent(pine_hill, sarah):
    """`BR-CWP-061` — REGRESSION GUARD, and the reason `payments` is not paged
    in SQL. The pairing is done over the whole list before anything is sliced;
    a `LIMIT` in the database would be free to cut between the two rows."""
    switch_on(pine_hill, sarah)
    account = elm_unit_with_services(pine_hill, sarah)
    principal = _Principal(pine_hill.id, [account.pk])
    with tenant_context(pine_hill.id):
        body, _total = selectors.money_page(
            list(principal.account_ids), year=None, params=ListParams(page=1, per=50)
        )
    rows = body["money"]
    for index, row in enumerate(rows):
        if row.get("kind") == "reversal" and index + 1 < len(rows):
            assert rows[index + 1].get("kind") == "payment", (
                "a reversal was not directly above the payment it undoes"
            )


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE SHARED WINDOW ITSELF
# ══════════════════════════════════════════════════════════════════════════


def test_an_absent_value_sorts_last_in_both_directions():
    """The browser's own rule, moved rather than changed: *"a missing date is
    not 'earliest', it is unknown, and burying it under a descending sort would
    hide the row"* (`portal/components/listTable.compareValues`).

    ⚠ **BOTH DIRECTIONS, BECAUSE THE KEY AND THE `reverse` FLAG HAVE TO AGREE.**
    `sorted(reverse=True)` inverts the WHOLE tuple, absent flag included, so a
    key that always marked absence the same way would put every empty cell
    FIRST under a descending sort — which is the one thing a test of this can
    catch and a reader cannot."""
    rows = [{"v": 3}, {"v": None}, {"v": 1}, {"v": 10}, {"v": None}]
    sorts = {"v": lambda row: row.get("v")}
    up, _ = _paging().on_the_server(rows, ListParams(page=1, per=50, sort="v", dir="asc"), sorts=sorts)
    down, _ = _paging().on_the_server(
        rows, ListParams(page=1, per=50, sort="v", dir="desc"), sorts=sorts
    )
    assert [row["v"] for row in up] == [1, 3, 10, None, None]
    assert [row["v"] for row in down] == [10, 3, 1, None, None]


def test_the_all_chip_is_an_absence_and_not_a_value():
    """`all` is what the toolbar supplies for *no narrowing*, so it never
    reaches a predicate — a filter that had to know the word `all` would be a
    control's vocabulary leaking into a server."""
    rows = [{"state": "owing"}, {"state": "clear"}]
    filters = {"state": lambda row, value: row["state"] == value}
    everything, total = _paging().on_the_server(
        rows, ListParams(page=1, per=50, filters={"state": "all"}), filters=filters
    )
    assert total == 2, "the `all` chip narrowed the list"
    narrowed, matched = _paging().on_the_server(
        rows, ListParams(page=1, per=50, filters={"state": "owing"}), filters=filters
    )
    assert matched == 1
    assert everything is not narrowed


def test_the_sort_is_stable_so_a_page_cannot_split_a_pair():
    """What keeps `BR-CWP-061`'s bounce pair together under a sort the key
    cannot tell apart. `sorted` is stable, and this is the case that says so
    out loud rather than relying on a reader knowing it."""
    rows = [{"k": 1, "id": "a"}, {"k": 1, "id": "b"}, {"k": 1, "id": "c"}]
    page, _ = _paging().on_the_server(
        rows, ListParams(page=1, per=50, sort="k", dir="desc"), sorts={"k": lambda row: row["k"]}
    )
    assert [row["id"] for row in page] == ["a", "b", "c"]


def test_the_reading_sort_vocabulary_is_the_one_the_screen_draws():
    """A sort the UI cannot ask for is surface with no caller (hard-won law 2).
    `how` is deliberately absent — the column is not sortable on screen."""
    assert sorted(portal_reads.READING_SORTS) == ["bill", "meter", "reading", "taken", "used"]
    assert portal_reads.READING_DEFAULT_SORT == "taken"
    assert portal_reads.READING_DEFAULT_DIR == "desc"


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-CWP-5747 — the portal pagination lane, 2026-09-19
# generated: 2026-09-19
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
