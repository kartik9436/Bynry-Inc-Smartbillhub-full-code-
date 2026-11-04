# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-LED-6640 — `core/sample_fixture.py` held its calendar as
#          `date()` CONSTANTS (June billed, July billed, August read-and-
#          unbilled), so from 1 September 2026 every period-scoped Finance
#          figure read $0.00 on a database holding 80 invoices, 66 payments
#          and 167 journal entries. The screens show the CURRENT accounting
#          period (`BR-TEN-022`, computed never stored) and there is no period
#          picker to move off it.
# Rules:   CLAUDE.md hard rule 4 (the fixture bills nothing new — the unbilled
#          month is the PO's own acceptance test and survives every shift) ·
#          BR-TEN-022 (the accounting period is COMPUTED) · BR-TEN-043 /
#          G6 (a money path reads a DECLARED day, `fixture.TODAY`, never a
#          clock of its own).
# Tests:   this file IS the test. It is the ONLY place the shift is exercised,
#          because `config/settings/test.py` pins `SBH_FIXTURE_TODAY` to the
#          anchor day so every other test sees the 2026 constants unchanged.
#          Delete this file and nothing else goes red — which is why the pin
#          says so in its own comment.
# Impacts: nothing. Pure functions, no database, no clock except in the one
#          case that is ABOUT the clock.
# ───────────────────────────────────────────────────────
"""The demo calendar travels with the real one.

WHAT WOULD MAKE THIS SUITE PASS WRONGLY, ASKED BEFORE IT WAS TRUSTED
=====================================================================
Three things, and each has a test of its own below:

1. **The shift could be a no-op** and every relative assertion would still
   hold on the anchor day. So `test_the_anchor_day_is_the_canonical_calendar`
   pins the offset to zero and the 2026 dates exactly, and every other test
   states a day that is NOT the anchor.
2. **The open month could quietly become BILLED**, which would satisfy "there
   is money in the current period" and would DELETE the Product Owner's
   acceptance test. `test_exactly_one_period_is_unbilled_and_it_is_the_last`
   refuses that in every month it is asked about.
3. **The whole thing could be asserted only against simulated dates** and be
   wrong today. `test_the_open_period_is_the_real_current_month` reads the
   REAL clock on purpose — it is the one assertion in the repo that goes red
   on a date rather than on a change, and that is the defect's own prevention
   column being honoured: *"a test that fails when the current accounting
   period holds no activity, asserted against `date.today()`"*.
"""
from __future__ import annotations

import calendar
import json
import os
import subprocess
import sys
import textwrap
from datetime import date, timedelta
from pathlib import Path

import pytest

from core import sample_fixture as fixture

#: A spread of simulated "todays": the anchor itself, the day the defect was
#: found, both ends of a month, a year boundary, a February, and the two days
#: the clamp exists for. Stated out loud so a reader can check the arithmetic
#: by hand rather than trusting a loop.
SIMULATED_DAYS: tuple[date, ...] = (
    date(2026, 8, 14),   # the anchor — offset 0
    date(2026, 9, 25),   # the day this defect was fixed
    date(2026, 10, 1),   # first of the month: everything clamps
    date(2026, 10, 2),   # the day a bill goes out
    date(2026, 11, 30),  # last day of a 30-day month
    date(2026, 12, 31),  # last day of the year
    date(2027, 1, 3),    # across a year boundary, early in the month
    date(2027, 2, 28),   # a February
    date(2028, 2, 29),   # a leap day
    date(2030, 7, 17),   # four years out — the shift is not a one-month patch
)


def _last_of(day: date) -> int:
    return calendar.monthrange(day.year, day.month)[1]


def test_the_anchor_day_is_the_canonical_calendar() -> None:
    """Offset zero reproduces the signed 2026 constants exactly.

    This is what makes the test-suite pin safe: every test written against
    June/July/August 2026 still sees June/July/August 2026.
    """
    cal = fixture.build_calendar(fixture.FIXTURE_ANCHOR_TODAY)
    assert cal["offset_months"] == 0
    assert cal["opening_read_on"] == date(2026, 5, 31)
    assert cal["busy_day"] == date(2026, 8, 8)
    shape = [
        (p["key"], p["start"], p["end"], p["read_on"], p["bill_on"], p["billed"])
        for p in cal["periods"]
    ]
    assert shape == [
        ("june", date(2026, 6, 1), date(2026, 6, 30), date(2026, 6, 30), date(2026, 7, 2), True),
        ("july", date(2026, 7, 1), date(2026, 7, 31), date(2026, 7, 31), date(2026, 8, 2), True),
        ("august", date(2026, 8, 1), date(2026, 8, 14), date(2026, 8, 14), None, False),
    ]


def test_the_suite_is_pinned_to_the_anchor() -> None:
    """The module-level calendar every other test imports is the canonical one.

    If this goes red, the pin in `config/settings/test.py` has been removed or
    overridden and the whole suite has just started depending on the wall
    clock.
    """
    assert fixture.TODAY == fixture.FIXTURE_ANCHOR_TODAY
    assert fixture.CALENDAR_OFFSET_MONTHS == 0
    assert fixture.PERIODS[0]["start"] == date(2026, 6, 1)
    assert fixture.OPENING_READ_ON == date(2026, 5, 31)
    assert fixture.BUSY_DAY == date(2026, 8, 8)


@pytest.mark.parametrize("today", SIMULATED_DAYS)
def test_the_open_period_starts_in_the_month_of_today(today: date) -> None:
    """THE DEFECT ITSELF. The unbilled period — and the cash dated in it — must
    land in the accounting period the Finance screens show, which is the
    calendar month `today` is in."""
    cal = fixture.build_calendar(today)
    open_period = cal["periods"][-1]
    assert open_period["start"] == date(today.year, today.month, 1)
    assert (open_period["read_on"].year, open_period["read_on"].month) == (
        today.year,
        today.month,
    )
    assert (cal["busy_day"].year, cal["busy_day"].month) == (today.year, today.month)


@pytest.mark.parametrize("today", SIMULATED_DAYS)
def test_exactly_one_period_is_unbilled_and_it_is_the_last(today: date) -> None:
    """The Product Owner's own acceptance test — *"everything done leaves
    nothing to evaluate"* — survives every shift. Travelling the calendar bills
    NOTHING new, so BILLED THIS MONTH stays $0.00 on purpose."""
    cal = fixture.build_calendar(today)
    billed = [p["billed"] for p in cal["periods"]]
    assert billed == [True, True, False]


@pytest.mark.parametrize("today", SIMULATED_DAYS)
def test_nothing_is_dated_in_the_future(today: date) -> None:
    """A demo may not contain a payment banked next week or a meter read
    nobody has taken. This is the clamp, and `2026-10-01` is the case it
    exists for."""
    cal = fixture.build_calendar(today)
    assert cal["opening_read_on"] <= today
    assert cal["busy_day"] <= today
    for period in cal["periods"]:
        assert period["start"] <= today, period["key"]
        assert period["end"] <= today, period["key"]
        assert period["read_on"] <= today, period["key"]
        if period["bill_on"] is not None:
            assert period["bill_on"] <= today, period["key"]


@pytest.mark.parametrize("today", SIMULATED_DAYS)
def test_the_periods_are_contiguous_with_no_hole(today: date) -> None:
    """Each period starts the day after the one before ends, and the opening
    read sits the day before the first.

    ⚠ **THIS IS THE ONE `_shift_months` GOT WRONG FIRST.** A day-preserving
    shift turns 30 June into 30 July, and the next period still starts on the
    1st — a one-day hole of consumption that no bill covers, on a money path.
    Month-end stickiness is what closes it.
    """
    cal = fixture.build_calendar(today)
    periods = cal["periods"]
    assert cal["opening_read_on"] + timedelta(days=1) == periods[0]["start"]
    for earlier, later in zip(periods, periods[1:]):
        assert earlier["end"] + timedelta(days=1) == later["start"], (
            f"{earlier['key']} ends {earlier['end']} and {later['key']} "
            f"starts {later['start']}"
        )


@pytest.mark.parametrize("today", SIMULATED_DAYS)
def test_the_billed_periods_are_whole_calendar_months_in_the_past(today: date) -> None:
    """A billed cycle covers a whole month and is finished before today —
    otherwise the ageing buckets and the two-cycle story stop making sense."""
    cal = fixture.build_calendar(today)
    for period in cal["periods"]:
        if not period["billed"]:
            continue
        assert period["start"].day == 1, period["key"]
        assert period["end"].day == _last_of(period["end"]), period["key"]
        assert period["end"] < today, period["key"]
        assert period["read_on"] == period["end"], period["key"]


@pytest.mark.parametrize("today", SIMULATED_DAYS)
def test_only_the_dates_move(today: date) -> None:
    """The keys and the collected shares are the signed part of this fixture
    and the shift does not touch them. The keys are stable IDENTIFIERS, not
    month names — 37 files ask for `august` meaning *the open one*."""
    cal = fixture.build_calendar(today)
    for canonical, moved in zip(fixture.CANONICAL_PERIODS, cal["periods"]):
        assert moved["key"] == canonical["key"]
        assert moved["collected_share"] == canonical["collected_share"]
        assert moved["billed"] == canonical["billed"]


def test_a_malformed_override_raises_rather_than_falling_back(monkeypatch) -> None:
    """A typo may not silently return the wall clock: a run asked to be
    deterministic would stop being so without saying a word — hard-won law
    14's *"a flag that is silently ignored is worse than one that errors"*."""
    monkeypatch.setenv(fixture.FIXTURE_TODAY_ENV, "the-fourteenth")
    with pytest.raises(ValueError):
        fixture.fixture_today()


def test_the_override_is_read(monkeypatch) -> None:
    monkeypatch.setenv(fixture.FIXTURE_TODAY_ENV, "2027-03-09")
    assert fixture.fixture_today() == date(2027, 3, 9)


def test_the_open_period_is_the_real_current_month() -> None:
    """READS THE REAL CLOCK, ON PURPOSE.

    Every other test here states the day it means. This one does not, because
    the defect was precisely that the fixture was right on the day it was
    written and wrong on every day after. It is the defect register's own
    prevention column made executable: *"a demo fixture whose months are
    constants needs a test that fails when the current accounting period holds
    no activity, asserted against `date.today()`"*.

    It cannot go red on a date it has not met — the arithmetic below holds in
    every month — so it is not the flaky kind of clock test. It goes red if
    somebody re-pins the calendar to constants.
    """
    really_today = date.today()
    cal = fixture.build_calendar(really_today)
    open_period = cal["periods"][-1]
    assert open_period["billed"] is False
    assert open_period["start"] == date(really_today.year, really_today.month, 1)
    assert cal["busy_day"] <= really_today
    assert (cal["busy_day"].year, cal["busy_day"].month) == (
        really_today.year,
        really_today.month,
    ), "the busy day's takings must land in the accounting period Finance shows"
    for period in cal["periods"]:
        if period["billed"]:
            assert period["bill_on"] <= really_today


def test_the_move_in_case_is_the_canonical_date_at_offset_zero() -> None:
    """`CASE_MOVED_IN` read a literal `date(2026, 7, 16)` until this defect,
    directly below `move_out_on`'s own warning against literals."""
    assert fixture.move_in_on() == date(2026, 7, 16)
    assert fixture.move_out_on() == date(2026, 7, 31)


def test_the_two_proration_cases_sit_inside_the_last_billed_period() -> None:
    """One tenancy starts halfway through the final billed period and the other
    ends as it closes, so ONE issued bill prorates in both directions. A literal
    move-in date makes the estate look like an account that was always there."""
    last_billed = max(
        (p for p in fixture.PERIODS if p["billed"]), key=lambda p: p["end"]
    )
    assert last_billed["start"] < fixture.move_in_on() < last_billed["end"]
    assert fixture.move_out_on() == last_billed["end"]


def test_the_correction_and_refund_are_the_canonical_dates_at_offset_zero() -> None:
    """All seven read literal `date(2026, 7, …)` until this defect."""
    assert fixture.OVERCHARGE["opened_on"] == date(2026, 7, 15)
    assert fixture.OVERCHARGE["approved_on"] == date(2026, 7, 16)
    assert fixture.OVERCHARGE["executed_on"] == date(2026, 7, 17)
    assert fixture.REFUND["requested_on"] == date(2026, 7, 20)
    assert fixture.REFUND["approved_on"] == date(2026, 7, 21)
    assert fixture.REFUND["issued_on"] == date(2026, 7, 23)
    assert fixture.REFUND["cleared_on"] == date(2026, 7, 29)
    assert "June" in fixture.OVERCHARGE["note"]
    assert "14 July" in fixture.OVERCHARGE["note"]


#: The days the fixture is re-imported on, to ask what it ACTUALLY declares in
#: another month. A subprocess rather than `importlib.reload`, because reloading
#: a module sixteen other test files import would leave the calendar changed for
#: whatever ran next — and under `-p randomly` that is a different file each run.
REIMPORT_DAYS: tuple[str, ...] = (
    "2026-08-14",  # the anchor
    "2026-09-25",  # the day the inversion was measured
    "2026-10-01",  # first of the month: the clamp is active
    "2027-01-03",  # across a year boundary
    "2028-02-29",  # a leap day
    "2030-07-17",
)


@pytest.mark.parametrize("day", REIMPORT_DAYS)
def test_the_correction_cannot_predate_the_bill_it_corrects(day: str) -> None:
    """THE INVARIANT THE FIXTURE ALREADY STATED AND THE LITERALS BROKE.

    `core/sample_fixture.py`'s own comment: *"THE DATES SIT BETWEEN THE TWO BILL
    RUNS ON PURPOSE (task D14) … an overcharge correction cannot exist before
    run 1 at all because it corrects a bill that has issued."* Measured on the
    first tenant seeded with a travelling calendar: run 1 issued **2026-08-02**
    and the rebill was stamped **2026-07-17**, sixteen days before it. Nothing
    went red — the corrections engine does not compare the two, every count was
    right and the trial balance footed. It was found by a readback printing
    `first_issued` per period, and by one row not fitting.

    ⚠ **THIS IMPORTS THE FIXTURE FRESH ON EACH DAY RATHER THAN RECOMPUTING THE
    OFFSETS**, and the difference is the whole test. A version that read the
    offsets out of the fixture and then checked those same offsets against the
    window would be asking the fixture to agree with itself — it would stay
    green through a re-typed literal, which is exactly the defect. What is
    asserted here is what the module ACTUALLY holds after being imported on that
    day.
    """
    probe = textwrap.dedent(
        """
        import json, sys
        sys.path.insert(0, ".")
        from core import sample_fixture as f
        billed = [p for p in f.PERIODS if p["billed"]]
        print(json.dumps({
            "today": f.TODAY.isoformat(),
            "run_1": billed[0]["bill_on"].isoformat(),
            "run_2": billed[-1]["bill_on"].isoformat(),
            "dates": {
                k: f.OVERCHARGE[k].isoformat()
                for k in ("opened_on", "approved_on", "executed_on")
            } | {
                k: f.REFUND[k].isoformat()
                for k in ("requested_on", "approved_on", "issued_on", "cleared_on")
            },
            "note": f.OVERCHARGE["note"],
            "move_in": f.move_in_on().isoformat(),
            "move_out": f.move_out_on().isoformat(),
        }))
        """
    )
    env = dict(os.environ, SBH_FIXTURE_TODAY=day)
    out = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    got = json.loads(out.stdout)
    run_1 = date.fromisoformat(got["run_1"])
    run_2 = date.fromisoformat(got["run_2"])
    today = date.fromisoformat(got["today"])
    assert today == date.fromisoformat(day)
    for name, iso in got["dates"].items():
        when = date.fromisoformat(iso)
        assert run_1 < when, f"{name} {when} is on or before bill run 1 ({run_1})"
        assert when <= run_2, f"{name} {when} is after bill run 2 ({run_2})"
        assert when <= today, f"{name} {when} is in the future"
    # The stored note names a month, and a month name is a date like any other.
    # (An `or True` sat on the line above during drafting — a check that cannot
    # fail, inside the test written to catch checks that cannot fail. It is
    # mentioned rather than silently removed because noticing it took a reread.)
    period_month = (run_1.replace(day=1) - timedelta(days=1)).strftime("%B")
    assert period_month in got["note"], (
        f"the correction note says {got['note']!r} but the bill it corrects "
        f"covers {period_month}"
    )
    # and the two proration cases stay inside the last billed period
    assert date.fromisoformat(got["move_in"]) < date.fromisoformat(got["move_out"])
