#!/usr/bin/env python3
"""CR-167-BRC10 follow-up (lane PLAN-MONEY) — the probe utility `plansrv-rcp`
that CR-167 §7.1 measured `DEF-RAT-9335` on, rebuilt from nothing.

§7.1 names the recipe in prose and no script: *"provisioned through the real
signup service with water, sewer, trash and fire and filled by the product's
own sample data (49 accounts, two issued cycles)"*. This is that recipe, so the
next lane runs it instead of re-deriving it. Pattern copied from
`cr081_seed_sewer_utility.py` (the dispatcher is swapped for a recorder because
a developer database has no broker).

    DATABASE_URL=postgres://postgres@127.0.0.1:55433/<db> \\
    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    /tmp/venv_a5c/bin/python 10-scripts/cr167_money_world.py [subdomain]

Then `10-scripts/cr167_base_checks_pg.py plansrv-rcp` adds the four water base
codes and names `BASE-W1` on the water schedule (its own docstring states the
two probe shortcuts).
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

from django.core.management import call_command  # noqa: E402

from apps.tenancy import models as tenancy_models  # noqa: E402
from apps.tenancy import services as tenancy_services  # noqa: E402
from core import jobs as core_jobs  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

SUBDOMAIN = sys.argv[1] if len(sys.argv) > 1 else "plansrv-rcp"

PAYLOAD = {
    "name": "Plans probe utility",
    "subdomain": SUBDOMAIN,
    "owner": {
        "email": f"owner@{SUBDOMAIN}.test",
        "full_name": "Plans Probe Owner",
        "password": "S3cure!passw0rd",
    },
    "country": "US",
    "state": "TX",
    "timezone": "America/Chicago",
    "currency": "USD",
    "services": ["water", "sewer", "trash", "fire"],
    "load_defaults": True,
}


def provision() -> tenancy_models.Tenant:
    existing = tenancy_models.Tenant.objects.filter(subdomain=SUBDOMAIN).first()
    if existing is not None:
        print(f"tenant {SUBDOMAIN} already exists — reusing it")
        return existing
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


def main() -> int:
    provision()
    call_command("seed_demo", tenant=SUBDOMAIN)
    call_command("load_sample_data", tenant=SUBDOMAIN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
