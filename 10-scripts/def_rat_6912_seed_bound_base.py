#!/usr/bin/env python3
"""`DEF-RAT-6912` — seed the PO's own live-beta case so it can be photographed.

WHAT IT BUILDS, on `brazosbend` and nowhere else:
  * two WATER base charge codes — `BASE-W` with **no amount at all** and
    `BASE-W-FIRE` at **$12.00**. Both `is_base`, which is the state a tenant
    reaches by ticking the box on CHG-02 step 1.
  * `BASE-W-FIRE` NAMED as the in-force version's `base_charge_code` on the
    water schedule the plan binds (`tariff_versions.base_charge_code`,
    `BR-RAT-1025`).
  * a plan, `RES-CITY`, binding water to that schedule.

⚠ **THE TWO CODES MUST PRICE DIFFERENTLY OR THE PHOTOGRAPH PROVES NOTHING.**
On every tenant today the named and the inferred code are the SAME code, so a
screenshot of a panel reading `$12.00 · …` cannot say which route answered it.
`BASE-W` is left with a null amount deliberately: the defect's own screenshot
read *"No amount set · from BASE-W"*, and that sentence is the thing that must
stop appearing.

It is re-entrant: every row is looked up by code before it is written, so a
second run re-points the binding and changes nothing else.

    DJANGO_SETTINGS_MODULE=config.settings.local \
    DATABASE_URL=postgres://... python 10-scripts/def_rat_6912_seed_bound_base.py [--unbind]

`--unbind` clears `base_charge_code` again, which is walk step 3 (the schedule
names nothing and the screen falls back to the inferred code).
"""

from __future__ import annotations

import os
import sys
import pathlib

BACKEND = pathlib.Path(__file__).resolve().parents[1] / "06-backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402
from django.utils import timezone  # noqa: E402

django.setup()

from core import tenancy as core_tenancy  # noqa: E402
from apps.tenancy import models as tm  # noqa: E402
from apps.rating import models as rm  # noqa: E402
from apps.rating import selectors  # noqa: E402

SUBDOMAIN = os.environ.get("SEED_TENANT", "brazosbend")
UNBIND = "--unbind" in sys.argv
RETIRE = "--retire-bound" in sys.argv


def main() -> int:
    tenant = tm.Tenant.objects.get(subdomain=SUBDOMAIN)
    with core_tenancy.tenant_context(tenant.id):
        water = tm.Service.objects.get(code="water")
        tariff = (
            rm.Tariff.objects.filter(tenant_id=tenant.id, service_id=water.id, deleted_at=None)
            .order_by("created_at")
            .first()
        )
        if tariff is None:
            print("no water schedule on this tenant — nothing to bind")
            return 2
        # ⚠ **THE VERSION IN FORCE TODAY, NEVER MERELY THE LATEST.**
        # `schedule_card.current_version` is `selectors.in_force_version`, and a
        # future-dated filing outranks it on `effective_from` while pricing
        # nothing. Binding the wrong row would seed a case the screen is right
        # to ignore, and the photograph would then prove the opposite of what
        # it claims.
        from datetime import date

        version = selectors.in_force_version(tariff, date.today())
        if version is None:
            print("water schedule has no in-force version — nothing to bind")
            return 2

        plain, _ = rm.Charge.objects.get_or_create(
            tenant_id=tenant.id,
            code="BASE-W",
            defaults=dict(
                name="Water base",
                charge_type="recurring",
                service_id=water.id,
                amount_rule="flat",
                amount=None,          # DEF-277 — absent is NOT zero
                is_base=True,
                taxable_default=False,
                auto_apply=True,
                waivable=False,
                separate_line=True,
                applies_to_customer_classes=[],
            ),
        )
        fire, _ = rm.Charge.objects.get_or_create(
            tenant_id=tenant.id,
            code="BASE-W-FIRE",
            defaults=dict(
                name="Water base · fire line",
                charge_type="recurring",
                service_id=water.id,
                amount_rule="flat",
                amount="12.0000",
                is_base=True,
                taxable_default=False,
                auto_apply=True,
                waivable=False,
                separate_line=True,
                applies_to_customer_classes=[],
            ),
        )
        # `plain` must sort FIRST for the inferred route to pick it — the
        # selector takes the first `is_base` row for the service, so a fixture
        # where the named code happens to be first proves nothing.
        rm.Charge.objects.filter(pk=plain.pk).update(deleted_at=None)

        if UNBIND:
            version.base_charge_code = None
        elif RETIRE:
            version.base_charge_code = fire
            rm.Charge.objects.filter(pk=fire.pk).update(
                deleted_at=timezone.now()
            )
        else:
            version.base_charge_code = fire
            rm.Charge.objects.filter(pk=fire.pk).update(deleted_at=None)
        version.save(update_fields=["base_charge_code", "updated_at"])

        plan, made = rm.RatePlan.objects.get_or_create(
            tenant_id=tenant.id,
            code="RES-CITY",
            defaults=dict(
                name="Residential City Plan",
                description="DEF-RAT-6912 walk",
                account_type_ids=[],
                status="draft",
                version=1,
            ),
        )
        rm.PlanService.objects.get_or_create(
            tenant_id=tenant.id,
            rate_plan_id=plan.id,
            service_id=water.id,
            defaults=dict(base_charge=None, outside_city_exempt=False, currency="USD"),
        )
        rm.PlanRateSchedule.objects.update_or_create(
            tenant_id=tenant.id,
            rate_plan_id=plan.id,
            service_id=water.id,
            defaults=dict(tariff_id=tariff.id),
        )

        print(f"tenant      {tenant.subdomain} {tenant.id}")
        print(f"schedule    {tariff.name} {tariff.id}")
        print(f"version     {version.id} effective {version.effective_from}")
        print(f"names       {version.base_charge_code_id}")
        print(f"BASE-W      {plain.id} amount={plain.amount}")
        print(f"BASE-W-FIRE {fire.id} amount={fire.amount}")
        print(f"plan        {plan.code} {plan.id} ({'created' if made else 'reused'})")
        print(f"URL         /{tenant.subdomain}/plans-rates/plans/{plan.id}/edit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
