#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Journey:  J73 — the bulk bill run, breakdown and scale (F1–F5, S1–S4) ·
#           08-qa/01-e2e/journeys/J73-bulk-run-breakdown-and-scale.md
# Criteria: 04-docs/05-modules/07-billing/20-bulk-run-clerk-acceptance.md §3–§4
# Seed:     manage.py seed_j72_bulk_run [--accounts N] [--send-failure] [--second-clerk]
# Spec:     07-frontend/e2e/J73-bulk-run-breakdown-and-scale.spec.ts (the browser half)
# Precedent: 10-scripts/cr051_kill_and_resume.py (a real kill, on real PostgreSQL)
# ───────────────────────────────────────────────────────
"""The half of J73 a browser cannot do: take a module down, kill a worker, time a pass.

TEST HARNESS ONLY. It changes no product code, writes only through the product's
own services and views, and refuses anything but PostgreSQL (hard-won law 14 —
every check here is about what a failed statement does to a transaction, which
SQLite cannot show).

SUBCOMMANDS
-----------
  meter-reads down|up|status
      F2's switch. **The product offers none** (`DEF-BIL-8510`): no setting,
      environment variable or seam hook makes Meter Reads stop answering. So
      this takes it down at the DATABASE: `routes` is renamed to
      `routes__j73_down`, which makes `metering.derivation.units_in_cycle` —
      the FIRST seam a Check calls — raise exactly as it would if Meter Reads'
      storage were unreachable; `up` renames it back. It is a real outage of
      one module's storage, not a mock, and it is only safe on a walk database
      nobody else is using: every route screen fails while it is down.

  f2-probe
      Creates (or finds) the September Riverside run, takes Meter Reads down,
      and drives the REAL views in-process — `POST …/check` (inline),
      `GET …/check`, `GET …/check/findings` — then brings it back and checks
      again. Prints what each answered.

  f1-worker-kill [--kill-at N] [--redis-port P]
      Starts a private redis and a real Celery worker on the `billing` queue,
      enqueues the Check as the product does (`run_jobs.enqueue_check`),
      SIGKILLs the worker when the job's progress passes N, records the
      progress and the saved results, starts a fresh worker, resumes the way
      the clerk's Resume does (`POST …/check/resume`), and records both again:
      how far it had got, how long the resume took, and whether any account
      was checked twice (two saved rows for one account). The Resume path runs
      the rest of the Check INSIDE the request (`DEF-BIL-8511`), which this
      subcommand is written to show.

  s1-check-time [--background]
      Runs the whole Check over the September run and prints its wall time and
      accounts per second — the S1 figure (≤ 10 min at 10,000, ≤ 30 min at
      40,000).

  s2-screens [--samples K]
      Times the three screens S2 names at the server, in-process through the
      real views: one tag's account list (`GET …/check/findings?tag=…`, page
      of 50), Sign off (`GET …/summary`) and Not in this run as the screen
      builds it today (`GET …/findings`). p50 / max against the 2-second bar.

USAGE (from 06-backend, against a walk database)
    DATABASE_URL=postgres://…/sbh_j73_10k DJANGO_SETTINGS_MODULE=config.settings.local \\
      JOBS_EAGER=false nice -n 10 python ../10-scripts/j73_bulk_run_harness.py f2-probe
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import statistics
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django

django.setup()

from django.conf import settings
from django.db import connection

settings.DEBUG = False  # no per-query log at 40,000 accounts (cr051_run_benchmark's reason)

DOWN_TABLE = "routes__j73_down"
SEPTEMBER = (date(2026, 9, 1), date(2026, 9, 30))
BILL_DATE = date(2026, 10, 1)
RUN_LABEL = "September 2026 · Riverside"


def _refuse_unless_postgres() -> None:
    if connection.vendor != "postgresql":
        sys.exit("refusing: J73's harness runs on PostgreSQL only (hard-won law 14)")


def _world():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "seed_journey_fixture", BACKEND.parent / "08-qa/01-e2e/stack/seed_journey_fixture.py"
    )
    sjf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sjf)  # type: ignore[union-attr]
    return sjf.tenant_and_actor()


def _september_run(tenant, actor):
    """The September Riverside run, created through `runs.create_run` if absent."""
    from apps.billing import models as bm
    from apps.billing import runs
    from apps.tenancy.management.commands.seed_j72_bulk_run import (
        _template,
        ensure_cycle,
    )

    cycle = ensure_cycle(tenant)
    run = bm.BillRun.objects.filter(
        tenant=tenant,
        cycle=cycle,
        period_start=SEPTEMBER[0],
        period_end=SEPTEMBER[1],
        parent_run__isnull=True,
    ).first()
    if run is None:
        template_id, _ = _template()
        run = runs.create_run(
            cycle_id=cycle.id,
            period_start=SEPTEMBER[0],
            period_end=SEPTEMBER[1],
            bill_date=BILL_DATE,
            due_days=21,
            label=RUN_LABEL,
            template_id=template_id,
            run_by=getattr(actor, "user", None),
        )
    return run


class _Api:
    """The REAL view functions, in-process, as a signed-in Billing Clerk.

    A request factory with `force_authenticate` stands in for the session
    cookie; `tenant_id` and `tenant_role` are what the tenant middleware and
    auth attach on a real request (`core.permissions._role_of`). What is timed
    and exercised is the view, its permission class and everything under it —
    not the network and not React.
    """

    def __init__(self, tenant, user, role: str = "billing_clerk") -> None:
        from rest_framework.test import APIRequestFactory

        self.factory = APIRequestFactory()
        self.tenant = tenant
        self.user = user
        self.role = role

    def call(self, view, method: str, path: str, data=None, **kwargs):
        from core import tenancy as core_tenancy
        from rest_framework.test import force_authenticate

        make = getattr(self.factory, method.lower())
        request = (
            make(path, data or {}, format="json") if method != "GET" else make(path, data or {})
        )
        force_authenticate(request, user=self.user)
        request.tenant_id = self.tenant.id
        request.tenant_role = self.role
        with core_tenancy.tenant_context(self.tenant.id):
            response = view(request, **kwargs)
        if hasattr(response, "render"):
            response.render()
        try:
            body = json.loads(response.content or b"null")
        except ValueError:
            body = response.content[:400].decode("utf-8", "replace")
        return response.status_code, body


# ── F2 · Meter Reads down ──────────────────────────────────────────────────
def meter_reads(state: str) -> str:
    with connection.cursor() as cur:
        cur.execute(
            "select to_regclass('routes') is not null, to_regclass(%s) is not null", [DOWN_TABLE]
        )
        up, down = cur.fetchone()
        if state == "status":
            return (
                "up"
                if up and not down
                else "down" if down and not up else f"odd (routes={up}, {DOWN_TABLE}={down})"
            )
        if state == "down":
            if down:
                return "already down"
            cur.execute(f'alter table routes rename to "{DOWN_TABLE}"')
            return "down: Meter Reads' routes table renamed; units_in_cycle will raise"
        if state == "up":
            if up:
                return "already up"
            cur.execute(f'alter table "{DOWN_TABLE}" rename to routes')
            return "up: routes restored"
    raise SystemExit(f"unknown state {state!r}")


def f2_probe() -> dict:
    from apps.billing import check_api
    from core import tenancy as core_tenancy

    tenant, actor = _world()
    with core_tenancy.tenant_context(tenant.id):
        run = _september_run(tenant, actor)
    api = _Api(tenant, getattr(actor, "user", actor))
    base = f"/api/{tenant.subdomain}/billing/runs/{run.pk}/check"
    out: dict = {"run": str(run.pk), "run_no": run.run_no}
    out["switch_down"] = meter_reads("down")
    try:
        out["post_check_while_down"] = api.call(
            check_api.run_check, "POST", base, {"background": False}, run_id=str(run.pk)
        )
        out["get_check_while_down"] = api.call(check_api.run_check, "GET", base, run_id=str(run.pk))
        out["get_findings_while_down"] = api.call(
            check_api.run_check_findings, "GET", base + "/findings", run_id=str(run.pk)
        )
    finally:
        out["switch_up"] = meter_reads("up")
    out["post_check_after_up"] = api.call(
        check_api.run_check, "POST", base, {"background": False}, run_id=str(run.pk)
    )
    out["get_check_after_up"] = api.call(check_api.run_check, "GET", base, run_id=str(run.pk))
    from apps.billing import models as bm

    with core_tenancy.tenant_context(tenant.id):
        out["run_kept"] = bm.BillRun.objects.filter(pk=run.pk).exists()
    return out


# ── F1 · kill a real Celery worker mid-Check ───────────────────────────────
def _start_redis(port: int) -> subprocess.Popen | None:
    probe = subprocess.run(
        ["redis-cli", "-p", str(port), "ping"], capture_output=True, text=True, check=False
    )
    if probe.stdout.strip() == "PONG":
        return None
    proc = subprocess.Popen(
        ["redis-server", "--port", str(port), "--save", "", "--appendonly", "no"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        if (
            subprocess.run(
                ["redis-cli", "-p", str(port), "ping"], capture_output=True, text=True, check=False
            ).stdout.strip()
            == "PONG"
        ):
            return proc
        time.sleep(0.1)
    raise SystemExit("redis did not start")


def _start_worker(broker: str, log: Path) -> subprocess.Popen:
    env = dict(os.environ, CELERY_BROKER_URL=broker, JOBS_EAGER="false")
    return subprocess.Popen(
        [
            "nice",
            "-n",
            "10",
            sys.executable,
            "-m",
            "celery",
            "-A",
            "config.celery",
            "worker",
            "-Q",
            "billing",
            "--concurrency",
            "1",
            "--loglevel",
            "warning",
            "--without-heartbeat",
            "--without-gossip",
            "--without-mingle",
        ],
        cwd=str(BACKEND),
        env=env,
        stdout=log.open("ab"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def _saved(run) -> dict:
    from apps.billing import check_models
    from django.db.models import Count

    rows = check_models.BillRunAccountCheck.objects.filter(bill_run=run)
    dupes = rows.values("account_id").annotate(n=Count("id")).filter(n__gt=1).count()
    return {"saved_rows": rows.count(), "accounts_saved_twice": dupes}


def f1_worker_kill(kill_at: int, redis_port: int, log: Path, *, finish: bool = False) -> dict:
    """F1 against a REAL Celery worker on PostgreSQL (DEF-BIL-8511 fixed).

    Kills the worker (SIGKILL — it writes nothing) once progress passes
    `kill_at`, starts a fresh worker, and then does what the Check SCREEN does:
    it polls `GET …/check` every 2 s. Since the fix, that read asks the workers
    whether any of them is executing the job; when none is, it hands the job
    back to the billing queue (`run_jobs.resume_job`) — so the run carries on
    by itself. `resumed_after_kill_s` is how long that took (before the fix:
    the broker's `visibility_timeout`, 8,820 s, or the clerk's Resume running
    the rest INSIDE the request). If the read has not resumed it within 120 s
    the harness presses Resume (`POST …/check/resume`) the way a clerk would,
    and records that the request returned without checking anything itself.
    With `finish`, it waits for the Check to end; otherwise it stops once the
    resumed pass has moved past the kill point and kills its own worker.
    """
    from apps.billing import check_api, check_models, run_jobs
    from core import jobs as core_jobs
    from core import tenancy as core_tenancy

    broker = f"redis://127.0.0.1:{redis_port}/0"
    settings.CELERY_BROKER_URL = broker
    from config.celery import app as celery_app

    celery_app.conf.broker_url = broker
    redis = _start_redis(redis_port)
    tenant, actor = _world()
    user = getattr(actor, "user", actor)
    out: dict = {"broker": broker, "kill_at": kill_at}
    worker = _start_worker(broker, log)
    api = _Api(tenant, user)
    try:
        with core_tenancy.tenant_context(tenant.id):
            run = _september_run(tenant, actor)
            check_models.BillRunAccountCheck.objects.filter(bill_run=run).delete()
            out["run"] = str(run.pk)
            started = time.perf_counter()
            record = run_jobs.enqueue_check(run, actor_user_id=user.id)
            job_id = record["id"]
            summary = dict(run.findings_summary or {})
            summary["job_id"] = job_id
            run.findings_summary = summary
            run.save(update_fields=["findings_summary", "updated_at"])
            out["job"] = job_id
            killed = None
            while time.perf_counter() - started < 3600:
                current = core_jobs.current(job_id)
                done = (current.get("progress") or {}).get("done") or 0
                if current["status"] in (core_jobs.FAILED, core_jobs.SUCCEEDED):
                    out["finished_before_kill"] = current["status"]
                    break
                if done >= kill_at:
                    os.killpg(worker.pid, signal.SIGKILL)
                    worker.wait()
                    killed = time.perf_counter()
                    break
                time.sleep(0.5)
            out["killed_after_s"] = None if killed is None else round(killed - started, 1)
            before = core_jobs.current(job_id)
            out["at_kill"] = {
                "status": before["status"],
                "progress": before.get("progress"),
                **_saved(run),
            }
        worker = _start_worker(broker, log)
        path = f"/api/{tenant.subdomain}/billing/runs/{run.pk}/check"
        resumed_at = None
        polls = []
        while killed is not None and time.perf_counter() - killed < 120:
            status, body = api.call(check_api.run_check, "GET", path, run_id=str(run.pk))
            job = (body or {}).get("job") or {} if isinstance(body, dict) else {}
            polls.append((round(time.perf_counter() - killed, 1), status, job.get("status")))
            if job.get("resumed"):
                resumed_at = time.perf_counter()
                break
            time.sleep(2)
        out["screen_polls"] = polls[-5:]
        if killed is not None and resumed_at is None:
            t0 = time.perf_counter()
            out["resume_response"] = api.call(
                check_api.run_check_resume, "POST", path + "/resume", {}, run_id=str(run.pk)
            )
            out["resume_request_s"] = round(time.perf_counter() - t0, 2)
            resumed_at = time.perf_counter()
            out["resumed_by"] = "clerk Resume"
        elif resumed_at is not None:
            out["resumed_by"] = "the Check screen's own poll"
        out["resumed_after_kill_s"] = (
            None if resumed_at is None or killed is None else round(resumed_at - killed, 1)
        )
        kill_done = ((out.get("at_kill") or {}).get("progress") or {}).get("done") or 0
        deadline = time.perf_counter() + (7200 if finish else 900)
        with core_tenancy.tenant_context(tenant.id):
            while time.perf_counter() < deadline:
                after = core_jobs.current(job_id)
                done = (after.get("progress") or {}).get("done") or 0
                if after["status"] in (core_jobs.FAILED, core_jobs.SUCCEEDED):
                    break
                if not finish and done >= kill_done + 50:
                    break
                time.sleep(1)
            out["after_resume"] = {
                "status": after["status"],
                "progress": after.get("progress"),
                "error": after.get("error"),
                **_saved(run),
            }
            from apps.billing import check_store

            out["tiles"] = check_store.counts(run)
    finally:
        try:
            os.killpg(worker.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        if redis is not None:
            redis.terminate()
    return out


# ── S1 · the Check's wall time ─────────────────────────────────────────────
def s1_check_time() -> dict:
    from apps.billing import check_models, check_store
    from core import tenancy as core_tenancy

    tenant, actor = _world()
    with core_tenancy.tenant_context(tenant.id):
        run = _september_run(tenant, actor)
        check_models.BillRunAccountCheck.objects.filter(bill_run=run).delete()
        started = time.perf_counter()
        counts = check_store.check_run(run)
        seconds = time.perf_counter() - started
    accounts = int(counts.get("accounts") or 0)
    return {
        "run": str(run.pk),
        "accounts": accounts,
        "seconds": round(seconds, 1),
        "accounts_per_second": round(accounts / seconds, 2) if seconds else None,
        "counts": counts,
    }


# ── S2 · three screens at 40,000 ───────────────────────────────────────────
def s2_screens(samples: int) -> dict:
    from apps.billing import api as billing_api
    from apps.billing import check_api
    from core import tenancy as core_tenancy

    tenant, actor = _world()
    with core_tenancy.tenant_context(tenant.id):
        run = _september_run(tenant, actor)
    api = _Api(tenant, getattr(actor, "user", actor))
    root = f"/api/{tenant.subdomain}/billing/runs/{run.pk}"
    _status, summary = api.call(
        check_api.run_check_findings, "GET", root + "/check/findings", run_id=str(run.pk)
    )
    tags = []
    if isinstance(summary, dict):
        for category in summary.get("categories") or []:
            for tag in category.get("tags") or []:
                tags.append((tag.get("count") or 0, tag.get("id") or tag.get("tag")))
    tag = max(tags)[1] if tags else None
    screens = {
        "tag_account_list": (
            check_api.run_check_findings,
            root + "/check/findings",
            {"tag": tag, "page_size": 50} if tag else {"list": "ready", "page_size": 50},
        ),
        "sign_off_summary": (billing_api.run_summary, root + "/summary", {}),
        "not_in_this_run_today (GET /findings)": (billing_api.run_findings, root + "/findings", {}),
    }
    out: dict = {"run": str(run.pk), "largest_tag": tag}
    for name, (view, path, params) in screens.items():
        times, last = [], None
        for _ in range(samples):
            t0 = time.perf_counter()
            last = api.call(view, "GET", path, params, run_id=str(run.pk))
            times.append(time.perf_counter() - t0)
            if times[-1] > 60:
                break  # a gunicorn worker is given 60 s; past that it is killed, not slow
        out[name] = {
            "status": last[0] if last else None,
            "p50_s": round(statistics.median(times), 3),
            "max_s": round(max(times), 3),
            "samples": len(times),
            "under_2s": max(times) < 2.0,
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    mr = sub.add_parser("meter-reads")
    mr.add_argument("state", choices=("down", "up", "status"))
    sub.add_parser("f2-probe")
    f1 = sub.add_parser("f1-worker-kill")
    f1.add_argument("--kill-at", type=int, default=200)
    f1.add_argument("--redis-port", type=int, default=6391)
    f1.add_argument("--log", default="/tmp/j73_f1_worker.log")
    f1.add_argument("--finish", action="store_true", help="wait for the Check to end")
    sub.add_parser("s1-check-time")
    s2 = sub.add_parser("s2-screens")
    s2.add_argument("--samples", type=int, default=5)
    args = parser.parse_args()
    _refuse_unless_postgres()
    if args.cmd == "meter-reads":
        result: object = meter_reads(args.state)
    elif args.cmd == "f2-probe":
        result = f2_probe()
    elif args.cmd == "f1-worker-kill":
        result = f1_worker_kill(args.kill_at, args.redis_port, Path(args.log), finish=args.finish)
    elif args.cmd == "s1-check-time":
        result = s1_check_time()
    else:
        result = s2_screens(args.samples)
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
