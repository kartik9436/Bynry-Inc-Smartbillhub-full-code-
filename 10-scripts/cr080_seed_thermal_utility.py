#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:   CR-080 — thermal/heat is billed on connected tonnage, not on a
#           meter. PO 2026-09-07: *"connected tonnage - it is capacity not
#           metering; i will ahve 100 tonne or 200 tonne etc"*.
# Rules:    BR-TEN-010 (provisioning is atomic and idempotent on the subdomain)
#           · CLAUDE.md rule 1 (every write inside a tenant context)
#           · CLAUDE.md hard-won law 6 (diff the RUNNING app) — this script
#           exists to produce the tenant that walkthrough then clicks through
# ───────────────────────────────────────────────────────
"""PROVISION A WATER + THERMAL UTILITY, SEED IT, AND BILL IT — through the
REAL signup service and the REAL bill run, so a browser has something to read.

    DATABASE_URL=postgres://... python3.12 10-scripts/cr080_seed_thermal_utility.py

⚠ **WATER AND THERMAL, NOT THERMAL ALONE, AND THE CHOICE IS DELIBERATE.** A
capacity service needs no metered backbone, so a thermal-only tenant is a
lawful shape and does bill. But the point of the walkthrough is that a **thermal
line stands beside familiar money on one document** — if it renders wrongly next
to a water line a person recognises, that is visible; on a page with nothing but
thermal on it, a blank quantity looks like the page.

⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** A mid-run reseed looks
exactly like a broken screen.

It prints, at the end, the arithmetic a person can check by hand: how many units
are connected at each tonnage, what the estate totals, and what the seeded
`$12.5000` per connected ton makes of it.
"""
from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402

settings.DEBUG = False

from django.core.management import call_command  # noqa: E402

from apps.tenancy import models as tenancy_models  # noqa: E402
from apps.tenancy import services as tenancy_services  # noqa: E402
from core import jobs as core_jobs  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

SUBDOMAIN = os.environ.get("TENANT", "cr080-thermal")

PAYLOAD = {
    "name": "CR-080 Thermal Utility",
    "subdomain": SUBDOMAIN,
    "owner": {
        "email": f"owner@{SUBDOMAIN}.test",
        "full_name": "CR-080 Owner",
        "password": "S3cure!passw0rd",
    },
    "country": "US",
    "state": "TX",
    "timezone": "America/Chicago",
    "currency": "USD",
    "services": ["water", "sewer", "thermal_heat"],
    "load_defaults": True,
}


def provision() -> tenancy_models.Tenant:
    """One utility, through the signup service. Idempotent on the subdomain."""
    existing = tenancy_models.Tenant.objects.filter(subdomain=SUBDOMAIN).first()
    if existing is not None:
        print(f"tenant {SUBDOMAIN} already exists — reusing it")
        return existing
    # The dispatcher is swapped for a recorder: provisioning ENQUEUES the sample
    # plant and a developer database has no broker. `cr051_provision_utilities`
    # does exactly this and for exactly this reason.
    previous = core_jobs._dispatcher  # noqa: SLF001
    core_jobs.set_job_dispatcher(lambda _record: None)
    try:
        result = tenancy_services.provision_tenant(PAYLOAD)
    finally:
        core_jobs.set_job_dispatcher(previous)
    tenant = tenancy_models.Tenant.objects.get(pk=result["id"])
    plant = result.get("sample_plant")
    if plant is not None:
        with core_tenancy.tenant_context(str(tenant.id)):
            from apps.tenancy import sample_data as tenancy_sample_data

            core_jobs.run_job(plant["job_id"], tenancy_sample_data.run_provisioning_plant)
    print(f"provisioned {SUBDOMAIN}")
    return tenant


def report(tenant) -> None:
    """The arithmetic, printed so a person can check it against the screen."""
    from apps.work import connection_models as work_tables
    from apps.metering import models as metering_models
    from apps.tenancy import service_size_classes as ssc
    from core import sample_fixture as fixture

    with core_tenancy.tenant_context(str(tenant.id)):
        rows = list(
            work_tables.ServiceCharacteristic.objects.filter(
                tenant_id=tenant.id, service__code="thermal_heat"
            ).values_list("key", "value", "unit_of_measure")
        )
        points = metering_models.ServicePoint.objects.filter(
            tenant_id=tenant.id, service__code="thermal_heat", deleted_at__isnull=True
        ).count()
    print(f"\nthermal service points ........ {points}")
    print(f"thermal characteristics ...... {len(rows)}")
    tally: dict[str, int] = {}
    total = Decimal("0")
    for _key, value, uom in rows:
        tally[f"{value} {uom}"] = tally.get(f"{value} {uom}", 0) + 1
        total += Decimal(str(value))
    for label, count in sorted(tally.items(), key=lambda kv: Decimal(kv[0].split()[0])):
        print(f"  {count:>3} unit(s) at {label}")
    rate = Decimal(fixture.CAPACITY_UNIT_PRICES["thermal_heat"])
    print(f"\nconnected total .............. {total} ton")
    print(f"seeded rate .................. ${rate} per ton per month")
    print(f"estate, per month ............ ${(total * rate).quantize(Decimal('0.01'))}")
    print(
        "the ratified ladder .......... "
        + ", ".join(
            f"{code}={ssc.capacity_of('thermal_heat', code)}"
            for code, _name in ssc.size_classes_for_service("thermal_heat")
        )
    )


def main() -> int:
    tenant = provision()
    print("seeding reference data …")
    call_command("seed_demo", tenant=SUBDOMAIN)
    print("loading sample data …")
    call_command("load_sample_data", tenant=SUBDOMAIN)
    report(tenant)
    print(
        f"\nNow: BASE=http://127.0.0.1:8080 TENANT={SUBDOMAIN} "
        "node 10-scripts/cr080_thermal_walkthrough.mjs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
