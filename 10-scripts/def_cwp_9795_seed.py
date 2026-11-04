#!/usr/bin/env python3
"""def_cwp_9795_seed — the world for the DEF-CWP-9795 portal walk (2026-10-06).

Walk: `10-scripts/def_cwp_9795_walk.mjs` · photographs:
`08-qa/screens/def-cwp-9795-2026-10-06/`.

Reuses `cr158_seed_portal_upload.py` (Six Rivers Utility, portal live) and adds
TWO accounts with a portal login each, so the one page is seen both ways:

  * **Grace Fellowship of Cedar Ford** — exempt from ONE tax by certificate
    (CF-REL-2026-0412, City of Cedar Ford utility tax, to 12/31/2028), recorded
    through rating's own `record_exemption_certificate`, exactly as the move-in
    records it. Ruling (A) 2026-10-05: the blanket `tax_exempt` flag stays
    false — which is the case the portal read missed.
  * **Marcus Bell** — the OLD blanket exemption (`tax_exempt`, to 03/31/2027),
    which must read on the portal exactly as it did before the fix.

Idempotent.

    cd 06-backend && DATABASE_URL=postgres://…/<db> DJANGO_SETTINGS_MODULE=config.settings.local \\
        JOBS_EAGER=true python ../10-scripts/def_cwp_9795_seed.py
"""

from __future__ import annotations

import importlib.util
import os
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

PORTAL_PASSWORD = "Six-Rivers-Walk-2026"  # walk fixture credential — never prod
SERVICES = ["water", "sewer", "trash"]
PEOPLE = [
    # (address, name, kind, email, blanket?)
    ("12 Cedar Ford Road", "Grace Fellowship of Cedar Ford", "company", "office@gracefellowship.test", False),
    ("14 Cedar Ford Road", "Marcus Bell", "person", "marcus.bell@example.test", True),
]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def main() -> int:
    cr158 = _load("cr158_seed_portal_upload", REPO / "10-scripts/cr158_seed_portal_upload.py")
    cr158.main()
    six = cr158._load("seed_six_service_one_time", REPO / "10-scripts/seed_six_service_one_time.py")

    from django.db import transaction

    from apps.customers import models as cm
    from apps.customers import services as customers_services
    from apps.metering import services as metering_services
    from apps.portal import credentials
    from apps.portal import models as pm
    from apps.rating import models as rating_models
    from apps.rating import services as rating_services
    from core import tenancy as core_tenancy
    from tests.journey_cohort_fixtures import _premises_for, _unit_on

    tenant, actor = six.sjf.tenant_and_actor()
    with core_tenancy.tenant_context(tenant.id):
        with transaction.atomic():
            for address, name, kind, email, blanket in PEOPLE:
                customer = cm.Customer.objects.filter(tenant=tenant, display_name=name).first()
                if customer is None:
                    premises_id = _premises_for(tenant, actor, address, SERVICES)
                    unit_id = _unit_on(tenant, actor, premises_id, "Main", SERVICES)
                    plan = rating_models.RatePlan.objects.get(tenant=tenant, code="SCW-RES")
                    metering_services.assign_unit_plan(actor, unit_id, {"tariff_id": str(plan.id)})
                    block = (
                        {"display_name": name, "kind": "company", "identity": {"tax_id": "74-3051190"}}
                        if kind == "company"
                        else {
                            "display_name": name,
                            "kind": "person",
                            "identity": {"phone": "(281) 555-0102", "date_of_birth": "1979-03-21"},
                        }
                    )
                    account = customers_services.create_account(
                        actor,
                        {
                            "unit_id": str(unit_id),
                            "account_type": "commercial" if kind == "company" else "residential",
                            "status": "active",
                            "opened_at": "2026-03-01",
                            "contact": {"full_name": name, "email": email, "phone": "(281) 555-0190"},
                            "customer": block,
                        },
                    )
                    credentials.create_credential(
                        tenant.id,
                        account=account["id"],
                        email=email,
                        password=PORTAL_PASSWORD,
                        otp_channel=pm.CHANNEL_EMAIL,
                    )
                    row = cm.Account.objects.get(pk=account["id"])
                    if blanket:
                        row.tax_exempt = True
                        row.tax_exempt_ref = "TX-EX-88213"
                        row.tax_exempt_expires = date(2027, 3, 31)
                        row.save(update_fields=["tax_exempt", "tax_exempt_ref", "tax_exempt_expires"])
                    else:
                        jurisdiction, _ = rating_models.TaxJurisdiction.objects.get_or_create(
                            tenant=tenant, name="City of Cedar Ford"
                        )
                        tax = rating_models.Tax.objects.create(
                            tenant=tenant,
                            jurisdiction=jurisdiction,
                            name="City of Cedar Ford utility tax",
                            kind="percent",
                            rate="0.020000",
                        )
                        category = rating_services.create_exemption_category(
                            actor, tax.id, {"code": "RELIGIOUS", "name": "Religious organisation"}
                        )
                        rating_services.record_exemption_certificate(
                            actor,
                            category["id"],
                            {
                                "account_id": str(row.pk),
                                "certificate_ref": "CF-REL-2026-0412",
                                "issued_on": "2026-01-01",
                                "expires_on": "2028-12-31",
                            },
                        )
    print("DEF-CWP-9795 walk world (Six Rivers Utility, tenant sixrivers):")
    for address, name, _kind, email, blanket in PEOPLE:
        print(f"  {name:32} {email:32} {'blanket' if blanket else 'certificate'}  {address}")
    print(f"  portal password ..... {PORTAL_PASSWORD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
