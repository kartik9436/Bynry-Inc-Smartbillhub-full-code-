# ── Trace ──────────────────────────────────────────────
# Change:   CR-029 (Routes & Cycles) — wave RC-W0, task W0-T2. B17 §7:
#           *"Done when: fixtures committed beside the tests that consume
#           them."* This is that file: the fixtures' own contract test.
# Fixtures: tests/cr029_schedule_fixtures.py · tests/cr029_dynamism_fixtures.py
# Rules:    B17 §2 (the eight one-word frequencies; the derived window) · B17 §5
#           (the dynamism audit's five rows) + G4 · D1's worked figure ("Sep
#           1-3") · CLAUDE.md rule 1 (every DB write inside `tenant_ctx`) ·
#           rule 3 (explicit UoM on every meter) · BR-MET-078 (no money).
# ───────────────────────────────────────────────────────
"""The RC-W0 fixtures, proved.

**What this file is FOR, and what it deliberately does not do.** RC-W2's period
engine and RC-W4's derivation tests do not exist yet, so these fixtures would
otherwise sit in the tree unexecuted until another lane picked them up — and an
unexecuted fixture is a guess with a filename. This module runs every one of
them and checks the things that must be true of the DATA regardless of what the
engine and the cascade eventually do:

* the eight frequency words are B17 §2's eight, in B17 §2's order;
* every stated window is `days_to_complete` days long, inclusive — which is the
  shape D1's worked figure *"Sep 1–3"* fixes, and the one an engine reading
  `days_to_complete` as an offset would get wrong;
* consecutive window starts advance by exactly the ruled step for their word;
* every day-of-month case's windows open on its start day;
* **every month-end window is the RULED clamp and nothing else** — OQ-339 was
  closed on 2026-08-23 (*"there is no 31st feb so we have to manage either 28th
  or 29th of Feb."*), so a stated window either opens on the anchor or, where
  the month is too short for it, on that month's LAST day — never a rolled or
  skipped one;
* each of the six dynamism scenarios builds, holds together, and records what
  the stored rows say.

⚠ **NOTHING HERE ASSERTS THAT TODAY'S DYNAMISM BEHAVIOUR IS RIGHT.** Four of
the six scenarios exist because it is not (B17 §5, and G4). The assertions are
about the scenario's SHAPE — the rows exist, the event happened, the ids line
up — so that when RC-W4 fixes the cascade these tests stay green and only
RC-W4's own expectations move.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from tests import cr029_schedule_fixtures as sched
from tests.cr029_dynamism_fixtures import (
    DYNAMISM_AUDIT,
    account_opened_and_closed_on_a_routed_unit,
    build_all,
    meter_attached_to_draft_routed_unit,
    premises_moved_between_areas,
    route_area_changed,
    routed_unit_with_no_meter,
    unit_moved_between_premises,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

# ═══════════════════════════════════════════════════════════════════════════
# PART 1 · THE SCHEDULE CASES — pure data, no database
# ═══════════════════════════════════════════════════════════════════════════

#: B17 §2's frequency table, transcribed here a SECOND time on purpose. If the
#: fixture module and this list ever disagree, one of them was edited without
#: reading the ruling — which is the drift the duplication exists to catch.
B17_EIGHT_WORDS = (
    "Daily",
    "Weekly",
    "Fortnightly",
    "Monthly",
    "Bimonthly",
    "Quarterly",
    "Semiannual",
    "Annual",
)


def test_the_vocabulary_is_b17s_eight_words_in_b17s_order():
    assert sched.FREQUENCY_WORDS == B17_EIGHT_WORDS
    assert len(sched.FREQUENCY_WORDS) == 8
    # every word is ONE word — the PO's instruction was *"give business names
    # to frequence - 1 word"*.
    assert all(" " not in word and "-" not in word for word in sched.FREQUENCY_WORDS)
    assert set(sched.FREQUENCY_STEP) == set(B17_EIGHT_WORDS)


def test_the_fixture_words_are_the_words_the_product_stores():
    """The fixtures and the shipped column must be ONE vocabulary.

    RC-W1 (commit d47fa88) made `apps/metering/schedule.FREQUENCIES` the
    canonical spelling; these cases carry it verbatim. Asserting the two
    against each other is what stops a rename on either side from becoming a
    fixture that quietly tests a word the product no longer has.
    """
    from apps.metering import schedule

    assert sched.FREQUENCY_WORDS == schedule.FREQUENCIES
    # and the legacy spellings the shipped rows hold still resolve INTO them,
    # which is what lets a CR-006 cycle be re-read as a CR-029 one
    assert schedule.business_frequency("bi_monthly") == "Bimonthly"
    assert schedule.business_frequency("biweekly") == "Fortnightly"


def test_every_frequency_word_has_at_least_one_case():
    covered = {case.frequency for case in sched.CASES}
    assert covered == set(B17_EIGHT_WORDS)
    # and the eight-word sweep is one case per word, no more
    assert [case.frequency for case in sched.VOCABULARY_CASES] == list(B17_EIGHT_WORDS)


def test_the_ruled_worked_figure_is_in_the_table_verbatim():
    """D1, quoted: *"a Monthly cycle starting the 1st with 3 days to complete
    proposes Sep 1-3 the moment August closes"*.

    This is the case that fixes the window's INCLUSIVITY. An engine that treats
    `days_to_complete` as an offset produces Sep 1–4 and fails here against the
    PO's own number rather than against a fixture's opinion.
    """
    case = sched.by_id("SC-MONTHLY-01")
    assert case.frequency == "Monthly"
    assert case.start_day == 1
    assert case.days_to_complete == 3
    assert case.windows[0] == (date(2026, 9, 1), date(2026, 9, 3))
    first, last = case.windows[0]
    assert (last - first).days + 1 == case.days_to_complete


@pytest.mark.parametrize("case", sched.CASES, ids=[c.case_id for c in sched.CASES])
def test_every_stated_window_is_days_to_complete_days_long_inclusive(case):
    for first, last in case.windows:
        assert last >= first, f"{case.case_id}: window ends before it starts"
        assert (
            last - first
        ).days + 1 == case.days_to_complete, (
            f"{case.case_id}: window {first}..{last} is not {case.days_to_complete} days"
        )


@pytest.mark.parametrize("case", sched.CASES, ids=[c.case_id for c in sched.CASES])
def test_the_first_stated_window_opens_on_the_first_run(case):
    if not case.windows:
        return  # SC-EDGE-FIRST-RUN-OFF-ANCHOR states none, on purpose
    assert case.windows[0][0] == case.first_run


@pytest.mark.parametrize("case", sched.CASES, ids=[c.case_id for c in sched.CASES])
def test_consecutive_starts_advance_by_the_ruled_step(case):
    kind, size = sched.FREQUENCY_STEP[case.frequency]
    starts = [first for first, _last in case.windows]
    for previous, following in zip(starts, starts[1:]):
        if kind == "days":
            assert (
                following - previous
            ).days == size, f"{case.case_id}: {case.frequency} must advance {size} days"
        else:
            months = (following.year - previous.year) * 12 + (following.month - previous.month)
            assert (
                months == size
            ), f"{case.case_id}: {case.frequency} must advance {size} calendar months"


@pytest.mark.parametrize("case", sched.CASES, ids=[c.case_id for c in sched.CASES])
def test_day_of_month_cases_open_on_their_start_day(case):
    if case.frequency not in sched.DAY_OF_MONTH_WORDS:
        assert case.start_day is None, (
            f"{case.case_id}: {case.frequency} is not day-of-month anchored "
            "(B17 §2: weekday anchor for weekly/fortnightly, n/a for daily)"
        )
        return
    assert case.start_day is not None
    # ⚠ **OQ-340 (ruled 2026-08-23) DECIDES WHICH DAY IS THE ANCHOR.** PO
    # verbatim: *"A: first window 15–17 Sep (start day becomes decorative)"* —
    # so when the first run disagrees with the stored start day, the FIRST RUN's
    # day is what every occurrence follows, and asserting against `start_day`
    # here would hold the fixtures to the reading the PO rejected.
    anchor = case.first_run.day if case.first_run.day != case.start_day else case.start_day
    for first, _last in case.windows:
        if first.day == anchor:
            continue
        # OQ-339's ruled clamp is the ONLY other lawful answer, and it is only
        # lawful in a month that genuinely cannot hold the anchor.
        assert first.day == _days_in_month(first) < anchor, (
            f"{case.case_id}: a stated window opens on {first.day}. The anchor is "
            f"{anchor} and {first.year}-{first.month:02d} has "
            f"{_days_in_month(first)} days, so this is neither the anchor nor "
            "OQ-339's clamp to the month's last day — it is a roll or a skip, "
            "and both were rejected by the PO on 2026-08-23."
        )


def test_the_month_end_family_covers_31_30_29_and_a_leap_year():
    """W0-T2, verbatim: *"month-end edges — start day 31 in February, start day
    29/30/31 across short months, and a leap year"*."""
    edges = {case.case_id: case for case in sched.MONTH_END_CASES}
    # start day 31 into February, and 31 into a 30-day month
    assert edges["SC-EDGE-31-FEB"].start_day == 31
    # …and February 2026 reads on the 28th — the ruling, as a date.
    assert (date(2026, 2, 28), date(2026, 2, 28)) in edges["SC-EDGE-31-FEB"].windows
    assert edges["SC-EDGE-31-APR"].start_day == 31
    # 30 and 29 into February
    assert edges["SC-EDGE-30-FEB"].start_day == 30
    assert edges["SC-EDGE-29-FEB-COMMON"].start_day == 29
    # ...and the leap year, where the SAME anchor needs no ruling at all
    leap = edges["SC-EDGE-29-FEB-LEAP"]
    assert (date(2028, 2, 29), date(2028, 3, 2)) in leap.windows, (
        "Feb 29 exists in 2028 — nothing to clamp. An engine that clamps every "
        "29th is wrong one year in four and right the other three."
    )
    assert date(2028, 2, 29).year % 4 == 0
    # a leap-day ANNIVERSARY, where the slow frequency makes the gap three years
    assert edges["SC-EDGE-ANNUAL-LEAP-DAY"].frequency == "Annual"
    assert (date(2029, 2, 28), date(2029, 2, 28)) in edges["SC-EDGE-ANNUAL-LEAP-DAY"].windows
    # and the edge reaches the slower day-of-month words too
    assert edges["SC-EDGE-QUARTERLY-31"].frequency == "Quarterly"


def test_the_pos_own_worked_figures_are_in_the_table_as_dates():
    """The three figures the PO was shown on 2026-08-23, each as a fixture.

    A ruling is only checkable if the number it was given on is in the tree.
    OQ-339 was put as *Monthly · start 31 · 3 days · February* and answered
    *"either 28th or 29th of Feb"*; OQ-340 as *first run 15 Sep against start
    day 1* and answered *"first window 15-17 Sep"*; OQ-341 as *Daily with 3
    days* and answered *"warning … if user override; let them do it"*.
    """
    common = sched.by_id("SC-EDGE-31-FEB-THE-RULED-FIGURE")
    assert (date(2026, 2, 28), date(2026, 3, 2)) in common.windows
    leap = sched.by_id("SC-EDGE-31-FEB-LEAP-THE-RULED-FIGURE")
    assert (date(2028, 2, 29), date(2028, 3, 2)) in leap.windows
    anchor = sched.by_id("SC-EDGE-FIRST-RUN-OFF-ANCHOR")
    assert anchor.start_day == 1 and anchor.first_run == date(2026, 9, 15)
    assert anchor.windows[0] == (date(2026, 9, 15), date(2026, 9, 17))
    overlap = sched.by_id("SC-EDGE-DTC-EXCEEDS-PERIOD")
    assert overlap.windows[0] == (date(2026, 9, 1), date(2026, 9, 3))
    assert overlap.windows[1] == (date(2026, 9, 2), date(2026, 9, 4))
    assert overlap.windows[1][0] <= overlap.windows[0][1], "they must actually overlap"


def _days_in_month(day: date) -> int:
    return (date(day.year + (day.month == 12), (day.month % 12) + 1, 1) - timedelta(days=1)).day


def test_every_month_end_window_is_the_clamp_and_never_a_roll_or_a_skip():
    """The cross-check that the case-by-case assertion above cannot make.

    A ROLL would put a window in the month AFTER the one the anchor names (3
    March for a 31 February); a SKIP would leave that month with no window at
    all. Both were rejected by the PO on 2026-08-23, so for every day-of-month
    case the occurrences must step ONE period at a time with no month missing
    and no month doubled.
    """
    for case in sched.CASES:
        if case.frequency not in sched.DAY_OF_MONTH_WORDS or case.start_day is None:
            continue
        _kind, size = sched.FREQUENCY_STEP[case.frequency]
        starts = [first for first, _last in case.windows]
        for previous, following in zip(starts, starts[1:]):
            months = (following.year - previous.year) * 12 + (following.month - previous.month)
            assert months == size, (
                f"{case.case_id}: {previous} → {following} moves {months} months "
                f"where {case.frequency} moves {size}. A short month must CLAMP "
                "inside its own month, never roll into the next one and never be "
                "skipped (OQ-339, ruled 2026-08-23)."
            )


# ═══════════════════════════════════════════════════════════════════════════
# PART 2 · THE DYNAMISM SCENARIOS — every write inside tenant_ctx (rule 1)
# ═══════════════════════════════════════════════════════════════════════════
pytestmark = pytest.mark.django_db


def test_dyn1_a_premises_moved_between_areas_builds_and_records_both_areas(brazos, dana):
    with tenant_ctx(brazos):
        scenario = premises_moved_between_areas(dana, brazos)

    assert scenario.scenario_id == "DYN-1"
    assert scenario.ids["north_route_code"] != scenario.ids["south_route_code"]
    assert scenario.ids["north_area_code"] != scenario.ids["south_area_code"]
    # the unit WAS routed before the move — otherwise the scenario proves nothing
    assert scenario.observed["stamped_route_code_before_move"] == scenario.ids["north_route_code"]
    # what the tag says NOW is South; what the stamp says is recorded, not judged
    assert scenario.observed["premises_area_code_after_move"] == scenario.ids["south_area_code"]
    assert "stamped_route_code_after_move" in scenario.observed


def test_dyn2_a_route_whose_area_changed_holds_a_member_from_the_old_area(brazos, dana):
    with tenant_ctx(brazos):
        scenario = route_area_changed(dana, brazos)

    assert scenario.scenario_id == "DYN-2"
    # the setup's whole point: one unit in the OLD area is a stored member, and
    # one unit in the NEW area is not — so "members not re-derived" is visible.
    assert scenario.observed["member_unit_ids_before"] == [str(scenario.ids["north_unit_id"])]
    assert str(scenario.ids["south_unit_id"]) not in scenario.observed["member_unit_ids_before"]
    assert scenario.observed["route_area_code_after"] == scenario.ids["south_area_code"]


def test_dyn3_a_unit_moved_between_premises_lands_on_the_other_premises(brazos, dana):
    with tenant_ctx(brazos):
        scenario = unit_moved_between_premises(dana, brazos)
        from apps.metering import models as metering_models

        unit = metering_models.Unit.objects.get(pk=scenario.ids["unit_id"])

    assert scenario.scenario_id == "DYN-3"
    assert str(unit.premises_id) == str(scenario.ids["target_premises_id"])
    assert scenario.observed["stamped_route_code_before_move"] == scenario.ids["north_route_code"]
    # the destination premises is genuinely on the OTHER route, so the question
    # "which route reads it now" has two different real answers
    assert scenario.ids["south_route_code"] != scenario.ids["north_route_code"]


def test_dyn4_the_draft_route_leak_is_reproduced_not_papered_over(brazos, dana):
    """G4. BR-MET-076 says a draft route stamps no service point; the fixture's
    job is to keep REPRODUCING the leak until RC-W4-T3 closes it, so this test
    asserts the setup (a draft route, a member unit, a meter attached) and
    records the stamp rather than demanding either value."""
    with tenant_ctx(brazos):
        scenario = meter_attached_to_draft_routed_unit(dana, brazos)
        from apps.metering import models as metering_models

        route = metering_models.Route.objects.get(pk=scenario.ids["draft_route_id"])

    assert scenario.scenario_id == "DYN-4"
    assert route.status == "draft"
    # the draft route held the membership BEFORE the meter arrived...
    assert scenario.observed["service_points_before_attach"] == 0
    assert scenario.observed["membership_route_codes"] == [scenario.ids["draft_route_code"]]
    # ...and the meter that arrived declares its unit of measure (rule 3)
    assert scenario.ids["uom"] == "kgal"
    assert "stamped_route_code_after_attach" in scenario.observed
    assert "stamped_cycle_code_after_attach" in scenario.observed


def test_dyn5_a_routed_unit_with_no_meter_has_no_service_point(brazos, dana):
    with tenant_ctx(brazos):
        scenario = routed_unit_with_no_meter(dana, brazos)

    assert scenario.scenario_id == "DYN-5"
    # both units are members; only one of them can be seen through a service point
    assert sorted(scenario.observed["member_unit_ids"]) == sorted(
        [str(scenario.ids["metered_unit_id"]), str(scenario.ids["meterless_unit_id"])]
    )
    assert scenario.observed["meterless_unit_service_points"] == 0
    assert scenario.observed["meterless_unit_stamped_route_code"] is None
    assert scenario.observed["metered_unit_stamped_route_code"] == scenario.ids["route_code"]


def test_dyn6_one_account_closes_and_one_stays_open_on_the_same_route(brazos, dana):
    with tenant_ctx(brazos):
        scenario = account_opened_and_closed_on_a_routed_unit(dana, brazos)

    assert scenario.scenario_id == "DYN-6"
    assert scenario.ids["closed_account_id"] != scenario.ids["open_account_id"]
    assert scenario.observed["closed_account_closed_at"] is not None
    assert scenario.observed["closed_account_status"] != scenario.observed["open_account_status"]
    # both units sit under ONE cycle, which is what makes "who does CY bill?" a
    # question with a wrong answer available (D13 — derived at bill-run time)
    assert scenario.observed["open_unit_stamped_cycle_code"] == scenario.ids["cycle_code"]


def test_the_whole_audit_builds_in_one_tenant_with_distinct_codes(brazos, dana):
    """RC-W4-T2 iterates `DYNAMISM_AUDIT`; this proves the six scenarios can
    coexist in one tenant — distinct route codes, distinct cycle codes — which
    they must, because `uq_routes_tenant_code` and BR-MET-074's per-service
    membership constraint would otherwise collide the moment two are built."""
    with tenant_ctx(brazos):
        scenarios = build_all(dana, brazos)

    assert set(scenarios) == {scenario_id for scenario_id, _b, _c in DYNAMISM_AUDIT}
    assert len(scenarios) == 6
    route_codes = [
        value
        for scenario in scenarios.values()
        for key, value in scenario.ids.items()
        if key.endswith("route_code")
    ]
    assert len(route_codes) == len(set(route_codes)), "two scenarios share a route code"


def test_no_scenario_carries_money_on_a_route_or_a_cycle(brazos, dana):
    """BR-MET-078, hardened by CR-029: *"routes and cycles are grouping only -
    so we will not tag late fees , etc"*, and D12 dropped the Balance column
    for the same reason.

    ⚠ The obvious version of this check — grepping the fixture SOURCE for the
    word "amount" — was written first and was wrong: it fired on the docstring
    that explains there is no money here. A check that cannot tell its subject
    from a sentence about its subject is worse than no check. So this reads the
    BUILT DATA instead: every value the scenarios hand downstream, and every
    route and cycle row they wrote.
    """
    from decimal import Decimal

    from apps.metering import models as metering_models

    #: ⚠ Matched as WHOLE UNDERSCORE-SEPARATED WORDS, not as substrings. The
    #: substring version fired on `routes.feeder_ref` — "fee" inside "feeder" —
    #: which is the second false positive this one check produced while being
    #: written, and both would have read as a real BR-MET-078 breach.
    money_words = {
        "amount",
        "balance",
        "fee",
        "fees",
        "price",
        "rate",
        "deposit",
        "penalty",
        "charge",
    }

    def money_shaped(name: str) -> set[str]:
        return {token for token in name.lower().split("_") if token in money_words}

    with tenant_ctx(brazos):
        scenarios = build_all(dana, brazos)

        for scenario in scenarios.values():
            for bag in (scenario.ids, scenario.observed):
                for key, value in bag.items():
                    assert not money_shaped(
                        key
                    ), f"{scenario.scenario_id} hands downstream a money-shaped key {key!r}"
                    assert not isinstance(
                        value, Decimal
                    ), f"{scenario.scenario_id}.{key} is a Decimal — no money on these surfaces"

        # …and the rows themselves: `routes` and `cycles` must have no money
        # COLUMN to seed, which is the rule this data is only allowed to obey.
        for model in (metering_models.Route, metering_models.Cycle):
            columns = {f.name.lower() for f in model._meta.get_fields() if hasattr(f, "attname")}
            offenders = {c for c in columns if money_shaped(c)}
            assert (
                not offenders
            ), f"{model.__name__} has grown a money-shaped column {offenders} — BR-MET-078"
