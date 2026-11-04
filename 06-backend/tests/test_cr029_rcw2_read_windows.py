# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (PO 2026-08-23) — Routes & Cycles. Wave RC-W2 tasks W2-T1
#           (*"Closing a window writes the W1-T4 record"*) and W2-T5.
#           Screens: SET-06D (Audit tab · Read history)
# Design:   04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §6, §7
# Rules:    D1 (*"yes"* — read windows are first-class CLOSABLE records) ·
#           BR-MET-078 (no money on these surfaces) · CLAUDE.md rule 1 (tenant
#           scoping · RLS FORCE) · rule 6 (idempotency posture) · rule 7 (every
#           change is audited) · BR-MET-048 (who/when/before→after)
# ───────────────────────────────────────────────────────
"""RC-W2-T1 — closing a read window, and the Read-history row it renders.

**THE ACCEPTANCE SHAPE IS THE PO'S OWN SCREENSHOT.** SET-06D's Audit tab draws
a closed window as

    Aug 2026 · Aug 3 · M. Chen · 196 · 196 · Complete
    └ window   └ read on └ reader └ collected └ expected └ result

and B17 §7 W2-T1's *"done when"* names that row: *"a closed window renders the
Read-history row (196 · 196 · Complete)"*. Seven facts, seven columns, and the
first test here is literally that line.

**CLOSING IS IDEMPOTENT AND A CLOSED WINDOW IS HISTORY.** The unique key
`(tenant, route, period_start)` is what makes a second close find the row rather
than write a second history — W1-T4's own words — and the FROM-NEXT rule
(SET-07D: *"Changing the schedule applies from the next window — nothing already
issued changes"*) means the dates on a closed record must not be restated when
the cycle's schedule changes tomorrow.

**NOTHING HERE IS MONEY** (BR-MET-078, hardened by this CR): a read window
counts meters.
"""

from datetime import date

import pytest

from apps.metering import models, read_windows, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

AUG = (date(2026, 8, 1), date(2026, 8, 3))


def _route(actor, code="RT-W2A", cycle_id=None):
    payload = {"code": code, "name": "Downtown walk", "service_codes": ["water"]}
    if cycle_id is not None:
        payload["cycle_id"] = cycle_id
    return services.create_route(actor, payload)


def _cycle(tenant, code="CY-W2A", **overrides):
    fields = {
        "code": code,
        "frequency": "Monthly",
        "start_day": 1,
        "days_to_complete": 3,
        "first_run_date": date(2026, 8, 1),
    }
    fields.update(overrides)
    return models.Cycle.objects.create(tenant=tenant, **fields)


# ═══════════════════════════════════════════════════════════════════════════
# THE ACCEPTANCE ROW — 196 · 196 · Complete
# ═══════════════════════════════════════════════════════════════════════════
def test_w2_t1__closing_a_window_writes_the_read_history_row(brazos, dana):
    """The PO's screenshot, field by field — **minus the Reader (OQ-343)**.

    ⚠ The screenshot reads *"Aug 2026 · Aug 3 · M. Chen · 196 · 196 ·
    Complete"* and this test asserted M. Chen. OQ-343 asked whether D6's
    *"reader — not required"* also removed the reader from a route's HISTORY,
    and the PO ruled on 2026-08-23, verbatim: *"B: no reader anywhere, correct
    the screenshot and drop the stored name"*. So the row is **Window · Read on
    · Collected · Expected · Result**, the screenshot is corrected rather than
    followed, and `read_windows.reader` is dropped by migration — the product
    does not keep data no screen shows.
    """
    with tenant_ctx(brazos):
        cycle = _cycle(brazos)
        route = _route(dana, cycle_id=str(cycle.id))
        closed = read_windows.close_read_window(
            dana,
            route_id=route["id"],
            period_start=AUG[0],
            period_end=AUG[1],
            read_on=date(2026, 8, 3),
            collected_count=196,
            expected_count=196,
            skip_count=0,
            result="Complete",
        )
    assert closed["period_start"] == "2026-08-01"
    assert closed["period_end"] == "2026-08-03"
    assert closed["read_on"] == "2026-08-03"
    # OQ-343 — the reader is gone from the payload as well as from the column.
    assert "reader_id" not in closed and "reader_name" not in closed
    assert closed["collected"] == 196
    assert closed["expected"] == 196
    assert closed["skips"] == 0
    assert closed["result"] == "Complete"
    assert closed["closed_at"] is not None


def test_w2_t1__the_window_carries_the_cycle_that_produced_it(brazos, dana):
    """W1-T4: *"a window whose cycle later moves still knows which calendar
    produced it"*. The cycle rides along from the route at close time."""
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, code="CY-W2B")
        route = _route(dana, code="RT-W2B", cycle_id=str(cycle.id))
        closed = read_windows.close_read_window(
            dana,
            route_id=route["id"],
            period_start=AUG[0],
            period_end=AUG[1],
            read_on=date(2026, 8, 3),
            collected_count=10,
            expected_count=10,
            result="Complete",
        )
    assert closed["cycle_id"] == str(cycle.id)


def test_w2_t1__a_partly_read_window_states_its_skips_rather_than_hiding_them(brazos, dana):
    """W1-T4: *"a skip is neither collected nor missing-by-accident"*, so
    "196 of 200" is never silently "196 of 196"."""
    with tenant_ctx(brazos):
        route = _route(dana, code="RT-W2C")
        closed = read_windows.close_read_window(
            dana,
            route_id=route["id"],
            period_start=AUG[0],
            period_end=AUG[1],
            read_on=date(2026, 8, 4),
            collected_count=190,
            expected_count=196,
            skip_count=6,
            result="Incomplete",
        )
    assert (closed["collected"], closed["expected"], closed["skips"]) == (190, 196, 6)
    assert closed["result"] == "Incomplete"


def test_w2_t1__the_result_vocabulary_is_the_schemas_and_nothing_else(brazos, dana):
    """`ck_read_windows_result` allows Complete | Incomplete. A third word is
    refused HERE, by name, rather than at the database — a constraint violation
    is a 500 and a refusal is a sentence."""
    from core import errors

    with tenant_ctx(brazos):
        route = _route(dana, code="RT-W2D")
        with pytest.raises(errors.ValidationError) as caught:
            read_windows.close_read_window(
                dana,
                route_id=route["id"],
                period_start=AUG[0],
                period_end=AUG[1],
                read_on=date(2026, 8, 3),
                collected_count=1,
                expected_count=1,
                result="Partly done",
            )
    assert caught.value.field_errors[0]["field"] == "result"


def test_w2_t1__the_counts_are_never_derived_from_each_other(brazos, dana):
    """⚠ **`result` IS STATED, NEVER INFERRED.** Nothing rules how a skip counts
    towards "Complete" — 190 collected + 6 skipped of 196 could be either — so
    the closer says which it was and this module does not guess. Asserted by
    keeping a Complete window whose collected count is short of expected."""
    with tenant_ctx(brazos):
        route = _route(dana, code="RT-W2E")
        closed = read_windows.close_read_window(
            dana,
            route_id=route["id"],
            period_start=AUG[0],
            period_end=AUG[1],
            read_on=date(2026, 8, 3),
            collected_count=190,
            expected_count=196,
            skip_count=6,
            result="Complete",
        )
    assert closed["result"] == "Complete"


# ═══════════════════════════════════════════════════════════════════════════
# IDEMPOTENCE AND HISTORY
# ═══════════════════════════════════════════════════════════════════════════
def test_w2_t1__closing_the_same_window_twice_writes_one_record(brazos, dana):
    """CLAUDE.md rule 6's posture, and W1-T4's stated reason for the unique key:
    *"a second close finds the row rather than writing a second history"*."""
    with tenant_ctx(brazos):
        route = _route(dana, code="RT-W2F")
        first = read_windows.close_read_window(
            dana,
            route_id=route["id"],
            period_start=AUG[0],
            period_end=AUG[1],
            read_on=date(2026, 8, 3),
            collected_count=196,
            expected_count=196,
            result="Complete",
        )
        second = read_windows.close_read_window(
            dana,
            route_id=route["id"],
            period_start=AUG[0],
            period_end=AUG[1],
            read_on=date(2026, 8, 9),  # different figures on the retry
            collected_count=3,
            expected_count=196,
            result="Incomplete",
        )
    assert second["id"] == first["id"]
    assert second["already_closed"] is True
    # The FIRST close is the history. A retry does not restate it.
    assert (second["collected"], second["read_on"], second["result"]) == (
        196,
        "2026-08-03",
        "Complete",
    )
    assert models.ReadWindow.objects.filter(route_id=route["id"]).count() == 1


def test_w2_t1__a_closed_window_is_not_restated_when_the_schedule_changes(brazos, dana):
    """FROM NEXT (SET-07D): *"Changing the schedule applies from the next window
    — nothing already issued changes."* The record's dates are STORED history,
    so moving the cycle's start day leaves last month's walk exactly as it was.
    """
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, code="CY-W2G")
        route = _route(dana, code="RT-W2G", cycle_id=str(cycle.id))
        read_windows.close_read_window(
            dana,
            route_id=route["id"],
            period_start=AUG[0],
            period_end=AUG[1],
            read_on=date(2026, 8, 3),
            collected_count=196,
            expected_count=196,
            result="Complete",
        )
        services.update_cycle(dana, str(cycle.id), {"start_day": 15, "days_to_complete": 2})
        history = read_windows.read_window_history(route["id"])
    assert [(row["period_start"], row["period_end"]) for row in history] == [
        ("2026-08-01", "2026-08-03")
    ]


def test_w2_t1__the_history_is_newest_first_and_names_no_reader(brazos, dana):
    """SET-06D's Audit tab reads top-down from the most recent walk.

    ⚠ **THIS TEST ASSERTED `reader_name == "M. Chen"` UNTIL 2026-08-23**, from
    the PO's own screenshot. OQ-343 closed with *"B: no reader anywhere, correct
    the screenshot and drop the stored name"*, so it now asserts the ABSENCE —
    inverted rather than deleted, so a later lane restoring the column from the
    screenshot goes red instead of quietly re-adding a field the PO removed.

    ⚠ **SCOPE: `routes.assigned_to` IS NOT TOUCHED.** It predates CR-029, D6
    explicitly preserved the ops tab's read-only reader display, and the PO was
    not asked about it. This ruling is about the after-the-fact *"who walked
    this closed window"*, nothing else.
    """
    with tenant_ctx(brazos):
        route = _route(dana, code="RT-W2H")
        for start, end, read_on in (
            (date(2026, 6, 1), date(2026, 6, 3), date(2026, 6, 3)),
            (date(2026, 7, 1), date(2026, 7, 3), date(2026, 7, 3)),
        ):
            read_windows.close_read_window(
                dana,
                route_id=route["id"],
                period_start=start,
                period_end=end,
                read_on=read_on,
                collected_count=5,
                expected_count=5,
                result="Complete",
            )
        history = read_windows.read_window_history(route["id"])
    assert [row["period_start"] for row in history] == ["2026-07-01", "2026-06-01"]
    assert "reader_name" not in history[0] and "reader_id" not in history[0]
    # …and the columns behind them are gone from the model, not merely unserved.
    assert not [
        field.name
        for field in models.ReadWindow._meta.get_fields()
        if field.name in ("reader", "reader_id")
    ]
    # ⚠ `routes.assigned_to` SURVIVES — D6 preserved it and OQ-343 did not ask.
    assert "assigned_to" in {field.name for field in models.Route._meta.get_fields()}


def test_w2_t1__closing_a_window_is_audited(brazos, dana, audit_rows):
    """CLAUDE.md rule 7 / BR-MET-048 — who closed it, when, and with what."""
    with tenant_ctx(brazos):
        route = _route(dana, code="RT-W2I")
        read_windows.close_read_window(
            dana,
            route_id=route["id"],
            period_start=AUG[0],
            period_end=AUG[1],
            read_on=date(2026, 8, 3),
            collected_count=196,
            expected_count=196,
            result="Complete",
        )
    assert "read_window.closed" in [row["action"] for row in audit_rows]


# ═══════════════════════════════════════════════════════════════════════════
# REFUSALS — tenancy, and a window that ends before it begins
# ═══════════════════════════════════════════════════════════════════════════
def test_w2_t1__another_tenants_route_is_absent_not_closable(brazos, dana, lonestar, erin):
    """HR-1 / CLAUDE.md rule 1: an unknown id and another tenant's id are one
    answer. A foreign key alone would not stop this — PostgreSQL evaluates
    referential integrity outside row-level security."""
    from core import errors

    with tenant_ctx(lonestar):
        theirs = _route(erin, code="RT-W2X")
    with tenant_ctx(brazos):
        with pytest.raises(errors.NotFoundError):
            read_windows.close_read_window(
                dana,
                route_id=theirs["id"],
                period_start=AUG[0],
                period_end=AUG[1],
                read_on=date(2026, 8, 3),
                collected_count=1,
                expected_count=1,
                result="Complete",
            )
    assert models.ReadWindow.objects.filter(route_id=theirs["id"]).count() == 0


def test_w2_t1__a_window_that_ends_before_it_begins_is_refused(brazos, dana):
    from core import errors

    with tenant_ctx(brazos):
        route = _route(dana, code="RT-W2J")
        with pytest.raises(errors.ValidationError):
            read_windows.close_read_window(
                dana,
                route_id=route["id"],
                period_start=date(2026, 8, 3),
                period_end=date(2026, 8, 1),
                read_on=date(2026, 8, 3),
                collected_count=1,
                expected_count=1,
                result="Complete",
            )


# ═══════════════════════════════════════════════════════════════════════════
# THE WRITERLESS TABLE RETIRES — B17 §7 W2-T1 / D1
# ═══════════════════════════════════════════════════════════════════════════
def test_w2_t1__read_schedules_gains_no_row_and_is_read_by_nothing(brazos, dana):
    """D1: the writerless `read_schedules` is REPLACED by the window record.
    RC-W2 stops using it; RC-W5 drops the table (a table is dropped after its
    story is written, not before)."""
    with tenant_ctx(brazos):
        cycle = _cycle(brazos, code="CY-W2K")
        route = _route(dana, code="RT-W2K", cycle_id=str(cycle.id))
        read_windows.close_read_window(
            dana,
            route_id=route["id"],
            period_start=AUG[0],
            period_end=AUG[1],
            read_on=date(2026, 8, 3),
            collected_count=1,
            expected_count=1,
            result="Complete",
        )
        assert models.ReadSchedule.objects.count() == 0
    source = read_windows.__file__.replace(".pyc", ".py")
    with open(source, encoding="utf-8") as handle:
        body = handle.read().split('"""', 2)[-1]
    assert "ReadSchedule" not in body
