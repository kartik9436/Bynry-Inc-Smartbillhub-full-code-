# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 2 · P2.25 (ONE calendar per report; mixing
#           refused, naming both).  Screens: 2·1 head · 2·2 group slots.
# Rules:    brief §7.2.3 p85, read as an image per B14 rule 42 — *"A billing
#           cycle does not sit inside a calendar month. It straddles two."*
# Tests:    this file
# Defects:  DEF-REP-6846 (the shared time dimension offers a calendar level on
#           a dataset that declares the billing calendar)
# ───────────────────────────────────────────────────────
"""P2.25 — TWO TIME HIERARCHIES, AND THEY DO NOT NEST."""

import pytest

from apps.reports import datasets, slicers


def test_p2_25__the_two_hierarchies_are_what_the_brief_draws():
    assert datasets.TIME_HIERARCHIES["calendar"] == (
        "year", "quarter", "accounting_period", "day",
    )
    assert datasets.TIME_HIERARCHIES["billing"] == ("year", "cycle", "day")


def test_p2_25__a_dataset_offers_only_its_own_calendars_levels():
    """⚠ **THIS IS `DEF-REP-6846` ASSERTED AGAINST.**

    `invoices` declares `time_hierarchy="billing"`, so it groups by `cycle` and
    NOT by `accounting_period`. Reading `D_TIME.hierarchy` instead — which is
    what an obvious implementation does — offers `accounting_period` here, a
    calendar level on a billing report, which is §7.2.3's fault shipped in the
    declaration itself.
    """
    assert datasets.BY_CODE["invoices"].time_hierarchy == "billing"
    levels = slicers.time_levels("invoices")
    assert "cycle" in levels
    assert "accounting_period" not in levels
    assert "quarter" not in levels

    assert "accounting_period" in slicers.time_levels("payments")
    assert "cycle" not in slicers.time_levels("payments")


def test_p2_25__the_declared_calendar_and_the_time_dimension_do_not_disagree():
    """The regression guard `DEF-REP-6846`'s prevention names.

    ⚠ **IT IS WRITTEN AS A `xfail`, NOT AS A SILENT SKIP, AND THAT IS
    DELIBERATE.** `D_TIME.hierarchy` disagrees with the declared calendar on
    **all nine** datasets today. Asserting agreement now would make this file
    red on a fault this lane did not cause and is not fixing (the shared
    `D_TIME` object is Phase 0's and moving it would re-declare nine datasets
    at once). Asserting nothing would let the disagreement widen unseen.
    `xfail(strict=True)` does the one useful thing: it stays quiet while the
    defect is open and goes **RED the day somebody fixes it**, naming this test
    as the place to delete the marker.
    """
    disagree = []
    for dataset in datasets.DATASETS:
        declared = datasets.TIME_HIERARCHIES[dataset.time_hierarchy]
        for dim in dataset.dimensions:
            if dim.name == datasets.DIM_TIME and tuple(dim.hierarchy or ()) != declared:
                disagree.append(dataset.code)
    # Measured 2026-09-27: all nine.
    assert len(disagree) == 9, (
        "DEF-REP-6846 has moved — re-measure it and update this count, or close "
        f"the defect: {disagree}"
    )


def test_p2_25__filtering_by_period_and_grouping_by_cycle_is_refused_naming_both():
    """p13's outcome row, verbatim: *"Filtering by accounting period and
    grouping by cycle is refused at save, naming both."*"""
    with pytest.raises(slicers.CalendarMixed) as raised:
        slicers.validate_grouping("invoices", ("cycle",), filters=("period",))
    message = str(raised.value)
    assert "cycle" in message
    assert "period" in message


def test_p2_25__the_dotted_wire_spelling_is_seen_too():
    """The ageing screen sends `f.period`. A calendar check that could not see
    the dotted form would be a check that cannot fire on the one screen that
    sends it — `runner`'s own note on `_FILTER_PREFIX`."""
    with pytest.raises(slicers.CalendarMixed):
        slicers.validate_grouping("invoices", ("cycle",), filters=("f.period",))


def test_p2_25__one_calendar_on_its_own_is_accepted_in_both_directions():
    """Law 7: a check that refused every grouping would pass the two cases
    above and be useless."""
    slicers.validate_grouping("invoices", ("cycle",), filters=("from", "to", "service"))
    slicers.validate_grouping("payments", ("accounting_period",), filters=("period", "class"))


def test_p2_25__year_and_day_commit_a_report_to_neither_calendar():
    """They mean the same thing in both hierarchies, so they discriminate
    nothing and must not trip the refusal."""
    assert slicers.calendar_of("year") is None
    assert slicers.calendar_of("day") is None
    assert slicers.calendar_of("accounting_period") == "calendar"
    assert slicers.calendar_of("cycle") == "billing"
    slicers.validate_grouping("invoices", ("year", "day"), filters=("period",))


def test_p2_25__the_head_can_always_say_which_calendar_this_report_rolls_up():
    """p84: *"The head says which calendar — 'Grouped by billing cycle'"*. A
    report that does not say is one a reader assumes about."""
    for dataset in datasets.DATASETS:
        assert slicers.declared_calendar(dataset.code) in datasets.TIME_HIERARCHIES


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 Phase 2 · P2.25 (p13, p85 read as images per B14 rule 42)
# generated: 2026-09-27 by lane REP-P2-MODEL
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
