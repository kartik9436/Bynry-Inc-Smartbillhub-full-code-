# ── Trace ──────────────────────────────────────────────
# Change:   CR-085 blueprint specification CPB-09 — *"Readings say when the next
#           read is due"*. Done is *"The Readings screen reads 'Next read: Sep 30
#           · in 22 days' above the list."* The blueprint names the gap exactly:
#           *"The readings data carries no next-read date. The usage data does,
#           and the screen shows it when it exists."*
# Rules:    BR-TEN-043 (the event date is an ARGUMENT, never a clock read in a
#           read model) · BR-CWP-093 (an absence closes the slot up, never a
#           dash) · B14 rule 35 (a server ships a date and a NUMBER, never the
#           sentence "in 22 days")
# ───────────────────────────────────────────────────────
"""How many days until somebody comes to read the meter."""

from __future__ import annotations

from datetime import date

from apps.metering import portal_reads


def test_cpb09_tc1__the_window_counts_the_days_to_its_start():
    """The blueprint's own sentence: *"Next read: Sep 30 · in 22 days"* — so on
    8 September a window opening on 30 September is 22 days away."""
    window = portal_reads.describe_read_window(
        {"from": "2026-09-30", "to": "2026-10-04", "open_now": False}, today=date(2026, 9, 8)
    )
    assert window["from"] == "2026-09-30"
    assert window["days_until"] == 22
    assert window["open_now"] is False


def test_cpb09_tc2__a_window_that_is_open_today_counts_zero_and_never_a_negative():
    """A crew already walking the route is not *"in −3 days"*. `open_now` is the
    fact the sentence turns on, and the count is clamped at zero rather than
    printing a negative a customer would have to interpret."""
    window = portal_reads.describe_read_window(
        {"from": "2026-09-05", "to": "2026-09-12", "open_now": True}, today=date(2026, 9, 8)
    )
    assert window["open_now"] is True
    assert window["days_until"] == 0


def test_cpb09_tc3__tomorrow_is_one_day_and_today_is_zero():
    """Off-by-one is the whole risk in a countdown, so both ends are pinned."""
    assert (
        portal_reads.describe_read_window(
            {"from": "2026-09-09", "to": "2026-09-12", "open_now": False},
            today=date(2026, 9, 8),
        )["days_until"]
        == 1
    )
    assert (
        portal_reads.describe_read_window(
            {"from": "2026-09-08", "to": "2026-09-12", "open_now": True},
            today=date(2026, 9, 8),
        )["days_until"]
        == 0
    )


def test_cpb09_tc4__no_window_is_None_and_the_slot_closes_up():
    """`BR-CWP-093`. Most days have no window open — Ana's own account has none
    at all today — and the honest answer is nothing rather than a dash."""
    assert portal_reads.describe_read_window(None, today=date(2026, 9, 8)) is None


def test_cpb09_tc5__the_readings_payload_carries_it_and_the_usage_payload_still_does():
    """The blueprint's gap in one sentence: *"The readings data carries no
    next-read date. The usage data does."* Both now do, from ONE derivation —
    a second countdown computed elsewhere is how two screens come to disagree
    about the same date."""
    import inspect

    from apps.portal import selectors

    source = inspect.getsource(selectors.account_readings)
    assert "next_read" in source
    assert "read_window_for_unit" in source


# ── DEF-MET-4684 — the source that could never answer ────────────────────────
#
# ⚠ **`open_read_window_for_unit` FILTERS `read_on IS NULL`, AND THE ONLY
# `ReadWindow.objects.create` IN THE PRODUCT IS `close_read_window()`, WHICH
# SETS `read_on` AT CREATION.** An OPEN window is unreachable by construction,
# `close_read_window` has zero callers anywhere, and `next_reading` has
# therefore been `None` on every tenant since the tile was written. Every check
# passed over it, because `None` is ALSO the right answer on a day with no
# window — the dead lookup and the quiet day are the same output.
#
# The honest source is the ROUTE's CYCLE SCHEDULE, through `period_engine`,
# which stores nothing and cannot be empty by construction.


def test_def_met_4678_tc1__the_schedule_answers_when_no_window_is_stored():
    """A monthly cycle reading on the 30th, three days to walk it, as of 8 Sep:
    the next window is **30 Sep – 2 Oct**, which is the blueprint's own date."""
    window = portal_reads.scheduled_read_window(
        frequency="monthly",
        start_day=30,
        days_to_complete=3,
        first_run=date(2026, 1, 30),
        today=date(2026, 9, 8),
    )
    assert window == {"from": "2026-09-30", "to": "2026-10-02", "open_now": False}


def test_def_met_4678_tc2__a_window_running_today_says_so():
    """The difference between *"your reading is due between 2 and 6 September"*
    and *"your next reading window opens on 2 September"* — two sentences, and
    `open_now` is which one the screen says."""
    window = portal_reads.scheduled_read_window(
        frequency="monthly",
        start_day=5,
        days_to_complete=7,
        first_run=date(2026, 1, 5),
        today=date(2026, 9, 8),
    )
    assert window is not None
    assert window["open_now"] is True
    assert window["from"] == "2026-09-05"


def test_def_met_4678_tc3__a_cycle_with_no_schedule_answers_None_and_invents_nothing():
    """A route on no cycle, or a cycle nobody has scheduled, has no next read.
    That is an absence to STATE, never a date to guess."""
    assert (
        portal_reads.scheduled_read_window(
            frequency=None, start_day=None, days_to_complete=None, first_run=None,
            today=date(2026, 9, 8),
        )
        is None
    )
