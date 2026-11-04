# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-030 (S90 · DSC-02 — the disconnect wizard)
#           Screens: S90 step 3 (`DSC-02.3` — Notice & date)
# Change:   OQ-CUS-1810 CLOSED by the PO on 2026-09-12, four answers in one
#           message: the period is **a per-tenant setting, seeded with our
#           three**; the clock counts **business days**; the roll uses **the
#           tenant's own holiday calendar, which already exists**; and a date
#           before the notice **warns, it does not block** — verbatim,
#           *"give a message but allow it"*.
# Rules:    BR-PAY-017 (the per-tenant ladder intervals — `notice_tier_days`
#           and `final_notice_hours`, family `collections`, screen S70) ·
#           BR-TEN-039 (the holiday calendar is tenant reference data, S63) ·
#           BR-TEN-043 (the event-time law: the date is an ARGUMENT, never a
#           clock — and so is the calendar) · BR-BIL-002 (the ratified
#           precedent: business-day grace excludes the tenant's public
#           holidays; billing has counted this way since 2026-08-11)
# Tests:    06-backend/tests/test_cus_1810_cut_date.py
# Impacts:  apps/customers/disconnect_reads.py (serves what this computes) ·
#           07-frontend/src/features/customers/DisconnectWizard.tsx step 3
# ───────────────────────────────────────────────────────
"""The earliest date a disconnection may lawfully happen, and nothing else.

WHAT THIS MODULE IS FOR, IN ONE SENTENCE
────────────────────────────────────────
The final notice was served on a date; the regulator allows a period after it;
that period is counted in BUSINESS days and rolled past the tenant's own public
holidays; the day it lands on is the earliest lawful cut.

⚠ **IT COMPUTES AND IT DOES NOT REFUSE.** The PO ruled the floor a WARNING and
not a block — *"(b) Floor it at the notice date itself now… - give a message but
allow it"*. So nothing here raises on an early date and no caller should: a
floor that PREVENTED a clerk from typing a date would be this product asserting
a legal rule it does not yet fully hold, and the PO was offered that and chose to
inform instead. `earliest_lawful_cut` answers a date or answers `None` with a
reason; deciding what to do about it belongs to the screen.

──────────────────────────────────────────────────────────────────────────────
WHY THIS DID NOT EXIST UNTIL TODAY, AND WHAT WAS ON SCREEN INSTEAD
──────────────────────────────────────────────────────────────────────────────
Step 3 of the disconnect wizard said so, in its own words, and it was true:

    "The earliest lawful cut date is not computed anywhere in this product. It
     is the notice date plus the statutory period, rolled forward past weekends
     and public holidays, and nothing performs that roll — so this screen cannot
     show it and cannot stop an unlawful date being chosen here."

The blocker was never the arithmetic. It was that **nobody had ruled what the
period is**, and a lane that picked a number would have written a legal rule
into a money-and-service path on its own authority. `OQ-CUS-1810` was minted for
it on 2026-09-12 and answered the same day.

⚠ **AND TWO OF ITS FOUR ANSWERS ASKED FOR THINGS THAT ALREADY EXISTED.** The
question's own body — written by the lane that minted it — said *"this product
holds no holiday calendar for any tenant"*. That was false, and one `grep`
disproved it: `tenancy.HolidayCalendar` (`holiday_calendars`, per tenant, unique
on `(tenant, holiday_date)`), ratified as `BR-TEN-039` with a screen (`S63`),
seeded at provisioning by `us_holidays.py`. **And the per-tenant period existed
too**: `settings_families.COLLECTIONS` has carried `notice_tier_days = [10, 5]`
and `final_notice_hours = 48` under `BR-PAY-017`, per tenant, on `S70`, since
the collections lane — *our three, seeded, editable per utility*, which is
answer 6 word for word. So this module BUILDS NOTHING NEW for either half; it
reads what was already there through `seams.tenant_holidays` and
`seams.tenant_collections_settings`. That is hard-won law 13's cost, recorded:
asking again is a bug in us, and the one command that would have caught it is
the one the law prescribes before anything reaches the PO.

──────────────────────────────────────────────────────────────────────────────
⚠ THE TRAP THIS MODULE IS WRITTEN TO AVOID, STATED BEFORE THE CODE
──────────────────────────────────────────────────────────────────────────────
**Adding 48 hours to the notice date gets the right answer on `B18`'s fixture
BY LUCK.** B18's worked case serves its final notice such that the cut falls on
**Saturday 22 August 2026** — a weekend, so the drawn case needs no roll at all
and a wrong implementation passes it green. `B14` rule 37 compounds it: the
blueprint draws *"Earliest lawful cut 05/14/2026"* counted from *"The final
notice, 05/09/2026"*, and a figure drawn in a wireframe is an ILLUSTRATION,
never a fact to build to — so neither of the two numbers a lane would reach for
is a rule.

**So the test that matters is one where the roll actually fires**, and it is in
`tests/test_cus_1810_cut_date.py`: a notice served **Thursday 21 May 2026**,
five business days, with **Monday 25 May 2026 — Memorial Day — in the tenant's
own seeded calendar**. The answer is **Friday 29 May**. Three wrong
implementations give three different wrong answers, and all three were shown
failing before this code was believed:

    naive + 5 calendar days                     Tuesday 26 May 2026
    weekdays only, holidays ignored             Thursday 28 May 2026
    business days, holidays honoured  ← right   Friday 29 May 2026

Memorial Day 2026 is a real row on the seeded `brazosbend` calendar, measured,
not a fixture invented for the test.

──────────────────────────────────────────────────────────────────────────────
⚠ ONE READING IS RECORDED HERE RATHER THAN HIDDEN, AND IT IS THE UNIT
──────────────────────────────────────────────────────────────────────────────
`BR-PAY-017` stores the final tier as **HOURS** (`final_notice_hours = 48`) and
the two tiers above it as **DAYS** (`notice_tier_days = [10, 5]`). The PO ruled
the clock counts **business days**. Converting 48 hours into business days is
therefore forced, and it is done by DIVIDING BY 24 AND ROUNDING UP: 48 → 2, and
a utility that sets 36 gets 2 rather than 1, because a period is a MINIMUM the
regulator grants the customer and rounding it down shortens their protection.

**That is a unit conversion, not a business decision** — it is what the stored
number already means — and it is stated out loud here because it is exactly the
kind of step that looks like arithmetic and behaves like a rule. If a utility's
regulator genuinely counts the final period in clock hours rather than in
business days, this reading is wrong for them and `BR-PAY-017` needs a unit
beside the number. Nothing here guesses further than the ruling reaches.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from math import ceil
from typing import Any

#: Monday–Friday. A tenant whose working week is not this is a real thing and is
#: NOT represented: `holiday_calendars` holds dates, not a weekly pattern, and
#: inventing a per-tenant weekend here would be a second place a working week
#: lives. Reported rather than guessed.
_WEEKEND = (5, 6)


def business_days_after(start: date, count: int, holidays: frozenset[date]) -> date:
    """The date `count` business days AFTER `start`, weekends and `holidays` out.

    Counted forward from `start`, which is itself never one of the counted days
    — the notice was served ON that day and the period begins after it. This is
    the same convention `late_fee._business_days_between` uses for the grace
    clock (`B4.1`: *"counted forward from the DUE date, so the due date itself is
    never one of the grace days"*), and the two agreeing matters more than either
    choice: a product that counted a period two ways would answer a regulator
    differently depending on which screen asked.

    `holidays` is an ARGUMENT and never a query — `BR-TEN-043`. A function that
    fetched the calendar itself could not be tested against a date it did not
    also have to seed, and would behave differently between a screen's preview
    and the act it previews. An EMPTY set is a legitimate answer (a tenant that
    keeps no calendar) and is not conflated with unknown; `seams.tenant_holidays`
    is what refuses an unreachable calendar, one layer up.

    `count <= 0` answers `start` itself rather than raising: a utility whose
    regulator grants no period is not this module's business to argue with.
    """
    if count <= 0:
        return start
    cursor = start
    remaining = count
    while remaining > 0:
        cursor += timedelta(days=1)
        if cursor.weekday() in _WEEKEND or cursor in holidays:
            continue
        remaining -= 1
    return cursor


def business_days_from_hours(hours: int) -> int:
    """`BR-PAY-017`'s final tier is stored in HOURS and the clock counts BUSINESS
    DAYS, so the two have to be reconciled. See the module docstring: divide by
    24 and round UP, because the period is a MINIMUM granted to the customer and
    rounding down shortens their protection. 48 → 2 · 36 → 2 · 72 → 3 · 0 → 0.
    """
    if hours <= 0:
        return 0
    return int(ceil(hours / 24))


@dataclass(frozen=True)
class CutFloor:
    """What step 3 needs to say, and the reason when it can say nothing.

    `earliest` is `None` whenever the floor cannot be computed, and `reason` then
    carries a CODE rather than a sentence — the screen owns the words
    (`B14` rule 31: no internal reference reaches a clerk, and a server sentence
    piped to the DOM is how `DEF-CUS-5087` happened one screen over).
    """

    #: The earliest lawful cut, or `None` when it could not be worked out.
    earliest: date | None
    #: `notice_not_served` · `no_case` — never a sentence. Empty when computed.
    reason: str
    #: The date the final notice was served, echoed so a screen can show both.
    notice_served_on: date | None
    #: The period actually applied, in business days, and where it came from.
    business_days: int
    #: `True` when the tenant has saved its own number over the seeded default.
    #: A screen may say *your regulator's period* rather than *the default*.
    tenant_configured: bool


def cut_floor(
    *,
    notice_served_on: date | None,
    final_notice_hours: int,
    holidays: frozenset[date],
    tenant_configured: bool = False,
    reason_when_absent: str = "notice_not_served",
) -> CutFloor:
    """The earliest lawful cut, from a served final notice and a tenant's period.

    ⚠ **NO NOTICE DATE MEANS NO FLOOR, AND THAT IS AN ABSENCE RATHER THAN A
    ZERO.** `disconnect_notices.served_on` is nullable and genuinely null on
    rows this product has created: a notice is ISSUED by the ladder and SERVED
    by a person outside the product, and the proof of service is typed in
    afterwards. A floor computed from an issue date would be a legal claim about
    a letter nobody has confirmed arrived. So it answers `None` with
    `notice_not_served`, and the screen says the period cannot be counted yet —
    which is also, exactly, why the PO's *"floor it at the notice date itself"*
    is a warning and not a block: the product is frequently not in a position to
    know.
    """
    if notice_served_on is None:
        return CutFloor(
            earliest=None,
            reason=reason_when_absent,
            notice_served_on=None,
            business_days=business_days_from_hours(final_notice_hours),
            tenant_configured=tenant_configured,
        )
    days = business_days_from_hours(final_notice_hours)
    return CutFloor(
        earliest=business_days_after(notice_served_on, days, holidays),
        reason="",
        notice_served_on=notice_served_on,
        business_days=days,
        tenant_configured=tenant_configured,
    )


def as_dict(floor: CutFloor) -> dict[str, Any]:
    """The wire shape. Dates as ISO strings; `reason` a code, never a sentence."""
    return {
        "earliest_lawful_cut": None if floor.earliest is None else floor.earliest.isoformat(),
        "unavailable_reason": floor.reason or None,
        "notice_served_on": (
            None if floor.notice_served_on is None else floor.notice_served_on.isoformat()
        ),
        "business_days": floor.business_days,
        "tenant_configured": floor.tenant_configured,
        # ⚠ **NOT A REFUSAL, AND THE FLAG SAYS SO ON THE WIRE.** PO 2026-09-12:
        # *"give a message but allow it"*. A later lane reading this payload must
        # not turn it into a validator, and a screen must not put a `min` on the
        # date field — that would silently prevent a clerk typing the date at
        # all, which is the opposite of what was ruled.
        "enforced": False,
    }
