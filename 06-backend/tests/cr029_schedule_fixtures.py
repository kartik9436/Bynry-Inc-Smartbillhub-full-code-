# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (Routes & Cycles, PO ruling *"G0 - Yes now"* 2026-08-23) —
#           wave RC-W0, task W0-T2 (B17 §7): *"Dynamism + schedule fixtures …
#           frequency cases for all eight words including month-end edges
#           (start day 31 · February)"*.
# Consumed by: RC-W2-T1 (the period engine — *"all eight frequencies pass
#           table-driven tests including month-end edges"*) and RC-W2-T5.
#           RC-W4 uses the dynamism half, which lives in
#           tests/cr029_dynamism_fixtures.py.
# Rules:    B17 §2 (a cycle captures start day · frequency · days to complete;
#           *"the reading window is DERIVED, never stored"*) · the pre-CR PO
#           ruling that named the eight one-word frequencies · BR-MET-078 (no
#           money anywhere near a cycle — nothing in this file is money) ·
#           BR-TEN-043 (nothing here reads a clock; every date is literal).
# Note:     NO DATABASE. These are pure data cases so the period engine can be
#           table-driven and tested without a tenant, and so the same table can
#           later drive an API-level test. Tenant scoping (CLAUDE.md rule 1)
#           does not arise because nothing here writes a row.
# ───────────────────────────────────────────────────────
"""The CR-029 schedule cases — every frequency word, and every month-end edge.

WHAT IS RULED, AND WHAT THIS FILE REFUSES TO DECIDE
---------------------------------------------------
Three things about a cycle's time are ruled (PO, pre-CR-029, verbatim):

    *"we can capture start day, frequency, monthly, weekly daily, biweekly,
    once in two months , quaterly etc and days to complete it ; give business
    names to frequence - 1 word."*

and B17 §2 turns that into: **start day · frequency · days to complete**, with
the reading window *"derived, not stored"*.

**The window's shape is ruled by a worked figure**, not by this file's opinion.
The decision log of 2026-08-23 (D1) states it: *"a Monthly cycle starting the
1st with 3 days to complete proposes **Sep 1–3** the moment August closes"*.
Three days to complete produced Sep 1, 2 and 3 — so a window is

    [start day, start day + days_to_complete − 1]   ← INCLUSIVE, N days long

and `SC-MONTHLY-01` below is literally that sentence, so an engine that reads
`days_to_complete` as an offset (Sep 1–4) goes RED against the PO's own number.

**AND THE MONTH-END QUESTION IS NOW RULED (OQ-339, PO 2026-08-23).** Verbatim:
*"there is no 31st feb so we have to manage either 28th or 29th of Feb."* — the
CLAMP reading, and the PO named BOTH February lengths, which is the leap-aware
form of it. So a cycle anchored on the 29th, 30th or 31st opens on **the last
day the month actually has**, and the cases below now state their windows
instead of refusing to. Skip and roll are rejected. Two neighbours the ruling
does NOT touch: a 29th anchor in a LEAP February is a real date and must not be
clamped (`SC-EDGE-29-FEB-LEAP`), and the ANCHOR is what clamps — never the
window's end, which is a length.

**TWO MORE SILENCES CLOSED THE SAME DAY, and their cases are ruled here too.**
**OQ-340** — *"A: first window 15-17 Sep (start day becomes decorative)"*: when
`first_run` disagrees with `start_day`, the FIRST RUN's day is the anchor
(`SC-EDGE-FIRST-RUN-OFF-ANCHOR`). **OQ-341** — *"B: refuse it (Daily accepts 1,
Weekly <=7, Monthly <=28) - you give warning and if user override; let them do
it"*: overlapping windows are a WARNING and not a refusal, so a Daily cycle with
three days to complete GENERATES its overlapping windows
(`SC-EDGE-DTC-EXCEEDS-PERIOD`).

**NOTHING IN THIS FILE IS UNRULED ANY MORE.** `UnruledEdge`, `UNRULED_CASES`
and `open_questions()` are gone rather than left empty: a marker that can never
fire is a claim a reader will believe (hard-won law 1).

HOW THE ENGINE TESTS USE THIS
-----------------------------
    for case in CASES:
        assert engine(case.frequency, case.start_day,
                      case.days_to_complete, case.first_run,
                      count=len(case.windows)) == list(case.windows)

`CASES` is every case in one tuple and every case states its windows.
`by_id()` fetches one. `FREQUENCY_WORDS` and `FREQUENCY_STEP` are the ruled
vocabulary itself, so a rename in RC-W1's migration has exactly one place to
disagree with — and `tests/test_cr029_w0_fixtures.py` asserts the eight words
against B17 §2's table, in B17's order.

THE STORED SPELLING — SETTLED 2026-08-23 BY RC-W1 (commit d47fa88)
------------------------------------------------------------------
These cases first carried a lowercase key, because the column's values were
RC-W1's to declare and not this lane's to guess. RC-W1 landed
`apps/metering/schedule.FREQUENCIES` holding **the capitalised business words
themselves** — `Daily … Annual`, B17 §2's table verbatim — with
`schedule.LEGACY_FREQUENCIES` mapping the shipped `monthly | bi_monthly |
quarterly` and the PO's own spellings onto them. So the cases now carry the
CANONICAL word and nothing has to translate at the boundary.
`tests/test_cr029_w0_fixtures.py` asserts `FREQUENCY_WORDS ==
schedule.FREQUENCIES`, so if either side is renamed the mismatch is a red test
rather than a silent divergence.

⚠ **RC-W1's CLAMP AND THE ENGINE NOW AGREE BY RULE, NOT BY COINCIDENCE.**
`schedule.derive_read_window` clamped the start day to the month's last day from
the day it shipped, as a RENDERING choice for a month a caller had already
picked, and this file recorded that it was not therefore ruled. OQ-339 ruled it,
so both paths call ONE helper — `schedule.clamp_day_to_month` — and neither owns
a second copy of the arithmetic that could drift from the other.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# ═══════════════════════════════════════════════════════════════════════════
# THE RULED VOCABULARY — eight one-word business names, in B17 §2's order
# ═══════════════════════════════════════════════════════════════════════════
#: B17 §2, the frequency table, top to bottom. Order is part of the contract:
#: the wizard's select renders it and the tests assert it.
FREQUENCY_WORDS: tuple[str, ...] = (
    "Daily",
    "Weekly",
    "Fortnightly",
    "Monthly",
    "Bimonthly",
    "Quarterly",
    "Semiannual",
    "Annual",
)

#: What each word ADVANCES BY, from B17 §2's "Means" column, verbatim:
#: Daily "every day" · Weekly "every week" · Fortnightly "every two weeks" ·
#: Monthly "every month" · Bimonthly "every two months" · Quarterly "every
#: three months" · Semiannual "every six months" · Annual "every year".
#: `("days", n)` steps by whole days; `("months", n)` steps the calendar.
#: Keyed by the CANONICAL word `apps/metering/schedule.FREQUENCIES` stores.
FREQUENCY_STEP: dict[str, tuple[str, int]] = {
    "Daily": ("days", 1),
    "Weekly": ("days", 7),
    "Fortnightly": ("days", 14),
    "Monthly": ("months", 1),
    "Bimonthly": ("months", 2),
    "Quarterly": ("months", 3),
    "Semiannual": ("months", 6),
    "Annual": ("months", 12),
}

#: Which words anchor on a DAY-OF-MONTH and can therefore hit a month-end edge
#: (B17 §2: *"day-of-month for monthly-and-slower; weekday anchor for
#: weekly/fortnightly; n/a for daily"*).
DAY_OF_MONTH_WORDS: frozenset[str] = frozenset(
    {"Monthly", "Bimonthly", "Quarterly", "Semiannual", "Annual"}
)


# ═══════════════════════════════════════════════════════════════════════════
# THE CASE SHAPE
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class ScheduleCase:
    """One (frequency, start day, days-to-complete, first run) → windows case.

    `windows` holds the occurrences in order, each an inclusive
    `(first_day, last_day)` pair `days_to_complete` days long. Every case in
    this file states its windows: since the PO ruled OQ-339, OQ-340 and OQ-341
    on 2026-08-23 there is no edge here whose answer is open.
    """

    case_id: str
    title: str
    frequency: str
    start_day: int | None  # None for Daily (n/a) and for the weekday-anchored words
    days_to_complete: int
    first_run: date
    windows: tuple[tuple[date, date], ...]
    authority: str
    tags: tuple[str, ...] = field(default_factory=tuple)


# ═══════════════════════════════════════════════════════════════════════════
# 1 · ONE CASE PER RULED WORD — the eight-word sweep RC-W2-T1 must pass
# ═══════════════════════════════════════════════════════════════════════════
_VOCABULARY: tuple[ScheduleCase, ...] = (
    ScheduleCase(
        case_id="SC-DAILY-01",
        title="Daily · a one-day window every day",
        frequency="Daily",
        start_day=None,  # B17 §2: start day is "n/a for daily"
        days_to_complete=1,
        first_run=date(2026, 9, 1),
        windows=(
            (date(2026, 9, 1), date(2026, 9, 1)),
            (date(2026, 9, 2), date(2026, 9, 2)),
            (date(2026, 9, 3), date(2026, 9, 3)),
        ),
        authority='B17 §2 — Daily "every day"; window length = days_to_complete (D1 worked figure)',
        tags=("vocabulary",),
    ),
    ScheduleCase(
        case_id="SC-WEEKLY-01",
        title="Weekly · a two-day window every seven days, anchored on the first run",
        frequency="Weekly",
        # B17 §2 calls this a "weekday anchor". WHICH INTEGER encodes a weekday
        # is an engine/schema question RC-W1/RC-W2 answer, so this case anchors
        # on the FIRST RUN DATE (a Tuesday) and needs no encoding at all.
        start_day=None,
        days_to_complete=2,
        first_run=date(2026, 9, 1),  # Tuesday
        windows=(
            (date(2026, 9, 1), date(2026, 9, 2)),
            (date(2026, 9, 8), date(2026, 9, 9)),
            (date(2026, 9, 15), date(2026, 9, 16)),
        ),
        authority='B17 §2 — Weekly "every week"',
        tags=("vocabulary",),
    ),
    ScheduleCase(
        case_id="SC-FORTNIGHTLY-01",
        title="Fortnightly · every fourteen days, and the third window crosses month end",
        frequency="Fortnightly",
        start_day=None,
        days_to_complete=3,
        first_run=date(2026, 9, 1),  # Tuesday
        windows=(
            (date(2026, 9, 1), date(2026, 9, 3)),
            (date(2026, 9, 15), date(2026, 9, 17)),
            # Sep 29 + 2 = Oct 1. A window running past month end is ARITHMETIC,
            # not a ruling: the anchor is in September and the window is three
            # days long. Nothing says a window stops at a month boundary.
            (date(2026, 9, 29), date(2026, 10, 1)),
        ),
        authority=(
            'B17 §2 — Fortnightly "every two weeks" (named so because the PO\'s '
            '"biweekly" also reads as twice-a-week)'
        ),
        tags=("vocabulary", "crosses-month-end"),
    ),
    ScheduleCase(
        case_id="SC-MONTHLY-01",
        title="Monthly · THE RULED WORKED FIGURE — the 1st, three days to complete, Sep 1–3",
        frequency="Monthly",
        start_day=1,
        days_to_complete=3,
        first_run=date(2026, 9, 1),
        windows=(
            (date(2026, 9, 1), date(2026, 9, 3)),
            (date(2026, 10, 1), date(2026, 10, 3)),
            (date(2026, 11, 1), date(2026, 11, 3)),
        ),
        # ⚠ This is the one case in the file that is quoted, not derived.
        authority=(
            "12-governance/02-decision-log.md 2026-08-23 (CR-029 D1), verbatim: "
            '"a Monthly cycle starting the 1st with 3 days to complete proposes '
            'Sep 1-3 the moment August closes". Three days = Sep 1, 2, 3 — which '
            "is what makes the window INCLUSIVE of its start day."
        ),
        tags=("vocabulary", "ruled-figure"),
    ),
    ScheduleCase(
        case_id="SC-BIMONTHLY-01",
        title='Bimonthly · every two months, the PO\'s "once in two months"',
        frequency="Bimonthly",
        start_day=10,
        days_to_complete=5,
        first_run=date(2026, 9, 10),
        windows=(
            (date(2026, 9, 10), date(2026, 9, 14)),
            (date(2026, 11, 10), date(2026, 11, 14)),
            (date(2027, 1, 10), date(2027, 1, 14)),  # and across the year boundary
        ),
        authority='B17 §2 — Bimonthly "every two months" (PO: "once in two months")',
        tags=("vocabulary", "crosses-year-end"),
    ),
    ScheduleCase(
        case_id="SC-QUARTERLY-01",
        title="Quarterly · every three months",
        frequency="Quarterly",
        start_day=15,
        days_to_complete=5,
        first_run=date(2026, 1, 15),
        windows=(
            (date(2026, 1, 15), date(2026, 1, 19)),
            (date(2026, 4, 15), date(2026, 4, 19)),
            (date(2026, 7, 15), date(2026, 7, 19)),
        ),
        authority='B17 §2 — Quarterly "every three months"',
        tags=("vocabulary",),
    ),
    ScheduleCase(
        case_id="SC-SEMIANNUAL-01",
        title="Semiannual · every six months",
        frequency="Semiannual",
        start_day=1,
        days_to_complete=7,
        first_run=date(2026, 1, 1),
        windows=(
            (date(2026, 1, 1), date(2026, 1, 7)),
            (date(2026, 7, 1), date(2026, 7, 7)),
            (date(2027, 1, 1), date(2027, 1, 7)),
        ),
        authority='B17 §2 — Semiannual "every six months"',
        tags=("vocabulary", "crosses-year-end"),
    ),
    ScheduleCase(
        case_id="SC-ANNUAL-01",
        title="Annual · every year",
        frequency="Annual",
        start_day=20,
        days_to_complete=10,
        first_run=date(2026, 6, 20),
        windows=(
            (date(2026, 6, 20), date(2026, 6, 29)),
            (date(2027, 6, 20), date(2027, 6, 29)),
            (date(2028, 6, 20), date(2028, 6, 29)),  # 2028 is a leap year; June is unaffected
        ),
        authority='B17 §2 — Annual "every year"',
        tags=("vocabulary",),
    ),
)


# ═══════════════════════════════════════════════════════════════════════════
# 2 · MONTH-END EDGES — W0-T2's *"start day 31 · February"*, and its family
# ═══════════════════════════════════════════════════════════════════════════
#: The ruling every case in this block is held to, quoted once. PO 2026-08-23,
#: closing OQ-339, verbatim: *"there is no 31st feb so we have to manage either
#: 28th or 29th of Feb."* — CLAMP TO THE MONTH'S LAST DAY, leap-aware because
#: the PO named both February lengths themselves.
_CLAMP = (
    "OQ-339 CLOSED — RULED 2026-08-23, PO verbatim: "
    '"there is no 31st feb so we have to manage either 28th or 29th of Feb." '
    "The anchor CLAMPS to the last day the month actually has; skip and roll "
    "are rejected. The clamp is per occurrence, so the anchor is not lost: a "
    "31st cycle clamped to 28 Feb is back on the 31st in March."
)

_MONTH_END: tuple[ScheduleCase, ...] = (
    ScheduleCase(
        case_id="SC-EDGE-31-FEB",
        title="Monthly on the 31st meets February — W0-T2's named case, now ruled",
        frequency="Monthly",
        start_day=31,
        days_to_complete=1,
        first_run=date(2026, 1, 31),
        windows=(
            (date(2026, 1, 31), date(2026, 1, 31)),
            # February 2026 has 28 days, so the 31st reads on the 28th.
            (date(2026, 2, 28), date(2026, 2, 28)),
            # …and MARCH IS BACK ON THE 31st. The clamp applies to the
            # occurrence, never to the anchor: a cycle that clamped once and
            # then read the 28th forever would have quietly moved the schedule.
            (date(2026, 3, 31), date(2026, 3, 31)),
        ),
        authority=_CLAMP,
        tags=("month-end", "february"),
    ),
    ScheduleCase(
        case_id="SC-EDGE-31-FEB-THE-RULED-FIGURE",
        title="THE PO'S OWN WORKED FIGURE — Monthly · 31st · 3 days · Feb 2026 → 28 Feb – 2 Mar",
        frequency="Monthly",
        start_day=31,
        days_to_complete=3,
        first_run=date(2026, 1, 31),
        windows=(
            (date(2026, 1, 31), date(2026, 2, 2)),
            # ⚠ THE FIGURE THE RULING WAS PUT TO THE PO ON. 28 Feb + 2 = 2 Mar.
            (date(2026, 2, 28), date(2026, 3, 2)),
            (date(2026, 3, 31), date(2026, 4, 2)),
        ),
        authority=_CLAMP + " Worked figure shown to the PO: Monthly, start 31, 3 days, Feb 2026.",
        tags=("month-end", "february", "ruled-figure"),
    ),
    ScheduleCase(
        case_id="SC-EDGE-31-FEB-LEAP-THE-RULED-FIGURE",
        title="The same figure in a LEAP February — 29 Feb – 2 Mar, which is why 'either 28th or 29th'",
        frequency="Monthly",
        start_day=31,
        days_to_complete=3,
        first_run=date(2028, 1, 31),
        windows=(
            (date(2028, 1, 31), date(2028, 2, 2)),
            # 2028 is a leap year: the clamp finds 29, not 28. This is the half
            # of the ruling the PO stated in the same breath.
            (date(2028, 2, 29), date(2028, 3, 2)),
            (date(2028, 3, 31), date(2028, 4, 2)),
        ),
        authority=_CLAMP + " Worked figure shown to the PO: the leap-year half, Feb 2028.",
        tags=("month-end", "february", "leap-year", "ruled-figure"),
    ),
    ScheduleCase(
        case_id="SC-EDGE-31-APR",
        title="Monthly on the 31st meets a 30-day month",
        frequency="Monthly",
        start_day=31,
        days_to_complete=2,
        first_run=date(2026, 3, 31),
        windows=(
            (date(2026, 3, 31), date(2026, 4, 1)),
            (date(2026, 4, 30), date(2026, 5, 1)),
            (date(2026, 5, 31), date(2026, 6, 1)),
        ),
        authority=(
            _CLAMP + " February is the case everyone names; there are four 30-day months a "
            "year and the same rule answers all of them."
        ),
        tags=("month-end", "short-month"),
    ),
    ScheduleCase(
        case_id="SC-EDGE-30-FEB",
        title="Monthly on the 30th meets February",
        frequency="Monthly",
        start_day=30,
        days_to_complete=1,
        first_run=date(2026, 1, 30),
        windows=(
            (date(2026, 1, 30), date(2026, 1, 30)),
            (date(2026, 2, 28), date(2026, 2, 28)),
            (date(2026, 3, 30), date(2026, 3, 30)),
        ),
        authority=_CLAMP + " A 30th anchor gets the same answer as a 31st — one rule, not two.",
        tags=("month-end", "february"),
    ),
    ScheduleCase(
        case_id="SC-EDGE-29-FEB-COMMON",
        title="Monthly on the 29th meets February in a COMMON year",
        frequency="Monthly",
        start_day=29,
        days_to_complete=1,
        first_run=date(2026, 1, 29),
        windows=(
            (date(2026, 1, 29), date(2026, 1, 29)),
            (date(2026, 2, 28), date(2026, 2, 28)),
            (date(2026, 3, 29), date(2026, 3, 29)),
        ),
        authority=(
            _CLAMP + " This is the edge that behaves DIFFERENTLY every fourth year, so it "
            "sits beside SC-EDGE-29-FEB-LEAP where the anchor exists and no clamp fires."
        ),
        tags=("month-end", "february", "common-year"),
    ),
    ScheduleCase(
        case_id="SC-EDGE-29-FEB-LEAP",
        title="Monthly on the 29th meets February in a LEAP year — a real date, and NO clamp",
        frequency="Monthly",
        start_day=29,
        days_to_complete=3,
        first_run=date(2028, 1, 29),
        windows=(
            (date(2028, 1, 29), date(2028, 1, 31)),
            # 2028 IS a leap year, so the 29th exists and nothing is clamped:
            # the window runs Feb 29 – Mar 2 as plain arithmetic. An engine that
            # clamps unconditionally to the 28th fails this case.
            (date(2028, 2, 29), date(2028, 3, 2)),
            (date(2028, 3, 29), date(2028, 3, 31)),
        ),
        authority=(
            "B17 §2 — the anchor exists in every one of these months (2028 is a "
            'leap year), so no clamp arises. B17 §7 W2-T1, verbatim: *"A start day '
            'of 29 in a leap February is fully ruled and must NOT be stubbed."'
        ),
        tags=("month-end", "february", "leap-year", "crosses-month-end"),
    ),
    ScheduleCase(
        case_id="SC-EDGE-ANNUAL-LEAP-DAY",
        title="Annual anchored on Feb 29 — the anniversary that exists once in four years",
        frequency="Annual",
        start_day=29,
        days_to_complete=1,
        first_run=date(2028, 2, 29),
        windows=(
            (date(2028, 2, 29), date(2028, 2, 29)),
            # 2029, 2030 and 2031 have no 29 February, so the anniversary reads
            # on the 28th in each of them — and 2032 is back on the 29th.
            (date(2029, 2, 28), date(2029, 2, 28)),
            (date(2030, 2, 28), date(2030, 2, 28)),
            (date(2031, 2, 28), date(2031, 2, 28)),
            (date(2032, 2, 29), date(2032, 2, 29)),
        ),
        authority=(
            _CLAMP + " Unlike the Monthly cases this one waits THREE years for the anchor "
            "to be representable again, which is why all five occurrences are stated."
        ),
        tags=("month-end", "february", "leap-year", "slow-frequency"),
    ),
    ScheduleCase(
        case_id="SC-EDGE-QUARTERLY-31",
        title="Quarterly on the 31st — the edge is not Monthly's alone",
        frequency="Quarterly",
        start_day=31,
        days_to_complete=1,
        first_run=date(2026, 1, 31),
        windows=(
            (date(2026, 1, 31), date(2026, 1, 31)),
            (date(2026, 4, 30), date(2026, 4, 30)),  # April has 30 days
            (date(2026, 7, 31), date(2026, 7, 31)),
            (date(2026, 10, 31), date(2026, 10, 31)),
        ),
        authority=_CLAMP + " Every day-of-month frequency inherits the same rule.",
        tags=("month-end", "short-month", "slow-frequency"),
    ),
    ScheduleCase(
        case_id="SC-EDGE-YEAR-BOUNDARY",
        title="A window that crosses New Year, then meets February",
        frequency="Monthly",
        start_day=30,
        days_to_complete=4,
        first_run=date(2026, 12, 30),
        windows=(
            # Dec 30 + 3 = Jan 2. The window crossing the year is arithmetic.
            (date(2026, 12, 30), date(2027, 1, 2)),
            (date(2027, 1, 30), date(2027, 2, 2)),
            # The clamp again, reached after a window that crossed a year end —
            # so an engine cannot pass by special-casing December.
            (date(2027, 2, 28), date(2027, 3, 3)),
        ),
        authority=_CLAMP + " Reached after a window that crossed a year boundary.",
        tags=("month-end", "crosses-year-end"),
    ),
    ScheduleCase(
        case_id="SC-EDGE-LONG-WINDOW",
        title="A ten-day window from the 25th — it ends inside the next month, every time",
        frequency="Monthly",
        start_day=25,
        days_to_complete=10,
        first_run=date(2026, 1, 25),
        windows=(
            (date(2026, 1, 25), date(2026, 2, 3)),
            (date(2026, 2, 25), date(2026, 3, 6)),
            (date(2026, 3, 25), date(2026, 4, 3)),
        ),
        authority=(
            "B17 §2 — the anchor exists in all three months; a window ending in "
            "the following month needs no ruling because only the ANCHOR is a "
            "day-of-month, not the end"
        ),
        tags=("crosses-month-end",),
    ),
    ScheduleCase(
        case_id="SC-EDGE-DTC-EXCEEDS-PERIOD",
        title="Days to complete longer than the period itself — Daily with a 3-day window, and they OVERLAP",
        frequency="Daily",
        start_day=None,
        days_to_complete=3,
        first_run=date(2026, 9, 1),
        windows=(
            (date(2026, 9, 1), date(2026, 9, 3)),
            # ⚠ WINDOW 2 OPENS INSIDE WINDOW 1, AND BOTH ARE REAL. OQ-341 was
            # ruled a WARNING with an override, not a refusal, so the engine
            # GENERATES this rather than stopping at occurrence 1.
            (date(2026, 9, 2), date(2026, 9, 4)),
            (date(2026, 9, 3), date(2026, 9, 5)),
        ),
        authority=(
            "OQ-341 CLOSED — RULED 2026-08-23, PO verbatim: "
            '"B: refuse it (Daily accepts 1, Weekly <=7, Monthly <=28) - you give '
            'warning and if user override; let them do it". The PO amended option B '
            "from a refusal to a WARNING with an override, so an overridden "
            "configuration generates its overlapping windows."
        ),
        tags=("validation", "overlap"),
    ),
    ScheduleCase(
        case_id="SC-EDGE-FIRST-RUN-OFF-ANCHOR",
        title="First run on a day that is not the start day — the FIRST RUN wins",
        frequency="Monthly",
        start_day=1,
        days_to_complete=3,
        first_run=date(2026, 9, 15),
        windows=(
            # The PO's own figure. The stored start day of 1 is decorative from
            # here on — which the PO quoted back in the ruling itself.
            (date(2026, 9, 15), date(2026, 9, 17)),
            (date(2026, 10, 15), date(2026, 10, 17)),
            (date(2026, 11, 15), date(2026, 11, 17)),
        ),
        authority=(
            "OQ-340 CLOSED — RULED 2026-08-23, PO verbatim: "
            '"A: first window 15-17 Sep (start day becomes decorative)". The anchor '
            "is first_run_date's day whenever the two disagree, and every later "
            "occurrence follows it."
        ),
        tags=("validation", "anchor", "ruled-figure"),
    ),
)


# ═══════════════════════════════════════════════════════════════════════════
# 3 · THE TABLES RC-W2 ITERATES
# ═══════════════════════════════════════════════════════════════════════════
CASES: tuple[ScheduleCase, ...] = _VOCABULARY + _MONTH_END

#: One case per ruled frequency word — the "all eight frequencies pass" sweep.
VOCABULARY_CASES: tuple[ScheduleCase, ...] = _VOCABULARY

#: The month-end family W0-T2 names, including the leap year that needs no clamp.
MONTH_END_CASES: tuple[ScheduleCase, ...] = _MONTH_END


def by_id(case_id: str) -> ScheduleCase:
    """One case by id — so a test can name the exact scenario it defends."""
    for case in CASES:
        if case.case_id == case_id:
            return case
    raise KeyError(f"no CR-029 schedule case {case_id!r}; have {[c.case_id for c in CASES]}")


def cases_with_tag(tag: str) -> tuple[ScheduleCase, ...]:
    return tuple(case for case in CASES if tag in case.tags)


# ⚠ **`open_questions()` IS GONE, AND ITS ABSENCE IS THE POINT.** It printed the
# question each unruled case refused to answer, so whoever raised them to the PO
# had the plain-English sentence and a concrete date already written. All three
# — OQ-339, OQ-340, OQ-341 — were ruled on 2026-08-23, so the function would now
# return an empty tuple forever, and a reporter that can never report is exactly
# the kind of dead reassurance hard-won law 1 is about. The questions live in
# `12-governance/01-open-questions.md` with the PO's words; the answers live in
# the `authority` string of every case above.
