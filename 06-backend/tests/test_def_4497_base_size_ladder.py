# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-6440 — `charge_code_amounts` holds ZERO rows on every seeded
#          tenant, so a base charge does not vary by connection size anywhere
#          and CHG-02 step 2 shows an empty table on a demo utility.
# Rules:   BR-RAT-088 (the CHARGE CODE owns the base) · BR-RAT-108 (its own
#          published water ladder: 5/8" $8.00 · 1" $14.00 · 2" $34.00) ·
#          BR-RAT-690 (the write path) · BR-RAT-089/092 (store 4, display 2) ·
#          DEF-455 (the code and the plan must agree to the cent) · DEF-277
#          (a blank base is NOT a zero)
# Tests:   this file
# ───────────────────────────────────────────────────────
"""DEF-6440 — THE SEEDED BASE CHARGE RISES WITH THE CONNECTION SIZE.

WHAT WAS WRONG, WITH THE FIGURES
---------------------------------
`BR-RAT-690` built the writer for `charge_code_amounts` on 2026-08-28 and
`BR-RAT-088` had published the example it exists for eight days before that —
a water base of **$8.00** at 5/8" and **$34.00** at 2" on ONE charge code.
**Neither reached the seed.** Counted on the live demo database on 2026-09-07:
`charge_code_amounts` held **0 rows**, on every tenant, so every connection of
every size was billed the single scalar in `charges.amount` and a utility
opening the per-size table saw nothing at all.

TC1 is the one that would have caught it: it asserts the SEED writes the table,
not that the table can be written.

THE TWO THINGS THAT MUST NOT MOVE
----------------------------------
* **The smallest size keeps the code's own figure** (TC2). The ladder is
  anchored on it, so every seeded bill is byte for byte what it was.
* **The code and `plan_services.base_charge` still agree to the cent** (TC3).
  `apps/billing/gather._base_charge_for` REFUSES a bill by name when they
  disagree — `BR-RAT-088`'s *"migration artefact"* clause — so an anchor that
  did not reproduce the plan's figure would STOP every seeded account rather
  than merely mis-bill it.
"""

from decimal import Decimal

import pytest

from apps.rating import base_size_amounts, models, sample_data, selectors
from apps.tenancy import service_size_classes

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx
from apps.rating.charge_prices import flat_amount as _flat  # CR-156-BRC10: the amount is a dated row

pytestmark = pytest.mark.django_db


def _configure_all_sizes(tenant, service_code):
    """The tenant's own `service_size_classes` rows for one service.

    Written through tenancy's MODEL: rating may not write another module's
    tables (B1/B8), and the point is that rating READS this list.
    """
    from apps.tenancy import models as tenancy_models

    for code, name in service_size_classes.size_classes_for_service(service_code):
        tenancy_models.MeterSizeClass.objects.update_or_create(
            tenant=tenant,
            code=code,
            defaults={"name": name, "active": True, "is_system": True},
        )


def _seeded(env, service_code="water", charge_code="BASE-W"):
    _configure_all_sizes(env.tenant, service_code)
    with tenant_ctx(env.tenant):
        sample_data.seed_sample_base_charge_codes(env.admin)
        charge = models.Charge.objects.get(code=charge_code)
        rows = {
            row.size_class: row.amount
            for row in models.ChargeCodeAmount.objects.filter(charge_id=charge.id)
        }
    return charge, rows


# ── TC1 — the defect itself: the SEED writes the table ──────────────────────
def test_tc1__the_seed_writes_a_per_size_base_for_water(env):
    """`charge_code_amounts` is no longer empty on a seeded tenant.

    ⚠ This asserts the SEED's output, not the writer's. `BR-RAT-690` already
    proves a utility CAN state a per-size base; what was missing for ten days
    is that the shipped fixture never did, so nobody meeting the demo tenant
    ever saw the size axis carry a price.
    """
    _charge, rows = _seeded(env)
    assert rows, "the seed wrote no charge_code_amounts rows at all"
    # All nine ratified water sizes are priced. An ABSENT size REFUSES a bill
    # (PO ruling 2026-08-28 — an unpriced size is never substituted), so a
    # partial ladder would stop billing every connection it missed.
    assert set(rows) == {
        code for code, _name in service_size_classes.size_classes_for_service("water")
    }


# ── TC2 — no seeded bill moves ──────────────────────────────────────────────
def test_tc2__the_smallest_size_keeps_the_figure_the_code_charged_before(env):
    """The 5/8" rung IS `$8.00` — the flat amount `BASE-W` states today.

    This is what makes the change safe to ship: every seeded meter on the demo
    tenant is a `W-58`, so the base each of them resolves is unchanged.
    """
    _charge, rows = _seeded(env)
    assert rows["W-58"] == Decimal("8.0000")


# ── TC3 — the refusal this change could have caused, and does not ───────────
def test_tc3__the_code_and_the_plan_still_agree_to_the_cent(env):
    """`DEF-455`'s requirement, which `gather._base_charge_for` enforces.

    A base on the charge code that DISAGREES with `plan_services.base_charge`
    does not mis-bill — it REFUSES the account by name. The plan still states
    the flat `$8.00`, so the 5/8" rung must be `$8.00` exactly.
    """
    _charge, rows = _seeded(env)
    from core import sample_fixture as fixture

    assert rows["W-58"] == Decimal(fixture.WATER_BASE).quantize(Decimal("0.0001"))


# ── TC4 — the register's own published ladder ───────────────────────────────
def test_tc4__the_three_figures_br_rat_108_publishes(env):
    """`BR-RAT-108`: *"`BASE-W` residential can state 5/8" $8.00 · 1" $14.00 ·
    2" $34.00"*. All three, from the seed, without anybody typing them."""
    _charge, rows = _seeded(env)
    assert rows["W-58"] == Decimal("8.0000")
    assert rows["W-1"] == Decimal("14.0000")
    assert rows["W-2"] == Decimal("34.0000")


# ── TC5 — one basis, or the bill refuses ────────────────────────────────────
def test_tc5__a_laddered_code_states_no_flat_amount(env):
    """CR-013 part 2: a code has ONE basis.

    `resolve_charge_codes` and `_validate_charge` both refuse a code stating
    BOTH a flat amount and a per-size table — the read half refuses on billing
    day. So the seed must clear the scalar when it writes the ladder, and a
    regression here would break every bill rather than one figure.
    """
    charge, rows = _seeded(env)
    assert rows
    assert _flat(charge) is None


# ── TC6 — the live read path answers per size ───────────────────────────────
def test_tc6__the_bill_path_resolves_a_different_base_for_a_2_inch(env):
    """The whole point, through the function billing actually calls.

    `$8.00` for a 5/8" and `$34.00` for a 2" — **`$26.00` a month per 2"
    connection** that no tenant could express in the seed before.
    """
    _seeded(env)
    with tenant_ctx(env.tenant):
        small = selectors.base_charge_from_charge_code(
            "water", customer_class="residential", size_class="W-58", named_code="BASE-W"  # DEF-RAT-9832
        )
        large = selectors.base_charge_from_charge_code(
            "water", customer_class="residential", size_class="W-2", named_code="BASE-W"  # DEF-RAT-9832
        )
    assert small["refusal"] is None and large["refusal"] is None
    assert Decimal(str(small["amount"])) == Decimal("8.0000")
    assert Decimal(str(large["amount"])) == Decimal("34.0000")
    assert Decimal(str(large["amount"])) - Decimal(str(small["amount"])) == Decimal("26.0000")


# ── TC7 — the commercial code gets the SAME ladder at its OWN price level ───
def test_tc7__one_ladder_two_price_levels(env):
    """`BR-RAT-108`'s shape: one service, two amounts, separated by CLASS.

    `BASE-W-COM` charges `$15.00` at 5/8", so its 2" rung is `15.00 x 4.25`.
    The ladder is stated once; only the anchor differs.
    """
    _charge, rows = _seeded(env, charge_code="BASE-W-COM")
    assert rows["W-58"] == Decimal("15.0000")
    assert rows["W-2"] == Decimal("63.7500")


# ── TC8 — a ratified size with no rung REFUSES rather than billing wrong ────
def test_tc8__a_size_class_with_no_rung_is_named_not_guessed():
    """`DEF-3087`'s shape one module over: two lists that grow independently.

    A size class ratified upstream with no multiplier here would otherwise reach
    a bill as a missing row, and a missing row REFUSES every connection of that
    size. The refusal names the file and what to add.
    """
    with pytest.raises(base_size_amounts.LadderIncomplete) as caught:
        base_size_amounts.multiplier("water", "W-99")
    assert "base_size_amounts.CAPACITY_RATIOS" in str(caught.value)


# ── TC9 — the ladder covers every ratified size of every laddered service ───
def test_tc9__no_laddered_service_has_an_unpriced_ratified_size():
    """The guard TC8 describes, run over the real vocabulary.

    This is the case that actually fires when somebody ratifies a new size
    class: it goes RED here rather than refusing a customer's bill.
    """
    for service in base_size_amounts.LADDERED_SERVICES:
        for code, _name in service_size_classes.size_classes_for_service(service):
            assert base_size_amounts.multiplier(service, code) > 0


# ── TC10 — a service with no signed base gets NO table, not a table of zeros ─
def test_tc10__an_unsigned_base_is_left_flat_rather_than_laddered():
    """Trash's base is `$0.00` by PO ruling (`OQ-317` option A — it bills per
    CART). Multiplying zero by a ladder is still zero, and a table of zeros is
    the flattest possible table. The seed writes none and leaves the flat
    figure, which is what every tenant has today."""
    assert base_size_amounts.size_amounts("trash", "0") == []
    assert base_size_amounts.size_amounts("water", "0") == []
    assert base_size_amounts.size_amounts("solar", "6.00") == []


# ── TC11 — money is stored to four places ───────────────────────────────────
def test_tc11__amounts_are_stored_to_four_decimals(env):
    """CLAUDE.md hard rule 2, on the column rather than on a served string."""
    from core.money_fields import AMOUNT_PLACES

    _charge, rows = _seeded(env)
    for amount in rows.values():
        assert amount.as_tuple().exponent == -AMOUNT_PLACES


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-6440
# generated: 2026-09-07 by the rating-pricing lane (claude)
# gates: proved RED before the seeder was wired — TC1 failed with
#        `the seed wrote no charge_code_amounts rows at all`.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
