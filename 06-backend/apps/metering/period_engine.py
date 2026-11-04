# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (PO 2026-08-23) — Routes & Cycles. Wave RC-W2 task W2-T1,
#           *"the period engine: a pure derivation (start day + frequency +
#           days-to-complete + first run) → the next N windows, computed on
#           demand"* (B17 §7). Kills gap G1 — *"the calendar does not tick"*.
#           Screens: SET-07.3 · SET-07D (Schedule tab) · S31 step 1 · S7
# Design:   04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §2, §7
# Rules:    D1 (*"yes"* — build the period generator; the run wizard OFFERS,
#           never forces) · the pre-CR PO ruling that named the three fields
#           and the eight one-word frequencies · D8② (*"Next cycle date"*) ·
#           BR-MET-077 (a cycle is a DEFINITION, not a schedule) ·
#           BR-MET-078 (NO money on these surfaces) · BR-TEN-043 (a window is
#           an ARGUMENT, never a clock) · CLAUDE.md prime directive
# Rulings:  **OQ-339 · OQ-340 · OQ-341 — ALL THREE CLOSED-RULED by the PO on
#           2026-08-23**, and this module is where each becomes arithmetic.
#           OQ-339 *"there is no 31st feb so we have to manage either 28th or
#           29th of Feb."* → clamp. OQ-340 *"A: first window 15-17 Sep (start
#           day becomes decorative)"* → the first run anchors. OQ-341 *"B:
#           refuse it (Daily accepts 1, Weekly <=7, Monthly <=28) - you give
#           warning and if user override; let them do it"* → warn, then
#           generate. This module holds NO stub any more.
# Tests:    06-backend/tests/test_cr029_rcw2_period_engine.py (table-driven
#           over tests/cr029_schedule_fixtures.py, RC-W0-T2)
# ───────────────────────────────────────────────────────
"""The billing calendar, as arithmetic: which windows a cycle proposes next.

════════════════════════════════════════════════════════════════════════════
COMPUTED ON DEMAND. THERE IS NO CRON AND THERE ARE NO STORED SCHEDULE ROWS
════════════════════════════════════════════════════════════════════════════
B17 §5 gap G1: *"the calendar does not tick: frequency and day defaults are
read by nothing; `read_schedules` has no writer and zero rows; every period is
typed by hand into the run wizard"*. This module closes it **without adding a
generator to keep alive**: a proposal is derived from the cycle's own three
fields the moment somebody asks, so it cannot go stale, cannot half-run, and
cannot disagree with the cycle it came from.

That is also why `read_schedules` RETIRES here rather than gaining its first
writer. Its columns (`frequency`, `last_generated_period`) are a GENERATOR's
bookkeeping — the state of a machine this design does not have. Nothing in this
wave reads it or writes it; RC-W5 drops the table.

A WINDOW IS INCLUSIVE AND IS `days_to_complete` DAYS LONG. From the PO's own
worked figure (decision log 2026-08-23, D1): *"a Monthly cycle starting the 1st
with 3 days to complete proposes **Sep 1-3** the moment August closes"* — three
days are Sep 1, 2 and 3, so the window is `[start, start + N − 1]`.

════════════════════════════════════════════════════════════════════════════
THE THREE RULINGS THIS MODULE IMPLEMENTS — PO, 2026-08-23
════════════════════════════════════════════════════════════════════════════
Until that day this module STUBBED on all three. It now implements them and
holds no `NotImplementedError` at all; each ruling is quoted where it is
executed as well as here.

**OQ-339 — A MONTH THAT HAS NO SUCH DAY: CLAMP.** Verbatim: *"there is no 31st
feb so we have to manage either 28th or 29th of Feb."* An occurrence anchored on
the 29th, 30th or 31st opens on **the last day the month actually has**, and the
PO named both February lengths, which is what makes it leap-aware. Worked:
Monthly, start 31, 3 days → February 2026 is **28 Feb – 2 Mar**; the same cycle
in leap 2028 is **29 Feb – 2 Mar**. SKIP (no February window) and ROLL (into
March) are rejected. **The clamp is per occurrence and never moves the anchor** —
March is back on the 31st. The arithmetic lives ONCE, in
`schedule.clamp_day_to_month`, called by this generator and by
`schedule.derive_read_window`'s renderer, so the two agree by rule rather than
by coincidence (which is what OQ-339 said the old arrangement was).

⚠ **A LEAP FEBRUARY IS NOT THE QUESTION.** 29 February 2028 is a real date and
is not clamped; an engine that clamped every 29th would be wrong in the one year
in four when the anchor exists.

**OQ-340 — FIRST RUN vs START DAY: THE FIRST RUN WINS.** Verbatim: *"A: first
window 15–17 Sep (start day becomes decorative)"*. When `first_run`'s day
disagrees with `start_day`, the anchor is the FIRST RUN's day and every later
occurrence follows it. Worked: Monthly, start day 1, 3 days, first run 15 Sep
2026 → **15–17 Sep**, then 15–17 Oct, then 15–17 Nov.

⚠ **AND THE STORED `start_day` THEN LIES TO THE OPERATOR**, which the PO
acknowledged in the ruling itself (*"start day becomes decorative"*). This module
does NOT rewrite the column — that value is the operator's and silently changing
it would be a second, unruled decision — so it SERVES the truth instead:
`effective_start_day()` answers the day the cycle really uses and says when it
differs from what is stored, and every schedule surface shows that rather than a
field the engine ignores.

**OQ-341 — DAYS-TO-COMPLETE LONGER THAN THE REPEAT: WARN, THEN GENERATE.**
Verbatim: *"B: refuse it (Daily accepts 1, Weekly ≤7, Monthly ≤28) - you give
warning and if user override; let them do it"* — **the PO amended option B from
a hard refusal to a warning with an override inside the ruling itself.** So
`overlap_warning()` names the collision at configuration time and this generator
produces the overlapping windows regardless: a Daily cycle with 3 days to
complete yields **1–3 Sep** and **2–4 Sep**, and both are real.

⚠ **THE COST THE RULING CREATES IS NOT THIS MODULE'S TO PAY, AND IS NOT HIDDEN.**
With overlap lawful, a read collected while two windows are open belongs to one
of them and nothing says which. `read_windows.window_for_read` states that
boundary and refuses rather than letting a call site decide it.

════════════════════════════════════════════════════════════════════════════
WEEKLY AND FORTNIGHTLY ANCHOR ON THE FIRST RUN
════════════════════════════════════════════════════════════════════════════
B17 §7 W2-T1, verbatim: *"no weekday-anchor column exists and `start_day` must
NOT be overloaded (a 1–7 that sometimes means Monday is the ambiguity the
one-word vocabulary was ruled to remove). If this wave needs the anchor, add a
new nullable column for it; otherwise anchor on `first_run` as the fixtures
do."* This wave does not need it, so no column is added and `start_day` is not
consulted for Daily, Weekly or Fortnightly — a stray value there is ignored
rather than silently read as a weekday.

════════════════════════════════════════════════════════════════════════════
NO ORM, NO TENANT, NO CLOCK
════════════════════════════════════════════════════════════════════════════
Every input is an argument (BR-TEN-043, gate G6), which is what lets the whole
calendar be asserted against the PO's own number with no fixture and no
database. Callers that need a clock read one and pass it in.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from apps.metering.schedule import FREQUENCIES, business_frequency, clamp_day_to_month

__all__ = [
    "FREQUENCIES",
    "FREQUENCY_STEP",
    "DAY_OF_MONTH_FREQUENCIES",
    "STATUS_NEXT",
    "STATUS_SCHEDULED",
    "WARN_WINDOWS_OVERLAP",
    "Window",
    "billing_period",
    "expected_span_days",
    "latest_opened_window",
    "occurrences",
    "upcoming_windows",
    "next_cycle_date",
    "effective_start_day",
    "overlap_ceiling",
    "overlap_warning",
]

#: OQ-341's warning code — the ONE machine name a screen renders when a cycle's
#: days-to-complete is longer than its own repeat. A code, not prose (G28: no
#: internal provenance reaches a utility user), and a WARNING rather than a
#: refusal because that is what the PO ruled: *"you give warning and if user
#: override; let them do it"*.
#:
#: ⚠ The three `GAP_*` codes that stood here — `cycle_month_end_anchor_unruled`,
#: `cycle_first_run_disagrees_with_start_day`, `cycle_windows_would_overlap` —
#: and the `UnruledSchedule` exception they travelled on are GONE. Each named a
#: question the PO closed on 2026-08-23, and a refusal code that can never be
#: raised is a claim a reader will believe (hard-won law 1).
WARN_WINDOWS_OVERLAP = "cycle_windows_overlap"

#: What each business word ADVANCES BY — B17 §2's "Means" column, verbatim:
#: Daily *"every day"* · Weekly *"every week"* · Fortnightly *"every two
#: weeks"* · Monthly *"every month"* · Bimonthly *"every two months"* ·
#: Quarterly *"every three months"* · Semiannual *"every six months"* ·
#: Annual *"every year"*. `("days", n)` steps whole days; `("months", n)` steps
#: the calendar, which is why the month-end question exists at all.
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

#: The words that anchor on a DAY-OF-MONTH and can therefore meet a month that
#: has no such day (B17 §2: *"day-of-month for monthly-and-slower; weekday
#: anchor for weekly/fortnightly; n/a for daily"*).
DAY_OF_MONTH_FREQUENCIES: frozenset[str] = frozenset(
    {"Monthly", "Bimonthly", "Quarterly", "Semiannual", "Annual"}
)

#: The two statuses the upgraded prototype draws on SET-07D's Schedule tab —
#: *"Next three windows with statuses Next/Scheduled"*. They are the screen's
#: own words, so they are stored nowhere and derived here from position.
STATUS_NEXT = "Next"
STATUS_SCHEDULED = "Scheduled"

#: A walk that has not reached `as_of` after this many occurrences is a
#: misconfiguration (a Daily cycle whose first run is a century back), not a
#: calendar. Refused by name rather than looping — this module is called from a
#: request path.
_MAX_STEPS = 20_000


@dataclass(frozen=True)
class Window:
    """One proposed read window: the period, its 1-based occurrence, its status.

    `status` is None from `occurrences` — a bare occurrence has no position
    relative to today — and is set by `upcoming_windows`, which is the caller
    that knows what "next" means.
    """

    period_start: date
    period_end: date
    occurrence: int
    status: str | None = None


def _word(frequency: str | None) -> str:
    """The canonical business word, or a refusal naming what was passed.

    Goes through `schedule.business_frequency` rather than owning a second
    mapping, so the shipped lowercase spellings (`monthly`, `bi_monthly`) and
    the PO's own (`biweekly`) are understood in exactly one place.
    """
    word = business_frequency(frequency)
    if word not in FREQUENCY_STEP:
        raise ValueError(
            f"unknown cycle frequency {frequency!r}. B17 §2 names eight business words "
            f"— {', '.join(FREQUENCIES)} — and a frequency the vocabulary does not hold "
            "stops the derivation rather than defaulting to Monthly, which would put a "
            "window on screen that no cycle defines."
        )
    return word


def _shift_months(anchor: date, months: int, *, day: int) -> date:
    """`anchor` moved `months` calendar months, landing on `day` — CLAMPED.

    ⚠ **THIS IS OQ-339, AND IT IS RULED.** PO 2026-08-23, verbatim: *"there is
    no 31st feb so we have to manage either 28th or 29th of Feb."* When the
    target month has no such day the occurrence opens on **the last day that
    month has** — 28 February in a common year, 29 in a leap one, which is the
    pair the PO named. Skip and roll are rejected.

    **The clamp does not move the anchor.** `day` is passed in on every call and
    is the cycle's own anchor, so a 31st cycle clamped to 28 February is back on
    the 31st in March. Re-anchoring on the clamped day would silently change the
    schedule the operator configured.

    The arithmetic itself is `schedule.clamp_day_to_month` — ONE helper shared
    with `schedule.derive_read_window`, which places a window inside a month a
    caller already picked. Before the ruling the two agreed by coincidence and
    OQ-339 said that was not an answer; they now agree by rule.
    """
    total = (anchor.year * 12 + (anchor.month - 1)) + months
    year, month = divmod(total, 12)
    month += 1
    return date(year, month, clamp_day_to_month(year, month, day))


def expected_span_days(frequency: str | None, period_start: date) -> int:
    """**BR-MET-121's bill-run half** — how many days ONE period of this
    frequency covers, starting at `period_start`. Pure; no clock.

    PO 2026-08-26, verbatim: *"when you run bill cycle you pull the reading and
    at that time we have to decide whether it is for 90 days or whrther it for
    30 days or 15 days ; and if there is an issue with reading days we flag
    it"*. The run's Days tab (W8) judges the span each read PRICES against the
    cycle being billed, and this is the cycle's own answer to "what span is
    that": the distance from `period_start` to the next occurrence, stepping
    one `FREQUENCY_STEP`.

    A days-step word answers its own constant (Fortnightly → 14). A months-step
    word answers the CALENDAR distance — Monthly from 1 Aug 2026 → **31**,
    Monthly from 1 Feb 2026 → **28**, Quarterly from 1 Jun 2026 → **92** — via
    `_shift_months`, so the OQ-339 clamp applies here exactly as it does to the
    schedule (a 31st-anchored month meeting February answers February's own
    length, never a phantom 31 days).

    Raises `ValueError` for a word the vocabulary does not hold (`_word`'s own
    refusal) — the caller reports the absence rather than judging against a
    guessed span. NOTHING here is a tenant threshold (BR-MET-020): this is the
    definition of the cycle's period, not a figure anyone tunes.
    """
    word = _word(frequency)
    unit, step = FREQUENCY_STEP[word]
    if unit == "days":
        return step
    return (_shift_months(period_start, step, day=period_start.day) - period_start).days


def _anchor_day(start_day: int | None, first_run: date) -> int:
    """The day-of-month a repeating occurrence lands on — **the first run's**.

    ⚠ **OQ-340, RULED.** PO 2026-08-23, verbatim: *"A: first window 15–17 Sep
    (start day becomes decorative)"*. A cycle whose `start_day` disagrees with
    its `first_run` is a cycle the wizard let a human save in two minds, and the
    PO chose the date they typed as the first run — so the anchor is
    `first_run.day`, always, and the stored start day drives nothing once they
    differ.

    **Worked, and it is the figure the ruling was put on:** Monthly, start day 1,
    3 days to complete, first run 15 Sep 2026 → the first window opens 15 Sep and
    every later one follows the 15th.

    **`start_day` is therefore not read here at all.** That is deliberate: a
    branch that used it when the two agreed and ignored it when they did not
    would compute the identical answer by two paths, and the second path is where
    a divergence would eventually hide. What the operator is OWED is not a secret
    use of their field but an honest statement of what the cycle does —
    `effective_start_day` below, served on the schedule payload.

    This lane recommended refuse-at-save (reading C) and was overruled; the
    recommendation and its reasoning stay in OQ-340's supersedes chain.
    """
    del start_day  # decorative once it disagrees — see the docstring
    return first_run.day


def effective_start_day(
    *, frequency: str | None, start_day: int | None, first_run: date | None
) -> dict[str, Any]:
    """What day this cycle ACTUALLY starts on, and whether the stored one agrees.

    ⚠ **THE HONEST FOLLOW-ON OQ-340 CREATES.** With the first run as the anchor,
    `cycles.start_day` can disagree with everything the cycle does — and *a
    stored field the engine ignores is a field that lies to the operator*. The
    column is NOT rewritten (that value is the operator's own, and changing it
    silently would be a second decision nobody ruled); the truth is SERVED
    beside it so a screen shows what the cycle does and can say that the stored
    value is decorative.

    Returns three keys, and the screens read all three:

      `effective_start_day` — the day occurrences open on, or `None` for the
          words that have no day-of-month anchor at all (Daily, Weekly,
          Fortnightly — B17 §7: *"`start_day` must NOT be overloaded"*).
      `start_day`           — what is stored, unchanged.
      `differs`             — `True` when the two are not the same number, which
          is exactly when a screen must show the effective day rather than the
          stored one.

    Worked: `{"effective_start_day": 15, "start_day": 1, "differs": True}` for
    the PO's own figure. `None` for a cycle with no first run: nothing anchors
    it yet, so there is no effective day to claim.
    """
    stored = None if start_day is None else int(start_day)
    try:
        word = _word(frequency)
    except ValueError:
        return {"effective_start_day": None, "start_day": stored, "differs": False}
    if word not in DAY_OF_MONTH_FREQUENCIES or first_run is None:
        return {"effective_start_day": None, "start_day": stored, "differs": False}
    effective = _anchor_day(stored, first_run)
    return {
        "effective_start_day": effective,
        "start_day": stored,
        "differs": stored is not None and stored != effective,
    }


def cycle_read_window(cycle: Any, anchor: date) -> tuple[date, date] | None:
    """**THE ONE READ WINDOW** a cycle has in `anchor`'s month — every surface
    that prints or checks a read window asks this (`DEF-MET-10588`, MQ-033,
    PO 2026-10-24: one read window).

    The start day is the EFFECTIVE one (`effective_start_day` above, OQ-340:
    the first run anchors) and the stored `start_day` only where nothing
    anchors the cycle — no first run, or a frequency with no day of month — so
    Reads and Settings cannot print two windows for one cycle. The window
    itself is `schedule.derive_read_window`, unchanged.

    Worked, the figure the defect was filed on (Brookfield `CY-001`): stored
    start day **10**, first run on the **14th**, 5 days to complete, anchored
    in October 2026 → **14 Oct … 18 Oct**, which Settings already printed;
    Reads printed 10 Oct … 14 Oct off the stored day until this existed.
    `None` when the cycle has not been given a day and a length.
    """
    from apps.metering.schedule import derive_read_window

    if cycle is None:
        return None
    anchor_day = effective_start_day(
        frequency=getattr(cycle, "frequency", None),
        start_day=getattr(cycle, "start_day", None),
        first_run=getattr(cycle, "first_run_date", None),
    )["effective_start_day"]
    start_day = anchor_day if anchor_day is not None else getattr(cycle, "start_day", None)
    return derive_read_window(start_day, getattr(cycle, "days_to_complete", None), anchor)


def overlap_ceiling(frequency: str | None) -> int:
    """The longest days-to-complete a cycle of this word can hold without its
    windows colliding — the threshold OQ-341's warning fires above.

    **PO 2026-08-23, verbatim:** *"B: refuse it (Daily accepts 1, Weekly ≤7,
    Monthly ≤28) - you give warning and if user override; let them do it"*. The
    three quoted numbers are the three the PO named; the rest are DERIVED the
    same way, which the ruling asks for by naming only three of eight.

    **The rule behind all eight: the SHORTEST gap the calendar can put between
    two consecutive occurrences.** Daily 1 · Weekly 7 · Fortnightly 14 are fixed
    day steps. The month-stepping words vary, so the ceiling is the minimum —
    Monthly is **28** because February is 28 days, which is exactly the number
    the PO quoted, and that is what makes this the derivation they had in mind
    rather than one of the alternatives (30, or 31, or the month's own length).
    Bimonthly is 59 (Jan+Feb), Quarterly 89 (Feb+Mar+Apr), Semiannual 181
    (Feb–Jul), Annual 365 (a common year).

    Computed rather than tabulated so the eight cannot drift from the eight
    words, and computed over a COMMON year: a leap day only ever makes the gap
    longer, and a ceiling that assumed one would miss the collision three years
    in four.
    """
    word = _word(frequency)
    unit, step = FREQUENCY_STEP[word]
    if unit == "days":
        return step
    # The shortest run of `step` consecutive months anywhere in a common year.
    lengths = [monthrange(2026, month)[1] for month in range(1, 13)]
    doubled = lengths + lengths
    return min(sum(doubled[start : start + step]) for start in range(12))


def overlap_warning(
    *, frequency: str | None, days_to_complete: int | None
) -> dict[str, Any] | None:
    """OQ-341's warning: *"you give warning and if user override; let them do it"*.

    `None` when the configuration fits. Otherwise a dict NAMING THE COLLISION —
    the word, the days asked for and the most that word can hold — so the screen
    can say *"a Daily cycle completes in 1 day; 3 means the next window opens
    before this one finishes"* rather than a bare "invalid".

    ⚠ **THIS IS NOT A REFUSAL AND MUST NEVER BECOME ONE.** The PO amended their
    own option B in the ruling itself: warn, and if the operator overrides, the
    configuration is accepted and the engine generates the overlapping windows.
    A caller that turned this dict into a `ValidationError` would be building
    reading B as it was written and not as it was ruled.

    Worked, on the figure the PO was shown: Daily with 3 days to complete →
    `{"code": "cycle_windows_overlap", "frequency": "Daily",
      "days_to_complete": 3, "max_days_to_complete": 1}`.
    """
    if days_to_complete is None:
        return None
    try:
        word = _word(frequency)
    except ValueError:
        # An unknown word has no repeat to compare against. The caller's own
        # validation refuses it by name; inventing a ceiling here would warn
        # about the wrong thing.
        return None
    try:
        days = int(days_to_complete)
    except (TypeError, ValueError):
        return None
    ceiling = overlap_ceiling(word)
    if days <= ceiling:
        return None
    return {
        "code": WARN_WINDOWS_OVERLAP,
        "frequency": word,
        "days_to_complete": days,
        "max_days_to_complete": ceiling,
    }


def _walk(
    *,
    frequency: str | None,
    start_day: int | None,
    days_to_complete: int | None,
    first_run: date | None,
    limit: int,
):
    """Every occurrence from the first run onward, in order, one at a time.

    Yields `Window`s with `status=None`. Every case this generator can meet is
    ruled since 2026-08-23 — the month-end clamp (OQ-339), the anchor when the
    first run disagrees with the start day (OQ-340) and windows that overlap
    (OQ-341) — so it raises nothing but the two structural refusals below: an
    unknown frequency word, and a days-to-complete under one day.
    """
    if days_to_complete is None or first_run is None:
        return
    if int(days_to_complete) < 1:
        raise ValueError(
            f"days_to_complete is {days_to_complete}; a read window is at least one day "
            "long (B17 §2: 'start day + N days IS the read window', inclusive)."
        )
    word = _word(frequency)
    length = timedelta(days=int(days_to_complete) - 1)
    unit, step = FREQUENCY_STEP[word]
    day_of_month = _anchor_day(start_day, first_run) if word in DAY_OF_MONTH_FREQUENCIES else None

    for index in range(limit):
        if index == 0:
            start = first_run
        elif unit == "days":
            start = first_run + timedelta(days=step * index)
        else:
            assert day_of_month is not None
            start = _shift_months(first_run, step * index, day=day_of_month)
        # ⚠ **NO OVERLAP CHECK LIVES HERE ANY MORE — OQ-341, RULED.** This loop
        # used to raise the moment occurrence n+1 opened inside occurrence n,
        # because generating it would have asserted that read windows may
        # overlap. The PO ruled that they may: *"you give warning and if user
        # override; let them do it"*. So the collision is a CONFIGURATION-time
        # warning (`overlap_warning`) and the generator produces both windows —
        # a crew really can be working two at once. A refusal reinstated here
        # would build option B as it was written rather than as it was amended.
        yield Window(period_start=start, period_end=start + length, occurrence=index + 1)


def occurrences(
    *,
    frequency: str | None,
    start_day: int | None,
    days_to_complete: int | None,
    first_run: date | None,
    count: int,
) -> tuple[Window, ...]:
    """The first `count` windows this cycle defines, from its first run onward.

    Returns `()` for a cycle that has not been given a first run or a
    days-to-complete: a cycle nobody has scheduled has no window, and inventing
    one would put a period in the run wizard that no human chose (the posture
    `schedule.backfill_schedule` already takes for the same reason).

    Worked, and it is the PO's own figure: `Monthly`, start day 1, 3 days to
    complete, first run 1 Sep 2026 → **1–3 Sep**, then **1–3 Oct**, then
    **1–3 Nov**.
    """
    if count < 1:
        return ()
    return tuple(
        _walk(
            frequency=frequency,
            start_day=start_day,
            days_to_complete=days_to_complete,
            first_run=first_run,
            limit=count,
        )
    )


def upcoming_windows(
    *,
    frequency: str | None,
    start_day: int | None,
    days_to_complete: int | None,
    first_run: date | None,
    as_of: date,
    count: int = 3,
) -> tuple[Window, ...]:
    """The next `count` windows as of a given day — the run wizard's proposal.

    **THE FIRST ONE IS THE ONE STILL RUNNING, IF ONE IS.** A window is skipped
    only once it has ENDED. D1's figure says Sep 1–3 is proposed *"the moment
    August closes"*; while August's own window is still open it is still the
    period a run would cover, so it stays the offer.

    ⚠ That reading of *"the moment August closes"* is a LANE JUDGMENT — the
    ruling states the figure for a closed month and says nothing about the days
    inside a running window — and it is written here rather than left in a call
    site so the next lane can overturn it in one place. Worked: as of **2 Aug**
    a 1st/3-day Monthly cycle offers **1–3 Aug**; as of **4 Aug** it offers
    **1–3 Sep**.

    Statuses are the upgraded prototype's own: the first is **Next**, the rest
    **Scheduled**. Nothing is stored — a status is a position, not a state.
    """
    if count < 1:
        return ()
    found: list[Window] = []
    for window in _walk(
        frequency=frequency,
        start_day=start_day,
        days_to_complete=days_to_complete,
        first_run=first_run,
        limit=_MAX_STEPS,
    ):
        if window.period_end < as_of:
            continue
        found.append(
            Window(
                period_start=window.period_start,
                period_end=window.period_end,
                occurrence=window.occurrence,
                status=STATUS_NEXT if not found else STATUS_SCHEDULED,
            )
        )
        if len(found) == count:
            break
    return tuple(found)


def latest_opened_window(
    *,
    frequency: str | None,
    start_day: int | None,
    days_to_complete: int | None,
    first_run: date | None,
    as_of: date,
) -> Window | None:
    """The most recent occurrence to have **opened** on or before `as_of`.

    `upcoming_windows` answers *what comes next*; this answers *what are we in
    the middle of, or have just come out of* — and BR-MET-132 is the rule that
    needed the second question asked. Verbatim (PO 2026-08-26): *"Keep counting
    until the run consumes the period — those are the chase days"*. On 22 Aug,
    with a reading window that ran 16–20 Aug, `upcoming_windows` has already
    moved on to September; the window a clerk is chasing is the August one, and
    only this function can name it.

    `None` when no occurrence has opened yet — a cycle whose first window is
    still in the future, and a cycle with no schedule at all (no `first_run` or
    no `days_to_complete`, where `_walk` yields nothing by rule). Both are a
    STATED absence: the caller falls back to the upcoming window and reports
    `before_open`, never a fabricated past.

    Pure, like everything else here: `as_of` is passed in, never read from a
    clock (BR-TEN-043).

    Worked, on the PO's own figure: Monthly, start day 16, 5 days to complete,
    first run 16 Aug 2026 → asked on **18 Aug** returns **16–20 Aug** (open),
    asked on **22 Aug** returns **16–20 Aug** (closed), asked on **17 Sep**
    returns **16–20 Sep**.
    """
    latest: Window | None = None
    for window in _walk(
        frequency=frequency,
        start_day=start_day,
        days_to_complete=days_to_complete,
        first_run=first_run,
        limit=_MAX_STEPS,
    ):
        if window.period_start > as_of:
            break
        latest = window
    return latest


def _anchors(*, frequency: str, start_day: int | None, first_run: date, limit: int):
    """Every occurrence's ANCHOR DATE from the first run onward. No window.

    ⚠ **`days_to_complete` IS NOT AN ARGUMENT HERE, AND THAT IS THE WHOLE
    POINT.** `_walk` above yields READ WINDOWS and needs the length because a
    window has one; a period boundary does not. How many days the crew takes to
    walk the route cannot change where one billing period ends and the next
    begins — and `_walk` returning nothing for a cycle with no
    `days_to_complete` would have made a perfectly well-scheduled cycle
    unbillable (`DEF-2708`).

    The two rulings that place an anchor are the SAME ones `_walk` obeys, and
    they are obeyed here by calling the same two helpers rather than by copying
    them: `_anchor_day` (OQ-340 — the first run wins) and `_shift_months`
    (OQ-339 — the month-end clamp).
    """
    unit, step = FREQUENCY_STEP[frequency]
    day_of_month = (
        _anchor_day(start_day, first_run) if frequency in DAY_OF_MONTH_FREQUENCIES else None
    )
    for index in range(limit):
        if index == 0:
            yield first_run
        elif unit == "days":
            yield first_run + timedelta(days=step * index)
        else:
            assert day_of_month is not None
            yield _shift_months(first_run, step * index, day=day_of_month)


def billing_period(
    *,
    frequency: str | None,
    start_day: int | None,
    first_run: date | None,
    as_of: date | None,
) -> tuple[date, date] | None:
    """**B4.3's DENOMINATOR, LOCATED ON A CALENDAR** — the BILLING period
    containing `as_of`, as `(start, end)` inclusive. Pure; no ORM, no clock.

    🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — AI-authored 2026-08-31 under the PO
    ruling of 2026-08-09 (*"AI will do it; we will review it later as human"*).
    This function decides the number a customer's standing charge is DIVIDED BY,
    so it is a money path however little arithmetic it contains; a row in
    `12-governance/09-human-review-ledger.md` states in plain English what it
    does and with which figures ($23.23 against $40.00). ⚠ **NO GLOB IN
    `10-scripts/gates/human_owned.txt` MATCHES THIS FILE**, so G7 reports
    conform over it. A lane may not add itself to that list, so the glob is
    ASKED FOR in the ledger row — the SEVENTH time this escape has hit a money
    path (`issue.py`, `decisions.py`, `read_analysis.py` and `cut_bill.py` each
    record an earlier one in their own margins).

    ⛔ **THIS IS NOT `latest_opened_window`, AND CONFUSING THE TWO IS `DEF-2708`
    — $16.77 on one customer's final bill.** A `Window` in this module is the
    READ window: `[anchor, anchor + days_to_complete − 1]`, the days the crew is
    out with the handheld, and this module's own worked figure says a Monthly
    cycle with 3 days to complete proposes *"Sep 1-3"*. **Three days is not a
    month.** The BILLING period is the span the standing charge covers, and it
    runs **anchor → the day before the NEXT anchor**. The read window is a short
    sub-window inside it, sharing its start.

    ════════════════════════════════════════════════════════════════════════
    WHY THE END IS THE NEXT ANCHOR AND NOT `expected_span_days`
    ════════════════════════════════════════════════════════════════════════
    `expected_span_days(frequency, period_start)` answers the same question by
    re-stepping from `period_start` — and for every anchor of the 28th or
    earlier the two agree exactly (1 Aug 2026 → 31 either way, which is the
    PO's own figure, asserted in
    `tests/test_def2708_billing_period_for_unit.py` TC-4 so the agreement is by
    rule rather than by coincidence).

    They diverge for a **month-end anchor**, and there the next anchor is right.
    A cycle anchored on the 31st opens 31 Jan → 28 Feb (OQ-339's clamp) →
    31 Mar. Re-stepping from the CLAMPED 28 Feb uses day 28 and answers 27 Mar,
    which leaves **28, 29 and 30 March in no period at all** — three days a
    customer cut on the 29th would be prorated against a period that does not
    contain their cut. `_shift_months` never moves the anchor (its own
    docstring), so walking the anchors keeps the periods tiling.

    ════════════════════════════════════════════════════════════════════════
    `None` IS AN HONEST ANSWER AND IT HAS FOUR CAUSES
    ════════════════════════════════════════════════════════════════════════
    A cycle with **no first run** (nothing anchors it — the posture
    `occurrences` already takes), a **frequency the vocabulary does not hold**
    (a pre-CR-029 cycle, or hand-written text), an `as_of` **before the first
    run** (no period has opened yet), and an `as_of` more than `_MAX_STEPS`
    occurrences out (a misconfiguration, refused rather than looped). In every
    one of them the caller STATES the absence — assuming a 30-day month would
    be money invented from a calendar nobody configured, which is exactly what
    `apps/billing/cut_bill.CUT_BILL_DENOMINATOR_ABSENT` exists to say.

    ⚠ **`as_of` IS AN ARGUMENT (BR-TEN-043 / G6).** A cut on 18 February
    committed by a clerk in March must divide by **February's 28 days**, not by
    March's 31: the same $40.00 base is $23.23 over 31 days and $25.71 over 28.
    Nothing here reads a clock.

    Worked, and it is the figure the PO was shown: Monthly, first run
    1 Aug 2026, asked on the cut day 18 Aug → **(1 Aug 2026, 31 Aug 2026)**,
    31 days, so 18 days of a $40.00 base is **$23.23**.
    """
    if first_run is None or as_of is None:
        return None
    try:
        word = _word(frequency)
    except ValueError:
        # An unruled frequency has no repeat, so it has no period. The caller
        # reports that; a defaulted "Monthly" here would divide a quarterly
        # customer's base charge by a third of its period, every period.
        return None
    opened: date | None = None
    for anchor in _anchors(
        frequency=word, start_day=start_day, first_run=first_run, limit=_MAX_STEPS
    ):
        if anchor > as_of:
            return None if opened is None else (opened, anchor - timedelta(days=1))
        opened = anchor
    return None


def next_cycle_date(
    *,
    frequency: str | None,
    start_day: int | None,
    days_to_complete: int | None,
    first_run: date | None,
    as_of: date,
) -> date | None:
    """D8② — the date *"closes in 4 days"* counts to. PO: *"Next cycle date"*.

    The next date this cycle comes round: the START of the first occurrence on
    or after `as_of`. **On the day itself it returns that day**, which is what
    makes the *"closes today"* state reachable.

    NOT the end of the window it is inside, and NOT the bill day. Those were the
    two candidates the countdown used to derive itself from (OQ-221's four-state
    reading, `dashboard_regions.CYCLE_CLOSE_FIELD`), and the PO named neither.

    `None` when the cycle has no schedule to speak of — a cycle with no first
    run or no days-to-complete has no next date, and inventing one would put a
    countdown on the dashboard that no cycle defines.

    ⚠ It used to RAISE for a month-end-anchored cycle and `selectors.cycle_dict`
    rendered the silence. OQ-339 closed that: a 31st cycle asked on 10 February
    2026 answers **28 February 2026**.
    """
    for window in _walk(
        frequency=frequency,
        start_day=start_day,
        days_to_complete=days_to_complete,
        first_run=first_run,
        limit=_MAX_STEPS,
    ):
        if window.period_start >= as_of:
            return window.period_start
    return None


# ── Lifecycle ─────────────────────────────────────────────
# packet: B17 (04-docs/02-decisions/17-cr029-routes-cycles-design.md) §2/§5/§7 RC-W2-T1 + the CR-029 record in 12-governance/11-change-requests.md (D1 · D8②) + OQ-339
# screens: S7 · SET-07.3 · SET-07D · S31
# generated: 2026-08-23 by the CR-029 RC-W2 lane
# checklist: A✔ B=deferred(RC-W3-T4 owns SET-07D's schedule card; the FE wiring of the run wizard's prefill is reported to the frontend lane) C✔(tests/test_cr029_rcw2_period_engine.py — RED first: ImportError, no such module) D✔ E✔ F✔ G✔ H=deferred(not a 🔒 path — no money, no rate, no RLS policy, no idempotency key; it derives DATES)
# gates: ruff✔ black✔
# exceptions: (1) 🔒 OQ-339 STUBBED on the generate-occurrences path — the month-end anchor is unruled and the three readings produce different bills · (2) OQ-340 stubbed (first run disagreeing with start day) and OQ-341 stubbed (days-to-complete longer than the period) — both REPORTED by this lane for minting, neither invented an answer · (3) *"the window still running is still the one offered"* is a LANE JUDGMENT over D1's figure, argued in `upcoming_windows` with its worked dates · (4) `start_day` is NOT consulted for Daily/Weekly/Fortnightly and no weekday-anchor column is added, per B17 §7's explicit instruction
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
