# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — usage pricing + totals)
#           Screens: — (priced lines render in S31.2)
# Rules:    BR-RAT-003 (round per line, half-up, 2dp, at finalization ONLY) ·
#           BR-RAT-005 (tax base = usage + base) · BR-RAT-012 (base charge per
#           service per cycle) · BR-RAT-027 (plan base is DERIVED per service)
# Golden:   GT-1 — B5 ❄️ FROZEN, finance-signed 2026-08-08 (05-golden-tests.md
#           lines 11-12). Every figure below is COPIED from those two lines.
# Tests:    this file (xfail until apps.rating.engine.price_period lands)
# Impacts:  06-backend/apps/billing/rating_seam.py · apps/rating/engine.py 🔒
# ───────────────────────────────────────────────────────
"""GT-1 - Electric flat $0.12/kWh, base $18.50, 684 kWh, tax 8.25% on usage+base -> total 108.88 (B5 GT-1, FROZEN 2026-08-08)

B5 GT-1 verbatim
----------------
  line 11: "Input: Electric flat $0.12/kWh, base $18.50, usage 684 kWh, tax
            8.25% on (usage+base)."
  line 12: "Assumed calc: 684x0.12 = 82.08; +18.50 = 100.58; tax 8.2979 -> 8.30;
            **total 108.88**." ... SUPERSEDED stamp: "finance freeze 2026-08-08:
            rules terminal - tax base = usage+base CONFIRMED (B4.2), round per
            line half-up 2dp CONFIRMED (B4.4); GT-1..61 signed as the
            billing-math contract, harness 33/33."

The "8.2979" in B5 is the unrounded tax shown to 4dp; the FINALIZED figure B5
signs is 8.30, and 8.30 is what this test asserts. Nothing here re-derives it.
"""

from decimal import Decimal

import pytest

from apps.billing import rating_seam

from .conftest import FULL_PERIOD, TAX_8_25, TAXED_ACCOUNT

pytestmark = pytest.mark.golden

# ── INPUT (B5 GT-1 line 11) ─────────────────────────────────────────────────
TARIFF = rating_seam.TariffConfig(
    service="electric",  # "Electric"
    model="flat",  # "flat"
    billed_unit="kWh",  # "$0.12/kWh"
    base_charge=Decimal("18.50"),  # "base $18.50"
    unit_price=Decimal("0.12"),  # "$0.12/kWh"
)
CONSUMPTION = rating_seam.Quantity(amount=Decimal("684"), unit="kWh")  # "usage 684 kWh"
TAXES = TAX_8_25  # "tax 8.25% on (usage+base)"

# ── EXPECTED (B5 GT-1 line 12) ──────────────────────────────────────────────
EXPECTED_USAGE = Decimal("82.08")  # "684x0.12 = 82.08"
EXPECTED_BASE = Decimal("18.50")  # "+18.50"
EXPECTED_TAXABLE_SUBTOTAL = Decimal("100.58")  # "= 100.58"
EXPECTED_TAX = Decimal("8.30")  # "tax 8.2979 -> 8.30"
EXPECTED_TOTAL = Decimal("108.88")  # "**total 108.88**"


def test_gt01_flat_residential():
    # B5 FROZEN 2026-08-08 - xfail flips to must-pass when the engine lands (W3).
    bill = rating_seam.price_period(
        tariff=TARIFF,
        consumption=CONSUMPTION,
        period=FULL_PERIOD,
        account=TAXED_ACCOUNT,
        taxes=TAXES,
    )

    usage = bill.sole_line("usage")
    assert usage.amount == EXPECTED_USAGE
    assert usage.quantity == Decimal("684")
    assert usage.unit == "kWh"  # hard rule 3: the unit travels with the number
    assert usage.unit_price == Decimal("0.12")
    assert usage.taxable is True  # B4.2: usage is in the tax base

    base = bill.sole_line("base")
    assert base.amount == EXPECTED_BASE
    assert base.taxable is True  # B4.2: base charge is in the tax base

    assert bill.taxable_subtotal == EXPECTED_TAXABLE_SUBTOTAL
    assert bill.tax_total == EXPECTED_TAX
    assert bill.total == EXPECTED_TOTAL


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (sha1[:7] of 05-golden-tests.md + 04-money-math-rules.md
#         + EP-RAT-05-engine.md + 06-rating/02-business-rules.md, concatenated in that order)
# generated: 2026-08-10 by story-coder (golden-fixture lane — B5 encoding, test-first)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure-math fixture) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → xfailed✔ (must NOT pass until the engine lands)
# exceptions: none — GT-1 is fully frozen in B5 (input and every output figure). FULL_PERIOD's day count is scaffolding only; GT-1 prorates nothing, so the B4.3 factor is 1 for any length.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
