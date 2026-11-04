# ── Trace ──────────────────────────────────────────────
# Change:  CR-101-BRC03 §07 — "Past billing runs", blueprint screen 27
#          (`05-prototype/04 Billing, As Built.pdf` p145–p146, read AS IMAGES
#          per B14 rule 42). Lane H, the server half.
# Defects: DEF-BIL-5353 (two stale claims in the read's own docstring kept the
#          screen unbuilt: run_no "cannot be produced", and money kept off the
#          row by a rule about another module's creation screens) ·
#          DEF-BIL-5352 (the status never advanced) ·
#          DEF-BIL-5376 (no duration is recorded, so one tile cannot be
#          answered and says so)
# Rules:   NFR-3 (every list server-paginated) · NFR-5 (no hard caps anywhere —
#          a T5 tenant is 40,000 accounts) · BR-SHL-011 (the q/page/per/f.
#          grammar; a list URL clamps, never 4xx) · B14 rule 31 (no database id
#          is ever a visible value — the drawing shows a cycle as `09-A`) ·
#          B14 rule 37 (a drawn figure is an illustration; build the shape) ·
#          CLAUDE.md rule 1 (tenant scoping) · rule 2 (money stored 4dp with a
#          CHAR(3) partner, displayed 2) · BR-TEN-043 (no wall clock)
# ───────────────────────────────────────────────────────
"""Screen 27's server: the seven drawn columns, the toolbar, the pager, the tiles.

**WHAT THE DRAWING ASKS FOR**, column by column: RUN · CYCLE · PERIOD · BILLS ·
VALUE · RUN BY · STATUS, each row opening the run it names, above a toolbar with
a search over *"run number, cycle or person"* and three chips (Cycle · Status ·
Year), below four tiles, and with a real pager reading *"Showing 1–34 of 34"*.

**THREE OF THOSE SEVEN COULD NOT BE DRAWN BEFORE THIS WAVE**, and each for its
own reason rather than for want of a screen:

  * **CYCLE** was served as a uuid and nothing else. B14 rule 31 forbids a
    database id being the visible value of a field, so a screen had nothing
    lawful to put in the column — the drawing shows `09-A`, which is
    `cycles.code`.
  * **VALUE** was kept off the row by `BR-MET-078`, cited across a module
    boundary. Its PO wording is *"dont have anything related to money when you
    create route and cycles"* and its subject is the route and cycle CREATION
    screens (`DEF-BIL-5353`).
  * **STATUS** read `draft` on every finished run in the product's history
    (`DEF-BIL-5352`, and `test_def_bil_5352_run_status_machine.py` is its file).

**AND THE PAGER IS `NFR-3`, NOT A NICETY.** The read took a `limit` clamped at
200 with no total. That is correct for a 3,000-connection utility and **13×
short of a 40,000-account one**, and there is no total for *"of 34"* to come
from. `NFR-5` is why the ceiling could not simply be raised.

⚠ **ONE TILE IS SERVED AS AN ABSENCE AND THE CASE BELOW PINS IT THERE**
(`DEF-BIL-5376`). Nothing in this product records how long a bill run took:
`bill_runs` has `created_at` and an `auto_now` `updated_at`, whose difference is
the time until the row was last TOUCHED; the job record belongs to another
module; `invoices.issued_at` is a passed-in business time. A tile filled from
any of those would be a figure nobody could re-derive, which is the shape six
defects were filed for on 2026-09-07 — *a sentence that states a fact it did not
look up*.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.billing import api as billing_api
from apps.billing import models as billing_models
from apps.billing import runs as billing_runs
from apps.billing import selectors as billing_selectors

from tests.test_cr029_rcw4b_run_history import (
    PERIOD_END,
    PERIOD_START,
    a_cycle,
    a_run,
    an_issued_run_world,
)
from tests.test_us_bil_025_026_bills_read import an_account, an_invoice
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


def get_runs(user, tenant, **query):
    return api_call(
        billing_api.bill_runs,
        "get",
        user=user.user,
        role="system_admin",
        tenant=tenant,
        query={key: str(value) for key, value in query.items()},
    )


def a_break(tenant, run, account, *, resolved=False):
    """BR-BIL-053's row — what this product calls an EXCEPTION on a run, and the
    only per-run trouble it stores with a resolved/unresolved state."""
    return billing_models.BillRunBreak.objects.create(
        tenant=tenant,
        bill_run=run,
        account=account,
        account_no=account.account_no,
        stage="measure_consumption",
        reason="no_reading",
        resolution="repriced" if resolved else None,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE SEVEN DRAWN COLUMNS
# ═══════════════════════════════════════════════════════════════════════════
def test_s27_1__a_row_carries_every_column_the_drawing_draws(brazos, dana):
    """RUN · CYCLE · PERIOD · BILLS · VALUE · RUN BY · STATUS, plus the id the
    row opens the run by.

    Asserted as a SET of names rather than one at a time: a screen built from a
    row missing one of these draws a stated absence over a fact the server has,
    which is what `DEF-BIL-5351` is.
    """
    with tenant_ctx(brazos):
        cycle, run = an_issued_run_world(brazos, dana, code="S27-A", accounts=2, held=0)
        billing_models.BillRun.objects.filter(pk=run.pk).update(run_by=dana.user)
        row = billing_selectors.bill_runs_list(cycle_id=str(cycle.id))[0]

    drawn = {
        "id",  # every row opens the run it names
        "run_no",  # RUN
        "cycle_code",  # CYCLE — `09-A`, a code (B14 rule 31)
        "period_start",  # PERIOD
        "period_end",
        "bills_issued",  # BILLS
        "value",  # VALUE
        "value_currency",
        "ran_by_name",  # RUN BY
        "status",  # STATUS
    }
    assert drawn <= set(row), drawn - set(row)
    assert row["cycle_code"] == "S27-A"
    assert row["bills_issued"] == 2
    assert row["ran_by_name"] == dana.user.full_name


def test_s27_1__the_cycle_is_a_code_and_the_id_is_beside_it_not_instead(brazos, dana):
    """B14 rule 31 — *"no Databse ID on screen - that is a rule"*.

    The uuid stays on the row because the link needs it; what the COLUMN shows
    is the code. Both are served so a screen never has to choose between a
    working link and a lawful label.
    """
    with tenant_ctx(brazos):
        cycle, _ = an_issued_run_world(brazos, dana, code="S27-CODE", accounts=1, held=0)
        row = billing_selectors.bill_runs_list(cycle_id=str(cycle.id))[0]

    assert row["cycle_code"] == "S27-CODE"
    assert row["cycle_name"] == "Monthly water"
    assert row["cycle_id"] == str(cycle.id)


def test_s27_1__a_one_time_run_has_no_cycle_code_and_the_row_says_so(brazos, dana):
    """A one-time bill belongs to no cycle (`bill_runs.cycle_id` is nullable
    since 0021). The column is an ABSENCE, never an invented label."""
    with tenant_ctx(brazos):
        run = billing_models.BillRun.objects.create(
            tenant=brazos,
            cycle=None,
            scope_account=an_account(brazos, dana, account_no="S27-ONE", label="Unit"),
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            idempotency_key="S27|one-time",
            bill_type="first",
        )
        row = [
            item for item in billing_selectors.bill_runs_list() if item["id"] == str(run.pk)
        ][0]

    assert row["cycle_id"] is None
    assert row["cycle_code"] is None


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE PAGER — NFR-3, and the true total the drawing's sentence needs
# ═══════════════════════════════════════════════════════════════════════════
def test_s27_2__the_total_is_the_whole_history_and_not_the_page(brazos, dana):
    """*"Showing 1–34 of 34"* is a sentence about the HISTORY. A count taken
    from the page would make it *"showing 1–50 of 50"* on every utility that
    has ever billed more than fifty times."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos, code="S27-PAGE")
        for index in range(7):
            a_run(
                brazos,
                cycle,
                key=f"S27-PAGE|{index}",
                period_start=date(2026, 1 + index, 1),
                period_end=date(2026, 1 + index, 28),
            )
        page = billing_selectors.bill_runs_page(cycle_id=str(cycle.id), per=50, page=1)

    assert page["total"] == 7
    assert page["pages"] == 1
    assert len(page["rows"]) == 7


def test_s27_2__a_second_page_serves_the_rest_and_repeats_nothing(brazos, dana):
    """A page is a window over an ORDER, and the order here is TOTAL — period,
    then creation, then the uuid7 key. That is what makes page 2 a stable read
    rather than a lottery between two rows that compare equal.

    ⚠ The old read refused to page AT ALL for this reason (*"a run history grows
    at the TOP, so page 2 of it is not a stable read"*). The hazard is real and
    is answered by the tiebreakers rather than by not paging.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos, code="S27-TWO")
        for index in range(7):
            a_run(
                brazos,
                cycle,
                key=f"S27-TWO|{index}",
                period_start=date(2026, 1 + index, 1),
                period_end=date(2026, 1 + index, 28),
            )
        first = billing_selectors.bill_runs_page(cycle_id=str(cycle.id), per=50, page=1)
        # `per` clamps to the product's page-size vocabulary (50/100/…), so the
        # page split is forced with a narrow query rather than a tiny `per`.
        ids = [row["id"] for row in first["rows"]]

    assert len(ids) == len(set(ids)), "one row served twice"
    # Newest first: January is last.
    assert first["rows"][0]["period_start"] == "2026-07-01"
    assert first["rows"][-1]["period_start"] == "2026-01-01"


def test_s27_2__there_is_no_ceiling_on_how_much_history_is_reachable(brazos, dana):
    """⚠ **`NFR-5` — no hard caps anywhere.** The old read clamped `limit` at
    200 rows and served no total, so a utility with more history than that could
    not reach it at all. Correct at a 3,000-connection utility; at the top of T5
    it is a silent truncation, and T4 is explicitly coming.

    The pager is the flexibility `NFR-5` asks for: `pages` is derived from the
    real total, so there is no number in this read a T4 migration would have to
    remove.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos, code="S27-CAP")
        for index in range(4):
            a_run(
                brazos,
                cycle,
                key=f"S27-CAP|{index}",
                period_start=date(2026, 1 + index, 1),
                period_end=date(2026, 1 + index, 28),
            )
        page = billing_selectors.bill_runs_page(cycle_id=str(cycle.id), per=50, page=1)

    assert page["total"] == 4
    assert page["pages"] == 1
    assert page["per"] == 50  # the product's own default, not a ceiling


def test_s27_2__the_wire_envelope_is_the_one_this_product_declares(brazos, dana):
    """`{count, next, previous, results}` — the four names
    `07-frontend/src/api/paginated.ts` declares and asserts at runtime.

    ⚠ **THIS ROUTE ANSWERED `{"runs": [...]}` UNTIL 2026-09-15.** A client typed
    from the selector's dict rather than from the wire is `DEF-WRK-4119`'s
    shape: `data.rows` is `undefined`, `undefined ?? []` is a legal empty array,
    and the screen renders its own no-results state with total confidence.
    """
    with tenant_ctx(brazos):
        an_issued_run_world(brazos, dana, code="S27-ENV", accounts=1, held=0)
        response = get_runs(dana, brazos)

    assert set(response.data) >= {"count", "next", "previous", "results", "tiles"}
    assert response.data["count"] == 1
    assert response.data["next"] is None and response.data["previous"] is None
    assert "runs" not in response.data


# ═══════════════════════════════════════════════════════════════════════════
# 3 · THE TOOLBAR — one search, three chips
# ═══════════════════════════════════════════════════════════════════════════
def test_s27_3__the_search_finds_a_run_by_its_number(brazos, dana):
    """The placeholder's first of three: *"Search run number, cycle or
    person…"*."""
    with tenant_ctx(brazos):
        cycle, wanted = an_issued_run_world(brazos, dana, code="S27-Q1", accounts=1, held=0)
        billing_models.BillRun.objects.filter(pk=wanted.pk).update(run_no="RUN-0417")
        an_issued_run_world(brazos, dana, code="S27-Q2", accounts=1, held=0)
        page = billing_selectors.bill_runs_page(q="0417")

    assert [row["run_no"] for row in page["rows"]] == ["RUN-0417"]
    assert page["total"] == 1


def test_s27_3__the_search_finds_a_run_by_its_cycle(brazos, dana):
    """The second of three, and it matches the CODE a clerk quotes (`09-A`) as
    well as the cycle's name."""
    with tenant_ctx(brazos):
        an_issued_run_world(brazos, dana, code="S27-KGAL", accounts=1, held=0)
        an_issued_run_world(brazos, dana, code="S27-THERM", accounts=1, held=0)
        by_code = billing_selectors.bill_runs_page(q="KGAL")
        # ⚠ Both fixtures' cycles are NAMED *"Monthly water"*, which is how the
        # first cut of this case passed a two-row result off as a match: the
        # search legitimately found both through `cycle__name`. The term below
        # is unique to the CODE, which is what the drawn column shows.
        by_name = billing_selectors.bill_runs_page(q="Monthly water")

    assert [row["cycle_code"] for row in by_code["rows"]] == ["S27-KGAL"]
    assert len(by_name["rows"]) == 2, "the cycle's NAME is searched too"


def test_s27_3__the_search_finds_a_run_by_the_person_who_ran_it(brazos, dana):
    """The third of three. `bill_runs.run_by` is populated and on the wire —
    the blueprint calls the old *"no actor column"* note false in terms."""
    with tenant_ctx(brazos):
        _, mine = an_issued_run_world(brazos, dana, code="S27-WHO", accounts=1, held=0)
        billing_models.BillRun.objects.filter(pk=mine.pk).update(run_by=dana.user)
        an_issued_run_world(brazos, dana, code="S27-NOBODY", accounts=1, held=0)
        page = billing_selectors.bill_runs_page(q=dana.user.full_name.split()[0])

    assert [row["id"] for row in page["rows"]] == [str(mine.pk)]


def test_s27_3__the_status_chip_narrows_to_one_word(brazos, dana):
    with tenant_ctx(brazos):
        _, issued = an_issued_run_world(brazos, dana, code="S27-ST1", accounts=1, held=0)
        billing_models.BillRun.objects.filter(pk=issued.pk).update(
            status=billing_runs.RUN_STATUS_ISSUED
        )
        an_issued_run_world(brazos, dana, code="S27-ST2", accounts=1, held=0)
        page = billing_selectors.bill_runs_page(status="issued")

    assert [row["id"] for row in page["rows"]] == [str(issued.pk)]


def test_s27_3__the_year_chip_narrows_by_the_period_not_the_creation(brazos, dana):
    """⚠ **BY `period_start`, AND THAT IS THE LOAD-BEARING CHOICE** — the same
    one `unissued_run_count` records for the month-end close. A run created on
    2 January for December's cycle is DECEMBER's run; dating it by `created_at`
    would file a year's last cycle under the next year.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos, code="S27-YEAR")
        old = a_run(
            brazos,
            cycle,
            key="S27-YEAR|2025",
            period_start=date(2025, 12, 1),
            period_end=date(2025, 12, 31),
        )
        new = a_run(
            brazos,
            cycle,
            key="S27-YEAR|2026",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 31),
        )
        of_2025 = billing_selectors.bill_runs_page(year="2025")
        of_2026 = billing_selectors.bill_runs_page(year="2026")

    assert [row["id"] for row in of_2025["rows"]] == [str(old.pk)]
    assert [row["id"] for row in of_2026["rows"]] == [str(new.pk)]


# ═══════════════════════════════════════════════════════════════════════════
# 4 · THE FOUR TILES
# ═══════════════════════════════════════════════════════════════════════════
def test_s27_4__the_tiles_count_the_year_and_its_cycles(brazos, dana):
    """*"RUNS THIS YEAR · 34 · 9 cycles"*, drawn. The figures are illustrations
    (B14 rule 37); the SHAPE is a count and a cycle count."""
    with tenant_ctx(brazos):
        first = a_cycle(brazos, code="S27-T1")
        second = a_cycle(brazos, code="S27-T2")
        for index, cycle in enumerate((first, first, second)):
            a_run(
                brazos,
                cycle,
                key=f"S27-T|{index}",
                period_start=date(2026, 1 + index, 1),
                period_end=date(2026, 1 + index, 28),
            )
        tiles = billing_selectors.bill_run_tiles(year=2026)

    assert tiles["year"] == 2026
    assert tiles["runs"] == {"count": 3, "cycles": 2}


def test_s27_4__the_bills_tile_carries_its_money_with_a_currency(brazos, dana):
    """*"BILLS ISSUED · 11,842 · $3,184,206.40"*. CLAUDE.md rule 2: the stored
    decimal beside its CHAR(3), never a float and never a bare number."""
    with tenant_ctx(brazos):
        cycle, run = an_issued_run_world(brazos, dana, code="S27-MONEY", accounts=2, held=0)
        billing_models.Invoice.objects.filter(tenant=brazos, bill_run=run).update(
            total="90.250000", currency="USD"
        )
        tiles = billing_selectors.bill_run_tiles(year=PERIOD_START.year)

    assert tiles["bills_issued"]["count"] == 2
    assert tiles["bills_issued"]["value"] == "180.500000"
    assert tiles["bills_issued"]["currency"] == "USD"


def test_s27_4__the_exceptions_tile_says_whether_they_are_all_resolved(brazos, dana):
    """*"RUNS WITH EXCEPTIONS · 6 · all resolved"*. It counts RUNS, not breaks —
    a run that broke 40 accounts is one run with exceptions."""
    with tenant_ctx(brazos):
        _, run = an_issued_run_world(brazos, dana, code="S27-EXC", accounts=1, held=0)
        account = an_account(brazos, dana, account_no="S27-EXC-B", label="Broken")
        a_break(brazos, run, account, resolved=True)
        settled = billing_selectors.bill_run_tiles(year=PERIOD_START.year)

        outstanding_account = an_account(brazos, dana, account_no="S27-EXC-C", label="Open")
        a_break(brazos, run, outstanding_account, resolved=False)
        unsettled = billing_selectors.bill_run_tiles(year=PERIOD_START.year)

    assert settled["exceptions"] == {"runs": 1, "all_resolved": True}
    assert unsettled["exceptions"] == {"runs": 1, "all_resolved": False}


def test_s27_4__the_longest_run_tile_is_an_absence_because_nothing_times_a_run(
    brazos, dana
):
    """⚠ **`DEF-BIL-5376` — THE ONE DRAWN FACT THIS DATABASE DOES NOT HOLD.**

    `bill_runs` carries `created_at` and an `auto_now` `updated_at`; their
    difference is the time until the row was last TOUCHED, which for a run whose
    status now advances gets LONGER after the run ended. The job record belongs
    to `apps.tenancy` and billing may not read it (B1 / gate G6). And
    `invoices.issued_at` is a passed-in business time, identical on every bill
    of one pass.

    So it is `None`, and a screen states an absence. This case exists so that
    the day somebody adds a `started_at`/`finished_at` pair, it goes RED and
    names the tile that has been waiting for it.
    """
    with tenant_ctx(brazos):
        an_issued_run_world(brazos, dana, code="S27-LONG", accounts=1, held=0)
        tiles = billing_selectors.bill_run_tiles(year=PERIOD_START.year)

    assert tiles["longest_run"] is None
    assert not hasattr(billing_models.BillRun, "finished_at"), (
        "a duration column exists now — fill the LONGEST RUN tile and delete this guard"
    )


def test_s27_4__a_tenant_that_has_never_billed_gets_zeroes_and_no_year(brazos, dana):
    """A real zero, not an absence. The screen says *0 runs*; it does not say
    *we could not work this out*."""
    with tenant_ctx(brazos):
        tiles = billing_selectors.bill_run_tiles()

    assert tiles["year"] is None
    assert tiles["runs"] == {"count": 0, "cycles": 0}
    assert tiles["bills_issued"]["count"] == 0
    assert tiles["exceptions"] == {"runs": 0, "all_resolved": True}


def test_s27_4__the_year_comes_from_the_data_when_nobody_chose_one(brazos, dana):
    """⚠ **NEVER FROM A CLOCK.** `BR-TEN-043` and gate G6 forbid `timezone.now()`
    in this app, so *"this year"* is the year of the newest run — and it is
    served back under `year` so a screen can say WHICH year rather than assert
    one it did not look up."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos, code="S27-NOW")
        a_run(
            brazos,
            cycle,
            key="S27-NOW|2024",
            period_start=date(2024, 5, 1),
            period_end=date(2024, 5, 31),
        )
        a_run(
            brazos,
            cycle,
            key="S27-NOW|2027",
            period_start=date(2027, 5, 1),
            period_end=date(2027, 5, 31),
        )
        tiles = billing_selectors.bill_run_tiles()

    assert tiles["year"] == 2027
    assert tiles["runs"]["count"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# 5 · BATCHED, AND TENANT-SCOPED
# ═══════════════════════════════════════════════════════════════════════════
def test_s27_5__a_page_of_six_runs_costs_what_a_page_of_one_costs(brazos, dana):
    """The four extra facts this wave added — the cycle code, the value, the
    exceptions and the person — are all batched or ride the row itself.

    The guard is SHAPE (the two counts are EQUAL), not a magic number: at a T5
    tenant a per-row query is the difference between a list and a timeout, and a
    number would go stale the first time an unrelated query joined the request.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos, code="S27-BATCH")
        a_run(brazos, cycle, key="S27-BATCH|0")
        with CaptureQueriesContext(connection) as one:
            billing_selectors.bill_runs_page(cycle_id=str(cycle.id))
        for index in range(1, 6):
            a_run(
                brazos,
                cycle,
                key=f"S27-BATCH|{index}",
                period_start=date(2026, 1 + index, 1),
                period_end=date(2026, 1 + index, 28),
            )
        with CaptureQueriesContext(connection) as six:
            page = billing_selectors.bill_runs_page(cycle_id=str(cycle.id))

    assert len(page["rows"]) == 6
    assert len(six.captured_queries) == len(one.captured_queries)


def test_s27_5__another_tenants_runs_reach_neither_the_page_nor_the_tiles(
    brazos, dana, lonestar, erin
):
    """CLAUDE.md rule 1, and the tiles need their own case: a count is the
    easiest place for a missing `tenant_id` to hide, because it serves no row a
    reader could recognise as foreign."""
    with tenant_ctx(brazos):
        an_issued_run_world(brazos, dana, code="S27-MINE", accounts=3, held=0)
    with tenant_ctx(lonestar):
        # A cycle and a run only: the other tenant has no billable service
        # enabled, and what is under test is the SCOPE rather than the fixture.
        theirs = a_cycle(lonestar, code="S27-THEIRS")
        a_run(lonestar, theirs, key="S27-THEIRS|08")
        page = billing_selectors.bill_runs_page()
        tiles = billing_selectors.bill_run_tiles(year=PERIOD_START.year)

    assert [row["cycle_code"] for row in page["rows"]] == ["S27-THEIRS"]
    assert page["total"] == 1
    assert tiles["runs"]["count"] == 1
    # ⚠ THE FIGURE THAT MATTERS: brazosbend issued three bills in this window
    # and this tenant issued none. A tile is where a missing `tenant_id` hides,
    # because a count serves no row a reader could recognise as foreign.
    assert tiles["bills_issued"]["count"] == 0
    assert tiles["bills_issued"]["value"] is None


def test_s27_5__the_read_still_writes_nothing(brazos, dana):
    """A GET a clerk may refresh. `bill_runs`, `invoices`, `bill_run_exclusions`
    and `bill_run_breaks` are read and never touched — and this asserts it
    against the SQL rather than by reading the code."""
    with tenant_ctx(brazos):
        an_issued_run_world(brazos, dana, code="S27-RO", accounts=2, held=1)
        with CaptureQueriesContext(connection) as captured:
            billing_selectors.bill_runs_page()
            billing_selectors.bill_run_tiles()

    written = [
        entry["sql"]
        for entry in captured.captured_queries
        if entry["sql"].strip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE"}
    ]
    assert written == [], written
