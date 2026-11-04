# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-LED-6493 — `GET /ledger/journal-entries` built EVERY journal
#          entry the tenant holds in order to draw fifty, because
#          `apps/ledger/api.py` handed DRF `list(result["rows"])`. Filed by this
#          lane BEFORE it was fixed (CLAUDE.md step W).
# Task:    Finance blueprint `P1.8` (SQL pagination) · `P1.10` (proved at
#          volume) · `P1.18` (Entry no. sorts by DATE, never by the rendered
#          string) — 05-prototype/07 Finance Blueprint.pdf p013, p020, p021
# Rules:   NFR-3 (universal server pagination) · NFR-5 (no hard caps anywhere) ·
#          BR-SHL-011 (a list URL clamps and never 4xx) · BR-LED-012 (the
#          journal list) · BR-LED-021 / BR-TEN-035 (the `JE-` series) · hard
#          rule 1 (tenant scoping) · hard rule 4 (a posted entry is immutable —
#          nothing here writes)
# Tests:   this file
# Impacts: 06-backend/apps/ledger/reporting.py (`journal_entry_list` gains
#          `offset`/`limit`/`sort`/`direction` and returns `total`) ·
#          06-backend/apps/ledger/api.py (the view asks for ONE page) ·
#          06-backend/core/pagination.py (`prepaged`, the envelope's stated home)
# ───────────────────────────────────────────────────────
"""DEF-LED-6493 — the journal takes its page in the DATABASE, and sorts by DATE.

RED-FIRST PROOF (hard-won law 7, in the harness that runs it — `pytest`, never a
`__main__`). Every case below was run against this worktree BEFORE the fix, and
the failures are quoted in the lane report. Three carry the defect:

  * `test_the_endpoint_asks_the_database_for_one_page` — *"GET
    /ledger/journal-entries sent no `LIMIT 50`; the page was taken in Python"*.
    It is aimed at the VIEW and not at the read model on purpose, so it can fail
    on a tree where the new keyword does not exist yet. A case calling
    `reporting.journal_entry_list(limit=50)` would only ever fail with
    `TypeError`, which proves a parameter was added and nothing at all about
    where the page is taken.
  * `test_the_statement_count_does_not_follow_the_book` — the measured counts.
  * `test_entry_no_sorts_by_date_and_never_by_the_rendered_string` — `?sort=number`
    was not accepted at all, so the column the drawing draws with a `⇅` could
    not be sorted; and the moment it is, the obvious implementation is
    `order_by("number")`, which is WRONG by eleven months.

⚠ **A CASE THAT COUNTS RETURNED ROWS CANNOT TELL SQL PAGING FROM PYTHON PAGING**
and would have passed, green, through the whole life of this defect: DRF sliced
the built list to exactly fifty rows and served a correct `count`, a correct
`next` and the correct entries. Everything about the ANSWER was right. So every
case here asserts the SQL that was sent, or the number of statements it took.

⚠ **AND THE COUNT CASE SAYS *THE COST DID NOT MOVE*, NEVER A LITERAL** (the form
`test_def_cus_5753_customers_list_pages_in_sql.py` argues for). An equality
against a number goes red the day an unrelated lane adds a `select_related`,
which teaches the next reader to edit the number instead of looking at it. What
`NFR-3` promises is that one screen costs the same whatever the book's size, so
the case builds a SECOND, larger population and asserts the count did not follow
it.

⚠ **WHY THE SORT CASE IS HERE AND NOT IN A FILE OF ITS OWN.** `P1.18`'s whole
content is *"a later lane simplifying this to a string sort would silently
reorder the journal"*, and the only place a string sort could be introduced is
the ordering this fix rewrites. A guard living next to the thing it guards is
read by the person changing it.

⚠ **`JE-011526-0001` PRECEDES `JE-020325-0001` AS TEXT AND FOLLOWS IT BY ELEVEN
MONTHS.** The PO ruled the `JE-{MM}{DD}{YY}-{0000}` format on 2026-09-23 knowing
this (*"you need je-MMDDYY- nnnn like this otherwise it will not work"*), so the
format is not the defect — sorting by it would be.

Run with `JOBS_EAGER=false` (DEF-567). The SQL cases are meaningful on either
backend; the isolation case wants PostgreSQL (`--ds=config.settings.pgtest`),
because SQLite has no row-level security.
"""

import re
from datetime import date
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.ledger import api as ledger_api
from apps.ledger import models as ledger_models
from apps.ledger import reporting
from core.pagination import DEFAULT_PAGE_SIZE

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    erin,
    lonestar,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

PAGE = DEFAULT_PAGE_SIZE  # 50 — IS-2's smallest page, the one a screen opens on
ENVELOPE = {"count", "next", "previous", "results"}


# ══════════════════════════════════════════════════════════════════════════
# Fixture — entries that HOLD lines, because a bare entry hides the bug
# ══════════════════════════════════════════════════════════════════════════
def _open_write_window() -> None:
    """`ledger/0004`'s sole-writer window, opened for a READ-PATH fixture.

    See `plant_entries` for why this is not a bypass of CLAUDE.md rule 5. It is
    a no-op on SQLite, which has no trigger and therefore no window."""
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.ledger_posting', 'on', true)")


def plant_entries(
    tenant, *, entries: int, tag: str, lines_each: int = 2, currency: str = "USD"
) -> int:
    """`entries` POSTED journal entries, each carrying `lines_each` real lines.

    ⚠ **A PAGE OF BARE ENTRIES WOULD HIDE THE HALF THAT COSTS MOST.** The read
    model sums each entry's lines to produce the `debit` and `credit` columns,
    and it does that over `journal_entry__in=entries` — the WHOLE filtered set.
    Plant entries with no lines and that pass reads nothing, so the second query
    could stay unbounded and the case would still go green.

    Written straight through the ORM rather than through `posting.post()`, which
    is deliberate and is the ONE thing in this file that is not the product's
    own path: twenty thousand real postings is a suite nobody runs, and what is
    under test is the READ. Nothing here asserts a money figure — the money
    cases live in `tests/test_us_led_ledger_api.py` over LE-1's real postings.

    ⚠ **AND THE WRITE WINDOW HAS TO BE OPENED BY HAND, WHICH IS HARD-WON LAW 14
    IN ITS PUREST FORM AND IS WHY THIS PARAGRAPH EXISTS.** `ledger/0004` puts a
    `BEFORE INSERT` trigger on `journal_entries` and `journal_lines` that refuses
    any row not written inside `app.ledger_posting = 'on'` (CLAUDE.md rule 5:
    only the posting service writes the books). **SQLite has no trigger**, so
    the first version of this fixture worked perfectly on the default suite and
    was refused outright on PostgreSQL with
    `psycopg.errors.RaiseException: CLAUDE.md rule 5: journal_entries is written
    ONLY by the ledger posting service` — a fixture that was *incapable of
    passing* on the only tier where the guarantee exists, which is exactly the
    shape law 7 names. It was found by running this file under
    `--ds=config.settings.pgtest` and by nothing else.

    Opening the window here is legitimate and is not a bypass of rule 5: this
    seeds READ-PATH VOLUME and asserts nothing about money. The window is
    transaction-local (`set_config(..., true)`), so it shuts itself.

    ⚠ **AND THE ENTRIES ARE BORN AS DRAFTS AND MOVED TO POSTED AFTER THEIR LINES
    EXIST, WHICH IS THE SECOND THING PostgreSQL REFUSED AND SQLITE ALLOWED.**
    A first version created them already `posted` and then inserted their lines;
    `ledger/0002`'s immutability trigger refused every line with *"hard rule 4 /
    BR-LED-003: journal entry … is POSTED — its lines are frozen"*. That is the
    database enforcing exactly what `CLAUDE.md` rule 4 says and the product's
    own post path already does — lines first, status last — so the fixture
    follows the product rather than working around the trigger.

    Dates march BACKWARDS from 2026-08-02 one day at a time, so the set spans
    months and a date sort has something to be wrong about.
    """
    _open_write_window()
    account = ledger_models.LedgerAccount.objects.filter(tenant=tenant).first()
    assert account is not None, "the tenant has no chart seeded"
    made = []
    for index in range(entries):
        made.append(
            ledger_models.JournalEntry(
                tenant=tenant,
                entry_date=date.fromordinal(date(2026, 8, 2).toordinal() - index),
                type=ledger_models.JE_STANDARD,
                status=ledger_models.JE_DRAFT,
                currency=currency,
                memo=f"Bill run {tag}-{index:05d}",
                source_type="invoice",
                posting_key=f"{tag}-{index:05d}",
            )
        )
    ledger_models.JournalEntry.objects.bulk_create(made)
    lines = []
    for entry in made:
        for seat in range(lines_each):
            lines.append(
                ledger_models.JournalLine(
                    tenant=tenant,
                    journal_entry=entry,
                    ledger_account=account,
                    side=(
                        ledger_models.SIDE_DEBIT
                        if seat % 2 == 0
                        else ledger_models.SIDE_CREDIT
                    ),
                    amount=Decimal("15066.0000"),
                )
            )
    ledger_models.JournalLine.objects.bulk_create(lines)
    # draft → posted, which is the transition `posting.post_draft` makes and the
    # only one the immutability trigger permits.
    ledger_models.JournalEntry.objects.filter(
        tenant=tenant, pk__in=[row.pk for row in made]
    ).update(status=ledger_models.JE_POSTED)
    return entries


def _factory():
    from rest_framework.test import APIRequestFactory

    return APIRequestFactory()


def _request(tenant, actor, **params):
    """A real DRF request for the VIEW, not a call to the read model under it.

    ⚠ **THE VIEW IS THE THING UNDER TEST IN THE SQL CASE.** The defect was in
    what `api.journal_entries` did with the read model's answer, and a case
    calling the read model directly would pass identically whether the ROUTE
    reaches it or still builds the whole book.
    """
    from rest_framework.test import force_authenticate

    request = _factory().get("/api/brazosbend/ledger/journal-entries", params)
    force_authenticate(request, user=actor.user)
    request.tenant_role = "system_admin"
    request.tenant_id = tenant.id
    return request


def _limit(queries, size: int):
    """The captured statements that take exactly `size` rows — the page, in SQL.

    ⚠ **`LIMIT 50` AND NOT `LIMIT`**, the false pass `DEF-RAT-5742` had to design
    itself out of: Django renders a `Subquery(...[:1])` as `LIMIT 1` inside a
    SELECT list, so a check for the bare word can go green on code that never
    asked the database for a page at all.
    """
    return [q for q in queries if re.search(rf"\bLIMIT\s+{size}\b", q["sql"], re.I)]


def _counts(queries):
    return [q for q in queries if re.search(r"\bCOUNT\(", q["sql"], re.I)]


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE PAGE IS TAKEN IN SQL — the case that goes red on the old code
# ══════════════════════════════════════════════════════════════════════════
def test_the_endpoint_asks_the_database_for_one_page(brazos, dana):
    """`NFR-3` — fifty rows cost fifty rows' work, whatever the book holds."""
    with tenant_ctx(brazos):
        plant_entries(brazos, entries=120, tag="A")
        with CaptureQueriesContext(connection) as captured:
            response = ledger_api.journal_entries(_request(brazos, dana))
        assert response.status_code == 200
        assert len(response.data["results"]) == PAGE
        assert response.data["count"] == 120

        statements = list(captured.captured_queries)
        assert _limit(statements, PAGE), (
            "GET /ledger/journal-entries sent no `LIMIT 50`; the page was taken "
            "in Python over a list the read model had already built in full"
        )
        assert _counts(statements), (
            "no COUNT(*) was sent — the envelope's `count` was `len()` over a "
            "list that had to exist first"
        )


def test_the_statement_count_does_not_follow_the_book(brazos, dana):
    """`NFR-3` — the COST of one screen does not grow with the tenant.

    The assertion is a COMPARISON and never a literal: a number would go red the
    day an unrelated lane adds a `select_related`, and the next reader would edit
    the number rather than look at it.
    """
    with tenant_ctx(brazos):
        plant_entries(brazos, entries=60, tag="B")
        with CaptureQueriesContext(connection) as small:
            ledger_api.journal_entries(_request(brazos, dana))
        small_count = len(small.captured_queries)

        plant_entries(brazos, entries=240, tag="C")
        with CaptureQueriesContext(connection) as large:
            ledger_api.journal_entries(_request(brazos, dana))
        large_count = len(large.captured_queries)

    assert large_count <= small_count, (
        f"the journal cost {small_count} statements over 60 entries and "
        f"{large_count} over 300 — the work follows the book, which at the top "
        f"of T5 is 40,000 entries built to draw fifty"
    )


def test_the_second_page_asks_for_the_second_page(brazos, dana):
    """`?page=2` is an OFFSET in SQL, not a slice of a built list."""
    with tenant_ctx(brazos):
        plant_entries(brazos, entries=120, tag="D")
        with CaptureQueriesContext(connection) as captured:
            response = ledger_api.journal_entries(_request(brazos, dana, page="2"))
        assert len(response.data["results"]) == PAGE
        offsets = [
            q
            for q in captured.captured_queries
            if re.search(r"\bOFFSET\s+50\b", q["sql"], re.I)
        ]
        assert offsets, "page 2 sent no `OFFSET 50` — it sliced a built list"


def test_a_larger_page_size_reaches_the_database(brazos, dana):
    """`per=100` is IS-2 vocabulary and must reach SQL, not a Python slice."""
    with tenant_ctx(brazos):
        plant_entries(brazos, entries=150, tag="E")
        with CaptureQueriesContext(connection) as captured:
            response = ledger_api.journal_entries(_request(brazos, dana, per="100"))
        assert len(response.data["results"]) == 100
        assert _limit(captured.captured_queries, 100), "`per=100` sent no LIMIT 100"


# ══════════════════════════════════════════════════════════════════════════
# 2 · P1.18 — THE ENTRY NUMBER SORTS BY DATE
# ══════════════════════════════════════════════════════════════════════════
def test_entry_no_sorts_by_date_and_never_by_the_rendered_string(brazos, dana):
    """`P1.18` — `JE-011526-0001` precedes `JE-020325-0001` as TEXT and follows
    it by eleven months.

    The drawing (p020 item 6) puts a `⇅` on the ENTRY NO. column, so a clerk CAN
    sort by it. `MMDDYY` does not sort chronologically as a string, and the PO
    ruled that format knowing so. **This case is the thing that stops a later
    lane "simplifying" the ordering to `order_by("number")`.**
    """
    with tenant_ctx(brazos):
        _open_write_window()
        account = ledger_models.LedgerAccount.objects.filter(tenant=brazos).first()
        # January 2026 gets the number that sorts FIRST as text; February gets
        # the one that sorts SECOND. Chronologically January comes first too, so
        # ASCENDING cannot tell the two orderings apart — it is DESCENDING that
        # separates them, which is why the assertion below is on `desc`.
        for key, day, number in (
            ("jan", date(2026, 1, 15), "JE-011526-0001"),
            ("feb", date(2026, 2, 3), "JE-020325-0001"),
        ):
            # Born a DRAFT, lined, then posted — the order `post_draft` uses and
            # the only one `ledger/0002`'s immutability trigger permits.
            entry = ledger_models.JournalEntry.objects.create(
                tenant=brazos,
                entry_date=day,
                type=ledger_models.JE_STANDARD,
                status=ledger_models.JE_DRAFT,
                currency="USD",
                number=number,
                memo=f"P1.18 {key}",
                source_type="manual_je",
                posting_key=f"p118-{key}",
            )
            ledger_models.JournalLine.objects.create(
                tenant=brazos,
                journal_entry=entry,
                ledger_account=account,
                side=ledger_models.SIDE_DEBIT,
                amount=Decimal("400.0000"),
            )
            ledger_models.JournalEntry.objects.filter(pk=entry.pk).update(
                status=ledger_models.JE_POSTED
            )

        newest_first = ledger_api.journal_entries(
            _request(brazos, dana, sort="number", dir="desc")
        ).data["results"]
        numbers = [row["je_number"] for row in newest_first if row["je_number"]]
        assert numbers[:2] == ["JE-020325-0001", "JE-011526-0001"], (
            "the journal ordered by the rendered string: `JE-011526-0001` came "
            "back as the NEWER entry, and it is eleven months older. The Entry "
            "no. column sorts by `entry_date`, never by `number` (P1.18)"
        )


def test_the_entry_number_column_is_offered_as_a_sort_at_all(brazos, dana):
    """The `⇅` the drawing puts on ENTRY NO. and DATE has to reach the server.

    `BR-SHL-011` says an unknown `sort` FALLS BACK and never errors, so an
    unsupported name cannot be told from a supported one by the status code.
    This asserts the vocabulary the read model declares instead.
    """
    assert "number" in reporting.JOURNAL_SORTS
    assert "entry_date" in reporting.JOURNAL_SORTS
    assert reporting.JOURNAL_DEFAULT_SORT == "entry_date"
    with tenant_ctx(brazos):
        plant_entries(brazos, entries=3, tag="F")
        body = ledger_api.journal_entries(
            _request(brazos, dana, sort="not-a-column")
        ).data
        assert body["count"] == 3, "an unknown sort must fall back, never 4xx"


def test_ascending_is_offered_and_is_the_opposite_of_descending(brazos, dana):
    """`dir=asc` reverses the list — the `⇅` cycles asc → desc → clear (p020)."""
    with tenant_ctx(brazos):
        plant_entries(brazos, entries=5, tag="G")
        oldest = ledger_api.journal_entries(
            _request(brazos, dana, sort="entry_date", dir="asc")
        ).data["results"]
        newest = ledger_api.journal_entries(
            _request(brazos, dana, sort="entry_date", dir="desc")
        ).data["results"]
        assert oldest[0]["entry_date"] < newest[0]["entry_date"]
        assert oldest[0]["entry_id"] == newest[-1]["entry_id"]


# ══════════════════════════════════════════════════════════════════════════
# 3 · REGRESSION GUARDS — they pass either way, and are labelled so
# ══════════════════════════════════════════════════════════════════════════
def test_the_envelope_did_not_change_shape(brazos, dana):
    """REGRESSION GUARD. `count`/`next`/`previous`/`results` plus the three keys
    this endpoint has always carried beside them. A second envelope shape would
    be a client-side special case for ever."""
    with tenant_ctx(brazos):
        plant_entries(brazos, entries=120, tag="H")
        body = ledger_api.journal_entries(_request(brazos, dana)).data
        assert ENVELOPE <= set(body)
        assert body["basis"] == "posting"
        assert "currency" in body and "unavailable" in body
        assert body["next"] and "page=2" in body["next"]
        assert body["previous"] is None


def test_an_out_of_range_page_clamps_and_never_errors(brazos, dana):
    """REGRESSION GUARD — `BR-SHL-011`: a list URL clamps, it does not 4xx, and
    it does not answer with a blank table and a `previous` link to page 998."""
    with tenant_ctx(brazos):
        plant_entries(brazos, entries=60, tag="I")
        body = ledger_api.journal_entries(_request(brazos, dana, page="999")).data
        assert body["count"] == 60
        assert len(body["results"]) == 10, "page 999 clamped to the LAST page"
        assert body["next"] is None


def test_the_reported_gaps_are_about_the_whole_book_not_the_page(brazos, dana):
    """`BR-LED-021` — `posted_entries_without_a_je_number` counts the FILTERED
    SET, not the fifty rows that happen to be on screen.

    ⚠ **THIS IS THE HALF A PAGING FIX BREAKS SILENTLY.** Page 1 of a 200-entry
    book would report the gap over fifty rows and page 4 over the last ten, so
    the same screen would state a different fact about the same book depending
    on which page a clerk stopped on.
    """
    with tenant_ctx(brazos):
        plant_entries(brazos, entries=120, tag="J")
        body = ledger_api.journal_entries(_request(brazos, dana)).data
        gap = next(
            row
            for row in body["unavailable"]
            if row["code"] == "posted_entries_without_a_je_number"
        )
        assert gap["entry_count"] == 120, (
            "the gap was counted over the PAGE: a clerk on page 1 and a clerk "
            "on page 3 would be told two different things about one book"
        )


def test_the_gap_does_not_put_forty_thousand_ids_on_the_wire(brazos, dana):
    """`NFR-3` again, one layer in: the gap's own `entry_ids` is BOUNDED, and
    the wire carries the COUNT rather than the list.

    An unbounded id list inside a bounded page is the same breach wearing the
    fix's clothes — at the top of T5 that is 40,000 UUIDs in a response that
    carries fifty rows.

    ⚠ **AND THE IDS NEVER REACHED A CLIENT ANYWAY — `DEF-LED-6521`, found by
    this case.** `wire.gap` serialises four NAMED keys while its docstring
    promised *"no field is dropped"*, so `entry_ids` has been on the read
    model's gap since the gap was written and on no response ever. It stays
    off the wire deliberately (hard-won law 2: nothing renders it) and the
    COUNT, which a screen CAN state in six words, is carried.
    """
    with tenant_ctx(brazos):
        plant_entries(brazos, entries=120, tag="K")
        result = reporting.journal_entry_list(offset=0, limit=PAGE)
        gap = next(
            row
            for row in result["unavailable"]
            if row["code"] == "posted_entries_without_a_je_number"
        )
        assert len(gap["entry_ids"]) <= reporting.GAP_ID_SAMPLE
        assert gap["entry_count"] == 120

        served = next(
            row
            for row in ledger_api.journal_entries(_request(brazos, dana)).data["unavailable"]
            if row["code"] == "posted_entries_without_a_je_number"
        )
        assert served["entry_count"] == 120
        assert "entry_ids" not in served


def test_the_currencies_banner_reads_the_whole_book(brazos, dana):
    """REGRESSION GUARD — `DEF-081`. The mixed-currency banner is a fact about
    the FILTERED SET. Derived from the page it would go quiet on page 2."""
    with tenant_ctx(brazos):
        plant_entries(brazos, entries=60, tag="L")
        # ⚠ **THE ODD ENTRY IS BORN IN CAD; ITS CURRENCY IS NEVER UPDATED.**
        # A first draft did `…filter(posting_key="L-00059").update(currency="CAD")`
        # and PostgreSQL refused it — *"journal entry … is POSTED and immutable"*
        # (hard rule 4, `ledger/0002`). SQLite has no such trigger and allowed
        # it, so the case was green on the default suite over a write the
        # product forbids. It is planted as row 60 of its own batch instead, so
        # it lands on PAGE 2 — which is the whole point: a banner derived from
        # page 1 would never see it.
        plant_entries(brazos, entries=1, tag="Lc", currency="CAD")
        result = reporting.journal_entry_list(offset=0, limit=PAGE)
        assert set(result["currencies"]) == {"CAD", "USD"}, (
            "the banner was derived from the page: the one CAD entry is row 60 "
            "and page 1 stops at 50"
        )


def test_the_whole_set_is_still_available_to_a_caller_that_wants_it(brazos, dana):
    """REGRESSION GUARD — eleven existing cases call `journal_entry_list()` with
    no page and read `rows` as the whole answer. Omitting `limit` must mean
    exactly what it has always meant."""
    with tenant_ctx(brazos):
        plant_entries(brazos, entries=120, tag="M")
        result = reporting.journal_entry_list()
        assert len(result["rows"]) == 120
        assert result["total"] == 120


def test_a_page_cannot_reach_another_tenant(brazos, lonestar, dana, erin):
    """REGRESSION GUARD — hard rule 1. Paging rewrote the query; the tenant
    predicate has to have survived it. Meaningful on PostgreSQL, where RLS is
    behind the ORM filter as well."""
    with tenant_ctx(brazos):
        plant_entries(brazos, entries=60, tag="N")
    with tenant_ctx(lonestar):
        plant_entries(lonestar, entries=3, tag="O")
        body = ledger_api.journal_entries(_request(lonestar, erin)).data
        assert body["count"] == 3
        assert all("O-" in row["memo"] for row in body["results"])


def test_no_cap_is_introduced_anywhere(brazos, dana):
    """`NFR-5` — the fix adds LIMIT/OFFSET and no MAXIMUM. A tenant with more
    entries than any page size still reports all of them and can reach the last
    one. T4 arrives without anything here having to be removed."""
    with tenant_ctx(brazos):
        plant_entries(brazos, entries=1100, tag="P", lines_each=1)
        body = ledger_api.journal_entries(_request(brazos, dana, per="1000")).data
        assert body["count"] == 1100
        assert len(body["results"]) == 1000
        last = ledger_api.journal_entries(
            _request(brazos, dana, per="1000", page="2")
        ).data
        assert len(last["results"]) == 100
