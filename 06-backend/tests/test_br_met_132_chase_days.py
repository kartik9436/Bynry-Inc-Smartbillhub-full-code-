# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-019 (the S25 Missing chip) · US-MET-018 (completeness bar +
#           chase list) · US-MET-012 (the derived Pending rows)
#           Screens: S25
# Change:   CR-038 — BR-MET-132, the chip's window predicate
# Rules:    BR-MET-132 (CONFIRMED, PO 2026-08-26, closes OQ-389 and amends
#           US-MET-019 §5's literal reading) · BR-MET-057 (the cycle read
#           window drives expectations) · BR-MET-049 (the plan-driven required
#           set) · CLAUDE.md rule 1 (tenant scoping)
# Tests:    the four clauses of BR-MET-132, each with the PO's own dates
# ───────────────────────────────────────────────────────
"""BR-MET-132 — the Missing chip counts through the chase days.

THE RULE, VERBATIM (04-docs/05-modules/04-metering/02-business-rules.md,
CONFIRMED, PO 2026-08-26):

  *"Keep counting until the run consumes the period — those are the chase
  days"*. Worked case: CY-001's reading window closes Aug 20 and the run is
  Aug 25; on Aug 22 sixty meters are unread. Under the literal §5 ("open
  windows only") the chip read **0** on exactly the days a clerk chases
  stragglers. The chip therefore counts missing required records for windows
  that are OPEN **or CLOSED-BUT-UNBILLED**, and drops a period only when its
  bill run has consumed it.

Every date below is the PO's own: window **16–20 Aug 2026**, asked on
**22 Aug**, run completing **25 Aug**.

═══════════════════════════════════════════════════════════════════════════
RED PROOF — MEASURED, NOT ASSERTED (hard-won law 7)
═══════════════════════════════════════════════════════════════════════════
The pre-ruling predicate was put back in `apps/metering/completeness.py` — the
chaseable set narrowed to `frozenset({"open"})`, and both `closed_unbilled`
branches of `current_window` removed, which is US-MET-019 §5 read literally and
is exactly what OQ-389 measured. MEASURED, verbatim:

    $ python3 -m pytest tests/test_br_met_132_chase_days.py -q
    11 failed, 2 passed in 96.00s

    FAILED test_br_met_132__the_chip_counts_a_closed_window_the_run_has_not_billed
    FAILED test_br_met_132__current_window_names_the_closed_unbilled_state
    FAILED test_br_met_132__an_issued_run_consumes_the_period_and_the_chip_drops_it
    FAILED test_br_met_132__a_draft_run_does_not_consume_the_period[draft]
    FAILED test_br_met_132__a_draft_run_does_not_consume_the_period[previewing]
    FAILED test_br_met_132__a_draft_run_does_not_consume_the_period[issuing]
    FAILED test_br_met_132__a_draft_run_does_not_consume_the_period[failed]
    FAILED test_br_met_132__a_draft_run_does_not_consume_the_period[cancelled]
    FAILED test_br_met_132__the_first_run_date_path_chases_too
    FAILED test_br_met_132__the_pending_rows_follow_the_chip
    FAILED test_br_met_132__another_tenants_issued_run_consumes_nothing

The first one is the defect in one line — the chip reading **0** over four
records nobody has read, on a day the bill has not gone out:

>       assert counts["missing"] == RECORDS_OWED_PER_METER, (
            "BR-MET-132: on 22 Aug, four days after the 16-20 Aug window closed
            and three days before the run, the four unread records must still be
            counted - this is the chase-day zero OQ-389 measured"
E       AssertionError: assert 0 == 4

The two that stayed GREEN under the revert are the two that must: `before_open`
(US-MET-018 TC-6 is untouched by this rule) and the widened-run overlap case,
which reaches 0 by both readings. Undoing the revert: `13 passed in 79.45s`.
"""

from datetime import date

import pytest

from apps.billing.models import BillRun
from apps.metering import completeness

from tests.test_us_met_018_completeness import (  # noqa: F401 — same fixture world
    routed_meters,
    seed_cycle_row,
)
from tests.test_us_met_018_plan_registers import (  # noqa: F401
    plan_with_version,
    planned_meter,
)
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    commit_read,
    csv_body,
    lonestarridge_payload,
    make_premises,
    make_unit,
    provisioned_tenant,
    seed_config,
    staff_actor,
    stage,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


#: The PO's own dates. The window is 16–20 Aug; the run lands 25 Aug; the
#: question is asked on 22 Aug, in the middle of the chase days.
WINDOW_START_DAY = 16
WINDOW_DAYS = 5
CHASE_DAY = date(2026, 8, 22)
BEFORE_THE_WINDOW = date(2026, 8, 12)
IN_THE_WINDOW = date(2026, 8, 18)
AFTER_THE_RUN = date(2026, 8, 26)

#: A TOU plan expects four records per meter — three window channels plus
#: `total` (BR-MET-049 read with BR-MET-059/BR-MET-052's sum-sanity). Nothing
#: is read in these fixtures, so all four are owed.
RECORDS_OWED_PER_METER = 4


def a_cycle_with_unread_meters(actor, tenant, *, code="CY-001", first_run=None):
    """One active cycle, one routed TOU meter on it, and not a single read.

    The §4 seed's sixty unread meters at unit-test size: the arithmetic the
    chip does is per-record, so one meter owing four records proves the same
    predicate as sixty owing two hundred and forty.
    """
    cycle = seed_cycle_row(
        tenant, code=code, start_day=WINDOW_START_DAY, days_to_complete=WINDOW_DAYS
    )
    if first_run is not None:
        cycle.first_run_date = first_run
        cycle.save(update_fields=["first_run_date"])
    plan = plan_with_version(
        tenant,
        name="TOU Residential",
        model="time_of_use",
        windows=("tou_on", "tou_mid", "tou_off"),
    )
    routed_meters(actor, tenant, cycle, plan, asset_no="M-7451", route_code="Route 3")
    return cycle


def a_run_over(tenant, cycle, *, status, start=date(2026, 8, 16), end=date(2026, 8, 20)):
    """A bill run over the cycle's period, in a named status.

    Written straight onto billing's own table: what is under test here is the
    metering predicate that READS a run, not `create_run`'s validation, which
    is US-BIL-001's business and is proven there.
    """
    return BillRun.objects.create(
        tenant=tenant,
        cycle_id=cycle.id,
        period_start=start,
        period_end=end,
        status=status,
        idempotency_key=f"{cycle.code}:{start}:{end}:{status}",
    )


# ── clause 1 · a CLOSED window nobody has billed is still counted ───────────


def test_br_met_132__the_chip_counts_a_closed_window_the_run_has_not_billed(brazos, dana):
    """BR-MET-132, PO verbatim: *"Keep counting until the run consumes the
    period — those are the chase days"*.

    The window closed on 20 Aug. It is 22 Aug. No run has issued. Four
    plan-required records have never been read, and the chip says so.
    """
    with tenant_ctx(brazos):
        a_cycle_with_unread_meters(dana, brazos)
        counts = completeness.missing_records_count(today=CHASE_DAY)

    assert counts["missing"] == RECORDS_OWED_PER_METER, (
        "BR-MET-132: on 22 Aug, four days after the 16-20 Aug window closed and three "
        "days before the run, the four unread records must still be counted - this is "
        "the chase-day zero OQ-389 measured"
    )
    assert counts["unresolved_meters"] == 0


def test_br_met_132__current_window_names_the_closed_unbilled_state(brazos, dana):
    """The state is a VALUE a surface can group on, not prose: `open` while it
    runs, `closed_unbilled` through the chase days, `before_open` once the run
    has consumed the period and the next window has not started."""
    with tenant_ctx(brazos):
        cycle = a_cycle_with_unread_meters(dana, brazos)

        assert completeness.current_window(cycle, IN_THE_WINDOW)["state"] == "open"
        assert completeness.current_window(cycle, CHASE_DAY)["state"] == "closed_unbilled"

        a_run_over(brazos, cycle, status="issued")
        assert completeness.current_window(cycle, CHASE_DAY)["state"] == "before_open"


# ── clause 2 · the drop condition is the RUN, not the calendar ──────────────


def test_br_met_132__an_issued_run_consumes_the_period_and_the_chip_drops_it(brazos, dana):
    """*"…and drops a period only when its bill run has consumed it."* The
    same tenant, the same unread meters, the same day — one issued run is
    the whole difference between 4 and 0."""
    with tenant_ctx(brazos):
        cycle = a_cycle_with_unread_meters(dana, brazos)
        before = completeness.missing_records_count(today=CHASE_DAY)["missing"]
        a_run_over(brazos, cycle, status="issued")
        after = completeness.missing_records_count(today=CHASE_DAY)["missing"]

    assert before == RECORDS_OWED_PER_METER
    assert after == 0, "an issued run over 16-20 Aug consumes the period (BR-MET-132)"


@pytest.mark.parametrize("status", ["draft", "issuing", "abandoned"])
def test_br_met_132__a_draft_run_does_not_consume_the_period(brazos, dana, status):
    """The OMISSIONS are the rule: a draft can be thrown away, an `issuing` run
    has put nothing out yet, and an `abandoned` run ended having issued nothing.
    A period with one of those over it has NOT been billed and its meters still
    need chasing.

    ⚠ **THIS CASE PARAMETRISED OVER `previewing`, `failed` AND `cancelled` UNTIL
    2026-09-15 AND NO WRITER IN THIS PRODUCT HAS EVER WRITTEN ANY OF THE THREE**
    (`BR-BIL-1045`, `DEF-BIL-5352`). It passed for the emptiest possible reason:
    the chip counts a period as unconsumed for EVERY word outside
    `RUN_STATUSES_THAT_CONSUME_A_PERIOD`, and that set was `{"completed"}` —
    which nothing wrote either, so the chip never dropped a period in its life
    and this case could not have failed whatever word it was handed.

    The three fictional words are replaced by the three real ones, and the
    argument each stood for survives the rename: `abandoned` is what `failed`
    and `cancelled` were reasoning about, and `previewing` never existed.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle_with_unread_meters(dana, brazos)
        a_run_over(brazos, cycle, status=status)
        counts = completeness.missing_records_count(today=CHASE_DAY)

    assert counts["missing"] == RECORDS_OWED_PER_METER, (
        f"a run in status {status!r} has issued nothing, so it consumes no period "
        "(BR-MET-132 / RUN_STATUSES_THAT_CONSUME_A_PERIOD)"
    )


def test_br_met_132__a_run_widened_past_the_window_still_consumes_it(brazos, dana):
    """Billing's predicate is OVERLAP, not equality. The wizard proposes the
    cycle's own occurrence, but a clerk may widen the period — a run over
    1–31 Aug covers a 16–20 Aug reading window and really did bill its
    reads."""
    with tenant_ctx(brazos):
        cycle = a_cycle_with_unread_meters(dana, brazos)
        a_run_over(
            brazos,
            cycle,
            status="issued",
            start=date(2026, 8, 1),
            end=date(2026, 8, 31),
        )
        counts = completeness.missing_records_count(today=CHASE_DAY)

    assert counts["missing"] == 0


# ── clause 3 · before the window opens there is still nothing to chase ──────


def test_br_met_132__a_window_that_has_not_opened_still_counts_nothing(brazos, dana):
    """BR-MET-132 amended the END of the window, never its start. US-MET-018
    TC-6 is untouched: on 12 Aug the 16–20 Aug window has not opened, so
    nothing is expected and nothing is chased.

    ⚠ This is also the phantom-backlog guard. A cycle with no `first_run_date`
    has never RUN — the previous month's derived window is a rendering, not an
    occurrence that happened — so a freshly configured cycle must not arrive
    already carrying last month's imaginary gap.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle_with_unread_meters(dana, brazos)
        counts = completeness.missing_records_count(today=BEFORE_THE_WINDOW)
        state = completeness.current_window(cycle, BEFORE_THE_WINDOW)

    assert counts["missing"] == 0
    assert state["state"] == "before_open"
    assert state["period_start"] == date(2026, 8, WINDOW_START_DAY)


# ── clause 4 · the ruled generator path (a cycle WITH a first run) ──────────


def test_br_met_132__the_first_run_date_path_chases_too(brazos, dana):
    """A cycle with a `first_run_date` walks `period_engine`'s ruled generator
    (OQ-339/340/341 closed) rather than the month-anchored fallback, and
    BR-MET-132 applies identically: `latest_opened_window` names 16–20 Aug on
    22 Aug, where `upcoming_windows` had already moved on to September."""
    with tenant_ctx(brazos):
        cycle = a_cycle_with_unread_meters(dana, brazos, first_run=date(2026, 8, 16))
        chasing = completeness.missing_records_count(today=CHASE_DAY)
        window = completeness.current_window(cycle, CHASE_DAY)

        a_run_over(brazos, cycle, status="issued")
        settled = completeness.missing_records_count(today=CHASE_DAY)
        after = completeness.current_window(cycle, CHASE_DAY)

    assert chasing["missing"] == RECORDS_OWED_PER_METER
    assert window["state"] == "closed_unbilled"
    assert (window["period_start"], window["period_end"]) == (
        date(2026, 8, 16),
        date(2026, 8, 20),
    )
    assert settled["missing"] == 0
    # The period is consumed, so the NEXT occurrence is what is offered.
    assert after["state"] == "before_open"
    assert after["period_start"] == date(2026, 9, 16)


# ── the chip's number has rows behind it ────────────────────────────────────


def test_br_met_132__the_pending_rows_follow_the_chip(brazos, dana):
    """Hard-won law 2, in the one place the two surfaces meet: a chip reading
    "4 missing" that drills into an empty list is a number with nothing behind
    it. `pending_read_entries` shares `CHASEABLE_WINDOW_STATES` with the chip
    so the two cannot disagree."""
    with tenant_ctx(brazos):
        cycle = a_cycle_with_unread_meters(dana, brazos)
        chasing = completeness.pending_read_entries(today=CHASE_DAY)
        a_run_over(brazos, cycle, status="issued")
        settled = completeness.pending_read_entries(today=CHASE_DAY)

    assert len(chasing) == RECORDS_OWED_PER_METER
    assert sorted(row["channel"] for row in chasing) == [
        "total",
        "tou_mid",
        "tou_off",
        "tou_on",
    ]
    assert settled == []


# ── tenant scoping (CLAUDE.md rule 1) ───────────────────────────────────────


def test_br_met_132__another_tenants_issued_run_consumes_nothing(brazos, dana):
    """CLAUDE.md rule 1, on the one query this rule added. Lone Star Ridge
    completes a run over the very same dates against the very same cycle id;
    Brazos Bend's chip must not go quiet on a neighbour's bill."""
    lonestar, _result = provisioned_tenant(lonestarridge_payload())

    with tenant_ctx(brazos):
        cycle = a_cycle_with_unread_meters(dana, brazos)

    with tenant_ctx(lonestar):
        BillRun.objects.create(
            tenant=lonestar,
            cycle_id=cycle.id,
            period_start=date(2026, 8, 16),
            period_end=date(2026, 8, 20),
            status="issued",
            idempotency_key="lonestar-run-over-brazos-period",
        )

    with tenant_ctx(brazos):
        counts = completeness.missing_records_count(today=CHASE_DAY)

    assert counts["missing"] == RECORDS_OWED_PER_METER


# ── Lifecycle ─────────────────────────────────────────────
# packet: BR-MET-132 (CONFIRMED 2026-08-26) + OQ-389's closure row + US-MET-019
#         §5 (the amended sentence) + US-MET-018 §2/TC-6
# generated: 2026-08-26 by the CR-038 BR-MET-132/133 lane
# checklist: A✔ B✔(the S25 chip renders the real count and its caption states
#            the amended predicate) C✔ D✔ E✔ F✔ G✔ H=deferred(not a 🔒 path —
#            no money, no rate, no RLS policy, no idempotency key; this counts
#            registers and reads one boolean off `bill_runs`)
# exceptions: (1) ONE window is examined — the most recent to have OPENED — so
#            an older period a run skipped is not counted. The PO's worked case
#            is a single period and the alternative has no floor; argued in
#            `completeness.current_window` and recorded in the decision log.
#            (2) on the no-first-run fallback path the closed-unbilled state is
#            offered for THIS month's window only, so a freshly configured
#            cycle does not arrive carrying last month's imaginary backlog.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
