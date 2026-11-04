# ── Trace ──────────────────────────────────────────────
# Change:   CR-091-BRC01 — *"when we create discount - we will ahve to take 1 or
#           more utility services - currently it is not available. also we will
#           ahve to dsplay in detail view and also allow to enit it duing edit
#           process"* (the PO, working chat session, 2026-09-10). Built inside
#           CR-087 by the PO's ruling of the same day.
# Rules:    PO ruling 2026-09-10 (decision log §7, THE SCOPE GAINS A PAIR, IT
#           DOES NOT WIDEN) · BR-RAT-024 (a service must be in the platform
#           catalog AND enabled for this tenant) · BR-RAT-963 (an empty specific
#           list is an unfinished form) · CLAUDE.md 🔒 rating math
# ───────────────────────────────────────────────────────
"""`CR-091-BRC01` — a discount names ONE OR MORE services.

⚠ **EVERY CASE HERE ASSERTS THE MONEY, NOT THE FLAG.** That is this repo's own
instruction for a control whose stored value reads the opposite way from what a
clerk picks (decision log, 2026-09-10, on the outside-city surcharge: *"So the
guard asserts MONEY, never the flag: sewer stays `$8.00` and water rises 15%"*).
A membership test that quietly selected the wrong lines would pass any assertion
about `applies_to_services` and produce a wrong bill, which is the failure the
whole rule exists to prevent.

⚠ **AND THE FIRST CASE IS THE ONE THAT MATTERS MOST: A STORED `one_service` ROW
PRICES TO THE SAME FIGURE IT ALWAYS DID.** The PO's ruling turns on it — *"The
existing `one_service` scope is NOT widened — every discount already saved keeps
the meaning it had, and no migration has to reinterpret stored rows"* — and the
change it protects is an equality becoming a membership test, which is exactly
the kind of edit that looks safe and is not.
"""

from decimal import Decimal

import pytest

from apps.rating import discount_pricing
from apps.rating import discounts as discount_models

pytestmark = pytest.mark.django_db

#: Design §A4 S1's own lines, so the figures below are the fixture's and not
#: this file's invention: electric 18.50 + 55.00 + 47.60 = **121.10**,
#: water 12.00 + 12.80 + 28.80 + 7.20 = **60.80**, sewer **8.00**.
#: Subtotal **189.90**.
LINES = (
    discount_pricing.BillLine("electric", "base", Decimal("18.50"), "BASE-E"),
    discount_pricing.BillLine("electric", "usage", Decimal("55.00"), "USAGE-E"),
    discount_pricing.BillLine("electric", "usage", Decimal("47.60"), "USAGE-E"),
    discount_pricing.BillLine("water", "base", Decimal("12.00"), "BASE-W"),
    discount_pricing.BillLine("water", "usage", Decimal("12.80"), "USAGE-W"),
    discount_pricing.BillLine("water", "usage", Decimal("28.80"), "USAGE-W"),
    discount_pricing.BillLine("water", "usage", Decimal("7.20"), "USAGE-W"),
    discount_pricing.BillLine("sewer", "base", Decimal("8.00"), "BASE-S"),
)

ELECTRIC = Decimal("121.10")
WATER = Decimal("60.80")
SEWER = Decimal("8.00")
SUBTOTAL = Decimal("189.90")


def _ten_percent(**kwargs) -> discount_pricing.DiscountRule:
    return discount_pricing.DiscountRule(
        code="TEST",
        discount_type=discount_models.DISCOUNT_PERCENTAGE,
        value=Decimal("10"),
        currency="USD",
        proof_before_first_reduction=False,
        **kwargs,
    )


def _applied(rule) -> Decimal:
    outcome = discount_pricing.price_discounts(LINES, (rule,))
    assert outcome.denied == (), outcome.denied
    return outcome.total_reduction()


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE STORED SINGULAR IS UNTOUCHED
# ══════════════════════════════════════════════════════════════════════════


def test_a_stored_one_service_row_prices_to_exactly_what_it_always_did():
    """⚠ **THE RULING'S OWN REQUIREMENT, IN MONEY.** 10% of water's `$60.80` is
    `$6.08`, and it was `$6.08` before `_scoped_base`'s equality became a
    membership test. Nothing about sewer or electric is reachable from this
    row."""
    assert _applied(
        _ten_percent(
            applies_to=discount_models.SCOPE_ONE_SERVICE,
            applies_to_service="water",
        )
    ) == Decimal("6.08")


def test_the_singular_does_not_read_the_plural_column_even_if_a_row_carries_both():
    """A `one_service` row that somehow also carried a list must price from the
    SINGULAR. Without this, the membership test would be a silent widening of
    every stored row the moment anything wrote the new column."""
    assert _applied(
        _ten_percent(
            applies_to=discount_models.SCOPE_ONE_SERVICE,
            applies_to_service="water",
            applies_to_services=("water", "electric", "sewer"),
        )
    ) == Decimal("6.08")


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE PLURAL — WHAT THE PO ASKED FOR
# ══════════════════════════════════════════════════════════════════════════


def test_two_services_reduce_those_two_and_nothing_else():
    """10% of water + electric = 10% of `$181.90` = **`$18.19`**, and sewer's
    `$8.00` is untouched. The whole of `CR-091`, in one figure."""
    assert _applied(
        _ten_percent(
            applies_to=discount_models.SCOPE_SPECIFIC_SERVICES,
            applies_to_services=("water", "electric"),
        )
    ) == Decimal("18.19")
    assert ELECTRIC + WATER == Decimal("181.90")


def test_one_service_in_the_plural_list_matches_the_singular_scope_to_the_cent():
    """A list of one is an equality. If these two ever disagree, one of the two
    scopes is selecting the wrong lines."""
    plural = _applied(
        _ten_percent(
            applies_to=discount_models.SCOPE_SPECIFIC_SERVICES,
            applies_to_services=("water",),
        )
    )
    singular = _applied(
        _ten_percent(
            applies_to=discount_models.SCOPE_ONE_SERVICE, applies_to_service="water"
        )
    )
    assert plural == singular == Decimal("6.08")


def test_a_service_the_bill_does_not_carry_adds_nothing_and_refuses_nothing():
    """Naming trash on a bill with no trash line reduces trash by nothing. The
    other two named services still price, so an unsold service does not take the
    whole discount down with it."""
    assert _applied(
        _ten_percent(
            applies_to=discount_models.SCOPE_SPECIFIC_SERVICES,
            applies_to_services=("water", "trash"),
        )
    ) == Decimal("6.08")


def test_every_service_named_one_by_one_is_the_whole_undiscounted_subtotal():
    """Naming all three is 10% of `$189.90` = **`$18.99`** — the same figure
    `all_services` gives, which is what makes the pair coherent."""
    named = _applied(
        _ten_percent(
            applies_to=discount_models.SCOPE_SPECIFIC_SERVICES,
            applies_to_services=("water", "electric", "sewer"),
        )
    )
    every = _applied(_ten_percent(applies_to=discount_models.SCOPE_ALL_SERVICES))
    assert named == every == Decimal("18.99")
    assert SUBTOTAL == ELECTRIC + WATER + SEWER


# ══════════════════════════════════════════════════════════════════════════
# 3 · `all_services` IS NOT A SPELLING OF `whole_bill`, AND THE DIFFERENCE IS
#     ONLY VISIBLE WITH TWO DISCOUNTS STACKED
# ══════════════════════════════════════════════════════════════════════════


def test_all_services_and_whole_bill_agree_on_a_bill_with_ONE_discount():
    """Which is why the distinction is safe to add: the ordinary case is
    identical."""
    assert _applied(_ten_percent(applies_to=discount_models.SCOPE_ALL_SERVICES)) == _applied(
        _ten_percent(applies_to=discount_models.SCOPE_WHOLE_BILL)
    )


def test_and_they_DIFFER_when_a_second_discount_runs_first():
    """⚠ **THE ARITHMETIC THAT ALREADY EXISTED, GIVEN A NAME A CLERK CAN
    CHOOSE.** `whole_bill` is the one scope the engine runs against the REDUCING
    subtotal; every other scope takes the UNDISCOUNTED sum of the lines it
    selects (`_scoped_base`'s own docstring). So after a `$10.00` fixed
    reduction has run:

      * `whole_bill` takes 10% of `$179.90` = **`$17.99`**
      * `all_services` takes 10% of `$189.90` = **`$18.99`**

    A one-cent-per-dollar difference on a real bill, and it is the choice
    precedence exists to make visible rather than a defect.
    """
    first = discount_pricing.DiscountRule(
        code="FIRST",
        discount_type=discount_models.DISCOUNT_FIXED_AMOUNT,
        value=Decimal("10"),
        currency="USD",
        applies_to=discount_models.SCOPE_WHOLE_BILL,
        proof_before_first_reduction=False,
        stacking_precedence=1,
    )
    second_whole = _ten_percent(
        applies_to=discount_models.SCOPE_WHOLE_BILL, stacking_precedence=2
    )
    second_all = _ten_percent(
        applies_to=discount_models.SCOPE_ALL_SERVICES, stacking_precedence=2
    )
    whole = discount_pricing.price_discounts(LINES, (first, second_whole))
    every = discount_pricing.price_discounts(LINES, (first, second_all))
    assert whole.total_reduction() == Decimal("10") + Decimal("17.99")
    assert every.total_reduction() == Decimal("10") + Decimal("18.99")
