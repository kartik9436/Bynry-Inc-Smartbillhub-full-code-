#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Journey:  J73 S2–S4 · 08-qa/01-e2e/journeys/J73-bulk-run-breakdown-and-scale.md
# Criteria: 04-docs/05-modules/07-billing/20-bulk-run-clerk-acceptance.md §4
# Seed:     manage.py seed_j72_bulk_run --accounts 40000 (the J73 world, B28's sbh_b28_40k)
# Siblings: 10-scripts/b28_parallel_check_proof.py (S1, the batched Check timed)
#           10-scripts/j73_bulk_run_harness.py (F1, F2; its s2-screens predates the
#           saved-check reads and times /summary and /findings, which the screen no
#           longer calls)
# ───────────────────────────────────────────────────────
"""The scale half of J73 that a browser cannot do: S2's server reads, S3's Send
with a worker killed part-way, S4's second utility during a 40,000-account Check.

TEST HARNESS ONLY. It writes only through the product's own views and job
records, refuses SQLite (hard-won law 14) and refuses a role that bypasses
row-level security (the figures would not be the product's — DEF-2717).

    s2-server [--samples K]
        The three screens' reads, in-process through the REAL views as a Billing
        Clerk, timed: the largest tag's account page (`GET …/check/findings?tag=`),
        Sign off (`GET …/sign-off-summary`) and Not in this run
        (`GET …/not-in-run?page=1&per=50`). Then NFR-3's question, asked of each
        list: how many rows does it serve when asked for 100,000 per page?

    calculate [--slots N]
        Price the run on a real Celery worker (`POST …/calculate`, background),
        polled to the end. Times it. The deployment ceiling
        BILLING_MAX_ACCOUNTS_PER_RUN (25,000 by default, DEF-BIL-4224) refuses a
        40,000-account run, so the operator's override is typed here (0) and the
        result says so.

    sign-off
        `POST …/release` with the five confirmations, as the Sign off step does.

    send-scale [--phases noindex:1:240,index:1:240,index:2:end] [--slots N] [--wait-quiet S]
        THE PRODUCT'S SEND SINCE 2.425.0 (DEF-BIL-8726, DEF-BIL-8710): batches of
        500 under a coordinator, timed phase by phase with the load beside every
        sample. Each phase but the last ends in a SIGKILL of the whole worker, and
        NOTHING hands the Send back but the Send screen's own poll
        (`GET …/issue/progress`, every 2 s). `noindex` drops billing 0037's
        `ix_invoice_lines_id` for that phase (as the database owner, harness
        only) to time the code before 2.424.0 on the same world; it is always
        re-created at the end.

    send-resume [--wait-alone S] [--kill-after S]
        The same, for a Send whose worker is ALREADY dead (killed by hand); with
        --kill-after, the resumed pass is killed again that many seconds in.

    send [--kill-at N] [--wait-alone S] [--slots N]
        `POST …/issue` with `background: true` on a real worker, polled as the
        Send step polls `GET /jobs/{id}`. When progress passes N the worker is
        SIGKILLed; a fresh worker starts and the job is watched for S seconds to
        see whether anything carries it on by itself; then it is handed back the
        way the Check's Resume does (`run_jobs.resume_job`) and polled to the
        end. Then a SECOND `POST …/issue`, and the rows it wrote are counted.

    db-verify
        Reads PostgreSQL: duplicate invoice numbers, every authorised bill issued
        exactly once, every issue audited once, journals balanced.

    s4 [--slots N] [--b-subdomain S] [--start-b-at N]
        A real worker with N slots. Utility A's whole Check is enqueued; when its
        progress passes the mark, utility B's Check is enqueued and timed from the
        press to B's coordinator running, its first batch running, and B done —
        with A's progress and A's running batches recorded beside each.

USAGE (from 06-backend, as a role with no BYPASSRLS):
    DATABASE_URL=postgres://sbh_b27:sbh_b27@127.0.0.1:55433/sbh_s14_40k \\
      DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      python ../10-scripts/j73_scale_proof.py s2-server
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
from datetime import date, datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

SEPTEMBER = (date(2026, 9, 1), date(2026, 9, 30))


def _setup(slots: int, broker: str | None) -> None:
    os.environ["BILLING_WORKERS"] = str(slots)
    os.environ.setdefault("BILLING_CHECK_BATCHES_PER_UTILITY", "0")
    # The operator's override of the per-run ceiling (DEF-BIL-4224); see `calculate`.
    os.environ.setdefault("BILLING_MAX_ACCOUNTS_PER_RUN", "0")
    if broker:
        os.environ["CELERY_BROKER_URL"] = broker
    import django

    django.setup()
    from django.conf import settings

    settings.DEBUG = False


def _refuse() -> None:
    from django.db import connection

    if connection.vendor != "postgresql":
        sys.exit("refusing: PostgreSQL only (hard-won law 14)")
    with connection.cursor() as cursor:
        cursor.execute("select rolsuper or rolbypassrls from pg_roles where rolname = current_user")
        if cursor.fetchone()[0]:
            sys.exit("refusing: this role bypasses row-level security")


def _world():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "seed_journey_fixture", BACKEND.parent / "08-qa/01-e2e/stack/seed_journey_fixture.py"
    )
    sjf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sjf)  # type: ignore[union-attr]
    return sjf.tenant_and_actor()


def _run_a(tenant, actor):
    from apps.billing import models as bm
    from apps.tenancy.management.commands.seed_j72_bulk_run import ensure_cycle

    cycle = ensure_cycle(tenant)
    return bm.BillRun.objects.get(
        tenant=tenant, cycle=cycle, period_start=SEPTEMBER[0], period_end=SEPTEMBER[1],
        parent_run__isnull=True,
    )


class _Api:
    """The REAL view functions, in-process, as a signed-in clerk (j73_bulk_run_harness's)."""

    def __init__(self, tenant, user, role: str = "billing_clerk") -> None:
        from rest_framework.test import APIRequestFactory

        self.factory = APIRequestFactory()
        self.tenant, self.user, self.role = tenant, user, role

    def call(self, view, method: str, path: str, data=None, **kwargs):
        from core import tenancy as core_tenancy
        from rest_framework.test import force_authenticate

        make = getattr(self.factory, method.lower())
        request = make(path, data or {}, format="json") if method != "GET" else make(path, data or {})
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
        return response.status_code, body, len(response.content or b"")


def _redis(port: int):
    probe = subprocess.run(["redis-cli", "-p", str(port), "ping"], capture_output=True, text=True)
    if probe.stdout.strip() == "PONG":
        return None
    proc = subprocess.Popen(
        ["redis-server", "--port", str(port), "--save", "", "--appendonly", "no"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        if subprocess.run(["redis-cli", "-p", str(port), "ping"], capture_output=True, text=True).stdout.strip() == "PONG":
            return proc
        time.sleep(0.1)
    raise SystemExit("redis did not start")


def _worker(slots: int, log: Path) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "celery", "-A", "config.celery", "worker", "-Q", "billing",
         "--concurrency", str(slots), "--loglevel", "warning",
         "--without-heartbeat", "--without-gossip", "--without-mingle"],
        cwd=str(BACKEND), env=dict(os.environ), stdout=log.open("ab"),
        stderr=subprocess.STDOUT, start_new_session=True,
    )


def _stop(worker: subprocess.Popen, sig=signal.SIGTERM) -> None:
    try:
        os.killpg(worker.pid, sig)
        worker.wait(timeout=30)
    except Exception:  # noqa: BLE001
        try:
            os.killpg(worker.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _load() -> float:
    return round(os.getloadavg()[0], 2)


# ── S2 · the three screens' reads ──────────────────────────────────────────
def s2_server(samples: int) -> dict:
    from apps.billing import check_api
    from core import tenancy as core_tenancy

    _refuse()
    tenant, actor = _world()
    with core_tenancy.tenant_context(tenant.id):
        run = _run_a(tenant, actor)
    api = _Api(tenant, getattr(actor, "user", actor))
    root = f"/api/{tenant.subdomain}/billing/runs/{run.pk}"
    status, summary, _ = api.call(check_api.run_check_findings, "GET", root + "/check/findings", run_id=str(run.pk))
    tags = []
    for category in (summary or {}).get("categories") or []:
        for tag in category.get("tags") or []:
            tags.append((tag.get("accounts") or tag.get("count") or 0, tag.get("code") or tag.get("id") or tag.get("tag")))
    tag = max(tags)[1] if tags else None
    screens = {
        "check_summary (categories and tags)": (check_api.run_check_findings, "/check/findings", {}),
        "tag_account_list": (check_api.run_check_findings, "/check/findings", {"tag": tag, "page": 1, "per": 50}),
        "ready_list": (check_api.run_check_findings, "/check/findings", {"list": "ready", "page": 1, "per": 50}),
        "sign_off_summary": (check_api.run_sign_off_summary, "/sign-off-summary", {}),
        "not_in_this_run": (check_api.run_not_in_run, "/not-in-run", {"page": 1, "per": 50}),
    }
    out: dict = {"run": str(run.pk), "tags": sorted(tags, reverse=True)[:6], "largest_tag": tag, "load_start": _load()}
    for name, (view, suffix, params) in screens.items():
        times, last = [], None
        for _ in range(samples):
            t0 = time.perf_counter()
            last = api.call(view, "GET", root + suffix, params, run_id=str(run.pk))
            times.append(time.perf_counter() - t0)
        body = last[1] if isinstance(last[1], dict) else {}
        out[name] = {
            "status": last[0],
            "first_s": round(times[0], 3),
            "p50_s": round(statistics.median(times), 3),
            "max_s": round(max(times), 3),
            "bytes": last[2],
            "rows_served": len(body.get("results") or body.get("accounts") or []),
            "count": body.get("count"),
            "under_2s": max(times) < 2.0,
        }
    # NFR-3: ask each list for 100,000 rows in one page.
    nfr3 = {}
    for name, (view, suffix, params) in {
        "tag_account_list": screens["tag_account_list"],
        "ready_list": screens["ready_list"],
        "not_in_this_run": screens["not_in_this_run"],
    }.items():
        big = dict(params, per=100000, page_size=100000)
        t0 = time.perf_counter()
        code, body, size = api.call(view, "GET", root + suffix, big, run_id=str(run.pk))
        body = body if isinstance(body, dict) else {}
        nfr3[name] = {
            "status": code,
            "seconds": round(time.perf_counter() - t0, 3),
            "rows_served": len(body.get("results") or body.get("accounts") or []),
            "per_answered": body.get("per"),
            "count": body.get("count"),
            "bytes": size,
        }
    out["nfr3_asked_for_100000_per_page"] = nfr3
    out["load_end"] = _load()
    return out


# ── the job loop shared by calculate and send ──────────────────────────────
def _poll(job_id: str, tenant_id, until: float, every: float = 2.0, kill_at: int | None = None,
          worker: subprocess.Popen | None = None, timeline: list | None = None, t0: float = 0.0):
    from core import jobs as core_jobs
    from core import tenancy as core_tenancy

    while time.perf_counter() < until:
        with core_tenancy.tenant_context(tenant_id):
            job = core_jobs.current(job_id)
        done = (job.get("progress") or {}).get("done")
        if timeline is not None:
            timeline.append((round(time.perf_counter() - t0), job["status"], done, _load()))
        if job["status"] in (core_jobs.SUCCEEDED, core_jobs.FAILED):
            return job, "ended"
        if kill_at is not None and done is not None and done >= kill_at and worker is not None:
            return job, "kill"
        time.sleep(every)
    with core_tenancy.tenant_context(tenant_id):
        return core_jobs.current(job_id), "timeout"


def calculate(slots: int, port: int, log: Path) -> dict:
    from apps.billing import api as billing_api
    from apps.billing import models as bm
    from core import tenancy as core_tenancy

    _refuse()
    tenant, actor = _world()
    with core_tenancy.tenant_context(tenant.id):
        run = _run_a(tenant, actor)
    api = _Api(tenant, getattr(actor, "user", actor))
    redis = _redis(port)
    worker = _worker(slots, log)
    out: dict = {"slots": slots, "BILLING_MAX_ACCOUNTS_PER_RUN": os.environ.get("BILLING_MAX_ACCOUNTS_PER_RUN"),
                 "load_start": _load()}
    timeline: list = []
    try:
        time.sleep(6)
        t0 = time.perf_counter()
        code, body, _ = api.call(billing_api.run_calculate, "POST",
                                 f"/api/{tenant.subdomain}/billing/runs/{run.pk}/calculate",
                                 {"background": True}, run_id=str(run.pk))
        out["post"] = {"status": code, "job_id": (body or {}).get("job_id") if isinstance(body, dict) else body}
        if code != 202:
            out["refused"] = body
            return out
        job, why = _poll(body["job_id"], tenant.id, time.perf_counter() + 4 * 3600, every=5,
                         timeline=timeline, t0=t0)
        out.update({"ended": why, "status": job["status"], "error": job.get("error"),
                    "progress": job.get("progress"), "seconds": round(time.perf_counter() - t0, 1)})
        with core_tenancy.tenant_context(tenant.id):
            out["drafts"] = bm.Invoice.objects.filter(bill_run=run, status=bm.INVOICE_DRAFT).count()
            out["breaks"] = bm.BillRunBreak.objects.filter(bill_run=run).count() if hasattr(bm, "BillRunBreak") else None
    finally:
        _stop(worker)
        if redis is not None:
            redis.terminate()
        out["load_end"] = _load()
        out["timeline"] = timeline[:: max(1, len(timeline) // 40)]
    return out


def sign_off() -> dict:
    from apps.billing import api as billing_api
    from core import tenancy as core_tenancy

    _refuse()
    tenant, actor = _world()
    with core_tenancy.tenant_context(tenant.id):
        run = _run_a(tenant, actor)
    api = _Api(tenant, getattr(actor, "user", actor))
    t0 = time.perf_counter()
    code, body, _ = api.call(
        billing_api.run_release, "POST", f"/api/{tenant.subdomain}/billing/runs/{run.pk}/release",
        {"confirmations": {k: True for k in ("compliance", "email_mandate", "sms_mandate", "autopay_mandate", "final")},
         "confirmed_at": datetime.now(timezone.utc).isoformat()},
        run_id=str(run.pk),
    )
    keep = ("id", "bill_count", "total_amount", "currency", "created", "released_at")
    return {"status": code, "seconds": round(time.perf_counter() - t0, 1),
            "release": {k: body.get(k) for k in keep} if isinstance(body, dict) else body}


def _issue_counts(run) -> dict:
    from django.db import connection

    with connection.cursor() as c:
        c.execute("select count(*) filter (where status <> 'draft'), count(*) filter (where status = 'draft') "
                  "from invoices where bill_run_id = %s", [str(run.pk)])
        issued, drafts = c.fetchone()
        c.execute("select count(*) from audit_log where action = 'invoice.issued' and entity_id in "
                  "(select id from invoices where bill_run_id = %s)", [str(run.pk)])
        audits = c.fetchone()[0]
    return {"issued": issued, "drafts": drafts, "issue_audits": audits}


def send(kill_at: int, wait_alone: int, slots: int, port: int, log: Path) -> dict:
    from apps.billing import api as billing_api
    from apps.billing import run_jobs
    from core import jobs as core_jobs
    from core import tenancy as core_tenancy

    _refuse()
    tenant, actor = _world()
    with core_tenancy.tenant_context(tenant.id):
        run = _run_a(tenant, actor)
        before = _issue_counts(run)
    api = _Api(tenant, getattr(actor, "user", actor))
    path = f"/api/{tenant.subdomain}/billing/runs/{run.pk}/issue"
    redis = _redis(port)
    worker = _worker(slots, log)
    out: dict = {"slots": slots, "kill_at": kill_at, "before": before, "load_start": _load()}
    timeline: list = []
    try:
        time.sleep(6)
        t0 = time.perf_counter()
        issued_at = datetime.now(timezone.utc).isoformat()
        code, body, _ = api.call(billing_api.run_issue, "POST", path,
                                 {"issued_at": issued_at, "background": True}, run_id=str(run.pk))
        out["post"] = {"status": code, "job_id": body.get("job_id") if isinstance(body, dict) else body}
        if code != 202:
            out["refused"] = body
            return out
        job_id = body["job_id"]
        job, why = _poll(job_id, tenant.id, time.perf_counter() + 4 * 3600, every=2,
                         kill_at=kill_at, worker=worker, timeline=timeline, t0=t0)
        if why == "kill":
            _stop(worker, signal.SIGKILL)
            killed_at = time.perf_counter()
            with core_tenancy.tenant_context(tenant.id):
                at_kill = core_jobs.current(job_id)
                out["at_kill"] = {"seconds": round(killed_at - t0, 1), "progress": at_kill.get("progress"),
                                  "status": at_kill["status"], **_issue_counts(run)}
            worker = _worker(slots, log)
            # Does anything carry it on by itself? The Send step only polls GET /jobs/{id}.
            job, why = _poll(job_id, tenant.id, time.perf_counter() + wait_alone, every=5,
                             timeline=timeline, t0=t0)
            with core_tenancy.tenant_context(tenant.id):
                out["after_waiting_alone"] = {"waited_s": wait_alone, "status": job["status"],
                                              "progress": job.get("progress"), **_issue_counts(run),
                                              "abandoned": run_jobs.job_is_abandoned(job_id)}
            # A second press of Send while it is stuck — what does the clerk get?
            code2, body2, _ = api.call(billing_api.run_issue, "POST", path,
                                       {"issued_at": issued_at, "background": True}, run_id=str(run.pk))
            out["send_pressed_again_while_stuck"] = {
                "status": code2, "same_job": isinstance(body2, dict) and body2.get("job_id") == job_id,
                "job_status": body2.get("status") if isinstance(body2, dict) else None}
            if job["status"] not in (core_jobs.SUCCEEDED, core_jobs.FAILED):
                r0 = time.perf_counter()
                with core_tenancy.tenant_context(tenant.id):
                    _record, outcome = run_jobs.resume_job(run, job_id)
                out["handed_back"] = {"outcome": outcome, "at_s": round(r0 - t0, 1)}
                job, why = _poll(job_id, tenant.id, time.perf_counter() + 4 * 3600, every=5,
                                 timeline=timeline, t0=t0)
                out["resume_seconds"] = round(time.perf_counter() - r0, 1)
        out.update({"ended": why, "status": job["status"], "error": job.get("error"),
                    "progress": job.get("progress"), "seconds": round(time.perf_counter() - t0, 1)})
        with core_tenancy.tenant_context(tenant.id):
            out["after"] = _issue_counts(run)
        # The second Send: a replay must write nothing.
        code3, body3, _ = api.call(billing_api.run_issue, "POST", path,
                                   {"issued_at": datetime.now(timezone.utc).isoformat(), "background": True},
                                   run_id=str(run.pk))
        time.sleep(10)
        with core_tenancy.tenant_context(tenant.id):
            out["second_send"] = {"status": code3, "created": body3.get("created") if isinstance(body3, dict) else None,
                                  "counts_after": _issue_counts(run)}
    finally:
        _stop(worker)
        if redis is not None:
            redis.terminate()
        out["load_end"] = _load()
        out["timeline"] = timeline[:: max(1, len(timeline) // 60)]
    return out


def send_resume(wait_alone: int, kill_after: int | None, slots: int, port: int, log: Path) -> dict:
    """A Send whose worker was KILLED already (by hand, `kill -9`, or by `send --kill-at`):
    a fresh worker, then the same questions `send` asks after its kill — does anything
    carry it on alone, what does a second press of Send do, does a hand-back finish it —
    and, with `kill_after`, a SECOND kill that many seconds into the resumed pass."""
    from apps.billing import api as billing_api
    from apps.billing import run_jobs
    from core import jobs as core_jobs
    from core import tenancy as core_tenancy

    _refuse()
    tenant, actor = _world()
    with core_tenancy.tenant_context(tenant.id):
        run = _run_a(tenant, actor)
        job_id = str(core_jobs.active_records(run_jobs.ISSUE_JOB)[0]["id"])
        job = core_jobs.current(job_id)
        out: dict = {"job": job_id, "at_start": {"status": job["status"], "progress": job.get("progress"),
                                                 **_issue_counts(run)}, "load_start": _load()}
    api = _Api(tenant, getattr(actor, "user", actor))
    path = f"/api/{tenant.subdomain}/billing/runs/{run.pk}/issue"
    redis = _redis(port)
    worker = _worker(slots, log)
    timeline: list = []
    t0 = time.perf_counter()
    try:
        time.sleep(6)
        job, why = _poll(job_id, tenant.id, time.perf_counter() + wait_alone, every=5, timeline=timeline, t0=t0)
        with core_tenancy.tenant_context(tenant.id):
            out["after_waiting_alone"] = {"waited_s": wait_alone, "status": job["status"],
                                          "progress": job.get("progress"), **_issue_counts(run),
                                          "abandoned": run_jobs.job_is_abandoned(job_id)}
        code2, body2, _ = api.call(billing_api.run_issue, "POST", path,
                                   {"issued_at": datetime.now(timezone.utc).isoformat(), "background": True},
                                   run_id=str(run.pk))
        out["send_pressed_again_while_stuck"] = {
            "status": code2, "same_job": isinstance(body2, dict) and body2.get("job_id") == job_id,
            "job_status": body2.get("status") if isinstance(body2, dict) else None}
        if job["status"] not in (core_jobs.SUCCEEDED, core_jobs.FAILED):
            r0 = time.perf_counter()
            with core_tenancy.tenant_context(tenant.id):
                _record, outcome = run_jobs.resume_job(run, job_id)
                before = _issue_counts(run)
            out["handed_back"] = {"outcome": outcome, "at_s": round(r0 - t0, 1), "issued_then": before["issued"]}
            until = time.perf_counter() + (kill_after if kill_after else 8 * 3600)
            job, why = _poll(job_id, tenant.id, until, every=5, timeline=timeline, t0=t0)
            with core_tenancy.tenant_context(tenant.id):
                now = _issue_counts(run)
            span = time.perf_counter() - r0
            out["resumed_pass"] = {"seconds": round(span, 1), "issued_in_it": now["issued"] - before["issued"],
                                   "bills_per_second": round((now["issued"] - before["issued"]) / span, 2) if span else None}
            if kill_after and why == "timeout":
                _stop(worker, signal.SIGKILL)
                with core_tenancy.tenant_context(tenant.id):
                    out["second_kill"] = {"status": core_jobs.current(job_id)["status"], **_issue_counts(run)}
                return out
        out.update({"ended": why, "status": job["status"], "error": job.get("error"),
                    "progress": job.get("progress"), "seconds": round(time.perf_counter() - t0, 1)})
        with core_tenancy.tenant_context(tenant.id):
            out["after"] = _issue_counts(run)
        code3, body3, _ = api.call(billing_api.run_issue, "POST", path,
                                   {"issued_at": datetime.now(timezone.utc).isoformat(), "background": True},
                                   run_id=str(run.pk))
        time.sleep(10)
        with core_tenancy.tenant_context(tenant.id):
            out["second_send"] = {"status": code3, "created": body3.get("created") if isinstance(body3, dict) else None,
                                  "counts_after": _issue_counts(run)}
    finally:
        _stop(worker)
        if redis is not None:
            redis.terminate()
        out["load_end"] = _load()
        out["timeline"] = timeline[:: max(1, len(timeline) // 60)]
    return out


def db_verify() -> dict:
    from django.db import connection

    from core import tenancy as core_tenancy

    _refuse()
    tenant, actor = _world()
    with core_tenancy.tenant_context(tenant.id):
        run = _run_a(tenant, actor)
        q = {
            "invoices_in_run": "select count(*) from invoices where bill_run_id = %(r)s",
            "issued": "select count(*) from invoices where bill_run_id = %(r)s and status <> 'draft'",
            "still_draft": "select count(*) from invoices where bill_run_id = %(r)s and status = 'draft'",
            "duplicate_invoice_numbers_in_tenant": (
                "select count(*) from (select invoice_no from invoices where invoice_no is not null "
                "group by invoice_no having count(*) > 1) d"),
            "accounts_issued_twice_in_run": (
                "select count(*) from (select account_id from invoices where bill_run_id = %(r)s "
                "and status <> 'draft' group by account_id having count(*) > 1) d"),
            "authorised_bill_count": "select coalesce(sum(bill_count),0) from bill_run_releases where bill_run_id = %(r)s",
            "releases": "select count(*) from bill_run_releases where bill_run_id = %(r)s",
            "releases_released": "select count(*) from bill_run_releases where bill_run_id = %(r)s and released_at is not null",
            "issue_audit_rows": ("select count(*) from audit_log where action = 'invoice.issued' and entity_id in "
                                 "(select id from invoices where bill_run_id = %(r)s)"),
            "invoices_with_two_issue_audits": (
                "select count(*) from (select entity_id from audit_log where action = 'invoice.issued' and entity_id in "
                "(select id from invoices where bill_run_id = %(r)s) group by entity_id having count(*) > 1) d"),
            "send_breaks": "select count(*) from bill_run_breaks where bill_run_id = %(r)s",
            "issued_bills_with_no_journal": (
                "select count(*) from invoices i where i.bill_run_id = %(r)s and i.status <> 'draft' and not exists "
                "(select 1 from journal_entries j where j.source_type = 'invoice' and j.source_id = i.id)"),
            "issued_bills_with_two_journals": (
                "select count(*) from (select j.source_id from journal_entries j join invoices i on j.source_id = i.id "
                "where j.source_type = 'invoice' and i.bill_run_id = %(r)s group by j.source_id having count(*) > 1) d"),
            "unbalanced_journal_entries": (
                "select count(*) from (select j.id from journal_entries j join invoices i on j.source_id = i.id "
                "join journal_lines l on l.journal_entry_id = j.id where j.source_type = 'invoice' and i.bill_run_id = %(r)s "
                "group by j.id having sum(case when l.side = 'debit' then l.amount else 0 end) "
                "<> sum(case when l.side = 'credit' then l.amount else 0 end)) d"),
            "journal_debits_total": (
                "select coalesce(sum(l.amount),0) from journal_lines l join journal_entries j on l.journal_entry_id = j.id "
                "join invoices i on j.source_id = i.id where j.source_type = 'invoice' and i.bill_run_id = %(r)s "
                "and l.side = 'debit'"),
            "journal_credits_total": (
                "select coalesce(sum(l.amount),0) from journal_lines l join journal_entries j on l.journal_entry_id = j.id "
                "join invoices i on j.source_id = i.id where j.source_type = 'invoice' and i.bill_run_id = %(r)s "
                "and l.side = 'credit'"),
            "issued_bills_total": "select coalesce(sum(total),0) from invoices where bill_run_id = %(r)s and status <> 'draft'",
        }
        out: dict = {"run": str(run.pk)}
        with connection.cursor() as c:
            for name, sql in q.items():
                try:
                    c.execute(sql, {"r": str(run.pk)})
                    out[name] = c.fetchone()[0]
                except Exception as exc:  # noqa: BLE001
                    out[name] = f"query failed: {exc}"
                    connection.rollback() if not connection.in_atomic_block else None
    return out


# ── S3 · the batched Send, phase by phase, killed and handed back by its poll ─
def _wait_for_quiet(limit_s: int, under: float = 2.0) -> dict:
    """Wait (up to `limit_s`) for the 1-minute load to drop under `under`."""
    t0 = time.perf_counter()
    seen = [_load()]
    while seen[-1] >= under and time.perf_counter() - t0 < limit_s:
        time.sleep(15)
        seen.append(_load())
    return {"waited_s": round(time.perf_counter() - t0), "load_then": seen[-1], "quiet": seen[-1] < under}


def _superuser_sql(sql: str) -> None:
    """The index switch is DDL the RLS role may not run: the harness does it as
    the database owner, through psql, on the test world only."""
    from django.db import connection

    db = connection.settings_dict
    subprocess.run(
        ["psql", "-h", db["HOST"], "-p", str(db["PORT"]), "-U", os.environ.get("SBH_DDL_USER", "postgres"),
         "-d", db["NAME"], "-v", "ON_ERROR_STOP=1", "-c", sql],
        check=True, capture_output=True, text=True,
        env={**os.environ, "PGPASSWORD": os.environ.get("SBH_DDL_PASSWORD", "postgres")},
    )


def send_scale(phases: list[tuple[bool, int, int | None]], slots: int, port: int, log: Path,
               wait_quiet: int) -> dict:
    """The product's Send at 40,000 bills, in PHASES, each ended by a SIGKILL.

    Each phase is `(index_on, cap, seconds)`: the line-id index present or
    dropped (DEF-BIL-8708 — dropped stands for the code before 2.424.0), the
    per-utility Send cap the fresh worker starts with, and how long the phase
    runs before its worker is SIGKILLed (None = to the end). Between phases
    NOTHING hands the Send back except the Send screen's own poll —
    `GET …/issue/progress`, every 2 s, exactly as `BulkRunPage.send()` polls —
    and the seconds from the kill to the poll answering `resumed: true` are
    recorded with the progress it read at that moment (never 0: it is counted
    from the bills). Load is recorded with every sample."""
    from apps.billing import api as billing_api
    from core import tenancy as core_tenancy

    _refuse()
    tenant, actor = _world()
    with core_tenancy.tenant_context(tenant.id):
        run = _run_a(tenant, actor)
        before = _issue_counts(run)
    api = _Api(tenant, getattr(actor, "user", actor))
    path = f"/api/{tenant.subdomain}/billing/runs/{run.pk}"
    out: dict = {"before": before, "quiet_wait": _wait_for_quiet(wait_quiet), "load_start": _load(),
                 "phases": []}
    redis = _redis(port)
    worker = None
    timeline: list = []
    t0 = time.perf_counter()
    job_id = None
    try:
        for number, (index_on, cap, seconds) in enumerate(phases, start=1):
            phase: dict = {"phase": number, "index": index_on, "cap": cap, "seconds_asked": seconds}
            _superuser_sql("CREATE INDEX IF NOT EXISTS ix_invoice_lines_id ON invoice_lines (id)" if index_on
                           else "DROP INDEX IF EXISTS ix_invoice_lines_id")
            os.environ["BILLING_SEND_BATCHES_PER_UTILITY"] = str(cap)
            worker = _worker(slots, log)
            # Wait for the worker to ANSWER on the billing queue: a POST made
            # before it does is told "no worker" and the product issues INLINE
            # in this process (run_jobs.would_run) — which happened once here,
            # 80 bills inline, before this wait existed.
            from apps.billing import run_jobs as _rj

            for _ in range(60):
                if _rj.would_run()[0]:
                    break
                time.sleep(2)
            else:
                out["refused"] = "the worker never answered on the billing queue"
                return out
            with core_tenancy.tenant_context(tenant.id):
                phase["start"] = {"s": round(time.perf_counter() - t0, 1), "load": _load(), **_issue_counts(run)}
            p0 = time.perf_counter()
            if job_id is None:
                code, body, _ = api.call(billing_api.run_issue, "POST", path + "/issue",
                                         {"issued_at": datetime.now(timezone.utc).isoformat(), "background": True},
                                         run_id=str(run.pk))
                phase["post"] = {"status": code, "job_id": body.get("job_id") if isinstance(body, dict) else body,
                                 "resumed": body.get("resumed") if isinstance(body, dict) else None}
                if code != 202:
                    out["refused"] = body
                    return out
                job_id = body["job_id"]
            until = None if seconds is None else p0 + seconds
            status = None
            while True:
                code, body, _ = api.call(billing_api.run_issue_progress, "GET", path + "/issue/progress",
                                         {"job": job_id}, run_id=str(run.pk))
                job = (body or {}).get("job") or {}
                status = job.get("status")
                now = round(time.perf_counter() - t0, 1)
                if job.get("resumed"):
                    phase["handed_back_by_the_poll"] = {"s_after_phase_start": round(time.perf_counter() - p0, 1),
                                                        "progress_read": job.get("progress")}
                if len(timeline) == 0 or now - timeline[-1][0] >= 10:
                    timeline.append((now, status, (job.get("progress") or {}).get("done"), _load()))
                if status in ("succeeded", "failed"):
                    break
                if until is not None and time.perf_counter() >= until:
                    break
                time.sleep(2)
            with core_tenancy.tenant_context(tenant.id):
                phase["end"] = {"s": round(time.perf_counter() - t0, 1), "load": _load(), "status": status,
                                **_issue_counts(run)}
            span = time.perf_counter() - p0
            issued = phase["end"]["issued"] - phase["start"]["issued"]
            loads = [row[3] for row in timeline if row[0] >= phase["start"]["s"]]
            phase.update({"seconds": round(span, 1), "issued_in_phase": issued,
                          "bills_per_second": round(issued / span, 2) if span else None,
                          "load_median": statistics.median(loads) if loads else None,
                          "load_max": max(loads) if loads else None})
            if status in ("succeeded", "failed"):
                _stop(worker)
                worker = None
                out["phases"].append(phase)
                break
            _stop(worker, signal.SIGKILL)
            worker = None
            phase["killed"] = True
            out["phases"].append(phase)
            # Written after every phase: a run that is itself killed keeps
            # what it measured (a session restart cost one whole run).
            Path(str(log) + ".partial.json").write_text(json.dumps(out, indent=2, default=str))
        out["ended"] = status
        out["seconds"] = round(time.perf_counter() - t0, 1)
        with core_tenancy.tenant_context(tenant.id):
            out["after"] = _issue_counts(run)
        code3, body3, _ = api.call(billing_api.run_issue, "POST", path + "/issue",
                                   {"issued_at": datetime.now(timezone.utc).isoformat(), "background": True},
                                   run_id=str(run.pk))
        time.sleep(5)
        with core_tenancy.tenant_context(tenant.id):
            out["second_send"] = {"status": code3,
                                  "created": body3.get("created") if isinstance(body3, dict) else None,
                                  "counts_after": _issue_counts(run)}
    finally:
        if worker is not None:
            _stop(worker)
        _superuser_sql("CREATE INDEX IF NOT EXISTS ix_invoice_lines_id ON invoice_lines (id)")
        if redis is not None:
            redis.terminate()
        out["load_end"] = _load()
        out["job"] = job_id
        out["timeline"] = timeline
    return out


# ── S4 · a second utility during a 40,000-account Check ────────────────────
def _b_run(subdomain: str):
    from apps.billing import models as bm
    from apps.billing import runs
    from apps.billing import template_models as tpl
    from apps.metering import derivation
    from apps.metering import models as mm
    from apps.tenancy import models as tm
    from core import tenancy as core_tenancy

    tenant = tm.Tenant.objects.get(subdomain=subdomain)
    with core_tenancy.tenant_context(tenant.id):
        best, size = None, 0
        for cycle in mm.Cycle.objects.all():
            n = len(derivation.units_in_cycle(cycle.id))
            if n > size:
                best, size = cycle, n
        run = bm.BillRun.objects.filter(cycle=best, period_start=SEPTEMBER[0], parent_run__isnull=True).first()
        if run is None:
            version = tpl.BillTemplateVersion.objects.filter(
                status=tpl.VERSION_PUBLISHED, template__template_type=tpl.TYPE_BILL).first()
            run = runs.create_run(cycle_id=best.id, period_start=SEPTEMBER[0], period_end=SEPTEMBER[1],
                                  bill_date=date(2026, 10, 1), due_days=21, label="September 2026 · S4 utility B",
                                  template_id=None if version is None else version.template_id)
    return tenant, run


def s4(slots: int, b_subdomain: str, start_b_at: int, port: int, log: Path) -> dict:
    from apps.billing import check_batches, check_models, run_jobs, runs
    from core import jobs as core_jobs
    from core import tenancy as core_tenancy

    _refuse()
    tenant_a, actor_a = _world()
    tenant_b, run_b = _b_run(b_subdomain)
    with core_tenancy.tenant_context(tenant_a.id):
        run_a = _run_a(tenant_a, actor_a)
        check_models.BillRunAccountCheck.objects.filter(bill_run=run_a).delete()
        scope_a = runs.scope_account_count(cycle_id=run_a.cycle_id, scope_services=None)
    with core_tenancy.tenant_context(tenant_b.id):
        check_models.BillRunAccountCheck.objects.filter(bill_run=run_b).delete()
        scope_b = runs.scope_account_count(cycle_id=run_b.cycle_id, scope_services=None)
    redis = _redis(port)
    worker = _worker(slots, log)
    out: dict = {"slots": slots, "cap_per_utility": check_batches.batch_cap(), "a_accounts": scope_a,
                 "b_accounts": scope_b, "b_tenant": b_subdomain, "load_start": _load()}
    events: list = []

    def state(tenant, coordinator):
        with core_tenancy.tenant_context(tenant.id):
            job = core_jobs.current(coordinator)
            active = core_jobs.active_records(check_batches.CHECK_BATCH_JOB)
        running = sum(1 for a in active if a["status"] == core_jobs.RUNNING)
        return job, running

    try:
        time.sleep(6)
        t0 = time.perf_counter()
        with core_tenancy.tenant_context(tenant_a.id):
            coord_a = run_jobs.enqueue_check(run_a)["id"]
        coord_b = None
        b_marks: dict = {}
        while True:
            time.sleep(1)
            now = time.perf_counter() - t0
            job_a, run_a_batches = state(tenant_a, coord_a)
            done_a = (job_a.get("progress") or {}).get("done") or 0
            if coord_b is None and done_a >= start_b_at:
                with core_tenancy.tenant_context(tenant_b.id):
                    coord_b = run_jobs.enqueue_check(run_b)["id"]
                tb = time.perf_counter()
                b_marks["pressed_at_s"] = round(now, 1)
                b_marks["a_when_pressed"] = {"done": done_a, "running_batches": run_a_batches}
            if coord_b is not None:
                job_b, run_b_batches = state(tenant_b, coord_b)
                since = round(time.perf_counter() - tb, 1)
                done_b = (job_b.get("progress") or {}).get("done") or 0
                if "b_running_s" not in b_marks and job_b["status"] != core_jobs.QUEUED:
                    b_marks["b_running_s"] = since
                    b_marks["a_when_b_started"] = {"done": done_a, "running_batches": run_a_batches}
                if "b_first_batch_s" not in b_marks and (run_b_batches or done_b):
                    b_marks["b_first_batch_s"] = since
                if "b_first_progress_s" not in b_marks and done_b:
                    b_marks["b_first_progress_s"] = since
                if "b_done_s" not in b_marks and job_b["status"] in (core_jobs.SUCCEEDED, core_jobs.FAILED):
                    b_marks["b_done_s"] = since
                    b_marks["b_status"] = job_b["status"]
                    b_marks["b_progress"] = job_b.get("progress")
                    b_marks["a_when_b_done"] = {"done": done_a, "running_batches": run_a_batches}
                events.append((round(now), done_a, run_a_batches, job_b["status"], done_b, run_b_batches, _load()))
            if job_a["status"] in (core_jobs.SUCCEEDED, core_jobs.FAILED) and (coord_b is None or "b_done_s" in b_marks):
                break
            if now > 3600:
                out["timeout"] = True
                break
        out.update({"a_status": job_a["status"], "a_seconds": round(time.perf_counter() - t0, 1),
                    "a_progress": job_a.get("progress"), **b_marks})
    finally:
        _stop(worker)
        if redis is not None:
            redis.terminate()
        out["load_end"] = _load()
        out["events"] = events[:: max(1, len(events) // 60)]
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    s2 = sub.add_parser("s2-server")
    s2.add_argument("--samples", type=int, default=5)
    for name in ("calculate", "send", "send-resume", "s4"):
        p = sub.add_parser(name)
        p.add_argument("--slots", type=int, default=4)
        p.add_argument("--redis-port", type=int, default=6397)
        if name == "send":
            p.add_argument("--kill-at", type=int, default=15000)
            p.add_argument("--wait-alone", type=int, default=120)
        if name == "send-resume":
            p.add_argument("--wait-alone", type=int, default=120)
            p.add_argument("--kill-after", type=int, default=0, help="SIGKILL the worker again this many seconds in")
        if name == "s4":
            p.add_argument("--b-subdomain", default="perf-utility-1")
            p.add_argument("--start-b-at", type=int, default=5000)
    sc = sub.add_parser("send-scale")
    sc.add_argument("--slots", type=int, default=4)
    sc.add_argument("--redis-port", type=int, default=6397)
    sc.add_argument("--wait-quiet", type=int, default=1800, help="wait up to S seconds for load < 2")
    sc.add_argument(
        "--phases",
        default="noindex:1:240,index:1:240,index:2:end",
        help="comma list of <index|noindex>:<cap>:<seconds|end>; each phase but the last ends in a SIGKILL",
    )
    sub.add_parser("sign-off")
    sub.add_parser("db-verify")
    args = parser.parse_args()
    slots = getattr(args, "slots", 4)
    port = getattr(args, "redis_port", None)
    _setup(slots, None if port is None else f"redis://127.0.0.1:{port}/0")
    log = Path(os.environ.get("TMPDIR", "/tmp")) / f"j73_scale_{args.cmd}.log"
    if args.cmd == "s2-server":
        result = s2_server(args.samples)
    elif args.cmd == "calculate":
        result = calculate(slots, port, log)
    elif args.cmd == "sign-off":
        result = sign_off()
    elif args.cmd == "send":
        result = send(args.kill_at, args.wait_alone, slots, port, log)
    elif args.cmd == "send-resume":
        result = send_resume(args.wait_alone, args.kill_after or None, slots, port, log)
    elif args.cmd == "db-verify":
        result = db_verify()
    elif args.cmd == "send-scale":
        phases = []
        for part in args.phases.split(","):
            index, cap, seconds = part.split(":")
            phases.append((index == "index", int(cap), None if seconds == "end" else int(seconds)))
        result = send_scale(phases, slots, port, log, args.wait_quiet)
    else:
        result = s4(slots, args.b_subdomain, args.start_b_at, port, log)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
