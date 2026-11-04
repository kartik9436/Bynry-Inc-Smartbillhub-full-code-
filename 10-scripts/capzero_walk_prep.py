#!/usr/bin/env python3
"""capzero_walk_prep — the world for the "$0.00 capacity line is left off" walk.

PO ruling 2026-10-17 (decision log *"A $0.00 CAPACITY LINE IS LEFT OFF THE
BILL; MUNICIPAL SOLAR IS SETUP, NOT CODE"*), `DEF-RAT-10210`. Adds, on a cycle of
its own (`CAP0-SOLAR`, so no other account's decisions get in the way):

    CAP0-FLAT   solar 6 kW (one SOL-P6) + battery 10 kW (one BAT-10)
                plan "Solar + battery flat fee": both schedules $0.00 per kW,
                BASE-SOL $25.00 and BASE-BAT $25.00, 4% tax
                → $25.00 + $25.00 + 4% = $2.00 → $52.00, NO $0.00 capacity line
    CAP0-MUNI   solar 6 kW (one SOL-P6)
                plan "Municipal Solar": $4.00 per kW, BASE-MSOL $10.00 "All
                sizes", 4% tax → 6 kW × $4.00 = $24.00 + $10.00 + $1.36 = $35.36

Walk database only — never a shared or demo database:

    DATABASE_URL=postgres://…/smartbillhub_cap0 python 10-scripts/capzero_walk_prep.py

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

CYCLE_CODE = "CAP0-SOLAR"
FLAT_PLAN = "Solar + battery flat fee"
MUNI_PLAN = "Municipal Solar"
TAX_RATE = Decimal("0.04")
# (plan, {service: (per-kW rate, base code, base amount)})
PLANS = {
    FLAT_PLAN: {
        "solar": (Decimal("0.0000"), "BASE-SOL", Decimal("25.0000")),
        "battery": (Decimal("0.0000"), "BASE-BAT", Decimal("25.0000")),
    },
    MUNI_PLAN: {"solar": (Decimal("4.0000"), "BASE-MSOL", Decimal("10.0000"))},
}
WORLD = (
    ("CAP0-FLAT", "Rosa Delgado", FLAT_PLAN, (("solar", "pv", "SOL-P6"), ("battery", "battery", "BAT-10"))),
    ("CAP0-MUNI", "Hal Brenner", MUNI_PLAN, (("solar", "pv", "SOL-P6"),)),
)


def _cycle(tenant):
    from apps.metering import models as metering_models

    cycle = metering_models.Cycle.objects.filter(tenant=tenant, code=CYCLE_CODE).first()
    if cycle is None:
        cycle = metering_models.Cycle.objects.create(
            tenant=tenant, code=CYCLE_CODE, name="Solar walk — monthly",
            start_day=1, days_to_complete=30, bill_day=1, due_days=21,
        )
    return cycle


def _tax(tenant, actor):
    from apps.ledger import services as ledger_services
    from apps.rating import models as rm

    tax = rm.Tax.objects.filter(tenant=tenant, name="Solar walk 4% tax").first()
    if tax is not None:
        return tax
    jurisdiction = rm.TaxJurisdiction.objects.create(
        tenant=tenant, name="Solar walk town", authority="Solar walk town"
    )
    account = ledger_services.create_tax_authority_account(name="Solar walk town tax payable", actor=actor)
    return rm.Tax.objects.create(
        tenant=tenant, jurisdiction=jurisdiction, name="Solar walk 4% tax", kind="percent",
        rate=TAX_RATE, liability_gl_account_id=account.id,
    )


def _plan(tenant, actor, name, services, tax):
    from apps.rating import models as rm
    from apps.rating import selectors as rating_selectors
    from apps.rating import services as rating_services
    from apps.tenancy import models as tm

    from tests.test_us_met_helpers import make_plan

    plan = make_plan(tenant, name=name, services=tuple(services))
    for row in rating_selectors.plan_rate_schedules(plan.id):
        code = row["tariff"].service.code
        rate, base_code, base_amount = services[code]
        charge = rm.Charge.objects.filter(tenant=tenant, code=base_code, deleted_at__isnull=True).first()
        if charge is None:
            charge = rm.Charge.objects.create(
                tenant=tenant, code=base_code, name=f"{code.title()} base charge ({name})",
                charge_type="recurring", amount_rule="flat", amount=base_amount,
                service=tm.Service.objects.get(code=code), is_base=True,
            )
        if not rm.TariffVersion.objects.filter(tenant=tenant, tariff=row["tariff"]).exists():
            version = rm.TariffVersion.objects.create(
                tenant=tenant, tariff=row["tariff"], model="tiered", base_charge=Decimal("0"),
                base_charge_code=charge, uom="kW", currency="USD",
                effective_from=date(2025, 1, 1), effective_to=None,
            )
            rm.RateTier.objects.create(
                tenant=tenant, tariff_version=version, seq=1, from_qty=Decimal("0"),
                to_qty=None, unit_price=rate,
            )
    try:
        rating_services.attach_tax_to_plan(actor, plan.id, {"tax": str(tax.id), "reason": "capacity $0 walk"})
    except Exception as exc:  # a re-run: already attached, and the refusal says so
        print(f"  (tax on {name}: {str(exc)[:120]})")
    return plan


def seed(tenant, actor) -> list[str]:
    from apps.assets import models as asset_models
    from apps.assets import services as asset_services
    from apps.customers import models as customer_models
    from apps.customers import services as customer_services
    from apps.metering import models as metering_models
    from apps.metering import premises_owners
    from apps.metering import services as metering_services
    from apps.tenancy import models as tm
    from apps.tenancy import services as tenancy_services

    from tests.test_us_met_helpers import make_premises, make_unit

    notes: list[str] = []
    for code in ("solar", "battery"):
        tenancy_services.update_tenant_service(actor, code, {"enabled": True})
        tm.TenantService.objects.filter(tenant=tenant, service__code=code).update(billing_basis="capacity")
    cycle = _cycle(tenant)
    tax = _tax(tenant, actor)
    plans = {name: _plan(tenant, actor, name, services, tax) for name, services in PLANS.items()}
    notes.append(f"cycle {CYCLE_CODE}; tax {tax.name} {tax.rate}")

    for tag, person, plan_name, equipment in WORLD:
        label = f"{tag} Unit 1"
        if customer_models.Account.objects.filter(tenant=tenant, unit__label=label).exists():
            notes.append(f"{tag}: already seeded")
            continue
        services = [code for code, _kind, _size in equipment]
        owner = premises_owners.create_premises_owner(actor, {"name": f"Owner {tag}", "category": "landlord"})
        premises = make_premises(
            actor, address_line=f"{tag[-1]}4 Sunfield Way", services_available=services, owner_id=owner["id"]
        )
        unit = make_unit(actor, premises["id"], label=label, services=services)
        metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(cycle=cycle)
        metering_services.assign_unit_plan(
            actor, unit["id"], {"tariff_id": str(plans[plan_name].id), "effective_from": "2025-01-01"}
        )
        for n, (code, kind, size) in enumerate(equipment, start=1):
            asset_no = f"{tag}-{code[:3].upper()}{n}"
            if not asset_models.Asset.objects.filter(tenant=tenant, asset_no=asset_no).exists():
                asset_services.create_asset(
                    actor,
                    {
                        "type": kind, "asset_no": asset_no, "service": code, "unit_id": str(unit["id"]),
                        "install_date": "2026-01-05", "size_class": size,
                    },
                )
        created = customer_services.create_account(
            actor,
            {
                "unit_id": str(unit["id"]),
                "account_type": "residential",
                "opened_at": "2026-09-01",
                "contact": {"full_name": person, "phone": "555-0117", "email": f"{tag.lower()}@example.com"},
                "customer": {"display_name": person, "kind": "person", "identity": {"phone": "555-0117"}},
                "addresses": [
                    {"kind": "mailing", "line1": f"{tag[-1]}4 Sunfield Way", "city": "Katy", "state": "TX"}
                ],
            },
        )
        customer_services.activate_account(actor, created["id"])
        account = customer_models.Account.objects.get(pk=created["id"])
        notes.append(f"{tag}: {account.account_no} {person}, {plan_name}, {', '.join(s for *_x, s in equipment)}")
    notes.extend(_portal_logins(tenant))
    return notes


PORTAL_PASSWORD = "Sunfield-2026!"


def _portal_logins(tenant) -> list[str]:
    """Turn the walk copy's portal on and give each walk account a login, so the
    customer's own bill page can be opened. Walk database only."""
    from apps.customers import models as customer_models
    from apps.portal import credentials
    from apps.portal import models as portal_models

    portal_models.PortalSettings.objects.filter(tenant=tenant).update(is_live=True)
    out = []
    for tag, *_rest in WORLD:
        email = f"{tag.lower()}@example.com"
        if credentials.credential_by_email(tenant.id, email) is not None:
            continue
        account = customer_models.Account.objects.get(tenant=tenant, unit__label=f"{tag} Unit 1")
        credentials.create_credential(
            tenant.id, account=account, email=email, password=PORTAL_PASSWORD, otp_channel="email"
        )
        out.append(f"{tag}: portal login {email} / {PORTAL_PASSWORD}")
    return out


def main() -> int:
    sjf.django_setup()
    from core import tenancy as core_tenancy

    tenant, actor = sjf.tenant_and_actor()
    with core_tenancy.tenant_context(tenant.id):
        from django.db import transaction

        with transaction.atomic():
            notes = seed(tenant, actor)
    print("capacity $0 walk world seeded on " + CYCLE_CODE + ":")
    for line in notes:
        print("  " + line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
