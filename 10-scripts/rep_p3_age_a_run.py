#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 Phase 3 · `P3.5`/`P3.6` — the half of journey
#          `J-REP-02` step 7 that a browser cannot perform.
# Rules:   BR-REP-018 (generated files retained 3 days) · CLAUDE.md hard-won
#          law 7's fifth shape (a check reporting zero over a scope it
#          silently excludes)
# ───────────────────────────────────────────────────────
"""Age one report run past the retention window, and sweep its file.

⚠ **A BROWSER CANNOT MOVE A CLOCK, AND `P3.5` IS A BEHAVIOUR RATHER THAN A
CONSTANT.** The walkthrough's step 7 asks for a row whose FILE IS GONE and
whose download control is therefore absent. On a freshly seeded tenant every
job was created minutes ago, so that row does not exist — and a walkthrough
that quietly skipped the step would report a clean walk over the one thing
this phase exists to get right.

So this script MAKES the state, prints exactly what it changed, and
`rep_p3_history_walkthrough.mjs` then photographs it. Run it between them.

⚠ **IT WRITES. USE A PRIVATE CLONE** — `10-scripts/proof-db.sh clone repp3` —
never a database another lane is reading. It moves `jobs.created_at` and the
export's `job_artifacts.created_at` backwards and runs this utility's export
sweep (`export_store.sweep_tenant`), which DELETES that utility's expired export
objects from the environment's S3 bucket (since 2026-10-02 exports live there).

    DATABASE_URL=... PYTHONPATH=06-backend python3 10-scripts/rep_p3_age_a_run.py

⚠ **IT AGES THE ROW *AND* SWEEPS THE FILE, WHICH ARE TWO DIFFERENT HALVES OF
`expired` AND ARE PROVED SEPARATELY ELSEWHERE.** The unit case
`test_a_run_older_than_the_window_expires_even_with_its_file_present` ages the
row and LEAVES the file, so it fails if the timestamp rule is removed. Here
both are done, because the screenshot the Product Owner reads should show the
state a real utility reaches: an old run whose file the sweep has taken.
"""
from __future__ import annotations

import os
import sys
from datetime import timedelta

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from django.utils import timezone  # noqa: E402

from apps.tenancy import exports as export_kernel, models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

subdomain = sys.argv[1] if len(sys.argv) > 1 else "brazosbend"
tenant = tenancy_models.Tenant.objects.get(subdomain=subdomain)
core_tenancy.set_current_tenant(tenant.id)

days = export_kernel.artifact_retention_days(tenant.id)  # this utility's own window
runs = list(
    tenancy_models.Job.objects.filter(
        tenant_id=tenant.id, kind=export_kernel.LIST_EXPORT_JOB, status="succeeded"
    ).order_by("created_at")
)
print(f"tenant {subdomain}: {len(runs)} succeeded export run(s); retention is {days} days")
if not runs:
    raise SystemExit("nothing to age — run an export first (the walkthrough's step 2 does)")

target = runs[0]
was = target.created_at
aged = timezone.now() - timedelta(days=days + 1)
moved = tenancy_models.Job.objects.filter(id=target.id).update(created_at=aged)
print(f"aged 1 run: {was.isoformat()} -> {aged.isoformat()} ({moved} row updated)")

# Since 2026-10-02 the file is an S3 object recorded in `job_artifacts`
# (DEF-MET-4954); age its row too, then run the daily sweep for THIS utility.
from apps.tenancy import export_store  # noqa: E402
from apps.tenancy.export_models import JobArtifact  # noqa: E402

JobArtifact.objects.filter(job_id=target.id).update(created_at=aged)
# DEF-TEN-9146: the sweep names the utility, so it never touches another's files.
result = export_store.sweep_tenant(tenant.id)
status = JobArtifact.objects.filter(job_id=target.id).values_list("status", flat=True).first()
print(f"export sweep: {result.deleted} deleted, {result.orphans} orphan(s), {result.refused} refused; "
      f"this run's file is now: {status}")
print("\nnow walk step 7 — /reports/history?f.status=expired must show this run with NO download control")
