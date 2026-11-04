# ── Trace ──────────────────────────────────────────────
# Change:  PO ruling 2026-09-10 — the outside-city surcharge becomes ONE
#          DROPDOWN of the services it APPLIES TO, pre-filled with every
#          service, and a clerk removes the ones to spare. Decision log entries
#          11 and 12 of 2026-09-10. NO schema, NO engine, NO migration.
# Rules:   BR-RAT-102 (the plan states the factor; the plan's own SERVICE LINE
#          states which services escape it) · BR-RAT-101 (the premises states
#          which side of the line it is on) · design §A4 S2 (the worked case)
# Tests:   this file
# ───────────────────────────────────────────────────────
"""The surcharge dropdown, asserted in DOLLARS because the flag is inverted.

⚠ **THE CLERK'S CHOICE IS THE EXACT NEGATION OF THE STORED FLAG, AND THAT IS
THE WHOLE REASON THIS FILE EXISTS.** The screen asks *which services does this
surcharge APPLY to*; the column stores *which services it SPARES*. Picked =
surcharged = `outside_city_exempt` **false**. Unpicked = spared = **true**.

**So a test that asserts the FLAG is worthless here.** Invert the mapping and
`outside_city_exempt == True` is still `True` — it is just true of the wrong
service, and every boolean assertion in the repository stays green while a
warehouse outside the city stops being surcharged, or a sewer line that has
been flat everywhere since §A4 S2 was signed starts being multiplied by 1.15.
The decision log says so in its own words: *"a control reading the opposite way
round from the value behind it is invisible to every check that asserts the
value … So the guard asserts MONEY, never the flag."*

**THE WORKED CASE IS THE SIGNED ONE.** Design §A4 S2, verbatim: *"BASE-S $8.00
(flat everywhere — the multiplier does NOT touch sewer)"*. A premises OUTSIDE
the city, on a plan that surcharges: **sewer's base stays `$8.00` and water's
`$8.00` becomes `$9.20`** at 15%. Those two numbers, side by side on one bill,
are the only thing that can tell a correct mapping from an inverted one.

**WHAT IS DELIBERATELY NOT ASSERTED.** Nothing here checks that the screen
renders a dropdown, or that a chip is removable. That is `PlanWizard`'s own DOM
suite and it cannot see money. This file starts at the PAYLOAD the new control
emits — the same `services` list the wizard posts — and ends at two amounts.

**PROVED RED FIRST, through pytest — the harness that will run it.** With
`setSurcharged`'s negation dropped (`outside_city_exempt: surchargedSet.has(...)`
instead of `!...`), the payload carries `sewer` surcharged and `water` spared,
and this file fails on the MONEY, verbatim:

    >       assert water == WATER_SURCHARGED
    E       AssertionError: assert Decimal('8.00') == Decimal('9.20')
    tests/test_cr090_the_surcharge_dropdown_is_the_negation.py:127

    1 failed, 4 passed

⚠ **FOUR OF THE FIVE STILL PASSED ON THAT DEFECT, AND THAT IS THE POINT OF THE
FILE'S SHAPE.** Both extremes — nothing spared and everything spared — are
symmetric under an inversion and cannot see it. Only the case with ONE service
spared can, which is why it is written first and why a suite of extremes would
have shipped the wrong bill.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.billing import gather

#: §A4 S2's own figures. `1.15` is the factor a 15% surcharge stores — the
#: conversion is the SERVER's (`services._validate_plan`) and is never done in
#: a browser, which is what `CR-087` D1 removed.
FACTOR = Decimal("1.15")
WATER_BASE = Decimal("8.00")
SEWER_BASE = Decimal("8.00")
WATER_SURCHARGED = Decimal("9.20")  # 8.00 × 1.15

#: A premises OUTSIDE the city limits. `BR-RAT-101`'s flag is THREE-state and
#: `None` refuses the bill by name, so it is stated here rather than omitted.
OUTSIDE = {"inside_city_limits": False, "address_line": "88 Quarry Hill Ct"}
INSIDE = {"inside_city_limits": True, "address_line": "101 Silver Creek Rd"}


def _jurisdiction(payload_services):
    """What `rating.selectors.plan_jurisdiction_pricing` publishes for a plan
    whose service lines are exactly what the wizard posted.

    Built from the PAYLOAD rather than from the database on purpose: the thing
    under test is the mapping between what a clerk picked and what is stored,
    and the payload is the first place that mapping is visible. The shape is
    the seam's own — `{"outside_city_factor", "exempt_services"}`.
    """
    return {
        "outside_city_factor": FACTOR,
        "exempt_services": tuple(
            line["service"] for line in payload_services if line["outside_city_exempt"]
        ),
    }


#: THE PAYLOAD THE NEW CONTROL EMITS when a clerk opens step 2 on a water +
#: sewer plan, leaves the surcharge at 15%, and REMOVES `sewer` from the
#: `Services surcharged` dropdown. `setSurcharged` rewrites every line, so
#: `water` is picked (`exempt` false) and `sewer` is not (`exempt` true).
SEWER_SPARED = (
    {"service": "water", "outside_city_exempt": False},
    {"service": "sewer", "outside_city_exempt": True},
)

#: The pre-filled state — the dropdown as it OPENS, with nothing removed. This
#: is also what `PlanService.outside_city_exempt`'s `default=False` already
#: means, which is why the control needs no effect to pre-fill itself.
NOTHING_SPARED = (
    {"service": "water", "outside_city_exempt": False},
    {"service": "sewer", "outside_city_exempt": False},
)

#: Every service removed. **ALLOWED, not refused** — PO ruling 2026-09-10:
#: pre-filling makes an empty picking a deliberate act, so a clerk who unpicks
#: everything has said *spare all of them*. ⚠ The DISCOUNT scope refuses an
#: empty list and that difference is deliberate; do not harmonise them.
ALL_SPARED = (
    {"service": "water", "outside_city_exempt": True},
    {"service": "sewer", "outside_city_exempt": True},
)


def _factor(service, payload_services, premises):
    return gather._jurisdiction_factor_for(
        service, jurisdiction=_jurisdiction(payload_services), premises=premises
    )


# ── THE MONEY ───────────────────────────────────────────────────────────────


def test_sewer_stays_eight_dollars_and_water_rises_to_nine_twenty():
    """§A4 S2's signed case, outside the city, both amounts on one bill."""
    water = WATER_BASE * _factor("water", SEWER_SPARED, OUTSIDE)
    sewer = SEWER_BASE * _factor("sewer", SEWER_SPARED, OUTSIDE)

    assert water == WATER_SURCHARGED
    assert sewer == SEWER_BASE
    # Said as the difference too, because that is the sentence a clerk reads:
    # one line moved by $1.20 and the other did not move at all.
    assert water - sewer == Decimal("1.20")


def test_the_dropdown_as_it_opens_surcharges_everything():
    """Nothing removed → both services move. The pre-filled default, in money.

    ⚠ **THIS IS THE HALF AN INVERSION PASSES.** A mapping written backwards
    still surcharges both services here, because nothing is spared either way.
    It is asserted so the pair above and below bracket the bug: the middle case
    is where an inversion shows, and a suite that only tested the extremes
    would be green on it.
    """
    assert WATER_BASE * _factor("water", NOTHING_SPARED, OUTSIDE) == WATER_SURCHARGED
    assert SEWER_BASE * _factor("sewer", NOTHING_SPARED, OUTSIDE) == Decimal("9.20")


def test_every_service_removed_is_allowed_and_charges_no_surcharge():
    """An empty picking is a STATEMENT here, and it yields the plain price.

    PO ruling 2026-09-10: *"this will not happen - we will have all services as
    default ooption"*, and pre-filling is what makes empty deliberate. Nothing
    refuses it, so the assertion is that both amounts are the un-uplifted ones
    rather than that a refusal was raised.
    """
    assert WATER_BASE * _factor("water", ALL_SPARED, OUTSIDE) == WATER_BASE
    assert SEWER_BASE * _factor("sewer", ALL_SPARED, OUTSIDE) == SEWER_BASE


def test_inside_the_city_nothing_moves_whatever_was_picked():
    """`BR-RAT-102`'s first gate — the premises decides, and it is shut.

    Asserted against the SPARED payload so the two gates cannot be confused for
    one another: a screen change that accidentally surcharged everything would
    still be invisible inside the city, and a reader needs to know that this
    file's other three cases are all outside it.
    """
    assert WATER_BASE * _factor("water", SEWER_SPARED, INSIDE) == WATER_BASE
    assert SEWER_BASE * _factor("sewer", SEWER_SPARED, INSIDE) == SEWER_BASE


def test_a_premises_nobody_placed_still_refuses_by_name():
    """`BR-RAT-101`'s three-state flag. Untouched by this change, asserted here
    so a lane reading this file does not conclude the screen change relaxed it.
    """
    with pytest.raises(gather.GatherProblem) as raised:
        _factor("water", SEWER_SPARED, {"address_line": "12 Unplaced Way"})
    assert "inside or outside the city limits" in str(raised.value)
