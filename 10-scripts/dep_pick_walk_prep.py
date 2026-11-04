"""DEF-CUS-9521 (lane DEP-PICK) — the data `dep_pick_walk.mjs` needs, written
ONCE and stated here. PO 2026-10-04, verbatim: *"(c) Let the clerk pick the
size on the Deposit step."*

1. The refundable charge code `DEP-SIZE` on water, priced 5/8" **$150.00** and
   2" **$600.00** (the ruling's worked figures), through
   `services.create_charge` — the write the Charge codes screen makes.
2. `SCW-RES` names `DEP-SIZE` as its deposit, through `plan_writes.correct` —
   the write *Fix a mistake* makes (CR-167 §15.3 did it through the screen).
3. **Probe shortcut, stated:** every vacant seeded unit has a water service
   point and NO meter, so `SCW-U-207` is given a 5/8" (W-58) water meter by
   copying a seeded meter row (new number, its service point, an assignment
   from 2026-08-01) — the *meter fitted* case. `SCW-U-355` is left with no
   meter — the ruling's *no meter fitted* case. Probe database only.

    DATABASE_URL=postgres://postgres@127.0.0.1:55433/sbh_deppick \\
    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    /tmp/venv_a5c/bin/python 10-scripts/dep_pick_walk_prep.py
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
from apps.rating import models, plan_writes, services  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

Asset = apps.get_model("assets", "Asset")
AssetAssignment = apps.get_model("assets", "AssetAssignment")
Unit = apps.get_model("metering", "Unit")


def main() -> int:
    tenant = tenancy_models.Tenant.objects.get(subdomain="brazosbend")
    core_tenancy.set_current_tenant(tenant.id)
    owner = identity_models.User.objects.filter(tenant_id=tenant.id).order_by("created_at").first()
    actor = SimpleNamespace(
        id=owner.id, pk=owner.id, role="system_admin", roles=("system_admin",), is_authenticated=True
    )
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
    plan = models.RatePlan.objects.get(tenant_id=tenant.id, code="SCW-RES")
    named = [
        rule.charge.code
        for rule in models.PlanChargeRule.objects.filter(rate_plan_id=plan.id, role="deposit")
    ]
    if named != ["DEP-SIZE"]:
        plan_writes.correct(
            actor,
            plan.id,
            {"deposits": [{"charge": "DEP-SIZE"}], "reason": "The plan asks a deposit by meter size"},
        )
        named = [
            rule.charge.code
            for rule in models.PlanChargeRule.objects.filter(rate_plan_id=plan.id, role="deposit")
        ]
    print(f"SCW-RES deposits: {named}")
    for unit_no, size in (("SCW-U-207", "W-58"),):
        unit = Unit.objects.get(tenant_id=tenant.id, unit_no=unit_no)
        if metering_selectors.connection_size_for(unit.id, "water") == size:
            print(f"{unit_no}: already {size}")
            continue
        point = metering_selectors._service_point_for(unit.id, "water")  # noqa: SLF001
        template = Asset.objects.filter(
            tenant_id=tenant.id, size_class=size, service_point__isnull=False
        ).order_by("asset_no").first()
        clone = Asset.objects.get(pk=template.pk)
        clone.pk = uuid.uuid4()
        clone.id = clone.pk
        clone.asset_no = f"WALK-{unit_no}"
        clone.serial_no = f"WALK-{unit_no}"
        clone.external_ref = None
        clone.service_point_id = point.id
        clone.size_class = size
        clone.save(force_insert=True)
        AssetAssignment.objects.create(tenant_id=tenant.id, asset=clone, unit=unit, from_date=date(2026, 8, 1))
        print(f"{unit_no}: water meter {clone.asset_no} -> {metering_selectors.connection_size_for(unit.id, 'water')}")
    unit = Unit.objects.get(tenant_id=tenant.id, unit_no="SCW-U-355")
    print(f"SCW-U-355: water size {metering_selectors.connection_size_for(unit.id, 'water')!r} (no meter)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
