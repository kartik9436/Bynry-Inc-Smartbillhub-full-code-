"""Give AC-2026-00041's unit (Apt 101, the PO's ACC-06 case: M-MASTER-01 +
W-5040 + sub-meter SM-7040) a sewer service billed as 90% of water USAGE —
the Ottumwa Water Works arrangement the demo data lacks.

Run on a PRIVATE copy of the demo database only, with DJANGO_SETTINGS_MODULE
and DATABASE_URL pointing at it:

    python 05-prototype/move-out-percent-service-2026-10-14/setup_sewer_share.py

Each step goes through the product's own service where one exists:
  * Settings > Services: sewer switched on (tenancy.update_tenant_service);
  * Premises > Edit: sewer added to the address's offered services
    (metering.update_premises);
  * Plans & Rates > New schedule: "Sewer at 90% of water" at $5.00/kgal,
    percent_of_service, usage basis, in force from 2026-01-01
    (rating.create_rate_schedule);
  * the schedule bound to the unit's published plan "Sample — Residential"
    (a PlanRateSchedule row, the way the test fixtures bind one — editing a
    published plan's schedule list is not what this walk is about);
  * the unit's sewer service point (metering.ensure_service_point) — no meter.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from apps.customers import models as customer_models  # noqa: E402
from apps.identity import models as identity_models  # noqa: E402
from apps.metering import models as metering_models  # noqa: E402
from apps.metering import services as metering_services  # noqa: E402
from apps.rating import models as rating_models  # noqa: E402
from apps.rating import services as rating_services  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from apps.tenancy import services as tenancy_services  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

ACCOUNT_NO = os.environ.get("ACCOUNT", "AC-2026-00041")
BASIS = os.environ.get("BASIS", "usage")


def main() -> int:
    tenant_id = core_tenancy.tenant_id_for_slug("brazosbend")
    with core_tenancy.tenant_context(tenant_id):
        user = identity_models.User.objects.filter(email__istartswith="dana@").first()
        actor = SimpleNamespace(id=user.id, pk=user.id, role="system_admin", user=user)
        account = customer_models.Account.objects.get(account_no=ACCOUNT_NO)
        unit = metering_models.Unit.objects.get(pk=account.unit_id)

        print("sewer on:", tenancy_services.update_tenant_service(actor, "sewer", {"enabled": True}).get("enabled"))

        premises = metering_models.Premises.objects.get(pk=unit.premises_id)
        offered = list(premises.services_available or [])
        if "sewer" not in offered:
            metering_services.update_premises(actor, premises.id, {"services_available": offered + ["sewer"]})
        print("premises offers:", metering_models.Premises.objects.get(pk=premises.id).services_available)

        # Settings > Charge codes — BR-RAT-088 refuses a schedule for a service
        # with no BASE charge code, so sewer gets one ($12.00, residential).
        if not rating_models.Charge.objects.filter(code="BASE-S", deleted_at__isnull=True).exists():
            rating_services.create_charge(
                actor,
                {
                    "code": "BASE-S",
                    "name": "Sewer base service — residential",
                    "charge_type": "recurring",
                    "service": "sewer",
                    "amount_rule": "flat",
                    "amount": "12.00",
                    "kind": "base",
                    "is_base": True,
                    "applies_to_customer_classes": ["residential"],
                    "effective_from": "2026-01-01",
                },
            )
        print("sewer base charge: BASE-S $12.00")

        structure = {"percent": "90", "basis_service": "water", "percent_basis": BASIS}
        if BASIS == "usage":
            structure["unit_price"] = "5.00"
        name = f"Sewer at 90% of water {BASIS} · DEF-BIL-10128 walk"
        tariff = rating_models.Tariff.objects.filter(name=name).first()
        if tariff is None:
            made = rating_services.create_rate_schedule(
                actor,
                {
                    "name": name,
                    "service": "sewer",
                    "model": "percent_of_service",
                    "uom": "kgal",
                    "effective_from": "2026-01-01",
                    "structure": structure,
                },
            )
            tariff = rating_models.Tariff.objects.get(pk=made["id"])
        print("schedule:", tariff.name)

        assignment = (
            rating_models.UnitPlanAssignment.objects.filter(unit_id=unit.id, assigned_to__isnull=True)
            .order_by("-assigned_from")
            .first()
        )
        plan = rating_models.RatePlan.objects.get(pk=assignment.rate_plan_id)
        sewer = tenancy_models.Service.objects.get(code="sewer")
        row, created = rating_models.PlanRateSchedule.objects.update_or_create(
            tenant_id=tenant_id, rate_plan=plan, service=sewer, defaults={"tariff": tariff}
        )
        print("plan:", plan.name, "binds sewer ->", row.tariff.name, "(new)" if created else "(updated)")

        point = metering_services.ensure_service_point(unit.id, "sewer")
        print("sewer service point:", getattr(point, "id", point))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
