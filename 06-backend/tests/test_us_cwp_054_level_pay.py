# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-054 (EP-CWP-10) — level pay: pay the same amount every
#           month. Screen: CWP-044
# Rules:    BR-CWP-054 (the level, the variance and the settle-up month are
#           SHOWN) · BR-BIL-017 (level = trailing average, whole $; eligibility
#           = 12 months of history) · BR-BIL-021 (every budget parameter is
#           TENANT config, seeded, nothing hardcoded) · BR-CWP-001 (enrolment
#           is not one of the six portal writes) · CLAUDE.md hard rule 2
# Golden:   ❄️ GT-24 is the frozen chain this arithmetic belongs to; nothing
#           here recomputes it — `budget.compute_level` is called
# Tests:    this file
# Impacts:  apps/portal/seams/billing_seam.py `level_pay_position` ·
#           apps/portal/selectors.py `level_pay`
# ───────────────────────────────────────────────────────
"""`US-CWP-054`'s cases — and the invariant that keeps two figures honest.

⚠ **THE SCREEN SHOWS THE AVERAGE AND THE LEVEL IN ONE SENTENCE**, and
`$125.0908…` rounding to `$125.00` is what makes that sentence true. The
average is the ONE piece of arithmetic on this path that is not
`apps.billing.budget`'s — that module publishes the rounded level and not the
raw average the story asks to show — so `test_..._the_average_ROUNDS_TO_the_level`
below is what stops the two from ever drifting apart quietly.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pytest

from apps.billing import budget
from apps.portal.seams import billing_seam
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    an_issued_bill,
    elm_street_account,
    switch_on,
)

#: `US-CWP-054` §4's own figures. Twelve bills totalling `$1,501.09`, so the
#: average is `$125.0908…` and the level is `$125.00`.
TWELVE = (
    "98.4000",
    "104.2000",
    "112.7000",
    "121.3000",
    "148.9000",
    "171.4000",
    "182.2000",
    "163.5000",
    "131.0000",
    "112.4000",
    "101.8000",
    "53.2900",
)
TRAILING_TOTAL = Decimal("1501.0900")


def _bill_the_year(tenant, account, amounts=TWELVE):
    """One issued bill a month, each in its own calendar month.

    ⚠ **ONE PER MONTH MATTERS.** `budget_history_for` counts DISTINCT billed
    PERIODS, not bills, so two bills in one month are one month of history —
    which is what stops an account enrolling on six months of data that
    `BR-BIL-017` says is not enough.
    """
    for index, amount in enumerate(amounts):
        month = index + 1
        issued = date(2025, month, 28) if month <= 12 else date(2026, month - 12, 28)
        an_issued_bill(
            tenant,
            account,
            number=f"BL-25{month:02d}-{index:04d}",
            total=amount,
            issued_on=issued,
        )


def read(tenant, account):
    with tenant_context(tenant.id):
        return billing_seam.level_pay_position(account.pk)


@pytest.mark.django_db
def test_us_cwp_054_tc1_twelve_months_of_1501_09_give_an_average_of_125_09_and_a_level_of_125(
    pine_hill, sarah
):
    """The story's headline figures, end to end."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        _bill_the_year(pine_hill, account)
    position = read(pine_hill, account)
    assert Decimal(position["trailing_total"]) == TRAILING_TOTAL
    assert position["monthly_average"] == "125.0908"
    assert position["level"] == "125"
    assert position["level_unavailable"] is None
    assert position["currency"] == "USD"


@pytest.mark.django_db
def test_us_cwp_054_the_average_ROUNDS_TO_the_level(pine_hill, sarah):
    """⚠ **THE INVARIANT BETWEEN THE TWO FIGURES ON ONE LINE.**

    `CWP-044` prints *"$125.09 rounded to $125.00"*. If the average were
    computed over a different divisor from the level — `len(actuals)` instead
    of the tenant's window, which is the trap `compute_level`'s own docstring
    names — the sentence would be arithmetically false on the screen and
    nothing else in this repo would notice. This asserts it cannot be.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        _bill_the_year(pine_hill, account)
    position = read(pine_hill, account)
    rounded = Decimal(position["monthly_average"]).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    assert str(rounded) == position["level"], "the screen would print two disagreeing figures"


@pytest.mark.django_db
def test_us_cwp_054_tc2_the_ROUNDING_is_the_tenants_and_not_a_rule_in_the_portal(pine_hill, sarah):
    """`BR-BIL-021` — the rounding mode is CONFIG, and this read carries which
    one was used rather than implying whole dollars is a law of the portal."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        _bill_the_year(pine_hill, account)
    position = read(pine_hill, account)
    assert position["rounding"] == budget.ROUNDING_WHOLE_DOLLAR
    # And the portal did not invent the figure: it is `compute_level`'s.
    with tenant_context(pine_hill.id):
        direct = budget.compute_level(
            trailing_actuals=tuple(Decimal(value) for value in reversed(TWELVE)),
            months=12,
            rounding=budget.ROUNDING_WHOLE_DOLLAR,
        )
    assert str(direct) == position["level"]


@pytest.mark.django_db
def test_us_cwp_054_tc3_too_little_history_gives_NO_LEVEL_and_a_reason_never_zero(pine_hill, sarah):
    """⚠ **`None`, NEVER `0.00`.** A zero monthly amount is a real, chooseable
    figure and would read as *this customer pays nothing* — the posture
    `budget_api` already takes one screen along."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        _bill_the_year(pine_hill, account, amounts=TWELVE[:4])
    position = read(pine_hill, account)
    assert position["level"] is None
    assert position["level"] != "0"
    assert position["months_of_history"] == 4
    assert position["required_months"] == 12
    assert "4/12 months" in position["level_unavailable"]


@pytest.mark.django_db
def test_cr085_cpb18_a_HOLE_in_the_history_names_the_MONTH_not_just_a_count(
    pine_hill, sarah
):
    """`CPB-18` — *"or says precisely which month is missing"*.

    ⚠ **THE COUNT WAS TRUE AND USELESS.** *11 of 12* does not say whether a
    bill went astray or whether the customer has simply not been here a year,
    and those two want opposite actions from them. This account has been billed
    for a whole year except **March 2025**, which is a genuine gap.

    ⚠ **NO LEVEL IS OFFERED ANYWAY, AND THAT IS A SIGNED RULE.**
    `eligibility_months` is the TENANT's (`BR-BIL-017`/`BR-BIL-021`); averaging
    eleven months and calling it a year would put a figure in front of a
    customer that no staff screen can reproduce. What this adds is the reason
    said precisely, never a level computed from a short history.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        # Every month of 2025 except March.
        for index, amount in enumerate(TWELVE):
            month = index + 1
            if month == 3:
                continue
            an_issued_bill(
                pine_hill,
                account,
                number=f"BL-25{month:02d}-{index:04d}",
                total=amount,
                issued_on=date(2025, month, 28),
            )
    position = read(pine_hill, account)
    assert position["level"] is None
    assert position["months_of_history"] == 11
    assert position["missing_months"] == [[2025, 3]]
    #: INSIDE the run of bills, so it is a gap and not a young account.
    assert position["missing_month_gaps"] == [[2025, 3]]
    assert position["missing_months_before_first_bill"] == []
    assert position["first_billed_month"] == [2025, 1]


@pytest.mark.django_db
def test_cr085_cpb18_a_YOUNG_account_has_no_gap_only_months_before_it_existed(
    pine_hill, sarah
):
    """⚠ **THE OTHER SHAPE, AND IT IS A DIFFERENT ANSWER.**

    Four bills, January to April, and nothing before them. Every missing month
    falls BEFORE the account's first bill, so nothing went astray — and the
    screen must not say *we are missing your bill*, which would send somebody
    to the telephone over a bill that was never due.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        _bill_the_year(pine_hill, account, amounts=TWELVE[:4])
    position = read(pine_hill, account)
    assert position["months_of_history"] == 4
    assert position["missing_month_gaps"] == []
    assert len(position["missing_months_before_first_bill"]) == 8
    assert position["first_billed_month"] == [2025, 1]
    #: The window ends at the NEWEST bill, so it runs May 2024 → April 2025 and
    #: never touches a clock. Newest first.
    assert position["missing_months"][0] == [2024, 12]
    assert position["missing_months"][-1] == [2024, 5]


@pytest.mark.django_db
def test_cr085_cpb18_an_account_never_billed_has_NO_history_rather_than_a_hole_in_one(
    pine_hill, sarah
):
    """⚠ **TWELVE ABSENCES FOR SOMEBODY WHO JOINED LAST WEEK IS TRUE AND
    USELESS**, and it would displace the sentence this case already has
    (*"We have not billed you yet, so there is nothing to average"*). An empty
    list is the honest answer and the screen keeps its own words."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    position = read(pine_hill, account)
    assert position["months_of_history"] == 0
    assert position["missing_months"] == []
    assert position["missing_month_gaps"] == []
    assert position["missing_months_before_first_bill"] == []
    assert position["first_billed_month"] is None


@pytest.mark.django_db
def test_us_cwp_054_tc6_the_settle_up_month_is_the_TENANTS_and_is_UNSET_by_default(
    pine_hill, sarah
):
    """⚠ **NEVER JUNE BY DEFAULT.** `settings_families` ratifies no month —
    *"rule names the parameter, ratifies no month"* — so an unset month reads
    as unset. A screen that hardcoded June would be right for one utility and
    silently wrong for every other, which is the failure no gate here can see.
    """
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        _bill_the_year(pine_hill, account)
    position = read(pine_hill, account)
    assert position["settle_up_month"] is None, "the seeded default names no month"
    assert position["relevel_cadence_months"] == 6


@pytest.mark.django_db
def test_us_cwp_054_tc4_an_account_with_no_bills_is_not_offered_a_level(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    position = read(pine_hill, account)
    assert position["level"] is None
    assert position["months_of_history"] == 0
    assert position["billed"] == []
    assert position["enrolled"] is False


@pytest.mark.django_db
def test_us_cwp_054_tc5_the_chart_series_is_what_was_BILLED_oldest_first(pine_hill, sarah):
    """The bars are billed totals and the line is the level (`TC-5`). The read
    reverses the newest-first order the published read answers with, so a chart
    reads left to right without a screen doing it."""
    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        _bill_the_year(pine_hill, account)
    position = read(pine_hill, account)
    assert len(position["billed"]) == 12
    assert Decimal(position["billed"][0]) == Decimal("98.4000"), "January first"
    assert Decimal(position["billed"][-1]) == Decimal("53.2900"), "December last"


@pytest.mark.django_db
def test_us_cwp_054_the_portal_body_carries_no_database_id_and_holds_the_join_control(
    pine_hill, sarah
):
    """`BR-CWP-001` — enrolment writes `account_budget_status`, which is not one
    of the six kinds of row the portal may write, so the control is HELD."""
    from apps.portal import selectors as portal_selectors

    switch_on(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        _bill_the_year(pine_hill, account)


    with tenant_context(pine_hill.id):
        body = portal_selectors.level_pay(account)
    assert body["level_pay"]["join_held"] is True
    assert body["level_pay"]["level"] == "125"
    assert str(account.pk) not in repr(body)
    assert str(account.pk)[:8] not in repr(body)


@pytest.mark.django_db
def test_us_cwp_054_tc7_TENANT_ISOLATION_an_oak_ridge_session_reads_no_pine_hill_bill(
    pine_hill, sarah, oak_ridge, elena
):
    """The twelve bills are Pine Hill's. Read under an Oak Ridge session — the
    same shape `US-NOT-013` TC-5 calls a forged id — the history is empty and
    no level is offered, rather than Pine Hill's `$125.00` appearing."""
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    account = elm_street_account(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        _bill_the_year(pine_hill, account)
    with tenant_context(oak_ridge.id):
        intruder = billing_seam.level_pay_position(account.pk)
    assert intruder["months_of_history"] == 0
    assert intruder["level"] is None
    assert read(pine_hill, account)["level"] == "125", "the read itself still works"
