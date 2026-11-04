# ── Trace ──────────────────────────────────────────────
# Rules:   BR-RAT-117 (PO 2026-08-22, verbatim: "ruccuring and Autom apply
#          land on bill") · BR-RAT-088 (is_base owns the base — never twice) ·
#          BR-RAT-108 (customer-class INCLUSION list) · B4.2 + BR-RAT-116
#          (what `taxable` means on a fee line)
# Defects: DEF-561 — NEITHER route reached a bill before this ·
#          DEF-RAT-5784 (2026-09-19) — route 2 then reached one WITHOUT
#          testing the code's trigger, and this file's own
#          `test_a_plan_named_code_*` case asserted that as correct
# ───────────────────────────────────────────────────────
"""BR-RAT-117 — a configured charge code becomes a LINE.

⚠ **THE PIN DEF-561 SAYS NOBODY HAD WRITTEN.** Every existing test of charge
codes tests the catalogue, the wizard, or R4's narrowing in isolation, so both
routes to a bill could be — and were — dead with every suite green. These
cases assert the LINE and its amount, and that it appears exactly ONCE.
"""
from datetime import date
from decimal import Decimal

import pytest

from apps.rating import models as rating_models, selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import brazos, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _plan(tenant, name="BR-RAT-117 plan"):
    return rating_models.RatePlan.objects.create(tenant=tenant, name=name, status="published")


def _code(tenant, code, *, amount="12.0000", auto=True, kind="recurring", base=False, classes=None):
    return rating_models.Charge.objects.create(
        tenant=tenant,
        code=code,
        name=f"{code} monthly service fee",
        charge_type=kind,
        auto_apply=auto,
        amount=Decimal(amount),
        is_base=base,
        applies_to_customer_classes=classes,
    )


def test_a_recurring_auto_apply_code_lands_on_the_bill(brazos):
    """The ruling itself: BOTH flags, no plan binding, and the $12.00 is there."""
    with tenant_ctx(brazos):
        plan = _plan(brazos)
        _code(brazos, "SVC-M")
        rows = selectors.billable_charge_codes(plan.id, date(2026, 8, 1))
    assert [r["code"] for r in rows] == ["SVC-M"]
    assert rows[0]["amount"] == Decimal("12.0000")


def test_one_flag_alone_does_NOT_land(brazos):
    """`recurring` without `auto_apply`, and `auto_apply` on a one-time code,
    both stay OFF the bill — they wait for their own trigger, which is what
    `charge_type` is for."""
    with tenant_ctx(brazos):
        plan = _plan(brazos, "One flag")
        _code(brazos, "REC-ONLY", auto=False)
        _code(brazos, "ONE-TIME", kind="one_time")
        rows = selectors.billable_charge_codes(plan.id, date(2026, 8, 1))
    assert rows == []


def test_THE_UNION__auto_applied_AND_plan_named_bills_ONCE(brazos):
    """⚠ The $24.00-for-one-$12.00-fee failure BR-RAT-088 was written from.
    A code that is auto-applied AND named by the plan yields ONE line."""
    with tenant_ctx(brazos):
        plan = _plan(brazos, "Both routes")
        code = _code(brazos, "SVC-BOTH")
        rating_models.PlanChargeRule.objects.create(tenant=brazos, rate_plan=plan, charge=code)
        rows = selectors.billable_charge_codes(plan.id, date(2026, 8, 1))
    assert len(rows) == 1, f"billed twice: {rows}"
    assert rows[0]["amount"] == Decimal("12.0000")


def test_a_plan_named_code_STILL_OBEYS_ITS_OWN_TRIGGER(brazos):
    """⚠ **THIS CASE WAS INVERTED ON 2026-09-19 (`DEF-RAT-5784`), AND THE OLD
    VERSION IS WHY THE DEFECT SURVIVED A MONTH.**

    It read `test_a_plan_named_code_lands_even_without_the_flags` and asserted
    that a `one_time` code a plan names BILLS — *"the route DEF-561 found
    dead: the plan names it, so it bills."* That was `DEF-561`'s
    over-implementation written down as an expectation, so the suite defended
    it: on `brazosbend` it meant `$955.00` a month of penalties and connection
    fees, `$11,460.00` a year, a `$250.00` tamper fee billed twelve times.

    **The ruling it now states** — PO 2026-09-19, verbatim: *"the charge code
    decides / Naming a charge in a plan makes it available. Whether it bills
    monthly is the charge code's own setting"*. Naming still makes the code
    AVAILABLE; the trigger still decides. `DEF-561`'s real finding — that
    `plan_charge_rules` had no billing reader at all — is untouched, and the
    reader is still here.
    """
    with tenant_ctx(brazos):
        plan = _plan(brazos, "Named only")
        code = _code(brazos, "NAMED", auto=False, kind="one_time")
        rating_models.PlanChargeRule.objects.create(tenant=brazos, rate_plan=plan, charge=code)
        rows = selectors.billable_charge_codes(plan.id, date(2026, 8, 1))
        still_named = rating_models.PlanChargeRule.objects.filter(
            tenant_id=brazos.id, rate_plan_id=plan.id, charge_id=code.id
        ).count()
    assert rows == [], f"a one-time code named by a plan rode an ordinary bill: {rows}"
    assert still_named == 1, "the binding was removed rather than the trigger honoured"


def test_the_base_code_is_excluded__it_has_its_own_route(brazos):
    """BR-RAT-088: `is_base` reaches the bill as the service's base. Letting it
    in here bills $12.00 twice — §A3 priced that at $23,069.50 a month."""
    with tenant_ctx(brazos):
        plan = _plan(brazos, "Base excluded")
        _code(brazos, "BASE-E", base=True)
        rows = selectors.billable_charge_codes(plan.id, date(2026, 8, 1))
    assert rows == []


def test_the_class_gate_is_an_INCLUSION_list(brazos):
    """BR-RAT-108: NULL/[] = every class; a listed class narrows."""
    with tenant_ctx(brazos):
        plan = _plan(brazos, "Class gate")
        _code(brazos, "COM-ONLY", classes=["commercial"])
        commercial = selectors.billable_charge_codes(
            plan.id, date(2026, 8, 1), customer_class="commercial"
        )
        residential = selectors.billable_charge_codes(
            plan.id, date(2026, 8, 1), customer_class="residential"
        )
    assert [r["code"] for r in commercial] == ["COM-ONLY"]
    assert residential == []


def test_a_per_size_code_REFUSES_rather_than_billing_the_flat_column(brazos):
    """The size ladder is per connection; billing the flat column would charge
    a 5/8-inch price to a 2-inch service. Refused BY NAME (R4's own posture)."""
    from core import errors

    with tenant_ctx(brazos):
        plan = _plan(brazos, "Per size")
        code = _code(brazos, "SIZED")
        rating_models.ChargeCodeAmount.objects.create(
            tenant=brazos, charge=code, size_class="2in", amount=Decimal("30.0000")
        )
        with pytest.raises(errors.BizError) as refused:
            selectors.billable_charge_codes(plan.id, date(2026, 8, 1))
    assert refused.value.br_ref == "BR-RAT-117"
    assert refused.value.params["code"] == "SIZED"
