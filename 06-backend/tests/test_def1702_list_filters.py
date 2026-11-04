# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-1702 — nine list screens render a `DataTable` and NO filter
#          control at all, and CR-045 wave D was sized for seven.
# Change:  CR-045 wave D tasks D.7 · D.8 · D.9 · D.10 · D.11 · D.12 · D.13–D.15
# Rules:   BR-SHL-010 (only a DECLARED capability renders) · BR-SHL-011 (the
#          `f.<name>` URL grammar, AND-combined ON THE SERVER; unknown params
#          ignored, invalid values fall back or clamp, never an error) ·
#          BR-TEN-043 (the event date is an argument, never a wall clock) ·
#          CLAUDE.md hard rule 1 (tenant scoping)
# ───────────────────────────────────────────────────────
"""**THE ONE PROPERTY THIS FILE EXISTS TO PIN: THE SERVER APPLIES THE FILTER.**

DEF-1702's nine screens are being given filter controls. The failure mode that
would make all nine WORSE than the bare toolbar they replace is a control that
narrows the page in hand rather than the result set — a subset of a subset,
rendered without a word of explanation, on lists that are paginated server-side.
Every case below therefore asserts on **`total`**, the count the server reports
for the whole filtered set, and never on `len(rows)`, which a client-side filter
would also satisfy.

**FIVE SHAPES OF LIE, ONE CASE EACH, ON EVERY LEG:**

  1. the filter NARROWS — `total` falls to the matching rows;
  2. it narrows to the RIGHT rows — the row that survives is the one that holds
     the value, checked by name and not by count;
  3. an ABSENT filter is not an empty one — no filter returns everything;
  4. an UNSERVABLE value returns NOTHING rather than everything. Falling back to
     "unfiltered" on a value the user explicitly picked shows them MORE than
     they asked for, which is the quietest possible way to be wrong;
  5. the vocabulary is PUBLISHED — the payload names the `f.<name>` it accepts
     and the options it will answer, so a screen never invents one (BR-SHL-010).

⚠ **RED PROVED FIRST (hard-won law 7).** Every case here was run against the
pristine tip — `c260f64`, before the six server legs existed — and the failures
are quoted in the lane report. They are the interesting kind: the lists answered
`200 OK` with the FULL result set, because `parse_list_params` drops every
`f.<name>` outside a view's `allowed_filters` and none of these views declared
any. A filter that is silently discarded is exactly the defect this work is
about, one layer down.

⚠ **AND TWO CASES BELOW ARE DELIBERATELY NEGATIVE.** `?segment=` still refuses
everything but `all` on Disconnects and on New connects. Filtering by a stored
value is not the same question as assigning a row to one exclusive tab, and
these two assertions are what keeps the second question OPEN (`OQ-371`, and
`disconnect_reads` §3's unruled precedence) while the first is answered.
"""

from datetime import date, timedelta

import pytest

from apps.customers import disconnect_reads, disconnects, move_reads, transfer_reads
from apps.customers import services as customers_services
from apps.metering import connection_reads, import_runs
from apps.metering import models as metering_models
from apps.metering import selectors as metering_selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: The as-of date every derived case is anchored on. BR-TEN-043: the event date
#: is an ARGUMENT. A test that read the wall clock would go red on one day of
#: the year and nobody would know which.
TODAY = date(2026, 8, 25)


# ════════════════════════════════════════════════════════════════════════════
# D.13–D.15 · `GET /imports` — `f.status` and `f.target`
#
# ⚠ `run_list` TOOK A `params` ARGUMENT AND IGNORED IT FROM CR-023 UNTIL NOW.
# `apps/metering/api.py` passed `request.query_params` into it the whole time,
# so the parameter looked wired and answered nothing, and all three Imports tabs
# fetched every run and narrowed it in the browser.
# ════════════════════════════════════════════════════════════════════════════
def _run(tenant, *, target, status, file_name):
    """One `import_runs` row, written directly.

    ⚠ **DIRECT, AND THAT IS THE RIGHT CHOICE HERE UNLIKE ELSEWHERE IN THIS
    SUITE.** The thing under test is a WHERE clause over two stored columns; a
    fixture that drove the five-stage runner to reach `failed` or `rolled_back`
    would be testing the runner, and would make the case unable to hold a
    `rolled_back` row at all without a load, an approval and a rollback point.
    """
    return metering_models.ImportRun.objects.create(
        tenant=tenant, target=target, status=status, file_name=file_name, counts={}
    )


def test_the_imports_list_filters_by_status_on_the_server(brazos, marcus):
    """Case 1 + 2 + 3 — `f.status` narrows, to the right rows, and only when set."""
    with tenant_ctx(brazos):
        _run(brazos, target="accounts", status="loaded", file_name="a.csv")
        _run(brazos, target="accounts", status="failed", file_name="b.csv")
        _run(brazos, target="premises", status="loaded", file_name="c.csv")

        assert len(import_runs.run_list(None)["rows"]) == 3  # case 3: no filter, everything

        loaded = import_runs.run_list({"f.status": "loaded"})["rows"]
        assert len(loaded) == 2
        assert {row["file_name"] for row in loaded} == {"a.csv", "c.csv"}

        failed = import_runs.run_list({"f.status": "failed"})["rows"]
        assert [row["file_name"] for row in failed] == ["b.csv"]


def test_the_imports_list_filters_by_target_which_tc_imp_12_already_wrote(brazos, marcus):
    """B18 TC-IMP-12 writes `GET /imports?target=accounts` and the route accepted
    no such param. This is that leg, in BR-SHL-011's signed `f.<name>` grammar.

    ⚠ It is what makes the three Imports tabs' own client-side `.filter(row =>
    …target…)` honest: `run_list` serves at most 200 rows, so narrowing AFTER
    the cap answers *the newest 200 runs that happen to be accounts runs*
    instead of *the newest 200 accounts runs*.
    """
    with tenant_ctx(brazos):
        _run(brazos, target="accounts", status="loaded", file_name="accounts.csv")
        _run(brazos, target="assets_meters", status="loaded", file_name="meters.csv")
        _run(brazos, target="premises", status="loaded", file_name="premises.csv")

        rows = import_runs.run_list({"f.target": "assets_meters"})["rows"]
        assert [row["file_name"] for row in rows] == ["meters.csv"]


def test_the_two_imports_filters_and_combine(brazos, marcus):
    """BR-SHL-011: declared filters AND-combine. Two dimensions, one row."""
    with tenant_ctx(brazos):
        _run(brazos, target="accounts", status="loaded", file_name="want.csv")
        _run(brazos, target="accounts", status="failed", file_name="wrong-status.csv")
        _run(brazos, target="premises", status="loaded", file_name="wrong-target.csv")

        rows = import_runs.run_list({"f.status": "loaded", "f.target": "accounts"})["rows"]
        assert [row["file_name"] for row in rows] == ["want.csv"]


def test_an_undeclared_imports_filter_is_ignored_and_never_an_error(brazos, marcus):
    """BR-SHL-011's fall-back law: an unknown `f.<name>` is IGNORED.

    ⚠ Ignored is the right answer for a name the endpoint never declared — it is
    a stale bookmark, not a user's choice. That is a different case from case 4
    below, where the user picked a value from a panel we drew.
    """
    with tenant_ctx(brazos):
        _run(brazos, target="accounts", status="loaded", file_name="a.csv")
        assert len(import_runs.run_list({"f.nonsense": "whatever"})["rows"]) == 1


def test_a_status_no_run_holds_returns_none_of_them(brazos, marcus):
    """Case 4, in its mildest form: an empty answer, never the whole list."""
    with tenant_ctx(brazos):
        _run(brazos, target="accounts", status="loaded", file_name="a.csv")
        assert import_runs.run_list({"f.status": "rolled_back"})["rows"] == []


def test_the_imports_filter_cannot_see_another_tenants_runs(brazos, lonestar, marcus):
    """Hard rule 1, restated over the new leg: a filter is not a way around RLS."""
    with tenant_ctx(brazos):
        _run(brazos, target="accounts", status="loaded", file_name="brazos.csv")
    with tenant_ctx(lonestar):
        assert import_runs.run_list({"f.status": "loaded"})["rows"] == []


# ════════════════════════════════════════════════════════════════════════════
# D.7 · `GET /cycles` — `f.frequency`
# ════════════════════════════════════════════════════════════════════════════
def _cycle(tenant, *, code, frequency, status="active"):
    return metering_models.Cycle.objects.create(
        tenant=tenant, code=code, name=f"Cycle {code}", frequency=frequency, status=status
    )


def test_the_cycles_list_filters_by_frequency(brazos, marcus):
    """SET-05.cycles drew a Frequency column and SORTED on it and could not
    FILTER on it — the one dimension the tab most obviously offers."""
    with tenant_ctx(brazos):
        _cycle(brazos, code="C-M", frequency="Monthly")
        _cycle(brazos, code="C-Q", frequency="Quarterly")

        rows = metering_selectors.cycles_page(filters={"frequency": "Monthly"})
        assert [row["code"] for row in rows] == ["C-M"]


def test_the_frequency_leg_matches_EXACTLY_so_annual_never_answers_for_semiannual(
    brazos, marcus
):
    """⚠ **THE REASON THIS LEG IS EXACT-PER-TOKEN AND NEVER `icontains`.**
    `annual` is a substring of `semiannual`, so a loose match would put every
    semiannual cycle in the annual answer with a count that looks plausible."""
    with tenant_ctx(brazos):
        _cycle(brazos, code="C-A", frequency="Annual")
        _cycle(brazos, code="C-S", frequency="Semiannual")

        rows = metering_selectors.cycles_page(filters={"frequency": "Annual"})
        assert [row["code"] for row in rows] == ["C-A"]


def test_the_frequency_leg_folds_BOTH_generations_of_the_spelling(brazos, marcus):
    """**THE CASE THAT NEARLY SHIPPED A CONTROL THAT MISSES ROWS.**

    `cycles.frequency` is FREE TEXT and holds two generations: RC-W1's migration
    0019 moved the shipped rows onto the eight business words (`Monthly`), and
    the CR-006 generation wrote the enum (`monthly`, `bi_monthly`). The frontend
    already folds them through `frequencyKey()`; a naive `frequency=` on the
    server would have answered ONE generation and quietly dropped the other —
    the user sees a shorter list and no reason why.

    Both spellings of Bimonthly, one filter, both rows.
    """
    with tenant_ctx(brazos):
        _cycle(brazos, code="C-NEW", frequency="Bimonthly")
        _cycle(brazos, code="C-OLD", frequency="bi_monthly")
        _cycle(brazos, code="C-OTHER", frequency="Monthly")

        rows = metering_selectors.cycles_page(filters={"frequency": "Bimonthly"})
        assert sorted(row["code"] for row in rows) == ["C-NEW", "C-OLD"]

        # …and asking with the LEGACY spelling finds both too, because the fold
        # is on the value asked for as well as on the value stored.
        rows = metering_selectors.cycles_page(filters={"frequency": "bi_monthly"})
        assert sorted(row["code"] for row in rows) == ["C-NEW", "C-OLD"]


def test_frequency_and_status_and_combine_on_cycles(brazos, marcus):
    with tenant_ctx(brazos):
        _cycle(brazos, code="C-1", frequency="Monthly", status="active")
        _cycle(brazos, code="C-2", frequency="Monthly", status="inactive")

        rows = metering_selectors.cycles_page(
            filters={"frequency": "Monthly", "status": "active"}
        )
        assert [row["code"] for row in rows] == ["C-1"]


# ════════════════════════════════════════════════════════════════════════════
# THE FIVE CUSTOMER WORKLISTS — D.8 · D.9 · D.10 · D.11 · D.12
#
# ⚠ **EVERY ONE OF THESE LISTS PAGES ON THE SERVER**, which is exactly why a
# browser-side filter would have been a lie on them: `per` is 50 by default and
# the control would have narrowed 50 rows out of however many the tenant has.
# So each case asserts on `total` — the server's count for the WHOLE filtered
# set — and the `_states_on` helper reads the vocabulary back off the payload
# rather than hardcoding it, so a state renamed upstream fails the leg's own
# test instead of silently making the option unreachable.
# ════════════════════════════════════════════════════════════════════════════
from django.db import connection as db_connection  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

from tests.test_w5_move_worklists import _account as _w5_account  # noqa: E402
from tests.test_w5_move_worklists import _booked_in, _moved_out  # noqa: E402
from tests.test_w6_connection_list import _build_row  # noqa: E402
from tests.test_w7_worklists import _at_tier, _mover, _owes, _through_step_4  # noqa: E402


def _states_on(payload):
    """The `code` set the payload PUBLISHES as filterable (BR-SHL-010).

    ⚠ It is read from the response and never retyped into the test. A test that
    hardcoded `"notice_sent"` would still pass on the day the server stopped
    offering it — and the SCREEN would then draw an option nothing can answer.
    """
    return {state["code"] for state in payload["states"]}


# ── D.9 · Move-ins — `f.state` ──────────────────────────────────────────────
def test_move_ins_filters_by_state_and_the_predicate_is_the_derivation(brazos, marcus):
    """`move_in_state` is §1's three-way derivation and the KPIs read it too, so
    the SQL predicate is that function read backwards — `waiting` is
    `opened_at IS NULL`, `scheduled` is `> as_of`, `due` is `<= as_of` and never
    null. Anything else and a row's STATE cell could disagree with the filter
    that produced it.
    """
    with tenant_ctx(brazos):
        _booked_in(marcus, brazos, label="1 Scheduled Way", name="Ahead, Ann",
                   opened_at=str(TODAY + timedelta(days=10)))
        _booked_in(marcus, brazos, label="2 Due Rd", name="Overdue, Otto",
                   opened_at=str(TODAY - timedelta(days=3)))
        _booked_in(marcus, brazos, label="3 Waiting Ln", name="Blocked, Bea", opened_at=None)

        everything = move_reads.move_ins_list(as_of=TODAY)
        assert everything["total"] == 3  # case 3 — no filter, no narrowing
        assert "state" in everything["filters"]  # case 5 — the vocabulary is published

        for code, expected in (("scheduled", 1), ("due", 1), ("waiting", 1)):
            answer = move_reads.move_ins_list(as_of=TODAY, filters={"state": code})
            assert answer["total"] == expected, code
            assert {row["state"] for row in answer["rows"]} == {code}, code


def test_a_move_in_state_we_do_not_serve_returns_nothing_never_everything(brazos, marcus):
    """**CASE 4, AND IT IS THE ONE WORTH THE MOST.** `in_progress` is drawn by
    B18 and marked UNSUPPORTED (`STEP_HAS_NO_STORE`). Falling back to
    "unfiltered" on a value the user picked would show them the whole tab while
    the chip on screen said `State: In progress` — a wrong answer that looks
    like a right one.
    """
    with tenant_ctx(brazos):
        _booked_in(marcus, brazos, label="1 Scheduled Way", name="Ahead, Ann",
                   opened_at=str(TODAY + timedelta(days=10)))
        answer = move_reads.move_ins_list(as_of=TODAY, filters={"state": "in_progress"})
        assert answer["total"] == 0
        assert answer["rows"] == []


# ── D.10 · Move-outs — `f.closed`, a window and not a state ─────────────────
def test_move_outs_filters_by_the_closed_window(brazos, marcus):
    """`MOVE_OUT_STATES` marks exactly ONE code `supported`, so a state filter
    would offer one option that changes nothing. `closed_at` is the one stored,
    filterable fact on the row, and the window is INCLUSIVE of the as-of date:
    `last7` on 2026-08-25 is 2026-08-19..2026-08-25 — seven dates, not eight.
    """
    with tenant_ctx(brazos):
        _moved_out(marcus, brazos, label="10 Recent St", name="Just, Left",
                   on=str(TODAY - timedelta(days=2)))
        _moved_out(marcus, brazos, label="11 Older Ave", name="While, Ago",
                   on=str(TODAY - timedelta(days=45)))

        everything = move_reads.move_outs_list(as_of=TODAY)
        assert everything["total"] == 2
        assert "closed" in everything["filters"]
        assert {w["code"] for w in everything["closed_windows"]} == {"last7", "last30", "last90"}

        assert move_reads.move_outs_list(as_of=TODAY, filters={"closed": "last7"})["total"] == 1
        assert move_reads.move_outs_list(as_of=TODAY, filters={"closed": "last30"})["total"] == 1
        assert move_reads.move_outs_list(as_of=TODAY, filters={"closed": "last90"})["total"] == 2


def test_the_closed_window_boundary_is_inclusive_of_the_as_of_date(brazos, marcus):
    """The off-by-one this window is most likely to get wrong, pinned: a row
    closed exactly `n - 1` days back is IN `last{n}` and a row closed one day
    earlier is OUT."""
    with tenant_ctx(brazos):
        _moved_out(marcus, brazos, label="20 Edge In", name="On, Boundary",
                   on=str(TODAY - timedelta(days=6)))
        _moved_out(marcus, brazos, label="21 Edge Out", name="Off, Boundary",
                   on=str(TODAY - timedelta(days=7)))

        answer = move_reads.move_outs_list(as_of=TODAY, filters={"closed": "last7"})
        assert answer["total"] == 1
        assert answer["rows"][0]["account_no"] is not None


def test_an_unserved_closed_window_returns_nothing_never_everything(brazos, marcus):
    """Case 4 again — `last365` is not a window we serve."""
    with tenant_ctx(brazos):
        _moved_out(marcus, brazos, label="10 Recent St", name="Just, Left", on=str(TODAY))
        assert move_reads.move_outs_list(as_of=TODAY, filters={"closed": "last365"})["total"] == 0


def test_the_move_outs_reads_sweep_is_NOT_narrowed_by_the_filter(brazos, marcus):
    """⚠ **THE ONE THING A KPI STRIP MUST NOT DO IS CHANGE WHEN A FILTER IS
    APPLIED.** The tiles answer *what is on this tab*, not *what am I looking at
    right now*. `_unit_reads_answers` is swept over the UNFILTERED window on
    purpose, so `FINAL READS DUE` counts the same before and after.
    """
    with tenant_ctx(brazos):
        _moved_out(marcus, brazos, label="10 Recent St", name="Just, Left",
                   on=str(TODAY - timedelta(days=2)))
        _moved_out(marcus, brazos, label="11 Older Ave", name="While, Ago",
                   on=str(TODAY - timedelta(days=45)))

        wide = move_reads.move_outs_list(as_of=TODAY)
        narrow = move_reads.move_outs_list(as_of=TODAY, filters={"closed": "last7"})
        assert narrow["total"] == 1 and wide["total"] == 2  # the FILTER did work
        assert narrow["kpis"] == wide["kpis"]  # and the TILES did not move


# ── D.12 · Transfers — `f.state` ────────────────────────────────────────────
def test_transfers_filters_by_state_and_never_offers_cancelled(brazos, marcus):
    """`list_queryset` excludes cancelled jobs from the list itself (§6), so
    `cancelled` is not an option — a control that offered it would report "none"
    for a reason the screen cannot show."""
    with tenant_ctx(brazos):
        _, account = _mover(marcus, brazos, name="Park, Jenna", label="Unit A")
        started = transfer_reads.transfers.start_transfer(
            marcus, {"from_account_id": str(account.id)}
        )

        everything = transfer_reads.list_transfers(as_of=TODAY)
        assert everything["total"] == 1
        assert "state" in everything["filters"]
        assert "cancelled" not in _states_on(everything)

        live = everything["rows"][0]["state"]
        assert transfer_reads.list_transfers(as_of=TODAY, filters={"state": live})["total"] == 1
        other = next(code for code in _states_on(everything) if code != live)
        assert transfer_reads.list_transfers(as_of=TODAY, filters={"state": other})["total"] == 0
        assert started["id"] is not None


def test_asking_transfers_for_cancelled_returns_nothing_never_everything(brazos, marcus):
    """Case 4: `cancelled` is off the vocabulary, so it must not re-admit the
    rows the list deliberately excludes — and it must not fall back to all."""
    with tenant_ctx(brazos):
        _mover(marcus, brazos, name="Park, Jenna", label="Unit A")
        _, account = _mover(marcus, brazos, name="Ruiz, Dana", label="Unit B")
        transfer_reads.transfers.start_transfer(marcus, {"from_account_id": str(account.id)})

        assert transfer_reads.list_transfers(as_of=TODAY)["total"] == 1
        answer = transfer_reads.list_transfers(as_of=TODAY, filters={"state": "cancelled"})
        assert answer["total"] == 0


# ── D.8 · Disconnects — `f.state` on the STORED case state ──────────────────
def test_disconnects_filters_by_the_stored_case_state(brazos, marcus, monkeypatch):
    """⛔ **NOT `?segment=` — see the next case.** This asks *does this row's
    stored `disconnect_cases.state` equal X*, which needs no ranking of the six
    non-exclusive segments and therefore takes none.
    """
    _owes(monkeypatch, 108.88)
    with tenant_ctx(brazos):
        account = _w5_account(marcus, brazos, label="30 Ladder Way", name="Owing, Olive",
                              status="active")
        _at_tier(marcus, account["id"], disconnects.TIER_1)

        everything = disconnect_reads.list_disconnects(as_of=TODAY)
        assert everything["total"] == 1
        assert "state" in everything["filters"]
        # The list can never hold these two — `open_cases` excludes them.
        assert {"stopped", "restored"}.isdisjoint(_states_on(everything))

        # ⚠ `row["state"]` is §5.8.2's TWO-AXIS cell — `{"stored", "held_by",
        # "one_cell_is_unresolved", …}` — precisely because `On hold` is
        # COMPUTED while the rest are STORED and a row can be both. The filter
        # matches `stored`, which is the only axis a `WHERE` clause can speak
        # for; reading the cell as a bare string here would have tested nothing
        # and passed, because `{...} != "notice_sent"` narrows to zero either
        # way. Measured: it narrowed to zero, and that is what caught it.
        live = everything["rows"][0]["state"]["stored"]
        narrow = disconnect_reads.list_disconnects(as_of=TODAY, filters={"state": live})
        assert narrow["total"] == 1
        other = next(code for code in _states_on(everything) if code != live)
        assert disconnect_reads.list_disconnects(
            as_of=TODAY, filters={"state": other}
        )["total"] == 0


def test_filtering_disconnects_by_state_does_NOT_answer_the_segment_question(brazos, marcus):
    """**A DELIBERATELY NEGATIVE ASSERTION, AND IT MUST STAY THAT WAY.**

    `disconnect_reads` §3 refuses every segment but `all` because B18 §5.8.2's
    six segments are not mutually exclusive and *no rule ranks them*. Adding a
    value filter answers a different question and must not be read as having
    settled that one. If a later lane makes this green it must be because the
    precedence was RULED — not because the refusal was inconvenient.
    """
    with tenant_ctx(brazos):
        with pytest.raises(NotImplementedError):
            disconnect_reads.list_disconnects(segment="at_notice", as_of=TODAY)


# ── D.11 · New connects — `f.state` ─────────────────────────────────────────
def test_new_connects_filters_by_state_over_the_open_vocabulary(brazos, dana):
    """Every state the payload OFFERS narrows to exactly the builds in it.

    ⚠ **THIS DOCSTRING AND ONE ASSERTION WERE WRONG AND ARE CORRECTED
    (`DEF-CUS-5431`).** It read *"The vocabulary is `OPEN_STATES` and not
    `CONNECTION_STATES`: this is the OPEN worklist, so `activated` and
    `cancelled` are already outside it"*, and asserted
    `{"activated", "cancelled"}.isdisjoint(...)`. **There is no such window.**
    `connection_reads._connections` is `Connection.objects.filter(tenant_id=…)`
    and nothing else, so an activated build has always been in this list — and
    the blueprint draws one (`CX-26-0004 · Activated`, p094). The option was
    withheld on a belief about the query, not on the query.
    """
    with tenant_ctx(brazos):
        _build_row(dana, no="CON-A", address="40 First Ave", units=1, done=0, orders=1,
                   target="2026-09-10", waiting_on=None, shape="requested", age_days=3)
        _build_row(dana, no="CON-B", address="41 Second Ave", units=1, done=1, orders=1,
                   target="2026-09-12", waiting_on=None, shape="in_progress", age_days=2)

        everything = connection_reads.list_connections()
        assert everything["total"] == 2
        assert "state" in everything["filters"]
        # The blueprint's three chips are OFFERED and in the drawn order, and
        # `open` leads because that is the chip drawn first (p094).
        offered = [state["code"] for state in everything["states"]]
        assert offered[:3] == ["open", "partly_activated", "activated"]
        # …and nothing a row can be in became unreachable by gaining a chip in
        # front of it, which is the failure mode of a redraw.
        assert set(connection_reads.OPEN_STATES) <= set(offered)

        by_state: dict[str, int] = {}
        for row in everything["rows"]:
            by_state[row["state"]] = by_state.get(row["state"], 0) + 1
        assert len(by_state) >= 2, "the fixture must hold two DIFFERENT states to be meaningful"

        for code, expected in by_state.items():
            answer = connection_reads.list_connections(filters={"state": code})
            assert answer["total"] == expected, code
            assert {row["state"] for row in answer["rows"]} == {code}, code


def test_the_activated_chip_returns_the_activated_build_and_open_returns_the_rest(brazos, dana):
    """**THE BLUEPRINT'S THREE CHIPS, EACH PROVED AGAINST A ROW (`DEF-CUS-5431`).**

    ⚠ **THIS TEST REPLACES ONE THAT PASSED FOR THE WRONG REASON**, and that is
    why it is worth the fixture. It was
    `test_a_connection_state_outside_the_open_set_returns_nothing`: it seeded a
    single `requested` build, asked for `state=activated`, and asserted zero.
    **Zero was the right answer to that fixture whether the filter worked or
    not** — there was no activated row for it to find — so the case could never
    have caught `activated` returning `.none()` while activated builds sat in
    the unfiltered page. Law 7's *looking at the wrong thing*, in the check
    that was pointed at the defect.

    So the fixture now holds one activated build and one that is not, and each
    chip is asked for the row it must return AND the row it must not.
    """
    with tenant_ctx(brazos):
        _build_row(dana, no="CON-A", address="40 First Ave", units=1, done=0, orders=1,
                   target="2026-09-10", waiting_on=None, shape="requested", age_days=3)
        _build_row(dana, no="CON-Z", address="41 Second Ave", units=1, done=1, orders=1,
                   target="2026-09-12", waiting_on=None, shape="activated", age_days=2)

        both = connection_reads.list_connections()
        assert both["total"] == 2, "an activated build is IN this list — there is no window"

        activated = connection_reads.list_connections(filters={"state": "activated"})
        assert [row["connection_no"] for row in activated["rows"]] == ["CON-Z"]

        # `open` is the KPI tile's own set: everything not activated or
        # cancelled, which is the one chip that is not a stored state.
        open_only = connection_reads.list_connections(filters={"state": "open"})
        assert [row["connection_no"] for row in open_only["rows"]] == ["CON-A"]
        assert open_only["total"] == both["kpis"]["open"], "the chip and the tile count one set"


def test_the_chip_narrows_in_sql_and_the_page_is_limited_there_too(brazos, dana):
    """**`NFR-3`, PROVED ON THE STATEMENT RATHER THAN ON THE ANSWER.**

    A filter that pulled the set and narrowed it in Python returns exactly the
    same rows as one that narrows in SQL, so **no assertion about the ANSWER
    can tell the two apart** — which is how `GET /outstandings` came to sort in
    Python and be found only by reading it. `CLAUDE.md` names four such
    breaches and says not to add a fifth, so this reads the SQL the server
    actually sent: the state predicate must be in the `WHERE`, and the page
    must be cut by `LIMIT` and not by a slice of a list already in memory.

    At 40,000 accounts — the top of T5 — the difference is the whole table.
    """
    with tenant_ctx(brazos):
        _build_row(dana, no="CON-A", address="40 First Ave", units=1, done=0, orders=1,
                   target="2026-09-10", waiting_on=None, shape="requested", age_days=3)
        _build_row(dana, no="CON-Z", address="41 Second Ave", units=1, done=1, orders=1,
                   target="2026-09-12", waiting_on=None, shape="activated", age_days=2)

        with CaptureQueriesContext(db_connection) as captured:
            connection_reads.list_connections(filters={"state": "activated"}, per=50)
        rows_sql = [
            entry["sql"]
            for entry in captured.captured_queries
            if "FROM" in entry["sql"] and "connections" in entry["sql"] and "LIMIT" in entry["sql"]
        ]
        assert rows_sql, "the page itself must be a SELECT with a LIMIT"
        assert any(
            '"state"' in sql and "WHERE" in sql for sql in rows_sql
        ), "the state chip must reach the WHERE clause, not a Python loop"

        with CaptureQueriesContext(db_connection) as open_capture:
            connection_reads.list_connections(filters={"state": "open"}, per=50)
        assert any(
            "IN (" in entry["sql"] and "WHERE" in entry["sql"]
            for entry in open_capture.captured_queries
            if "connections" in entry["sql"]
        ), "`open` is a set and is asked for as `state IN (…)` in SQL"


def test_a_connection_state_we_do_not_serve_returns_nothing_never_everything(brazos, dana):
    """Case 4 — a value outside the vocabulary narrows to nothing rather than
    falling back to the whole tab while the chip on screen names a filter."""
    with tenant_ctx(brazos):
        _build_row(dana, no="CON-A", address="40 First Ave", units=1, done=0, orders=1,
                   target="2026-09-10", waiting_on=None, shape="requested", age_days=3)
        assert connection_reads.list_connections(filters={"state": "banana"})["total"] == 0


def test_filtering_new_connects_by_state_does_NOT_answer_OQ_371(brazos, dana):
    """**THE SECOND DELIBERATELY NEGATIVE ASSERTION.** OQ-371 asks which
    EXCLUSIVE tab holds a build that is `partly_activated` AND waiting.
    `f.state` returns the builds in a state and claims nothing about which tab
    owns them, so `?segment=` still refuses everything but `all`.
    """
    with tenant_ctx(brazos):
        with pytest.raises(NotImplementedError):
            connection_reads.list_connections(segment="partly_activated")
