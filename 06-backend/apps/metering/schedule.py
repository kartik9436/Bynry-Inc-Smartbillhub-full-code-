# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (PO 2026-08-23) — Routes & Cycles. Wave RC-W1 tasks
#           W1-T1 (🔒 the cycle schedule migration) and W1-T2 (one generation).
#           Screens: S8 · SET-05/07 · SET-07D · S27 · S31 step 1 (run picker)
# Design:   04-docs/02-decisions/17-cr029-routes-cycles-design.md (B17) §2, §6
# Rules:    the pre-CR PO ruling, verbatim — *"routes and cycles are grouping
#           only - so we will not tag late fees , etc - we can capture start
#           day, frequency, monthly, weekly daily, biweekly, once in two
#           months , quaterly etc and days to complete it ; give business names
#           to frequence - 1 word."* · D2 (*"Yes"*, unify the two column
#           generations) · BR-MET-077 · BR-MET-078 (NO money here, ever)
# Tests:    06-backend/tests/test_cr029_rcw1_schedule.py
# Impacts:  apps/metering/services.py (writes both generations through this) ·
#           apps/metering/selectors.py (`cycle_dict` derives the window here) ·
#           apps/metering/migrations/0019_cr029_cycle_schedule.py (backfill)
# ───────────────────────────────────────────────────────
"""The cycle's three facts about time, as pure functions.

A CYCLE CAPTURES EXACTLY THREE THINGS (B17 §2): **start day** · **frequency**
(one business word) · **days to complete**. The reading window is **derived,
never stored** — the upgraded prototype states it as product copy on SET-07D
(*"Derived, not stored"*).

NO ORM, NO TENANT CONTEXT, NO CLOCK, NO WRITES. Every input is an argument, in
the posture `apps/reports/dashboard_period.py` records for the same reason: the
placement of a window is arithmetic, and arithmetic that reads a clock cannot be
asserted against a signed figure.

⚠ **WHAT THIS MODULE DELIBERATELY DOES NOT DO.** It does not walk the calendar.
*"Which period is the current one for a Quarterly cycle"* needs the frequency
and the first-run date stepped forward, and that is **RC-W2's period engine**
(B17 §7 W2-T1: *"a pure derivation … → the next N windows"*). What lives here is
the one thing W1 needs and the engine will reuse: **where a window sits inside
one named month, and how long it runs**.

**THE ANCHOR IS THE CALLER'S, AND W1 PASSES THE TENANT'S TODAY.** `cycle_dict`
anchors the derived window on the month of `seams.tenant_today()` — the ops
Cycles tab and the run picker are both asking *"what is this cycle's window
now"*. That placement is a LANE JUDGMENT, not a signed rule: no ruling says
which occurrence S27 renders, and W2's engine replaces it with the true
per-frequency period. It is recorded here rather than left in a call site so the
next lane can overturn it in one place.
"""

from calendar import monthrange
from datetime import date, timedelta

#: B17 §2 — the eight one-word business names, in the design's order. The PO
#: asked for one word each (*"give business names to frequence - 1 word"*);
#: **Fortnightly** carries their *"biweekly"* because biweekly also means
#: twice-a-week in common use, and a schedule word that means two things is the
#: one thing a vocabulary exists to prevent.
FREQUENCIES: tuple[str, ...] = (
    "Daily",
    "Weekly",
    "Fortnightly",
    "Monthly",
    "Bimonthly",
    "Quarterly",
    "Semiannual",
    "Annual",
)

#: What the shipped rows and the shipped clients say, and what each becomes.
#: The three on the left of the first block are `CYCLE_FREQUENCIES` as CR-006
#: shipped it (`monthly` · `bi_monthly` · `quarterly`); the rest are the PO's
#: own spellings in the ruling, so a caller typing the sentence's words is
#: understood rather than refused.
LEGACY_FREQUENCIES: dict[str, str] = {
    "daily": "Daily",
    "weekly": "Weekly",
    "biweekly": "Fortnightly",
    "bi_weekly": "Fortnightly",
    "fortnightly": "Fortnightly",
    "monthly": "Monthly",
    "bimonthly": "Bimonthly",
    "bi_monthly": "Bimonthly",
    "quarterly": "Quarterly",
    "semiannual": "Semiannual",
    "semi_annual": "Semiannual",
    "annual": "Annual",
    "yearly": "Annual",
}


def business_frequency(value: str | None) -> str | None:
    """The business word for anything a caller or a shipped row may hold.

    Already-correct words pass through unchanged (case-insensitively, so
    `MONTHLY` and `Monthly` are one value). An unrecognised word is returned
    UNCHANGED rather than guessed at — the caller's own validation refuses it by
    name, which is a better answer than this function silently choosing one.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for word in FREQUENCIES:
        if text.lower() == word.lower():
            return word
    return LEGACY_FREQUENCIES.get(text.lower().replace("-", "_"), text)


def backfill_schedule(
    *,
    read_day_from: int | None = None,
    read_day_to: int | None = None,
    window_start: date | None = None,
    window_end: date | None = None,
) -> tuple[int | None, int | None]:  # noqa: D417 — the date pair is kept for 0019
    """W1-T1's backfill: `(start_day, days_to_complete)` from what a row has.

    **THE DAY PAIR FIRST, THE CALENDAR DATES SECOND.** `read_day_from`/
    `read_day_to` are CR-006's day-of-month DEFAULTS and say what the cycle
    normally does — *"this cycle reads on the 1st–3rd"* — which is exactly the
    new pair's meaning. `window_start`/`window_end` are one PARTICULAR period
    from the 2026-08-08 modal, so they are a weaker source: they answer "when
    did August run" and are read only when the day pair is absent.

    Both lengths are **INCLUSIVE**: reading the 1st–3rd is three days, not two.
    That is the whole reason this is a function and not a subtraction at four
    call sites.

    Returns `(None, None)` when nothing is there. A cycle nobody has scheduled
    stays unscheduled — inventing a start day here would put a window on screen
    that no human chose.

    ⚠ **`window_start` / `window_end` ARE STILL PARAMETERS AND THE COLUMNS ARE
    GONE (W5-T2, metering 0021).** They are kept because **migration 0019 calls
    this function against its own historical model**, where the columns still
    exist — that is the whole point of a historical model, and 0019 must keep
    replaying correctly on a fresh database forever. The live write path
    (`services._sync_cycle_schedule`) passes only the day pair, which is all a
    client can still send.
    """
    if read_day_from is not None and read_day_to is not None and read_day_to >= read_day_from:
        return read_day_from, read_day_to - read_day_from + 1
    if window_start is not None and window_end is not None and window_end >= window_start:
        return window_start.day, (window_end - window_start).days + 1
    if read_day_from is not None:
        return read_day_from, None
    if window_start is not None:
        return window_start.day, None
    return None, None


# ⚠ **`legacy_day_pair` IS GONE — W5-T2, 2026-08-23.** It answered
# `(read_day_from, read_day_to)` so the deprecated columns stayed TRUE while
# they existed, and metering 0021 dropped them. Nothing computes a compatibility
# copy any more; `services._check_cycle_days` keeps the one piece of arithmetic
# that outlived the columns — the derived CLOSE day, `start_day +
# days_to_complete - 1` clamped at 31 — and states there why the clamp is the
# honest reading rather than a rounding error.


def clamp_day_to_month(year: int, month: int, day: int) -> int:
    """OQ-339's ruled clamp, in ONE place: `day`, or the month's last day.

    **PO ruling 2026-08-23, verbatim:** *"there is no 31st feb so we have to
    manage either 28th or 29th of Feb."* A cycle anchored on the 29th, 30th or
    31st meets months that have no such date, and the PO chose CLAMP TO THE
    MONTH'S LAST DAY — naming BOTH February lengths themselves, which is what
    makes it leap-aware rather than a hard-coded 28. Skip (February gets no
    window) and roll (the anchor overflows into March) were both rejected.

    **Worked, and it is the figure the ruling was put on:** a Monthly cycle,
    start day 31, three days to complete. February 2026 → opens **28 Feb** and
    runs to 2 Mar. February 2028 is a leap year → opens **29 Feb**, runs to
    2 Mar.

    ⚠ **A LEAP 29th IS NOT CLAMPED.** `clamp_day_to_month(2028, 2, 29)` is 29,
    because 29 February 2028 is a real date. An engine that clamped every 29th
    would be wrong in the one year in four when the anchor exists.

    ⚠ **THE CLAMP IS PER OCCURRENCE AND NEVER MOVES THE ANCHOR.** A 31st cycle
    clamped to 28 February is back on the 31st in March. Storing the clamped day
    would quietly re-anchor the schedule, which is not what the ruling says.

    **THIS FUNCTION EXISTS BECAUSE TWO PATHS NEEDED THE SAME ANSWER.**
    `derive_read_window` below places a window in a month someone already chose
    (the ops Cycles tab, the run picker) and clamped from the day it shipped;
    `period_engine` decides WHICH OCCURRENCES EXIST and, until the ruling,
    refused to. OQ-339's closure says the two *"now agree by rule rather than by
    coincidence"* — this is that rule, called from both, so neither owns a
    second copy that could drift.

    Values below 1 are raised to 1 for the same reason the renderer already did:
    a day-of-month is 1..31 and a stored 0 is a corrupt row, not a month-end
    question.
    """
    return min(max(int(day), 1), monthrange(year, month)[1])


def derive_read_window(
    start_day: int | None, days_to_complete: int | None, anchor: date
) -> tuple[date, date] | None:
    """*"start day + N days IS the read window"* (B17 §2), placed in `anchor`'s
    month. `None` when the cycle has not been given both facts.

    **THE START DAY CLAMPS TO THE MONTH'S LAST DAY**, and since 2026-08-23 that
    is a PO RULING rather than this module's judgment: OQ-339, verbatim *"there
    is no 31st feb so we have to manage either 28th or 29th of Feb."* The
    arithmetic moved to `clamp_day_to_month` above so that `period_engine`'s
    generator and this renderer answer from ONE rule; the clamp
    `apps/reports/dashboard_regions.py` applies to its own day is the same one.

    **THE END MAY LEAVE THE MONTH.** 29 Aug + 5 days is 2 Sep, and that is the
    honest answer: the window is a LENGTH the crew works through, not a range
    inside a calendar box.

    Worked, and it is the figure the wizard shows: start day 1, 5 days to
    complete, anchored anywhere in August 2026 → **1 Aug 2026 … 5 Aug 2026**.
    """
    if start_day is None or days_to_complete is None:
        return None
    if days_to_complete < 1:
        return None
    start = date(
        anchor.year, anchor.month, clamp_day_to_month(anchor.year, anchor.month, start_day)
    )
    return start, start + timedelta(days=int(days_to_complete) - 1)


# ── Lifecycle ─────────────────────────────────────────────
# packet: B17 (04-docs/02-decisions/17-cr029-routes-cycles-design.md) §2/§6/§7 +
#         the CR-029 record in 12-governance/11-change-requests.md
# generated: 2026-08-23 by the CR-029 RC-W1 lane
# checklist: A✔ B=deferred(RC-W3 owns the screens) C✔(tests/test_cr029_rcw1_schedule.py) D✔ E✔ F✔ G✔ H=deferred(not a 🔒 path itself — no money, no rate, no RLS policy, no idempotency key; the MIGRATION that calls it is 🔒 and carries the flag)
# gates: ruff✔ black✔
# exceptions: (0) `clamp_day_to_month` is the OQ-339 RULING (PO 2026-08-23, *"there is no 31st feb so we have to manage either 28th or 29th of Feb."*) expressed once and called by both the renderer here and `period_engine`'s generator — what was a lane judgment until that date is now law, and the two agree by rule · (1) the ANCHOR MONTH for `cycle_dict`'s derived window is the tenant's today — a lane judgment, no ruling names the occurrence S27 renders, replaced by RC-W2's period engine; recorded in the module docstring and reported for a decision-log row · (2) `legacy_day_pair` clamps at 31 and is therefore lossy for a window that leaves the month — stated at the function, and the derived window carries the truth
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
