# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-030 (S90 · DSC-02 step 3)
# Change:   OQ-CUS-1810 CLOSED, PO 2026-09-12 — the notice period is a
#           per-tenant setting, the clock counts BUSINESS days, the roll uses
#           the tenant's own holiday calendar, and an early date WARNS.
# Rules:    BR-PAY-017 · BR-TEN-039 · BR-TEN-043 · BR-BIL-002 (the precedent)
# Tests:    this file IS the proof.
# ───────────────────────────────────────────────────────
"""The roll, tested where it actually fires.

⚠ **WHY `B18`'s OWN FIXTURE IS NOT THE TEST.** Its worked case lands the cut on
**Saturday 22 August 2026**. A weekend, so the drawn case needs no roll at all —
a naive `+2 days` passes it green, and that is the trap `DisconnectWizard.tsx`
recorded before anybody had built this. `B14` rule 37 says the same of the
blueprint's drawn `05/14/2026`: a figure in a wireframe is an illustration.

So the case below is one where the roll FIRES, and it is built on real data
rather than an invented calendar: **Memorial Day, Monday 25 May 2026, is a row
on the seeded `brazosbend` holiday calendar** — measured, 22 rows, one of them
`2026-05-25`.

    notice served    Thursday 21 May 2026
    period           five business days
    in the way       Monday 25 May 2026 — Memorial Day

    naive + 5 calendar days                  →  Tuesday 26 May 2026   ✗
    weekdays only, holidays ignored          →  Thursday 28 May 2026  ✗
    business days, holidays honoured         →  Friday 29 May 2026    ✓

**All three were run before this file was believed** (hard-won law 7), through
`pytest`, which is the harness that runs it — not through a hand-written driver.
Deleting `or cursor in holidays` from `business_days_after` gives Thursday 28
May and `test_memorial_day_pushes_the_cut_a_day_later` fails naming both dates;
replacing the loop with `start + timedelta(days=count)` gives Tuesday 26 May and
two cases fail.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.customers import cut_date

#: Memorial Day 2026, as it is seeded on a provisioned tenant.
MEMORIAL_DAY_2026 = date(2026, 5, 25)


def test_the_roll_fires_on_a_real_seeded_holiday() -> None:
    """THE CASE THAT MATTERS. Five business days from Thursday 21 May 2026, with
    Memorial Day in the way, is FRIDAY 29 MAY — not Thursday 28 May, which is
    what a weekday count with no calendar answers."""
    answer = cut_date.business_days_after(
        date(2026, 5, 21), 5, frozenset({MEMORIAL_DAY_2026})
    )
    assert answer == date(2026, 5, 29), (
        f"expected Friday 29 May 2026, got {answer:%A %d %b %Y}. Thursday 28 May "
        "means the holiday was not skipped; Tuesday 26 May means the weekend was not."
    )


def test_memorial_day_pushes_the_cut_a_day_later() -> None:
    """The SAME count over the SAME dates with an EMPTY calendar answers a day
    earlier — so this pair is what proves the calendar is actually consulted
    rather than merely passed in. A single-date assertion cannot tell the
    difference between a working skip and a holiday that happened to fall on a
    weekend."""
    with_holiday = cut_date.business_days_after(
        date(2026, 5, 21), 5, frozenset({MEMORIAL_DAY_2026})
    )
    without = cut_date.business_days_after(date(2026, 5, 21), 5, frozenset())
    assert without == date(2026, 5, 28)
    assert with_holiday == date(2026, 5, 29)
    assert (with_holiday - without).days == 1


def test_the_weekend_is_skipped_without_any_calendar() -> None:
    """Friday 22 May 2026 + 1 business day is MONDAY 25 May by the weekend rule
    alone. ⚠ And on a tenant that keeps Memorial Day it is TUESDAY 26 — the same
    input, two lawful answers, which is the whole reason the calendar is an
    argument."""
    assert cut_date.business_days_after(date(2026, 5, 22), 1, frozenset()) == date(2026, 5, 25)
    assert cut_date.business_days_after(
        date(2026, 5, 22), 1, frozenset({MEMORIAL_DAY_2026})
    ) == date(2026, 5, 26)


def test_the_notice_day_itself_is_never_counted() -> None:
    """`B4.1`'s convention, matched deliberately so the two clocks in this
    product cannot answer a regulator differently. Thursday + 1 business day is
    Friday, not Thursday."""
    assert cut_date.business_days_after(date(2026, 5, 21), 1, frozenset()) == date(2026, 5, 22)


@pytest.mark.parametrize(
    ("hours", "days"),
    [(48, 2), (24, 1), (36, 2), (72, 3), (0, 0), (1, 1)],
)
def test_hours_become_business_days_by_rounding_up(hours: int, days: int) -> None:
    """`BR-PAY-017` stores the final tier in HOURS and the PO ruled the clock in
    BUSINESS DAYS. Rounded UP, because the period is a MINIMUM granted to the
    customer and rounding down shortens their protection. `36 -> 2` is the case
    that distinguishes this from truncation."""
    assert cut_date.business_days_from_hours(hours) == days


def test_a_full_floor_on_the_seeded_48_hour_period() -> None:
    """End to end with the number a provisioned tenant actually carries:
    `final_notice_hours = 48`, measured on `brazosbend`.

    A notice served **Thursday 21 May 2026** gives TWO business days: Friday 22
    is one, the weekend is skipped, and Monday 25 would be two — except that on a
    tenant keeping **Memorial Day** it is a holiday, so the answer rolls to
    **Tuesday 26 May**.

    ⚠ **THIS ASSERTION WAS WRONG WHEN FIRST WRITTEN, AND THE CORRECTION IS WORTH
    KEEPING.** The first draft of this case claimed that at a 48-hour period the
    holiday *cannot* change the answer, and asserted Tuesday 26 for both
    calendars. `pytest` answered **Monday 25 May** for the empty one and the case
    failed. So the tenant's REAL seeded number does exercise the roll — the
    implementation was right and the reasoning about it was not, which is the
    cheapest possible version of that lesson. The five-business-day case above
    still earns its place: it is the one where a weekday-only count and a
    holiday-aware count differ, and a 48-hour period alone would not tell those
    two implementations apart on every notice date."""
    floor = cut_date.cut_floor(
        notice_served_on=date(2026, 5, 21),
        final_notice_hours=48,
        holidays=frozenset({MEMORIAL_DAY_2026}),
    )
    assert floor.business_days == 2
    assert floor.earliest == date(2026, 5, 26)
    assert floor.reason == ""
    without = cut_date.cut_floor(
        notice_served_on=date(2026, 5, 21), final_notice_hours=48, holidays=frozenset()
    )
    assert without.earliest == date(2026, 5, 25), (
        "two business days from Thursday 21 May with no calendar is MONDAY 25 May; "
        "if this says Tuesday 26 the weekend skip is wrong, and if it says Saturday "
        "23 the business-day count is not happening at all"
    )


def test_no_served_notice_means_no_floor_and_a_reason_code() -> None:
    """`disconnect_notices.served_on` is nullable and genuinely null on rows this
    product creates: the ladder ISSUES a notice and a person SERVES it outside
    the product. A floor computed from an issue date would be a legal claim about
    a letter nobody has confirmed arrived — so it answers `None`, with a CODE and
    never a sentence (`B14` rule 31)."""
    floor = cut_date.cut_floor(
        notice_served_on=None, final_notice_hours=48, holidays=frozenset()
    )
    assert floor.earliest is None
    assert floor.reason == "notice_not_served"
    assert " " not in floor.reason  # a code, not a sentence


def test_the_payload_says_it_is_not_enforced() -> None:
    """PO 2026-09-12: *"give a message but allow it"*. The wire shape carries
    `enforced: False` so a later lane cannot read this as a validator, and no
    screen puts a `min` on the date field — that would silently prevent a clerk
    typing the date at all, which is the opposite of what was ruled."""
    wire = cut_date.as_dict(
        cut_date.cut_floor(
            notice_served_on=date(2026, 5, 21), final_notice_hours=48, holidays=frozenset()
        )
    )
    assert wire["enforced"] is False
    assert wire["earliest_lawful_cut"] == "2026-05-25"  # no calendar passed here
    assert wire["unavailable_reason"] is None
    assert wire["business_days"] == 2


def test_a_period_of_nothing_answers_the_notice_date_itself() -> None:
    """A utility whose regulator grants no period is not this module's business
    to argue with. It answers the notice date rather than raising."""
    assert cut_date.business_days_after(date(2026, 5, 21), 0, frozenset()) == date(2026, 5, 21)
