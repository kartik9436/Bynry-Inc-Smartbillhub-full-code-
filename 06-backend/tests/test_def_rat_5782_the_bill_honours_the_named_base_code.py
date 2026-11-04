# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-5782 — the live billing path never receives the rate
#          schedule's base-charge binding, so a catalogue with more than one
#          `is_base` code for a service refuses EVERY bill even when a human
#          has said which code owns that service's base. Reported live:
#          Ottumwa Water Works, move-out final bill, *"3 base charge codes for
#          water. Scope them on Charge codes."*
#          DEF-RAT-6918 — and once the binding DOES arrive, a named code that
#          fails the narrowing must not fall through to an inferred code or to
#          the ambiguity count.
# Rules:   BR-RAT-1025 (PO 2026-09-19 — *"plan → rate schedule -> charge code →
#          base charges"*; the schedule NAMES the code) · BR-RAT-088 (the
#          CHARGE CODE owns the base AMOUNT) · BR-RAT-108 (the customer-class
#          list is an INCLUSION list; NULL/`[]` is every class) · DEF-468 (two
#          self-declared base codes and no binding still REFUSE) · BR-BIL-055
#          (a refusal stops ONE account) · B14 rules 32/33 (clerk copy) ·
#          CLAUDE.md hard rule 2 (money 4dp stored, 2dp displayed)
# Impacts: apps/rating/selectors.py :: pricing_inputs_for_version,
#          base_charge_from_charge_code · apps/billing/gather.py ::
#          _base_charge_code_for, _tariff_config_for
# ───────────────────────────────────────────────────────
"""**THE SCHEDULE SAID WHICH CODE; THE BILL MUST CHARGE THAT CODE.**

⚠ **THE FIGURES ARE CHOSEN SO THAT NO CASE CAN PASS BY COINCIDENCE.** The
catalogue holds three water base codes at **$8.00**, **$19.75** and **$34.00**,
and the schedule names the MIDDLE one. `$19.75` is a figure neither a
first-match (`$8.00`, catalogue order) nor a last-match (`$34.00`) would ever
produce, and the plan states no base of its own, so the only object that can
put `19.7500` on the bill is the named charge code.

⚠ **RED PROVED FIRST, THROUGH THE HARNESS THAT RUNS IT (hard-won law 7), on
real PostgreSQL 16 as well as on the SQLite suite (hard-won law 14).** The
red output for each case is quoted on the case itself.

**THE NEGATIVE HALF IS THE HALF THAT MATTERS.** `DEF-468`'s refusal is
CORRECT — two codes declaring themselves the base and nobody saying which is a
bill decided by catalogue order — and this change must not weaken it by one
account. `test_three_codes_and_NO_binding_still_refuses_exactly_as_today` is
that guard, and it passed on the tip before the fix and must go on passing.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.billing import gather
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models

from tests.test_def_438_parity import (
    SERVICE_DATE,
    _account_on,
    _price_live,
    _water_plan,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

WATER = "water"

#: The three figures. The middle one is the one a person chose.
DECOY_LOW = Decimal("8.00")
NAMED = Decimal("19.75")
DECOY_HIGH = Decimal("34.00")


def _base_code(tenant, code, amount, *, classes=None, is_base=True):
    """One water charge code that declares itself the base.

    `classes=None` is `BR-RAT-108`'s *every class*, stored as the empty list a
    tenant's own Charge-codes card produces.
    """
    return rating_models.Charge.objects.create(
        tenant=tenant,
        code=code,
        name=f"Water base {code}",
        charge_type="recurring",
        amount_rule="flat",
        amount=amount,
        service=tenancy_models.Service.objects.get(code=WATER),
        is_base=is_base,
        applies_to_customer_classes=classes or [],
    )


def _three_codes(tenant):
    """The PO's configuration: THREE codes, all `is_base`, all reaching every
    customer class. This is what produced *"3 base charge codes for water."*"""
    return (
        _base_code(tenant, "BASE-W-A", DECOY_LOW),
        _base_code(tenant, "BASE-W-B", NAMED),
        _base_code(tenant, "BASE-W-C", DECOY_HIGH),
    )


def _bind(tenant, plan, charge):
    """Point every water schedule version of this plan at `charge`, the way
    step 1 of the rate-schedule wizard does."""
    rating_models.TariffVersion.objects.filter(tenant=tenant, tariff__service__code=WATER).update(
        base_charge_code_id=charge.id
    )


def _only_the_charge_code_states_a_base(tenant, plan):
    """Clear the two RETIRED base columns — the plan's and the schedule's.

    ⚠ **LOAD-BEARING, AND THE SECOND HALF WAS MISSED ON THE FIRST DRAFT.**
    `gather._base_charge_for` REFUSES when the charge code states one figure and
    EITHER the plan or the rate schedule version states a different one — that
    is `BR-RAT-088`'s migration-artefact tripwire, and it fires before anything
    about the binding is reached. `_water_plan` writes `$8.00` onto BOTH
    objects, so a fixture that cleared only the plan would have refused every
    case in this file with

        Two base charges for water. Clear 8.00 on the rate schedule.

    — a red that looks exactly like the defect and has nothing to do with it.

    **This is the world a real tenant is in**, which is why it is the right
    fixture rather than a convenient one: `BR-RAT-088` retired both columns,
    `RateScheduleWizard` has had no control for either since, and a version
    written today stores NULL. With both silent, the ONLY object that can state
    a base is the charge code — which is what makes `19.7500` proof.
    """
    rating_models.PlanService.objects.filter(tenant=tenant, rate_plan_id=plan.id).update(
        base_charge=None
    )
    rating_models.TariffVersion.objects.filter(tenant=tenant, tariff__service__code=WATER).update(
        base_charge=None
    )


def _water_base(data):
    return [config for config in data.tariffs if config.service == WATER][0].base_charge


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE DEFECT, REPRODUCED AND THEN FIXED
# ══════════════════════════════════════════════════════════════════════════


def test_the_bill_charges_the_code_the_schedule_NAMED(brazos, dana):
    """**THE LIVE CUSTOMER'S BILL.**

    Three base codes reach this account; the schedule names `BASE-W-B`. The
    bill must carry `19.7500` — the named code's figure — and must not refuse.

    RED on the tip, through `pytest`:

        apps.billing.gather.GatherProblem: 3 base charge codes for water.
        Scope them on Charge codes.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _only_the_charge_code_states_a_base(brazos, plan)
        _low, named, _high = _three_codes(brazos)
        _bind(brazos, plan, named)

        data = _price_live(account)

    # Hard rule 2 — stored to 4 decimals. A first match would be 8.00 and a
    # last match 34.00; only the binding produces this figure.
    assert _water_base(data) == NAMED


def test_the_named_code_wins_even_when_it_is_neither_first_nor_last(brazos, dana):
    """The same configuration asked of rating's own read, so a failure here
    separates *the binding never crossed the seam* from *billing mis-read the
    answer*."""
    from apps.rating import selectors as rating_selectors

    with tenant_ctx(brazos):
        _three_codes(brazos)
        answer = rating_selectors.base_charge_from_charge_code(
            WATER, customer_class="residential", named_code="BASE-W-B"
        )

    assert answer["refusal"] is None
    assert answer["code"] == "BASE-W-B"
    assert answer["amount"] == NAMED


def test_the_binding_reaches_billing_through_rating_s_published_projection(brazos, dana):
    """⚠ **THE HOP THAT WAS MISSING, ASSERTED ON ITS OWN.**

    `pricing_inputs_for_version` is the ONE projection of a stored version onto
    the engine's inputs, and the binding was simply not on it — so no caller
    could have passed it however carefully it was written. Billing reads this
    key by name; a lane that renames it breaks the bill and this assertion is
    what says so first.
    """
    from apps.rating import selectors as rating_selectors

    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        _only_the_charge_code_states_a_base(brazos, plan)
        _low, named, _high = _three_codes(brazos)
        _bind(brazos, plan, named)
        version = rating_models.TariffVersion.objects.filter(
            tenant=brazos, tariff__service__code=WATER
        ).first()
        inputs = rating_selectors.pricing_inputs_for_version(version, SERVICE_DATE)

    # The CODE, not the id: `base_charge_from_charge_code` narrows on
    # `charges.code`, and a uuid here would never match anything.
    assert inputs["base_charge_code"] == "BASE-W-B"


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE BOUNDARY — what must NOT move
# ══════════════════════════════════════════════════════════════════════════


def test_three_codes_and_NO_binding_still_refuses_exactly_as_today(brazos, dana):
    """⚠ **`DEF-468` IS UNTOUCHED, AND THIS IS THE GUARD THAT SAYS SO.**

    Nobody has said which code owns water's base, so billing by catalogue
    order would decide what a customer pays. It refuses, in the same six words
    a clerk reads today. This case PASSED on the tip and must go on passing;
    a fix that made it green by weakening the refusal would be the defect.

    ⚠ **AMENDED 2026-10-06 (`DEF-RAT-9832`, PO ruling), NOT DELETED.** Still
    never catalogue order — but no longer a refusal: nobody named a code, so
    none is taken and the bill completes at `$0.00` with the warning (*"if it
    is not provided then you will take it zeo"*).
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _only_the_charge_code_states_a_base(brazos, plan)
        _three_codes(brazos)

        data = _price_live(account)

    assert _water_base(data) == Decimal("0")
    assert any(row["key"] == "billing.oneTime.warn.baseNotSet" for row in data.warnings)


def test_one_code_and_no_binding_bills_the_inferred_code_unchanged(brazos, dana):
    """The configuration every tenant is on today: one `is_base` code, no
    binding. The inferred route answers and nothing about it moved.

    ⚠ **AMENDED 2026-10-06 (`DEF-RAT-9832`, PO ruling): there is no inferred
    route.** One unbound code prices nothing (2026-09-28, *"An unbound
    `is_base` code prices nothing"*), so the bill is `$0.00` with the warning."""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _only_the_charge_code_states_a_base(brazos, plan)
        _base_code(brazos, "BASE-W-A", DECOY_LOW)

        data = _price_live(account)

    assert _water_base(data) == Decimal("0")
    assert _water_base(data) != DECOY_LOW


def test_no_base_code_at_all_REFUSES__it_no_longer_falls_back_to_the_plan(
    brazos, dana, settings
):
    """⚠ **SUPERSEDED 2026-09-28 (`DEF-BIL-7170`), AND THE SUPERSESSION IS THE
    POINT.**

    This case was `test_no_base_code_at_all_still_bills_from_the_plan` and it
    asserted `Decimal("8.00")` — *"a tenant that has not adopted `BR-RAT-088`
    bills exactly what it billed yesterday"*. **PO ruling 2026-09-28**,
    verbatim: *"we will never take default value from plan $8.0 - that is
    retired"* — never a source and never a fallback, **not even when the charge
    code is silent**.

    So the tenant that has adopted nothing is now TOLD SO, in six words,
    pointing at the one screen that can fix it. This is the only bill this
    ruling stops that used to be produced, and it is stopped deliberately.

    The ruled chain is still stated OFF here and only here, so the LIVE path is
    what is proved.

    ⚠ **SUPERSEDED 2026-09-30 — THE BILL NO LONGER REFUSES; IT BILLS `$0.00`
    AND WARNS.** PO: *"if user did not define and bind base charges in rate
    schedule - then as a default you take 0 and complete the bill instead of
    refusing - if you want to show the warning you can display it dueing the
    process"*. What this case protects is UNCHANGED: the bill never takes an
    unbound or inferred code's figure, and never the retired `$8.00`.
    """
    settings.BILLING_RESOLUTION_STEPS = ""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        data = _price_live(account)

    assert _water_base(data) == Decimal("0")
    # AMENDED 2026-10-01 (billing red triage): the account also carries
    # `noAgreements` (no service agreements on file — `31358c239`, PO
    # 2026-09-30 option C: bill all and warn), which names no service. The
    # base warning is asserted whole, beside it.
    assert [w["key"] for w in data.warnings] == [
        "billing.oneTime.warn.noAgreements",
        "billing.oneTime.warn.baseNotSet",
    ]
    assert [
        w["params"]["service_code"]
        for w in data.warnings
        if w["key"] == "billing.oneTime.warn.baseNotSet"
    ] == [WATER]


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE FAIL DIRECTION — DEF-RAT-6918, and requirement 3 of this lane
# ══════════════════════════════════════════════════════════════════════════


def test_a_named_code_scoped_to_another_class_REFUSES_and_names_the_code(brazos, dana):
    """⚠ **THE WHOLE POINT OF THE BINDING, IN THE FAIL DIRECTION
    (`DEF-RAT-6918`).**

    The schedule names a code scoped to `commercial`; this account is
    `residential`, and two other codes reach it. Falling through would bill
    `$8.00` or refuse with *"2 base charge codes"* — telling a clerk to scope
    codes when the scoping is exactly what they already did. The screen shows
    `BASE-W-COM`; a bill from any other code makes the screen and the bill
    disagree with neither visibly wrong.

    RED on the tip once the binding was wired, before this branch existed:

        AssertionError: assert 'BASE-W-COM' in '2 base charge codes for
        water. Scope them on Charge codes.'

    ⚠ **SUPERSEDED 2026-09-30 — THE BILL NO LONGER REFUSES; IT BILLS `$0.00`
    AND WARNS.** PO: *"if user did not define and bind base charges in rate
    schedule - then as a default you take 0 and complete the bill instead of
    refusing - if you want to show the warning you can display it dueing the
    process"*. What this case protects is UNCHANGED: the bill never takes an
    unbound or inferred code's figure, and never the retired `$8.00`.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _only_the_charge_code_states_a_base(brazos, plan)
        _base_code(brazos, "BASE-W-A", DECOY_LOW)
        _base_code(brazos, "BASE-W-C", DECOY_HIGH)
        commercial = _base_code(brazos, "BASE-W-COM", NAMED, classes=["commercial"])
        _bind(brazos, plan, commercial)

        data = _price_live(account)

    assert _water_base(data) == Decimal("0")
    # AMENDED 2026-10-01 (billing red triage): the account also carries
    # `noAgreements` (no service agreements on file — `31358c239`, PO
    # 2026-09-30 option C: bill all and warn), which names no service. The
    # base warning is asserted whole, beside it.
    assert [w["key"] for w in data.warnings] == [
        "billing.oneTime.warn.noAgreements",
        "billing.oneTime.warn.baseNotSet",
    ]
    assert [
        w["params"]["service_code"]
        for w in data.warnings
        if w["key"] == "billing.oneTime.warn.baseNotSet"
    ] == [WATER]
    # It must NOT have become either decoy's figure.
    assert _water_base(data) not in (DECOY_LOW, DECOY_HIGH, NAMED)


def test_a_named_code_that_has_been_RETIRED_refuses_rather_than_inferring(brazos, dana, settings):
    """⚠ **THE SILENT-WRONG-BILL CASE, AND IT IS WHY THE FALL-THROUGH HAD TO
    GO.**

    Exactly ONE other base code exists, so a fall-through would not refuse —
    it would quietly bill `$8.00` under a schedule whose own screen names a
    different code. `_guard_bound_base_charge_code` refuses this at
    ACTIVATION; somebody retiring the code afterwards is the same fact
    arriving at billing time, and it must fail the same way rather than
    inventing an answer.

    ⚠ **THE RULED CHAIN IS STATED OFF HERE, AND WITHOUT THAT THIS CASE IS A
    CHECK THAT CANNOT FAIL (hard-won law 7 habit 2).** With `R3,R4` served —
    the shipped default — `resolution.resolve_base_charge`'s named arm raises
    on exactly this configuration, so the test goes GREEN on the tip while the
    LIVE path, which is its subject, quietly bills `$8.00`. It was measured
    doing precisely that: on the first red run this case PASSED unfixed. Off,
    the live path is the only thing answering and the case is red until the
    fall-through is gone.

    ⚠ **SUPERSEDED 2026-09-30 — THE BILL NO LONGER REFUSES; IT BILLS `$0.00`
    AND WARNS.** PO: *"if user did not define and bind base charges in rate
    schedule - then as a default you take 0 and complete the bill instead of
    refusing - if you want to show the warning you can display it dueing the
    process"*. What this case protects is UNCHANGED: the bill never takes an
    unbound or inferred code's figure, and never the retired `$8.00`.
    """
    from django.utils import timezone

    settings.BILLING_RESOLUTION_STEPS = ""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _only_the_charge_code_states_a_base(brazos, plan)
        _base_code(brazos, "BASE-W-A", DECOY_LOW)
        retired = _base_code(brazos, "BASE-W-B", NAMED)
        _bind(brazos, plan, retired)
        rating_models.Charge.objects.filter(pk=retired.id).update(deleted_at=timezone.now())

        data = _price_live(account)

    assert _water_base(data) == Decimal("0")
    # AMENDED 2026-10-01 (billing red triage): the account also carries
    # `noAgreements` (no service agreements on file — `31358c239`, PO
    # 2026-09-30 option C: bill all and warn), which names no service. The
    # base warning is asserted whole, beside it.
    assert [w["key"] for w in data.warnings] == [
        "billing.oneTime.warn.noAgreements",
        "billing.oneTime.warn.baseNotSet",
    ]
    assert [
        w["params"]["service_code"]
        for w in data.warnings
        if w["key"] == "billing.oneTime.warn.baseNotSet"
    ] == [WATER]
    assert _water_base(data) != DECOY_LOW


def test_a_named_code_that_is_no_longer_a_base_charge_refuses(brazos, dana, settings):
    """Same fact, the other way somebody can cause it: the tick came off
    `is_base` after the schedule named the code. It is not an inferred-code
    fallback and it is not a zero.

    The ruled chain is stated off for the reason the case above gives: with it
    on, the chain refuses and this case cannot see what the live path does.

    ⚠ **SUPERSEDED 2026-09-30 — THE BILL NO LONGER REFUSES; IT BILLS `$0.00`
    AND WARNS.** PO: *"if user did not define and bind base charges in rate
    schedule - then as a default you take 0 and complete the bill instead of
    refusing - if you want to show the warning you can display it dueing the
    process"*. What this case protects is UNCHANGED: the bill never takes an
    unbound or inferred code's figure, and never the retired `$8.00`.
    """
    settings.BILLING_RESOLUTION_STEPS = ""
    with tenant_ctx(brazos):
        plan = _water_plan(brazos, base_code=False)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _only_the_charge_code_states_a_base(brazos, plan)
        _base_code(brazos, "BASE-W-A", DECOY_LOW)
        unticked = _base_code(brazos, "BASE-W-B", NAMED)
        _bind(brazos, plan, unticked)
        rating_models.Charge.objects.filter(pk=unticked.id).update(is_base=False)

        data = _price_live(account)

    assert _water_base(data) == Decimal("0")
    # AMENDED 2026-10-01 (billing red triage): the account also carries
    # `noAgreements` (no service agreements on file — `31358c239`, PO
    # 2026-09-30 option C: bill all and warn), which names no service. The
    # base warning is asserted whole, beside it.
    assert [w["key"] for w in data.warnings] == [
        "billing.oneTime.warn.noAgreements",
        "billing.oneTime.warn.baseNotSet",
    ]
    assert [
        w["params"]["service_code"]
        for w in data.warnings
        if w["key"] == "billing.oneTime.warn.baseNotSet"
    ] == [WATER]
    assert _water_base(data) != DECOY_LOW
