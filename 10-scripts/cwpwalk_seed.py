#!/usr/bin/env python3
"""cwpwalk_seed — the world for the 21-walk portal-request web walk (2026-10-02).

Walk script: `10-scripts/cwpwalk_portal_walk21.mjs` · read-back:
`10-scripts/cwpwalk_readback.py` · results:
`08-qa/screens/portal-walk21-2026-10-02/RESULTS.md`.

PO 2026-10-01, verbatim: *"When you take utilty take it for 6 utility services water,
trash, sewer, fire, solar and battery - self service portal"*. So this REUSES
`cr158_seed_portal_upload.py` — Six Rivers Utility (`sixrivers`), exactly those six
services, the portal live — and adds what a walk of TWELVE applications needs:

  * a billing CLERK who signs in (the PO's *"clark"*), Dana Mercer — the walk is
    the clerk's, not the owner's;
  * EIGHT addresses ON FILE, one per walk that applies at a known address. Four
    are single-unit (the applicant types no unit) and four are three-unit
    buildings (the applicant types the unit). A one-service walk's address
    carries ONLY that service, because the portal derives what is asked for from
    what the address carries — the applicant ticks nothing on a known address;
  * SIX customers already on file, each with an active account at
    `700 Kingfisher Lane` and a portal login, for the six walks that LINK.

Every row goes through the owning module's own service, as a clerk's screen would.
Idempotent: re-running changes nothing already there.

    cd 06-backend && DATABASE_URL=postgres://…/<db> DJANGO_SETTINGS_MODULE=config.settings.local \\
        JOBS_EAGER=true python ../10-scripts/cwpwalk_seed.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

SIX = ["water", "sewer", "trash", "fire", "solar", "battery"]
#: The equipment that SIZES each capacity service — codes Six Rivers' own
#: sample set already plants (`select … from assets`), never invented here.
SIZES = {"trash": "CART-96", "fire": "FL-4", "solar": "SOL-P4", "battery": "BAT-10"}
EQUIPMENT = {"trash": "container_cart", "fire": "fire_line", "solar": "pv", "battery": "battery"}
POSTCODE = "77494"
CLERK_EMAIL = "dana.mercer@sixriversutility.com"
PASSWORD = "S3cure!passw0rd"  # walk fixture credential — never prod
PORTAL_PASSWORD = "Six-Rivers-Walk-2026"

#: The addresses on file. (address, unit labels, services)
ON_FILE = [
    ("14 Alder Run", ["Main"], ["water"]),
    ("16 Alder Run", ["Main"], SIX),
    ("18 Alder Run", ["Main"], ["sewer"]),
    ("20 Alder Run", ["Main"], SIX),
    ("400 Heron Court", ["Unit 1", "Unit 2", "Unit 3"], ["trash"]),
    ("402 Heron Court", ["Unit 1", "Unit 2", "Unit 3"], SIX),
    ("404 Heron Court", ["Unit 1", "Unit 2", "Unit 3"], ["fire"]),
    ("406 Heron Court", ["Unit 1", "Unit 2", "Unit 3"], SIX),
]

#: The customers already on file, one per LINK walk. (label, name, kind, phone,
#: tax id, portal email). Each phone differs from what its applicant types, so
#: nothing but the clerk's link can join them.
EXISTING = [
    ("W2", "Marcus Bell", "person", "(281) 555-0102", None, "marcus.bell@example.test"),
    ("W4", "Alder Freight Co", "company", "(281) 555-0104", "74-1000004", "ap@alderfreight.test"),
    ("W5", "Nadia Rahman", "person", "(281) 555-0105", None, "nadia.rahman@example.test"),
    ("W8", "Heron Court Partners LLC", "company", "(281) 555-0108", "74-1000008", "ops@heroncourt.test"),
    ("W10", "Tomas Vega", "person", "(281) 555-0110", None, "tomas.vega@example.test"),
    ("W11", "Kestrel Energy Co-op", "company", "(281) 555-0111", "74-1000011", "office@kestrel.test"),
]
KINGFISHER = "700 Kingfisher Lane"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _clerk(tenant):
    from django.contrib.auth.hashers import make_password
    from django.utils import timezone

    from apps.identity import models as im

    user = im.User.objects.filter(tenant=tenant, email__iexact=CLERK_EMAIL).first()
    if user is None:
        user = im.User.objects.create(
            tenant=tenant,
            email=CLERK_EMAIL,
            full_name="Dana Mercer",
            phone="(281) 555-0190",
            password_hash=make_password(PASSWORD),
            must_change_password=False,
            password_changed_at=timezone.now(),
        )
        im.TenantMembership.objects.create(
            tenant=tenant,
            user=user,
            role=im.Role.objects.get(code="billing_clerk"),
            status=im.TenantMembership.STATUS_ACTIVE,
        )
    return user


def _premises(tenant, actor, plan_id, address, labels, services, n0):
    from apps.assets import services as asset_services
    from apps.metering import models as mm
    from apps.metering import services as metering_services
    from tests.test_us_met_helpers import make_premises, make_unit

    row = mm.Premises.objects.filter(tenant=tenant, address_line=address).first()
    if row is not None:
        return str(row.id)
    premises = make_premises(
        actor,
        address_line=address,
        city="Katy",
        state="TX",
        postal_code=POSTCODE,
        premises_type="apartment_complex" if len(labels) > 1 else "single_family",
        services_available=list(services),
        owner_manager="Riverbend Holdings LLC",
    )
    for n, label in enumerate(labels):
        unit = make_unit(actor, premises["id"], label=label)
        metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(plan_id)})
        for code in services:
            metering_services.ensure_service_point(unit["id"], code)
        tag = f"{n0:02d}{n}"
        if "water" in services:
            asset_services.create_asset(
                actor,
                {
                    "type": "meter",
                    "asset_no": f"WM-WALK-{tag}",
                    "service": "water",
                    "unit": "gal",
                    "read_method": "manual",
                    "multiplier": "1",
                    "unit_id": unit["id"],
                    "install_date": "2026-01-02",
                    "size_class": "W-58",
                },
            )
        for code, size in SIZES.items():
            if code not in services:
                continue
            asset_services.create_asset(
                actor,
                {
                    "type": EQUIPMENT[code],
                    "asset_no": f"{code[:3].upper()}-WALK-{tag}",
                    "service": code,
                    "unit_id": unit["id"],
                    "install_date": "2026-01-02",
                    "size_class": size,
                },
            )
    return premises["id"]


def _existing(actor, tenant, unit_ids):
    from apps.customers import models as cm
    from apps.customers import services as customers_services
    from apps.portal import credentials
    from apps.portal import models as pm

    made = []
    for (walk, name, kind, phone, tax_id, email), unit_id in zip(EXISTING, unit_ids):
        customer = cm.Customer.objects.filter(tenant=tenant, display_name=name).first()
        if customer is None:
            block = (
                {"display_name": name, "kind": "company", "identity": {"tax_id": tax_id}}
                if kind == "company"
                else {
                    "display_name": name,
                    "kind": "person",
                    "identity": {"phone": phone, "date_of_birth": "1979-03-21"},
                }
            )
            account = customers_services.create_account(
                actor,
                {
                    "unit_id": str(unit_id),
                    "account_type": "commercial" if kind == "company" else "residential",
                    "status": "active",
                    "opened_at": "2026-03-01",
                    "contact": {"full_name": name, "email": email, "phone": phone},
                    "customer": block,
                },
            )
            link = cm.CustomerAccount.objects.get(account_id=account["id"])
            customer = link.customer
            credentials.create_credential(
                tenant.id,
                account=account["id"],
                email=email,
                password=PORTAL_PASSWORD,
                otp_channel=pm.CHANNEL_EMAIL,
            )
        acct = cm.CustomerAccount.objects.filter(tenant=tenant, customer=customer).select_related("account").first()
        made.append(
            {
                "walk": walk,
                "name": name,
                "customer_no": customer.customer_no,
                "customer_id": str(customer.id),
                "account_no": acct.account.account_no,
                "portal_email": email,
            }
        )
    return made


#: A SECOND utility, for the three "another utility cannot see it" walks. It
#: sells water only and its owner signs in with the walk's fixture password.
OTHER = {
    "name": "Oak Hollow Water",
    "subdomain": "oakhollow",
    "state": "Texas",
    "services": ["water"],
    "currency": "USD",
    "plan": "growth",
    "load_defaults": True,
    "owner": {
        "full_name": "Omar Haddad",
        "email": "omar@oakhollowwater.com",
        "password": PASSWORD,
        "phone": "+1 (281) 555-0299",
    },
}


def _other_utility() -> None:
    from apps.portal import settings_service
    from apps.tenancy import models as tm
    from apps.tenancy import services as tsvc
    from core import tenancy as core_tenancy
    from types import SimpleNamespace

    tenant = tm.Tenant.objects.filter(subdomain=OTHER["subdomain"]).first()
    if tenant is None:
        tsvc.provision_tenant({**OTHER, "owner": dict(OTHER["owner"])})
        tenant = tm.Tenant.objects.get(subdomain=OTHER["subdomain"])
    from apps.identity import models as im

    with core_tenancy.tenant_context(tenant.id):
        owner = im.User.objects.get(tenant=tenant, email__iexact=OTHER["owner"]["email"])
        actor = SimpleNamespace(id=owner.id, pk=owner.id, role="system_admin", user=owner)
        settings_service.save_settings(actor, tenant.id, {"is_live": True})


def main() -> int:
    cr158 = _load("cr158_seed_portal_upload", REPO / "10-scripts/cr158_seed_portal_upload.py")
    cr158.main()
    _other_utility()

    from django.db import transaction

    from apps.metering import models as mm
    from apps.rating import models as rm
    from core import tenancy as core_tenancy

    six = cr158._load("seed_six_service_one_time", REPO / "10-scripts/seed_six_service_one_time.py")
    tenant, actor = six.sjf.tenant_and_actor()
    with core_tenancy.tenant_context(tenant.id):
        with transaction.atomic():
            clerk = _clerk(tenant)
            plan = rm.RatePlan.objects.get(tenant=tenant, code="SCW-RES")
            for n, (address, labels, services) in enumerate(ON_FILE):
                _premises(tenant, actor, plan.id, address, labels, services, n)
            king = _premises(
                tenant, actor, plan.id, KINGFISHER, [f"Unit {i}" for i in range(1, 7)], ["water"], 20
            )
            units = list(
                mm.Unit.objects.filter(premises_id=king).order_by("label").values_list("id", flat=True)
            )
            linked = _existing(actor, tenant, units)
    out = {
        "tenant": tenant.subdomain,
        "clerk": {"email": CLERK_EMAIL, "password": PASSWORD, "id": str(clerk.id)},
        "portal_password": PORTAL_PASSWORD,
        "linked": linked,
    }
    print("CWPWALK world:")
    print(json.dumps(out, indent=2))
    (REPO / "08-qa/screens/portal-walk21-2026-10-02").mkdir(parents=True, exist_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
