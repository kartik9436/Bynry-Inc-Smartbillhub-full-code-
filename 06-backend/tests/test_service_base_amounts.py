# ── Trace ──────────────────────────────────────────────
# Delegation: PO 2026-09-07 — *"you can research in amrket at Municiapl utility
#          in north amrica and put it there"*, in answer to being asked for one
#          monthly base figure per service. Every figure asserted below is a
#          LANE JUDGMENT under that delegation; the PO has seen NONE of them.
#          ⚠ EXCEPT SEWER: `BASE-S` $9.00 is CONFIRMED 2026-10-01 (PO: "Yes" to
#          *"Is $9.00 a month right for the demo sewer base?"*).
# Rules:   BR-RAT-080 · BR-RAT-088 (the code and `plan_services.base_charge`
#          must agree to the cent or the bill is REFUSED) · CR-013 part 1 /
#          DEF-277 (a stored `"0"` is a PRICE, a blank is a REFUSAL) ·
#          CR-013 part 2 (a code states a FLAT amount OR a per-size table,
#          NEVER both — the bill stops on billing day when it finds both)
# ───────────────────────────────────────────────────────
"""THE SEVEN RESEARCHED BASE CHARGES, AND THE TWO WAYS THEY CAN GO WRONG.

⚠ **THIS FILE ASSERTS FIGURES NO HUMAN HAS RATIFIED, ON PURPOSE.** CLAUDE.md's
sign-off rule says *"a test asserts the ratified figure so drift goes RED"*.
These are not ratified — they are a lane's reading of published municipal rate
schedules under a delegation — so what the assertions buy is different and
worth naming: they make sure the figure a reader sees in the decision log, the
review-ledger row and the seeded bill is ONE figure, and that changing it is a
deliberate act that shows up in a diff rather than a silent drift. When the PO
corrects a row, this file moves in the same commit.

⚠ **AND THE SECOND HALF IS THE ONE THAT STOPS A BILL.** `CR-013` part 2: a
charge code may state a FLAT AMOUNT or a PER-SIZE TABLE and never both, and
`resolve_charge_codes` refuses the BILL — not the figure, the bill — when it
finds both. Raising a base from `$0.00` does not arm that trap by itself:
`base_size_amounts.size_amounts()` returns `[]` for every service outside
`LADDERED_SERVICES`, so the seeder writes a flat amount. **What WOULD arm it is
somebody adding one of these seven to `LADDERED_SERVICES` later**, because the
anchor is no longer zero and the ladder would start producing rows beside the
scalar. `test_no_researched_service_is_laddered` is that tripwire, and it names
what to do instead.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.rating import base_size_amounts, sample_data, service_base_amounts
from apps.tenancy import service_size_classes
from core import sample_fixture as fixture

#: The figures as researched on 2026-09-07, service → monthly base.
#: ⚠ Restated here rather than imported so that a change to the module is a
#: change to TWO files and shows up as a failing test rather than as a silent
#: agreement with itself.
EXPECTED: dict[str, str] = {
    "sewer": "9.0000",
    "storm_water": "2.0000",
    "broadband": "30.0000",
    "battery": "5.0000",
    "fire": "0.0000",
    "thermal_heat": "20.0000",
    "solar": "0.0000",
}


@pytest.mark.parametrize(("service", "amount"), sorted(EXPECTED.items()))
def test_each_researched_base_is_the_figure_the_record_states(service, amount):
    """The seeded figure and the recorded figure are one figure."""
    assert service_base_amounts.base_for(service, "UNSET") == amount


def test_every_researched_figure_carries_its_utility_and_year():
    """A figure with no source is a figure somebody invented.

    CLAUDE.md: *AI implements signed law, never invents it.* A delegation to
    research the market is not a licence to make numbers up, so the source
    travels IN the datum and this case is what keeps it there.
    """
    for service in EXPECTED:
        source = service_base_amounts.source_for(service)
        assert source and len(source) > 60, service


def test_fire_is_a_deliberate_zero_because_the_diameter_charge_already_exists():
    """$0.00 for fire, for TWO independent reasons — see the module's own note.

    **(1)** Every municipal private-fire-service schedule found prices ONE
    monthly charge by pipe DIAMETER and prints no customer charge beside it,
    and `service_size_classes.FIRE_DEFAULT_PRICES` is exactly that schedule —
    so a flat base would charge the same connection twice.

    **(2)** ⚠ **AND IT WOULD MOVE A SIGNED FIGURE ON A REAL CUSTOMER.** The PO
    signed the going-live customer's warehouse at `$60.00` a month on
    2026-09-03. `tests/test_cr063_c3_fire_priced.py` asserts that figure, a 2"
    line at `$12.00` and a mixed property at `$84.00`, and **all three would go
    red on any non-zero fire base** — which is the check doing its job, not an
    obstacle. A collision with a signed figure goes to the PO with its
    supersession stated (CLAUDE.md hard-won law 13); it is not a lane's to
    absorb, so it is in the report and the decision log instead.
    """
    assert service_base_amounts.base_for("fire", "UNSET") == "0.0000"
    # The PO-signed size prices are untouched and are what a fire line pays.
    assert service_size_classes.FIRE_DEFAULT_PRICES["FL-2"] == Decimal("12.0000")
    assert service_size_classes.FIRE_DEFAULT_PRICES["FL-6"] == Decimal("60.0000")
    assert service_size_classes.fire_charge({"FL-6": 1, "FL-2": 2}) == Decimal("84.00")


def test_solar_is_a_deliberate_zero_and_not_a_gap():
    """$0.00 is the FINDING for solar — see the module docstring's reasoning.

    Most North American municipal utilities levy nothing monthly for a
    customer-owned rooftop array; where a charge exists it is PER kW, which
    this product already expresses as solar's `$14.00`/kW capacity price. So
    the zero is stated rather than omitted — `CR-013` part 1 / `DEF-277`: a
    blank base means *this size is not served* and STOPS the bill, a stored
    zero prints `$0.00`.
    """
    assert service_base_amounts.base_for("solar", "UNSET") == "0.0000"
    assert Decimal(service_base_amounts.base_for("solar", "0")) == Decimal("0")
    assert "solar" in service_base_amounts.RESEARCHED_BASES


def test_the_signed_three_are_not_touched_and_cannot_be():
    """Water, electric and gas are signed in the billing workbook `[W] §1`.

    A row for one of them in the researched map would silently overwrite signed
    law on every seeded tenant with the suite and every gate green — the shape
    of `DEF-CUS-3653`, where an absence was invisible to every check the repo
    has. `_validate()` refuses it at IMPORT, which is why this case can only
    assert the state rather than provoke the failure.
    """
    for signed in ("water", "electric", "gas"):
        assert signed not in service_base_amounts.RESEARCHED_BASES
    assert Decimal(fixture.WATER_BASE) == Decimal("8.00")
    assert Decimal(fixture.ELECTRIC_BASE) == Decimal("12.00")
    assert Decimal(fixture.GAS_BASE) == Decimal("6.00")


def test_trash_stays_at_the_zero_the_po_ruled():
    """`OQ-317` option A retired the trash base — trash bills per CART.

    A researched default for trash would reverse a decision the Product Owner
    made, which is the one thing a delegation to research the market does NOT
    authorise. `BR-RAT-090`: `$15.00` a cart, so three carts is `$45.00`.
    """
    assert "trash" not in service_base_amounts.RESEARCHED_BASES
    assert Decimal(fixture.TRASH_BASE) == Decimal("0")


def test_no_researched_service_is_laddered():
    """⚠ **CR-013 part 2 — A CODE STATES A FLAT AMOUNT OR A TABLE, NEVER BOTH.**

    `resolve_charge_codes` refuses the BILL when it finds both, so this is a
    stopped bill on billing day and not a wrong figure. While every anchor here
    was `$0.00`, `size_amounts()` returned `[]` for two independent reasons and
    the trap was double-locked. **Six of these seven anchors are non-zero now**,
    so only one lock is left: none of them is in `LADDERED_SERVICES`.

    If a size ladder is wanted for one of these services, the answer is NOT to
    add it to `LADDERED_SERVICES` — it also needs a `CAPACITY_RATIOS` entry
    giving each size's RATED CAPACITY relative to the smallest, or
    `base_size_amounts.multiplier` raises `LadderIncomplete` and every
    connection of an unpriced size stops billing (PO ruling 2026-08-28: an
    unpriced size is REFUSED and never substituted).

    And for five of the seven the honest answer is that the size axis is
    ALREADY priced elsewhere — fire by diameter, battery and solar per kW,
    storm water per ERU, broadband per Mbps — so a base ladder would charge the
    same capacity twice.
    """
    for service in EXPECTED:
        assert not base_size_amounts.has_ladder(service), service
        assert base_size_amounts.size_amounts(service, EXPECTED[service]) == []


def test_sewer_has_no_size_classes_so_its_base_can_only_be_flat():
    """Not a choice — `service_size_classes` rules sewer to have NONE.

    An empty tuple there means *ruled to have none* (as against a raise, which
    means *nobody has said*), so sewer's `$9.00` is flat by law rather than by
    preference.
    """
    assert service_size_classes.size_classes_for_service("sewer") == ()


def test_the_plan_and_the_charge_code_read_one_expression():
    """`DEF-455` / `DEF-2823` — two sources for one figure drift INVISIBLY.

    `gather._base_charge_for` REFUSES a bill by name when the plan and the
    charge code state different bases, so a drift here is a stopped bill on
    every account of that service. `_backbone_base_pair` and the two
    `service_base_amounts.base_for` calls in `capacity_base_charge_codes` /
    `_plan_payloads` exist so the two cannot differ; this case asserts the
    property rather than the plumbing.
    """
    for service, amount in EXPECTED.items():
        if service in fixture.BACKBONE_BASE:
            res, com = sample_data._backbone_base_pair(service)
            assert res == amount and com == amount, service
        else:
            assert service_base_amounts.base_for(service, fixture.CAPACITY_BASE) == amount, service


def test_every_capacity_service_that_is_seeded_has_a_researched_row():
    """A service the seed prices and this file forgets keeps a `$0.00` base.

    That is lawful and silent, which is the combination this repo keeps paying
    for. `fire` joining `CAPACITY_ESTATE_SERVICES` without joining
    `CAPACITY_BASE_CODE` took down fourteen of seventeen seeding blocks
    (`DEF-3087`); the failure here is quieter — the twelfth service would simply
    bill nothing for its connection and nobody would see it.
    """
    missing = [
        code
        for code in fixture.CAPACITY_ESTATE_SERVICES
        if code not in service_base_amounts.RESEARCHED_BASES
    ]
    assert missing == [], (
        f"{missing} are seeded capacity services with no row in "
        "apps/rating/service_base_amounts.RESEARCHED_BASES, so each bills "
        "$0.00 for having a connection. Add a researched municipal figure WITH "
        "ITS UTILITY AND YEAR, or add the service to that module's RULED_ZERO "
        "with the ruling that put it there."
    )
