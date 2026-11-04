# ── Trace ──────────────────────────────────────────────
# Story:    CR-043 finding 2 / DEF-968 — six decimal places of money and
#           percentage, at a clerk.   Screens: BIL-02 Charges tab
# Rules:    CLAUDE.md hard rule 2 (money 4 stored, percentages 6 stored, BOTH
#           DISPLAY 2) · BR-RAT-087 (the display half, PO's words) ·
#           BR-MET-144 (a QUANTITY: at most 2dp, trailing zeros trimmed) ·
#           BR-RAT-015 (sewer = % of water usage-charge dollars) ·
#           BR-RAT-026/032 (pure tiers)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""The numbers INSIDE a priced line's own sentence.

`invoice_lines.description` is the one place a figure reaches a person without
passing through a formatter, and it is a string, so no gate in this repo can
see it. The Product Owner could, on the live deployment at v2.61.1:

    "water usage tier 1 (0-5.000000 kgal)"
    "sewer usage — 40.000000% of water usage charges"

RED-FIRST RECORD (hard-won law 7) — against the tree before
`apps/rating/pricing/wording.py` was wired in, verbatim:

    AssertionError: assert 'water usage tier 1 (0-5 kgal)' == 'water usage tier
    1 (0-5.000000 kgal)'

TWO RULES, AND THE TEST ASSERTS THE DIFFERENCE BETWEEN THEM
------------------------------------------------------------
A percentage PADS to two (`40.00%`); a quantity TRIMS to none (`5`, never
`5.00`). Both produce a well-formed string, so a fix that reached for the wrong
formatter would look right everywhere except on the bill. `test_the_two_rules_
are_not_the_same_rule` is that assertion, written as a negative.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.metering import quantity_display
from apps.rating.pricing import wording
from apps.rating.pricing import contracts
from apps.rating.pricing.contracts import MeasuredUsage, ModelConfig, SubscriptionContext
from apps.rating.pricing.models import percent_of_service, tiered

USD = "USD"


def _subscription(service: str = "water") -> SubscriptionContext:
    return SubscriptionContext(service=service, currency=USD)


def _usage(quantity, unit):
    return MeasuredUsage(
        billed_quantity=quantity,
        unit=unit,
        raw_quantity=quantity,
        multiplier=Decimal("1"),
    )


def test_cr043_f2__a_tier_block_states_its_bounds_at_display_precision():
    """DEF-968. `0-5 kgal`, not `0-5.000000 kgal`."""
    config = ModelConfig(
        model="tiered",
        billed_unit="kgal",
        tiers=(
            contracts.TierSpec(upper=Decimal("5.000000"), unit_price=Decimal("4.000000")),
            contracts.TierSpec(upper=Decimal("15.000000"), unit_price=Decimal("6.500000")),
            contracts.TierSpec(upper=None, unit_price=Decimal("9.000000")),
        ),
    )
    lines = tiered.price(
        _subscription(),
        _usage(Decimal("20"), "kgal"),
        config,
    )
    said = [line.description for line in lines]
    assert said == [
        "water usage tier 1 (0-5 kgal)",
        "water usage tier 2 (5-15 kgal)",
        "water usage tier 3 (15+ kgal)",
    ]
    # NON-VACUOUS: the storage precision really is six places, so a test that
    # only checked "contains kgal" would pass over the defect.
    assert config.tiers[0].upper == Decimal("5.000000")
    for description in said:
        assert ".000000" not in description

    # ⚠ AND THE MONEY ON THE LINE IS UNTOUCHED. This change is a SENTENCE, not a
    # rounding site: the amounts stay exact Decimals at full precision and B4
    # finalizes them exactly once, later.
    assert [line.amount for line in lines] == [
        Decimal("20.000000"),  # 5 × 4.00
        Decimal("65.000000"),  # 10 × 6.50
        Decimal("45.000000"),  # 5 × 9.00
    ]


def test_cr043_f2__a_percent_of_service_line_states_its_rate_at_two_places():
    """DEF-968, the percentage half. `90.00%`, not `90.000000%` and not `90%`.

    ⚠ **THE SENTENCE'S LAST TWO WORDS MOVED WITH `CR-081` (2026-09-08) AND THE
    DEFECT THIS TEST GUARDS DID NOT.** It read *"sewer usage — 40.00% of water
    usage charges"* while sewer was a percentage of water's MONEY; it is now
    *"of water volume"*. `percent` is still `NUMERIC(18,6)`, an f-string still
    prints a Decimal at its storage scale, and `wording.percent_text` is still
    the one thing between that and a customer's bill.

    ⚠ **`unit_price` NO LONGER CARRIES THE FACTOR.** It used to be the rate the
    line was priced at — `0.4`, a fraction of somebody else's money. It is now
    sewer's OWN price per unit, and the factor lives only in the sentence and in
    the quantity. A test that still asserted `0.4` here would be asserting the
    old meaning of the column.
    """
    config = ModelConfig(
        model="percent_of_service",
        billed_unit=None,
        percent=Decimal("90.000000"),
        basis_service="water",
        # `CR-130-BRC07` — A PERCENTAGE OF WHAT, required from 2026-09-22. The
        # plugin refuses a None rather than assuming `'usage'`, so this fixture
        # states it: the sentence under test — *"of water volume"* — is the
        # USAGE basis's wording, and the charge basis says *"of water usage
        # charges"* instead.
        percent_basis="usage",
        basis_quantity=Decimal("8.000000"),
        basis_unit="kgal",
        unit_price=Decimal("5.000000"),
    )
    (line,) = percent_of_service.price(
        _subscription("sewer"),
        _usage(Decimal("0"), "kgal"),
        config,
    )
    assert line.description == "sewer usage — 90.00% of water volume"
    # The ARITHMETIC still uses the stored six-place value.
    assert line.quantity == Decimal("7.200000")  # 8.000000 × 0.9
    assert line.amount == Decimal("36.000000")  # 7.2 × 5.000000
    assert line.unit_price == Decimal("5.000000")


def test_cr043_f2__the_two_rules_are_not_the_same_rule():
    """A percentage PADS; a quantity TRIMS. Written as the negative, because a
    fix that reached for one formatter for both would pass every other test."""
    assert wording.percent_text(Decimal("40.000000")) == "40.00"
    assert wording.quantity_text(Decimal("40.000000")) == "40"
    assert wording.quantity_text(Decimal("5.000000")) != "5.00"
    assert wording.percent_text(Decimal("0.5")) == "0.50"
    # Half-up, B4's direction, on both.
    assert wording.quantity_text(Decimal("2.005")) == "2.01"
    assert wording.percent_text(Decimal("1.005")) == "1.01"


@pytest.mark.parametrize(
    "value",
    ["0", "5.000000", "8", "15.5", "26.240000", "3.7200", "2.005", "0.004", "1000.000000"],
)
def test_cr043_f2__the_quantity_rule_here_agrees_with_meterings_own(value):
    """THE DRIFT GUARD, and it is why the duplication is allowed.

    `apps/rating/pricing` is a pure module and may not import another app, so
    BR-MET-144 is implemented twice — here and in
    `apps/metering/quantity_display.py`, which is its canonical statement. A
    copy nobody checks is how two surfaces come to disagree (DEF-894's own
    lesson: six surfaces formatting independently is how three of them drift).

    So the copy is not trusted; it is COMPARED. Change either implementation and
    this goes red, which is the whole benefit of the coupling without the
    coupling itself.
    """
    assert wording.quantity_text(Decimal(value)) == quantity_display.quantity_text(Decimal(value))
