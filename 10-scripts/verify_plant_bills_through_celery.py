#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: BE-07 jobs framework — the WORKER half, asked about BILLS
# Defect:   DEF-3222 (the sample plant's bill count has only ever been measured
#           with JOBS_EAGER=True, i.e. inline in the caller's own process) ·
#           DEF-320 (four job kinds enqueued and production dispatched none) ·
#           DEF-3224 (which services reach a bill, not merely how many)
# Rules:    B3 (a worker sets tenant context EXPLICITLY, never ambiently) ·
#           BR-TEN-063 (the plant's failure never rolls back a tenant) ·
#           CLAUDE.md law 1 (a comment claiming a guarantee is not the
#           guarantee) · law 14 (prove it on PostgreSQL, not on the suite)
# Tests:    tests/test_cr017_celery_transport.py (the transport, not the plant)
# Impacts:  apps/tenancy/tasks.py · apps/tenancy/services.dispatch_job
# ───────────────────────────────────────────────────────
"""**DOES A TENANT PROVISIONED THROUGH A REAL CELERY WORKER GET THE SAME BILLS?**

**RUN 2026-09-02 AND THE ANSWER IS YES, IDENTICALLY.** Three processes on one
box — PostgreSQL 16.13, a real `redis-server`, and a real `celery -A
config.celery worker -Q celery,billing` — with `JOBS_EAGER=False`, one tenant
selling **electric + water + sewer** provisioned through
`apps.tenancy.services.provision_tenant`:

    job tenancy.sample_data_plant: succeeded
    premises            70
    accounts            70
    ISSUED INVOICES     95
    services on bills   ['sewer', 'water']
    sold but absent     ['electric']
    blocks              17, failed 0

**The inline run of the same shape produces the same 70 / 70 / 95 / 0-of-17**
(`tests/test_service_billing_coverage.py`, `svc-elec-water-sewer`). So the
worker path and the inline path agree on every figure, and `DEF-3224`'s missing
electric reproduces through the worker too — it is a fixture fact, not a
transport one. **There is no divergence to chase**, which is worth knowing
because it was an open possibility until this ran.

⚠ **THAT IS ONE RUN OF ONE SHAPE, AND IT IS A MEASUREMENT, NOT A GUARANTEE
(CLAUDE.md law 1).** It says the transport does not change the outcome for this
signup shape on this build. It does not prove a worker that is DOWN, a queue
with no consumer, or a broker that drops a message — those are `DEF-320`'s
territory and `verify_celery_transport.py`'s.

WHY THIS EXISTS, AND WHY THE TWO SCRIPTS BESIDE IT DO NOT ANSWER IT.
`verify_celery_transport.py` proves a worker CONSUMES the queue — it enqueues
four kinds and requires each to leave `queued`, and the sample plant reaches
`succeeded` with progress 10/10. `verify_billing_queue_split.py` proves the
billing queue has its own consumer. **Neither counts a single invoice.** A plant
job that finishes is not the same statement as a plant that BILLS: `BR-TEN-063`
makes a partly-seeded plant a SOFT failure, so a run in which every billing
block collapsed still ends `succeeded` with a full progress count.

**AND EVERY BILL FIGURE IN THIS REPO WAS MEASURED THE OTHER WAY.**
`tests/test_service_billing_coverage.py` — the file that owns the "does this
signup shape bill" question — sets `JOBS_EAGER = True` in each case, which runs
the plant INLINE, inside the caller's own process and inside the caller's own
tenant context. **Production runs `JOBS_EAGER=False`** (`config/settings/
production.py`), where the plant is a message, a broker and a separate process
that must re-enter the tenant itself. The two paths have never been compared on
their OUTPUT, only on their status.

WHAT COULD DIFFER, and it is not hypothetical:
  * **tenant context.** `run_job` must load the record BEFORE it can read the
    tenant off it, and `jobs` carries RLS FORCE, so a worker with no
    `app.tenant_id` reads zero rows. `apps/tenancy/tasks.py` sends `tenant_id`
    beside `job_id` for exactly this reason. Inline dispatch never exercises it,
    because the caller is already in context.
  * **the transaction boundary.** Inline, the plant runs inside the request's
    transaction; through a worker it runs in its own, after the tenant row has
    committed. Law 14's aborted-transaction trap lives on that seam and the
    default suite (in-memory SQLite) cannot show it.
  * **the queue.** Billing has had its own queue since CR-051 task 29, so "a
    worker is alive" and "MY job will run" are different sentences.

HOW TO RUN IT — THREE PROCESSES, and it needs all three::

    redis-server --daemonize yes --port 6379 --save "" --appendonly no
    createdb sbh_celery_proof
    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/sbh_celery_proof" \\
    .venv/bin/python manage.py migrate --noinput

    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL="postgres://…/sbh_celery_proof" \\
    .venv/bin/python 10-scripts/verify_plant_bills_through_celery.py

It starts the worker itself, provisions ONE tenant with `JOBS_EAGER=False`,
waits for the plant job to reach a terminal state, and then COUNTS: issued
invoices, and the service codes that reached an invoice line. It exits non-zero
when the plant produces no bills, so "the worker ran and the product billed
nothing" is a failure and not a silent pass.

⚠ **IT PROVES ONE SHAPE, NOT THE SCOREBOARD.** The comparison figure is whatever
`tests/test_service_billing_coverage.py` records for the same signup shape run
inline. Print both and read them side by side; this script deliberately does not
import that file's `RECORD`, because a script that carries its own copy of the
number it is checking is the fifteenth copy (G47's own reasoning).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ["JOBS_EAGER"] = "false"

import django

django.setup()

from apps.billing import models as billing_models
from apps.customers import models as customers_models
from apps.metering import models as metering_models
from apps.tenancy import models as tenancy_models
from apps.tenancy import services as tenancy_services
from core import tenancy as core_tenancy
from django.conf import settings

TIMEOUT_S = 900
POLL_S = 3
SERVICES = ["electric", "water", "sewer"]  # the PO's own shape, 2026-09-02


def start_worker(log_path: Path) -> subprocess.Popen:
    """A worker on BOTH queues. `-Q celery,billing` and not a bare worker:
    since CR-051 task 29 the default worker no longer drains billing, and a
    proof that silently skipped the billing queue would be measuring the very
    gap it exists to rule out."""
    env = dict(os.environ)
    env["JOBS_EAGER"] = "false"
    env["PYTHONUNBUFFERED"] = "1"
    log = log_path.open("wb")
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "config.celery",
            "worker",
            "-Q",
            "celery,billing",
            "--loglevel",
            "info",
            "--concurrency",
            "2",
            "-n",
            f"plantproof-{uuid.uuid4().hex[:8]}@%h",
        ],
        cwd=str(BACKEND),
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )


def wait_for_terminal(job_id, tenant_id) -> str:
    deadline = time.time() + TIMEOUT_S
    last = "queued"
    while time.time() < deadline:
        with core_tenancy.tenant_context(tenant_id):
            row = tenancy_models.Job.objects.filter(id=job_id).first()
        last = row.status if row is not None else "MISSING"
        if last in ("succeeded", "failed"):
            return last
        time.sleep(POLL_S)
    return last


def main() -> int:
    assert settings.JOBS_EAGER is False, (
        "JOBS_EAGER must be FALSE — with it on, the plant runs inline and this "
        "script measures the path it exists to compare against"
    )
    print(f"database: {settings.DATABASES['default']['NAME']}")
    print(f"JOBS_EAGER={settings.JOBS_EAGER}  (production dispatch)")

    log_path = Path("/tmp/celery-plant-proof.log")
    worker = start_worker(log_path)
    print(f"worker pid {worker.pid}; log {log_path}")
    time.sleep(10)
    if worker.poll() is not None:
        print("WORKER DIED ON STARTUP:")
        print(log_path.read_text()[-3000:])
        return 2

    try:
        sub = f"celeryproof{uuid.uuid4().hex[:6]}"
        payload = {
            "subdomain": sub,
            "name": f"Celery plant proof {sub}",
            "services": list(SERVICES),
            "owner": {
                "full_name": "Dana Whitfield",
                "email": f"dana@{sub}.example.invalid",
                "password": "S3cure!passw0rd",
                "phone": None,
            },
        }
        result = tenancy_services.provision_tenant(payload)
        tenant_id = result.get("tenant_id") or result.get("id")
        print(f"provisioned {sub}: created={result.get('created')} tenant={tenant_id}")

        with core_tenancy.tenant_context(tenant_id):
            jobs = list(tenancy_models.Job.objects.all().values("id", "kind", "status"))
        print(f"jobs enqueued: {jobs}")
        if not jobs:
            print("FAIL: provisioning enqueued NO job — nothing for a worker to run")
            return 1

        for job in jobs:
            status = wait_for_terminal(job["id"], tenant_id)
            print(f"  job {job['kind']}: {status}")
            if status == "queued":
                print(
                    "FAIL: the record never left `queued` — nothing consumed the queue"
                )
                return 1

        with core_tenancy.tenant_context(tenant_id):
            issued = billing_models.Invoice.objects.filter(
                tenant_id=tenant_id, status="issued"
            ).count()
            prem = metering_models.Premises.objects.filter(tenant_id=tenant_id).count()
            accts = customers_models.Account.objects.filter(tenant_id=tenant_id).count()
            on_bills = sorted(
                str(c)
                for c in billing_models.InvoiceLine.objects.filter(
                    tenant_id=tenant_id, invoice__status="issued"
                )
                .values_list("service__code", flat=True)
                .distinct()
                if c
            )
            blocks = []
            for row in tenancy_models.SampleDataRun.objects.filter(tenant_id=tenant_id):
                for b in row.blocks or []:
                    blocks.append(dict(b, module=b.get("module") or row.module))
        failed = [b for b in blocks if b.get("outcome") != "seeded"]

        print("\n── THROUGH A REAL CELERY WORKER ─────────────────────────────")
        print(f"  signup shape        {'+'.join(SERVICES)}")
        print(f"  premises            {prem}")
        print(f"  accounts            {accts}")
        print(f"  ISSUED INVOICES     {issued}")
        print(f"  services on bills   {on_bills}")
        print(f"  sold but absent     {sorted(set(SERVICES) - set(on_bills))}")
        print(f"  blocks              {len(blocks)}, failed {len(failed)}")
        for b in failed:
            print(
                f"    FAILED {b.get('module')}/{b.get('block')}: {str(b.get('detail'))[:240]}"
            )

        if issued == 0:
            print("\nFAIL: the worker ran the plant and the product billed NOTHING.")
            return 1
        print("\nPASS: a plant dispatched through Celery produced bills.")
        print("Compare `ISSUED INVOICES` against the inline figure that")
        print("tests/test_service_billing_coverage.py records for the same shape.")
        return 0
    finally:
        worker.terminate()
        try:
            worker.wait(timeout=20)
        except subprocess.TimeoutExpired:
            worker.kill()


if __name__ == "__main__":
    raise SystemExit(main())
