#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:   CR-081 — sewer is a percentage of the water VOLUME, priced on a
#           sewer rate schedule of its own. PO 2026-09-07: *"we ahve to apply
#           this method - Way 2 … a percentage of the gallons"*; six ❄️ frozen
#           figures re-signed 2026-09-08: *"C — factor 90%, rate $5.00 →
#           $36.00, which is what a real sewer customer actually pays"*.
# Rules:    BR-RAT-1015 · BR-TEN-010 (provisioning is atomic and idempotent on
#           the subdomain) · CLAUDE.md hard rule 1 (every write inside a tenant
#           context) · hard-won law 6 (diff the RUNNING app)
# ───────────────────────────────────────────────────────
"""PROVISION A WATER + SEWER UTILITY, SEED IT AND BILL IT — through the REAL
signup service and the REAL bill run, so a browser has a sewer line to read.

    DATABASE_URL=postgres://... python3.12 10-scripts/cr081_seed_sewer_utility.py

⚠ **WATER AND SEWER, NEVER SEWER ALONE.** `core.sample_fixture._SEWER_NEEDS_WATER`
refuses a sewer service point on a tenant that sells no water, and it is right
to: sewer's quantity is borrowed from the water meter, so a sewer-only tenant
has nothing to take 90% of. The refusal is the product working, not a limit of
this script.

It prints, at the end, the arithmetic a person can check against the screen: the
reference unit's metered water, the 90% that becomes sewer, and the money.
"""
from __future__ import annotations

import os
import sys
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

SUBDOMAIN = os.environ.get("TENANT", "cr081-sewer")

PAYLOAD = {
    "name": "CR-081 Sewer Utility",
    "subdomain": SUBDOMAIN,
    "owner": {
        "email": f"owner@{SUBDOMAIN}.test",
        "full_name": "CR-081 Owner",
        "password": "S3cure!passw0rd",
    },
    "country": "US",
    "state": "TX",
    "timezone": "America/Chicago",
    "currency": "USD",
    "services": ["water", "sewer", "trash"],
    "load_defaults": True,
}


def provision() -> tenancy_models.Tenant:
    """One utility, through the signup service. Idempotent on the subdomain."""
    existing = tenancy_models.Tenant.objects.filter(subdomain=SUBDOMAIN).first()
    if existing is not None:
        print(f"tenant {SUBDOMAIN} already exists — reusing it")
        return existing
    # The dispatcher is swapped for a recorder: provisioning ENQUEUES the sample
    # plant and a developer database has no broker. `cr080_seed_thermal_utility`
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
    """The arithmetic, printed so a person can check it against the screen.

    ⚠ **IT READS THE STORED TARIFF, NOT THE FIXTURE CONSTANTS.** The point of
    the exercise is that the ruling reached the DATABASE; printing the fixture's
    own 90 and $5.0000 back would prove only that this file can read itself.
    """
    from apps.billing import models as billing_models
    from apps.rating import models as rating_models

    with core_tenancy.tenant_context(str(tenant.id)):
        version = (
            rating_models.TariffVersion.objects.filter(
                tenant_id=tenant.id, model="percent_of_service"
            )
            .select_related("basis_service", "tariff__service")
            .first()
        )
        if version is None:
            print("\n⚠ NO percent_of_service version on this tenant — nothing to read")
            return
        tiers = list(
            rating_models.RateTier.objects.filter(
                tenant_id=tenant.id, tariff_version=version
            ).values_list("from_qty", "to_qty", "unit_price")
        )
        sewer_lines = list(
            billing_models.InvoiceLine.objects.filter(
                tenant_id=tenant.id, service__code="sewer", kind="usage"
                # `unit`, not `uom` — `invoice_lines` names the column `unit`
                # while `tariff_versions` names its own `uom`. The first draft
                # of this report used `uom` for both and died AFTER the seed and
                # the bill run had finished, which is the cheap version of this
                # mistake; the same slip inside the bill run would not have been.
            ).values_list("description", "quantity", "unit", "unit_price", "amount")[:6]
        )
        invoice_count = billing_models.Invoice.objects.filter(tenant_id=tenant.id).count()

    print("\n── THE STORED SEWER TARIFF ──────────────────────────────────")
    print(f"service .................. {version.tariff.service.code}")
    print(f"model .................... {version.model}")
    print(f"billed unit .............. {version.uom}")
    print(f"basis service ............ {version.basis_service.code if version.basis_service else None}")
    print(f"return-to-sewer factor ... {version.percent}%")
    for lo, hi, price in tiers:
        print(f"rate ..................... {lo} → {hi if hi is not None else '∞'} @ ${price}")
    if not tiers:
        print("rate ..................... NONE — the migration did not reach this row")

    print(f"\n── SEWER LINES ON REAL INVOICES ({invoice_count} invoices) ──────────")
    if not sewer_lines:
        print("  (none — the bill run produced no sewer usage line)")
    for description, quantity, uom, unit_price, amount in sewer_lines:
        print(f"  {description} · {quantity} {uom} @ ${unit_price} · ${amount}")
    print(
        f"\nNow: BASE=http://127.0.0.1:8080 TENANT={SUBDOMAIN} "
        "node 10-scripts/cr081_sewer_walkthrough.mjs"
    )


def main() -> int:
    tenant = provision()
    print("seeding reference data …")
    call_command("seed_demo", tenant=SUBDOMAIN)
    print("loading sample data …")
    call_command("load_sample_data", tenant=SUBDOMAIN)
    report(tenant)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
