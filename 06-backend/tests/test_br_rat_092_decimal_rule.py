# ── Trace ──────────────────────────────────────────────
# Rules:    BR-RAT-092 (PO 2026-08-20: "all finance field need same decimal
#           rule") · OQ-286 CLOSED (PO: "for perctnage you can have 6 decimal
#           places") · BR-RAT-089 · CR-013 part 1 (rates keep six) · B4 ❄️
# ───────────────────────────────────────────────────────
"""The decimal rule, asserted where it is declared rather than where it is used.

`decimal_places` appears on 56 columns and the RULE that decides it appeared
nowhere — so the number was correct 56 times by coincidence and could be wrong
the 57th time with nothing to notice. These assert the declaration itself.
"""

from decimal import Decimal

from apps.rating.models import ChargeCodeAmount
from core import money_fields as mf


def _places(model, field: str) -> int:
    return model._meta.get_field(field).decimal_places


class TestTheThreeKinds:
    def test_an_amount_is_four_places(self):
        """The PO's reason, recorded: utilities type at most two places, so four
        is headroom for anything derived and six was never earning its extra two."""
        assert mf.AMOUNT_PLACES == 4
        assert mf.money_field().decimal_places == 4

    def test_a_percent_is_SIX_and_that_is_the_whole_of_OQ_286(self):
        """A percent stored as a FRACTION needs two more places than the percent
        it expresses. CR-013 part 4 wants a tax rate to four decimals of PERCENT —
        6.2500% — which is 0.062500 as a fraction. At four places that becomes
        0.0625: two decimals of percent, lost with no error raised anywhere."""
        assert mf.PERCENT_PLACES == 6
        assert Decimal("0.062500").as_tuple().exponent == -6

    def test_a_rate_is_six_because_its_precision_COMPOUNDS(self):
        """A rate is multiplied by a quantity before it becomes money, so
        truncating it moves the bill — where truncating an amount only moves
        itself. CR-013 part 1 restates frozen B4 for exactly these."""
        assert mf.RATE_PLACES == 6


def test_the_quantum_agrees_with_the_column_it_rounds_for():
    """The failure this prevents: someone writes Decimal("0.0001") at a call site,
    the column later changes, and the two disagree silently — a rounded value that
    the column then rounds AGAIN, differently."""
    assert mf.AMOUNT_QUANTUM == Decimal("0.0001")
    assert mf.PERCENT_QUANTUM == Decimal("0.000001")
    assert -mf.AMOUNT_QUANTUM.as_tuple().exponent == mf.AMOUNT_PLACES


def test_charge_code_amounts_is_the_first_adopter():
    """Chosen because the table is EMPTY, so narrowing costs nothing and proves
    the path before the other 55 columns follow. If this ever reads 6 again,
    someone re-typed the number instead of taking the rule."""
    assert _places(ChargeCodeAmount, "amount") == mf.AMOUNT_PLACES == 4


def test_narrowing_loses_nothing_the_product_actually_stores():
    """Checked before the ruling was recorded and asserted here so it stays true:
    no figure in the fixture and no expected value in the golden set carries more
    than four decimals, so every number the product holds survives the narrowing
    unchanged."""
    from core import sample_fixture as fixture

    for _from, _reason, tiers in fixture.WATER_VERSION_HISTORY:
        for price in tiers:
            assert -Decimal(price).as_tuple().exponent <= mf.AMOUNT_PLACES, price
    assert -Decimal(fixture.WATER_BASE).as_tuple().exponent <= mf.AMOUNT_PLACES
