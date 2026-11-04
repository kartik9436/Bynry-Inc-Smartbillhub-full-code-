# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 Phase 2 · P2.17 (slicers derived from the model;
#           group to three levels with subtotals) · P2.26 (four visible).
# Rules:    brief §7.2.1 / §7.2.1B p83-p84 read as images (B14 rule 42) ·
#           CLAUDE.md hard rule 2 (money in Decimal, never a float) · NFR-5
# Tests:    this file
# ───────────────────────────────────────────────────────
"""P2.17 — THIRTEEN SLICERS WHERE THERE WERE TWO, AND SUBTOTALS THAT REFUSE.

No `django_db`: every function under test is pure over the declaration, and a
DB mark would add 133 seconds of migration to a test that reads a tuple.
"""

import pytest

from apps.reports import additivity, datasets, slicers


# ═══════════════════════════════════════════════════════════════════════════
# P2.17 — the slicers come from the dataset, not from the report
# ═══════════════════════════════════════════════════════════════════════════
def test_p2_17__ar_ageing_inherits_all_thirteen_dimensions_as_slicers():
    """The PO's finding: *"two slicers where the fact has about a dozen"*.

    Measured: `AR_AGEING_DIMENSIONS` is 13 and the ageing is served from the
    `payments` dataset. All thirteen are OFFERED — see the next test for how
    many are actually servable, which is the number that matters.
    """
    found = slicers.slicers_for("payments")
    assert len(found) == 13
    assert [entry["name"] for entry in found] == [
        dim.name for dim in datasets.AR_AGEING_DIMENSIONS
    ]


def test_p2_17__the_brief_says_thirteen_and_NINE_are_servable_measured():
    """⚠ **`DEF-REP-6847`, ASSERTED SO THE NUMBER CANNOT DRIFT UNNOTICED.**

    p12's outcome says AR Ageing *"goes from 2 slicers to the 13 its fact
    actually has, free"*. Measured against the code, it goes from 2 to **9**:
    the `payments` dataset accepts no filter for `customer_type`, `unit`,
    `area` or `rate_schedule`, so a chip for any of those would filter nothing
    — hard-won law 2, dead UI, on a live screen.

    **Nine is still four and a half times two**, which is the PO's finding
    answered; what is NOT answered is the last four, and that is a gap in the
    dataset's filter vocabulary rather than in this module. It is recorded as a
    number here so the next reader meets it instead of re-deriving it.
    """
    entries = slicers.slicers_for("payments")
    servable = [e["name"] for e in entries if e["servable"]]
    assert len(servable) == 9
    assert sorted(e["name"] for e in entries if not e["servable"]) == [
        "area", "customer_type", "rate_schedule", "unit",
    ]


def test_p2_17__across_the_nine_datasets_thirtyseven_of_seventyone_are_servable():
    """The blind-spot number law 7 asks for: a count of what is EXCLUDED
    printed beside the count of what is covered, so *"derived from the model"*
    can never be read as *"all of them work"*."""
    declared = sum(len(slicers.slicers_for(d.code)) for d in datasets.DATASETS)
    servable = sum(
        1 for d in datasets.DATASETS for e in slicers.slicers_for(d.code) if e["servable"]
    )
    assert (declared, servable) == (71, 37), (
        "DEF-REP-6847 has moved — re-measure and update this pair, or close it"
    )


def test_p2_17__a_dimension_added_to_a_dataset_reaches_every_report_on_it():
    """*"Adding a dimension to a dataset makes it available on every report
    built on it, with no report edited."* Asserted by construction: two
    definitions on one dataset see the same list."""
    one = slicers.slicers_for("payments", {"register": "R1"})
    two = slicers.slicers_for("payments", {"register": "R7"})
    assert [e["name"] for e in one] == [e["name"] for e in two]


def test_p2_17__every_dataset_offers_every_dimension_it_declares():
    """The blind-spot check (law 7): counted, not sampled."""
    for dataset in datasets.DATASETS:
        offered = {e["name"] for e in slicers.slicers_for(dataset.code)}
        assert offered == set(dataset.dimension_names()), dataset.code


# ═══════════════════════════════════════════════════════════════════════════
# P2.26 — four visible, the rest behind + Filter
# ═══════════════════════════════════════════════════════════════════════════
def test_p2_26__exactly_four_slicers_are_visible_never_thirteen():
    """*"Thirteen chips on screen is a worse screen, not a better one."*"""
    assert len(slicers.visible_slicers("payments")) == slicers.VISIBLE_SLICERS == 4
    assert len(slicers.slicers_for("payments")) == 13, "the other nine are still offered"


def test_p2_26__the_definition_names_its_four_and_they_win():
    named = slicers.visible_slicers(
        "payments", {"slicers": ["service", "collections_state", "age_bucket", "premises"]}
    )
    assert named == ("service", "collections_state", "age_bucket", "premises")


def test_p2_26__a_definition_naming_an_UNSERVABLE_dimension_does_not_get_a_dead_chip():
    """`DEF-REP-6847` on the bar. `area` is declared on `payments` and the
    dataset accepts no filter for it, so naming it must not put it on screen."""
    named = slicers.visible_slicers("payments", {"slicers": ["area", "service"]})
    assert "area" not in named
    assert "service" in named


def test_p2_26__a_definition_naming_a_dimension_the_dataset_lacks_is_ignored_not_served():
    """`BR-SHL-011` — fall back, never 4xx. A chip for a dimension the fact
    has not got is a control that filters nothing."""
    got = slicers.visible_slicers("payments", {"slicers": ["service", "invented_thing"]})
    assert "invented_thing" not in got
    assert "service" in got


def test_p2_26__a_dataset_with_fewer_than_four_dimensions_shows_what_it_has():
    """`audit_log` declares 3 and 2 are servable. A bar that padded to four
    would draw a chip for a dimension that does not exist."""
    assert len(slicers.visible_slicers("audit_log")) == 2


# ═══════════════════════════════════════════════════════════════════════════
# Grouping — three levels, refused past that, refused for a level that is not one
# ═══════════════════════════════════════════════════════════════════════════
def test_p2_17__three_levels_are_accepted_and_a_fourth_is_refused_naming_the_count():
    slicers.validate_grouping("payments", ("consumer_class", "service", "area"))
    with pytest.raises(slicers.GroupingRefused) as raised:
        slicers.validate_grouping("payments", ("consumer_class", "service", "area", "unit"))
    assert "3" in str(raised.value)


def test_p2_17__grouping_by_something_the_dataset_does_not_declare_is_refused_by_name():
    with pytest.raises(slicers.GroupingRefused) as raised:
        slicers.validate_grouping("payments", ("shoe_size",))
    assert "shoe_size" in str(raised.value)


def test_p2_17__grouping_by_a_hierarchy_level_is_accepted_not_only_by_a_dimension():
    """`premises` declares `(area, route, premises)`, so *group by route* is a
    real request and must not be refused as an unknown dimension."""
    slicers.validate_grouping("payments", ("route",))
    assert "route" in slicers.levels_for("payments", "premises")


def test_p2_17__the_same_level_twice_is_refused():
    with pytest.raises(slicers.GroupingRefused):
        slicers.validate_grouping("payments", ("service", "service"))


# ═══════════════════════════════════════════════════════════════════════════
# The subtotals — and the one distinction that makes this correct
# ═══════════════════════════════════════════════════════════════════════════
ROWS = [
    {"account_no": "A-1", "class": "RES", "service": "WATER", "total": "100.0000"},
    {"account_no": "A-2", "class": "RES", "service": "WATER", "total": "48121.1400"},
    {"account_no": "A-3", "class": "COM", "service": "WATER", "total": "250.0000"},
]


def test_p2_17__a_group_row_carries_its_count_its_path_and_its_subtotal():
    out = slicers.group_rows("payments", ROWS, ("class",), measures=("total",))
    groups = [row for row in out if row.get("__kind__") == "group"]
    assert [g["value"] for g in groups] == ["RES", "COM"], "groups keep the rows' own order"
    res = groups[0]
    assert res["rows"] == 2
    assert res["subtotals"]["total"] == "48221.1400"      # ⚠ Decimal, not float
    assert res["path"] == [{"dimension": "class", "column": "class", "value": "RES"}]


def test_p2_18__the_group_path_is_the_drill_through_filter_set():
    """*"A $48,221.14 subtotal opens the 412 rows that make it."* The path IS
    the filter set, so the rows behind a subtotal cannot be a different query
    from the one that produced it."""
    out = slicers.group_rows("payments", ROWS, ("class", "service"), measures=("total",))
    deepest = [r for r in out if r.get("__kind__") == "group" and r["level"] == 1][0]
    assert deepest["path"] == [
        {"dimension": "class", "column": "class", "value": "RES"},
        {"dimension": "service", "column": "service", "value": "WATER"},
    ]
    # Applying that path to the facts returns exactly the rows it counted.
    behind = [
        row
        for row in ROWS
        if all(row.get(step["dimension"]) == step["value"] for step in deepest["path"])
    ]
    assert len(behind) == deepest["rows"]


def test_p2_17__every_fact_row_survives_grouping():
    """A grouping that loses rows is a report that lost money."""
    out = slicers.group_rows("payments", ROWS, ("class",), measures=("total",))
    facts = [row for row in out if row.get("__kind__") != "group"]
    assert len(facts) == len(ROWS)


def test_p2_17__a_month_subtotal_is_a_NUMBER_while_the_grand_total_refuses():
    """⚠ **THE DISTINCTION THIS MODULE EXISTS FOR.**

    Group AR Ageing by month. The month's subtotal holds `time` FIXED — it is
    the receivable within one month, summed across accounts, which is exactly
    what a balance is for. The GRAND total spans every month and is §7.2.2's
    first trap. A module that refused both would make grouping useless and
    would still pass every refusal test in the suite.
    """
    # A subtotal at the only grouped level spans nothing below it.
    assert slicers.subtotal_across("payments", ("accounting_period",), 0) == ()
    lawful = additivity.footer("payments", {"total": "48221.1400"},
                               slicers.subtotal_across("payments", ("accounting_period",), 0))
    assert lawful["total"] == "48221.1400"

    # The footer spans time, and refuses.
    across = slicers.footer_across("payments", ("accounting_period",), {"from": "2026-07-01"})
    assert datasets.DIM_TIME in across
    refused = additivity.footer("payments", {"total": "48221.1400"}, across)
    assert refused["total"]["refused"] is True


def test_p2_17__an_unlawful_subtotal_still_refuses_at_the_level_that_spans_it():
    """The other direction of the same rule: group by class THEN by month, and
    the CLASS subtotal spans months — so it refuses, while each month inside it
    does not."""
    across = slicers.subtotal_across("payments", ("consumer_class", "accounting_period"), 0)
    assert datasets.DIM_TIME in across
    assert additivity.footer("payments", {"total": "1.0000"}, across)["total"]["refused"] is True


def test_p2_17__a_subtotal_is_decimal_and_never_a_float():
    """CLAUDE.md hard rule 2. `0.1 + 0.2` in `float` is `0.30000000000000004`,
    which on a few thousand rows ties out to nothing."""
    rows = [{"c": "X", "total": "0.1000"}, {"c": "X", "total": "0.2000"}]
    out = slicers.group_rows("payments", rows, ("c",), measures=("total",))
    group = [r for r in out if r.get("__kind__") == "group"][0]
    assert group["subtotals"]["total"] == "0.3000"


def test_p2_17__a_level_no_row_carries_is_NOT_bucketed_under_None():
    """⚠ **A MONEY GUARD, NOT A TIDINESS ONE (`DEF-REP-6847`).**

    `row.get(level)` returns `None` for every row when the column is absent, so
    the obvious implementation puts ALL the rows in ONE group keyed `None` and
    gives it a subtotal — a figure equal to the grand total, labelled with a
    blank, looking exactly like a correct group. Measured, 57 of 71 declared
    dimensions have no column on their own dataset, so that is the COMMON case.
    """
    rows = [{"account_no": "A-1", "total": "100.0000"}]
    out = slicers.group_rows("payments", rows, ("collections_state",), measures=("total",))
    assert not any(r.get("__kind__") == "group" for r in out)
    assert out == [dict(rows[0])]
    assert slicers.groupable_on("payments", "collections_state", rows) is False


def test_p2_17__grouping_by_nothing_returns_the_facts_unchanged():
    out = slicers.group_rows("payments", ROWS, (), measures=("total",))
    assert out == [dict(row) for row in ROWS]



# ═══════════════════════════════════════════════════════════════════════════
# DEF-REP-9150 — the footer asks the window the report SERVED, not the request
# ═══════════════════════════════════════════════════════════════════════════
AGEING_BANDS = ("current", "d1_30", "d31_60", "d61_90", "d90_plus", "total")


def test_def_rep_9150__an_as_at_report_asked_with_from_to_still_totals():
    """The Finance Aging view, its CSV and the viewer after a filter all send
    `from`+`to`; `ar_aging` reads only `to` and serves `{"as_of": …}`. Measured
    on a seeded utility before the fix: `$340.20` over 8 accounts became six
    em-dashes. The served instant spans no time, so every band is a number."""
    request = {"from": "2026-10-01", "to": "2026-10-31"}
    served = {"as_of": "2026-10-31"}
    # The request alone still reads as a range — the guard has not been
    # weakened, it has been given the better fact.
    assert datasets.DIM_TIME in slicers.footer_across("payments", (), request)
    across = slicers.footer_across("payments", (), request, served)
    assert datasets.DIM_TIME not in across
    totals = {name: "68.0400" for name in AGEING_BANDS} | {"total": "340.2000"}
    footer = additivity.footer("payments", totals, across)
    assert footer["total"] == "340.2000"
    assert not additivity.has_refusal(footer)


def test_def_rep_9150__a_served_start_equal_to_end_is_an_instant_too():
    """`plans_and_discounts` serves its as-at date as `{start: d, end: d}`."""
    across = slicers.footer_across(
        "payments", (), {"from": "2026-10-01", "to": "2026-10-31"},
        {"start": "2026-10-31", "end": "2026-10-31"},
    )
    assert datasets.DIM_TIME not in across


def test_def_rep_9150__a_balance_over_a_SERVED_RANGE_still_refuses():
    """The other half, and the one that keeps the guard honest: a running
    ledger `balance` over a served window of a month is a balance summed across
    time and must still come back as an em-dash and its reason."""
    across = slicers.footer_across(
        "journal_lines", (), {"from": "2026-10-01", "to": "2026-10-31"},
        {"start": "2026-10-01", "end": "2026-10-31"},
    )
    assert datasets.DIM_TIME in across
    footer = additivity.footer("journal_lines", {"balance": "1.0000", "debit": "5.0000"}, across)
    assert footer["balance"]["refused"] is True
    assert footer["balance"]["reason_code"] == "balance_does_not_sum_across_time"
    assert footer["debit"] == "5.0000"  # a flow still sums


def test_def_rep_9150__a_served_window_never_ADDS_time():
    """A served range defers to the request: no `from`/`to` asked, no `time`
    added — the fix can only remove a refusal, never manufacture one."""
    across = slicers.footer_across("payments", (), {}, {"start": "2026-10-01", "end": "2026-10-31"})
    assert datasets.DIM_TIME not in across


def test_def_rep_9150__grouping_by_month_still_refuses_an_as_at_grand_total():
    """A served instant removes only the WINDOW's contribution. Grouped by
    month, the grand total still spans months and still refuses."""
    across = slicers.footer_across(
        "payments", ("accounting_period",), {"from": "2026-10-01", "to": "2026-10-31"},
        {"as_of": "2026-10-31"},
    )
    assert datasets.DIM_TIME in across

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 Phase 2 · P2.17 · P2.26 (p12, p13, p83, p84 read as images per B14 rule 42)
# generated: 2026-09-27 by lane REP-P2-MODEL
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
