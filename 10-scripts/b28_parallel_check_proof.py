#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Plan:     04-docs/05-modules/07-billing/15-bulk-bill-run-build-plan.md B28
#           (changes row 55) — "PostgreSQL proof at 40,000 accounts"
# Journey:  J73 S1/S4 · 08-qa/01-e2e/journeys/J73-bulk-run-breakdown-and-scale.md
# Seed:     manage.py seed_j72_bulk_run --accounts 40000 (the J73 world)
# Code:     06-backend/apps/billing/check_batches.py
# ───────────────────────────────────────────────────────
"""Time the bulk Check at scale on REAL Celery workers and real PostgreSQL 16.

TEST HARNESS ONLY. Writes nothing but what the product writes when a clerk
presses Check: it enqueues the Check through `run_jobs.enqueue_check` exactly as
`POST …/check` does, and real worker processes on the `billing` queue run the
coordinator and its batches. It refuses SQLite (hard-won law 14) and refuses a
role that bypasses row-level security — a superuser skips every tenant policy,
so its figures would not be the product's (19-check-cost-measured.md §1).

    after [--slots N] [--cap K] [--redis-port P]
        Starts a private redis and ONE Celery worker with `--concurrency N` on
        the `billing` queue (BILLING_WORKERS=N; the per-utility cap is K, or
        the ruled default max(1, N // 2) when K is 0). Clears the September
        run's saved Check, enqueues the Check, and polls the job records every
        2 s until the coordinator ends: wall time, batch count, the most batches
        ever RUNNING and ever ACTIVE (queued + running) at once — which must
        never exceed the cap — and the saved result: one row per account, every
        row saved by this Check, nobody saved twice.

    before
        The Check as one pass in this process (`check_store.check_run` — the
        inline path). Run it from a checkout of the tip BEFORE B28 to time the
        old code; run it here for the batched code on one worker.

USAGE (from 06-backend, as a role with no BYPASSRLS):
    DATABASE_URL=postgres://sbh_b27:sbh_b27@127.0.0.1:55433/sbh_b28_40k \\
      DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      nice -n 10 python ../10-scripts/b28_parallel_check_proof.py after --slots 4 --cap 0
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")


def _setup(slots: int, cap: int, broker: str | None) -> None:
    os.environ["BILLING_WORKERS"] = str(slots)
    os.environ["BILLING_CHECK_BATCHES_PER_UTILITY"] = str(cap)
    if broker:
        os.environ["CELERY_BROKER_URL"] = broker
    import django

    django.setup()
    from django.conf import settings

    settings.DEBUG = False  # no per-query log at 40,000 accounts


def _refuse() -> None:
    from django.db import connection

    if connection.vendor != "postgresql":
        sys.exit("refusing: PostgreSQL only (hard-won law 14)")
    with connection.cursor() as cursor:
        cursor.execute("select rolsuper or rolbypassrls from pg_roles where rolname = current_user")
        if cursor.fetchone()[0]:
            sys.exit("refusing: this role bypasses row-level security; the figure would not be the product's")


def _world():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "seed_journey_fixture", BACKEND.parent / "08-qa/01-e2e/stack/seed_journey_fixture.py"
    )
    sjf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sjf)  # type: ignore[union-attr]
    tenant, actor = sjf.tenant_and_actor()
    sys.path.insert(0, str(BACKEND.parent / "10-scripts"))
    return tenant, actor


def _september_run(tenant, actor):
    from datetime import date

    from apps.billing import models as bm
    from apps.billing import runs
    from apps.tenancy.management.commands.seed_j72_bulk_run import _template, ensure_cycle

    cycle = ensure_cycle(tenant)
    run = bm.BillRun.objects.filter(
        tenant=tenant,
        cycle=cycle,
        period_start=date(2026, 9, 1),
        period_end=date(2026, 9, 30),
        parent_run__isnull=True,
    ).first()
    if run is None:
        template_id, _ = _template()
        run = runs.create_run(
            cycle_id=cycle.id,
            period_start=date(2026, 9, 1),
            period_end=date(2026, 9, 30),
            bill_date=date(2026, 10, 1),
            due_days=21,
            label="September 2026 · Riverside",
            template_id=template_id,
            run_by=getattr(actor, "user", None),
        )
    return run


def _redis(port: int):
    probe = subprocess.run(["redis-cli", "-p", str(port), "ping"], capture_output=True, text=True)
    if probe.stdout.strip() == "PONG":
        return None
    proc = subprocess.Popen(
        ["redis-server", "--port", str(port), "--save", "", "--appendonly", "no"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        if subprocess.run(["redis-cli", "-p", str(port), "ping"], capture_output=True, text=True).stdout.strip() == "PONG":
            return proc
        time.sleep(0.1)
    raise SystemExit("redis did not start")


def _worker(slots: int, log: Path) -> subprocess.Popen:
    return subprocess.Popen(
        [
            "nice", "-n", "10", sys.executable, "-m", "celery", "-A", "config.celery", "worker",
            "-Q", "billing", "--concurrency", str(slots), "--loglevel", "warning",
            "--without-heartbeat", "--without-gossip", "--without-mingle",
        ],
        cwd=str(BACKEND),
        env=dict(os.environ),
        stdout=log.open("ab"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def _saved(run, coordinator_id=None) -> dict:
    from django.db.models import Count

    from apps.billing import check_models

    rows = check_models.BillRunAccountCheck.objects.filter(bill_run=run)
    out = {
        "saved_rows": rows.count(),
        "accounts_saved_twice": rows.values("account_id").annotate(n=Count("id")).filter(n__gt=1).count(),
    }
    if coordinator_id is not None:
        out["saved_by_this_check"] = rows.filter(job_id=coordinator_id).count()
    return out


def after(slots: int, cap: int, port: int, log: Path) -> dict:
    import signal

    from apps.billing import check_batches, check_models, run_jobs, runs
    from core import jobs as core_jobs
    from core import tenancy as core_tenancy

    _refuse()
    tenant, actor = _world()
    with core_tenancy.tenant_context(tenant.id):
        run = _september_run(tenant, actor)
        scope = runs.scope_account_count(cycle_id=run.cycle_id, scope_services=None)
        check_models.BillRunAccountCheck.objects.filter(bill_run=run).delete()
    redis = _redis(port)
    worker = _worker(slots, log)
    out: dict = {
        "slots": slots,
        "cap": check_batches.batch_cap(),
        "batch_size": check_batches.BATCH_SIZE,
        "accounts_in_scope": scope,
        "load_at_start": os.getloadavg(),
    }
    try:
        time.sleep(6)  # the worker connects to the broker
        with core_tenancy.tenant_context(tenant.id):
            started = time.perf_counter()
            record = run_jobs.enqueue_check(run, actor_user_id=None)
        coordinator = record["id"]
        out["coordinator"] = coordinator
        peak_running = peak_active = 0
        timeline = []
        while True:
            time.sleep(2)
            with core_tenancy.tenant_context(tenant.id):
                job = core_jobs.current(coordinator)
                active = core_jobs.active_records(check_batches.CHECK_BATCH_JOB)
            running = sum(1 for a in active if a["status"] == core_jobs.RUNNING)
            peak_running = max(peak_running, running)
            peak_active = max(peak_active, len(active))
            elapsed = time.perf_counter() - started
            timeline.append((round(elapsed), (job.get("progress") or {}).get("done"), running))
            if len(timeline) % 15 == 1:
                print(f"  {elapsed:7.0f}s  {job['status']:<9} {job.get('progress')}  running {running}", flush=True)
            if job["status"] in (core_jobs.SUCCEEDED, core_jobs.FAILED):
                break
            if worker.poll() is not None:
                out["worker_exited"] = worker.returncode
                break
        seconds = time.perf_counter() - started
        with core_tenancy.tenant_context(tenant.id):
            job = core_jobs.current(coordinator)
            batches = (job.get("checkpoint") or {}).get("batches") or []
            run.refresh_from_db()
            out.update(
                {
                    "status": job["status"],
                    "error": job.get("error"),
                    "seconds": round(seconds, 1),
                    "minutes": round(seconds / 60, 1),
                    "ms_per_account": round(1000 * seconds / max(scope, 1), 1),
                    "batches": len(batches),
                    "peak_batches_running": peak_running,
                    "peak_batches_active": peak_active,
                    "progress": job.get("progress"),
                    "summary_accounts": (run.findings_summary or {}).get("accounts"),
                    "summary_job_id_is_this_check": (run.findings_summary or {}).get("job_id") == coordinator,
                    **_saved(run, coordinator),
                }
            )
        out["load_at_end"] = os.getloadavg()
        out["timeline_every_2s"] = timeline[:: max(1, len(timeline) // 40)]
    finally:
        try:
            os.killpg(worker.pid, signal.SIGTERM)
            worker.wait(timeout=30)
        except Exception:  # noqa: BLE001
            os.killpg(worker.pid, signal.SIGKILL)
        if redis is not None:
            redis.terminate()
    return out


def before() -> dict:
    from apps.billing import check_models, check_store
    from core import tenancy as core_tenancy

    _refuse()
    tenant, actor = _world()
    with core_tenancy.tenant_context(tenant.id):
        run = _september_run(tenant, actor)
        check_models.BillRunAccountCheck.objects.filter(bill_run=run).delete()
        load = os.getloadavg()
        started = time.perf_counter()
        counts = check_store.check_run(run)
        seconds = time.perf_counter() - started
        saved = _saved(run)
    accounts = int(counts.get("accounts") or 0)
    return {
        "accounts": accounts,
        "seconds": round(seconds, 1),
        "minutes": round(seconds / 60, 1),
        "ms_per_account": round(1000 * seconds / max(accounts, 1), 1),
        "load_at_start": load,
        "load_at_end": os.getloadavg(),
        **saved,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("after")
    a.add_argument("--slots", type=int, default=4)
    a.add_argument("--cap", type=int, default=0)
    a.add_argument("--redis-port", type=int, default=6391)
    sub.add_parser("before")
    args = parser.parse_args()
    if args.cmd == "after":
        broker = f"redis://127.0.0.1:{args.redis_port}/0"
        _setup(args.slots, args.cap, broker)
        log = Path(os.environ.get("TMPDIR", "/tmp")) / f"b28_worker_{args.slots}_{args.cap}.log"
        result = after(args.slots, args.cap, args.redis_port, log)
        result["worker_log"] = str(log)
    else:
        _setup(int(os.environ.get("BILLING_WORKERS", "2")), 0, None)
        result = before()
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
