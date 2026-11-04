# ── Trace ──────────────────────────────────────────────
# Rule:     BR-RAT-094 (PO ruling 2026-08-20, DEF-411 option B) — "Keep the one
#           that was signed off for its stated purpose, put a gate on it, and
#           delete the tax one. Nobody has ever defended letting a plan skip a
#           state tax."
# Defect:   DEF-411 — `plan_charge_rules.amount_override` and
#           `plan_tax_rules.rate_override` both let a PLAN set a price, which
#           CR-013 part 5 forbids ("a plan may not invent a price").
# Shape:    Two claimants, two different answers, because only one of them has a
#           ratified use. BR-RAT-043 defends the charge override for ONE stated
#           purpose — "plan discounts = negative-amount charge rules on the
#           plan" — so it survives GATED TO NEGATIVE. `rate_override` has no
#           such defence and is refused outright.
# Prove-it: run this file against the previous commit and the three refusal
#           tests fail (a positive override saved; `rate_override` accepted),
#           which is the RED that hard-won law 7 requires before trusting green.
# ───────────────────────────────────────────────────────
"""BR-RAT-094 — a plan attaches prices; it never sets one."""

from decimal import Decimal

import pytest

from apps.rating import services
from core import errors

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import api_call, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _seed(env):
    """The smallest plan payload the wizard path accepts, plus two charges."""
    from tests.test_us_rat_plans import _wizard_payload, _wizard_seed

    seed = _wizard_seed(env)
    env.charge("PAPERLESS", "Paperless discount", charge_type="recurring", amount="2.00")
    return seed, _wizard_payload


def test_br_rat_094__a_negative_amount_override_is_still_accepted(env):
    """BR-RAT-043's ratified use survives the gate — that is the point of (B)."""
    seed, payload_for = _seed(env)
    payload = payload_for(
        env,
        seed,
        charge_rules=[
            {"charge": "PAPERLESS", "amount_override": "-2.00", "recurrence": "recurring"}
        ],
    )
    with tenant_ctx(env.tenant):
        plan = services.create_plan(env.admin, payload)
    assert Decimal(plan["charge_rules"][0]["amount_override"]) == Decimal("-2.00")


def test_br_rat_094__a_positive_amount_override_is_refused(env):
    """A plan raising a charge above its charge code IS a plan setting a price."""
    seed, payload_for = _seed(env)
    payload = payload_for(
        env,
        seed,
        charge_rules=[
            {"charge": "PAPERLESS", "amount_override": "4.00", "recurrence": "recurring"}
        ],
    )
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as raised:
        services.create_plan(env.admin, payload)
    fields = raised.value.field_errors
    assert any(
        error["field"].endswith("amount_override")
        and error["message_key"] == "rating.above_maximum"
        and error["params"]["maximum"] == "0"
        for error in fields
    ), fields


def test_br_rat_094__zero_is_the_boundary_and_is_accepted(env):
    """The gate is `> 0`, not `>= 0`: a zeroed charge is a 100% discount."""
    seed, payload_for = _seed(env)
    payload = payload_for(
        env,
        seed,
        charge_rules=[
            {"charge": "PAPERLESS", "amount_override": "0", "recurrence": "recurring"}
        ],
    )
    with tenant_ctx(env.tenant):
        plan = services.create_plan(env.admin, payload)
    assert Decimal(plan["charge_rules"][0]["amount_override"]) == Decimal("0")


def test_br_rat_094__a_plan_tax_rule_may_not_carry_a_rate_override(env):
    """"Nobody has ever defended letting a plan skip a state tax."""
    seed, payload_for = _seed(env)
    tax = env.tax("TX State Utility Tax", rate="0.0625")
    payload = payload_for(
        env,
        seed,
        tax_rules=[{"jurisdiction": tax["jurisdiction"]["id"], "rate_override": "0.0100"}],
    )
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as raised:
        services.create_plan(env.admin, payload)
    assert any(
        error["field"].endswith("rate_override") for error in raised.value.field_errors
    ), raised.value.field_errors


def test_br_rat_094__the_served_plan_never_carries_a_tax_rate_override(env):
    """Not merely un-writable: the read path states NULL, so no screen shows one."""
    seed, payload_for = _seed(env)
    tax = env.tax("TX State Utility Tax", rate="0.0625")
    payload = payload_for(
        env, seed, tax_rules=[{"jurisdiction": tax["jurisdiction"]["id"]}]
    )
    with tenant_ctx(env.tenant):
        plan = services.create_plan(env.admin, payload)
    assert plan["tax_rules"][0]["rate_override"] is None
