# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-014 (capacity-charge lines) · US-RAT-015 (TC-2: capacity
#           resolved through the registry) · US-RAT-012 (the demand half)
#           Screens: — (the lines render in S31.2 and S21)
# Rules:    BR-RAT-018/019/022 (capacity model; tenant-defined unit + rate;
#           calendar-day prorated) · BR-RAT-029 (taxable LIKE BASE) ·
#           BR-RAT-014 (demand: measurement is a max-demand REGISTER READ; the
#           engine consumes the quantity and computes no ratchet/PF) ·
#           BR-RAT-003 · BR-RAT-038 · BR-RAT-044
# Golden:   GT-15 / GT-17 (solar 4 x 10.00 = 40.00; battery 2 x 12.00 = 24.00) ·
#           GT-31 (= WE-16: 10/31 x 40.00 = 12.90, check #21 of the frozen
#           harness) · GT-20 (= WE-4: 14.2 kW x 9.50 = 134.90) · GT-21
#           (= WE-5: 48,200 kWh x 0.085 = 4,097.00 and 182 kW x 11.00 =
#           2,002.00)
# Tests:    this file (US-RAT-014 TC-1/2/4/6/7 + the demand cases)
# Impacts:  apps/rating/pricing/models/capacity.py 🔒 ·
#           apps/rating/pricing/models/demand.py 🔒
# ───────────────────────────────────────────────────────
"""US-RAT-014 — capacity charges, and the demand charge beside them.

TWO SHAPES, ONE FILE, BECAUSE THEY ARE THE SAME QUESTION IN TWO UNITS.
A capacity charge bills what a customer has CONNECTED (4 solar panels); a demand
charge bills the SIZE of what they drew (a 182 kW peak). Neither bills a volume,
and both put a unit on the bill that is not the unit of the energy beside them —
which is the mistake CLAUDE.md hard rule 3 exists to prevent and the reason both
plugins carry their own unit onto their own line.
"""

from decimal import Decimal

import pytest

from apps.billing import rating_seam
from apps.rating import engine
from apps.rating.pricing import errors

USD = "USD"
ACCOUNT = rating_seam.AccountContext(currency=USD, tax_exempt=False)
JULY = rating_seam.BillingPeriod(cycle_days=31, service_days=31)
#: WE-16's own shape: solar activated on the 22nd of a 31-day July -> 10 days.
FROM_THE_22ND = rating_seam.BillingPeriod(cycle_days=31, service_days=10)

SOLAR = rating_seam.TariffConfig(
    service="solar",
    model="capacity",
    billed_unit="panel",
    base_charge=None,
    capacity=rating_seam.CapacityRate(unit_label="panel", rate_per_unit=Decimal("10.00")),
)
BATTERY = rating_seam.TariffConfig(
    service="battery",
    model="capacity",
    billed_unit="kW block",
    base_charge=None,
    capacity=rating_seam.CapacityRate(unit_label="kW block", rate_per_unit=Decimal("12.00")),
)
FOUR_PANELS = rating_seam.Quantity(amount=Decimal("4"), unit="panel")
TWO_BLOCKS = rating_seam.Quantity(amount=Decimal("2"), unit="kW block")


def price(tariff, consumption, period=JULY, account=ACCOUNT):
    return rating_seam.price_period(
        tariff=tariff, consumption=consumption, period=period, account=account
    )


def refuse(tariff, consumption, period=JULY, account=ACCOUNT):
    """Straight to the engine — billing's seam translates rating refusals
    (DEF-047), and a test of a rating rule must ask rating."""
    return engine.price_period(
        tariff=tariff, consumption=consumption, period=period, account=account
    )


# ── Capacity (BR-RAT-018/022/029) ───────────────────────────────────────────


def test_us_rat_014_tc1_capacity_reproduces_gt15_and_gt17():
    """GT-15 / GT-17 — 4 panels at $10.00 and 2 kW blocks at $12.00."""
    (solar,) = price(SOLAR, FOUR_PANELS).lines_of("base")
    (battery,) = price(BATTERY, TWO_BLOCKS).lines_of("base")
    assert solar.amount == Decimal("40.00")
    assert battery.amount == Decimal("24.00")
    # The tenant's OWN word for the unit reaches the customer's bill.
    assert solar.unit == "panel" and solar.quantity == Decimal("4")
    assert "4 panel @ 10.00" in solar.description


def test_us_rat_014_tc1_capacity_is_taxable_like_base_structurally():
    """BR-RAT-029 — and it is the KIND that puts it in the B4.2 base, not a
    flag, so a mis-seeded taxable flag could not move it either way."""
    (solar,) = price(SOLAR, FOUR_PANELS).lines_of("base")
    assert solar.kind == "base"
    assert solar.taxable
    taxed = price(SOLAR, FOUR_PANELS)
    assert taxed.taxable_subtotal == Decimal("40.00")


def test_us_rat_014_tc2_capacity_prorates_on_calendar_days():
    """GT-31 (= WE-16) — solar from the 22nd of a 31-day July: 10/31 x 40.00."""
    (solar,) = price(SOLAR, FOUR_PANELS, period=FROM_THE_22ND).lines_of("base")
    assert solar.amount == Decimal("12.90")
    assert "(prorated)" in solar.description


def test_us_rat_014_both_capacity_lines_prorate_not_only_the_solar_one():
    """B5 GT-15 as AMENDED 2026-08-11: "BOTH lines prorate". The battery line
    read as exempt only because WE-16 stated the solar figure alone."""
    (battery,) = price(BATTERY, TWO_BLOCKS, period=FROM_THE_22ND).lines_of("base")
    assert battery.amount == Decimal("7.74")  # 10/31 x 24.00


def test_us_rat_014_tc4_an_exempt_account_still_gets_its_capacity_lines():
    """BR-RAT-006 — exemption zeroes the TAX, never the charge."""
    exempt = rating_seam.AccountContext(currency=USD, tax_exempt=True)
    bill = rating_seam.price_period(
        tariff=SOLAR,
        consumption=FOUR_PANELS,
        period=JULY,
        account=exempt,
        taxes=(rating_seam.TaxRule(code="State", rate=Decimal("0.0825")),),
    )
    (solar,) = bill.lines_of("base")
    assert solar.amount == Decimal("40.00")
    assert bill.tax_total == Decimal("0.00")


def test_us_rat_014_capacity_never_rounds_inside_the_plugin():
    """BR-RAT-003 — 10/31 x 40.00 leaves the plugin as a fraction."""
    from apps.rating.pricing import contracts
    from apps.rating.pricing.models import capacity

    (line,) = capacity.price(
        contracts.SubscriptionContext(service="solar", currency=USD),
        contracts.MeasuredUsage(
            billed_quantity=Decimal("4"),
            unit="panel",
            raw_quantity=Decimal("4"),
            multiplier=Decimal("1"),
        ),
        contracts.ModelConfig(
            model="capacity",
            billed_unit="panel",
            capacity=contracts.CapacitySpec(unit_label="panel", rate_per_unit=Decimal("10.00")),
        ),
        period=contracts.PeriodShape(
            cycle_days=31, service_days=10, factor=Decimal(10) / Decimal(31)
        ),
    )
    assert line.amount != Decimal("12.90")  # unrounded at the plugin boundary
    assert line.amount.quantize(Decimal("0.01")) == Decimal("12.90")


def test_us_rat_014_tc7_negative_capacity_units_are_refused():
    """A negative capacity would put a CREDIT on a customer's bill by
    arithmetic rather than by decision."""
    with pytest.raises(errors.RatingInputError):
        refuse(SOLAR, rating_seam.Quantity(amount=Decimal("-2"), unit="panel"))


def test_us_rat_014_capacity_refuses_one_tenants_units_against_anothers_label():
    """BR-RAT-038 — 4 panels are not 4 kW blocks, and no factor exists between
    one tenant's word and another's."""
    with pytest.raises(errors.UomMismatch):
        refuse(BATTERY, FOUR_PANELS)


def test_us_rat_014_capacity_refuses_a_tariff_with_no_rate():
    with pytest.raises(errors.TariffConfigError):
        refuse(
            rating_seam.TariffConfig(service="solar", model="capacity", billed_unit="panel"),
            FOUR_PANELS,
        )


# ── Demand (BR-RAT-014) ─────────────────────────────────────────────────────

INDUSTRIAL = rating_seam.TariffConfig(
    service="electric",
    model="demand",
    billed_unit="kWh",
    base_charge=None,
    energy_rate_per_kwh=Decimal("0.085"),
    demand_rate_per_kw=Decimal("11.00"),
)


def industrial_usage(kwh="48200", kw="182"):
    """WE-5's own quantities: post-multiplier energy, and the peak beside it."""
    return rating_seam.Quantity(
        amount=Decimal(kwh),
        unit="kWh",
        demand=rating_seam.Quantity(amount=Decimal(kw), unit="kW"),
    )


def test_us_rat_012_demand_reproduces_gt21_energy_and_peak():
    """GT-21 (= WE-5) — 48,200 kWh x $0.085 and 182 kW x $11.00."""
    lines = price(INDUSTRIAL, industrial_usage()).lines_of("usage")
    assert [line.amount for line in lines] == [Decimal("4097.00"), Decimal("2002.00")]


def test_us_rat_012_demand_puts_two_different_units_on_one_bill():
    """The whole point of the model, and the thing hard rule 3 is about: the
    energy line is kWh and the demand line is kW, on the same bill."""
    energy, demand = price(INDUSTRIAL, industrial_usage()).lines_of("usage")
    assert energy.unit == "kWh" and energy.quantity == Decimal("48200")
    assert demand.unit == "kW" and demand.quantity == Decimal("182")
    assert "peak 182 kW" in demand.description


def test_us_rat_012_demand_reproduces_gt20_commercial_peak():
    """GT-20 (= WE-4) — 14.2 kW x $9.50 = $134.90, a fractional peak."""
    commercial = rating_seam.TariffConfig(
        service="electric",
        model="demand",
        billed_unit="kWh",
        energy_rate_per_kwh=Decimal("0.19"),
        demand_rate_per_kw=Decimal("9.50"),
    )
    _, demand = price(commercial, industrial_usage(kwh="0", kw="14.2")).lines_of("usage")
    assert demand.amount == Decimal("134.90")


def test_us_rat_012_demand_refuses_when_the_peak_register_was_not_read():
    """BR-RAT-014's measurement is a REGISTER READ. On WE-5 the difference
    between absent and zero is $2,002.00."""
    with pytest.raises(errors.MissingDemandQuantity) as excinfo:
        refuse(INDUSTRIAL, rating_seam.Quantity(amount=Decimal("48200"), unit="kWh"))
    assert "unread" in str(excinfo.value)


def test_us_rat_012_demand_refuses_a_ratchet_it_cannot_compute():
    """US-RAT-007 TC-8 — "no silent math". Pricing the raw peak instead would
    under-bill every bill this tariff prices, invisibly."""
    with pytest.raises(errors.TariffConfigError) as excinfo:
        refuse(
            rating_seam.TariffConfig(
                service="electric",
                model="demand",
                billed_unit="kWh",
                energy_rate_per_kwh=Decimal("0.085"),
                demand_rate_per_kw=Decimal("11.00"),
                ratchet_enabled=True,
            ),
            industrial_usage(),
        )
    assert "PROPOSED" in str(excinfo.value)


def test_us_rat_012_demand_refuses_a_power_factor_penalty_it_cannot_compute():
    with pytest.raises(errors.TariffConfigError):
        refuse(
            rating_seam.TariffConfig(
                service="electric",
                model="demand",
                billed_unit="kWh",
                energy_rate_per_kwh=Decimal("0.085"),
                demand_rate_per_kw=Decimal("11.00"),
                pf_penalty_enabled=True,
            ),
            industrial_usage(),
        )


def test_us_rat_012_demand_refuses_half_a_tariff():
    with pytest.raises(errors.TariffConfigError):
        refuse(
            rating_seam.TariffConfig(
                service="electric",
                model="demand",
                billed_unit="kWh",
                energy_rate_per_kwh=Decimal("0.085"),
            ),
            industrial_usage(),
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-014@70a0044 (the four frozen sources: 04-docs/02-decisions/05-golden-tests.md · 04-docs/02-decisions/04-money-math-rules.md · 04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md · 04-docs/05-modules/06-rating/02-business-rules.md)
# generated: 2026-08-16 by the pricing-engines lane (EP-RAT-06 US-RAT-014 + the demand half of EP-RAT-02 US-RAT-007 §7)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_rat_014_capacity.py✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔
# exceptions: the BATTERY proration figure 7.74 is B5 GT-15's own AMENDED text of 2026-08-11 ("the battery line prorates too — $24.00 x 10/31 = $7.74"), not a figure invented here. GT-15 itself is PROPOSED; its 40.00 solar line is inside GT-17's frozen taxable base and its proration is the frozen harness's check #21 (WE-16/GT-31).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
