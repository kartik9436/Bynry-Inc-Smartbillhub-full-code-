# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (PO 2026-08-23) — Routes & Cycles. Wave RC-W2 tasks W2-T1
#           (the period engine) and W2-T5 (tests first).
#           Screens: SET-07.3 · SET-07D (Schedule tab) · S31 step 1
# Design:   04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §2, §7
# Rules:    the pre-CR PO ruling (start day · frequency · days to complete) ·
#           D1 (*"yes"* — build the period generator) · the D1 worked figure
#           (*"a Monthly cycle starting the 1st with 3 days to complete
#           proposes Sep 1-3 the moment August closes"*) · BR-TEN-043 (a window
#           is an ARGUMENT, never a clock) · BR-MET-078 (no money here) ·
#           CLAUDE.md prime directive · **OQ-339 · OQ-340 · OQ-341 — ALL THREE
#           CLOSED-RULED by the PO on 2026-08-23**, and this file is where each
#           ruling's own worked figure is asserted as a date.
# Fixtures: tests/cr029_schedule_fixtures.py (RC-W0-T2) — CONSUMED, never
#           restated. Its nine `UnruledEdge` markers are gone: every case now
#           states the windows the rulings give it.
# ───────────────────────────────────────────────────────
"""RC-W2-T1 — the period engine, held to RC-W0's table and to three rulings.

WHAT THIS FILE DEFENDS, IN ONE SENTENCE EACH
--------------------------------------------
1. **All eight frequency words generate.** B17 §7 W2-T1's *"done when"* is
   *"all eight frequencies pass table-driven tests including month-end edges"*,
   and the table is RC-W0's, not this file's.
2. **The window is INCLUSIVE.** D1's own worked figure — three days to complete
   produced Sep 1, 2 AND 3 — so an engine reading `days_to_complete` as an
   offset (Sep 1–4) goes RED against the PO's number.
3. **THE THREE RULINGS, EACH ON ITS OWN WORKED FIGURE.** Every one was open in
   this file a day ago as a stub, and each is now a date:

   **OQ-339 — CLAMP TO THE MONTH'S LAST DAY.** PO verbatim: *"there is no 31st
       feb so we have to manage either 28th or 29th of Feb."* Monthly · start
       31 · 3 days · February 2026 → **28 Feb – 2 Mar**; the same cycle in leap
       2028 → **29 Feb – 2 Mar**. Skip and roll are rejected. **A 29th anchor in
       a leap February needs NO clamp** and an engine that clamps every 29th is
       wrong one year in four.
   **OQ-340 — THE FIRST RUN WINS.** PO verbatim: *"A: first window 15–17 Sep
       (start day becomes decorative)"*. Monthly · start day 1 · 3 days · first
       run 15 Sep 2026 → **15–17 Sep**, then 15–17 Oct, then 15–17 Nov.
   **OQ-341 — WARN, DO NOT REFUSE.** PO verbatim: *"B: refuse it (Daily accepts
       1, Weekly ≤7, Monthly ≤28) - you give warning and if user override; let
       them do it"* — the option was AMENDED in the ruling itself. A Daily cycle
       with 3 days to complete generates **1–3 Sep** and **2–4 Sep**, and both
       are real windows.

4. **A leap February is not an edge.** `SC-EDGE-29-FEB-LEAP` is a real date in
   every one of its months and is asserted separately from the sweep so it
   cannot be lost in a loop.
5. **The engine and `schedule.derive_read_window` agree BY RULE.** One helper,
   `schedule.clamp_day_to_month`, is called by both — the renderer that places a
   window in a month someone picked and the generator that decides which
   occurrences exist. They agreed by coincidence before the ruling and OQ-339
   said in as many words that coincidence was not an answer.

NO DATABASE, NO CLOCK, NO TENANT. Every input is an argument (BR-TEN-043), so
every figure here is checkable against the PO's own number without a fixture.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.metering import period_engine, schedule

from tests import cr029_schedule_fixtures as fx


def _generate(case: fx.ScheduleCase, count: int) -> list[tuple[date, date]]:
    """The engine over one fixture case, as plain `(start, end)` pairs."""
    windows = period_engine.occurrences(
        frequency=case.frequency,
        start_day=case.start_day,
        days_to_complete=case.days_to_complete,
        first_run=case.first_run,
        count=count,
    )
    return [(w.period_start, w.period_end) for w in windows]


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE VOCABULARY — all eight words, from RC-W0's table
# ═══════════════════════════════════════════════════════════════════════════
def test_w2_t1__every_frequency_word_has_a_case_and_the_words_are_b17s():
    """The sweep is over the RULED vocabulary itself, so a renamed word is red."""
    assert period_engine.FREQUENCIES == schedule.FREQUENCIES == fx.FREQUENCY_WORDS
    assert {case.frequency for case in fx.VOCABULARY_CASES} == set(fx.FREQUENCY_WORDS)


@pytest.mark.parametrize("case", fx.VOCABULARY_CASES, ids=lambda c: c.case_id)
def test_w2_t1__all_eight_frequencies_generate_their_windows(case: fx.ScheduleCase):
    assert _generate(case, len(case.windows)) == list(case.windows)


def test_w2_t1__the_d1_worked_figure_is_reproduced_exactly():
    """*"a Monthly cycle starting the 1st with 3 days to complete proposes Sep
    1-3 the moment August closes"* — the decision log, 2026-08-23, verbatim.

    Written out rather than left inside the sweep because it is the one figure
    in this wave the PO stated in words, and INCLUSIVITY hangs on it: three days
    to complete are Sep 1, 2 and 3, not Sep 1 to Sep 4.
    """
    case = fx.by_id("SC-MONTHLY-01")
    assert _generate(case, 1) == [(date(2026, 9, 1), date(2026, 9, 3))]


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE RULED CASES — every one, prefix exact
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("case", fx.CASES, ids=lambda c: c.case_id)
def test_w2_t1__every_case_generates_exactly_what_the_fixture_states(case: fx.ScheduleCase):
    """Every case, including the twelve that were stubs until 2026-08-23."""
    assert _generate(case, len(case.windows)) == list(case.windows)


def test_w2_t1__a_leap_february_is_a_real_date_and_must_not_clamp():
    """`SC-EDGE-29-FEB-LEAP` — the 29th exists in February 2028.

    B17 §7 W2-T1, verbatim: *"A start day of 29 in a **leap** February is fully
    ruled and must NOT be stubbed."* OQ-339's ruling says the same thing from
    the other side — *"either 28th or 29th of Feb"* — so an engine that clamps
    unconditionally to the 28th fails here.
    """
    case = fx.by_id("SC-EDGE-29-FEB-LEAP")
    assert _generate(case, 3) == [
        (date(2028, 1, 29), date(2028, 1, 31)),
        (date(2028, 2, 29), date(2028, 3, 2)),
        (date(2028, 3, 29), date(2028, 3, 31)),
    ]


def test_w2_t1__a_window_may_end_in_the_next_month_or_the_next_year():
    """Only the ANCHOR is a day-of-month; the end is arithmetic (RC-W0's own
    authority note on `SC-EDGE-LONG-WINDOW` and `SC-EDGE-YEAR-BOUNDARY`)."""
    assert _generate(fx.by_id("SC-EDGE-LONG-WINDOW"), 3) == [
        (date(2026, 1, 25), date(2026, 2, 3)),
        (date(2026, 2, 25), date(2026, 3, 6)),
        (date(2026, 3, 25), date(2026, 4, 3)),
    ]
    assert _generate(fx.by_id("SC-EDGE-YEAR-BOUNDARY"), 2)[0] == (
        date(2026, 12, 30),
        date(2027, 1, 2),
    )


# ═══════════════════════════════════════════════════════════════════════════
# 3 · OQ-339 — THE CLAMP, ON THE PO'S OWN FIGURE
# ═══════════════════════════════════════════════════════════════════════════
def test_oq339__the_ruled_worked_figure_28_feb_to_2_mar():
    """PO 2026-08-23, verbatim: *"there is no 31st feb so we have to manage
    either 28th or 29th of Feb."*

    The figure the ruling was put on: **Monthly · start 31 · 3 days · February
    2026 → 28 Feb – 2 Mar**. Written out rather than left inside the sweep,
    because it is the number the PO answered and a sweep failure names a case
    id where this names the date.
    """
    windows = period_engine.occurrences(
        frequency="Monthly",
        start_day=31,
        days_to_complete=3,
        first_run=date(2026, 1, 31),
        count=3,
    )
    assert [(w.period_start, w.period_end) for w in windows] == [
        (date(2026, 1, 31), date(2026, 2, 2)),
        (date(2026, 2, 28), date(2026, 3, 2)),
        # AND MARCH IS BACK ON THE 31st — the clamp is per occurrence. A cycle
        # that clamped once and then read the 28th for ever would have moved
        # the schedule, which is not what "there is no 31st feb" says.
        (date(2026, 3, 31), date(2026, 4, 2)),
    ]


def test_oq339__the_leap_half_of_the_same_sentence_is_29_feb_to_2_mar():
    """*"either 28th **or 29th** of Feb"* — the PO named both, which is what
    makes the clamp leap-aware rather than a hard-coded 28."""
    windows = period_engine.occurrences(
        frequency="Monthly",
        start_day=31,
        days_to_complete=3,
        first_run=date(2028, 1, 31),
        count=2,
    )
    assert (windows[1].period_start, windows[1].period_end) == (
        date(2028, 2, 29),
        date(2028, 3, 2),
    )


def test_oq339__skip_and_roll_are_both_rejected():
    """The two readings the PO did NOT choose, asserted as absences.

    SKIP would leave February with no window at all — so a twelve-window walk
    of a 31st cycle would name eleven months. ROLL would put the February
    occurrence in March — so March would hold two. Neither may happen.
    """
    windows = period_engine.occurrences(
        frequency="Monthly",
        start_day=31,
        days_to_complete=1,
        first_run=date(2026, 1, 31),
        count=12,
    )
    months = [(w.period_start.year, w.period_start.month) for w in windows]
    assert len(months) == len(set(months)) == 12, "no month doubled (roll) and none missing (skip)"
    assert (2026, 2) in months
    assert next(w for w in windows if w.period_start.month == 2).period_start == date(2026, 2, 28)


def test_oq339__the_generator_and_the_renderer_share_one_clamp():
    """OQ-339's own closing words: the two *"now agree by rule rather than by
    coincidence"*. One helper, called from both, so neither can drift."""
    assert schedule.clamp_day_to_month(2026, 2, 31) == 28
    assert schedule.clamp_day_to_month(2028, 2, 31) == 29
    assert schedule.clamp_day_to_month(2028, 2, 29) == 29, "a leap 29th is not clamped"
    assert schedule.clamp_day_to_month(2026, 3, 31) == 31
    assert schedule.derive_read_window(31, 3, date(2026, 2, 10)) == (
        date(2026, 2, 28),
        date(2026, 3, 2),
    )
    generated = period_engine.occurrences(
        frequency="Monthly",
        start_day=31,
        days_to_complete=3,
        first_run=date(2026, 1, 31),
        count=2,
    )[1]
    assert (generated.period_start, generated.period_end) == schedule.derive_read_window(
        31, 3, date(2026, 2, 10)
    )


# ═══════════════════════════════════════════════════════════════════════════
# 3b · OQ-340 — THE FIRST RUN WINS, AND THE START DAY IS DECORATIVE
# ═══════════════════════════════════════════════════════════════════════════
def test_oq340__the_first_run_wins_on_the_pos_own_figure():
    """PO 2026-08-23, verbatim: *"A: first window 15–17 Sep (start day becomes
    decorative)"*. Monthly, start day 1, 3 days, first run 15 Sep 2026."""
    windows = period_engine.occurrences(
        frequency="Monthly",
        start_day=1,
        days_to_complete=3,
        first_run=date(2026, 9, 15),
        count=3,
    )
    assert [(w.period_start, w.period_end) for w in windows] == [
        (date(2026, 9, 15), date(2026, 9, 17)),
        (date(2026, 10, 15), date(2026, 10, 17)),
        (date(2026, 11, 15), date(2026, 11, 17)),
    ]


def test_oq340__the_effective_start_day_is_served_and_says_when_it_differs():
    """⚠ **THE HONEST FOLLOW-ON THE RULING CREATES.** With the first run as the
    anchor, `cycles.start_day` no longer describes what the cycle does — and a
    stored field the engine ignores is a field that lies to the operator.

    So the engine SERVES the effective day rather than leaving the screens to
    infer it, and says out loud when it differs from what is stored. The stored
    column is NOT rewritten: that is the operator's own value and silently
    changing it would be a second, unruled decision.
    """
    assert period_engine.effective_start_day(
        frequency="Monthly", start_day=1, first_run=date(2026, 9, 15)
    ) == {"effective_start_day": 15, "start_day": 1, "differs": True}
    # Agreeing fields: nothing differs and the answer is the stored day.
    assert period_engine.effective_start_day(
        frequency="Monthly", start_day=15, first_run=date(2026, 9, 15)
    ) == {"effective_start_day": 15, "start_day": 15, "differs": False}
    # Daily/Weekly/Fortnightly never read `start_day` at all (B17 §7), so there
    # is no effective day to report and a stray stored value is not "differing".
    assert period_engine.effective_start_day(
        frequency="Weekly", start_day=3, first_run=date(2026, 9, 1)
    ) == {"effective_start_day": None, "start_day": 3, "differs": False}


def test_oq340__a_first_run_anchor_still_clamps_by_the_oq339_rule():
    """The two rulings meet: a cycle whose FIRST RUN is the 31st is anchored on
    the 31st, and February still clamps. One rule, applied to whichever day is
    the anchor."""
    windows = period_engine.occurrences(
        frequency="Monthly",
        start_day=1,  # decorative
        days_to_complete=1,
        first_run=date(2026, 1, 31),
        count=2,
    )
    assert [w.period_start for w in windows] == [date(2026, 1, 31), date(2026, 2, 28)]


# ═══════════════════════════════════════════════════════════════════════════
# 3c · OQ-341 — OVERLAP IS GENERATED, AND THE WARNING NAMES THE COLLISION
# ═══════════════════════════════════════════════════════════════════════════
def test_oq341__overlapping_windows_are_generated_not_refused():
    """PO 2026-08-23, verbatim: *"B: refuse it (Daily accepts 1, Weekly ≤7,
    Monthly ≤28) - you give warning and if user override; let them do it"*.

    The option was AMENDED inside the ruling: a warning, then the operator's
    override, then real windows. So the Daily-with-3-days figure generates
    **1–3 Sep** and **2–4 Sep** and both are real.
    """
    windows = period_engine.occurrences(
        frequency="Daily",
        start_day=None,
        days_to_complete=3,
        first_run=date(2026, 9, 1),
        count=3,
    )
    assert [(w.period_start, w.period_end) for w in windows] == [
        (date(2026, 9, 1), date(2026, 9, 3)),
        (date(2026, 9, 2), date(2026, 9, 4)),
        (date(2026, 9, 3), date(2026, 9, 5)),
    ]
    assert windows[1].period_start <= windows[0].period_end, "they overlap, and that is the point"


def test_oq341__the_warning_names_the_collision_and_quotes_the_ceiling():
    """*"you give warning"* — and a warning that does not say what collided is
    not one. The three ceilings the PO quoted are asserted by name."""
    assert period_engine.overlap_ceiling("Daily") == 1
    assert period_engine.overlap_ceiling("Weekly") == 7
    assert period_engine.overlap_ceiling("Monthly") == 28
    # "derive the rest" — the shortest gap the calendar can put between two
    # occurrences of that word. Fortnightly is 14 days; Bimonthly's shortest two
    # months are Jan+Feb / Feb+Mar (59); Quarterly's are Feb+Mar+Apr (89);
    # Semiannual's shortest six months are 181; a common year is 365.
    assert period_engine.overlap_ceiling("Fortnightly") == 14
    assert period_engine.overlap_ceiling("Bimonthly") == 59
    assert period_engine.overlap_ceiling("Quarterly") == 89
    assert period_engine.overlap_ceiling("Semiannual") == 181
    assert period_engine.overlap_ceiling("Annual") == 365

    warning = period_engine.overlap_warning(frequency="Daily", days_to_complete=3)
    assert warning is not None
    assert warning["code"] == period_engine.WARN_WINDOWS_OVERLAP
    assert warning["days_to_complete"] == 3
    assert warning["max_days_to_complete"] == 1
    assert warning["frequency"] == "Daily"
    # No warning when it fits, and none at the ceiling itself.
    assert period_engine.overlap_warning(frequency="Daily", days_to_complete=1) is None
    assert period_engine.overlap_warning(frequency="Monthly", days_to_complete=28) is None
    assert period_engine.overlap_warning(frequency="Monthly", days_to_complete=29) is not None


def test_oq341__nothing_in_the_engine_refuses_an_overridden_configuration():
    """The stub that used to live in `_walk` is GONE, not replaced by a
    validation error: *"let them do it"*. A 45-day Monthly cycle generates."""
    windows = period_engine.occurrences(
        frequency="Monthly",
        start_day=1,
        days_to_complete=45,
        first_run=date(2026, 9, 1),
        count=3,
    )
    assert [(w.period_start, w.period_end) for w in windows] == [
        (date(2026, 9, 1), date(2026, 10, 15)),
        (date(2026, 10, 1), date(2026, 11, 14)),
        (date(2026, 11, 1), date(2026, 12, 15)),
    ]


def test_oq341__the_unruled_schedule_stub_is_gone_from_the_engine():
    """All three questions this class was raised for were ruled on 2026-08-23.

    A stub that can never fire is a claim a reader will believe (hard-won law
    1), so the class, its gap codes and every `raise` of it are removed rather
    than left standing. This test is the guard against one creeping back.
    """
    for gone in ("UnruledSchedule", "GAP_MONTH_END_ANCHOR", "GAP_FIRST_RUN_OFF_ANCHOR"):
        assert not hasattr(period_engine, gone), f"{gone} outlived the ruling that closed it"
    source = (period_engine.__file__ or "").replace(".pyc", ".py")
    with open(source, encoding="utf-8") as handle:
        body = handle.read().split('"""', 2)[-1]
    assert "NotImplementedError" not in body


# ═══════════════════════════════════════════════════════════════════════════
# 4 · WHAT THE RUN WIZARD AND THE DASHBOARD ASK IT (W2-T2 / W2-T3)
# ═══════════════════════════════════════════════════════════════════════════
def test_w2_t2__upcoming_windows_carry_the_screenshots_two_statuses():
    """SET-07D's Schedule tab: *"Next three windows with statuses Next/
    Scheduled"*. The FIRST is Next; every later one is Scheduled."""
    windows = period_engine.upcoming_windows(
        frequency="Monthly",
        start_day=1,
        days_to_complete=3,
        first_run=date(2026, 9, 1),
        as_of=date(2026, 9, 20),
        count=3,
    )
    assert [(w.period_start, w.period_end, w.status) for w in windows] == [
        (date(2026, 10, 1), date(2026, 10, 3), period_engine.STATUS_NEXT),
        (date(2026, 11, 1), date(2026, 11, 3), period_engine.STATUS_SCHEDULED),
        (date(2026, 12, 1), date(2026, 12, 3), period_engine.STATUS_SCHEDULED),
    ]


def test_w2_t2__a_window_still_running_is_still_the_one_offered():
    """D1's figure says Sep 1–3 is proposed *"the moment August closes"*. While
    August's own window is still running it is still what a run would cover, so
    the proposal is the first window that has not ENDED — a lane judgment,
    recorded here and in the engine's docstring rather than left implicit."""
    windows = period_engine.upcoming_windows(
        frequency="Monthly",
        start_day=1,
        days_to_complete=3,
        first_run=date(2026, 8, 1),
        as_of=date(2026, 8, 2),  # inside the August window
        count=1,
    )
    assert (windows[0].period_start, windows[0].period_end) == (
        date(2026, 8, 1),
        date(2026, 8, 3),
    )
    closed = period_engine.upcoming_windows(
        frequency="Monthly",
        start_day=1,
        days_to_complete=3,
        first_run=date(2026, 8, 1),
        as_of=date(2026, 8, 4),  # August has closed
        count=1,
    )
    assert (closed[0].period_start, closed[0].period_end) == (
        date(2026, 9, 1),
        date(2026, 9, 3),
    )


def test_w2_t3__the_next_cycle_date_is_the_next_occurrence_not_a_window_end():
    """D8②, PO verbatim: *"which date 'closes in 4 days' counts to - Next cycle
    date"*. A cycle's date is the day it comes round — the next occurrence's
    START — not the end of the window it is inside and not the bill day."""
    assert period_engine.next_cycle_date(
        frequency="Monthly",
        start_day=1,
        days_to_complete=3,
        first_run=date(2026, 8, 1),
        as_of=date(2026, 8, 28),
    ) == date(2026, 9, 1)
    # On the day itself: today IS the next cycle date, which is what makes the
    # "closes today" state reachable.
    assert period_engine.next_cycle_date(
        frequency="Monthly",
        start_day=1,
        days_to_complete=3,
        first_run=date(2026, 8, 1),
        as_of=date(2026, 9, 1),
    ) == date(2026, 9, 1)


def test_w2_t3__a_month_end_cycle_can_now_say_when_it_next_comes_round():
    """This asserted a REFUSAL until OQ-339 was ruled: a 31st-anchored cycle
    asked for its next date raised, and the caller rendered the silence. It now
    answers **28 February 2026**, which is the ruling as a countdown."""
    assert period_engine.next_cycle_date(
        frequency="Monthly",
        start_day=31,
        days_to_complete=1,
        first_run=date(2026, 1, 31),
        as_of=date(2026, 2, 10),
    ) == date(2026, 2, 28)


# ═══════════════════════════════════════════════════════════════════════════
# 5 · WHAT THE ENGINE REFUSES, AND WHAT IT DOES NOT READ
# ═══════════════════════════════════════════════════════════════════════════
def test_w2_t1__an_unknown_frequency_is_refused_by_name():
    with pytest.raises(ValueError) as raised:
        period_engine.occurrences(
            frequency="Sometimes",
            start_day=1,
            days_to_complete=1,
            first_run=date(2026, 1, 1),
            count=1,
        )
    assert "Sometimes" in str(raised.value)


def test_w2_t1__the_shipped_lowercase_spellings_are_understood():
    """CR-006 shipped `monthly`; `schedule.business_frequency` maps it. The
    engine goes through that one mapping rather than owning a second."""
    assert period_engine.occurrences(
        frequency="monthly",
        start_day=1,
        days_to_complete=3,
        first_run=date(2026, 9, 1),
        count=1,
    ) == period_engine.occurrences(
        frequency="Monthly",
        start_day=1,
        days_to_complete=3,
        first_run=date(2026, 9, 1),
        count=1,
    )


def test_w2_t1__a_cycle_with_no_days_to_complete_produces_nothing():
    """A cycle nobody has scheduled has no window — the posture
    `schedule.backfill_schedule` already takes. Inventing a one-day window
    would put a period on screen no human chose."""
    assert (
        period_engine.occurrences(
            frequency="Monthly",
            start_day=1,
            days_to_complete=None,
            first_run=date(2026, 9, 1),
            count=3,
        )
        == ()
    )
    assert (
        period_engine.occurrences(
            frequency="Monthly",
            start_day=1,
            days_to_complete=3,
            first_run=None,
            count=3,
        )
        == ()
    )


def test_w2_t1__weekly_and_fortnightly_anchor_on_the_first_run_not_on_start_day():
    """B17 §7 W2-T1: *"no weekday-anchor column exists and `start_day` must NOT
    be overloaded"* — *"otherwise anchor on `first_run` as the fixtures do"*.

    So a Weekly cycle carrying a stray `start_day` generates the SAME windows as
    one carrying none: the integer is not silently read as a weekday.
    """
    anchored = period_engine.occurrences(
        frequency="Weekly",
        start_day=None,
        days_to_complete=2,
        first_run=date(2026, 9, 1),
        count=3,
    )
    with_stray_day = period_engine.occurrences(
        frequency="Weekly",
        start_day=3,
        days_to_complete=2,
        first_run=date(2026, 9, 1),
        count=3,
    )
    assert anchored == with_stray_day
    assert [(w.period_start, w.period_end) for w in anchored] == list(
        fx.by_id("SC-WEEKLY-01").windows
    )


def test_w2_t1__the_engine_reads_no_clock_and_no_database():
    """BR-TEN-043 / gate G6, asserted rather than asserted-in-a-comment."""
    source = (period_engine.__file__ or "").replace(".pyc", ".py")
    with open(source, encoding="utf-8") as handle:
        text = handle.read()
    body = text.split('"""', 2)[-1]  # past the module docstring
    for forbidden in ("date.today", "datetime.now", "objects.", "models."):
        assert forbidden not in body, f"the engine must not use {forbidden}"
