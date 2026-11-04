# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · `P6.11` wave 4 — R46 Bill Projection. Drawing read
#           as an IMAGE (B14 rule 42): p062 of
#           `05-prototype/09 Reports Build Brief.pdf`, rendered at 3.0x.
# Rules:    `BR-REP-042` (PO ruling 2026-09-27 — ± 15% of the USAGE part only,
#           never the fixed charges) · `OQ-REP-12769` (the *Winter average*
#           basis — UNRULED and stubbed) · `BR-REP-024` (NULL with a reason,
#           never a 0) · CLAUDE.md hard rule 2 (money 4dp, DISPLAY 2) · hard
#           rule 3 (consumption always with an explicit unit) · B14 rule 37 (a
#           figure drawn in a wireframe is an ILLUSTRATION).
# ───────────────────────────────────────────────────────
"""**R46 BILL PROJECTION — and the ± range is the whole point of this file.**

⚠ **`BR-REP-042` WAS RULED ON 2026-09-27 AND NO TEST ASSERTED IT UNTIL THIS
ONE.** A ruled figure with no test is a figure that drifts silently, and this
particular one has **two plausible wrong answers sitting either side of it** —
15% of the TOTAL, and the number actually printed on the drawing. Both are
asserted as NOT the answer, by name, because a test that only asserted the right
figure would pass on an implementation that happened to agree by coincidence on
one fixture.

⚠ **NOTHING HERE SKIPS**, and nothing here needs a database: the ruling is
arithmetic over components, so it is proved as arithmetic.
"""

from decimal import Decimal as D

import pytest

from apps.rating import projection

# ── p062's OWN FOUR COMPONENTS, figure for figure ───────────────────────────
WATER_BASE = D("18.00")
WATER_USAGE = D("59.64")
SEWER_BASE = D("22.00")
SEWER_USAGE = D("88.46")

DRAWN_TOTAL = D("188.10")          # p062's `Projected total`, at DISPLAY width
DRAWN_BAND = D("12.00")            # p062's `±$12` — an ILLUSTRATION (B14 r37)

# ⚠ **THE DRAWING PRINTS TWO DECIMALS AND THE ENGINE STORES FOUR, AND THE
# DIFFERENCE IS HARD RULE 2 RATHER THAN A DISAGREEMENT.** p062's sewer usage row
# reads `3,880 gal x 0.0228 = 88.46`, and `3880 x 0.0228` is **88.464** — the
# drawing is displaying it, correctly, at two places. So the stored figures are
# `148.1040` of usage and `188.1040` in total, and the ruled band is `22.2156`,
# which DISPLAYS as the `$22.22` the ruling's own arithmetic gives. Both widths
# are asserted below: the storage figure because that is what the read serves,
# and the display figure because that is what the customer is shown and what the
# ruling was reasoned in.
STORED_USAGE_PART = D("148.1040")   # 59.6400 + 88.4640
STORED_TOTAL = D("188.1040")
RULED_BAND = D("22.2156")           # 0.15 x 148.1040
RULED_BAND_DISPLAYED = D("22.22")
BAND_OVER_THE_TOTAL = D("28.2156")  # 0.15 x 188.1040 — the wrong answer

# ── `BR-REP-042`'s OWN SIGNED WORKED EXAMPLE ────────────────────────────────
SIGNED_BASE = D("24.00")
SIGNED_USAGE = D("60.00")
SIGNED_TOTAL = D("84.00")
SIGNED_BAND = D("9.0000")           # 0.15 x 60.00
SIGNED_BAND_OVER_TOTAL = D("12.6000")  # 0.15 x 84.00 — the rule names this as wrong


def _base(name, service, amount):
    return projection.component(
        name=name,
        service=service,
        basis=projection.BASIS_MONTHLY,
        rate=amount,
        quantity=D("1"),
        unit="month",
    )


def _usage(name, service, quantity, rate, unit="gal"):
    return projection.component(
        name=name,
        service=service,
        basis=projection.BASIS_STRAIGHT_LINED,
        rate=rate,
        quantity=quantity,
        unit=unit,
    )


def test_THE_BAND_IS_15_PERCENT_OF_THE_USAGE_PART_AND_NEVER_OF_THE_TOTAL():
    """⚠ **THE RULING, ASSERTED AS ARITHMETIC** — `BR-REP-042`.

    PO verbatim: *"Set a percentage — say ±15% — applied to the usage part only,
    never to fixed charges"*.

    On p062's own four components:

        base   18.00 + 22.00 =  40.00   ← NO range over this
        usage  59.64 + 88.46 = 148.10   ← the range is over THIS
        total                  188.10

        ruled  0.15 x 148.10 = 22.215   →  ± $22.22
        wrong  0.15 x 188.10 = 28.215   →  ± $28.22
    """
    components = [
        _base("Water base", "water", WATER_BASE),
        _usage("Water usage", "water", D("4200"), D("0.0142")),
        _base("Sewer base", "sewer", SEWER_BASE),
        _usage("Sewer usage", "sewer", D("3880"), D("0.0228")),
    ]
    band = projection.band_for(components)

    assert band == RULED_BAND
    # And at the width a CUSTOMER sees it, which is the width the ruling was
    # reasoned in (hard rule 2 — stored 4, displayed 2).
    assert band.quantize(D("0.01")) == RULED_BAND_DISPLAYED
    # ⚠ **BOTH WRONG ANSWERS ASSERTED BY NAME.** A test that only asserted the
    # right one would pass on a coincidence.
    assert band != BAND_OVER_THE_TOTAL, "the band was struck over the TOTAL, not the usage"
    assert band != DRAWN_BAND, "the band came from the DRAWING, which is an illustration"
    # And the fixed charges are genuinely outside it: the band is smaller than
    # 15% of the total by exactly 15% of the base.
    assert BAND_OVER_THE_TOTAL - band == (WATER_BASE + SEWER_BASE) * D("0.15")


def test_the_rules_own_signed_worked_example_is_nine_dollars_and_not_twelve_sixty():
    """`BR-REP-042` verbatim: *"`$84.00` made of `$24.00` base and `$60.00` usage
    carries ± `$9.00`, not ± `$12.60`."*

    Asserted separately from p062's figures on purpose: the rule was SIGNED on
    this example, and a signature covers only what was shown.
    """
    components = [
        _base("Water base", "water", SIGNED_BASE),
        _usage("Water usage", "water", D("6000"), D("0.01")),
    ]
    assert projection.projected_total(components) == D("84.0000") == SIGNED_TOTAL
    band = projection.band_for(components)
    assert band == SIGNED_BAND
    assert band != SIGNED_BAND_OVER_TOTAL


def test_a_bill_of_only_fixed_charges_has_no_range_at_all():
    """The ruling's reasoning, taken to its end — *"the fixed `$24.00` is known
    exactly; a range over it invents doubt the product does not have"*.

    An account with no usage component has a bill the product knows exactly, so
    the band is **None** and never `$0.00`: a `$0.00` range is a printed promise
    of exactness, and `BR-REP-024` forbids the plausible number.
    """
    components = [_base("Fire line", "fire", D("60.00"))]
    assert projection.projected_total(components) == D("60.0000")
    assert projection.band_for(components) is None


def test_the_winter_average_basis_is_stubbed_and_never_guessed():
    """`OQ-REP-12769`, and the prime directive.

    ⚠ **THE STUB CARRIES THE QUESTION'S ID IN THE CODE**, which is what the
    prime directive asks for, so a lane that reaches this line is sent to the
    question rather than to a default.
    """
    with pytest.raises(NotImplementedError) as raised:
        projection.winter_average_quantity(account="100244", service="sewer")
    assert "OQ-REP-12769" in str(raised.value)


def test_a_winter_average_component_is_served_null_with_its_reason_and_is_outside_the_band():
    """`BR-REP-024` **and** `BR-REP-042`, and the second half is the subtle one.

    The row is DRAWN on p062, so it is served rather than dropped — a component
    that vanished would make the table disagree with the drawing while the total
    quietly stopped mentioning sewer. But it is **excluded from the band**,
    because widening the range by a quantity nobody derived is not the doubt the
    product actually has.
    """
    unruled = projection.component(
        name="Sewer usage",
        service="sewer",
        basis=projection.BASIS_WINTER_AVERAGE,
        rate=D("0.0228"),
        unit="gal",
    )
    components = [
        _base("Water base", "water", WATER_BASE),
        _usage("Water usage", "water", D("4200"), D("0.0142")),
        unruled,
    ]
    assert unruled.quantity is None
    assert unruled.projected is None
    assert unruled.absence == "winter_average_basis_is_not_ruled"
    # It IS a usage-driven basis — so the exclusion is because it did not
    # project, not because the basis was miscategorised. Both halves matter.
    assert unruled.is_usage is True
    # The band is 15% of the water usage ALONE.
    assert projection.band_for(components) == D("8.9460")  # 0.15 x 59.64

    view = projection.projection(components=components, days_elapsed=14, days_in_period=30)
    codes = {problem["code"] for problem in view["problems"]}
    assert "winter_average_basis_is_not_ruled" in codes
    assert view["problems"][0]["oq_ref"] == "OQ-REP-12769"


def test_the_straight_line_is_p062s_own_arithmetic():
    """*"Projected from 14 days"* — 1,960 gal over 14 of 30 days → **4,200 gal**.

    That is the quantity p062 draws on its water usage row, so the drawing's own
    two figures and its third agree, which is the only figure on this page that
    can be checked against itself.
    """
    assert projection.straight_line(D("1960"), 14, 30) == D("4200.000000")
    # Nothing consumed yet is not a projection of nothing.
    assert projection.straight_line(D("1960"), 0, 30) is None
    assert projection.straight_line(None, 14, 30) is None


def test_every_quantity_row_carries_its_unit():
    """CLAUDE.md hard rule 3, and p062's own note about why UNIT is a column:

    *"Every quantity carries its unit, in its own column — hard rule 3, and the
    reason there is no Total usage tile on a multi-service account."*
    """
    components = [
        _base("Water base", "water", WATER_BASE),
        _usage("Water usage", "water", D("4200"), D("0.0142")),
    ]
    for found in components:
        if found.quantity is not None:
            assert found.unit, f"{found.component} served a quantity with no unit"


def test_the_tile_and_the_total_are_one_derivation():
    """p062 draws `$188.00` in the tile over a `188.10` total — the DRAWING
    rounding for a tile, not two figures (B14 rule 37).

    The read serves one number, so a screen cannot show a tile that disagrees
    with the column beneath it.
    """
    components = [
        _base("Water base", "water", WATER_BASE),
        _usage("Water usage", "water", D("4200"), D("0.0142")),
        _base("Sewer base", "sewer", SEWER_BASE),
        _usage("Sewer usage", "sewer", D("3880"), D("0.0228")),
    ]
    view = projection.projection(components=components, days_elapsed=14, days_in_period=30)
    assert view["totals"]["projected_bill"] == projection.projected_total(components)
    assert view["totals"]["projected_bill"] == STORED_TOTAL
    # ⚠ **AND IT IS THE DRAWN FIGURE AT DISPLAY WIDTH**, which is the check that
    # the engine and the drawing agree rather than merely being close: p062's
    # `188.10` is `188.1040` displayed at two places (hard rule 2).
    assert view["totals"]["projected_bill"].quantize(D("0.01")) == DRAWN_TOTAL
    assert view["totals"]["projected_band"] == RULED_BAND
    # The band is NOT additive — it is derived from the usage part.
    assert view["additivity"]["projected_band"] == "non"


def test_the_band_fraction_is_declared_once():
    """Hard-won law 5 in miniature: one source for the ruled figure.

    A second `0.15` typed into a viewer or a screen is how a ruled percentage
    drifts, and the drift would be invisible — 15% and 12% both look like
    plausible ranges.
    """
    assert projection.PROJECTION_BAND == D("0.150000")
    # Stored at hard rule 2's six places for a percentage.
    assert projection.PROJECTION_BAND.as_tuple().exponent == -6
