# ── Trace ──────────────────────────────────────────────
# Change:  CR-166-BRC10 round 4 task 9 — the discounts web walk, step 9.
# Defects: DEF-RAT-9327 (an approved charge waiver on NAMED charge codes stopped
#          the WHOLE bill of every enrolled account)
# Rules:   BR-RAT-068 (a scoped discount — `named_codes` named — is taken over
#          the TARIFF lines in its scope, of what is printed) · BR-RAT-962
#          (`charge_waiver` is in the priceable set) · decision log 2026-08-22
#          (fees and deposits are never discounted — no signed rule)
# ───────────────────────────────────────────────────────
"""DEF-RAT-9327 — a named-codes discount prices; it never stops a bill.

The walk's own figure: water, base `BASE-W` $8.00 + 10 kgal at $4.20 + 2 kgal at
$5.00 = **$60.00**. Mia Okafor is enrolled in *Lead line waiver*, a charge waiver
on the named code `BASE-W`. The waiver removes what its scope selects — the
$8.00 base line — so her bill is **$60.00 − $8.00 = $52.00**, with the base line
still printed at $8.00 beside the reduction (BR-RAT-068's overlay).

Until this fix the engine REFUSED the whole account (`BillRunBreak`, *"rating
refused to price this bill … the engine's priced lines do not carry a charge
code"*): `billing.gather` always knew the base's code and handed it across the
seam as `TariffConfig.base_charge_code`, and the engine dropped it.

A code the engine can never find on a tariff line — a FEE such as a connection
charge — is refused when the discount is APPROVED, where a clerk is looking,
because discounting a fee has no signed rule and a waiver that silently took
$0.00 off is the failure BR-RAT-068's *"subsidy granted is reportable"*
forbids. A refusal at a bill run would be an outage; at approval it is a
correction.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import rating_seam
from apps.rating import discount_services
from apps.rating import discounts as dm
from apps.rating import models as rating_models
from apps.rating.discount_services import DiscountRuleError

from tests.test_cr166_discounts_round2 import _discount
from tests.test_cr166_discounts_round2 import _today  # noqa: F401 — the pinned "today"
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401

D = Decimal
PERIOD = rating_seam.BillingPeriod(cycle_days=30, service_days=30)
ACCOUNT = rating_seam.AccountContext(currency="USD")


def _water(base_code="BASE-W"):
    """The walk's residential water schedule: $8.00 base + 0–10 @ 4.20 + 10+ @ 5.00."""
    return rating_seam.TariffConfig(
        service="water",
        model="tiered",
        billed_unit="kgal",
        base_charge=D("8.00"),
        base_charge_code=base_code,
        tiers=(
            rating_seam.Tier(upper=D("10"), unit_price=D("4.20")),
            rating_seam.Tier(upper=None, unit_price=D("5.00")),
        ),
    )


def _waiver(codes=("BASE-W",), **kwargs):
    defaults = dict(
        code="LEADWAIVE",
        name="Lead line waiver",
        discount_type="charge_waiver",
        value=D("0"),
        currency="USD",
        applies_to="named_codes",
        applies_to_charge_codes=codes,
    )
    defaults.update(kwargs)
    return rating_seam.DiscountRule(**defaults)


def _bill(*discounts, base_code="BASE-W"):
    return rating_seam.price_bill(
        services=((_water(base_code), rating_seam.Quantity(amount=D("12"), unit="kgal")),),
        period=PERIOD,
        account=ACCOUNT,
        taxes=(),
        discounts=discounts,
    )


# ══ the engine — the walk's figure ═══════════════════════════════════════════


def test_def_rat_9327_a_waiver_on_the_base_code_takes_the_base_off_60_becomes_52():
    """RED before the fix: `PricingRefused: discount 'LEADWAIVE' has scope
    `named_codes` … the engine's priced lines do not carry a charge code`."""
    bill = _bill(_waiver())
    assert bill.sole_line("base").amount == D("8.00")  # still printed in full
    (line,) = bill.lines_of("discount")
    assert line.amount == D("-8.00")
    assert line.description == "Lead line waiver"
    assert bill.total == D("52.00")


def test_def_rat_9327_a_percentage_on_a_named_code_is_a_percentage_of_that_line():
    """BR-RAT-068: a scoped percentage is a percentage of the printed lines in
    its scope — 50% of the $8.00 base, not of the $60.00 bill."""
    bill = _bill(_waiver(discount_type="percentage", value=D("50")))
    (line,) = bill.lines_of("discount")
    assert line.amount == D("-4.00")
    assert bill.total == D("56.00")


def test_def_rat_9327_a_named_code_not_on_this_bill_reduces_nothing_and_the_bill_prices():
    """An account whose bill carries no line from the named code — the
    municipal account has no residential base — gets no reduction, exactly
    as a base-only discount on a bill with no base. The bill is NOT stopped."""
    bill = _bill(_waiver(), base_code="BASE-COM")
    assert bill.lines_of("discount") == ()
    assert bill.total == D("60.00")


def test_def_rat_9327_the_charge_code_survives_rounding():
    """The code is stamped on the base candidate and must cross finalize, or
    apply-discounts (which runs AFTER finalize) cannot see it."""
    from apps.rating.pricing.contracts import KIND_BASE, LineCandidate
    from apps.rating.pricing.stages.finalize import finalize_line

    line = finalize_line(
        LineCandidate(kind=KIND_BASE, description="water base charge", amount=D("8.004"),
                      taxable=True, charge_code="BASE-W")
    )
    assert (line.amount, line.charge_code) == (D("8.00"), "BASE-W")


# ══ approval — a code that can never be on a tariff line ═══════════════════


def _charge(tenant, code, *, is_base):
    return rating_models.Charge.objects.create(
        tenant=tenant,
        code=code,
        name=f"{code} charge",
        charge_type="recurring" if is_base else "one_time",
        amount_rule="flat",
        amount=D("8.00") if is_base else D("45.00"),
        is_base=is_base,
    )


def _named(actor, codes):
    row = _discount(
        actor,
        "LEADWAIVE",
        value="0",
        approve=False,
        discount_type=dm.DISCOUNT_CHARGE_WAIVER,
        applies_to=dm.SCOPE_NAMED_CODES,
        applies_to_charge_codes=list(codes),
    )
    discount_services.submit_discount(actor, row.id)
    return row


@pytest.mark.django_db
def test_def_rat_9327_approval_refuses_a_waiver_naming_a_fee_code(brazos, dana):
    with tenant_ctx(brazos):
        _charge(brazos, "BASE-T", is_base=True)
        _charge(brazos, "CONN-T", is_base=False)
        row = _named(dana, ("BASE-T", "CONN-T"))
        with pytest.raises(DiscountRuleError) as refusal:
            discount_services.approve_discount(dana, row.id)
    assert refusal.value.message_key == "rating.discounts.named_code_not_priceable"
    assert refusal.value.params == {"codes": "CONN-T"}


@pytest.mark.django_db
def test_def_rat_9327_approval_accepts_a_waiver_naming_a_base_code(brazos, dana):
    with tenant_ctx(brazos):
        _charge(brazos, "BASE-T", is_base=True)
        row = _named(dana, ("BASE-T",))
        discount_services.approve_discount(dana, row.id)
        assert dm.DiscountVersion.objects.filter(discount=row, status=dm.VERSION_ACTIVE).exists()
