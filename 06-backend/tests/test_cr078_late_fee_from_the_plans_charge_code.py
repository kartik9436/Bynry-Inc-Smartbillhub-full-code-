# ── Trace ──────────────────────────────────────────────
# Change:  **CR-078** (PO ruling 2026-09-07, FINANCE RE-SIGNED the same day —
#          12-governance/09-human-review-ledger.md). PO verbatim: *"this is
#          wrong - you ahve to take late fees form charge code mentione din the
#          plan - if plan doent provide you that charge code then you have to
#          put zero on late payment. - Logic aplplied ot Minimum late fee $5- -
#          you can link these defaults in Charge code - we have a charge code
#          for late payment"*.
# Rules:   BR-RAT-1011 (the plan names the charge code; naming none charges
#          ZERO) · BR-BIL-001 + B4 ❄️ (the arithmetic, UNMOVED) · BR-BIL-075
#          (which GL account the fee books to) · IS-1 (a retired charge is not
#          chargeable) · HR-1 (another tenant's is the same answer as absent) ·
#          CLAUDE.md rule 1 (tenant scoping) · rule 2 (money 4dp / display 2)
# Golden:  GT-8 ❄️ — `max(5.00, 0.015 × 542.10) = 8.13`, and GT-10 ❄️ carries
#          the same 8.13 into `82.08 + 18.50 + 8.13 + 8.30 = 117.01`. **THIS
#          FILE ASSERTS 8.13 IS STILL 8.13 WHEN IT COMES OFF THE PLAN'S CHARGE
#          CODE**, which is the sentence the finance re-sign turns on.
# Tests:   this file
# Impacts: apps/rating/models.RatePlan · apps/rating/selectors ·
#          apps/rating/services · apps/billing/late_fee ·
#          apps/billing/rating_seam · apps/billing/decisions ·
#          apps/rating/migrations/0026 + 0027
# ───────────────────────────────────────────────────────
"""The late fee comes from the charge code the PLAN names — and from nothing else.

WHAT THIS FILE HAS TO PROVE, AND WHY EACH HALF IS HERE
------------------------------------------------------
The change is a ROUTING change over a ❄️ FROZEN figure, so two claims carry it
and both were shown to the PO in plain English before the re-sign:

  1. **THE FIGURE DOES NOT MOVE.** The seeded `LATE` charge code carries
     `percent 1.5, min_amount 5` — the same two figures as Settings → Billing
     defaults — so `max($5.00, 1.5% × $542.10)` is **$8.13** whichever copy the
     engine reads. Asserted here against a real plan and a real charge code
     rather than against the literals GT-8 hands in, because "the two copies
     agree" is exactly the claim a test has to make bite.
  2. **A PLAN NAMING NO CODE CHARGES ZERO, AND DOES NOT FALL BACK.** This is the
     REVERSAL, and it is asserted as a REPLACEMENT of the old behaviour: the same
     account, the same overdue portion, the same grace — $8.13 with the code and
     **$0.00** without it. A test that only asserted the zero could not tell a
     later reader that $8.13 is what it replaced.

⚠ **THE REJECTED READING IS ASSERTED TOO.** Every other nullable term in this
product falls back to the tenant default; this one does not, and a lane
"tidying" that inconsistency away would be reinstating the behaviour the PO
ruled against. So `test_a_plan_with_no_code_does_not_fall_back_to_the_tenant_
default` sets the tenant's Billing defaults to a figure that could not be
mistaken for anything else and proves it never reaches the fee.

⚠ **`percent` IS A FRACTION, NOT PERCENTAGE POINTS, AND THE FIXTURE READS THE
OTHER WAY.** `lookup_defaults.json` writes `"percent": "1.5"`; the seeded ROW
holds `0.015`. `amount_rules.percent_with_minimum` multiplies without dividing,
and GT-8's frozen arithmetic is written `0.015 × 542.10`. A read that served
`1.5` through would charge **$813.15** on the reference bill, so the units are
asserted rather than assumed.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from apps.billing import late_fee
from apps.rating import models as rating_models
from apps.rating import selectors as rating_selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
    make_plan,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: ❄️ GT-8's own inputs and its signed answer. The overdue portion is B5's;
#: the two dates satisfy B5's stated condition ("past Due date beyond grace",
#: 6 calendar days elapsed against a 5-day window) and are fixture scaffolding.
GT8_OVERDUE_PORTION = Decimal("542.10")
GT8_FEE = Decimal("8.13")
DUE_DATE = dt.date(2026, 7, 15)
AS_OF = dt.date(2026, 7, 21)
GRACE_DAYS = 5
GRACE_MODE = "calendar"

#: The seeded figures on the `LATE` charge code, as the DATABASE holds them.
#: `0.015` is a FRACTION — see the module docstring.
SEEDED_PERCENT = Decimal("0.015")
SEEDED_MINIMUM = Decimal("5")


def a_plan_with_the_late_code(tenant, name="Late-fee plan"):
    """A published plan pointed at the tenant's own seeded `LATE` code."""
    plan = make_plan(tenant, name=name, code=name.lower().replace(" ", "-"))
    charge = rating_models.Charge.objects.get(tenant=tenant, code="LATE", deleted_at__isnull=True)
    rating_models.RatePlan.objects.filter(pk=plan.pk).update(late_fee_charge=charge)
    plan.refresh_from_db()
    return plan, charge


def fee_for(plan):
    """GT-8's assessment, with the terms taken from the plan (BR-RAT-1011)."""
    return late_fee.assess_late_fee_for_plan(
        rate_plan_id=plan.id,
        overdue_amount=GT8_OVERDUE_PORTION,
        due_date=DUE_DATE,
        as_of=AS_OF,
        grace_days=GRACE_DAYS,
        grace_mode=GRACE_MODE,
    )


def test_the_seeded_late_code_carries_the_billing_defaults_figures(brazos):
    """The whole re-sign rests on this: the two copies hold the same numbers."""
    with tenant_ctx(brazos):
        charge = rating_models.Charge.objects.get(
            tenant=brazos, code="LATE", deleted_at__isnull=True
        )
    assert charge.amount_rule == "percent_with_minimum"
    # ⚠ A FRACTION. `lookup_defaults.json` says "1.5"; the row says 0.015.
    assert charge.percent == SEEDED_PERCENT, (
        "charges.percent stores a FRACTION (seed_demo line 163). Serving the "
        "fixture's 1.5 through would charge 813.15 on GT-8's reference bill."
    )
    assert charge.min_amount == SEEDED_MINIMUM


def test_the_frozen_fee_is_the_same_when_it_comes_off_the_plans_charge_code(brazos):
    """❄️ GT-8 / GT-10: **8.13**, now sourced from the plan rather than the screen."""
    with tenant_ctx(brazos):
        plan, charge = a_plan_with_the_late_code(brazos)
        terms = rating_selectors.plan_late_fee_terms(plan.id)
        assert terms is not None
        assert terms["percent"] == SEEDED_PERCENT
        assert terms["minimum"] == SEEDED_MINIMUM
        assert terms["charge_id"] == str(charge.id)  # BR-BIL-075 — where it books

        fee, used = fee_for(plan)
    assert fee == GT8_FEE, "the routing change must not move a ❄️ FROZEN B4/B5 figure"
    assert used is not None and used.code == "LATE"


def test_a_plan_naming_no_charge_code_charges_zero(brazos):
    """THE RULING: *"if plan doent provide you that charge code ... put zero"*."""
    with tenant_ctx(brazos):
        plan, _ = a_plan_with_the_late_code(brazos, name="Zero plan")
        with_code, _ = fee_for(plan)
        rating_models.RatePlan.objects.filter(pk=plan.pk).update(late_fee_charge=None)
        without_code, terms = fee_for(plan)

    # Asserted as a REPLACEMENT, not as a bare zero: this is what it replaced.
    assert with_code == GT8_FEE
    assert without_code == Decimal("0.00")
    assert terms is None, "no terms were used, because there is no fee to compute"


def test_a_plan_with_no_code_does_not_fall_back_to_the_tenant_default(brazos):
    """The REJECTED reading, asserted so a later 'tidy-up' goes RED.

    Settings → Billing defaults still holds `late_pct` and `late_min_amount`,
    and every other nullable term on a plan falls back to a tenant default. If
    a lane restored that chain here, this test is what fails: the tenant
    default is set to a figure nothing else in the product produces, and the
    fee stays $0.00.
    """
    from apps.tenancy import models as tenancy_models

    with tenant_ctx(brazos):
        plan, _ = a_plan_with_the_late_code(brazos, name="No fallback plan")
        rating_models.RatePlan.objects.filter(pk=plan.pk).update(late_fee_charge=None)
        settings_row = tenancy_models.TenantSettings.objects.get(tenant=brazos)
        billing_defaults = dict(settings_row.billing_defaults or {})
        billing_defaults["late_pct"] = "0.99"  # 99% — unmistakable if it leaks
        billing_defaults["late_min_amount"] = "77.77"
        settings_row.billing_defaults = billing_defaults
        settings_row.save(update_fields=["billing_defaults"])

        fee, terms = fee_for(plan)

    assert fee == Decimal("0.00"), (
        "BR-RAT-1011: a plan naming no late-fee charge code charges ZERO. A fee of "
        "77.77 or 536.68 here means the tenant Billing-defaults fallback is back."
    )
    assert terms is None


def test_a_retired_charge_code_is_the_same_answer_as_none(brazos):
    """IS-1 — a retired charge is not chargeable, so the plan charges zero."""
    with tenant_ctx(brazos):
        plan, charge = a_plan_with_the_late_code(brazos, name="Retired code plan")
        assert fee_for(plan)[0] == GT8_FEE
        charge.deleted_at = dt.datetime(2026, 8, 1, tzinfo=dt.timezone.utc)
        charge.save(update_fields=["deleted_at"])
        fee, terms = fee_for(plan)
        assert fee == Decimal("0.00")
        assert terms is None
        # And it is COUNTED rather than silent — the guard's own input.
        missing = rating_selectors.plans_missing_late_fee_charge()
    reasons = {row["code"]: row["reason"] for row in missing}
    assert reasons.get("retired-code-plan") == "names_a_retired_charge_code"


def test_another_tenants_plan_is_UNREADABLE_and_never_a_free_zero(brazos, lonestar):
    """HR-1, and the distinction that keeps the ruled zero safe.

    Another tenant's plan is not *"a plan that provides no charge code"* — it is
    NO PLAN AT ALL from here, which is a data fault. If this answered $0.00 the
    two states would be indistinguishable, and any account whose plan could not
    be read would be silently free for the rest of its life. It raises instead,
    and `decisions.apply_decisions` lets that stop the calculate step.
    """
    with tenant_ctx(lonestar):
        other_plan, _ = a_plan_with_the_late_code(lonestar, name="Other utility plan")
    with tenant_ctx(brazos):
        assert rating_selectors.plan_late_fee_terms(other_plan.id) is None
        with pytest.raises(late_fee.LateFeePlanUnreadable):
            fee_for(other_plan)


def test_a_new_plan_starts_pointed_at_the_tenants_seeded_code(brazos, dana):
    """The forward half of `CR-078`'s ordering.

    The backfill fixes today's plans. Without a create-time default every plan
    made TOMORROW would charge $0.00 with nothing raising — the same silent
    failure one day later, which is `CR-068` R3's clock-in-a-rule shape. So a
    plan created through the service starts pointed at the tenant's own seeded
    code, ON THE PLAN where a human can see it and clear it.
    """
    from apps.rating import services as rating_services

    with tenant_ctx(brazos):
        created = rating_services.create_plan(
            dana, {"code": "CR078-NEW", "name": "CR-078 new plan"}
        )
        assert created["late_fee_charge"] is not None
        assert created["late_fee_charge"]["code"] == "LATE"

        # …and CLEARING it is expressible, which is what makes the zero a
        # choice rather than an accident.
        cleared = rating_services.update_plan(dana, created["id"], {"late_fee_charge": None})
    assert cleared["late_fee_charge"] is None


def test_a_plan_planted_around_the_service_is_COUNTED_rather_than_silent(brazos, dana):
    """`CR-078` step 3 and step 5 in one — *prove none is unpopulated*, and make
    the ones that are VISIBLE.

    ⚠ **THIS TEST FAILED FIRST AND THE FAILURE WAS THE USEFUL PART.** It was
    written asserting *"every plan names a code"* and went red on the fixture
    helper `make_plan`, which writes `RatePlan.objects.get_or_create` directly
    and therefore skips `create_plan`'s default. `create_plan` is the ONLY
    writer of `rate_plans` in the product (grep: `apps/rating/services.py:1413`
    and nothing else), so no live path can produce this state today — but a
    fixture can, an import could, and a lane adding a second writer tomorrow
    would.

    So the assertion is the one that survives that: a plan reaching the table
    around the service is **COUNTED**, by name and with a reason. That count is
    what `manage.py cr078_late_fee_codes` prints and what gate `G121` fails on.
    A plan charging $0.00 in late fees is lawful (the PO ruled it) and must
    never be INVISIBLE, which is the whole of step 5.
    """
    from apps.rating import services as rating_services

    with tenant_ctx(brazos):
        through_the_service = rating_services.create_plan(
            dana, {"code": "CR078-SERVICE", "name": "CR-078 through the service"}
        )
        assert through_the_service["late_fee_charge"] is not None

        # Planted around it, exactly as a fixture or a future second writer would.
        make_plan(brazos, name="Planted plan", code="planted-plan")
        missing = rating_selectors.plans_missing_late_fee_charge()

    seen = {row["code"]: row["reason"] for row in missing}
    assert seen.get("planted-plan") == "names_no_charge_code", (
        "a plan that reached rate_plans around create_plan charges $0.00 in late "
        f"fees and must be COUNTED, not silent. Counted: {seen}"
    )
    assert "cr078-service" not in seen and "CR078-SERVICE" not in seen
