#!/usr/bin/env python3
"""capbase_walk_prep — two TRASH accounts on the J72 cycle, for the capacity-base walk.

PO ruling 2026-10-01 (decision log *"BUILT: A CAPACITY BASE IS LOOKED UP BY SIZE
ON EVERY BILL"*, BR-BIL-1067). The J72 world (`seed_j72_bulk_run`) bills water
and electric only, so it cannot show a base found by size. This adds, to the
SAME cycle `J72-RIVERSIDE`, two premises with one unit each taking trash only:

    CAP-WALK-A   2 × CART-96            base 2 × $3.00 + carts 2 × $15.00 = $36.00
    CAP-WALK-B   1 × CART-96, 1 × CART-35
                 BASE-T prices CART-96 and CART-64 and NOT CART-35, so CART-35's
                 base bills $0.00 with the warning "BASE-T has no price for
                 CART-35. Billed $0.00." → $3.00 + $0.00 + 2 × $15.00 = $33.00

BASE-T is created PER SIZE (no flat amount), the shape a per-size code has on
the charge-code screen. Walk database only — never a shared or demo database:

    DATABASE_URL=postgres://…/sbh_cap72 python 10-scripts/capbase_walk_prep.py

Idempotent on its own rows (re-running finds them and adds nothing).
"""

from __future__ import annotations

import importlib.util
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "06-backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

_spec = importlib.util.spec_from_file_location(
    "seed_journey_fixture", REPO / "08-qa/01-e2e/stack/seed_journey_fixture.py"
)
sjf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sjf)  # type: ignore[union-attr]

CYCLE_CODE = "J72-RIVERSIDE"
PLAN_NAME = "Trash by cart (capacity walk)"
PER_CART = Decimal("15.0000")
BASE_T = {"CART-96": Decimal("3.0000"), "CART-64": Decimal("2.0000")}
WORLD = (
    ("CAP-WALK-A", "Lena Ortiz", ("CART-96", "CART-96")),
    ("CAP-WALK-B", "Marco Diaz", ("CART-96", "CART-35")),
)


def seed(tenant, actor) -> list[str]:
    from apps.assets import models as asset_models
    from apps.assets import services as asset_services
    from apps.customers import models as customer_models
    from apps.customers import services as customer_services
    from apps.metering import models as metering_models
    from apps.metering import premises_owners
    from apps.metering import services as metering_services
    from apps.rating import models as rm
    from apps.rating import selectors as rating_selectors
    from apps.tenancy import models as tm
    from apps.tenancy import services as tenancy_services

    from tests.test_us_met_helpers import make_plan, make_premises, make_unit

    notes: list[str] = []
    tenancy_services.update_tenant_service(actor, "trash", {"enabled": True})
    trash = tm.Service.objects.get(code="trash")
    tm.TenantService.objects.filter(tenant=tenant, service=trash).update(billing_basis="capacity")
    cycle = metering_models.Cycle.objects.get(tenant=tenant, code=CYCLE_CODE)

    plan = make_plan(tenant, name=PLAN_NAME, services=("trash",))
    for row in rating_selectors.plan_rate_schedules(plan.id):
        if not rm.TariffVersion.objects.filter(tenant=tenant, tariff=row["tariff"]).exists():
            version = rm.TariffVersion.objects.create(
                tenant=tenant,
                tariff=row["tariff"],
                model="tiered",
                base_charge=Decimal("0"),
                uom="cart",
                currency="USD",
                effective_from=date(2025, 1, 1),
                effective_to=None,
            )
            rm.RateTier.objects.create(
                tenant=tenant, tariff_version=version, seq=1, from_qty=Decimal("0"),
                to_qty=None, unit_price=PER_CART,
            )
    charge = rm.Charge.objects.filter(tenant=tenant, code="BASE-T", deleted_at__isnull=True).first()
    if charge is None:
        charge = rm.Charge.objects.create(
            tenant=tenant, code="BASE-T", name="Trash base charge", charge_type="recurring",
            amount_rule="flat", amount=None, service=trash, is_base=True,
        )
        for size, amount in BASE_T.items():
            rm.ChargeCodeAmount.objects.create(tenant=tenant, charge=charge, size_class=size, amount=amount)
    notes.append(f"BASE-T per size: {', '.join(f'{k} ${v:.2f}' for k, v in BASE_T.items())}; CART-35 not priced")

    for tag, name, carts in WORLD:
        if customer_models.Account.objects.filter(tenant=tenant, unit__label=f"{tag} Unit 1").exists():
            notes.append(f"{tag}: already seeded")
            continue
        owner = premises_owners.create_premises_owner(actor, {"name": f"Owner {tag}", "category": "landlord"})
        premises = make_premises(
            actor, address_line=f"{tag[-1]}0 Riverside Ct", services_available=["trash"], owner_id=owner["id"]
        )
        unit = make_unit(actor, premises["id"], label=f"{tag} Unit 1", services=["trash"])
        metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(cycle=cycle)
        metering_services.assign_unit_plan(
            actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
        )
        for n, size in enumerate(carts, start=1):
            asset_no = f"{tag}-C{n}"
            if not asset_models.Asset.objects.filter(tenant=tenant, asset_no=asset_no).exists():
                asset_services.create_asset(
                    actor,
                    {
                        "type": "container_cart", "asset_no": asset_no, "service": "trash",
                        "unit_id": str(unit["id"]), "install_date": "2026-01-05", "size_class": size,
                    },
                )
        created = customer_services.create_account(
            actor,
            {
                "unit_id": str(unit["id"]),
                "account_type": "residential",
                "opened_at": "2026-08-01",
                "contact": {"full_name": name, "phone": "555-0172"},
                "customer": {"display_name": name, "kind": "person", "identity": {"phone": "555-0172"}},
                "addresses": [
                    {"kind": "mailing", "line1": f"{tag[-1]}0 Riverside Ct", "city": "Katy", "state": "TX"}
                ],
            },
        )
        customer_services.activate_account(actor, created["id"])
        account = customer_models.Account.objects.get(pk=created["id"])
        notes.append(f"{tag}: {account.account_no} {name}, carts {', '.join(carts)}")
    return notes


def main() -> int:
    sjf.django_setup()
    from core import tenancy as core_tenancy

    tenant, actor = sjf.tenant_and_actor()
    with core_tenancy.tenant_context(tenant.id):
        from django.db import transaction

        with transaction.atomic():
            notes = seed(tenant, actor)
    print("capacity-base walk world seeded on " + CYCLE_CODE + ":")
    for line in notes:
        print("  " + line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
