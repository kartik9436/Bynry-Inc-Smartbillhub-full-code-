# ── Trace ──────────────────────────────────────────────
# Change:   CR-085 blueprint specifications CPB-06 and CPB-07, the portal
#           blueprint's own words:
#             CPB-06 *"Usage compares against the same month last year"* —
#               done is *"The Usage screen reads '800 kWh · 86 kWh more than
#               August 2025' beside the chart, rather than the sentence saying
#               there is nothing to compare with."*
#             CPB-07 *"Usage compares against last month"* — done is *"The
#               Usage screen reads '5% less than July' under the big number,
#               and a clerk looking at the same account sees the same 5%."*
# Rules:    BR-MET-106 (an unread month is ABSENT, never 0) · CLAUDE.md hard
#           rule 2 (percentages carried at 6 dp, DISPLAYED at 2) · hard rule 3
#           (a consumption always carries its unit) · B14 rule 35 (the
#           catalogue writes the words; the server ships a CODE)
# Why here: CPB-07's acceptance sentence is *"and a clerk looking at the same
#           account sees the same 5%"*, so the arithmetic belongs in the module
#           BOTH surfaces already read — `metering.monthly_usage`, whose
#           metrics `monthly_usage_reads.usage_payload` serves to the staff
#           Usage tab (S21) and, through `portal.seams.metering_seam`, to the
#           portal. A browser-side subtraction would be a second answer nobody
#           else could reproduce, which is the blueprint's own stated reason
#           the spec was open.
# ───────────────────────────────────────────────────────
"""The two comparisons a person actually arrives with, and their absences."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from apps.metering import monthly_usage as rules


def point(month: str, quantity: str | None, unit: str | None = "kWh") -> rules.MonthPoint:
    year, mon = month.split("-")
    return rules.MonthPoint(
        period_month=date(int(year), int(mon), 1),
        quantity=None if quantity is None else Decimal(quantity),
        unit=None if quantity is None else unit,
    )


# ── CPB-07 · against last month ──────────────────────────────────────────────


def test_cpb07_tc1__the_latest_month_against_the_one_before_it():
    """The blueprint's own figure: *"5% less than July"*.

    August `760` against July `800` is `-40 kWh`, which is `-5%` exactly.
    """
    change = rules.month_on_month([point("2026-07", "800"), point("2026-08", "760")])
    assert change.absent_reason is None
    assert change.this_month == date(2026, 8, 1)
    assert change.against_month == date(2026, 7, 1)
    assert change.difference == Decimal("-40")
    assert change.unit == "kWh"
    assert change.percent == Decimal("-5.000000")
    assert change.direction == "less"


def test_cpb07_tc2__an_unchanged_month_says_the_same_and_never_a_signed_zero():
    """Ana's own account: 800 kWh in July and 800 in August.

    `BR-MET-106` treats *no change* as a fact rather than an absence, so this
    answers — and the direction is a THIRD value, because *0% more* is not
    something a person says.
    """
    change = rules.month_on_month([point("2026-07", "800"), point("2026-08", "800")])
    assert change.absent_reason is None
    assert change.difference == Decimal("0")
    assert change.percent == Decimal("0")
    assert change.direction == "same"


def test_cpb07_tc3__an_absent_month_between_is_skipped_and_the_answer_names_what_it_used():
    """`BR-MET-106`: an unread month is ABSENT, never `0`.

    So the comparison walks back to the nearest month that HAS a figure and
    reports WHICH — June, not July — rather than subtracting from a zero that
    would tell a customer they used nothing.
    """
    change = rules.month_on_month(
        [point("2026-06", "1000"), point("2026-07", None), point("2026-08", "800")]
    )
    assert change.absent_reason is None
    assert change.against_month == date(2026, 6, 1)
    assert change.difference == Decimal("-200")
    assert change.percent == Decimal("-20.000000")


def test_cpb07_tc4__one_month_of_history_has_nothing_to_compare_with():
    change = rules.month_on_month([point("2026-08", "800")])
    assert change.absent_reason == "no_earlier_month"
    assert change.percent is None
    assert change.difference is None


def test_cpb07_tc5__an_earlier_month_of_exactly_zero_is_unanswerable_as_a_percentage():
    """A percentage change from nothing is not infinity, it is unanswerable —
    the same judgment `yoy_change` already records for `prior_year_zero`. The
    DIFFERENCE still answers, because `+800 kWh` is a true sentence."""
    change = rules.month_on_month([point("2026-07", "0"), point("2026-08", "800")])
    assert change.absent_reason == "earlier_month_zero"
    assert change.percent is None
    assert change.difference == Decimal("800")
    assert change.direction == "more"


def test_cpb07_tc6__two_months_that_disagree_about_the_unit_have_no_comparison():
    """CLAUDE.md hard rule 3 — kWh and kgal share a month and nothing else."""
    change = rules.month_on_month([point("2026-07", "800", "kgal"), point("2026-08", "760", "kWh")])
    assert change.absent_reason == "mixed_units"
    assert change.difference is None
    assert change.percent is None


def test_cpb07_tc7__nothing_read_at_all_answers_a_reason_rather_than_a_zero():
    change = rules.month_on_month([point("2026-07", None), point("2026-08", None)])
    assert change.absent_reason == "no_current_reads"


# ── CPB-06 · against the same month last year ────────────────────────────────


def test_cpb06_tc1__the_blueprints_own_figure_86_kwh_more_than_august_2025():
    """*"800 kWh · 86 kWh more than August 2025"* — so August 2025 read `714`."""
    points = [point("2025-08", "714")] + [point(f"2026-0{m}", None) for m in (1, 2, 3)]
    points.append(point("2026-08", "800"))
    change = rules.same_month_last_year(points)
    assert change.absent_reason is None
    assert change.this_month == date(2026, 8, 1)
    assert change.against_month == date(2025, 8, 1)
    assert change.difference == Decimal("86")
    assert change.unit == "kWh"
    assert change.direction == "more"


def test_cpb06_tc2__it_is_the_SAME_CALENDAR_MONTH_and_never_the_nearest_one():
    """The whole point of this comparison is that it is seasonal: August against
    August. A July 2025 figure is NOT an answer to *how does this August
    compare*, so an absent August 2025 is reported rather than substituted."""
    change = rules.same_month_last_year([point("2025-07", "714"), point("2026-08", "800")])
    assert change.absent_reason == "no_same_month_last_year"
    assert change.difference is None


def test_cpb06_tc3__ana_has_three_months_and_no_prior_year_at_all():
    """The live demo account. The screen must say so rather than compare with
    nothing — this is the branch that ships today."""
    change = rules.same_month_last_year(
        [point("2026-06", "800"), point("2026-07", "800"), point("2026-08", "800")]
    )
    assert change.absent_reason == "no_same_month_last_year"


def test_cpb06_tc4__a_percentage_travels_too_and_is_carried_at_six_places():
    change = rules.same_month_last_year([point("2025-08", "714"), point("2026-08", "800")])
    assert change.percent == Decimal("12.044818")


def test_cpb06_tc5__mixed_units_between_the_two_augusts_refuse():
    change = rules.same_month_last_year(
        [point("2025-08", "714", "kgal"), point("2026-08", "800", "kWh")]
    )
    assert change.absent_reason == "mixed_units"


# ── the read model both surfaces share ───────────────────────────────────────
#
# ⚠ **THIS IS THE HALF THAT MAKES CPB-07's SECOND SENTENCE TRUE** — *"and a
# clerk looking at the same account sees the same 5%"*. The arithmetic above
# could be right and reach only the portal; `usage_payload`'s `metrics` block
# is the ONE object the staff Usage tab (S21) and `CWP-033` both read, so a
# figure that appears here appears identically on both.


def test_cpb0607_tc8__both_comparisons_reach_the_metrics_block_the_two_screens_share():
    from apps.metering import monthly_usage_reads as reads

    metrics = reads._metrics(
        [point("2025-08", "714")]
        + [point(f"2025-{m:02d}", None) for m in (9, 10, 11, 12)]
        + [point(f"2026-{m:02d}", None) for m in (1, 2, 3, 4, 5, 6)]
        + [point("2026-07", "800"), point("2026-08", "760")]
    )

    assert metrics["vs_last_month"]["difference_display"] == "-40"
    assert metrics["vs_last_month"]["unit"] == "kWh"
    # CLAUDE.md hard rule 2: carried at six places, DISPLAYED at two.
    assert metrics["vs_last_month"]["value"] == "-5.000000"
    assert metrics["vs_last_month"]["display"] == "-5.00"
    assert metrics["vs_last_month"]["direction"] == "less"
    assert metrics["vs_last_month"]["against_month"] == "2026-07"
    assert metrics["vs_last_month"]["absent_reason"] is None

    assert metrics["same_month_last_year"]["difference_display"] == "46"
    assert metrics["same_month_last_year"]["unit"] == "kWh"
    assert metrics["same_month_last_year"]["against_month"] == "2025-08"
    assert metrics["same_month_last_year"]["direction"] == "more"
    assert metrics["same_month_last_year"]["absent_reason"] is None


def test_cpb0607_tc9__mixed_units_across_the_window_refuse_both_comparisons_too():
    """The existing `mixed_units_across_months` short circuit returns four
    metrics and would leave these two simply MISSING from the object — which a
    screen reading `metrics.vs_last_month.absent_reason` would crash on. Every
    branch of `_metrics` returns the same shape."""
    from apps.metering import monthly_usage_reads as reads

    metrics = reads._metrics([point("2026-07", "800", "kgal"), point("2026-08", "760", "kWh")])
    assert metrics["vs_last_month"]["absent_reason"] == "mixed_units_across_months"
    assert metrics["same_month_last_year"]["absent_reason"] == "mixed_units_across_months"


def test_cpb0607_tc10__an_account_with_nothing_read_carries_both_keys_with_a_reason():
    from apps.metering import monthly_usage_reads as reads

    metrics = reads._metrics([point("2026-07", None), point("2026-08", None)])
    assert metrics["vs_last_month"]["absent_reason"] == "no_current_reads"
    assert metrics["same_month_last_year"]["absent_reason"] == "no_current_reads"
    assert metrics["vs_last_month"]["display"] is None
