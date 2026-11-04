# ── Trace ──────────────────────────────────────────────
# Epics:    EP-BIL-01 (bill run — late-fee assessment)
#           Screens: — (the fee line renders on the invoice / S31.2)
#           NOTE: no US-ID is cited in this header ON PURPOSE. The story that
#           owns the late-fee candidate list is the whole six-tab S31.2 preview,
#           and this file ships one calculation of it, not the story. The story
#           is named in the docstring. Same precedent as
#           apps/billing/rating_seam.py.
# Rules:    BR-BIL-001 (late fee = max($5, 1.5% × OVERDUE PORTION); grace from
#           the DUE date) · BR-BIL-008 (grace: tenant-defined, default 5
#           calendar days, range 0–30) · BR-BIL-002 (calendar OR business days,
#           both modes) · BR-BIL-003 (waiver is manual, never automatic) ·
#           BR-TEN-043 (event-time law: `as_of` is an argument, not a clock)
# Golden:   GT-8 — B5 ❄️ FROZEN 2026-08-08. The frozen FIGURE (8.13) is asserted
#           in 06-backend/tests/golden/test_gt08_late_fee.py; this file asserts
#           the grace clock, which B5 states in words and not in dates.
# Tests:    this file
# Impacts:  apps/billing/late_fee.py · apps/billing/services.py
# ───────────────────────────────────────────────────────
"""The late-fee grace clock — the half GT-8 states in words rather than dates.

Serves US-BIL-002 (the Balances tab's late-fee candidates) without shipping it.

B5 GT-8 says "past Due date beyond grace" and gives no calendar. So the FIGURE
is pinned by the golden file and the CLOCK is pinned here, from BR-BIL-001/008
(grace runs from the due date, tenant-defined length, default 5) and BR-BIL-002
(calendar or business days).

    ✅ BOTH OPEN BOUNDARIES ARE NOW RULED (PO, 2026-08-11). This block used to
    say "one boundary is reported, not settled"; it no longer is, and the note
    is kept in its resolved form rather than deleted so the history reads.

    1. WHERE "beyond grace" STARTS. EP-BIL-01 §7's two worked examples implied
       boundaries one business day apart — WE-15(d) has the fee apply strictly
       AFTER the grace days elapse, WE-15(e) has it apply ON the day they
       expire. B4/B5 froze neither. `late_fee.py` applied WE-15(d)'s convention
       to BOTH modes, and the PO RULED that convention correct for both on
       2026-08-11 (due Thu 10 Sep + 5 grace → calendar Wed 16 Sep, business-day
       Fri 18 Sep, not Thu 17). WE-15(e)'s text is the erroneous one.

    2. PUBLIC HOLIDAYS. Business days were Mon–Fri with no holiday calendar, so
       Christmas Day counted as a working day and a bill due Thu 24 Dec 2026
       with 5 business days' grace had its fee assessed on Fri 1 Jan, New Year's
       Day. The PO ruled 2026-08-11 (option A, "build the holiday calendar now")
       that the clock skips the tenant's public holidays: the same bill is now
       assessed Tue 5 Jan. `test_business_day_grace_skips_public_holidays`
       asserts both the ruled answer and the rejected one.

    The business-day assertions below are therefore RATIFIED figures, not
    merely consistency checks against calendar mode as they once were.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import late_fee, services

# GT-8's inputs (the figures themselves are asserted in tests/golden/).
OVERDUE = Decimal("542.10")
PERCENT = Decimal("0.015")
MINIMUM = Decimal("5")
DUE = date(2026, 7, 15)  # a Wednesday


#: A tenant that keeps NO holiday calendar, stated explicitly. Business-day
#: mode refuses `None` (PO ruling 2026-08-11) precisely so that "no holidays"
#: is something a caller says rather than something it gets by not thinking.
NO_HOLIDAYS: frozenset[date] = frozenset()


def assess(as_of, grace_days=5, mode="calendar", overdue=OVERDUE, holidays=NO_HOLIDAYS):
    return services.assess_late_fee(
        overdue_amount=overdue,
        percent=PERCENT,
        minimum=MINIMUM,
        due_date=DUE,
        as_of=as_of,
        grace_days=grace_days,
        grace_mode=mode,
        holidays=holidays,
    )


def test_grace_is_counted_from_the_due_date_in_calendar_days():
    """BR-BIL-001/008 — 5 calendar days from Jul 15 means Jul 20 is still free."""
    assert assess(date(2026, 7, 15)) == Decimal("0.00")  # due date itself
    assert assess(date(2026, 7, 20)) == Decimal("0.00")  # last grace day
    assert assess(date(2026, 7, 21)) == Decimal("8.13")  # first day past grace


def test_grace_length_is_a_tenant_setting_not_a_constant():
    """BR-BIL-008 — 0–30, tenant-defined; 5 is a DEFAULT nothing here supplies."""
    assert assess(date(2026, 7, 16), grace_days=0) == Decimal("8.13")
    assert assess(date(2026, 7, 15), grace_days=0) == Decimal("0.00")
    assert assess(date(2026, 8, 14), grace_days=30) == Decimal("0.00")
    assert assess(date(2026, 8, 15), grace_days=30) == Decimal("8.13")


def test_a_grace_setting_outside_the_ratified_range_refuses():
    """Hard-won law 3 — a misconfigured tenant setting stops the assessment."""
    with pytest.raises(ValueError, match="BR-BIL-008"):
        assess(date(2026, 9, 1), grace_days=45)
    with pytest.raises(ValueError, match="BR-BIL-008"):
        assess(date(2026, 9, 1), grace_days=-1)


def test_an_unknown_grace_mode_refuses_rather_than_falling_through():
    """A mode the code does not implement never silently becomes the other one."""
    with pytest.raises(ValueError, match="BR-BIL-002"):
        assess(date(2026, 7, 30), mode="banking_days")


def test_business_day_mode_skips_weekends_consistently_with_calendar_mode():
    """BR-BIL-002 — both modes required; the BOUNDARY convention is shared.

    Due Wed Jul 15, 5 business days: Thu 16, Fri 17, Mon 20, Tue 21, Wed 22 —
    grace expires with Jul 22, and (per the convention this lane applies to both
    modes) the fee applies from Jul 23. Under calendar mode the same 5 days run
    out on Jul 20. The weekend is what separates them, which is the whole
    content of the setting.

    RULED 2026-08-11 by the PO: the "strictly after" convention is correct for
    both modes. WE-15(e) placed it one business day earlier and is the erroneous
    example. This was REPORTED, not decided, until that ruling.
    """
    assert late_fee._business_days_between(DUE, date(2026, 7, 22), NO_HOLIDAYS) == 5
    assert assess(date(2026, 7, 21), mode="business") == Decimal("0.00")
    assert assess(date(2026, 7, 22), mode="business") == Decimal("0.00")
    assert assess(date(2026, 7, 23), mode="business") == Decimal("8.13")
    # The same as_of date, the two modes, different answers — the setting bites.
    assert assess(date(2026, 7, 21), mode="calendar") == Decimal("8.13")


def test_business_day_grace_skips_public_holidays():
    """PO ruling 2026-08-11 — the worked case they were shown, as a test.

    Bill due Thu 24 Dec 2026, 5 business days' grace.

      Mon-Fri only : Fri 25 (Christmas) · Mon 28 · Tue 29 · Wed 30 · Thu 31
                     -> fee charged Fri 1 Jan, NEW YEAR'S DAY
      holiday-aware: Mon 28 · Tue 29 · Wed 30 · Thu 31 · Mon 4 Jan
                     -> fee charged Tue 5 Jan

    Four days of grace, and the difference between assessing a fee on a public
    holiday and not. Both halves are asserted so the test states the behaviour
    that was rejected as well as the one that was ruled.
    """
    christmas_due = date(2026, 12, 24)  # a Thursday
    tenant_holidays = frozenset({date(2026, 12, 25), date(2027, 1, 1)})

    def charged_on(as_of, holidays):
        return services.assess_late_fee(
            overdue_amount=OVERDUE,
            percent=PERCENT,
            minimum=MINIMUM,
            due_date=christmas_due,
            as_of=as_of,
            grace_days=5,
            grace_mode="business",
            holidays=holidays,
        )

    # Holiday-aware: 1 Jan is still inside grace, 5 Jan is past it.
    assert charged_on(date(2027, 1, 1), tenant_holidays) == Decimal("0.00")
    assert charged_on(date(2027, 1, 4), tenant_holidays) == Decimal("0.00")
    assert charged_on(date(2027, 1, 5), tenant_holidays) == Decimal("8.13")

    # The rejected behaviour, kept so the ruling's effect is visible: with no
    # calendar, the fee lands ON New Year's Day.
    assert charged_on(date(2027, 1, 1), NO_HOLIDAYS) == Decimal("8.13")


def test_business_day_grace_refuses_an_unstated_holiday_calendar():
    """Hard-won law 3 — the unsafe option must be the one you type.

    Defaulting `holidays` to Mon-Fri would silently reinstate the behaviour the
    PO ruled against, and would do it for every caller that simply had not been
    updated. So business mode refuses `None`. Calendar mode does NOT, because
    calendar days are calendar days and a caller need not branch on the mode.
    """
    with pytest.raises(ValueError, match="holiday calendar"):
        assess(date(2026, 7, 23), mode="business", holidays=None)

    assert assess(date(2026, 7, 21), mode="calendar", holidays=None) == Decimal("8.13")


def test_the_fee_is_a_percentage_of_the_overdue_portion_only():
    """B4.1 — the base is the past-due part, never the full balance.

    The caller supplies the overdue portion; a bigger balance behind it cannot
    change the answer, because the function is never told about it.
    """
    assert assess(date(2026, 7, 21), overdue=Decimal("542.10")) == Decimal("8.13")
    # A smaller overdue portion falls back to the $5 floor (BR-BIL-001's max).
    assert assess(date(2026, 7, 21), overdue=Decimal("45.00")) == Decimal("5.00")
    # And nothing past due is no fee at all — the floor is a minimum on a fee
    # that applies, not a charge for being a customer.
    assert assess(date(2026, 7, 21), overdue=Decimal("0")) == Decimal("0.00")


def test_the_amount_comes_from_ratings_percent_with_minimum_rule():
    """One implementation of max($5, 1.5% × overdue), not two.

    Billing owns the clock; rating owns the arithmetic (BR-RAT-045). If these
    ever diverge, GT-8 and this assertion disagree at the same moment.
    """
    from apps.billing import rating_seam
    from core import money

    assert money.finalize(
        rating_seam.charge_amount(
            rule=late_fee.LATE_FEE_RULE, percent=PERCENT, basis=OVERDUE, minimum=MINIMUM
        )
    ) == assess(date(2026, 7, 21))


def test_no_automatic_waiver_exists():
    """BR-BIL-003 — the first-time waiver is a manual staff decision.

    Asserted as an absence: there is no waiver argument and no waiver branch, so
    nothing can waive a fee without a person doing it in the UI.
    """
    import inspect

    signature = inspect.signature(services.assess_late_fee)
    assert not [name for name in signature.parameters if "waiv" in name.lower()]
    source = inspect.getsource(late_fee.assess_late_fee)
    assert "waiv" not in source.lower().replace("waiver is manual", "")


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-002@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — recomputed 2026-08-10)
# generated: 2026-08-10 by story-coder (rating-engine lane — GT-8 companion seam)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure calculation) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_gt08_late_fee_grace.py 10 passed✔ · pytest tests -m golden → 12 passed / 1 xfailed✔ · run_gates 15 PASS/0 FAIL/1 SKIP✔
# revised: 2026-08-11 (holiday lane) — the two items this trailer used to carry as REPORTED are both RULED and this file now asserts the ratified figures. (1) The business-day boundary is the PO's ruling of 2026-08-11, not a consistency check: due Thu 10 Sep + 5 grace → business-day Fri 18 Sep. (2) Holidays ARE now excluded from business days: due Thu 24 Dec 2026 + 5 business days' grace → Tue 5 Jan 2027, not Fri 1 Jan. RED PROOF EXECUTED for (2): with `and cursor not in holidays` deleted from `_business_days_between`, this file measured `1 failed, 9 passed in 0.12s` — FAILED test_business_day_grace_skips_public_holidays, `AssertionError: assert Decimal('8.13') == Decimal('0.00')` at as_of=2027-01-01. Reverted → `10 passed in 0.07s`.
# exceptions: this file builds its holiday sets BY HAND, so it pins the CLOCK and not the read that feeds it — the tenant's stored rows reaching this clock intact is tests/test_bil_holiday_seam.py's job, because a parsing bug in that read would leave every assertion here green. The two files are the two halves and neither is sufficient alone.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
