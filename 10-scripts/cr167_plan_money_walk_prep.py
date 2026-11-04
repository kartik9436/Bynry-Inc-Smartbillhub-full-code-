"""CR-167-BRC10 follow-up (lane PLAN-MONEY) — the data `cr167_plan_money_walk.mjs`
needs and the product has no seeded shape for, written ONCE, stated here.

1. The refundable charge code `DEP-SIZE` on water, priced 5/8" **$150.00** and
   2" **$600.00** (the PO's worked figures, `OQ-RAT-12786`), through
   `services.create_charge` — the same write the Charge codes screen makes.
2. **Probe shortcut, stated:** New account offers only VACANT units, and every
   vacant unit on the seeded `SCW-RES` plan has a water service point and NO
   meter on it — so no vacant unit has a connection size. Three of them are
   given a water meter by copying an existing seeded meter row of the wanted
   size (new number, the vacant unit's service point, an assignment from
   2026-08-01): `SCW-U-207` 5/8" (W-58), `SCW-U-351` 2" (W-2), `SCW-U-353`
   3/4" (W-34, a size DEP-SIZE does not price). `SCW-U-355` is left with no
   meter (no size recorded). Probe database only (`sbh_planmoney`).

    DATABASE_URL=postgres://postgres@127.0.0.1:55433/sbh_planmoney \\
    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    /tmp/venv_a5c/bin/python 10-scripts/cr167_plan_money_walk_prep.py
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import date
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.apps import apps  # noqa: E402

from apps.identity import models as identity_models  # noqa: E402
from apps.metering import selectors as metering_selectors  # noqa: E402
from apps.rating import models, services  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

Asset = apps.get_model("assets", "Asset")
AssetAssignment = apps.get_model("assets", "AssetAssignment")
Unit = apps.get_model("metering", "Unit")


def main() -> int:
    tenant = tenancy_models.Tenant.objects.get(subdomain="brazosbend")
    core_tenancy.set_current_tenant(tenant.id)
    owner = identity_models.User.objects.filter(tenant_id=tenant.id).order_by("created_at").first()
    actor = SimpleNamespace(id=owner.id, pk=owner.id, role="system_admin", roles=("system_admin",), is_authenticated=True)
    if not models.Charge.objects.filter(tenant_id=tenant.id, code="DEP-SIZE").exists():
        services.create_charge(
            actor,
            {
                "code": "DEP-SIZE",
                "name": "Security deposit by meter size",
                "charge_type": "refundable",
                "service": "water",
                "amount_rule": "flat",
                "is_base": False,
                "size_amounts": [
                    {"size_class": "W-58", "amount": "150.00"},
                    {"size_class": "W-2", "amount": "600.00"},
                ],
                "effective_from": "2026-08-01",
            },
        )
        print("created DEP-SIZE")
    for unit_no, size in (("SCW-U-207", "W-58"), ("SCW-U-351", "W-2"), ("SCW-U-353", "W-34")):
        unit = Unit.objects.get(tenant_id=tenant.id, unit_no=unit_no)
        if metering_selectors.connection_size_for(unit.id, "water") == size:
            print(f"{unit_no}: already {size}")
            continue
        point = metering_selectors._service_point_for(unit.id, "water")  # noqa: SLF001
        template = (
            Asset.objects.filter(tenant_id=tenant.id, size_class=size, service_point__isnull=False)
            .order_by("asset_no")
            .first()
        )
        if template is None:
            template = Asset.objects.filter(tenant_id=tenant.id, size_class="W-58", service_point__isnull=False).first()
        clone = Asset.objects.get(pk=template.pk)
        clone.pk = uuid.uuid7() if hasattr(uuid, "uuid7") else uuid.uuid4()
        clone.id = clone.pk
        clone.asset_no = f"WALK-{unit_no}"
        clone.serial_no = f"WALK-{unit_no}"
        clone.external_ref = None
        clone.service_point_id = point.id
        clone.size_class = size
        clone.save(force_insert=True)
        AssetAssignment.objects.create(
            tenant_id=tenant.id, asset=clone, unit=unit, from_date=date(2026, 8, 1)
        )
        print(f"{unit_no}: water meter {clone.asset_no} {size} -> connection size "
              f"{metering_selectors.connection_size_for(unit.id, 'water')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
