# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-RAT-10026 — a second Residential base code for one service was
#           refused ("BASE-E already covers Residential.") at step 1 and at Create.
# Ruling:   PO 2026-10-09, decision log "PO RULING — A SERVICE MAY HOLD TWO OR
#           MORE BASE CODES FOR THE SAME CUSTOMER CLASS; THE "ALREADY COVERS"
#           REFUSAL GOES …" — PO, verbatim: *"yes please do it"*. Supersedes ONE
#           sentence of 2026-10-06 (*"user will not hvae same base charge for
#           same customer class"*) and nothing else.
# Rules:    BR-RAT-088 / BR-RAT-1025 as amended 2026-10-09
# ───────────────────────────────────────────────────────
"""Two base codes for one service and one customer class, each billed only
where a rate schedule NAMES it.

The figures, as the user reported them (City of Queen West) and as the ruling
states them:

* Electric has BASE-E (Residential) and BASE-E-OUT (Residential, suburban).
  Both SAVE — before the fix the second was refused with
  ``rating.charges.base_already_covered`` naming BASE-E.
* Two every-class codes, and an every-class beside a one-class code, save too.
  Code STRINGS stay unique (a second ``BASE-E`` is still refused).
* The bill reads only the code the rate schedule names: the schedule naming
  W-RES ($8.00) bills $8.00, the one naming W-RES-OUT ($11.50) bills $11.50; a
  schedule naming none bills $0.00 with the *Choose a base code* warning — never
  *"2 base charge codes"* and never a guess.

WHAT WOULD PASS WRONGLY: a selector that returned the first same-class code
regardless of ``named_code`` would pass the W-RES case — the W-RES-OUT case is
the one that tells the two codes apart, so both are asserted on the same account.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import transaction

from apps.billing import bill_warnings
from apps.rating import models as rating_models
from apps.rating import selectors, services
from core import errors

from tests.test_def_2381_customer_type_not_covered import _typed
from tests.test_def_438_parity import _account_on, _price_live, _water_plan
from tests.test_def_rat_5782_the_bill_honours_the_named_base_code import (
    _base_code,
    _water_base,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos, dana
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — env
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

WATER = "water"
W_RES = Decimal("8.00")
W_RES_OUT = Decimal("11.50")


def _base(env, code, amount, *, service="electric", classes=None):
    return services.create_charge(
        env.admin,
        {
            "code": code,
            "name": f"{code} base",
            "service": service,
            "charge_type": "recurring",
            "amount_rule": "flat",
            "amount": amount,
            "is_base": True,
            "effective_from": "2000-01-01",
            **({"applies_to_customer_classes": classes} if classes else {}),
        },
    )


# ── the save ───────────────────────────────────────────────────────────────
def test_two_residential_electric_base_codes_both_save(env):
    """The reported case. RED before the fix: ValidationError
    ``rating.charges.base_already_covered`` naming BASE-E."""
    env.enable("electric")
    with tenant_ctx(env.tenant):
        _base(env, "BASE-E", "12.00", classes=["residential"])
        row = _base(env, "BASE-E-OUT", "14.00", classes=["residential"])
        codes = sorted(
            rating_models.Charge.objects.filter(
                tenant=env.tenant, is_base=True, service__code="electric", deleted_at__isnull=True
            ).values_list("code", flat=True)
        )
    assert row["code"] == "BASE-E-OUT"
    assert codes == ["BASE-E", "BASE-E-OUT"]


def test_two_every_class_codes_and_an_every_class_beside_a_one_class_code_save(env):
    env.enable("water")
    with tenant_ctx(env.tenant):
        _base(env, "W-ALL", "8.00", service=WATER)
        _base(env, "W-ALL-2", "9.00", service=WATER)  # was refused naming W-ALL
        _base(env, "W-COM", "15.00", service=WATER, classes=["commercial"])
        _base(env, "W-COM-2", "16.00", service=WATER, classes=["commercial"])  # was refused naming W-COM


def test_editing_a_base_code_into_a_class_another_holds_saves(env):
    env.enable("electric")
    with tenant_ctx(env.tenant):
        _base(env, "BASE-E", "12.00", classes=["residential"])
        com = _base(env, "BASE-E-COM", "20.00", classes=["commercial"])
        updated = services.update_charge(
            env.admin, com["id"], {"applies_to_customer_classes": ["residential"]}
        )
    assert updated["applies_to_customer_classes"] == ["residential"]


def test_the_code_string_is_still_unique(env):
    """Existing uniqueness is untouched: a second ``BASE-E`` is still refused —
    only the class-overlap refusal went."""
    env.enable("electric")
    with tenant_ctx(env.tenant):
        _base(env, "BASE-E", "12.00", classes=["residential"])
        with pytest.raises(errors.ValidationError) as refused:
            with transaction.atomic():
                _base(env, "BASE-E", "14.00", classes=["residential"])
    assert refused.value.message_key != "rating.charges.base_already_covered"


def test_the_step_one_probe_and_its_route_are_gone():
    """The warning on New/Edit charge code step 1 is retired with the refusal:
    nothing is left to warn about."""
    from apps.rating import api as rating_api

    assert not hasattr(services, "base_code_clash")
    assert not hasattr(services, "base_codes_clash")
    assert not hasattr(rating_api, "charge_base_clash")
    assert not any("base-clash" in str(route.pattern) for route in rating_api.urlpatterns)


# ── the bill ───────────────────────────────────────────────────────────────
@pytest.fixture
def _cycle_and_water(monkeypatch):
    from apps.customers import selectors as customer_selectors
    from apps.metering import selectors as metering_selectors

    monkeypatch.setattr(
        metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "C-01", "name": "Cycle 1", "due_days": 21},
    )
    monkeypatch.setattr(customer_selectors, "billed_service_codes_for", lambda *_a, **_k: (WATER,))


def _name_on_schedule(plan, charge):
    """Point this plan's water schedule at ``charge`` — step 1 of the rate-schedule
    wizard. ``None`` clears it."""
    tariff_ids = rating_models.PlanRateSchedule.objects.filter(rate_plan=plan).values_list(
        "tariff_id", flat=True
    )
    rating_models.TariffVersion.objects.filter(tariff_id__in=list(tariff_ids)).update(
        base_charge_code_id=None if charge is None else charge.id
    )


def _warned(data):
    return [row["params"]["service_code"] for row in data.warnings if row["key"] == bill_warnings.BASE_NOT_SET]


def test_each_schedule_bills_its_own_same_class_code_and_none_bills_zero(
    brazos, dana, _cycle_and_water
):
    """One residential account; its schedule names W-RES, then W-RES-OUT, then
    nothing. Each answer is the named code's own figure; nothing named is
    $0.00 + the warning, never "2 base charge codes for water"."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _typed(account, "residential")
        w_res = _base_code(brazos, "W-RES", W_RES, classes=["residential"])
        w_res_out = _base_code(brazos, "W-RES-OUT", W_RES_OUT, classes=["residential"])

        _name_on_schedule(plan, w_res)
        named_res = _price_live(account)
        _name_on_schedule(plan, w_res_out)
        named_out = _price_live(account)
        _name_on_schedule(plan, None)
        named_none = _price_live(account)

    assert (_water_base(named_res), _warned(named_res)) == (W_RES, [])
    assert (_water_base(named_out), _warned(named_out)) == (W_RES_OUT, [])
    assert _water_base(named_none) == Decimal("0")
    assert _warned(named_none) == [WATER]


def test_the_selector_and_the_seam_narrow_to_the_named_code(brazos, dana):
    """The two configuration readers (plan list base total, rate-change impact,
    portal standing charge) read the same narrowing."""
    from apps.rating import seams

    with tenant_ctx(brazos):
        _water_plan(brazos, base_code=False)
        _base_code(brazos, "W-RES", W_RES, classes=["residential"])
        _base_code(brazos, "W-RES-OUT", W_RES_OUT, classes=["residential"])
        res = selectors.base_charge_from_charge_code(WATER, customer_class="residential", named_code="W-RES")
        out = selectors.base_charge_from_charge_code(WATER, customer_class="residential", named_code="W-RES-OUT")
        none = selectors.base_charge_from_charge_code(WATER, customer_class="residential", named_code=None)
        seam_out = seams.base_charge_for(WATER, customer_class="residential", named_code="W-RES-OUT")
    assert (res["code"], Decimal(res["amount"])) == ("W-RES", W_RES)
    assert (out["code"], Decimal(out["amount"])) == ("W-RES-OUT", W_RES_OUT)
    assert none["refusal_reason"] == selectors.BASE_NOT_NAMED and none["not_set"] is True
    assert "base charge codes for" not in (none["refusal"] or "")
    assert (seam_out["refusal"], Decimal(seam_out["amount"])) == (None, W_RES_OUT)
