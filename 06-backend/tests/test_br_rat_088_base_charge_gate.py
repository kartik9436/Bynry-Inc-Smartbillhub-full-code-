# ── Trace ──────────────────────────────────────────────
# Rules:    BR-RAT-088 (the CHARGE CODE owns the base — PO ruling 2026-08-20,
#           closing B1/OQ-238 against two CONFIRMED rules) · design §A3 (the
#           activation gate, moved there from part 5 step 4's warning)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""§A3's activation gate, and the qualifier that keeps it from breaking everyone.

WHY A GATE AND NOT A WARNING
----------------------------
With the charge code owning the base, a service whose base code is missing bills
**no base at all**. Every line on that bill is individually correct and the total
is short by the base — the same silent shape as the double-base §A3 forbids, in
the other direction. §A3 moved it from part 5 step 4's *"flags a bound schedule
with no base charge"* to a refusal for exactly that reason.

THE QUALIFIER IS THE INTERESTING PART: *"where the plan expects one"*
--------------------------------------------------------------------
`Charge.is_base` defaults False, so on the day this shipped no tenant had
declared a base code anywhere. A gate that fired unconditionally would have
refused EVERY schedule activation in the product. So adoption is inferred from
the tenant's own data, and the two tests below are the two sides of that:
a tenant with no declared base codes is untouched; a tenant with some is held to
it. The gate turns itself on per tenant, which is why there is no follow-up
commit needed to "enable" it — the failure mode CLAUDE.md law 1 exists to warn
about.
"""

from __future__ import annotations

import pytest

from django.test import override_settings

from apps.rating import models, services
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — env/growth_plan fixtures
from tests.test_us_rat_helpers import RES_WATER_TIERS, tenant_ctx

pytestmark = pytest.mark.django_db


def nothing_switched_on():
    """The OFF state, STATED rather than inherited — `DEF-2817`.

    ⚠ **THE SHIPPED DEFAULT IS NO LONGER EMPTY, SO A CASE THAT MEANS *"with
    nothing switched on"* MUST SAY SO.** `test_br_bil_870_resolution_switch.py`
    adopted this posture on 2026-09-01 in these words: *"Read a use of this as
    here the switch is OFF, and that is the point, never as here the switch
    happens to be off."* It wrote the helper for its own cases and the rule did
    not travel; the case below is what that cost.

    A deployment that has typed the one-line rollback
    (`SBH_BILLING_RESOLUTION_STEPS=` emptied) is exactly this state, so a case
    written this way is also the one that keeps proving the rollback still
    works.
    """
    return override_settings(BILLING_RESOLUTION_STEPS="")


def test_br_rat_088_gate__a_tenant_with_NO_declared_base_codes_is_untouched(env):
    """The self-activating qualifier, **with the ruled chain NOT serving R4**.

    ⚠ **THIS CASE'S SUBJECT MOVED UNDER IT ON 2026-09-01 AND THE DOCSTRING USED
    TO SAY THE OPPOSITE OF THE RULING (`DEF-2817`).** It read *"Today's
    behaviour, preserved exactly. If this fails, the gate shipped in a form that
    refuses every activation in the product"* — a correct alarm to write on
    2026-08-20, and the reverse of what `DEF-2923` established: where the chain
    serves R4 the gate is MEANT to fire for a tenant that has declared no base
    code, because with R4 on the charge code is the only source of a base and
    `BR-BIL-872` gives the refusal no fallback.
    `test_def2923_base_code_gate_follows_the_switch.py::TC1` asserts exactly
    that refusal and passes, so the two files contradicted each other and only
    one of them said which switch state it meant.

    So this case now STATES the state it is about. What it still proves is the
    half that is still true and still matters: with nothing switched on, a
    tenant that has never declared a base code activates schedules exactly as it
    did before, and the gate has not been shipped in a form that refuses every
    activation in the product.

    `declare_base=False` because the ABSENCE is this case's subject — the
    fixture must not hand it the very row it is testing the absence of.
    """
    env.enable("water")
    with nothing_switched_on():
        schedule = env.tiered_schedule(
            "Res Water · Inclining", "water", RES_WATER_TIERS, declare_base=False
        )
    assert schedule["id"]


def test_br_rat_088_gate__a_tenant_that_HAS_declared_one_is_held_to_it(env):
    """The tenant has moved to declared base codes — for ELECTRIC. Activating a
    WATER schedule must now refuse, because water has none and a bill for it
    would carry no base at all."""
    env.enable("water", "electric")
    electric_base = env.charge("BASE-E", "Electric base service", service="electric")
    with tenant_ctx(env.tenant):
        models.Charge.objects.filter(pk=electric_base["id"]).update(is_base=True)

    # `declare_base=False`: WATER having no base code is the whole case, so the
    # fixture must not declare one on the way past (`DEF-2965`).
    with pytest.raises(Exception) as raised:
        env.tiered_schedule(
            "Res Water · Inclining", "water", RES_WATER_TIERS, declare_base=False
        )
    assert "BR-RAT-088" in str(raised.value) or "no_base_charge_code" in str(raised.value)


def test_br_rat_088_gate__declaring_the_services_OWN_base_lets_it_activate(env):
    """The other half: the gate is satisfied by data, not by disabling it."""
    env.enable("water")
    water_base = env.charge("BASE-W", "Water base service", service="water")
    with tenant_ctx(env.tenant):
        models.Charge.objects.filter(pk=water_base["id"]).update(is_base=True)

    # `declare_base=False`: this case proves the gate is satisfied BY DATA the
    # test itself declared, so the fixture declaring more would hide which row
    # let the activation through.
    schedule = env.tiered_schedule(
        "Res Water · Inclining", "water", RES_WATER_TIERS, declare_base=False
    )
    assert schedule["id"]


# ── DEF-372 · the declaration has a DOOR ───────────────────────────────────
#
# ⚠ EVERY TEST ABOVE SETS THE FLAG WITH `.update(is_base=True)`, AND THAT IS THE
# DEFECT THEY COULD NOT SEE. A queryset update is a door no user has: until
# 2026-08-21 `CHARGE_FIELDS` refused `is_base` on write and `charge_row` never
# served it, so the gate above was correct, tested, green — and **unreachable on
# every tenant in the product**, because its own qualifier (fire only where the
# tenant has SOME declared base) can never hold for a tenant that cannot declare
# one. Hard-won law 2, with a passing suite over it.
#
# These cases go through the SERVICE a screen calls, which is the only thing
# that can tell the two states apart. CHG-02 is the screen (§18 row 9).


def test_def_372__is_base_can_be_DECLARED_through_the_write_path_a_screen_uses(env):
    """`create_charge` accepts the flag, and `charge_row` serves it back."""
    env.enable("water")
    created = env.charge("BASE-W", "Water base service", service="water", is_base=True)
    assert created["is_base"] is True

    # …and it is a real column value, not an echo of the payload.
    with tenant_ctx(env.tenant):
        assert models.Charge.objects.get(pk=created["id"]).is_base is True


def test_def_372__the_gate_fires_on_a_base_declared_the_way_a_user_declares_one(env):
    """The whole chain, with no ORM back door in it: a tenant declares an
    ELECTRIC base through the write path, and a WATER activation is refused."""
    env.enable("water", "electric")
    env.charge("BASE-E", "Electric base service", service="electric", is_base=True)

    # `declare_base=False`: WATER having no base code is the whole case, so the
    # fixture must not declare one on the way past (`DEF-2965`).
    with pytest.raises(Exception) as raised:
        env.tiered_schedule(
            "Res Water · Inclining", "water", RES_WATER_TIERS, declare_base=False
        )
    assert "BR-RAT-088" in str(raised.value) or "no_base_charge_code" in str(raised.value)


def test_def_372__a_charge_that_declares_nothing_reads_back_False(env):
    """The default is unchanged, so no existing row silently becomes a base."""
    env.enable("water")
    assert env.charge("CONN", "New connection fee")["is_base"] is False


def test_def_372__the_declaration_can_be_withdrawn_through_the_same_door(env):
    """`update_charge` takes it too — a base declared in error is fixable
    without a database console."""
    env.enable("water")
    created = env.charge("BASE-W", "Water base service", service="water", is_base=True)
    with tenant_ctx(env.tenant):
        updated = services.update_charge(env.admin, created["id"], {"is_base": False, "effective_from": "2000-01-01"})
    assert updated["is_base"] is False
