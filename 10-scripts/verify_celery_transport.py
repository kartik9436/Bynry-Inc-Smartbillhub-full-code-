#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: BE-07 jobs framework — the PROOF that the Celery transport consumes
#            the queue, run against a real Redis, a real worker process and a
#            real database, under PRODUCTION dispatch (JOBS_EAGER=false).
# Change:   PO ruling 2026-08-19 — *"We want Async job install redis and celery;
#           Trigger after tenant creation; also add these two services in docker
#           compose"* (12-governance/02-decision-log.md)
# Defect:   DEF-320 (four job kinds enqueued, production dispatched none) ·
#           DEF-326 (the bulk rate change answered 202 and applied no price)
# ───────────────────────────────────────────────────────
"""Does a job enqueued under production dispatch actually RUN? Ask a worker.

WHY THIS IS A SCRIPT AND NOT A PYTEST TEST, stated so nobody "fixes" it into one.
The thing that shipped broken was not a function — every unit test of every job
body passes, and has all along. What shipped broken was the SPACE BETWEEN THREE
PROCESSES: a web process that enqueues, a broker that carries, and a worker that
consumes. Every test in `06-backend/tests` runs in ONE process and turns
`JOBS_EAGER` on to make the job finish, which is precisely the configuration
production does not use. A test that proved this would have to start a broker
and fork a worker, and a suite that does that is a suite people switch off.

So: `06-backend/tests/test_cr017_celery_transport.py` proves the WIRING in
process (the dispatcher reaches the task, the task enters the right tenant's
context, a broker that is down leaves a `queued` record and no 500), and THIS
proves the thing only three processes can prove.

    redis-server --daemonize yes --port 6379 --save "" --appendonly no
    python3 10-scripts/verify_celery_transport.py

It exits non-zero the moment any kind fails to leave `queued`, and prints one
line per kind with the status the worker left behind.

WHAT COUNTS AS A PASS, and why `failed` is one for three of the four kinds.
The question this answers is *"did anything consume the queue"*, and a record
that reads `failed: <a named error>` answers it as completely as `succeeded`
does — the worker took the message, entered the tenant, loaded the body and ran
it. `queued` is the ONLY failing outcome, because `queued` is what DEF-320 was.
The sample plant is held to the higher bar and must reach `succeeded`, because
it is the one this lane can hand a payload that is real.

⚠ **THIS SCRIPT CANNOT PROVE ANYTHING ABOUT A BILLING JOB, AND FROM 2026-08-31 THAT
IS A REAL LIMIT AND NOT A GAP IN THE LIST OF KINDS (CR-051 task 29).** The worker
it starts below carries no `-Q`, so it consumes the DEFAULT queue — which was every
queue until billing was given its own. Add `billing.run.calculate` (or its two
siblings) to `KINDS` and this script will sit there watching a record read `queued`
until the timeout, and report it as DEF-320 — *"nothing consumed the queue"* — when
the real cause is that the message is on a queue this worker was never asked to
drain. **The billing queue has its own three-process proof:**
`10-scripts/verify_billing_queue_split.py`, which additionally checks the thing
only two workers can show — that a `-Q celery` worker LEAVES a billing message
alone.
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
os.environ.setdefault(
    "DATABASE_URL", "postgres://smartbillhub:smartbillhub@localhost:5432/sbh_e2e"
)
# ⚠ THE WHOLE POINT. Eager dispatch would run every body inside this script and
# prove nothing about a worker; this is production's own setting.
os.environ["JOBS_EAGER"] = "false"
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")

import django  # noqa: E402

django.setup()

from django.utils import timezone  # noqa: E402

from apps.audit import services as audit_services  # noqa: E402
from apps.rating import services as rating_services  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from apps.tenancy import exports as tenancy_exports  # noqa: E402
from apps.tenancy import sample_data as tenancy_sample_data  # noqa: E402
from core import jobs as core_jobs  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

TIMEOUT_S = 240
POLL_S = 1.0


def _worker_env() -> dict[str, str]:
    env = dict(os.environ)
    env["JOBS_EAGER"] = "false"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def start_worker(log_path: Path) -> subprocess.Popen:
    log = log_path.open("wb")
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "config.celery",
            "worker",
            "--loglevel",
            "info",
            "--concurrency",
            "2",
            # A queue of this run's own, so a second lane's worker on the same
            # Redis cannot steal these messages and report a false green.
            "-n",
            f"verify-{uuid.uuid4().hex[:8]}@%h",
        ],
        cwd=str(BACKEND),
        env=_worker_env(),
        stdout=log,
        stderr=subprocess.STDOUT,
    )


def wait_for_terminal(job_id: str, tenant_id) -> str:
    deadline = time.time() + TIMEOUT_S
    last = "queued"
    while time.time() < deadline:
        with core_tenancy.tenant_context(tenant_id):
            row = tenancy_models.Job.objects.filter(id=uuid.UUID(job_id)).first()
        last = row.status if row is not None else "MISSING"
        if last in ("succeeded", "failed"):
            return last
        time.sleep(POLL_S)
    return last


def main() -> int:
    tenant = tenancy_models.Tenant.objects.order_by("provisioned_at").first()
    if tenant is None:
        print("no tenant on this database — run the e2e stack's seed first")
        return 2
    print(f"tenant under test: {tenant.subdomain} ({tenant.id})")

    log_path = Path("/tmp/celery-verify.log")
    worker = start_worker(log_path)
    print(f"worker pid {worker.pid}; log {log_path}")
    time.sleep(8)  # let it connect to the broker and register its tasks
    if worker.poll() is not None:
        print("WORKER DIED ON STARTUP:")
        print(log_path.read_text()[-3000:])
        return 2

    enqueued: list[tuple[str, str]] = []
    try:
        with core_tenancy.tenant_context(tenant.id):
            owner = None
            # 1 · the tenancy sample plant — the CR-017 kind, held to `succeeded`
            enqueued.append(
                (
                    tenancy_sample_data.PLANT_JOB_KIND,
                    core_jobs.enqueue(
                        tenancy_sample_data.PLANT_JOB_KIND,
                        # No scope_key: this tenant's real plant already ran and
                        # a scope-keyed re-enqueue would FOLD INTO IT and return
                        # a `succeeded` record without a worker touching
                        # anything — a false green of exactly the shape this
                        # script exists to refuse.
                        payload={"actor_user_id": str(owner) if owner else None},
                    )["id"],
                )
            )
            # 2 · the bulk rate change — DEF-326, the critical one
            enqueued.append(
                (
                    rating_services.RATE_CHANGE_JOB,
                    core_jobs.enqueue(
                        rating_services.RATE_CHANGE_JOB,
                        payload={
                            "entities": [],
                            "change": {"kind": "percent", "value": "0"},
                            "effective_from": timezone.now().date().isoformat(),
                            "reason": "CR-017 transport verification",
                            "fingerprint": f"verify-{uuid.uuid4().hex}",
                            "actor_user_id": None,
                        },
                    )["id"],
                )
            )
            # 3 · the audit CSV export (the S61 feed rides the same kind)
            enqueued.append(
                (
                    audit_services.EXPORT_JOB,
                    core_jobs.enqueue(
                        audit_services.EXPORT_JOB,
                        payload={
                            "filters": {},
                            "archive": False,
                            "row_count": 0,
                            "actor_user_id": None,
                        },
                    )["id"],
                )
            )
            # 4 · the shared list export
            enqueued.append(
                (
                    tenancy_exports.LIST_EXPORT_JOB,
                    core_jobs.enqueue(
                        tenancy_exports.LIST_EXPORT_JOB,
                        payload={"resource": "premises", "row_count": 0, "filters": {}},
                    )["id"],
                )
            )

        failures = 0
        for kind, job_id in enqueued:
            status = wait_for_terminal(job_id, tenant.id)
            verdict = "PASS" if status in ("succeeded", "failed") else "FAIL"
            if kind == tenancy_sample_data.PLANT_JOB_KIND and status != "succeeded":
                verdict = "FAIL"
            if verdict == "FAIL":
                failures += 1
            with core_tenancy.tenant_context(tenant.id):
                row = tenancy_models.Job.objects.filter(id=uuid.UUID(job_id)).first()
            detail = (row.error or "")[:120] if row is not None else "no record"
            progress = row.progress if row is not None else None
            print(f"  {verdict}  {kind:32s} {status:10s} progress={progress} {detail}")
        return 1 if failures else 0
    finally:
        worker.terminate()
        try:
            worker.wait(timeout=20)
        except subprocess.TimeoutExpired:
            worker.kill()


if __name__ == "__main__":
    sys.exit(main())
