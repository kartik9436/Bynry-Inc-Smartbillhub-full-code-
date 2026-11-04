#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2799 — the seeded utility configures NO per-size rate row and NO
#          version base charge, so the ruled R1–R7 chain refuses 47 of 47
#          accounts at R3 and the cutover cannot be measured past R3 on the
#          repo's own fixture.
# Rules:   BR-RAT-120 (the sizes a schedule serves are the SCHEDULE's) ·
#          BR-RAT-088 (the charge code owns the base) · DEF-277 (a BLANK base
#          means *this size is not served*) · CLAUDE.md hard rule 1 (tenant
#          scoping) · hard-won law 4 (a template change never reaches a host
#          that already exists)
# Tests:   06-backend/tests/test_def2799_seeded_size_axis.py — the seeder half.
#          This script is the SAME two facts applied to a tenant that already
#          exists, and it refuses on exactly the same grounds.
# Impacts: nothing customer-facing. Proved below: no live pricing read touches
#          `rate_size_rows`, and the base written is the figure the PLAN already
#          states, which `gather._base_charge_for` calls "a duplicate rather
#          than a disagreement" and passes through untouched.
# ───────────────────────────────────────────────────────
"""Give an ALREADY-SEEDED tenant the size axis and version base its schedules lack.

WHY THIS EXISTS AND IS NOT JUST A SEEDER CHANGE
-----------------------------------------------
Hard-won law 4, in its data form: **the seeder fix reaches a tenant seeded after
it and no other.** Every deployment that already carries Brazos Bend — the
development database, the demo host, this repo's own measurement clone — keeps
`rate_size_rows` at zero rows and `tariff_versions.base_charge` at NULL for
ever, so the ruled chain goes on refusing every bill at R3 there. Rate content
is append-only once a version is active (BR-RAT-037), so re-running the seeder
cannot repair it either: `create_rate_schedule` skips a schedule whose name
already exists.

WHAT IT WRITES, AND WHAT IT REFUSES TO WRITE
--------------------------------------------
Per in-force schedule version, exactly the two facts `DEF-2799` names:

  1. `rate_size_rows` — one row per RATIFIED size class of the version's own
     service, `minimum_bill` NULL ("this size IS served and has no floor", r10's
     em-dash). Read through `apps.rating.sample_data.sample_size_rows`, the SAME
     helper the two seeders call, so the repaired tenant and a freshly seeded
     one cannot state different ladders.
  2. `tariff_versions.base_charge` — the figure the PLAN that binds this tariff
     ALREADY states for that service, and nothing else.

**It REFUSES rather than choosing** where a single answer does not exist:

  · a tariff bound by two plans stating DIFFERENT bases — no one scalar is a
    duplicate of both, and writing either makes `gather._base_charge_for` refuse
    every bill on the other plan (OQ-238);
  · a tariff bound by NO plan — there is no stated figure to copy, and inventing
    one would price a schedule nobody has priced;
  · a version that ALREADY states a base different from the plan's — that is a
    live OQ-238 disagreement this script did not create and must not paper over.

⚠ **IT MOVES NO BILL, AND THAT IS CHECKED SOMEWHERE ELSE RATHER THAN CLAIMED
HERE** (hard-won law 1 — a comment claiming a guarantee is not the guarantee).
The check is `10-scripts/def2799_live_base_charges.py`, which prints the
per-service base charge `gather` resolves for every ready account of a prepared
run. It is run BEFORE and AFTER this script and the two outputs must be
byte-identical. On the seeded tenant they are water **$8.00** on the reference
account and **$390.00** across the 47 accounts of the July run.

    DJANGO_SETTINGS_MODULE=config.settings.local \
    DATABASE_URL=postgres://…/<db>?sslmode=disable \
    JOBS_EAGER=false \
    python3 10-scripts/def2799_apply_size_axis.py --tenant brazosbend [--dry-run]

⚠ **THE BASE HALF IS A WORKAROUND FOR `DEF-2823`.** `BR-RAT-088` retired
`tariff_versions.base_charge` and the S11 wizard has had no control for it since;
`resolution_catalogue.schedule_version_facts` nevertheless builds R3's per-size
base from that retired scalar. When that defect is fixed this script's second
half is deleted, not kept.
"""

from __future__ import annotations

import argparse
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

from django.db import connection, transaction  # noqa: E402

from apps.rating import models as rating_models  # noqa: E402
from apps.rating.sample_data import sample_size_rows  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402


def _plan_base_by_tariff() -> dict[str, set[Decimal]]:
    """Every base the PLANS state for the service each tariff prices.

    A set, because the refusal this script owes the operator is *"two plans
    disagree"* and a dict would silently keep the last one seen.
    """
    bases: dict[str, set[Decimal]] = {}
    for row in rating_models.PlanRateSchedule.objects.select_related("rate_plan", "service"):
        stated = (
            rating_models.PlanService.objects.filter(
                rate_plan_id=row.rate_plan_id, service_id=row.service_id
            )
            .values_list("base_charge", flat=True)
            .first()
        )
        if stated is None:
            continue
        bases.setdefault(str(row.tariff_id), set()).add(Decimal(str(stated)))
    return bases


def apply(tenant_id, *, dry_run: bool) -> dict:
    written_rows = 0
    versions_based = 0
    notes: list[str] = []
    plan_bases = _plan_base_by_tariff()

    versions = rating_models.TariffVersion.objects.filter(
        tenant_id=tenant_id
    ).select_related("tariff", "tariff__service")
    for version in versions:
        service = version.tariff.service.code
        # ── 1 · the size axis (BR-RAT-120) ───────────────────────────────
        for row in sample_size_rows(service):
            _obj, created = rating_models.RateSizeRow.objects.get_or_create(
                tenant_id=tenant_id,
                tariff_version=version,
                size_class=row["size_class"],
                defaults={"minimum_bill": None, "currency": version.currency or "USD"},
            )
            written_rows += int(created)

        # ── 2 · the version base (the DEF-2823 workaround) ───────────────
        stated = plan_bases.get(str(version.tariff_id))
        if not stated:
            notes.append(
                f"{version.tariff.name} ({service}) — NO plan states a base for this "
                "service, so there is no figure to copy and none is invented. The chain "
                "will still refuse this schedule at R3."
            )
            continue
        if len(stated) > 1:
            notes.append(
                f"REFUSED {version.tariff.name} ({service}) — two plans state DIFFERENT "
                f"bases ({', '.join(sorted(str(v) for v in stated))}). One scalar cannot "
                "be a duplicate of both and writing either would make "
                "`gather._base_charge_for` refuse every bill on the other plan (OQ-238)."
            )
            continue
        want = next(iter(stated))
        held = None if version.base_charge is None else Decimal(str(version.base_charge))
        if held is not None and held != want:
            notes.append(
                f"REFUSED {version.tariff.name} ({service}) — the version already states "
                f"{held} and the plan states {want}. That is a live OQ-238 disagreement "
                "this script did not create and must not paper over."
            )
            continue
        if held is None:
            version.base_charge = want
            version.save(update_fields=["base_charge"])
            versions_based += 1

    if dry_run:
        notes.append("DRY RUN — the transaction is rolled back; nothing was kept.")
    return {"size_rows": written_rows, "versions_based": versions_based, "notes": notes}


def main() -> int:
    parser = argparse.ArgumentParser(description="DEF-2799 — size axis + version base")
    parser.add_argument("--tenant", required=True, help="tenant subdomain")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if connection.vendor != "postgresql":
        raise SystemExit(
            "REFUSING: this is not PostgreSQL, so RLS and FORCE ROW LEVEL SECURITY do "
            "not exist and nothing written here would be written under tenant separation."
        )

    tenant = tenancy_models.Tenant.objects.filter(subdomain=args.tenant).first()
    if tenant is None:
        raise SystemExit(f"no tenant with subdomain {args.tenant!r}")

    class _Done(Exception):
        def __init__(self, result):
            super().__init__("done")
            self.result = result

    try:
        with transaction.atomic():
            with core_tenancy.tenant_context(tenant.id):
                result = apply(tenant.id, dry_run=args.dry_run)
            if args.dry_run:
                raise _Done(result)
    except _Done as done:
        result = done.result

    print(f"tenant {tenant.name!r} ({tenant.subdomain})")
    print(f"  rate_size_rows written ..... {result['size_rows']}")
    print(f"  versions given a base ...... {result['versions_based']}")
    for note in result["notes"]:
        print(f"  · {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2799 · DEF-2823 · CR-052 task 20
# generated: 2026-08-31 by the DEF-2799/DEF-2798 lane (claude)
# gates: golden-verify 33 PASS / 0 FAIL before and after — no ❄️ B4/B5 figure is
#        read, asserted or moved here; this script computes no money.
# exceptions: (1) it writes `tariff_versions.base_charge`, a column BR-RAT-088
#        RETIRED, and does so ONLY as the stated workaround for DEF-2823;
#        (2) it copies a figure and never composes one — every value written is
#        already stored on the plan that binds the tariff.
# ──────────────────────────────────────────────────────────
