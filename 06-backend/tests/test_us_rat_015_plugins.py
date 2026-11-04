# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-015 (rule-type plugins: one interface per pricing model, one
#           per charge amount rule — a new rule type is a new module)
#           Screens: — (nothing here is visible to a user; that is the point)
# Rules:    BR-RAT-044 (pricing models behind ONE price(...) interface; the
#           stage holds no per-model branching; registry CLOSED at import) ·
#           BR-RAT-045 (charge amount rules behind ONE amount(...) interface;
#           no implementation rounds its own return value) · BR-RAT-041 (v1 =
#           flat / percent / percent-with-minimum) · BR-RAT-003 (rounding is a
#           finalization concern, never a plugin concern) · BR-BIL-037 (the
#           stage order is data, not folklore)
# Golden:   GT-1 · GT-2 · GT-5 (priced through the registry) · GT-8 (the
#           amount-rule arithmetic) — B5 ❄️ FROZEN 2026-08-08
# Tests:    this file (US-RAT-015 TC-1/3/4/5/6/7/8)
# Impacts:  apps/rating/pricing/registry.py · apps/rating/pricing/models/** ·
#           apps/rating/pricing/amount_rules/** · apps/rating/engine.py 🔒
# ───────────────────────────────────────────────────────
"""US-RAT-015 — the engine's SHAPE, asserted rather than described.

Every test here defends a property that is invisible in the output and therefore
cannot be defended by a golden figure: that the price-usage stage names no
model, that an unregistered model refuses instead of pricing as zero, that no
plugin rounds, and that nothing at runtime can add or replace an
implementation. Those are the properties that decide what the NEXT rate shape
costs (hard-won law 1: a comment claiming them is not them).
"""

import ast
import pathlib
from decimal import Decimal

import pytest

from apps.rating import engine
from apps.rating.pricing import contracts, errors, registry, stages
from apps.rating.pricing.models import flat, tiered
from apps.rating.pricing.stages import price_usage

SUBSCRIPTION = contracts.SubscriptionContext(service="water", currency="USD")
PERIOD = contracts.PeriodShape(cycle_days=30, service_days=30, factor=Decimal(1))


def usage(amount: str, unit: str = "kgal") -> contracts.MeasuredUsage:
    value = Decimal(amount)
    return contracts.MeasuredUsage(
        billed_quantity=value, unit=unit, raw_quantity=value, multiplier=Decimal(1)
    )


def _executable_source(module) -> str:
    """A module's CODE with every docstring and comment removed.

    The grep in TC-4 has to look at what the stage DOES, not at what its
    docstring says it does not do — this file's own prose names the models it
    forbids, and so does the stage's. Parsing is the only honest way to tell
    "the code branches on a model" from "the comment mentions one".
    """
    tree = ast.parse(pathlib.Path(module.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(ast.fix_missing_locations(tree))


def test_us_rat_015_tc1_models_resolve_through_the_registry_not_a_branch():
    """TC-1 — the registry returns the same callables the modules define.

    THE ROSTER IS ASSERTED EXACTLY, and it moved on 2026-08-16: `time_of_use`,
    `percent_of_service`, `capacity` and `demand` were registered, taking the
    engine from two rate shapes to six. This assertion is what makes that a
    reviewed event rather than a silent one — a plugin appearing here without a
    lane behind it fails a test.

    ⚠ **`seasonal` JOINED THE ROSTER ON 2026-10-01 (`DEF-RAT-8832`).** This
    paragraph read *"`seasonal` is deliberately NOT in the list … it stays a
    module-shaped hole and refuses loudly"* until then. `OQ-234` was CLOSED by
    the PO on 2026-09-07 — *"please split  swithch it on"* — and the reason
    stopped being true that day: the CALLER now counts the calendar days per
    season and WE-18 is engine-verified as GT-34. TC-5 never asserted the
    seasonal refusal (it uses an invented `interval` model), so it is unchanged.
    """
    assert registry.PRICING_MODELS.resolve("flat") is flat.price
    assert registry.PRICING_MODELS.resolve("tiered") is tiered.price
    assert registry.PRICING_MODELS.names() == (
        "capacity",
        "demand",
        "flat",
        "percent_of_service",
        "seasonal",
        "tiered",
        "time_of_use",
    )


def test_us_rat_015_tc3_three_amount_rules_share_one_interface():
    """TC-3 — flat / percent / percent-with-minimum, one call shape each.

    The percent-with-minimum line is GT-8's arithmetic:
    max(5.00, 0.015 x 542.10). It is asserted UNROUNDED here (8.1315) because a
    plugin returns NUMERIC(18,6) and the caller finalizes once — GT-8's frozen
    8.13 is asserted in tests/golden/, at the finalization boundary where it
    belongs.
    """
    assert engine.amount_for(rule="flat", amount=Decimal("85.00")) == Decimal("85.00")
    assert engine.amount_for(
        rule="percent", percent=Decimal("0.40"), basis=Decimal("13.74")
    ) == Decimal("5.496")
    assert engine.amount_for(
        rule="percent_min",
        percent=Decimal("0.015"),
        basis=Decimal("542.10"),
        minimum=Decimal("5"),
    ) == Decimal("8.1315")
    # The minimum wins when the percentage does not clear it (B4.1's floor).
    assert engine.amount_for(
        rule="percent_min",
        percent=Decimal("0.015"),
        basis=Decimal("45.00"),
        minimum=Decimal("5"),
    ) == Decimal("5")
    assert registry.AMOUNT_RULES.names() == ("flat", "percent", "percent_min")


def test_us_rat_015_tc4_the_price_usage_stage_names_no_model():
    """TC-4 — grep the stage: the only model reference is the registry lookup.

    Proven RED first (hard-won law 7): with `if source.config.model == "tiered"`
    inserted into price_usage.py, this test fails naming the model it found.
    """
    body = _executable_source(price_usage)
    for model_name in ("tiered", "tou", "demand", "seasonal", "capacity", "percent_of_service"):
        assert model_name not in body, (
            f"price_usage.py names the model {model_name!r} — BR-RAT-044 says the "
            "stage carries no per-model branching; the model is a registry key."
        )
    assert "PRICING_MODELS.resolve" in body


def test_us_rat_015_tc5_an_unregistered_model_refuses_and_never_prices_zero():
    """TC-5 — fail closed (hard-won law 3): no plugin means no bill, not a $0 one."""
    with pytest.raises(errors.UnknownPricingModel) as raised:
        price_usage.price_usage(
            contracts.NormalizedInput(
                subscription=SUBSCRIPTION,
                usage=usage("3.72"),
                config=contracts.ModelConfig(model="interval", billed_unit="kgal"),
                period=PERIOD,
            )
        )
    message = str(raised.value)
    assert "interval" in message  # the model is named for the operator
    assert "flat" in message and "tiered" in message  # and so is what IS available

    with pytest.raises(errors.UnknownAmountRule):
        engine.amount_for(rule="formula", amount=Decimal("1"))


def test_us_rat_015_tc6_no_plugin_rounds_its_own_return_value():
    """TC-6 — plugins return NUMERIC(18,6); 2dp appears only at finalization."""
    lines = flat.price(
        SUBSCRIPTION,
        usage("3"),
        contracts.ModelConfig(model="flat", billed_unit="kgal", unit_price=Decimal("0.005")),
    )
    # 3 x 0.005 = 0.015 — a plugin that rounded would return 0.01 or 0.02.
    assert lines[0].amount == Decimal("0.015")
    assert isinstance(lines[0], contracts.LineCandidate)  # unrounded by TYPE

    # And the amount rules likewise: 0.015 x 542.10 = 8.1315, not 8.13.
    assert (
        engine.amount_for(
            rule="percent_min",
            percent=Decimal("0.015"),
            basis=Decimal("542.10"),
            minimum=Decimal("5"),
        )
        .as_tuple()
        .exponent
        < -2
    )


def test_us_rat_015_tc7_the_registry_is_closed_at_import_time():
    """TC-7 — no runtime path can add or replace an implementation."""
    assert registry.PRICING_MODELS.sealed is True
    assert registry.AMOUNT_RULES.sealed is True

    with pytest.raises(errors.RegistryClosed):
        registry.PRICING_MODELS.register("tenant_supplied", lambda *a, **k: ())
    with pytest.raises(errors.RegistryClosed):
        registry.AMOUNT_RULES.register("formula", lambda ctx: Decimal("0"))
    # A replacement is refused as firmly as an addition.
    with pytest.raises(errors.RegistryClosed):
        registry.PRICING_MODELS.register("flat", lambda *a, **k: ())
    assert registry.PRICING_MODELS.resolve("flat") is flat.price


def test_us_rat_015_tc8_plugins_are_pure():
    """TC-8 — a plugin receives its inputs and returns data. Nothing else."""
    config = contracts.ModelConfig(
        model="tiered",
        billed_unit="kgal",
        tiers=(
            contracts.TierSpec(upper=Decimal("2"), unit_price=Decimal("3.00")),
            contracts.TierSpec(upper=None, unit_price=Decimal("4.50")),
        ),
    )
    first = tiered.price(SUBSCRIPTION, usage("3.72"), config, period=PERIOD)
    second = tiered.price(SUBSCRIPTION, usage("3.72"), config, period=PERIOD)
    assert first == second
    # The inputs are frozen dataclasses, so a plugin cannot mutate what it got.
    with pytest.raises(Exception):
        config.tiers = ()  # type: ignore[misc]


def test_us_rat_015_stage_order_is_data_not_folklore():
    """US-BIL-029 TC-4, applied to the engine's own stages.

    The order lives in one constant; removing a stage from the engine has to
    fail a test rather than silently skip work.
    """
    # `apply_discounts` joined 2026-08-22 (DEF-502 — the pipeline had no
    # discount stage at all). After `finalize` because a scoped discount is a
    # percentage of the PRINTED amounts (BR-RAT-068); before `compute_tax`
    # because R6 precedes R7 and each tax picks its own base (BR-RAT-071/106).
    assert stages.STAGE_ORDER == (
        "normalize",
        "price_usage",
        "apply_charges",
        "finalize",
        "apply_discounts",
        "compute_tax",
        "assemble",
    )
    engine_source = pathlib.Path(engine.__file__).read_text()
    for stage_name in stages.STAGE_ORDER:
        assert f"{stage_name}_stage" in engine_source or f"{stage_name}(" in engine_source


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-015@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — recomputed 2026-08-10)
# generated: 2026-08-10 by story-coder (rating-engine lane — EP-RAT-05)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure engine) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_rat_015_plugins.py✔ · pytest tests -m golden → 7 passed / 4 xfailed✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔ · run_gates 14 PASS/0 FAIL/1 SKIP✔
# exceptions: US-RAT-015 TC-2 (capacity through the registry) is NOT covered — no capacity plugin is registered, because capacity configuration cannot travel on the seam's TariffConfig and GT-15 is PROPOSED rather than frozen. TC-9 (two tenants pricing the same model concurrently) is not covered here: the registry holds callables and no tenant state, and the tariff version each tenant prices with is resolved by the CALLER under RLS — that assertion belongs in the G5 isolation suite once billing's run exists.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
