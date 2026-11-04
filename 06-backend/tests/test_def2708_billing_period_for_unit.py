# ── Trace ──────────────────────────────────────────────
# Defect:  **DEF-2708** — the bill raised at a disconnection charges a FULL
#          month's standing charge for a PART month, because B4.3's denominator
#          is read through `apps.customers.seams.billing_period_for_unit` and
#          `apps.metering.selectors.billing_period_for_unit` HAS NEVER EXISTED.
#          On the PO's own account `A-11488`, cut 18 August on a $40.00 monthly
#          base: **$40.00 charged where 18 days of 31 is $23.23 — $16.77 too
#          much, on a customer's final bill.**
# Rules:   B4.3 ❄️ FROZEN (base ÷ cycle length × service days — the RULE does
#          not move here; this supplies the denominator the rule already asks
#          for) · BR-MET-121 (PO 2026-08-26, *"when you run bill cycle you pull
#          the reading and at that time we have to decide whether it is for 90
#          days or whrther it for 30 days or 15 days"*) · OQ-339 (the month-end
#          clamp) · OQ-340 (the first run is the anchor) · BR-MET-077 (a cycle
#          is a DEFINITION) · BR-MET-082 Amendment 1 + CR-029 D4 (a unit's cycle
#          is DERIVED at run time, never read off a stale stamp) ·
#          BR-TEN-043 / G6 (no clock on a money path — `as_of` is an argument) ·
#          CLAUDE.md rule 1 (tenant scoping) · rule 3 (units are explicit)
# Tests:   this file
# ───────────────────────────────────────────────────────
"""**THE DENOMINATOR, PUBLISHED.** 18 days of *what* — and the answer is 31.

════════════════════════════════════════════════════════════════════════════
WHAT WAS ACTUALLY MISSING, AND WHY IT WAS NOT A COLUMN
════════════════════════════════════════════════════════════════════════════
The lane that filed `DEF-2708` established — correctly, and this file verified
it again before writing a line — that **a billing period is NOT readable off
the `cycles` table as it stands**:

  * metering `0021_cr029_drop_legacy_cycle_columns` executes
    `RemoveField(model_name="cycle", name="window_start")` and the same for
    `window_end`; metering `0023` took `bill_date`. A cycle now carries
    `frequency` · `start_day` · `days_to_complete` · `bill_day` · `due_days` ·
    `first_run_date` and **not one calendar date describing a period**.
  * `period_engine`'s `Window` is the **READ** window — `[start, start +
    days_to_complete − 1]`, the days the crew is out with the handheld. The
    module's own worked figure says so: *"a Monthly cycle starting the 1st with
    3 days to complete proposes Sep 1-3"*. **Three days is not a month**, and
    dividing a $40.00 base by 3 would have been very much worse than dividing
    it by 18.

**But the BILLING period is derivable, and from facts the PO has already
ruled — so no column is added and no new rule is minted.** A billing period is
the span **from one occurrence's anchor date to the day before the next
occurrence's anchor date**. Both ends come from the cycle's own ruled fields:

  * the ANCHOR is `first_run_date`'s day — `OQ-340`, PO 2026-08-23, *"A: first
    window 15–17 Sep (start day becomes decorative)"*;
  * the STEP is `FREQUENCY_STEP`, B17 §2's own table;
  * a month with no such day CLAMPS — `OQ-339`, *"there is no 31st feb so we
    have to manage either 28th or 29th of Feb."*

That is the identical arithmetic `period_engine.expected_span_days` already
performs for **BR-MET-121's bill-run half**, published to billing since
2026-08-26 as `selectors.cycle_expected_span_days` and consumed by
`apps/billing/read_analysis.py` to judge whether a read's span is 15, 30 or 90
days. **The cut-bill path simply never asked metering the question metering was
already answering for the run's Days tab.** TC-4 asserts the two agree, so they
agree by rule rather than by coincidence — the standard `OQ-339` set.

════════════════════════════════════════════════════════════════════════════
RED-FIRST RECORD (hard-won law 7)
════════════════════════════════════════════════════════════════════════════
Every case here was run against the tree before the implementation landed and
failed on the missing callables, verbatim:

    AttributeError: module 'apps.metering.period_engine' has no attribute
    'billing_period'
    AttributeError: module 'apps.metering.selectors' has no attribute
    'billing_period_for_unit'

The transcript is in the lane report and in `12-governance/02-decision-log.md`.
"""

from datetime import date

import pytest

from apps.metering import models as metering_models
from apps.metering import period_engine
from apps.metering import selectors as metering_selectors

from tests.test_us_bil_001_prepare import a_billed_unit, a_cycle
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
    make_plan,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: `A-11488`'s own August, and the two numbers the whole defect is made of.
AUGUST_START = date(2026, 8, 1)
AUGUST_END = date(2026, 8, 31)
CUT_ON = date(2026, 8, 18)


def _an_august_cycle(tenant, *, code="08-A", frequency="Monthly", first_run=AUGUST_START):
    """A cycle configured the way CR-029 says a cycle is configured.

    `a_cycle`'s three ruled fields plus the two the period engine anchors on.
    `days_to_complete=5` is deliberately NOT 31: the READ window is 1–5 August
    and the BILLING period is 1–31 August, and a test whose two numbers were
    equal could not tell the two apart — which is the exact confusion
    `DEF-2708` is made of.
    """
    cycle = a_cycle(tenant, code=code)
    cycle.frequency = frequency
    cycle.days_to_complete = 5
    cycle.first_run_date = first_run
    cycle.save(update_fields=["frequency", "days_to_complete", "first_run_date"])
    return cycle


def _a_unit_on(actor, tenant, cycle):
    """One metered unit whose service point names `cycle` — no read needed."""
    plan = make_plan(tenant, name="A-11488 Residential", services=("electric",))
    return a_billed_unit(
        actor, tenant, cycle, plan, asset_no=f"M-{cycle.code}", label="A", consumption=None
    )


# ════════════════════════════════════════════════════════════════════════════
# TC-1 · THE PURE ARITHMETIC — 18 DAYS OF **31**, AND NOT OF 5
# ════════════════════════════════════════════════════════════════════════════
def test_tc1__the_billing_period_is_the_span_between_anchors_not_the_read_window():
    """`period_engine.billing_period` — no ORM, no tenant, no clock.

    The PO's own case: a Monthly cycle first run 1 August 2026, asked about the
    cut day, answers **1–31 August**. The cycle's `days_to_complete` is not an
    argument at all, which is the point: how long the crew takes to read the
    meters cannot change what a customer's standing charge is divided by.
    """
    period = period_engine.billing_period(
        frequency="Monthly", start_day=1, first_run=AUGUST_START, as_of=CUT_ON
    )
    assert period == (AUGUST_START, AUGUST_END)
    assert (period[1] - period[0]).days + 1 == 31  # B4.3's denominator


def test_tc1b__every_frequency_answers_its_own_span_and_february_is_short():
    """Four of B17 §2's eight words, and the month that made `OQ-339` exist.

    February 2026 is 28 days, so the same cycle asked in February answers 28 —
    a bill prorated on a fabricated 30 would over-charge a February customer
    and under-charge an August one, which is why nothing here assumes a month.
    """
    assert period_engine.billing_period(
        frequency="Monthly", start_day=1, first_run=date(2026, 1, 1), as_of=date(2026, 2, 14)
    ) == (date(2026, 2, 1), date(2026, 2, 28))
    assert period_engine.billing_period(
        frequency="Quarterly", start_day=1, first_run=date(2026, 6, 1), as_of=date(2026, 7, 4)
    ) == (
        date(2026, 6, 1),
        date(2026, 8, 31),
    )  # 92 days
    assert period_engine.billing_period(
        frequency="Fortnightly", start_day=None, first_run=date(2026, 6, 1), as_of=date(2026, 6, 9)
    ) == (
        date(2026, 6, 1),
        date(2026, 6, 14),
    )  # 14 days
    assert period_engine.billing_period(
        frequency="Annual", start_day=1, first_run=date(2026, 1, 1), as_of=date(2026, 8, 18)
    ) == (
        date(2026, 1, 1),
        date(2026, 12, 31),
    )  # 365 days


def test_tc1c__a_month_end_anchor_tiles_the_calendar_with_no_gap():
    """**OQ-339's clamp, and the reason the end is the NEXT ANCHOR minus a day.**

    A cycle anchored on the 31st opens 31 Jan, then 28 Feb (clamped — the PO
    named both February lengths), then 31 Mar. Deriving the end by re-stepping
    from the CLAMPED start would answer 28 Feb → 27 Mar and leave **28, 29 and
    30 March belonging to no period at all** — three days a customer cut on the
    29th would be prorated against a period that does not contain them. The
    next anchor closes it: 28 Feb → **30 Mar**, and the periods tile.
    """
    assert period_engine.billing_period(
        frequency="Monthly", start_day=31, first_run=date(2026, 1, 31), as_of=date(2026, 2, 10)
    ) == (date(2026, 1, 31), date(2026, 2, 27))
    assert period_engine.billing_period(
        frequency="Monthly", start_day=31, first_run=date(2026, 1, 31), as_of=date(2026, 3, 29)
    ) == (date(2026, 2, 28), date(2026, 3, 30))


def test_tc1d__no_schedule_and_no_opened_occurrence_are_both_a_stated_absence():
    """`None`, never a guess. A cycle nobody has scheduled has no period, and a
    date before the first run is not inside one — assuming a 30-day month would
    be money invented from a calendar nobody configured."""
    assert (
        period_engine.billing_period(frequency="Monthly", start_day=1, first_run=None, as_of=CUT_ON)
        is None
    )
    assert (
        period_engine.billing_period(
            frequency=None, start_day=1, first_run=AUGUST_START, as_of=CUT_ON
        )
        is None
    )
    assert (
        period_engine.billing_period(
            frequency="Monthly", start_day=1, first_run=date(2026, 9, 1), as_of=CUT_ON
        )
        is None
    )


# ════════════════════════════════════════════════════════════════════════════
# TC-2 · THE SELECTOR — THE READ TWO CALLERS HAVE WAITED FOR SINCE 2026-08-11
# ════════════════════════════════════════════════════════════════════════════
def test_tc2__the_unit_read_answers_the_august_period(brazos, marcus):
    """`apps.metering.selectors.billing_period_for_unit(unit_id, as_of=…)` —
    the contract written out verbatim in `apps/customers/seams.py`, answered.

    ISO strings, `{start, end}`, exactly as the seam asks. The unit's cycle is
    reached through metering's own service-point/route resolution, which is why
    customers may not make this join itself (B1)."""
    with tenant_ctx(brazos):
        cycle = _an_august_cycle(brazos)
        unit = _a_unit_on(marcus, brazos, cycle)
        period = metering_selectors.billing_period_for_unit(unit["id"], as_of=CUT_ON)

    assert period == {"start": "2026-08-01", "end": "2026-08-31"}


def test_tc2b__the_read_window_is_a_different_and_shorter_span(brazos, marcus):
    """The two spans, side by side, from ONE cycle — `DEF-2708` in one assert.

    The crew reads 1–5 August (5 days); the customer is billed on 1–31 August
    (31 days). Dividing a $40.00 base by the READ window would have charged
    **$144.00** for 18 days, so this is not a nicety."""
    with tenant_ctx(brazos):
        cycle = _an_august_cycle(brazos)
        unit = _a_unit_on(marcus, brazos, cycle)
        billing = metering_selectors.billing_period_for_unit(unit["id"], as_of=CUT_ON)
        read_window = period_engine.latest_opened_window(
            frequency=cycle.frequency,
            start_day=cycle.start_day,
            days_to_complete=cycle.days_to_complete,
            first_run=cycle.first_run_date,
            as_of=CUT_ON,
        )

    assert billing == {"start": "2026-08-01", "end": "2026-08-31"}
    assert (read_window.period_start, read_window.period_end) == (
        date(2026, 8, 1),
        date(2026, 8, 5),
    )


def test_tc2c__an_unscheduled_cycle_and_an_unstamped_unit_both_answer_none(brazos, marcus):
    """Two absences the caller must STATE rather than fill in.

    A pre-CR-029 cycle carries no frequency and no first run — every cycle
    `a_cycle` builds is one — and a unit whose service point names no cycle has
    no period to read. Both answer `None`, and `cut_bill.CUT_BILL_DENOMINATOR
    _ABSENT` is what a caller does with that."""
    with tenant_ctx(brazos):
        legacy = a_cycle(brazos, code="LEGACY")  # no frequency, no first run
        unit = _a_unit_on(marcus, brazos, legacy)
        assert metering_selectors.billing_period_for_unit(unit["id"], as_of=CUT_ON) is None

        metering_models.ServicePoint.objects.filter(tenant=brazos, unit_id=unit["id"]).update(
            cycle=None
        )
        assert metering_selectors.billing_period_for_unit(unit["id"], as_of=CUT_ON) is None


def test_tc2d__two_cycles_on_one_unit_answer_none_rather_than_picking_one(brazos, marcus):
    """A unit billed on two different calendars has no single period.

    Answering one of them would silently choose which calendar a customer's
    base charge is divided by — a $40.00 base is $23.23 over 31 days and
    $25.71 over 28. The absence is stated instead."""
    with tenant_ctx(brazos):
        august = _an_august_cycle(brazos, code="08-A")
        unit = _a_unit_on(marcus, brazos, august)
        quarterly = _an_august_cycle(brazos, code="08-Q", frequency="Quarterly")
        points = list(
            metering_models.ServicePoint.objects.filter(tenant=brazos, unit_id=unit["id"])
        )
        assert points, "the fixture must give the unit at least one service point"
        metering_services_point = points[0]
        metering_models.ServicePoint.objects.create(
            tenant=brazos,
            unit_id=unit["id"],
            service_id=metering_services_point.service_id,
            cycle=quarterly,
        )
        assert metering_selectors.billing_period_for_unit(unit["id"], as_of=CUT_ON) is None


# ════════════════════════════════════════════════════════════════════════════
# TC-3 · HARD RULE 1 — A CROSS-TENANT UNIT IS ABSENT, NEVER ANOTHER TENANT'S
# ════════════════════════════════════════════════════════════════════════════
def test_tc3__another_tenants_unit_is_absent(brazos, lonestar, marcus):
    """CLAUDE.md rule 1. Brazos Bend's unit read from Lone Star answers `None` —
    a period is a fact about somebody's money and it does not leak."""
    with tenant_ctx(brazos):
        cycle = _an_august_cycle(brazos)
        unit = _a_unit_on(marcus, brazos, cycle)
    with tenant_ctx(lonestar):
        assert metering_selectors.billing_period_for_unit(unit["id"], as_of=CUT_ON) is None


# ════════════════════════════════════════════════════════════════════════════
# TC-4 · THE TWO PUBLISHED FACTS AGREE BY RULE, NOT BY COINCIDENCE
# ════════════════════════════════════════════════════════════════════════════
def test_tc4__the_period_length_matches_br_met_121s_expected_span(brazos, marcus):
    """`cycle_expected_span_days` has answered *"how long is one period of this
    cycle"* for billing's Days tab since 2026-08-26. This read answers the same
    question with two dates, and the two must not drift: 1 August 2026 →
    **31** both ways. `OQ-339`'s own complaint about the schedule was that two
    derivations agreed *by coincidence*; this asserts the agreement."""
    with tenant_ctx(brazos):
        cycle = _an_august_cycle(brazos)
        unit = _a_unit_on(marcus, brazos, cycle)
        period = metering_selectors.billing_period_for_unit(unit["id"], as_of=CUT_ON)
        span = metering_selectors.cycle_expected_span_days(cycle.id, period_start=AUGUST_START)

    start = date.fromisoformat(period["start"])
    end = date.fromisoformat(period["end"])
    assert (end - start).days + 1 == span == 31


# ════════════════════════════════════════════════════════════════════════════
# TC-5 · BR-TEN-043 — `as_of` IS AN ARGUMENT, AND ON A MONEY PATH IT MATTERS
# ════════════════════════════════════════════════════════════════════════════
def test_tc5__the_period_follows_the_event_date_and_not_a_clock(brazos, marcus):
    """A cut committed in March for a February cut day must be prorated against
    **February's** 28 days, not March's 31. Asking a clock would give whichever
    month the clerk happened to click in — the same $40.00 base is $23.23 over
    31 days and $25.71 over 28."""
    with tenant_ctx(brazos):
        cycle = _an_august_cycle(brazos, first_run=date(2026, 1, 1))
        unit = _a_unit_on(marcus, brazos, cycle)
        february = metering_selectors.billing_period_for_unit(unit["id"], as_of=date(2026, 2, 18))
        march = metering_selectors.billing_period_for_unit(unit["id"], as_of=date(2026, 3, 18))

    assert february == {"start": "2026-02-01", "end": "2026-02-28"}
    assert march == {"start": "2026-03-01", "end": "2026-03-31"}


# ════════════════════════════════════════════════════════════════════════════
# TC-6 · THE CYCLE IS **DERIVED** (CR-029 D4), NOT READ OFF A STALE STAMP
# ════════════════════════════════════════════════════════════════════════════
def test_tc6__a_unit_reached_through_its_route_answers_the_routes_cycle(brazos, dana):
    """**BR-MET-082 Amendment 1, applied to the denominator.**

    PO verbatim: *"at the time of Run -> it will figure out how many accounts or
    meter or devices it has to take into account; every run it is not necessry
    it will ahve same number of accounts or meters - since Utility will make
    changes"*. So `units_in_cycle` stopped trusting `service_points.cycle_id`
    and started deriving membership from the route — because a stale stamp
    dropped units out of bill runs (`DEF-225` / `DEF-249`). A denominator read
    off that same stale stamp would have the same bug with money attached, so
    this read derives too.

    Here the unit is on a route WITH a route id, so the route-less "explicit
    statement" branch cannot fire and the answer can only have come through
    `derivation.routes_for_unit`. The route's cycle is Monthly with a first run
    of 1 August, so the period is **1–31 August** — the same 31 the PO's own
    figure divides by.
    """
    from apps.metering import services as metering_services

    from tests.test_def227_all_services_route_stamp import _active_route

    with tenant_ctx(brazos):
        cycle = _an_august_cycle(brazos, code="08-RT")
        route = _active_route(dana, code="RT-2708", service_code="water", cycle=cycle)
        premises = make_premises(dana, address_line="12 Foundry Row")
        unit = make_unit(dana, premises["id"], label="Unit A")
        metering_services.ensure_service_point(unit["id"], "water")
        metering_services.update_route(dana, route.id, {"unit_ids": [unit["id"]]})
        point = metering_models.ServicePoint.objects.get(
            tenant_id=brazos.id, unit_id=unit["id"], service__code="water"
        )
        period = metering_selectors.billing_period_for_unit(unit["id"], as_of=CUT_ON)

    # The stamp carries a ROUTE, so the route-less branch is provably not what
    # answered — the derivation is.
    assert point.route_id == route.id
    assert period == {"start": "2026-08-01", "end": "2026-08-31"}
