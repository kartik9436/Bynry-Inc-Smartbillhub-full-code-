# ── Trace ──────────────────────────────────────────────
# Change:  CR-167-BRC10 follow-up (lane PLAN-MONEY) — `OQ-RAT-12786` CLOSED
#          2026-10-03, PO verbatim: *"(a) Class or size: the deposit table gets
#          a size column, like charge codes have."*
# Rules:   BR-RAT-020 (SUPERSEDED in part 2026-10-03 — a deposit is priced by
#          customer class OR by meter size) · BR-RAT-023 as amended (the plan
#          names its deposit as a refundable charge code) · BR-BIL-012
# Red:     written FIRST and run against tip `8cfa7ab19` (quoted in CR-167
#          §15): the write refused the code with
#          `rating.plans.deposit_code_priced_by_size`, form-options left it
#          out, and the read raised `NotImplementedError("OQ-RAT-12786")`.
# ───────────────────────────────────────────────────────
"""A deposit priced by meter size, end to end on the rating side.

THE WORKED FIGURE THE PO WAS SHOWN: a deposit code priced 5/8" **$150.00** and
2" **$600.00** asks a 5/8" connection $150.00 and a 2" connection $600.00. The
size is the connection size of the SERVICE THE CODE NAMES on the customer's
unit — `seams.connection_size_for`, the same seam billing sizes a base from —
so it is monkeypatched here and proved for real on PostgreSQL through the
screen (CR-167 §15).
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.rating import models, plan_reads, plan_writes, seams, selectors, services
from core import errors

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import RES_WATER_TIERS, tenant_ctx

pytestmark = pytest.mark.django_db

TODAY = date(2026, 10, 3)
UNIT = str(uuid4())
WATER_SIZES = (("W-58", 'Water 5/8"'), ("W-2", 'Water 2"'))


@pytest.fixture(autouse=True)
def _today(monkeypatch):
    monkeypatch.setattr(seams, "tenant_today", lambda: TODAY)


def _sizes(tenant):
    from apps.tenancy import models as tenancy_models

    for code, name in WATER_SIZES:
        tenancy_models.MeterSizeClass.objects.update_or_create(
            tenant=tenant, code=code, defaults={"name": name, "active": True, "is_system": True}
        )


def _late_fee_code(env):
    with tenant_ctx(env.tenant):
        if models.Charge.objects.filter(code="LATE").exists():
            return
    env.charge(
        "LATE",
        "Late payment fee",
        charge_type="penalty",
        amount_rule="percent_with_minimum",
        amount=None,
        percent="0.015",
        min_amount="5.00",
    )


def _world(env):
    env.enable("water")
    _late_fee_code(env)
    _sizes(env.tenant)
    schedule = env.tiered_schedule("Res Water", "water", RES_WATER_TIERS)
    with tenant_ctx(env.tenant):
        services.create_charge(
            env.admin,
            {
                "code": "DEP-SIZE",
                "name": "Security deposit by size",
                "charge_type": "refundable",
                "service": "water",
                "amount_rule": "flat",
                "is_base": False,
                "size_amounts": [
                    {"size_class": "W-58", "amount": "150.00"},
                    {"size_class": "W-2", "amount": "600.00"},
                ],
                "effective_from": "2000-01-01",
            },
        )
    return schedule


def _contract(schedule, **overrides):
    body = {
        "details": {"name": "Residential City Plan", "code": "RCP", "customer_classes": []},
        "services": [{"service": "water", "schedule": schedule["id"], "surcharged": False}],
        "charge_codes": [],
        "taxes": [],
        "deposits": [],
        "discounts": [],
        "budget_billing": False,
        "minimum_bill_amount": "10.00",
        "effective_from": "2026-09-01",
        "publish": False,
    }
    body.update(overrides)
    return body


def _plan(env, schedule):
    with tenant_ctx(env.tenant):
        return plan_writes.create(
            env.admin, _contract(schedule, deposits=[{"charge": "DEP-SIZE"}], publish=True)
        )


def test_a_deposit_code_priced_by_size_is_named_on_a_plan(env):
    """Red at the tip: `rating.plans.deposit_code_priced_by_size`."""
    plan = _plan(env, _world(env))
    deposits = plan["deposits"]
    assert [row["ref"]["code"] for row in deposits] == ["DEP-SIZE"]
    assert deposits[0]["priced_by"] == "size"
    assert [(r["class_or_size_label"], r["amount_display"]) for r in deposits[0]["rows"]] == [
        ('Water 2"', "600.00"),
        ('Water 5/8"', "150.00"),
    ]


def test_form_options_offer_a_deposit_code_priced_by_size(env):
    """Red at the tip: the code was dropped from `deposit_codes`."""
    _world(env)
    with tenant_ctx(env.tenant):
        options = plan_reads.form_options()
    offered = {row["ref"]["code"]: row for row in options["deposit_codes"]}
    assert "DEP-SIZE" in offered
    assert offered["DEP-SIZE"]["priced_by"] == "size"


@pytest.mark.parametrize("size, asked", [("W-58", Decimal("150.00")), ("W-2", Decimal("600.00"))])
def test_the_connection_size_picks_the_deposit(env, monkeypatch, size, asked):
    """The PO's figure: 5/8" asks $150.00, 2" asks $600.00. Red at the tip:
    `NotImplementedError: OQ-RAT-12786`."""
    plan = _plan(env, _world(env))
    seen = []

    def _size(unit_id, service_code):
        seen.append((unit_id, service_code))
        return size

    monkeypatch.setattr(seams, "connection_size_for", _size)
    with tenant_ctx(env.tenant):
        residential = seams.account_type_id_by_code("residential")
        answer = selectors.deposit_rule_for(plan["id"], residential, unit_id=UNIT)
    assert answer["amount"] == Decimal(asked)
    assert seen == [(UNIT, "water")], "the size of the service the code names, on this unit"


@pytest.mark.parametrize("size, refusal", [(None, "size_not_recorded"), ("W-1", "size_not_priced")])
def test_a_size_the_code_does_not_price_is_refused_by_name_never_none(env, monkeypatch, size, refusal):
    """`None` would read as *this plan asks no deposit* and connect the
    customer with none taken."""
    plan = _plan(env, _world(env))
    monkeypatch.setattr(seams, "connection_size_for", lambda unit_id, service_code: size)
    with tenant_ctx(env.tenant):
        residential = seams.account_type_id_by_code("residential")
        answer = selectors.deposit_rule_for(plan["id"], residential, unit_id=UNIT)
    assert answer is not None
    assert answer["amount"] is None
    assert answer["refusal"] == refusal
    assert answer["code"] == "DEP-SIZE"


def test_the_customers_deposit_step_refuses_an_unpriced_size_by_name():
    """customers reads the refusal as a refusal, never as *asks none*."""
    from apps.customers import deposit

    with pytest.raises(errors.ValidationError) as caught:
        deposit.plan_asks_deposit(
            {"amount": None, "currency": None, "refusal": "size_not_priced", "code": "DEP-SIZE", "size_class": "W-1"}
        )
    assert caught.value.message_key == "customers.deposit.sizeNotPriced"
    assert deposit.plan_asks_deposit({"amount": Decimal("600.00"), "currency": "USD"}) == Decimal("600.0000")
    assert deposit.plan_asks_deposit(None) is None


def test_a_deposit_priced_by_class_is_unchanged(env):
    """Not a cent moves for a class-priced code: $150.00, no size asked."""
    env.enable("water")
    _late_fee_code(env)
    schedule = env.tiered_schedule("Res Water", "water", RES_WATER_TIERS)
    env.charge("DEPOSIT", "Security deposit", charge_type="refundable", amount="150.00")
    with tenant_ctx(env.tenant):
        plan = plan_writes.create(
            env.admin, _contract(schedule, deposits=[{"charge": "DEPOSIT"}], publish=True)
        )
        residential = seams.account_type_id_by_code("residential")
        answer = selectors.deposit_rule_for(plan["id"], residential)
    assert answer["amount"] == Decimal("150.00")
    assert "refusal" not in answer
