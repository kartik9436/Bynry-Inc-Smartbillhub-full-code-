"""Seed ONE approved move-in on a proof database, through the product's own door.

Companion to `10-scripts/br_cus_1090_move_in_number_walkthrough.mjs`
(`BR-CUS-1090`, `CR-133-BRC07`).

WHY A SEED SCRIPT AND NOT A BACK-FILL
-------------------------------------
`customers/0063` §1 refuses to number the `move_in_jobs` rows that already exist:
allocating now would spend a tenant's counter on jobs nobody was ever told a
number for. So a database seeded before this change holds an approved move-in
with **no** reference, which is a real state the screen states in words — and it
is NOT the state the walkthrough exists to check.

This raises a **new** job the way a clerk does, so the walk exercises the path
the ruling is about rather than a row somebody patched.

⚠ **IT GOES THROUGH `move_in_jobs.raise_for_request`, NOT AN `objects.create`.**
A seed that wrote the row itself would allocate its own number and prove nothing
about the door — which is the *check that cannot fail* shape CLAUDE.md law 7
names. If the real door stops allocating, this script stops producing a number
and the walk goes red, which is the whole point.

⚠ **IT IS IDEMPOTENT AND SAYS SO.** `uq_move_in_jobs_tenant_request` means one
request raises one job; a second run reports the refusal by name and changes
nothing.

RUN IT
------
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL="postgres://…/sbh_clone_<label>?sslmode=disable" \\
      python ../10-scripts/br_cus_1090_seed_an_approved_move_in.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from django.db import transaction  # noqa: E402

from apps.tenancy.models import Tenant  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

SUBDOMAIN = os.environ.get("SEED_TENANT", "brazosbend")


def main() -> int:
    tenant = Tenant.objects.filter(subdomain=SUBDOMAIN).first()
    if tenant is None:  # pragma: no cover
        print(f"no `{SUBDOMAIN}` tenant in this database")
        return 2

    with core_tenancy.tenant_context(tenant.id):
        from apps.customers import models as cmodels, move_in_jobs

        # The request this job is raised for. An APPROVED move-in that already
        # has a job is the ordinary seeded state; this script numbers a job
        # raised now, so it wants a request with no job of its own.
        taken = set(
            move_in_jobs.MoveInJob.objects.values_list("request_id", flat=True)
        )
        request = (
            cmodels.ServiceRequest.objects.exclude(id__in=taken)
            .order_by("request_no")
            .first()
        )
        if request is None:  # pragma: no cover
            print("every request on this tenant already has a move-in job")
            return 2

        with transaction.atomic():
            result = move_in_jobs.raise_for_request(None, request)

        if result.get("code") == move_in_jobs.JOB_ALREADY_RAISED:
            print(f"already raised for {request.request_no}: {result['move_no']}")
            return 0

        print(
            f"raised a move-in job for {request.request_no} "
            f"({request.applicant_name}) → {result['move_no']}"
        )
        if not result.get("move_no"):
            print(
                "  ⚠ NO NUMBER. This tenant has no `move_in` series row — the "
                "reason is SERVED beside the row rather than faked, and the "
                "repair door is `manage.py seed_demo --tenant <subdomain>`."
            )
        return 0


if __name__ == "__main__":
    sys.exit(main())
