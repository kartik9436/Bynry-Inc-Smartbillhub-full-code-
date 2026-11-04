# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-033 (EP-RBS-05) — CR-075 wave R′, runbook 21.
# Rules:    BR-RBS-003 · BR-RBS-004 · BR-RBS-006 · BR-RBS-011 · BR-RBS-012 ·
#           BR-RBS-019 · BR-RBS-020 · BR-RBS-021 · BR-RBS-023 · BR-RBS-027 ·
#           BR-RBS-035 · BR-MET-020 · RBR-18 · CLAUDE.md hard rule 3 ·
#           B14 rules 31, 32, 33
# Tests:    this file. The PostgreSQL half — the real seams and the savepoint —
#           is tests/test_rbs_reads_runbooks_pg.py.
# Impacts:  apps/runbooks/definitions/read_validation.py
# ───────────────────────────────────────────────────────
"""Runbook 21, against the rules rather than against itself.

**EVERY CASE HERE ASSERTS A RULE AND NOT AN IMPLEMENTATION.** A test asserting
*"step 3 returns a dict with five keys"* would go green over a runbook that had
stopped carrying units on its totals, which is the one thing in this runbook
that cannot move.

⚠ **THE SEAMS ARE REPLACED, AND WHAT THAT DOES AND DOES NOT PROVE IS STATED.**
These cases hand the runbook fixed answers so the DECISIONS can be exercised — a
meter-day in two units, a silent meter, a gap over the limit, a cap that
refuses, a sample row — none of which one seeded batch happens to contain
together. **It proves the runbook's reasoning and NOTHING about the seams**: a
seam returning the wrong shape passes every case in this file. That is what
`tests/test_rbs_reads_runbooks_pg.py` is for, and it runs the REAL seams against
real rows on real PostgreSQL. Both numbers are quoted in the lane report;
neither is quoted alone.
"""

import pytest

from apps.runbooks.contract import BLOCK_TYPES
from apps.runbooks.definitions import read_validation as rv
from apps.runbooks.engine import executor

#: ⚠ **THE WHOLE FILE NEEDS A DATABASE, AND NOT BECAUSE THESE CASES READ ONE.**
#: The executor opens a nested `transaction.atomic()` around every per-record
#: step — the SAVEPOINT hard-won law 14 makes non-negotiable — and
#: `transaction.atomic()` asks for a connection before it does anything else.
pytestmark = pytest.mark.django_db


def _day(
    meter_no="WM-04471",
    day="2026-09-06",
    *,
    asset_id=None,
    intervals=96,
    quantity="1140",
    unit="gal",
    unit_conflict=False,
    first_at="2026-09-06T00:00:00",
    last_at="2026-09-06T23:45:00",
    service="water",
    sample=False,
    zero=0,
):
    """One rolled-up meter-day, in the shape the seam hands across."""
    return {
        "asset_id": asset_id or f"asset-{meter_no}",
        "meter_no": meter_no,
        "channel": "total",
        "day": day,
        "intervals": intervals,
        "zero_intervals": zero,
        "nonzero_intervals": max(intervals - zero, 0),
        "quantity": quantity,
        "unit": unit,
        "unit_conflict": unit_conflict,
        "first_at": first_at,
        "last_at": last_at,
        "service": service,
        "is_sample": sample,
    }


def _batch(days, *, intervals=None, unreadable=0):
    return {
        "batch_id": "batch-21",
        "batch_no": "AMI-0091",
        "file_name": "ami-2026-09-06.csv",
        "status": "validated",
        "source_kind": "ami_replay",
        "source_detail": None,
        "service": "water",
        "intervals": 96 * len(days) if intervals is None else intervals,
        "intervals_unreadable": unreadable,
        "meters": len({one["asset_id"] for one in days}),
        "meter_days": list(days),
    }


def _limits(high="5000", unit="gal", service="water", source="service"):
    return {
        "general": {"present": True, "est_method": "average", "est_max_consecutive": 3},
        "services": [
            {
                "service": service,
                "source": source,
                "high_pct": "300.000000",
                "high_abs_value": high,
                "high_abs_unit": unit,
                "low_pct": "20.000000",
            }
        ],
        "integrity_rules": [],
        "judgment_rules": [],
        "legacy_fallback_services": ["water"],
    }


def _normal(average="380", unit="gal", last_good_day="2026-09-05"):
    return {
        "average_per_day": average,
        "unit": unit,
        "unit_conflict": False,
        "reads_seen": 90,
        "days_covered": 90,
        "last_good_day": last_good_day,
        "window_days": 90,
        "window_start": "2026-06-08",
        "window_end": "2026-09-06",
    }


@pytest.fixture
def seams(monkeypatch):
    """Fixed answers for the four reads runbook 21 makes.

    Everything defaults to *nothing is connected and nothing has landed*, which
    is the STOP — so a case that forgets to give the runbook work cannot
    accidentally assert on a happy path.
    """
    state = {"connections": [], "batch": None, "limits": _limits(), "normals": {}, "cap": None}
    monkeypatch.setattr(
        rv.integrations_seam, "live_connections", lambda keys: list(state["connections"])
    )
    monkeypatch.setattr(rv.metering_seam, "interval_batch", lambda batch_id=None: state["batch"])
    monkeypatch.setattr(rv.metering_seam, "read_validation_limits", lambda: state["limits"])
    monkeypatch.setattr(
        rv.metering_seam,
        "meter_normals",
        lambda ids, *, as_of, days=90: {
            one: state["normals"].get(one, _normal()) for one in ids
        },
    )
    monkeypatch.setattr(rv, "_cap", lambda ctx: state["cap"])
    return state


def _run(params=None):
    definition = rv.RUNBOOK
    ctx = executor.build_context(definition, tenant_id="t", run_id=None, params=params or {})
    return executor.execute(definition, ctx=ctx)


def _blocks(result):
    return {block["block"]: block["payload"] for block in result.report}


def _checked(result, step):
    return (result.set_results.get(step) or {}).get("checked") or {}


def _tiles(result):
    return {tile["id"]: tile for tile in _blocks(result)["kpis"]["tiles"]}


# ── step 1 · the two doors, and the stop ──────────────────────────────────


def test_both_doors_shut_stops_the_run_and_names_both_absences(seams):
    """PO 2026-09-06: *"in absence of API conenctions … that is a valid case"*."""
    result = _run()
    stop = (result.set_results[rv.STEP_GATHER])["stop"]
    assert stop["headline"] == "No intervals to validate."
    assert "No meter connection is set up." in stop["detail"]
    assert "No interval batch is waiting either" in stop["detail"]
    assert stop["fix_label"] == "Open reads"


def test_a_connection_with_nothing_landed_is_its_own_sentence(seams):
    """*"No connection"* and *"nothing landed"* have different fixes."""
    seams["connections"] = [
        {"key": "meters_itron", "display_name": "Itron", "enabled": True, "status": "working"}
    ]
    stop = (_run().set_results[rv.STEP_GATHER])["stop"]
    assert stop["headline"] == "Nothing has landed yet."
    assert "Itron is connected" in stop["detail"]  # the fixture was "MDM" until CR-110-BRC04


def test_a_named_batch_that_is_gone_says_so_rather_than_nothing_landed(seams):
    """A batch a clerk CHOSE and that has since been posted is a third state."""
    stop = (_run({"batch": "batch-21"}).set_results[rv.STEP_GATHER])["stop"]
    assert stop["headline"] == "That batch is not here."
    assert "already have been posted" in stop["detail"]


def test_a_stopped_run_reads_never_reached_on_every_later_step(seams):
    """`BR-RBS-027`. A blank cell reads as *nothing wrong*; this one does not."""
    chain = _blocks(_run())["chain"]
    states = [cell["state"] for cell in chain["cells"]]
    assert states == ["bad", "notReached", "notReached", "notReached", "notReached", "notReached"]
    assert {cell["note"] for cell in chain["cells"][1:]} == {"Never reached"}


def test_a_stopped_run_draws_no_kpi_strip(seams):
    """A strip of zeros over a run that examined nothing reads like a clean night.

    Hard-won law 7: *a run that examined nothing and a run that found nothing
    wrong must not read the same.* The strip is ABSENT, not zeroed.
    """
    blocks = _blocks(_run())
    assert "kpis" not in blocks
    assert set(blocks) == {"verdict", "sentence", "chain", "records"}


def test_the_word_failed_appears_nowhere_on_a_stopped_run(seams):
    """A designed answer is not a failure, and the screen must not call it one."""
    text = repr(_run().report).lower()
    assert "failed" not in text
    assert "error" not in text


# ── BR-RBS-019 · the one number this runbook is about ─────────────────────


def test_the_unit_of_work_is_the_meter_day_and_never_the_interval(seams):
    """`RBR-18` restating `BR-RBS-019`: 176,640 intervals become 1,840 records.

    Proved at the shape rather than at the figure: the run pins ONE subject per
    meter-day whatever the interval count, and the declared subject type is
    `meter_day`. A runbook pinned on intervals would open 176,640 savepoints
    for 1,840 decisions.
    """
    seams["batch"] = _batch([_day("WM-1"), _day("WM-2"), _day("WM-3")], intervals=288)
    result = _run()
    assert rv.RUNBOOK.subject_type == "meter_day"
    assert len(result.subjects) == 3
    assert {one.subject_type for one in result.subjects} == {"meter_day"}
    assert _checked(result, rv.STEP_GATHER)["intervals_in_the_batch"] == 288
    assert _checked(result, rv.STEP_GATHER)["meter_days_out"] == 3


def test_the_rollup_is_a_kpi_tile_so_the_two_figures_can_be_reconciled(seams):
    """176,640 in and 1,840 out is a CLAIM only when both numbers are shown.

    And the third — the rows the importer could not read — is what makes the
    subtraction possible. Without it a reader has to assume they net to zero.
    """
    seams["batch"] = _batch([_day("WM-1"), _day("WM-2")], intervals=192, unreadable=7)
    tile = _tiles(_run())["rollup"]
    assert tile["value"]["text"] == "192 → 2"
    assert tile["detail"] == "7 could not be read"


# ── CLAUDE.md hard rule 3 · every quantity carries its unit ───────────────


def test_a_quantity_without_a_unit_cannot_even_be_constructed():
    """Hard rule 3, enforced at the object rather than at the screen.

    ⚠ **THIS IS THE CASE THE WHOLE RUNBOOK IS ARRANGED AROUND.** An aggregation
    that drops its unit is a number nobody can check, and this is the one place
    in the module where 176,640 readings are added together.
    """
    with pytest.raises(ValueError) as caught:
        rv.MeterDay(
            asset_id="a",
            meter_no="WM-1",
            channel="total",
            day="2026-09-06",
            intervals=96,
            quantity=rv._decimal("1140"),
            unit=None,
            outcome=rv.OUTCOME_PLANNED,
            issue=None,
            reason="x",
            decided_by_rule="y",
            fix_route="reads",
            fix_label="Open read →",
        )
    assert "EXPLICIT unit and one is never assumed" in str(caught.value)


def test_a_meter_day_in_two_units_is_queued_and_never_totalled(seams):
    """Adding gallons to litres produces a number with no meaning at all."""
    seams["batch"] = _batch([_day("WM-9", quantity=None, unit="gal", unit_conflict=True)])
    result = _run()
    row = _blocks(result)["records"]["rows"][0]
    assert row["cells"]["issue"]["text"] == "Two units in one day"
    assert row["cells"]["meter"]["text"] == "WM-9"


def test_a_meter_with_no_unit_is_queued_rather_than_assumed(seams):
    """*Never assume* is the second half of hard rule 3 and the harder half."""
    seams["batch"] = _batch([_day("WM-8", unit=None, quantity=None)])
    row = _blocks(_run())["records"]["rows"][0]
    assert row["cells"]["issue"]["text"] == "No unit on the meter"


def test_every_quantity_a_clerk_reads_carries_its_unit(seams):
    """A column of bare totals invites a comparison nobody can vouch for."""
    seams["batch"] = _batch([_day("WM-7", intervals=60, last_at="2026-09-06T14:45:00")])
    estimates = _blocks(_run())["row_decisions"]["rows"]
    assert estimates, "the short gap should have produced an estimate"
    assert estimates[0]["cells"]["quantity"]["text"].endswith(" gal")


# ── step 2 · the importer's own figures, and what it cannot judge ─────────


def test_a_service_with_no_limits_is_reported_and_never_treated_as_passed(seams):
    """`BR-MET-020` — thresholds are SKIPPED AND REPORTED, with the service NAMED.

    Hard-won law 7's `G32` shape: a check reporting zero over a scope it
    silently excludes is indistinguishable from a clean one.
    """
    seams["limits"] = _limits(source="none")
    seams["batch"] = _batch([_day("WM-5")])
    checked = _checked(_run(), rv.STEP_LIMITS)
    assert checked["services_with_no_limits"] == ["water"]
    assert checked["meter_days_judged_against_a_limit"] == 0


def test_a_limit_in_a_different_unit_is_counted_rather_than_compared(seams):
    """A limit of 50 kgal and a day of 1,140 gal are not comparable numbers."""
    seams["limits"] = _limits(high="50", unit="kgal")
    seams["batch"] = _batch([_day("WM-4")])
    checked = _checked(_run(), rv.STEP_LIMITS)
    assert checked["limit_unit_mismatch"] == 1
    assert checked["meter_days_judged_against_a_limit"] == 0


def test_a_day_above_the_high_limit_is_queued_with_the_tenants_own_figure(seams):
    seams["limits"] = _limits(high="900")
    seams["batch"] = _batch([_day("WM-3", quantity="1140")])
    row = _blocks(_run())["records"]["rows"][0]
    assert row["cells"]["issue"]["text"] == "Above the high limit"


def test_a_register_going_backwards_is_a_rollover_and_not_a_low_reading(seams):
    """99,940 → 00,120 has not consumed a negative amount, and the fix differs."""
    seams["batch"] = _batch([_day("WM-00517", quantity="-99820")])
    row = _blocks(_run())["records"]["rows"][0]
    assert row["cells"]["issue"]["text"] == "Rollover"
    assert row["cells"]["fix"]["label"] == "Confirm rollover →"


# ── step 3 · the gaps, and the cadence this card cannot agree about ───────


def test_the_cadence_is_measured_from_the_timestamps_and_never_assumed(seams):
    """Divergence 2. `RB-121` says *96 intervals* AND *reads arrive hourly*.

    Assuming 96 would report an hourly day as 75% missing; assuming 24 would
    report a quarter-day of 15-minute data as complete. So the spacing is read
    off the readings this meter actually sent.
    """
    hourly = _day("WM-H", intervals=24, first_at="2026-09-06T00:00:00", last_at="2026-09-06T23:00:00")
    quarter = _day("WM-Q", intervals=96, first_at="2026-09-06T00:00:00", last_at="2026-09-06T23:45:00")
    seams["batch"] = _batch([hourly, quarter])
    plan = {one["meter_no"]: one for one in _run().set_results[rv.STEP_GAPS]["plan"]}
    assert plan["WM-H"]["expected_intervals"] == 24
    assert plan["WM-Q"]["expected_intervals"] == 96
    assert plan["WM-H"]["missing_intervals"] == 0
    assert plan["WM-Q"]["missing_intervals"] == 0


def test_a_silent_meter_is_a_different_finding_from_a_short_gap(seams):
    """One is estimated; the other dispatches a crew. They must not read alike."""
    silent = _day("WM-01128", intervals=0, quantity="0", first_at=None, last_at=None, zero=0)
    seams["batch"] = _batch([silent])
    seams["normals"] = {silent["asset_id"]: _normal(last_good_day="2026-09-02")}
    checked = _checked(_run(), rv.STEP_GAPS)
    assert checked["silent_meters"] == 1
    assert checked["meter_days_with_a_short_gap"] == 0


def test_every_queued_exception_carries_its_last_good_day(seams):
    """`RB-121`: *"each queued meter with its last good day"* — S-4, on the row.

    It is what a field crew is dispatched on and what a clerk deciding whether
    to estimate needs, and one fact serves both.
    """
    silent = _day("WM-01128", intervals=0, quantity="0", first_at=None, last_at=None)
    seams["batch"] = _batch([silent])
    seams["normals"] = {silent["asset_id"]: _normal(last_good_day="2026-09-02")}
    row = _blocks(_run())["records"]["rows"][0]
    assert row["cells"]["last_good"]["text"] == "2026-09-02"


def test_a_meter_that_never_reported_says_so_rather_than_printing_a_date(seams):
    """`None` is not a date and it is not zero — it is *never reported*."""
    silent = _day("WM-NEW", intervals=0, quantity="0", first_at=None, last_at=None)
    seams["batch"] = _batch([silent])
    seams["normals"] = {silent["asset_id"]: _normal(average=None, last_good_day=None)}
    row = _blocks(_run())["records"]["rows"][0]
    assert row["cells"]["last_good"]["text"] == "Never reported"


# ── step 4 · estimation, its policy limit, and the cap ────────────────────


def test_a_short_gap_is_estimated_from_this_meters_own_average(seams):
    """S-1. A fleet average would estimate a bungalow from a block of flats."""
    partial = _day("WM-02871", intervals=68, last_at="2026-09-06T16:45:00")
    seams["batch"] = _batch([partial])
    seams["normals"] = {partial["asset_id"]: _normal(average="210", unit="gal")}
    estimates = _blocks(_run())["row_decisions"]["rows"]
    assert estimates[0]["cells"]["from"]["text"] == "90-day average, gal"
    assert estimates[0]["cells"]["quantity"]["text"] == "210 gal"


def test_a_meter_with_no_history_is_queued_rather_than_estimated_at_zero(seams):
    """**No normal is not a normal of zero.** A zero bills a gap as no use."""
    partial = _day("WM-NOHIST", intervals=68, last_at="2026-09-06T16:45:00")
    seams["batch"] = _batch([partial])
    seams["normals"] = {partial["asset_id"]: _normal(average=None, unit=None)}
    result = _run()
    assert _checked(result, rv.STEP_ESTIMATE)["estimates_impossible_no_history"] == 1
    assert _blocks(result)["records"]["rows"][0]["cells"]["issue"]["text"] == (
        "No history to estimate from"
    )


def test_a_gap_longer_than_the_settings_limit_is_queued_never_estimated(seams):
    """`RB-121` guard, verbatim: *"queued for a person, never estimated"*."""
    stale = _day("WM-04471", intervals=68, last_at="2026-09-06T16:45:00")
    seams["batch"] = _batch([stale])
    seams["normals"] = {stale["asset_id"]: _normal(last_good_day="2026-08-30")}
    row = _blocks(_run())["records"]["rows"][0]
    assert row["cells"]["issue"]["text"] == "Gap too long to estimate"
    assert row["cells"]["fix"]["label"] == "Estimate by hand →"


def test_the_cap_refuses_the_whole_run_and_never_truncates_it(seams):
    """`BR-RBS-006`. Estimating the first 200 and dropping 40 is a failure that
    LOOKS like success: the screen would read *200 estimated* and forty
    meter-days would silently never reach a bill."""
    days = [
        _day(f"WM-{n}", intervals=68, last_at="2026-09-06T16:45:00")
        for n in range(4)
    ]
    seams["batch"] = _batch(days)
    seams["cap"] = 2
    result = _run()
    stop = result.set_results[rv.STEP_ESTIMATE]["stop"]
    assert stop["headline"] == "Too many estimates for one run."
    assert "needs 4 estimates and the limit is 2" in stop["detail"]
    assert "Nothing has been estimated." in stop["detail"]
    assert "kpis" not in _blocks(result)


# ── BR-RBS-002 / 003 · the port that binds no writer ──────────────────────


def test_the_port_is_called_and_its_own_refusal_is_the_outcome(seams):
    """`BR-RBS-003`: dry and live are ONE code path. There is no `is_bound` branch.

    `write_read` binds no writer at all, and not because a wave has not reached
    it — `US-MET-010` says the person who commits a reading certifies it, and an
    automation may not sign one.
    """
    seams["batch"] = _batch([_day("WM-1")])
    result = _run()
    outcomes = {record.outcome for record in result.records}
    assert outcomes == {rv.OUTCOME_PLANNED}
    assert "no writer bound" in result.records[0].decided_by_rule


def test_the_kpi_says_to_validate_while_nothing_is_written(seams):
    """A tile reading *1,802 Validated* over a run that wrote nothing is the
    most dangerous sentence this screen could print."""
    seams["batch"] = _batch([_day("WM-1")])
    tiles = _tiles(_run())
    assert tiles["validated"]["label"] == "To validate"
    assert tiles["validated"]["detail"] == "Planned — nothing is written yet"
    assert tiles["estimated"]["label"] == "To estimate"


def test_it_declares_exactly_one_port_and_it_is_metering_s(seams):
    """`BR-RBS-022`. A runbook holds only the ports it declared."""
    assert rv.RUNBOOK.ports == ("write_read",)


# ── BR-RBS-012 · the guard ────────────────────────────────────────────────


def test_a_sample_meter_day_is_guarded_and_still_counted(seams):
    """`BR-RBS-035` + `BR-RBS-012`: guarded is not the same as absent.

    A row quietly dropped inside a read is invisible on every screen and its
    guard is a check that can never fire.
    """
    seams["batch"] = _batch([_day("WM-REAL"), _day("WM-SAMPLE", sample=True)])
    result = _run()
    assert len(result.subjects) == 2
    assert [one.label for one in result.guarded] == ["WM-SAMPLE · 2026-09-06"]
    assert len(result.records) == 1
    assert _checked(result, rv.STEP_GATHER)["sample_meter_days_guarded"] == 1


# ── BR-RBS-020 / 021 · the report ─────────────────────────────────────────


def test_every_block_is_one_of_the_twelve(seams):
    seams["batch"] = _batch([_day("WM-1")])
    assert set(_blocks(_run())) <= set(BLOCK_TYPES)


def test_no_rule_id_and_no_database_id_reaches_a_clerk(seams):
    """B14 rules 31 and 32. The rule travels in `meta`, which no block draws."""
    seams["batch"] = _batch([_day("WM-3", quantity="99999")])
    seams["limits"] = _limits(high="900")
    rows = _blocks(_run())["records"]["rows"]
    drawn = repr([row["cells"] for row in rows])
    assert "BR-" not in drawn
    assert "asset-" not in drawn
    assert rows[0]["meta"]["decided_by_rule"]


def test_a_refusal_sentence_stays_within_six_words(seams):
    """B14 rule 33. The explanation goes in its own column, not in the label."""
    for label in rv.ISSUE_LABELS.values():
        assert len(label.split()) <= 6, label


def test_every_queued_row_names_a_fix_route(seams):
    """`BR-RBS-011`. A finding with nowhere to go is a defect in the runbook."""
    silent = _day("WM-01128", intervals=0, quantity="0", first_at=None, last_at=None)
    seams["batch"] = _batch([silent, _day("WM-3", quantity="99999")])
    seams["limits"] = _limits(high="900")
    rows = _blocks(_run())["records"]["rows"]
    assert rows
    for row in rows:
        assert row["cells"]["fix"]["to"]


def test_the_empty_state_says_what_was_examined_rather_than_nothing_found(seams):
    """*0 exceptions* over 1,840 meter-days and over nothing are different days."""
    seams["batch"] = _batch([_day("WM-1"), _day("WM-2")], intervals=192)
    empty = _blocks(_run())["records"]["empty"]
    assert "192 intervals rolled up to 2 meter-days" in empty["helper"]
    assert empty["title"] == "Every meter-day validated."


def test_the_records_empty_payload_matches_what_the_renderer_reads(seams):
    """`DEF-RBS-4352` one level down: the renderer reads `title` and `helper`.

    `contract.PAYLOAD_FIELDS` checks the TOP-LEVEL keys of a payload and stops
    there, so a wrong nested shape crosses the wire as untyped JSON and draws an
    error boundary. This asserts the two fields `RecordsBlock.tsx` actually
    reads.
    """
    seams["batch"] = _batch([_day("WM-1")])
    empty = _blocks(_run())["records"]["empty"]
    assert set(empty) == {"title", "helper"}
