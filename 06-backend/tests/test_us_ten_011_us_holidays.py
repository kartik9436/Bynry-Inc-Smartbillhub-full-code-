# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-011 (S63 holiday calendar)   Screens: S63
# Rules:    BR-TEN-039 (tenant holiday calendar) · BR-BIL-002 (business-day
#           grace excludes the tenant's public holidays — PO 2026-08-11) ·
#           BR-TEN-043 (the year is an argument, never a clock)
# ───────────────────────────────────────────────────────
"""The US federal holiday seed, and the calendar that no longer runs out.

PO ruling 2026-08-11: *"for time being consider USA and Load US holiday for
given year as a seed data"*. This proves the dates are right, that the seed is
idempotent and never overwrites a tenant's own label, and — the part worth
reading — that **the PO's own Christmas figure comes out of a provisioned
tenant's calendar**, which needs TWO years in it.

This header used to end *"…which provisioning does not seed"*, and tc6 asserted
that gap as a defect. **DEF-042 closed it on 2026-08-15**: provisioning seeds the
sign-up year and the next, `services.ensure_us_holidays_through` extends a
calendar forward without ever re-seeding one a tenant emptied on purpose, and
G24 fails the build if either half regresses. The sentence is corrected rather
than left standing, because a docstring describing a gap that has been closed is
the same defect as one describing a guarantee that was never built.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import late_fee
from apps.tenancy import models as tenancy_models
from apps.tenancy import services as tenancy_services
from apps.tenancy.us_holidays import us_federal_holidays

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: 2026, checked against the federal calendar. Independence Day is the one that
#: matters: 4 July 2026 is a SATURDAY, so it is observed on Friday 3 July.
EXPECTED_2026 = [
    (date(2026, 1, 1), "New Year's Day"),
    (date(2026, 1, 19), "Birthday of Martin Luther King, Jr."),
    (date(2026, 2, 16), "Washington's Birthday"),
    (date(2026, 5, 25), "Memorial Day"),
    (date(2026, 6, 19), "Juneteenth National Independence Day"),
    (date(2026, 7, 3), "Independence Day"),
    (date(2026, 9, 7), "Labor Day"),
    (date(2026, 10, 12), "Columbus Day"),
    (date(2026, 11, 11), "Veterans Day"),
    (date(2026, 11, 26), "Thanksgiving Day"),
    (date(2026, 12, 25), "Christmas Day"),
]


def test_us_ten_011_tc1__the_eleven_federal_holidays_for_2026():
    """Every date, by name. A wrong holiday moves money on a late fee."""
    assert us_federal_holidays(2026) == EXPECTED_2026


def test_us_ten_011_tc2__a_saturday_holiday_is_observed_on_the_friday_before():
    """THE RULE THE PO WAS NOT SHOWN, asserted so it is visible rather than assumed.

    Offices close on the OBSERVED day, and that is what a calendar deciding
    "which days is nobody working" has to hold. 4 July 2026 is a Saturday, so
    3 July is seeded — and **4 July is NOT**, because seeding both would remove
    two business days from a grace window for one holiday, which no rule
    supports.
    """
    days = dict(us_federal_holidays(2026))
    assert date(2026, 7, 3) in days
    assert date(2026, 7, 4) not in days

    # A Sunday holiday goes the other way. 4 July 2027 is a Sunday → Monday 5th.
    days_2027 = dict(us_federal_holidays(2027))
    assert date(2027, 7, 5) in days_2027
    assert date(2027, 7, 4) not in days_2027


def test_us_ten_011_tc3__a_new_years_day_on_a_saturday_lands_in_the_previous_year():
    """An edge the observed rule creates, asserted rather than discovered later.

    1 January 2022 was a Saturday, so it was observed on Friday 31 December
    2021 — a date OUTSIDE the year asked for. That is federally correct and it
    means a year's list can carry a date from December before it. Seeding is
    keyed on the date itself, so nothing collides; but a reader counting "11
    dates all inside the year" would be wrong, and now finds this test instead.
    """
    days = dict(us_federal_holidays(2022))
    assert date(2021, 12, 31) in days
    assert date(2022, 1, 1) not in days


def test_us_ten_011_tc4__a_floating_holiday_is_never_shifted():
    """Memorial Day is defined as the last Monday in May and cannot fall on a
    weekend. Applying the observed rule to it would move a date the statute
    already placed."""
    for year in (2025, 2026, 2027, 2028):
        days = dict(us_federal_holidays(year))
        for day, label in days.items():
            if label in ("Memorial Day", "Labor Day", "Thanksgiving Day"):
                assert day.weekday() < 5, f"{label} {year} landed on a weekend"


def test_us_ten_011_tc5__provisioning_seeds_them_and_a_re_run_never_duplicates(brazos):
    """Idempotent, and it never overwrites a label the tenant has renamed.

    A tenant that renames "Columbus Day" to "Indigenous Peoples' Day" — a real
    and common choice — must not have it silently reverted by a re-provision.
    """
    with tenant_ctx(brazos):
        rows = tenancy_models.HolidayCalendar.objects.filter(tenant=brazos)
        # TWO years, not one (DEF-042). This assertion used to read
        # `== len(EXPECTED_2026)`; provisioning now seeds the sign-up year AND
        # the next, because a one-year calendar expires silently on 1 January.
        assert rows.filter(holiday_date__year=2026).count() == len(EXPECTED_2026)
        assert rows.filter(holiday_date__year=2027).count() == len(us_federal_holidays(2027))

        renamed = rows.get(holiday_date=date(2026, 10, 12))
        renamed.label = "Indigenous Peoples' Day"
        renamed.save(update_fields=["label"])

        created = tenancy_services._seed_us_holidays(brazos, 2026)

        assert created == 0  # nothing new
        assert rows.count() == len(EXPECTED_2026) + len(us_federal_holidays(2027))
        assert rows.get(holiday_date=date(2026, 10, 12)).label == "Indigenous Peoples' Day"


def test_us_ten_011_tc6__the_pos_christmas_case_comes_out_of_a_provisioned_tenant(brazos):
    """THE TEST THAT MATTERS — and it now proves the fix instead of the gap.

    The PO's figure: a bill due **Thu 24 Dec 2026** with 5 business days' grace
    must charge the fee on **Tue 5 Jan 2027**, not Fri 1 Jan.

    Walk it. After the due date: Fri 25 Dec is Christmas — skip. Weekend — skip.
    Mon 28, Tue 29, Wed 30, Thu 31 are days 1-4. **Fri 1 Jan 2027 is New Year's
    Day** — skip. Weekend — skip. Mon 4 Jan is day 5, grace ends, and the fee
    applies strictly after: **Tue 5 Jan**. The PO's number.

    **THIS CASE USED TO ASSERT THE DEFECT.** Provisioning seeded ONE year — the
    year the tenant signed up — so a tenant provisioned in 2026 had no 2027
    dates, and the calculation quietly stopped skipping holidays it had never
    been told about. The old body asserted `date(2027, 1, 1) not in seeded` and
    then showed the fee landing **Mon 4 Jan**: a day early, *on a public
    holiday*, for every customer of that tenant. It was written that way on
    purpose, because a test proving only the good case would have left the gap
    invisible and passing.

    **DEF-042 closed it**, and the case is REWRITTEN rather than deleted so the
    reversal stays readable: provisioning now seeds the sign-up year AND the
    next, and the figure is taken from what a provisioned tenant ACTUALLY holds
    rather than from a set the test assembles for itself. That distinction is
    the whole point — the old test could conjure 2027 by hand and prove the
    arithmetic while the product still shipped the wrong answer.
    """
    with tenant_ctx(brazos):
        seeded = frozenset(
            tenancy_models.HolidayCalendar.objects.filter(tenant=brazos).values_list(
                "holiday_date", flat=True
            )
        )
        # What provisioning ACTUALLY leaves, now: next year's dates are there.
        assert date(2027, 1, 1) in seeded, (
            "provisioning must seed the following year too — without 1 Jan 2027 "
            "the PO's Christmas case answers Mon 4 Jan, a day early and on a "
            "public holiday (DEF-042)"
        )

        def fee_on(as_of: date) -> Decimal:
            return late_fee.assess_late_fee(
                overdue_amount=Decimal("542.10"),
                percent=Decimal("0.015"),
                minimum=Decimal("5.00"),
                due_date=date(2026, 12, 24),
                as_of=as_of,
                grace_days=5,
                grace_mode="business",
                holidays=seeded,
            )

        # The PO's own figure, straight off a provisioned tenant's calendar.
        assert fee_on(date(2027, 1, 4)) == Decimal("0.00")  # Mon 4 Jan: still in grace
        assert fee_on(date(2027, 1, 5)) == Decimal("8.13")  # Tue 5 Jan: the PO's number


def test_us_ten_011_tc7__topping_up_extends_a_calendar_but_never_re_seeds_an_empty_one(brazos):
    """`ensure_us_holidays_through` fills forward — and leaves an empty calendar alone.

    Two behaviours, and the second is the one that would do damage if it were
    wrong. BR-TEN-039 makes the calendar the TENANT's: a utility outside the US
    deletes every seeded date, legitimately. An empty calendar and a brand-new
    calendar look identical in the data, so a top-up that treats "empty" as
    "needs seeding" would silently re-impose US federal holidays on a tenant
    that removed them — every time anything called it.
    """
    with tenant_ctx(brazos):
        rows = tenancy_models.HolidayCalendar.objects.filter(tenant=brazos)

        # (1) EXTENDS: 2028 is not covered yet, so topping up creates it.
        #
        # Counted against the SEEDER'S OWN LIST rather than against calendar
        # year 2028, because the observed-date rule can push a year's holiday
        # into the previous calendar year: 1 Jan 2028 falls on a Saturday and
        # is observed on Fri 31 Dec 2027. A test that filtered on
        # `holiday_date__year=2028` would be off by one and would look like a
        # seeding bug rather than the statute it actually is.
        before = rows.count()
        created = tenancy_services.ensure_us_holidays_through(brazos, 2028)
        assert created == len(us_federal_holidays(2028))
        assert rows.count() == before + len(us_federal_holidays(2028))
        assert rows.filter(holiday_date=date(2027, 12, 31)).exists(), (
            "New Year's Day 2028 is observed on Fri 31 Dec 2027 — the observed "
            "rule means a year's holidays are not all inside that calendar year"
        )

        # Idempotent: a second call over the same horizon creates nothing.
        assert tenancy_services.ensure_us_holidays_through(brazos, 2028) == 0

        # (2) NEVER RE-SEEDS: the tenant empties their calendar on purpose.
        rows.delete()
        assert tenancy_services.ensure_us_holidays_through(brazos, 2028) == 0
        assert rows.count() == 0, (
            "an empty calendar is the tenant's own choice (BR-TEN-039) and must "
            "never be re-seeded with US federal holidays they deleted"
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-011@808e015 (04-docs/05-modules/01-tenancy/02-business-rules.md ·
#         04-docs/05-modules/07-billing/02-business-rules.md)
# generated: 2026-08-11 by Eng-Lead (PO ruling: seed US holidays for the year)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S63 CRUD already shipped) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔
# exceptions: DEF-042 CLOSED 2026-08-15 — tc6 no longer asserts the defect.
#         It used to prove BOTH outcomes, because with only the provisioned year
#         seeded the PO's own Christmas case gave Mon 4 Jan instead of their
#         Tue 5 Jan, and a test proving only the good case would have left that
#         invisible and passing. Provisioning now seeds the sign-up year AND the
#         next, so tc6 reads the figure off what a provisioned tenant actually
#         holds; tc7 covers the top-up, including that an EMPTY calendar is the
#         tenant's own choice (BR-TEN-039) and is never re-seeded. G24
#         holiday-horizon fails the build if either half regresses
#         · the OBSERVED-date rule (Saturday → Friday) was never put to the PO
#         and is flagged in the human-review ledger, not treated as settled.
#         It bit while writing tc7: 1 Jan 2028 is a Saturday, so that year's
#         holiday is seeded on Fri 31 Dec 2027 and a count filtered on calendar
#         year 2028 is off by one. tc3 had already written this down — the
#         first assertion was made anyway, which is the argument for tc3
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
