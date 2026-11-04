# ── Trace ──────────────────────────────────────────────
# Change:  DEF-CUS-9821 — the world New Connect step 2's This-plan block is
#          walked on (`def_cus_9821_plan_block_walk.mjs`).
# ───────────────────────────────────────────────────────
"""def_cus_9821_plan_block_world — the drawing's plan, on a CR-171 matrix world.

    cd 06-backend && DATABASE_URL=postgres://…/<db> DJANGO_SETTINGS_MODULE=config.settings.local \\
        JOBS_EAGER=false CELERY_BROKER_URL=memory:// python ../10-scripts/def_cus_9821_plan_block_world.py [tenant]

Idempotent. On the tenant (default `mvimatrix`):
  * Battery switched on (the Settings act);
  * Battery base codes `BASE-BAT` (every class, $6.00) and `BASE-BAT-RES`
    (Residential, $5.00) — so a Residential account has TWO that could serve;
  * the schedule *Municipal Battery Service Rate* (0–500 kWh $0.0425, over
    500 kWh $0.0390), written through the screen's own service, then its
    version's base code CLEARED — the state `DEF-RAT-9797` lists as *"live,
    names no base code"* (a schedule saved before that ruling);
  * the plan `MBSP` *Municipal Solar PV & Battery Service Plan*, published
    from 10/01/2026: Solar on the sample solar schedule (which names
    `BASE-SOL`), Battery on the schedule above, the tenant's late fee and
    deposit, every tax and every offered discount.
The walk's figures, never signed law.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.db import transaction  # noqa: E402

from apps.rating import discounts as dm  # noqa: E402
from apps.rating import models as rm  # noqa: E402
from apps.rating import plan_writes  # noqa: E402
from apps.rating import services as rsvc  # noqa: E402
from apps.tenancy import models as tm  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

SLUG = sys.argv[1] if len(sys.argv) > 1 else "mvimatrix"


def main() -> None:
    tenant = tm.Tenant.objects.get(subdomain=SLUG)
    with core_tenancy.tenant_context(tenant.id):
        from apps.identity import models as im

        from types import SimpleNamespace

        # The tenant's own System Admin, carrying THEIR role — never a typed one.
        membership = (
            im.TenantMembership.objects.filter(tenant=tenant, role__code="system_admin")
            .select_related("user", "role")
            .order_by("user__created_at")
            .first()
        )
        actor = SimpleNamespace(id=membership.user.id, pk=membership.user.id, user=membership.user, role=membership.role.code)
        with transaction.atomic():
            from tests.journey_cohort_fixtures import ensure_services_enabled

            print("services on:", ensure_services_enabled(tenant, actor, "solar", "battery"))
        with transaction.atomic():
            if not rm.Charge.objects.filter(tenant=tenant, code="BASE-BAT").exists():
                rsvc.create_charge(actor, {
                    "code": "BASE-BAT", "name": "Battery base", "service": "battery",
                    "charge_type": "recurring", "amount_rule": "flat", "amount": "6.00",
                    "is_base": True, "effective_from": "2026-08-01",
                })
            tariff = rm.Tariff.objects.filter(tenant=tenant, name="Municipal Battery Service Rate").first()
            if tariff is None:
                made = rsvc.create_rate_schedule(actor, {
                    "name": "Municipal Battery Service Rate", "service": "battery", "model": "tiered",
                    "uom": "kWh", "effective_from": "2026-10-01",
                    "structure": {"tiers": [
                        {"from_qty": "0", "to_qty": "500", "unit_price": "0.0425"},
                        {"from_qty": "500", "to_qty": None, "unit_price": "0.0390"},
                    ]},
                })
                tariff = rm.Tariff.objects.get(pk=made["id"])
            if not rm.Charge.objects.filter(tenant=tenant, code="BASE-BAT-RES").exists():
                rsvc.create_charge(actor, {
                    "code": "BASE-BAT-RES", "name": "Battery base, residential", "service": "battery",
                    "charge_type": "recurring", "amount_rule": "flat", "amount": "5.00",
                    "is_base": True, "applies_to_customer_classes": ["residential"],
                    "effective_from": "2026-08-01",
                })
            cleared = rm.TariffVersion.objects.filter(tenant=tenant, tariff=tariff).update(base_charge_code=None)
            print("battery schedule versions naming no base code:", cleared)
            # The sample solar schedule was seeded before `DEF-RAT-9797`'s
            # ruling and names none; a schedule saved today names the only
            # code that serves it — `BASE-SOL` — so the walk's Solar does too.
            sol_code = rm.Charge.objects.get(tenant=tenant, code="BASE-SOL")
            named = rm.TariffVersion.objects.filter(
                tenant=tenant, tariff__service__code="solar", tariff__deleted_at__isnull=True
            ).update(base_charge_code=sol_code)
            print("solar schedule versions naming BASE-SOL:", named)
            if not rm.Charge.objects.filter(tenant=tenant, code="DEPOSIT").exists():
                rsvc.create_charge(actor, {
                    "code": "DEPOSIT", "name": "Security deposit", "charge_type": "refundable",
                    "amount_rule": "flat", "is_base": False, "effective_from": "2026-08-01",
                    "size_amounts": [
                        {"size_class": "All sizes", "customer_class": "residential", "amount": "150.00"},
                        {"size_class": "All sizes", "customer_class": "commercial", "amount": "300.00"},
                    ],
                })
        with transaction.atomic():
            if rm.RatePlan.objects.filter(tenant=tenant, code="MBSP").exists():
                print("plan MBSP exists")
                return
            solar = rm.Tariff.objects.get(tenant=tenant, service__code="solar", deleted_at__isnull=True, name__icontains="solar")
            late = rm.Charge.objects.filter(tenant=tenant, charge_type="penalty", deleted_at__isnull=True).order_by("code").first()
            deposit = rm.Charge.objects.get(tenant=tenant, code="DEPOSIT")
            taxes = list(rm.Tax.objects.filter(tenant=tenant, deleted_at__isnull=True, is_draft=False, superseded_by__isnull=True))
            discounts = [
                one.code
                for one in dm.Discount.objects.filter(tenant=tenant)
                if dm.DiscountVersion.objects.filter(discount=one, status=dm.VERSION_ACTIVE).exists()
            ][:3]
            plan = plan_writes.create(actor, {
                "details": {"name": "Municipal Solar PV & Battery Service Plan", "code": "MBSP", "customer_classes": []},
                "services": [
                    {"service": "solar", "schedule": str(solar.id)},
                    {"service": "battery", "schedule": str(tariff.id)},
                ],
                "charge_codes": [{"charge": late.code}] if late else [],
                "taxes": [{"tax": str(tax.id)} for tax in taxes],
                "deposits": [{"charge": deposit.code}] if deposit else [],
                "discounts": [{"discount": code} for code in discounts],
                "minimum_bill_amount": None,
                "effective_from": "2026-10-01",
                "publish": True,
            })
            print("plan", plan["code"], plan["status"], plan["id"])


if __name__ == "__main__":
    main()
