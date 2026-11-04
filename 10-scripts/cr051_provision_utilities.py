#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: N whole utilities on ONE database, provisioned through the REAL
#            signup path, so CR-051 task 27 can fire their bill runs at once.
# Change:   CR-051 task 27 (PO 2026-08-31) — *"what if we get 10 utilities
#           firing billing at the same time, will it hamper live system
#           performance"*.
# Rules:    BR-TEN-010 (provisioning is atomic and idempotent on the subdomain)
#           · BR-TEN-012/013 (reference seed only through the owning module's
#           services) · CLAUDE.md rule 1 (every write inside tenant_context,
#           and the connection must be SUBJECT to RLS — DEF-2717)
# ───────────────────────────────────────────────────────
"""Provision N utilities and give each one a billable cycle.

WHY THIS EXISTS. `manage.py seed_demo` hardcodes ONE subdomain, `brazosbend`,
so there has never been a second utility in a developer database and task 27's
question — *ten utilities firing billing at the same time* — could not be asked
at all.

**EVERY TENANT IS CREATED THROUGH THE PATH A REAL CUSTOMER WALKS.**
`tenancy.services.provision_tenant` is what the S114 signup screen calls; this
passes it the same payload shape and nothing else, and then runs the
sample-plant job the signup enqueues. That gives each utility its OWN reference
data, its OWN plans and rate schedules, and its OWN premises, units, meters and
billing cycle — which is the half that decides whether a bill run can start.

⚠ **THE ACCOUNTS ARE WRITTEN DIRECTLY, AND IT IS SAID RATHER THAN HIDDEN.** The
sample plant's own Accounts block does not complete on a freshly provisioned
tenant (`DEF-2718`), so this writes an `accounts` row per unit and then clones
within the tenant to reach the wanted count. **These are real tenants with a
real estate and a synthetic customer base**, which for a CONTENTION measurement
is the right trade: the database sees the same statement mix against the same
tables under a different `app.tenant_id`, and that is the thing being measured.
**It is NOT a demo fixture and must never be used as one.**

⚠ **NOTHING IS CLONED ACROSS TENANTS, and that is a hard rule and not a
preference.** Every FK a unit or an account carries — its premises, its plan,
its cycle, its status — points at a row of ITS OWN tenant. Copying one tenant's
unit into another would create a cross-tenant foreign key, which is CLAUDE.md
hard rule 1 broken in the schema itself.

IT IS IDEMPOTENT. Provisioning is idempotent on the subdomain (BR-TEN-010) and
a replay tops each tenant up to the wanted account count rather than doubling
it.

USAGE
    DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=postgres://… \\
      python3 10-scripts/cr051_provision_utilities.py --count 10 --accounts 200
    python3 10-scripts/cr051_provision_utilities.py --list
    python3 10-scripts/cr051_provision_utilities.py --remove     # sweep them
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402

settings.DEBUG = False

from apps.customers import models as customer_models  # noqa: E402
from apps.metering import models as metering_models  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from apps.tenancy import services as tenancy_services  # noqa: E402
from core import jobs as core_jobs  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

import cr051_run_benchmark as bench  # noqa: E402

#: The subdomains this script owns. Prefixed so nothing else can be mistaken
#: for one, and so a database can be swept clean by the prefix alone.
PREFIX = "perf-utility-"


def _payload(index: int) -> dict:
    return {
        "name": f"Perf Utility {index}",
        "subdomain": f"{PREFIX}{index}",
        "owner": {
            "email": f"owner@{PREFIX}{index}.test",
            "full_name": f"Perf Owner {index}",
            "password": "S3cure!passw0rd",
        },
        "country": "US",
        "state": "TX",
        "timezone": "America/Chicago",
        "currency": "USD",
        "services": ["water", "sewer"],
        "load_defaults": True,
    }


def _billable_cycle(tenant):
    """The tenant's cycle with the most units in it, and those units."""
    from apps.metering import derivation

    cycle, unit_ids = None, []
    with core_tenancy.tenant_context(str(tenant.id)):
        for candidate in metering_models.Cycle.objects.all():
            found = derivation.units_in_cycle(candidate.id)
            if len(found) > len(unit_ids):
                cycle, unit_ids = candidate, found
    return cycle, unit_ids


def provision(index: int) -> tenancy_models.Tenant:
    """One utility, through the signup service. Idempotent on the subdomain."""
    subdomain = f"{PREFIX}{index}"
    existing = tenancy_models.Tenant.objects.filter(subdomain=subdomain).first()
    if existing is not None:
        return existing
    # ⚠ The dispatcher is swapped for a recorder: provisioning ENQUEUES the
    # sample-plant job and a developer database has no broker. The body is run
    # in-process below, which is what a dev container's JOBS_EAGER would do.
    previous = core_jobs._dispatcher  # noqa: SLF001
    core_jobs.set_job_dispatcher(lambda _record: None)
    try:
        result = tenancy_services.provision_tenant(_payload(index))
    finally:
        core_jobs.set_job_dispatcher(previous)
    tenant = tenancy_models.Tenant.objects.get(pk=result["id"])
    plant = result.get("sample_plant")
    if plant is not None:
        with core_tenancy.tenant_context(str(tenant.id)):
            from apps.tenancy import sample_data as tenancy_sample_data

            core_jobs.run_job(
                plant["job_id"], tenancy_sample_data.run_provisioning_plant
            )
    return tenant


def stock(tenant, accounts: int) -> tuple[object, int]:
    """Top this tenant's billable cycle up to `accounts`. Returns (cycle, held).

    Two steps, and the order matters: an `accounts` row on every unit the cycle
    already covers (which is what a real utility looks like), and only then the
    within-tenant clone that takes it past the unit count.
    """
    cycle, unit_ids = _billable_cycle(tenant)
    if cycle is None or not unit_ids:
        return None, 0
    with core_tenancy.tenant_context(str(tenant.id)):
        status = customer_models.AccountStatus.objects.filter(
            tenant_id=tenant.id, code="active"
        ).first()
        kind = customer_models.AccountType.objects.first()
        if status is None:
            sys.exit(
                f"{tenant.subdomain}: no 'active' account status — provisioning is incomplete"
            )
        held = set(
            str(one)
            for one in customer_models.Account.objects.filter(
                tenant_id=tenant.id, unit_id__in=unit_ids
            ).values_list("unit_id", flat=True)
        )
        made = 0
        for position, unit_id in enumerate(unit_ids, start=1):
            if str(unit_id) in held:
                continue
            customer_models.Account.objects.create(
                tenant_id=tenant.id,
                unit_id=unit_id,
                account_no=f"PF-{position:06d}",
                status=status,
                account_type=kind,
            )
            made += 1
        total = customer_models.Account.objects.filter(
            tenant_id=tenant.id, unit_id__in=unit_ids
        ).count()
        if total < accounts:
            templates = list(
                customer_models.Account.objects.filter(
                    tenant_id=tenant.id, unit_id__in=unit_ids
                ).order_by("account_no")[:8]
            )
            for index in range(total, accounts):
                bench.clone_account(templates[index % len(templates)], index)
            total = accounts
        return cycle, total


def remove() -> None:
    """Sweep every tenant this script made. Refuses if one has issued a bill —
    an issued invoice can never be deleted (hard rule 4)."""
    from apps.billing import models as billing_models

    for tenant in tenancy_models.Tenant.objects.filter(subdomain__startswith=PREFIX):
        with core_tenancy.tenant_context(str(tenant.id)):
            issued = billing_models.Invoice.objects.exclude(
                status=billing_models.INVOICE_DRAFT
            ).count()
        if issued:
            print(
                f"  REFUSING {tenant.subdomain}: {issued} issued invoice(s) — hard rule 4"
            )
            continue
        print(
            f"  {tenant.subdomain}: leaving the rows in place — removal is not automated"
        )
    print(
        "\nThese tenants are deliberately NOT deleted by this script: a tenant graph "
        "spans ~80 tables and a half-deleted one is worse than a labelled one. Drop the "
        "whole benchmark database instead, or delete by subdomain prefix by hand."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument(
        "--accounts", type=int, default=200, help="billable accounts per utility"
    )
    parser.add_argument(
        "--list", action="store_true", help="report what exists and stop"
    )
    parser.add_argument(
        "--remove", action="store_true", help="report how to sweep them"
    )
    args = parser.parse_args()

    from django.db import connection

    if connection.vendor != "postgresql":
        sys.exit(
            "tenant context is a Postgres GUC — this needs PostgreSQL (CLAUDE.md rule 1)"
        )
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
        )
        superuser, bypass = cursor.fetchone()
    if superuser or bypass:
        # DEF-2717 — with RLS bypassed a tenant reads another tenant's rows and
        # this script would happily stock the wrong utility.
        sys.exit(
            "REFUSING: this connection's role bypasses row-level security, so a "
            "tenant_context does not scope anything (DEF-2717, hard rule 1)."
        )

    if args.remove:
        remove()
        return 0

    if args.list:
        for tenant in tenancy_models.Tenant.objects.filter(
            subdomain__startswith=PREFIX
        ).order_by("subdomain"):
            cycle, unit_ids = _billable_cycle(tenant)
            with core_tenancy.tenant_context(str(tenant.id)):
                held = customer_models.Account.objects.filter(
                    unit_id__in=unit_ids
                ).count()
            print(
                f"  {tenant.subdomain:<20} cycle {getattr(cycle, 'code', '—'):<8} "
                f"{len(unit_ids):>6} units {held:>6} accounts"
            )
        return 0

    for index in range(1, args.count + 1):
        tenant = provision(index)
        cycle, held = stock(tenant, args.accounts)
        print(
            f"  {tenant.subdomain:<20} cycle {getattr(cycle, 'code', '—'):<8} "
            f"{held:>6} billable accounts"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
