# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-012 (usage pricing: consumption → priced lines — multiplier,
#           tiers, proration, UoM gate, purity, unit discipline)
#           Screens: — (priced lines render in S31.2)
# Rules:    BR-RAT-001 (multiplier BEFORE tiers) · BR-RAT-002 (tier thresholds
#           reset per bill and scale with the prorated period) · BR-RAT-003
#           (round per line, half-up, 2dp, at finalization ONLY) · BR-RAT-004
#           (calendar-day proration) · BR-RAT-026 (pure tiers) · BR-RAT-032
#           (tier contiguity) · BR-RAT-038 (UoM gate — no silent conversion)
# Golden:   GT-1 · GT-2 · GT-3 · GT-5 — B5 ❄️ FROZEN 2026-08-08. The frozen
#           FIGURES are asserted in 06-backend/tests/golden/, once. This file
#           asserts the RULES those figures pin, including the ones no B5 case
#           discriminates.
# Tests:    this file (US-RAT-012 TC-1/2/3/4/7/8/9)
# Impacts:  apps/rating/engine.py 🔒 · apps/rating/pricing/**
# ───────────────────────────────────────────────────────
"""US-RAT-012 — usage pricing, rule by rule.

Division of labour with tests/golden/: the golden files own B5's FIGURES and
copy each one from the frozen document. This file owns the RULES — the
behaviours a figure implies but does not always discriminate. `test_..._tc2b`
below exists precisely because of one of those: breaking tier spans into
cumulative bounds leaves GT-2 and GT-5 GREEN (in both, the remaining quantity is
smaller than either reading of the span), so B5 alone does not defend that rule.
Proven by deliberately introducing the break and watching the golden suite pass
before this test existed — hard-won law 7, in the direction that matters.

No figure here is presented as a B5 figure. Where an amount appears it is
derived from the CONFIRMED formula in EP-RAT-05 §7
(`usage = Σ tiers min(remaining, span × proration) × price`) and is labelled as
derived; the frozen numbers stay in tests/golden/ where finance can find them.
"""

from decimal import Decimal

import pytest

from apps.billing import rating_seam
from apps.rating.pricing import errors

USD = "USD"
ACCOUNT = rating_seam.AccountContext(currency=USD, tax_exempt=False)
FULL_MONTH = rating_seam.BillingPeriod(cycle_days=30, service_days=30)
HALF_MONTH = rating_seam.BillingPeriod(cycle_days=30, service_days=15)

# The B5 GT-2 tier table, reused as a STRUCTURE (its figures are asserted in
# tests/golden/test_gt02_tiered_water.py, not here).
WATER_TIERS = (
    rating_seam.Tier(upper=Decimal("2"), unit_price=Decimal("3.00")),
    rating_seam.Tier(upper=Decimal("5"), unit_price=Decimal("4.50")),
    rating_seam.Tier(upper=None, unit_price=Decimal("6.00")),
)


def water_tariff(**overrides):
    base = {
        "service": "water",
        "model": "tiered",
        "billed_unit": "kgal",
        "base_charge": None,
        "tiers": WATER_TIERS,
    }
    base.update(overrides)
    return rating_seam.TariffConfig(**base)


def price(tariff, quantity, unit="kgal", period=FULL_MONTH, account=ACCOUNT, **kwargs):
    return rating_seam.price_period(
        tariff=tariff,
        consumption=rating_seam.Quantity(amount=quantity, unit=unit),
        period=period,
        account=account,
        **kwargs,
    )


def refuse(tariff, quantity, unit="kgal", period=FULL_MONTH, account=ACCOUNT, **kwargs):
    """The same call, made to the ENGINE rather than to billing's seam.

    ADDED 2026-08-11 (DEF-047), and the reason is a rule worth knowing before
    writing the next refusal test here. `price` above goes through
    `rating_seam` because that is the published shape B5's fixtures bind to and
    it carries the `lines_of` / `sole_line` helpers the positive cases read. The
    REFUSAL cases cannot go that way any more: the seam now TRANSLATES a rating
    refusal into `rating_seam.PricingRefused` on its way into billing, because
    an untranslated one used to escape billing's per-account run loop and kill a
    whole run of 1,124 accounts over one mistyped rate.

    That translation is correct, and it means a test of BR-RAT-038 must ask
    RATING — the rule is written in rating's own error hierarchy, and asserting
    billing's wrapper here would test the adapter twice and the rule not at all.
    The translation itself is asserted where it belongs, at the seam and at the
    loop: tests/golden/test_gt05_tier_multiplier.py and
    tests/test_us_bil_004_run_loop.py tc8.

    Inputs stay seam-typed on purpose — `apps/rating/pricing/stages/normalize.py`
    reads them structurally, by attribute, and never imports billing.
    """
    from apps.rating import engine

    return engine.price_period(
        tariff=tariff,
        consumption=rating_seam.Quantity(amount=quantity, unit=unit),
        period=period,
        account=account,
        **kwargs,
    )


def test_us_rat_012_tc1_flat_line_carries_quantity_unit_and_price():
    """TC-1 — a flat usage line reports what it charged, not just the amount."""
    tariff = rating_seam.TariffConfig(
        service="electric",
        model="flat",
        billed_unit="kWh",
        base_charge=Decimal("18.50"),
        unit_price=Decimal("0.12"),
    )
    bill = price(tariff, Decimal("684"), unit="kWh")

    usage = bill.sole_line("usage")
    assert (usage.quantity, usage.unit, usage.unit_price) == (
        Decimal("684"),
        "kWh",
        Decimal("0.12"),
    )
    assert usage.taxable is True  # B4.2
    assert bill.sole_line("base").taxable is True  # B4.2
    assert bill.currency == USD


def test_us_rat_012_tc2_tier_blocks_consume_in_order():
    """TC-2 — every unit bills through a tier, in block order (BR-RAT-026)."""
    bill = price(water_tariff(), Decimal("3.72"))
    lines = bill.lines_of("usage")

    assert [line.quantity for line in lines] == [Decimal("2"), Decimal("1.72")]
    assert [line.unit_price for line in lines] == [Decimal("3.00"), Decimal("4.50")]
    # BR-RAT-026: no allowance, no included units — the quantities billed sum to
    # the quantity measured, exactly.
    assert sum(line.quantity for line in lines) == Decimal("3.72")
    # The top block is never reached at 3.72 kgal, so it produces no line at all
    # rather than a 0.00 one.
    assert len(lines) == 2


def test_us_rat_012_tc2b_tier_quantity_is_the_span_not_the_upper_bound():
    """A tier bills its SPAN, never its upper bound (BR-RAT-032 contiguity).

    NOT DISCRIMINATED BY B5. GT-2 (3.72 kgal) and GT-5 (2,740 kWh) both stop in a
    block whose remaining quantity is below the span under either reading, so
    replacing `span = upper - lower` with `span = upper` leaves both golden tests
    GREEN. Verified by making that exact break and running `pytest -m golden`:
    7 passed. This test is the guard that break has to fail, and it does — with
    the break in place, the middle block bills 4 kgal instead of 3.

    Consumption of 6 kgal crosses BOTH boundaries of B5's own tier table, which
    is what makes the two readings diverge. The expected split (2 / 3 / 1) is
    the CONFIRMED formula of EP-RAT-05 §7, not a B5 figure.
    """
    lines = price(water_tariff(), Decimal("6")).lines_of("usage")

    assert [line.quantity for line in lines] == [Decimal("2"), Decimal("3"), Decimal("1")]
    assert [line.unit_price for line in lines] == [
        Decimal("3.00"),
        Decimal("4.50"),
        Decimal("6.00"),
    ]


def test_us_rat_012_tc3_multiplier_lands_before_the_tier_table():
    """TC-3 — B4.4: the tiered quantity is post-multiplier, never the raw delta.

    AMENDED 2026-08-11 by PO ruling (decision 4). The RULE this test is named
    for is unchanged and is still what it asserts: a tier table must never see
    a raw dial delta. What changed is WHO multiplies. Metering does; the engine
    refuses to. So this test now drives the engine with the post-multiplier
    quantity B5 itself states (2,740) and proves the tiering half, while the
    multiplication half is proved by GT-5's chain test against
    `apps.metering.quantities`.

    It was previously written the only way it could be written — hand the
    engine 274 and a x10 tariff multiplier — and would now pass a raw delta
    through untouched. Rewritten rather than deleted, because the assertion it
    makes about tier blocks is exactly as valuable as it was; only its input
    route moved.
    """
    tariff = rating_seam.TariffConfig(
        service="electric",
        model="tiered",
        billed_unit="kWh",
        base_charge=None,
        tiers=(
            rating_seam.Tier(upper=Decimal("1000"), unit_price=Decimal("0.10")),
            rating_seam.Tier(upper=None, unit_price=Decimal("0.14")),
        ),
        # No multiplier: the engine refuses one (see the trip-wire below).
    )
    lines = price(tariff, Decimal("2740"), unit="kWh").lines_of("usage")

    # 2,740 crosses the block boundary. The raw delta 274 would stop inside
    # block 1 and produce a SINGLE line — so two blocks remains the observable
    # consequence of the multiplier having been applied before tiering, wherever
    # that now happens.
    assert len(lines) == 2
    assert [line.quantity for line in lines] == [Decimal("1000"), Decimal("1740")]
    assert sum(line.quantity for line in lines) == Decimal("2740")


def test_us_rat_012_tc3b_engine_refuses_a_tariff_multiplier():
    """The other half of the ruling: the engine will not silently ignore one.

    A tariff multiplier reaching the engine means its caller believes the
    engine multiplies. Since metering already did, pricing it again is the
    $4,853 → $194,113 failure. Ignoring the field would produce the right
    number today and leave the wrong belief in place for tomorrow.
    """
    from apps.rating.pricing import errors as pricing_errors

    tariff = rating_seam.TariffConfig(
        service="electric",
        model="tiered",
        billed_unit="kWh",
        tiers=(rating_seam.Tier(upper=None, unit_price=Decimal("0.10")),),
        multiplier=Decimal("10"),
    )
    with pytest.raises(pricing_errors.TariffConfigError):
        refuse(tariff, Decimal("2740"), unit="kWh")


def test_us_rat_012_tc4_proration_scales_the_base_and_the_tier_thresholds():
    """TC-4 — B4.3/BR-RAT-002: base × days, thresholds × days, quantity NEVER.

    US-RAT-012 TC-4 states the threshold half as "tier thresholds scale ×15/30
    (0–1,000 → 0–500) before pricing". B5 GT-3 freezes only the base half
    (15.25) and says in its own words that the usage half is "pending usage
    figures", so the threshold behaviour is asserted structurally here — on
    quantities, which need no frozen money to check.
    """
    assert rating_seam.prorate_base_charge(
        base_charge=Decimal("30.50"), period=HALF_MONTH
    ) == Decimal("15.25")

    tariff = rating_seam.TariffConfig(
        service="electric",
        model="tiered",
        billed_unit="kWh",
        base_charge=Decimal("30.50"),
        tiers=(
            rating_seam.Tier(upper=Decimal("1000"), unit_price=Decimal("0.10")),
            rating_seam.Tier(upper=None, unit_price=Decimal("0.14")),
        ),
    )
    lines = price(tariff, Decimal("800"), unit="kWh", period=HALF_MONTH).lines_of("usage")

    # 0–1,000 scaled by 15/30 is 0–500: 500 units bill in block 1 and the
    # remaining 300 bill in block 2. Over a full month all 800 would sit in
    # block 1 — that difference IS the rule.
    assert [line.quantity for line in lines] == [Decimal("500"), Decimal("300")]
    # The metered quantity itself is never prorated: 500 + 300 = 800, not 400.
    assert sum(line.quantity for line in lines) == Decimal("800")
    # And the base line carries the prorated amount, marked as prorated.
    assert price(tariff, Decimal("800"), unit="kWh", period=HALF_MONTH).sole_line(
        "base"
    ).amount == Decimal("15.25")


def test_us_rat_012_tc7_uom_mismatch_blocks_rating_and_never_converts():
    """TC-7 — BR-RAT-038: a ccf read against a kgal tariff blocks, with a message."""
    with pytest.raises(errors.UomMismatch) as raised:
        refuse(water_tariff(), Decimal("3.72"), unit="ccf")

    message = str(raised.value)
    assert "ccf" in message and "kgal" in message  # both units named for the user
    assert "BR-RAT-038" in message


def test_us_rat_012_tc8_engine_is_pure_and_repeatable():
    """TC-8 — identical inputs, identical output, no writes, no clock."""
    first = price(water_tariff(base_charge=Decimal("12.00")), Decimal("3.72"))
    second = price(water_tariff(base_charge=Decimal("12.00")), Decimal("3.72"))

    assert first == second  # frozen dataclasses compare by value
    assert [line.amount for line in first.lines] == [line.amount for line in second.lines]


def test_us_rat_012_tc8b_pricing_source_has_no_orm_or_clock():
    """TC-8 (static half) — the pricing path reads no table and no wall clock.

    The purity test above proves repeatability; this one proves there is nothing
    to be non-deterministic WITH. A stage that grew a `.objects.` call or a
    `datetime.now()` would pass the value comparison above and fail here.
    """
    import pathlib

    root = pathlib.Path(rating_seam.__file__).resolve().parents[1] / "rating"
    sources = [root / "engine.py", root / "proration.py", *(root / "pricing").rglob("*.py")]
    assert sources, "the pricing package must exist to be checked"
    for path in sources:
        text = path.read_text()
        for forbidden in (".objects.", "datetime.now()", "timezone.now()", "import requests"):
            code = "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))
            assert (
                forbidden not in code
            ), f"{path.name} reaches for {forbidden} — the engine is pure"


def test_us_rat_012_tc9_consumption_without_a_unit_is_rejected():
    """TC-9 — CLAUDE.md hard rule 3: a unit is never assumed."""
    with pytest.raises(errors.MissingUnit):
        refuse(water_tariff(), Decimal("3.72"), unit="")


def test_us_rat_012_tc9b_a_tariff_that_cannot_price_refuses():
    """Fail closed (hard-won law 3): no price and no tier is a refusal, not 0.00."""
    with pytest.raises(errors.TariffConfigError):
        refuse(
            rating_seam.TariffConfig(
                service="electric", model="flat", billed_unit="kWh", unit_price=None
            ),
            Decimal("100"),
            unit="kWh",
        )
    with pytest.raises(errors.TariffConfigError):
        refuse(water_tariff(tiers=()), Decimal("3.72"))
    # Usage above a closed top block is unbilled usage — also a refusal
    # (BR-RAT-026: every unit bills through a tier).
    with pytest.raises(errors.TariffConfigError):
        refuse(
            water_tariff(tiers=(rating_seam.Tier(upper=Decimal("2"), unit_price=Decimal("3.00")),)),
            Decimal("3.72"),
        )


def test_us_rat_012_tc9c_a_period_with_no_cycle_refuses():
    """B4.3 needs a real cycle length; zero days is not a period."""
    with pytest.raises(errors.InvalidPeriod):
        refuse(
            water_tariff(),
            Decimal("3.72"),
            period=rating_seam.BillingPeriod(cycle_days=0, service_days=0),
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — recomputed 2026-08-10)
# generated: 2026-08-10 by story-coder (rating-engine lane — EP-RAT-05)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure engine) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_rat_012_engine.py✔ · pytest tests -m golden → 7 passed / 4 xfailed✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔ · run_gates 14 PASS/0 FAIL/1 SKIP✔
# exceptions: US-RAT-012 TC-5 (TOU) and TC-6 (sewer %-of-water) are NOT covered — neither model's configuration travels on the seam's TariffConfig, so there is nothing to drive them with. TC-10 (cross-tenant isolation) is not covered here: the engine takes no tenant argument and touches no queryset, so isolation is the CALLER's RLS boundary and belongs in the G5 suite once billing's run exists. Every amount in this file is either quoted from tests/golden/ or derived from the CONFIRMED EP-RAT-05 §7 formula and labelled as derived — no B5 figure is restated here.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
