"""CR-171-BRC10 P2.28–P2.31 (lane MVI-WIZ-BILL) — give the demo utility the
J4 worked case so the Billing step can be photographed beside images 41–44:
a plan that asks a Residential deposit of **$150.00** and names a one-time
**CONNECT $25.00**, and a one-time code the clerk adds, **RUSH $40.00** —
so the table reads $150.00 + $25.00 + $40.00 = **$215.00**, and $100.00 paid
by check leaves *"$115.00 goes on the first bill."*

It uses the same rows `06-backend/tests/test_cr171_p1_12_move_in_fees.py`
builds (`_code`, `PlanChargeRule`, `PlanDepositRule`), on the demo's
*Residential Standard* plan, whose vacant units are the walk's. The plan's
own `CONN` rule is detached so the plan names exactly the drawn rows.

    DATABASE_URL=postgres://…/<walk db> DJANGO_SETTINGS_MODULE=config.settings.local \\
      python 10-scripts/cr171_wiz_bill_world.py

⚠ It writes REAL rows. Never point it at a database somebody uses.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
from decimal import Decimal

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "06-backend"))

import django  # noqa: E402

django.setup()


def _load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def main() -> None:
    from django.db import transaction

    from apps.customers import models as customer_models
    from apps.rating import models as rating_models
    from core import tenancy as core_tenancy

    sjf = _load("seed_journey_fixture", REPO / "08-qa/01-e2e/stack/seed_journey_fixture.py")
    tenant, _actor = sjf.tenant_and_actor()
    fees = _load("cr171_fee_fixture", REPO / "06-backend/tests/test_cr171_p1_12_move_in_fees.py")

    with transaction.atomic(), core_tenancy.tenant_context(tenant.id):
        plan = rating_models.RatePlan.objects.get(tenant=tenant, name="Residential Standard")
        connect = fees._code(tenant, "CONNECT", Decimal("25.0000"), name="Connection")
        rush = fees._code(tenant, "RUSH", Decimal("40.0000"), name="Same-day turn-on")
        # A code with no GL is refused at the first bill's draft (§9.MONEY), so
        # both borrow the tenant's own connection fee's account.
        gl = rating_models.Charge.objects.get(tenant=tenant, code="CONN").gl_account_id
        for row in (connect, rush):
            row.gl_account_id = gl
            row.save(update_fields=["gl_account_id"])
        rating_models.PlanChargeRule.objects.filter(rate_plan=plan, charge__code="CONN").delete()
        rating_models.PlanChargeRule.objects.get_or_create(
            tenant=tenant, rate_plan=plan, charge=connect, defaults={"role": "charge"}
        )
        residential = customer_models.AccountType.objects.get(tenant_id=tenant.id, code="residential")
        rating_models.PlanDepositRule.objects.update_or_create(
            tenant=tenant,
            rate_plan=plan,
            account_type_id=residential.id,
            defaults={"amount": Decimal("150.0000"), "currency": "USD"},
        )
        # Image 41's Discounts (Autopay 0.50%, Paperless $1.00) and Tax
        # (*Non-profit*): the demo's own AUTOPAY and PAPERLESS programmes,
        # offered on this plan, and one exemption category on each tax the
        # plan's residential accounts pay.
        from apps.rating import discounts as discount_models
        from apps.rating import plan_reads

        for code in ("AUTOPAY", "PAPERLESS"):
            discount = discount_models.Discount.objects.get(tenant=tenant, code=code)
            discount_models.PlanDiscountRule.objects.get_or_create(
                tenant=tenant, rate_plan=plan, discount=discount
            )
        for row in plan_reads.plan_sections(plan.id).get("taxes") or []:
            tax = rating_models.Tax.objects.get(pk=row["ref"]["id"])
            rating_models.TaxExemptionCategory.objects.get_or_create(
                tenant=tenant, tax=tax, code="NONPROFIT",
                defaults={"name": "Non-profit", "requires_certificate": True},
            )
        print(f"plan {plan.name}: deposit $150.00 residential, CONNECT $25.00, RUSH $40.00, "
              "AUTOPAY + PAPERLESS offered, Non-profit exemption")


if __name__ == "__main__":
    main()
