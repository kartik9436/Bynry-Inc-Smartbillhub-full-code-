# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — tiered pricing)
#           Screens: — (priced lines render in S31.2)
# Rules:    BR-RAT-002 (tier thresholds reset each bill, scale with the prorated
#           period) · BR-RAT-026 (PURE tiers — every unit bills through a tier,
#           no allowance) · BR-RAT-032 (tier contiguity) · BR-RAT-003 (round per
#           line, half-up, 2dp, at finalization ONLY)
# Golden:   GT-2 — B5 ❄️ FROZEN, finance-signed 2026-08-08 (05-golden-tests.md
#           lines 15-16). Every figure below is COPIED from those two lines.
# Tests:    this file (xfail until apps.rating.engine.price_period lands)
# Impacts:  06-backend/apps/billing/rating_seam.py · apps/rating/engine.py 🔒
# ───────────────────────────────────────────────────────
"""GT-2 - Tiers 0-2@3.00 / 2-5@4.50 / 5+@6.00 kgal, base $12, 3.72 kgal -> 25.74+tax (B5 GT-2, FROZEN 2026-08-08)

B5 GT-2 verbatim
----------------
  line 15: "Input: tiers 0-2 kgal @ $3.00, 2-5 @ $4.50, 5+ @ $6.00; base $12;
            usage 3.72 kgal."
  line 16: "Assumed: 2x3.00 + 1.72x4.50 = 6.00+7.74 = 13.74; +12 = 25.74; +tax."
            ... SUPERSEDED stamp: "both dependencies terminal: tier evaluation
            on post-multiplier consumption with thresholds reset each bill
            CONFIRMED (B4.4), pure tiers only per PO R5 -> BR-RAT-026; rounding
            CONFIRMED (B4.4)."

NOT FROZEN IN B5: the tax and the bill total. B5 stops at "+tax" — it names no
tax rate and no total for GT-2 — so this test asserts the pre-tax figures only
and asserts NOTHING about tax. Supplying a rate here would be inventing an
input; the tax rule itself is already proven by GT-1/GT-10/GT-11.
"""

from decimal import Decimal

import pytest

from apps.billing import rating_seam

from .conftest import FULL_PERIOD, TAXED_ACCOUNT

pytestmark = pytest.mark.golden

# ── INPUT (B5 GT-2 line 15) ─────────────────────────────────────────────────
TARIFF = rating_seam.TariffConfig(
    service="water",
    model="tiered",
    billed_unit="kgal",  # "kgal"
    base_charge=Decimal("12.00"),  # "base $12"
    tiers=(
        rating_seam.Tier(upper=Decimal("2"), unit_price=Decimal("3.00")),  # "0-2 kgal @ $3.00"
        rating_seam.Tier(upper=Decimal("5"), unit_price=Decimal("4.50")),  # "2-5 @ $4.50"
        rating_seam.Tier(upper=None, unit_price=Decimal("6.00")),  # "5+ @ $6.00"
    ),
)
CONSUMPTION = rating_seam.Quantity(amount=Decimal("3.72"), unit="kgal")  # "usage 3.72 kgal"

# ── EXPECTED (B5 GT-2 line 16) ──────────────────────────────────────────────
EXPECTED_USAGE = Decimal("13.74")  # "2x3.00 + 1.72x4.50 = 6.00+7.74 = 13.74"
EXPECTED_BASE = Decimal("12.00")  # "+12"
EXPECTED_TAXABLE_SUBTOTAL = Decimal("25.74")  # "= 25.74"

# B5's own decomposition of the usage charge, quoted so the tier split is a
# stated expectation and not an inference: block 1 consumes exactly 2 kgal at
# 3.00 (= 6.00) and block 2 takes the remaining 1.72 kgal at 4.50 (= 7.74).
# The top block (5+) is never reached at 3.72 kgal.
EXPECTED_TIER_1 = Decimal("6.00")  # "2x3.00 ... = 6.00"
EXPECTED_TIER_2 = Decimal("7.74")  # "1.72x4.50 ... 7.74"


def test_gt02_tiered_water():
    # B5 FROZEN 2026-08-08 - xfail flips to must-pass when the engine lands (W3).
    bill = rating_seam.price_period(
        tariff=TARIFF,
        consumption=CONSUMPTION,
        period=FULL_PERIOD,
        account=TAXED_ACCOUNT,
        # NOT FROZEN IN B5: GT-2 names no tax rate, so none is supplied.
        taxes=(),
    )

    usage_lines = bill.lines_of("usage")
    # The engine may emit one usage line or one per tier block; both shapes are
    # legitimate (B5 does not rule on line granularity), so the frozen total is
    # asserted first and the block split only when the engine reports blocks.
    assert sum((line.amount for line in usage_lines), Decimal("0")) == EXPECTED_USAGE
    assert {line.unit for line in usage_lines} == {"kgal"}  # hard rule 3
    assert all(line.taxable is True for line in usage_lines)  # B4.2

    if len(usage_lines) > 1:  # per-block lines: assert B5's own split
        assert [line.amount for line in usage_lines][:2] == [EXPECTED_TIER_1, EXPECTED_TIER_2]

    base = bill.sole_line("base")
    assert base.amount == EXPECTED_BASE
    assert base.taxable is True

    assert bill.taxable_subtotal == EXPECTED_TAXABLE_SUBTOTAL

    # NOT FROZEN IN B5: tax and total for GT-2 ("+tax", no rate, no figure).
    # Deliberately unasserted — see the module docstring.


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (sha1[:7] of 05-golden-tests.md + 04-money-math-rules.md
#         + EP-RAT-05-engine.md + 06-rating/02-business-rules.md, concatenated in that order)
# generated: 2026-08-10 by story-coder (golden-fixture lane — B5 encoding, test-first)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure-math fixture) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → xfailed✔ (must NOT pass until the engine lands)
# exceptions: PARTIAL — B5 GT-2 ends at "+tax" and names no tax rate and no total, so tax/total are NOT asserted and no rate is supplied. The three-block split (6.00 / 7.74 / untouched) is asserted only when the engine reports per-block lines, because B5 rules on the amounts, not on line granularity.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
