"""`CR-166-BRC10` ruling 2 for fixtures: put an account's unit on a plan that
carries the discounts a test enrols it in.

PO 2026-10-03: *"Only accounts whose plan carries the discount can get it."*
Tests written before the ruling enrolled accounts whose unit was on no plan at
all; the product now refuses that by name (`rating.discounts.plan_does_not_carry`),
so those fixtures state the plan the ruling requires. Written to the ORM
directly because each caller's own fixture already writes the account that way;
nothing here is a rule — only the shape the rule needs to exist.
"""

from datetime import date
from typing import Any

from apps.rating import discounts as discount_models
from apps.rating import models as rating_models


def carry(tenant: Any, unit_id: Any, discounts: Any, *, since: date = date(2026, 1, 1)) -> Any:
    """The unit is on "Discount fixture plan" from `since`, and the plan binds
    every discount given. Idempotent."""
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        code="discount-fixture-plan",
        defaults={"name": "Discount fixture plan", "status": "published"},
    )
    if not rating_models.UnitPlanAssignment.objects.filter(
        tenant=tenant, unit_id=unit_id, assigned_to__isnull=True
    ).exists():
        rating_models.UnitPlanAssignment.objects.create(
            tenant=tenant,
            unit_id=unit_id,
            rate_plan=plan,
            plan_version=1,
            assigned_from=since,
            source="change_plan",
        )
    else:
        plan_id = (
            rating_models.UnitPlanAssignment.objects.filter(
                tenant=tenant, unit_id=unit_id, assigned_to__isnull=True
            )
            .values_list("rate_plan_id", flat=True)
            .first()
        )
        plan = rating_models.RatePlan.objects.get(pk=plan_id)
    for discount in discounts:
        discount_models.PlanDiscountRule.objects.get_or_create(
            tenant=tenant, rate_plan=plan, discount=discount
        )
    return plan
