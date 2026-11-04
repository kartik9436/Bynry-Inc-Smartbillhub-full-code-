# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (PO 2026-08-23) — Routes & Cycles. Wave RC-W2 tasks W2-T2
#           (the run wizard OFFERS, never forces) and W2-T5 (integration).
#           Screens: S31 step 1 (run picker) · SET-07D (Schedule tab) · S27
# Design:   04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §7
# Rules:    D1 (*"yes"* — the generator; *"the run wizard offers, never
#           forces"*) · D9 (*"when we configure Cycle we are provideing default
#           values; mostly it wil remain as it is but user can over ride them
#           during billing"*) · BR-BIL-005 🔒 (a run is unique on tenant ·
#           cycle · period) · CLAUDE.md rule 4 (financial immutability) ·
#           rule 6 (idempotency) · OQ-339 (the month-end anchor — UNRULED)
# ───────────────────────────────────────────────────────
"""RC-W2-T2 — a proposal is an OFFER, and the idempotency key does not move.

FOUR THINGS ARE DEFENDED HERE
-----------------------------
1. **The cycle proposes.** Picking a cycle now yields the next period without
   anybody typing one — gap G1's *"every period is typed by hand into the run
   wizard"* — with the screenshot's own **Next / Scheduled** statuses.
2. **It never forces.** A run created over a DIFFERENT period than the proposal
   is created, not refused. The proposal is a default, not a rule.
3. **The idempotency key is untouched.** BR-BIL-005 keys a run on
   `(tenant, cycle, period)`; a proposal changes what is TYPED, never what is
   KEYED, so running the proposed period twice is still one run.
4. **FROM NEXT.** *"Changing the schedule applies from the next window —
   nothing already issued changes."* A schedule edit moves the next proposal
   and leaves every existing run's period exactly where it was.

⚠ **AND THE UNRULED CYCLE PROPOSES NOTHING.** A cycle anchored on the 31st
serves an empty proposal list with a stated reason (OQ-339) rather than a window
somebody's call site chose. That is the assertion that stops the clamp leaking
in through the read path.
"""

from datetime import date

import pytest

from apps.billing import models as billing_models
from apps.billing import runs as billing_runs
from apps.metering import models as metering_models
from apps.metering import period_engine, selectors, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

AS_OF = date(2026, 8, 20)


def _cycle(tenant, code="CY-P1", **overrides):
    fields = {
        "code": code,
        "frequency": "Monthly",
        "start_day": 1,
        "days_to_complete": 3,
        "first_run_date": date(2026, 8, 1),
        "bill_day": 5,
        "due_days": 21,
    }
    fields.update(overrides)
    return metering_models.Cycle.objects.create(tenant=tenant, **fields)


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE CYCLE PROPOSES — Next / Scheduled, derived, never stored
# ═══════════════════════════════════════════════════════════════════════════
def test_w2_t2__a_cycle_proposes_its_next_windows_with_the_screenshots_statuses(brazos, dana):
    with tenant_ctx(brazos):
        row = _cycle(brazos)
        served = selectors.cycle_dict(row, as_of=AS_OF)
    assert [
        (w["period_start"], w["period_end"], w["status"]) for w in served["proposed_windows"]
    ] == [
        ("2026-09-01", "2026-09-03", period_engine.STATUS_NEXT),
        ("2026-10-01", "2026-10-03", period_engine.STATUS_SCHEDULED),
        ("2026-11-01", "2026-11-03", period_engine.STATUS_SCHEDULED),
    ]
    assert served["next_period"] == {"period_start": "2026-09-01", "period_end": "2026-09-03"}


def test_w2_t2__the_prefill_carries_the_cycles_own_bill_and_due_defaults(brazos, dana):
    """D9 — the cycle provides the defaults the run may override. The wizard
    prefills from the SAME payload it takes the period from, so no second read
    can disagree with the first."""
    with tenant_ctx(brazos):
        served = selectors.cycle_dict(_cycle(brazos, code="CY-P2"), as_of=AS_OF)
    assert served["bill_day"] == 5
    assert served["due_days"] == 21
    assert served["next_period"] is not None


def test_w2_t3__the_cycle_publishes_the_next_cycle_date(brazos, dana):
    """D8② — *"which date 'closes in 4 days' counts to - Next cycle date"*."""
    with tenant_ctx(brazos):
        served = selectors.cycle_dict(_cycle(brazos, code="CY-P3"), as_of=AS_OF)
    assert served["next_cycle_date"] == "2026-09-01"


def test_w2_t2__a_cycle_with_no_schedule_proposes_nothing_and_says_nothing_false(brazos, dana):
    with tenant_ctx(brazos):
        served = selectors.cycle_dict(
            _cycle(
                brazos, code="CY-P4", start_day=None, days_to_complete=None, first_run_date=None
            ),
            as_of=AS_OF,
        )
    assert served["proposed_windows"] == []
    assert served["next_period"] is None
    assert served["next_cycle_date"] is None
    assert served["schedule_gap"] is None


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE MONTH-END CYCLE — OQ-339 REACHES THE SCREEN AS A WINDOW, NOT A GAP
# ═══════════════════════════════════════════════════════════════════════════
def test_w2_t2__a_month_end_cycle_proposes_the_clamped_window(brazos, dana):
    """⚠ **THIS TEST ASSERTED A STATED ABSENCE UNTIL 2026-08-23.** A cycle
    anchored on the 31st proposed nothing and the payload carried a
    `schedule_gap` naming the silence, because clamping at the call site would
    have answered OQ-339 by call site.

    The PO ruled it — *"there is no 31st feb so we have to manage either 28th or
    29th of Feb."* — so the same cycle now proposes **28 February 2026** and the
    gap is gone. A settings page that used to show a warning shows a window.
    """
    with tenant_ctx(brazos):
        served = selectors.cycle_dict(
            _cycle(brazos, code="CY-P5", start_day=31, first_run_date=date(2026, 1, 31)),
            # After January's own window has ENDED (31 Jan + 3 days = 2 Feb), so
            # the first thing proposed is February's — the ruled clamp.
            as_of=date(2026, 2, 10),
        )
    assert served["proposed_windows"][0]["period_start"] == "2026-02-28"
    assert served["next_period"]["period_start"] == "2026-02-28"
    assert served["next_cycle_date"] == "2026-02-28"
    assert served["schedule_gap"] is None
    # …and March is back on the 31st: the clamp is per occurrence.
    assert served["proposed_windows"][1]["period_start"] == "2026-03-31"


def test_w2_t2__the_list_read_still_carries_every_cycle(brazos, dana):
    """One 31st-anchored cycle must not take the Cycles page down with it —
    which was true when it proposed nothing and is true now that it proposes."""
    with tenant_ctx(brazos):
        _cycle(brazos, code="CY-P6")
        _cycle(brazos, code="CY-P7", start_day=31, first_run_date=date(2026, 1, 31))
        rows = {row["code"]: row for row in selectors.cycles_list()}
    assert set(rows) >= {"CY-P6", "CY-P7"}
    assert rows["CY-P7"]["schedule_gap"] is None
    assert rows["CY-P7"]["proposed_windows"], "a month-end cycle proposes windows now"


def test_w2_t2__an_overlapping_cycle_proposes_its_windows_AND_warns(brazos, dana):
    """OQ-341, ruled: *"you give warning and if user override; let them do it"*.

    So the read serves BOTH — real overlapping windows and a warning that names
    the collision. Not one instead of the other: an operator who overrode the
    warning is entitled to see the schedule they asked for.
    """
    with tenant_ctx(brazos):
        served = selectors.cycle_dict(
            _cycle(
                brazos,
                code="CY-POV",
                frequency="Daily",
                start_day=None,
                days_to_complete=3,
                first_run_date=date(2026, 9, 1),
                bill_day=None,
            ),
            as_of=date(2026, 9, 1),
        )
    windows = served["proposed_windows"]
    assert (windows[0]["period_start"], windows[0]["period_end"]) == ("2026-09-01", "2026-09-03")
    assert (windows[1]["period_start"], windows[1]["period_end"]) == ("2026-09-02", "2026-09-04")
    warning = served["schedule_warning"]
    assert warning["code"] == "cycle_windows_overlap"
    assert warning["days_to_complete"] == 3 and warning["max_days_to_complete"] == 1
    # G28 — no internal provenance in the sentence a utility user reads.
    assert "OQ-" not in warning["detail"] and "BR-" not in warning["detail"]
    assert served["schedule_gap"] is None


# ═══════════════════════════════════════════════════════════════════════════
# 3 · OFFERS, NEVER FORCES — and the idempotency key does not move
# ═══════════════════════════════════════════════════════════════════════════
def test_w2_t2__a_run_can_be_created_over_the_proposed_period(brazos, dana):
    with tenant_ctx(brazos):
        row = _cycle(brazos, code="CY-P8")
        served = selectors.cycle_dict(row, as_of=AS_OF)
        proposal = served["next_period"]
        run = billing_runs.create_run(
            cycle_id=row.id,
            period_start=date.fromisoformat(proposal["period_start"]),
            period_end=date.fromisoformat(proposal["period_end"]),
        )
    assert (run.period_start.isoformat(), run.period_end.isoformat()) == (
        "2026-09-01",
        "2026-09-03",
    )


def test_w2_t2__the_clerk_may_run_a_period_the_cycle_did_not_propose(brazos, dana):
    """*"The run wizard OFFERS, never forces"* (D1). A proposal that could not
    be edited would be a schedule, and B17 §2 is explicit that a cycle is a
    DEFINITION and not a schedule."""
    with tenant_ctx(brazos):
        row = _cycle(brazos, code="CY-P9")
        run = billing_runs.create_run(
            cycle_id=row.id,
            period_start=date(2026, 9, 5),  # not the proposed 1st–3rd
            period_end=date(2026, 9, 8),
        )
    assert run.period_start == date(2026, 9, 5)


def test_w2_t2__running_the_proposal_twice_is_still_one_run(brazos, dana):
    """BR-BIL-005 🔒 — the key is (tenant, cycle, period) and the proposal does
    not touch it. A double-click on "Create run" is refused with the original."""
    with tenant_ctx(brazos):
        row = _cycle(brazos, code="CY-PA")
        served = selectors.cycle_dict(row, as_of=AS_OF)
        start = date.fromisoformat(served["next_period"]["period_start"])
        end = date.fromisoformat(served["next_period"]["period_end"])
        first = billing_runs.create_run(cycle_id=row.id, period_start=start, period_end=end)
        with pytest.raises(billing_runs.DuplicateRun) as refusal:
            billing_runs.create_run(cycle_id=row.id, period_start=start, period_end=end)
    assert refusal.value.original.pk == first.pk
    assert billing_models.BillRun.objects.filter(cycle_id=row.id).count() == 1


def test_w2_t2__two_different_proposals_are_two_different_runs(brazos, dana):
    with tenant_ctx(brazos):
        row = _cycle(brazos, code="CY-PB")
        served = selectors.cycle_dict(row, as_of=AS_OF)
        windows = served["proposed_windows"]
        for window in windows[:2]:
            billing_runs.create_run(
                cycle_id=row.id,
                period_start=date.fromisoformat(window["period_start"]),
                period_end=date.fromisoformat(window["period_end"]),
            )
        keys = set(
            billing_models.BillRun.objects.filter(cycle_id=row.id).values_list(
                "idempotency_key", flat=True
            )
        )
    assert len(keys) == 2


# ═══════════════════════════════════════════════════════════════════════════
# 4 · FROM NEXT — nothing already run moves
# ═══════════════════════════════════════════════════════════════════════════
def test_w2_t2__a_schedule_change_applies_from_the_next_window_only(brazos, dana):
    """SET-07D, verbatim: *"Changing the schedule applies from the next window —
    nothing already issued changes."*"""
    with tenant_ctx(brazos):
        row = _cycle(brazos, code="CY-PC")
        served = selectors.cycle_dict(row, as_of=AS_OF)
        start = date.fromisoformat(served["next_period"]["period_start"])
        end = date.fromisoformat(served["next_period"]["period_end"])
        run = billing_runs.create_run(cycle_id=row.id, period_start=start, period_end=end)

        services.update_cycle(dana, str(row.id), {"days_to_complete": 5})
        row.refresh_from_db()
        after = selectors.cycle_dict(row, as_of=AS_OF)
        run.refresh_from_db()

    # The run keeps the window it was created over…
    assert (run.period_start, run.period_end) == (date(2026, 9, 1), date(2026, 9, 3))
    # …and the CYCLE proposes the NEW length from the next window onward.
    assert after["next_period"] == {"period_start": "2026-09-01", "period_end": "2026-09-05"}


def test_w2_t2__moving_the_start_day_without_the_first_run_proposes_nothing(brazos, dana):
    """⚠ **A REAL CONSEQUENCE OF OQ-340, ASSERTED RATHER THAN HIDDEN.**

    Editing a cycle's start day and leaving its first run where it was produces
    the case OQ-340 was minted for: a cycle in two minds about when its window
    opens. The PO ruled the FIRST RUN wins — *"A: first window 15–17 Sep (start
    day becomes decorative)"* — so the cycle keeps proposing on its first run's
    day and the edited start day drives nothing.

    ⚠ **AND THE PAYLOAD SAYS SO OUT LOUD.** A stored field the engine ignores is
    a field that lies to the operator, so `effective_start_day` carries the day
    the cycle really uses and `start_day_differs` is True. The stored column is
    NOT rewritten — that value is the operator's own.
    """
    with tenant_ctx(brazos):
        row = _cycle(brazos, code="CY-PF")
        # The bill day moves with the read window — BR-MET-009 refuses a bill
        # day that falls before the reading has finished.
        services.update_cycle(
            dana, str(row.id), {"start_day": 12, "days_to_complete": 2, "bill_day": 19}
        )
        row.refresh_from_db()
        after = selectors.cycle_dict(row, as_of=AS_OF)
    assert after["schedule_gap"] is None
    assert row.start_day == 12, "the operator's own column is not rewritten"
    assert after["effective_start_day"] == row.first_run_date.day
    assert after["start_day_differs"] is True
    assert after["proposed_windows"], "the cycle proposes on its first run's day"
    assert all(
        window["period_start"].endswith(f"-{row.first_run_date.day:02d}")
        for window in after["proposed_windows"]
    )


def test_w2_t2__moving_a_route_between_cycles_does_not_restate_a_closed_window(brazos, dana):
    """The route half of FROM NEXT: a route moved to another cycle keeps its
    closed Read history exactly as it was — the record stores the window that
    was walked, and the cycle it names is the calendar that produced it."""
    from apps.metering import read_windows

    with tenant_ctx(brazos):
        old = _cycle(brazos, code="CY-PD")
        new = _cycle(brazos, code="CY-PE", start_day=20, first_run_date=date(2026, 8, 20))
        route = services.create_route(
            dana, {"code": "RT-PD", "service_codes": ["water"], "cycle_id": str(old.id)}
        )
        read_windows.close_read_window(
            dana,
            route_id=route["id"],
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 3),
            read_on=date(2026, 8, 3),
            collected_count=196,
            expected_count=196,
            result="Complete",
        )
        services.update_route(dana, route["id"], {"cycle_id": str(new.id)})
        history = read_windows.read_window_history(route["id"])

    assert len(history) == 1
    assert (history[0]["period_start"], history[0]["period_end"]) == ("2026-08-01", "2026-08-03")
    assert history[0]["cycle_id"] == str(old.id)
