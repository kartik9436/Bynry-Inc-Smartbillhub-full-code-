# ── Trace ──────────────────────────────────────────────
# Rules:   BR-RAT-088 (CONFIRMED 2026-08-20 — the charge code owns the base
#          amount, and is the ONLY source of one) · BR-BIL-870 (a rule of the
#          chain prices a real bill where the deployment names it; the default
#          names R3 and R4 since 2026-09-01) · BR-BIL-872 (a switched rule's
#          refusal refuses the ACCOUNT and there is no fallback) ·
#          BR-BIL-873 (R3 and R4 switch together) · BR-RAT-120 (the sequencing
#          clause, amended 2026-09-01)
# Defects: DEF-2923 (CLOSED here) · DEF-2922 (the constant decides nothing)
# CR:      CR-057
# Tests:   this file
# ───────────────────────────────────────────────────────
"""`DEF-2923` — THE BASE-CHARGE-CODE GATE FOLLOWS THE SWITCH.

WHAT WENT WRONG, IN ONE SENTENCE
--------------------------------
The Product Owner ruled R3 and R4 on (2026-09-01, *"Can you wire them in now -
R3 and R4"*). The flip made seven cases of the switch suite fail, and not one
was a fixture problem: **a tenant that had declared no `is_base` charge code
for a service had every account of that service REFUSED on its next bill run**,
by name, with no fallback (`BR-BIL-872`).

That is `BR-RAT-088` behaving exactly as signed — with R4 served, the charge
code is the ONLY source of a base amount — meeting a live default for the first
time.

WHY NO EXISTING CHECK SAW IT
----------------------------
`_guard_base_charge_code` already refused to activate a schedule for a service
with no base code, but only for a tenant that had declared **some** base code
somewhere. That self-activating qualifier was correct while nothing was
switched on: a tenant with none had simply not adopted the model and went on
pricing the old way. **The day R4 is served it stops being correct**, because
there is no old way left for the chain to price from.

And both preflights ran over three utilities that all carry seeded base codes
(`DEF-455`), so `163 accounts · 0 refused` was true and incomplete — a
statement about three well-configured utilities that says nothing about a
fourth.

WHAT THIS FILE PINS
-------------------
The gate now consults `steps_served_by_chain()`, so the two states are opposite
and both are asserted here:

  * **pair ON (the shipped default)** — a tenant with NO base charge code
    anywhere is REFUSED AT SCHEDULE ACTIVATION, naming `BR-RAT-088` and the
    service. The refusal has moved from billing day to a settings screen, where
    the sentence names the fix and nobody's bill has stopped. TC1, TC2.
  * **pair OFF (the one-line rollback)** — the SAME tenant activates the SAME
    schedule successfully. Behaviour before the ruling is preserved exactly,
    which is what makes the rollback real. TC3.

⚠ **TC3 IS THE HALF THAT KEEPS THIS HONEST.** A gate that fired unconditionally
would pass TC1 and TC2 and would refuse every activation on every unadopted
tenant the day it shipped — the exact failure the original qualifier existed to
prevent. Asserting only the refusal would not tell those two apart.
"""

from __future__ import annotations

import pytest
from django.test import override_settings

from apps.billing import resolution_switch
from apps.rating import models, services
from core import errors

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import RES_WATER_TIERS, tenant_ctx

pytestmark = pytest.mark.django_db


def _a_complete_water_schedule(env):
    """A draft that is complete in every way EXCEPT the base charge code."""
    return services.create_rate_schedule(
        env.admin,
        {
            "name": "Res Water · Inclining",
            "service": "water",
            "model": "tiered",
            "structure": {"tiers": RES_WATER_TIERS},
        },
    )


def _activate(env, draft_id):
    return services.activate_rate_schedule(
        env.admin,
        draft_id,
        {
            "model": "tiered",
            "uom": "kgal",
            "effective_from": "2026-09-01",
            "structure": {"tiers": RES_WATER_TIERS},
        },
    )


def test_TC0_the_precondition__this_tenant_has_declared_NO_base_charge_code(env):
    """The fixture this file rests on, asserted rather than assumed.

    Every case below is about *a tenant that has not adopted declared base
    codes*. If the fixture ever seeds one, TC3 would still pass and TC1/TC2
    would fail for a reason that has nothing to do with the switch — so the
    precondition is checked in its own case, where the failure names itself.
    """
    with tenant_ctx(env.tenant):
        assert not models.Charge.objects.filter(
            tenant=env.tenant, is_base=True, deleted_at__isnull=True
        ).exists(), "this suite needs a tenant that has declared no is_base code"


def test_TC1_with_the_pair_ON_activation_is_REFUSED_naming_the_rule_and_the_service(env):
    """The shipped default serves R3 and R4, so the gate fires for EVERY tenant.

    This is `DEF-2923` closed at its cause: the refusal happens HERE, while
    somebody is configuring, instead of on the day the money is due.
    """
    assert resolution_switch.steps_served_by_chain() == frozenset({"R3", "R4"}), (
        "this case is about the SHIPPED default serving the pair; if that "
        "changes, the case below is asserting nothing."
    )
    with tenant_ctx(env.tenant):
        draft = _a_complete_water_schedule(env)
        with pytest.raises(errors.BizError) as refusal:
            _activate(env, draft["id"])

    problem = refusal.value
    assert problem.code == errors.BIZ_STATE
    # The RULE is named, so the person fixing it can find what decided this.
    assert problem.br_ref == "BR-RAT-088"
    # And the SERVICE is named — a refusal that does not say which service is a
    # refusal nobody can act on (BR-SHL-020).
    assert problem.params.get("service") == "water"
    assert problem.message_key == "rating.schedules.no_base_charge_code"


def test_TC2_the_refusal_is_CURABLE_by_doing_exactly_what_it_says(env):
    """⚠ **A REFUSAL THAT CANNOT BE CLEARED IS AN OUTAGE, NOT A GATE.**

    `BR-RAT-120` accepted a real cost — *"the system refuses bills that price
    perfectly well today"* — on the understanding that the refusal is curable.
    So this asserts the cure, in the words the message uses: declare the base
    charge code for the service, and the same activation succeeds.
    """
    with tenant_ctx(env.tenant):
        draft = _a_complete_water_schedule(env)
        with pytest.raises(errors.BizError):
            _activate(env, draft["id"])

        # Do what the sentence says.
        models.Charge.objects.create(
            tenant=env.tenant,
            code="BASE-W",
            name="Water base service",
            charge_type="recurring",
            amount_rule="flat",
            amount="8.0000",
            service=tenancy_service(env, "water"),
            is_base=True,
        )

        activated = _activate(env, draft["id"])

    assert activated["current_version"] is not None


@override_settings(BILLING_RESOLUTION_STEPS="")
def test_TC3_with_the_pair_OFF_the_SAME_tenant_activates_the_SAME_schedule(env):
    """THE ROLLBACK, AND THE PROOF THE GATE DID NOT SIMPLY BECOME UNCONDITIONAL.

    `SBH_BILLING_RESOLUTION_STEPS=` emptied is the documented one-line rollback.
    A deployment that types it is back to the behaviour that shipped before the
    ruling, and this case is what says so: a tenant that has declared no base
    charge code anywhere activates its schedule exactly as it always could.

    ⚠ **WITHOUT THIS CASE, A GATE THAT REFUSED EVERY UNADOPTED TENANT
    UNCONDITIONALLY WOULD PASS THIS FILE** — and that is the failure the
    original *"where the plan expects one"* qualifier was written to prevent.
    """
    assert resolution_switch.steps_served_by_chain() == frozenset()
    with tenant_ctx(env.tenant):
        draft = _a_complete_water_schedule(env)
        activated = _activate(env, draft["id"])

    assert activated["current_version"] is not None


def tenancy_service(env, code):
    from apps.tenancy import models as tenancy_models

    return tenancy_models.Service.objects.get(code=code)


# ── Lifecycle ─────────────────────────────────────────────
# packet: BR-RAT-088 · BR-BIL-870/872/873 · BR-RAT-120 (amended 2026-09-01) ·
#         DEF-2923 · CR-057 · decision log 2026-09-01
# proved RED: TC1 and TC2 fail with `SBH_BILLING_RESOLUTION_STEPS=` (the gate
#         correctly does not fire when the chain does not state the base), and
#         TC3 fails when `_the_chain_states_the_base()` is forced True — so
#         each half of the condition is shown to be load-bearing.
