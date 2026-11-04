# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-6960 — the rate-change impact analysis and the customer
#          portal's standing charge read the base through
#          `apps.rating.seams.base_charge_for`, which took no binding, so from
#          the moment `DEF-RAT-5782` made the BILL honour the code the rate
#          schedule names, a customer could see one standing charge and be
#          billed another.
# Rules:   BR-RAT-1025 (PO 2026-09-19 — *"plan → rate schedule -> charge code →
#          base charges"*) · BR-RAT-088 (the CHARGE CODE owns the base AMOUNT) ·
#          BR-RAT-108 (the customer-class list is an INCLUSION list) ·
#          DEF-468 (two self-declared base codes and no binding still REFUSE) ·
#          US-CWP-062 TC-8 (a missing standing charge is a REASON, never $0.00) ·
#          CLAUDE.md hard rule 2 (money 4dp stored, 2dp displayed)
# Impacts: apps/rating/seams.py :: base_charge_for ·
#          apps/rating/selectors.py :: named_base_charge_code, impact_figures ·
#          apps/portal/seams/rating_seam.py :: standing_charge_monthly
# ───────────────────────────────────────────────────────
"""**THREE DOORS ONTO ONE BASE, AND THEY MAY NOT DISAGREE.**

⚠ **THE FIGURES ARE `DEF-RAT-5782`'s AND ARE REUSED ON PURPOSE.** Three water
base codes at **$8.00**, **$19.75** and **$34.00**, and the schedule names the
MIDDLE one, so `$19.75` is a figure neither a first-match (`$8.00`, catalogue
order) nor a last-match (`$34.00`) can produce. Both retired base columns are
cleared, so the named charge code is the only object in the picture that states
an amount.

**MEASURED BEFORE THE FIX, on this branch, on the SAME account:**

    the bill                     19.750000
    the impact-analysis door     {'wired': True, 'amount': None,
                                  'refusal': 'BaseChargeCodeUnresolved'}
    the portal standing charge   {'amount': None, 'per_service': {},
                                  'unavailable': 'BaseChargeCodeUnresolved'}

So the customer read *we cannot work this out* on `CWP-052` over a bill that
charged **$19.75**, and every affected account was counted `base_charge_refused`
by the impact analysis. **The disagreement runs the other way too** and that
half is worse: a named code scoped to another customer class made the bill
REFUSE while the two doors here quietly answered with the INFERRED code's
`$8.00` — a figure nobody will ever be billed, on a customer's screen.

⚠ **RED PROVED FIRST, through `pytest`, on SQLite and on real PostgreSQL 16
(hard-won laws 7 and 14).** The red output is quoted on each case.
"""

from __future__ import annotations

from typing import Any

import pytest

from apps.billing import gather
from apps.portal.seams import rating_seam
from apps.rating import models as rating_models, seams as rating_seams, selectors

from tests.test_def_438_parity import SERVICE_DATE, _account_on, _price_live, _water_plan
from tests.test_def_rat_5782_the_bill_honours_the_named_base_code import (
    DECOY_HIGH,
    DECOY_LOW,
    NAMED,
    WATER,
    _base_code,
    _bind,
    _only_the_charge_code_states_a_base,
    _three_codes,
    _water_base,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _water_version(tenant):
    return rating_models.TariffVersion.objects.filter(
        tenant=tenant, tariff__service__code=WATER
    ).first()


def _impact_door(tenant, plan_base=None):
    """The base exactly as `impact_figures` asks for it — through the seam,
    with the binding taken off the SAME projection the bill reads."""
    version = _water_version(tenant)
    inputs = selectors.pricing_inputs_for_version(version, SERVICE_DATE)
    # ⚠ **NO `customer_class`, BECAUSE `impact_figures` HOLDS NONE** — a helper
    # that passed one would be testing a call the product does not make
    # (`by_class_unavailable_reason: "OQ-319"` is the same absence, said on the
    # wire). It is the seam's own documented unscoped case.
    return rating_seams.base_charge_for(
        WATER,
        plan_base,
        inputs["base_charge"],
        named_code=inputs["base_charge_code"],
    )


def _portal_door(tenant, account, customer_class="residential"):
    plan_id = (
        rating_models.UnitPlanAssignment.objects.filter(
            tenant=tenant, unit_id=account.unit_id, assigned_to__isnull=True
        )
        .values_list("rate_plan_id", flat=True)
        .first()
    )
    return rating_seam.standing_charge_monthly(
        tenant.id,
        rate_plan_id=plan_id,
        service_codes=[WATER],
        customer_class=customer_class,
        on=SERVICE_DATE,
    )


def _the_live_customers_configuration(tenant, dana):
    """Three `is_base` water codes, the schedule naming the middle one."""
    plan = _water_plan(tenant)
    account, _unit, _asset, _delta = _account_on(tenant, dana, plan)
    _only_the_charge_code_states_a_base(tenant, plan)
    _low, named, _high = _three_codes(tenant)
    _bind(tenant, plan, named)
    return plan, account


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE DEFECT — one figure, three surfaces
# ══════════════════════════════════════════════════════════════════════════


def test_the_customer_and_their_bill_see_the_SAME_standing_charge(brazos, dana):
    """**THE HEADLINE, AND IT IS THE CUSTOMER'S OWN SCREEN.**

    `CWP-052` quotes what this account pays a month; the bill charges it. Both
    must read `$19.75`.

    RED on the tip:

        AssertionError: assert None == Decimal('19.75')
         +  where None = {'amount': None, 'per_service': {},
                          'unavailable': 'BaseChargeCodeUnresolved'}['amount']
    """
    with tenant_ctx(brazos):
        _plan, account = _the_live_customers_configuration(brazos, dana)

        bill = _water_base(_price_live(account))
        portal = _portal_door(brazos, account)

    # Stored to 4 decimals, displayed to 2 (hard rule 2): $19.75 on both.
    assert bill == NAMED
    assert portal["unavailable"] is None
    assert portal["amount"] == NAMED
    assert portal["per_service"][WATER] == NAMED


def test_the_impact_analysis_prices_the_code_the_schedule_NAMED(brazos, dana):
    """The other surface, on the same configuration and in the same breath.

    An impact figure that counted this account `base_charge_refused` is a
    filing that under-reports its own affected population, over a base the
    bill charges without complaint.

    RED on the tip:

        AssertionError: assert 'BaseChargeCodeUnresolved' is None
    """
    with tenant_ctx(brazos):
        _plan, _account = _the_live_customers_configuration(brazos, dana)
        answer = _impact_door(brazos)

    assert answer["refusal"] is None
    assert answer["amount"] == NAMED


def test_the_impact_analysis_HANDS_THE_BINDING_DOWN_at_its_own_call_site(
    brazos, dana, monkeypatch
):
    """⚠ **BUILT IS NOT WIRED (hard-won law 2).** A seam that TAKES a
    `named_code` nothing passes is dead parameter: every test above it can be
    written against the seam and pass while the impact analysis goes on
    refusing.

    So this asserts the CALL, from inside `impact_figures`, on both sides of
    the comparison — and it asserts each side carries ITS OWN version's
    binding, because a filing that moves the base from one code to another is
    exactly what an impact analysis is asked to price.

    RED on the tip:

        AssertionError: impact_figures called base_charge_for with
        named_code=None on both sides
    """
    seen: list[Any] = []
    real = rating_seams.base_charge_for

    def _spy(*args, **kwargs):
        seen.append(kwargs.get("named_code"))
        return real(*args, **kwargs)

    monkeypatch.setattr(rating_seams, "base_charge_for", _spy)

    with tenant_ctx(brazos):
        plan, _account = _the_live_customers_configuration(brazos, dana)
        tariff = rating_models.PlanRateSchedule.objects.get(
            tenant=brazos, rate_plan_id=plan.id, service__code=WATER
        ).tariff
        version = _water_version(brazos)
        selectors.impact_figures(tariff, WATER, version, version, SERVICE_DATE)

    assert seen, "impact_figures never reached the base charge — fixture, not behaviour"
    assert set(seen) == {"BASE-W-B"}, (
        f"impact_figures called base_charge_for with named_code={seen}"
    )


def test_the_seam_and_billing_still_AGREE_ABOUT_THE_SIGNATURE(brazos, dana):
    """⚠ **`DEF-RAT-7000`, FOUND WHILE REPRODUCING THIS ONE AND BIGGER THAN
    IT.** `base_charge_for` resolves a PRIVATE function in another module by
    name and passed it a `code_label=` argument that
    `gather._base_charge_for` lost on 2026-09-24 (`DEF-CUS-6550` cut a 63-word
    refusal to ten and the parameter stopped being read). The seam's
    `except Exception` then reported the broken call as an ordinary refusal:

        {'wired': True, 'amount': None, 'refusal': 'TypeError'}

    **Every tenant with an `is_base` charge code was affected** — which is
    every tenant this product provisions — so the portal's standing charge and
    the whole rate-change impact analysis had been answering *we cannot work
    this out* for three days over bills that were being produced normally.

    ⚠ **THE ONE `is_base` CODE AND NO BINDING IS THE CASE THAT EXPOSES IT**,
    because it is the plainest configuration there is: nothing is ambiguous,
    nothing is scoped, nothing is named. A refusal here can only be a fault of
    ours.

    RED on the tip:

        AssertionError: assert 'TypeError' is None
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        _account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _only_the_charge_code_states_a_base(brazos, plan)
        _base_code(brazos, "BASE-W-A", DECOY_LOW)
        answer = _impact_door(brazos)

    assert answer["refusal"] is None, "the seam and billing disagree about a signature"
    assert answer["amount"] == DECOY_LOW


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE FAIL DIRECTION — requirement 3: all three fail the SAME way
# ══════════════════════════════════════════════════════════════════════════


def test_a_named_code_that_cannot_price_the_service_refuses_on_ALL_THREE(
    brazos, dana, settings
):
    """⚠ **THE HALF WHERE THE PORTAL WAS SHOWING A FIGURE NOBODY WOULD BE
    BILLED.**

    The schedule names `BASE-W-COM`, scoped to commercial; the account is
    residential, and exactly one other base code reaches it. Before the fix
    the bill REFUSED by name while these two doors fell through to the
    inferred `$8.00` — a wrong figure quoted to a customer, with nothing
    visibly broken anywhere.

    RED on the tip:

        AssertionError: the portal quoted 8.00 for a base the bill refuses

    The ruled chain is stated off for the reason
    `test_a_named_code_that_has_been_RETIRED_refuses_rather_than_inferring`
    gives one file over: with `R3,R4` served the chain refuses first and the
    LIVE path, which is this case's subject, is never reached.
    """
    settings.BILLING_RESOLUTION_STEPS = ""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _only_the_charge_code_states_a_base(brazos, plan)
        _base_code(brazos, "BASE-W-A", DECOY_LOW)
        commercial = _base_code(brazos, "BASE-W-COM", NAMED, classes=["commercial"])
        _bind(brazos, plan, commercial)

        with pytest.raises(gather.GatherProblem) as refusal:
            _price_live(account)

        impact = _impact_door(brazos)
        portal = _portal_door(brazos, account)

    assert "BASE-W-COM" in str(refusal.value)
    assert impact["refusal"] is not None
    assert impact["amount"] is None
    assert portal["amount"] is None, "the portal quoted a base the bill refuses"
    assert portal["unavailable"] is not None


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE BOUNDARY — requirement 2 and requirement 4: nothing else moves
# ══════════════════════════════════════════════════════════════════════════


def test_a_schedule_naming_NOTHING_behaves_exactly_as_it_does_today(brazos, dana):
    """The configuration every tenant is on: one `is_base` code, no binding.
    All three doors answer `$8.00`, which is what they answered yesterday.

    This case PASSED on the tip and must go on passing — a fix that moved it
    would be the defect.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _only_the_charge_code_states_a_base(brazos, plan)
        _base_code(brazos, "BASE-W-A", DECOY_LOW)

        bill = _water_base(_price_live(account))
        impact = _impact_door(brazos)
        portal = _portal_door(brazos, account)

    assert bill == DECOY_LOW
    assert impact["amount"] == DECOY_LOW
    assert portal["amount"] == DECOY_LOW


def test_two_codes_and_NO_binding_still_refuse_on_all_three(brazos, dana):
    """⚠ **`DEF-468` IS UNTOUCHED.** Nobody has said which code owns water's
    base, so the catalogue's ORDER would decide what a customer pays. All
    three refuse, exactly as they did before this change."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _only_the_charge_code_states_a_base(brazos, plan)
        _base_code(brazos, "BASE-W-A", DECOY_LOW)
        _base_code(brazos, "BASE-W-C", DECOY_HIGH)

        with pytest.raises(gather.GatherProblem) as refusal:
            _price_live(account)
        impact = _impact_door(brazos)
        portal = _portal_door(brazos, account)

    assert "2 base charge codes for water." in str(refusal.value)
    assert impact["refusal"] is not None
    assert portal["amount"] is None


def test_the_binding_is_read_by_ONE_narrowing(brazos, dana):
    """`named_base_charge_code` is the single expression three doors read, and
    it answers the CODE rather than the id — a uuid would match nothing
    downstream and fall silently through to the inferred code."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        _low, named, _high = _three_codes(brazos)
        _bind(brazos, plan, named)
        version = _water_version(brazos)

        assert selectors.named_base_charge_code(version) == "BASE-W-B"
        assert selectors.named_base_charge_code(None) is None
        assert (
            selectors.pricing_inputs_for_version(version, SERVICE_DATE)["base_charge_code"]
            == "BASE-W-B"
        )
