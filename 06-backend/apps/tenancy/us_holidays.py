# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-011 (S63 holiday calendar — the tenant's own dates)
#           Screens: S63
# Rules:    BR-TEN-039 (tenant holiday calendar) · BR-BIL-002 (business-day
#           grace excludes the tenant's public holidays — PO 2026-08-11) ·
#           BR-TEN-043 (event-time law: the year is an argument, never a clock)
# Tests:    06-backend/tests/test_us_ten_011_us_holidays.py
# Impacts:  apps/tenancy/services._seed_us_holidays (provisioning) ·
#           apps/billing/late_fee.py through the tenancy seam (the grace clock)
# ───────────────────────────────────────────────────────
"""The eleven US federal holidays for a year, computed rather than listed.

WHY THIS EXISTS, AND WHAT IT IS NOT. The holiday lane refused to seed any
calendar, on the ground that no signed document names a default set and this is
a multi-country product. It was right to refuse, and the consequence was stated
plainly: business-day grace behaved exactly as before, so *"the Christmas fix
does nothing until someone enters Christmas."* The PO then ruled, verbatim:

    "for time being consider USA and Load US holiday for given year as a
    seed data"

**"For the time being" is load-bearing and is why this module is named for the
country it encodes.** This is an interim default for a US-first launch, NOT a
statement that the product is US-only. The tenant's own calendar (S63 /
BR-TEN-039) remains the authority: a tenant adds, edits and deletes its dates,
and a tenant outside the US deletes these and enters its own. Nothing downstream
knows these dates came from a seed.

COMPUTED, NOT A TABLE OF DATES. A hardcoded list for 2026 is wrong in 2027, and
wrong SILENTLY — the calendar would simply hold no holidays for the current year
and every business-day grace calculation would quietly revert to weekends-only.
That is the same failure mode as a partition window that stops being renewed.
The rules below are stable federal law (5 U.S.C. § 6103) and produce any year.

────────────────────────────────────────────────────────────────────────────
THE OBSERVED-DATE RULE, and why it is applied
────────────────────────────────────────────────────────────────────────────
When a fixed-date holiday falls on a Saturday it is observed the FRIDAY before;
on a Sunday, the MONDAY after. This module seeds the OBSERVED date, because
what the calendar is used for is deciding which days an office is closed, and
that is the observed day. Independence Day 2026 falls on a Saturday: the
offices close on **Friday 3 July**, and a grace clock that skipped 4 July would
skip a day everyone worked and count a day nobody did.

⚠ FLAGGED, not assumed: the PO ruled "load US holidays" and was not shown the
observed-date question. The alternative — seeding the statutory date and
letting a tenant adjust — is defensible and produces different money on a late
fee. This reading is recorded in the human-review ledger as not covered by the
signature.

Both dates are never seeded. When 4 July is a Saturday, only 3 July is written:
a calendar holding both would remove two business days from a grace window for
one holiday, which no rule anywhere supports.
"""

from __future__ import annotations

from datetime import date, timedelta

#: 5 U.S.C. § 6103, in the order they fall. `label` is what a tenant sees on
#: S63 and may rename; the date is what the grace clock reads.
FIXED_DATE_HOLIDAYS: tuple[tuple[int, int, str], ...] = (
    (1, 1, "New Year's Day"),
    (6, 19, "Juneteenth National Independence Day"),
    (7, 4, "Independence Day"),
    (11, 11, "Veterans Day"),
    (12, 25, "Christmas Day"),
)

#: (month, weekday, nth, label) — nth is 1-based; -1 means the LAST such
#: weekday in the month. Weekday is Python's Monday=0.
FLOATING_HOLIDAYS: tuple[tuple[int, int, int, str], ...] = (
    (1, 0, 3, "Birthday of Martin Luther King, Jr."),
    (2, 0, 3, "Washington's Birthday"),
    (5, 0, -1, "Memorial Day"),
    (9, 0, 1, "Labor Day"),
    (10, 0, 2, "Columbus Day"),
    (11, 3, 4, "Thanksgiving Day"),
)


def observed(day: date) -> date:
    """The day the holiday is actually taken — Saturday → Friday, Sunday → Monday.

    Applied to FIXED-date holidays only. A floating holiday is defined as a
    weekday and can never land on a weekend, so shifting one would move a date
    the statute already placed.
    """
    if day.weekday() == 5:  # Saturday
        return day - timedelta(days=1)
    if day.weekday() == 6:  # Sunday
        return day + timedelta(days=1)
    return day


def nth_weekday(year: int, month: int, weekday: int, nth: int) -> date:
    """The nth `weekday` of a month; `nth=-1` is the last one.

    Written out rather than pulled from a package: the product's dependency
    list is not the place to resolve a five-line calendar rule, and a wrong
    holiday moves money on a late fee.
    """
    if nth == -1:
        # Walk back from the last day of the month.
        day = date(year, month, 1)
        day = date(year + (month == 12), (month % 12) + 1, 1) - timedelta(days=1)
        while day.weekday() != weekday:
            day -= timedelta(days=1)
        return day
    day = date(year, month, 1)
    while day.weekday() != weekday:
        day += timedelta(days=1)
    return day + timedelta(weeks=nth - 1)


def us_federal_holidays(year: int) -> list[tuple[date, str]]:
    """The eleven, for one year, sorted, with the observed rule applied.

    `year` is an ARGUMENT and never `date.today().year` — BR-TEN-043's
    event-time law. A caller that wants "this year" names it, so a seed run and
    a test and a re-run in 2031 all reach the same answer for the same input.
    """
    days: list[tuple[date, str]] = [
        (observed(date(year, month, day)), label) for month, day, label in FIXED_DATE_HOLIDAYS
    ]
    days += [
        (nth_weekday(year, month, weekday, nth), label)
        for month, weekday, nth, label in FLOATING_HOLIDAYS
    ]
    return sorted(days)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-011@808e015 (04-docs/05-modules/01-tenancy/02-business-rules.md ·
#         04-docs/05-modules/07-billing/02-business-rules.md — the two rules this
#         data serves; a change to either makes this stamp findable as stale)
# generated: 2026-08-11 by Eng-Lead (PO ruling: "for time being consider USA and
#         Load US holiday for given year as a seed data")
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure computation) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_ten_011_us_holidays.py
# exceptions: (1) THE OBSERVED-DATE RULE IS A CHOICE THE PO WAS NOT SHOWN. A
#         Saturday holiday is seeded on the Friday before, because the calendar
#         decides which days an office is closed; seeding the statutory date
#         instead is defensible and produces a different late fee. Flagged in
#         the human-review ledger, not treated as settled.
#         (2) This is COUNTRY-SPECIFIC by name and by design — the PO's "for
#         time being" is quoted in the docstring rather than paraphrased,
#         because a later reader needs to know this is an interim US-first
#         default and not a claim about the product's market.
#         (3) Inauguration Day (a federal holiday in the DC area only, every
#         four years) is deliberately ABSENT: it is not observed nationally and
#         seeding it would close offices in 49 states that were open.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
