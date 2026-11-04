# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-012 (usage pricing — TC-6, the sewer case) · US-RAT-007
#           (the %-of-water structure this prices) · US-RAT-015 (the plugin
#           interface it registers through)
#           Screens: — (the line renders in S31.2 and on the bill)
# Rules:    BR-RAT-015 ❄️ SUPERSEDED 2026-09-08 by CR-081 (was: % of WATER
#           USAGE-CHARGE DOLLARS, excl. base, excl. tax; now: % of the water
#           QUANTITY, priced on sewer's own schedule) · BR-RAT-010 reopened and
#           answered the other way · BR-RAT-003 (no plugin rounds) · BR-RAT-044
# Golden:   GT-17 (= WE-1, recomputed by 10-scripts/03-golden-verify.py):
#           water 8 kgal -> sewer 90% x 8 = 7.2 kgal x $5.0000 = **36.00** (the
#           4120 posting; it was 40% x 39.50 = 15.80 until 2026-09-08).
#           GT-25 (WE-9): 90% x 6 kgal x $5.0000 = 27.00 (was 10.60)
# Tests:    this file (US-RAT-012 TC-6 + the seam refusal)
# Impacts:  apps/rating/pricing/models/percent_of_service.py 🔒 ·
#           apps/rating/engine.py 🔒 (the two-pass that supplies the basis)
# ───────────────────────────────────────────────────────
"""US-RAT-012 TC-6 — a service priced as a percentage of another service.

TWO THINGS ARE UNDER TEST AND ONLY ONE OF THEM IS ARITHMETIC.

The arithmetic is CR-081 and its re-signed figure: on B5 GT-17 the meter reads
**8 kgal** of water, 90% of that volume reaches the sewer, and the sewer line is
**7.2 kgal x $5.0000 = $36.00**.

⚠ **THIS PARAGRAPH READ, UNTIL 2026-09-08:** *"The arithmetic is BR-RAT-015 and
its frozen figure: on B5 GT-17 the water usage lines are $20.00 and $19.50, the
water BASE is $8.00, and the sewer line is $15.80 — 40% of 39.50 and not of
47.50."* Quoted rather than deleted (hard-won law 1). The PO reopened
`BR-RAT-010` and re-signed six frozen figures under HUMAN-GUIDE §6, verbatim:
*"C — factor 90%, rate $5.00 → $36.00, which is what a real sewer customer
actually pays"*. **The base-charge exclusion it argued about is not an
exclusion any more** — a base charge is not a quantity of water, so there is
nothing to exclude it from. The tests below that used to prove those exclusions
now prove the thing that replaced them: **the basis is the METERED VOLUME and
not any amount of money on the bill**, which is the same guarantee stated
against the new rule.

The other thing is the SEAM. Sewer's price depends on a service that is not
sewer, so the engine has to price water first and hand the answer across. When
water is NOT on the bill there is no answer, and CLAUDE.md's rule for that case
is exact: an unwired seam REPORTS that it cannot answer, never answers 0. A
sewer line priced at $0.00 is a bill that silently forgives a charge, on every
bill, for as long as nobody notices.
"""

from decimal import Decimal

import pytest

from apps.billing import rating_seam
from apps.rating import engine
from apps.rating.pricing import errors

USD = "USD"
ACCOUNT = rating_seam.AccountContext(currency=USD, tax_exempt=False)
FULL_MONTH = rating_seam.BillingPeriod(cycle_days=31, service_days=31)

#: B5 GT-17's own water schedule ([W] §1: "0–5 kgal $4.00 / 5–15 $6.50 / 15+
#: $8.00") with the bill's $8.00 water base — the base is here on purpose, so
#: the exclusion is exercised rather than assumed.
WATER = rating_seam.TariffConfig(
    service="water",
    model="tiered",
    billed_unit="kgal",
    base_charge=Decimal("8.00"),
    tiers=(
        rating_seam.Tier(upper=Decimal("5"), unit_price=Decimal("4.00")),
        rating_seam.Tier(upper=Decimal("15"), unit_price=Decimal("6.50")),
        rating_seam.Tier(upper=None, unit_price=Decimal("8.00")),
    ),
)
SEWER = rating_seam.TariffConfig(
    service="sewer",
    model="percent_of_service",
    billed_unit="kgal",
    percent=Decimal("90"),  # PERCENT POINTS, as S11 stores them
    basis_service="water",
    # `CR-130-BRC07` — A PERCENTAGE OF WHAT. Stated rather than defaulted, and
    # the fixture would REFUSE without it: the plugin never assumes a basis,
    # because 90% of the water VOLUME is $36.00 here and 90% of the water
    # MONEY is $35.55 — two different bills off the same two numbers.
    percent_basis="usage",
    # CR-081 — sewer's OWN rate, which it has never had until now. Stored as
    # `flat` stores one (BR-RAT-032, a single 0→∞ tier) and unwrapped onto the
    # seam by `rating.selectors.pricing_inputs`.
    unit_price=Decimal("5.0000"),
)
EIGHT_KGAL = rating_seam.Quantity(amount=Decimal("8"), unit="kgal")


def bill(services, **kwargs):
    return engine.price_bill(services=services, period=FULL_MONTH, account=ACCOUNT, **kwargs)


def test_us_rat_012_tc6_sewer_is_90_percent_of_the_water_volume():
    """GT-17 ❄️ RE-SIGNED — 90% x 8 kgal = 7.2 kgal at $5.0000 = 36.00."""
    priced = bill(((WATER, EIGHT_KGAL), (SEWER, EIGHT_KGAL)))
    water_usage = [line for line in priced.lines_of("usage") if line.service == "water"]
    assert [line.amount for line in water_usage] == [Decimal("20.00"), Decimal("19.50")]

    (sewer,) = [line for line in priced.lines_of("usage") if line.service == "sewer"]
    assert sewer.amount == Decimal("36.00")
    assert sewer.taxable  # B4.2 — the sewer line is itself in the tax base


def test_us_rat_012_tc6_the_basis_is_a_volume_and_not_any_money_on_the_bill():
    """CR-081 — the successor to the old "excl. base" test, and it holds more.

    On the DOLLAR basis the water base had to be EXCLUDED by a filter, and this
    test proved the filter ran (40% x 47.50 = 19.00 was the failure it guarded).
    On the VOLUME basis there is no filter to run and nothing to exclude, so the
    guarantee is stated the other way round: the sewer amount is a function of
    the METERED QUANTITY ALONE, and moving any money on the bill leaves it
    exactly where it is.
    """
    priced = bill(((WATER, EIGHT_KGAL), (SEWER, EIGHT_KGAL)))
    (base,) = [line for line in priced.lines_of("base") if line.service == "water"]
    assert base.amount == Decimal("8.00")  # the base IS on the bill …
    (sewer,) = [line for line in priced.lines_of("usage") if line.service == "sewer"]
    assert sewer.amount == Decimal("36.00")

    # Double the water BASE and treble every water PRICE. Not one cent of that
    # can reach the sewer line, because the sewer line never reads any of it.
    dearer_water = rating_seam.TariffConfig(
        service="water",
        model="tiered",
        billed_unit="kgal",
        base_charge=Decimal("16.00"),
        tiers=(
            rating_seam.Tier(upper=Decimal("5"), unit_price=Decimal("12.00")),
            rating_seam.Tier(upper=Decimal("15"), unit_price=Decimal("19.50")),
            rating_seam.Tier(upper=None, unit_price=Decimal("24.00")),
        ),
    )
    dearer = bill(((dearer_water, EIGHT_KGAL), (SEWER, EIGHT_KGAL)))
    (still,) = [line for line in dearer.lines_of("usage") if line.service == "sewer"]
    assert still.amount == Decimal("36.00")
    assert still.quantity == Decimal("7.2")


def test_us_rat_012_tc6_tax_cannot_reach_the_basis():
    """The old "excl. tax" guarantee, restated: a volume carries no tax at all,
    so the sewer line cannot be taxed twice by the back door."""
    taxed = bill(
        ((WATER, EIGHT_KGAL), (SEWER, EIGHT_KGAL)),
        taxes=(rating_seam.TaxRule(code="State", rate=Decimal("0.0825")),),
    )
    (sewer,) = [line for line in taxed.lines_of("usage") if line.service == "sewer"]
    assert sewer.amount == Decimal("36.00")  # unchanged by the presence of tax


def test_us_rat_012_tc6_the_sewer_line_states_its_quantity_its_unit_and_its_rate():
    """⚠ THIS TEST ASSERTED THE OPPOSITE UNTIL 2026-09-08, AND SAID WHY:
    *"A line priced off DOLLARS has no metered volume. Printing '3.2 kgal' would
    state a consumption nobody measured."* Under CR-081 the quantity is not
    invented — it IS the number the price is applied to, and printing it is the
    only way the customer can check the line.

    **THE UNIT IS THE BASIS SERVICE'S**, not sewer's own guess: a utility
    metering water in `ccf` bills sewer in `ccf`.
    """
    priced = bill(((WATER, EIGHT_KGAL), (SEWER, EIGHT_KGAL)))
    (sewer,) = [line for line in priced.lines_of("usage") if line.service == "sewer"]
    assert sewer.quantity == Decimal("7.2")
    assert sewer.unit == "kgal"
    assert sewer.unit_price == Decimal("5.0000")
    # ⚠ THIS READ `"40% of water usage charges"` UNTIL 2026-08-27, AND IT
    # PASSED THROUGHOUT THE DEFECT IT LOOKS LIKE IT WOULD CATCH (DEF-968,
    # CR-043 finding 2).
    #
    # The description used to interpolate `config.percent` raw. This fixture
    # builds that percent as `Decimal("40")`, so the sentence here really was
    # *"40% of water usage charges"* and the assertion was true. The DATABASE
    # column is `NUMERIC(18,6)`, so the same line on a real bill read **"sewer
    # usage — 40.000000% of water usage charges"** — which is what the Product
    # Owner photographed on the live deployment at v2.61.1.
    #
    # **A fixture that supplies a tidier value than the column can hold tests
    # the fixture.** `tests/test_cr043_line_wording.py` prices from an explicit
    # `Decimal("40.000000")` for exactly that reason; this assertion is updated
    # to the new wording rather than deleted, because the fact it guards — the
    # sentence STATES ITS BASIS, since a sewer line has no meter reading beside
    # it — is still worth holding.
    #
    # Hard rule 2: percentages are stored to six and DISPLAYED to two, padded —
    # `40.00%`, the convention `selectors._display_percent` already serves
    # everywhere else in this product (BR-RAT-087).
    assert "90.00% of water volume" in sewer.description


def test_us_rat_012_tc6_line_order_follows_the_caller_not_the_pricing_order():
    """Sewer is priced SECOND and printed where the caller put it — a document
    must not silently reorder itself the day a plan gains a sewer line."""
    priced = bill(((SEWER, EIGHT_KGAL), (WATER, EIGHT_KGAL)))
    services = [line.service for line in priced.lines if line.service]
    assert services.index("sewer") < services.index("water")


# ── The seam refusal. This is the half CLAUDE.md's rule is about. ────────────


def test_us_rat_012_tc6_sewer_refuses_when_water_is_not_on_the_bill():
    """The basis service is absent — REFUSE BY NAME, never price zero."""
    with pytest.raises(errors.BasisUnavailable) as excinfo:
        bill(((SEWER, EIGHT_KGAL),))
    message = str(excinfo.value)
    assert "water" in message
    assert "0.00" in message  # the refusal SAYS what it declined to do


def test_us_rat_012_tc6_sewer_refuses_when_the_basis_service_has_no_usage():
    """Water on the bill as BASE ONLY (a vacation hold, BR-BIL-028) leaves no
    metered volume. 90% of nothing measured is not $0.00 either."""
    with pytest.raises(errors.BasisUnavailable):
        engine.price_bill(
            services=((SEWER, EIGHT_KGAL),),
            base_only_services=(WATER,),
            period=FULL_MONTH,
            account=ACCOUNT,
        )


def test_us_rat_012_tc6_a_percent_tariff_may_not_be_its_own_basis():
    """Chained percentages have no signed rule and no frozen figure, so the
    engine refuses rather than inventing an evaluation order."""
    chained = rating_seam.TariffConfig(
        service="stormwater",
        model="percent_of_service",
        billed_unit="kgal",
        percent=Decimal("10"),
        basis_service="sewer",
        percent_basis="usage",
        unit_price=Decimal("1.0000"),
    )
    with pytest.raises(errors.BasisUnavailable):
        bill(((WATER, EIGHT_KGAL), (SEWER, EIGHT_KGAL), (chained, EIGHT_KGAL)))


def test_us_rat_012_tc6_refuses_a_tariff_with_no_percent_or_no_basis():
    with pytest.raises(errors.TariffConfigError):
        bill(
            (
                (WATER, EIGHT_KGAL),
                (
                    rating_seam.TariffConfig(
                        service="sewer",
                        model="percent_of_service",
                        billed_unit="kgal",
                        basis_service="water",
                        percent_basis="usage",
                        unit_price=Decimal("5.0000"),
                    ),
                    EIGHT_KGAL,
                ),
            )
        )
    with pytest.raises(errors.TariffConfigError):
        bill(
            (
                (WATER, EIGHT_KGAL),
                (
                    rating_seam.TariffConfig(
                        service="sewer",
                        model="percent_of_service",
                        billed_unit="kgal",
                        percent=Decimal("90"),
                        unit_price=Decimal("5.0000"),
                    ),
                    EIGHT_KGAL,
                ),
            )
        )


def test_us_rat_012_tc6_percent_is_points_not_a_fraction():
    """US-RAT-007 TC-6 stores what the tenant typed (90 = 90%). A tariff read as
    a fraction would bill 90 x 8 kgal = 720 kgal of sewer at $5.0000 =
    $3,600.00 — visible, but only once."""
    priced = bill(((WATER, EIGHT_KGAL), (SEWER, EIGHT_KGAL)))
    (sewer,) = [line for line in priced.lines_of("usage") if line.service == "sewer"]
    assert sewer.amount == Decimal("36.00")


def test_cr081_sewer_refuses_a_factor_with_no_rate():
    """CR-081's NEW refusal, and it could not exist on the dollar basis: the
    price used to come from the water schedule. A sewer tariff with a factor and
    no rate of its own is HALF configured, and half a tariff bills $0.00."""
    rateless = rating_seam.TariffConfig(
        service="sewer",
        model="percent_of_service",
        billed_unit="kgal",
        percent=Decimal("90"),
        basis_service="water",
        percent_basis="usage",
    )
    with pytest.raises(errors.TariffConfigError) as excinfo:
        bill(((WATER, EIGHT_KGAL), (rateless, EIGHT_KGAL)))
    assert "no rate per unit" in str(excinfo.value)


def test_cr081_the_sewer_line_borrows_the_basis_services_unit():
    """Hard rule 3 — a utility metering water in `ccf` bills sewer in `ccf`, and
    the unit is COPIED from the basis rather than read off the sewer tariff."""
    ccf_water = rating_seam.TariffConfig(
        service="water",
        model="flat",
        billed_unit="ccf",
        unit_price=Decimal("3.00"),
    )
    ccf_sewer = rating_seam.TariffConfig(
        service="sewer",
        model="percent_of_service",
        billed_unit="ccf",
        percent=Decimal("90"),
        basis_service="water",
        percent_basis="usage",
        unit_price=Decimal("4.0000"),
    )
    priced = bill(
        (
            (ccf_water, rating_seam.Quantity(amount=Decimal("10"), unit="ccf")),
            (ccf_sewer, rating_seam.Quantity(amount=Decimal("10"), unit="ccf")),
        )
    )
    (sewer,) = [line for line in priced.lines_of("usage") if line.service == "sewer"]
    assert (sewer.quantity, sewer.unit) == (Decimal("9.0"), "ccf")
    assert sewer.amount == Decimal("36.00")  # 9 ccf x 4.0000


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (the four frozen sources: 04-docs/02-decisions/05-golden-tests.md · 04-docs/02-decisions/04-money-math-rules.md · 04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md · 04-docs/05-modules/06-rating/02-business-rules.md)
# generated: 2026-08-16 by the pricing-engines lane (EP-RAT-05 US-RAT-012 TC-6) · AMENDED 2026-09-08 by the CR-081 lane (the volume basis; BR-RAT-015 ❄️ SUPERSEDED, BR-RAT-010 reopened)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_rat_012_percent_of_service.py✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔
# exceptions: 36.00 and its 7.2 kgal basis are recomputed from raw inputs by the harness (GT-17 ❄️ RE-SIGNED 2026-09-08 under HUMAN-GUIDE §6). The $3,600.00 counter-figure is derived here to show what reading the percent as a fraction would cost, and is labelled as such.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
