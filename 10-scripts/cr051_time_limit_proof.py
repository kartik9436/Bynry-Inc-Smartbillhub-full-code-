#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: CR-051 task 30's TIME bound, proved by running a REAL Celery
#            worker against a REAL broker and watching a task be stopped.
# Change:   CR-051 task 30 — *"State the largest run this deployment accepts
#           and what it does above it — no task time limit and no account cap
#           exist today."* The cap shipped 2026-08-31; this is the limit.
# Rules:    BR-BIL-1030 (a background job is bounded in time as well as in
#           size, and what it does at the limit is fail honestly) ·
#           CLAUDE.md hard-won law 7 (prove a guard RED before trusting green)
# Defects:  DEF-2829 (the CR counted task 30 done over its own caveat) ·
#           DEF-2806 (a hard-killed job stays `running` for ever)
# Tests:    the DETERMINISTIC half is
#           06-backend/tests/test_cr051_task30_time_limit.py (tc5, tc6, tc9,
#           tc10). This is the half a suite cannot host — see below.
# ───────────────────────────────────────────────────────
"""Run a real Celery worker with a tiny time limit and watch a task be stopped.

WHY THIS IS A SCRIPT AND NOT A TEST, and it is not a preference
---------------------------------------------------------------
A soft time limit is delivered by the WORKER POOL: Celery arms a timer in the
parent process and raises `SoftTimeLimitExceeded` inside the child that is
running the task. There is no worker in pytest, no broker, and no pool — so
there is nothing to arm the timer. `test_cr051_run_scale.py` records the same
disposition for the killed-worker proof and gives the same reason, and
`cr026_import_benchmark.py` is the standing precedent for a measurement that
is a script rather than a case.

WHAT IT PROVES, in two passes, and the second is the one that matters
--------------------------------------------------------------------
**PASS 1 — THE MECHANISM.** A job body that sleeps past the soft limit. The
worker stops it, `core.jobs.run_job` catches it on the ordinary failure path,
and the job RECORD reads `failed` with a sentence a clerk can read — not
`running`, not `queued`, and not `SoftTimeLimitExceeded: ` with nothing after
the colon. Its CHECKPOINT survives, so the next attempt resumes.

**PASS 2 — A REAL REGISTERED JOB, ON REAL BILLS.** The same limit against
`billing.bills.print_set` over a seeded utility's issued bills. This is the
pass that proves the per-bill `except Exception` in `print_set._add_one` does
not SWALLOW the limit and hold it as one broken bill — which it would have,
silently, before `core.jobs.reraise_if_time_limit` was called there.

**AND THE CONTROL.** Both passes are re-run with a generous limit and must
SUCCEED. A proof that only ever shows a failure cannot tell "the limit works"
from "the job is broken".

⚠ **ONE THING TO READ CAREFULLY IN PASS 2's OUTPUT.** The sentence on the
record says *"after about 4 seconds"* — the SETTING — while pass 2's limit came
from the worker flag (0.4 s). That is correct rather than a bug:
`core.jobs.time_limit_error_text` reads `CELERY_TASK_SOFT_TIME_LIMIT`, which is
what bounds a real deployment, and no deployment passes the flag. It is said
here so nobody reads the mismatch as the sentence being wrong.

THE SLEEPING JOB KIND IS NOT IN THE PRODUCT AND IT IS NOT LEFT BEHIND
---------------------------------------------------------------------
Pass 1 needs a job body the worker will run and that takes a known time. The
worker loads job handlers from each app's `AppConfig.ready()`, so the handler
has to be in an installed app — and adding a sleeping job kind to a billing
module to make a test pass is exactly the shape this repo keeps paying for.
Instead the script WRITES A THROWAWAY DJANGO APP into a temporary directory,
appends it to `INSTALLED_APPS` through a temporary settings module that
inherits everything else, and deletes both at the end. Nothing under
`06-backend/` is touched, before or after.

USAGE
    DATABASE_URL=postgres://…  python3 10-scripts/cr051_time_limit_proof.py
    python3 10-scripts/cr051_time_limit_proof.py --soft 4 --hard 30
    python3 10-scripts/cr051_time_limit_proof.py --skip-print-set

It starts `redis-server` if nothing is listening and stops only what it
started. It writes ONE job record per pass and deletes them in a `finally`.
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "06-backend"

BROKER_HOST, BROKER_PORT = "127.0.0.1", 6379
BROKER_URL = f"redis://{BROKER_HOST}:{BROKER_PORT}/9"

SLEEP_KIND = "proof.sleep"
BILLING_QUEUE = "billing"

PROOF_APP = '''"""A throwaway app that registers ONE job kind: a body that sleeps.

Written by 10-scripts/cr051_time_limit_proof.py into a temporary directory and
deleted with it. It exists because a Celery worker can only run a job kind some
installed app registered, and a sleeping job kind has no business living in a
billing module.
"""

import time

from django.apps import AppConfig


class ProofConfig(AppConfig):
    name = "proofsleep"

    def ready(self):
        from core import jobs as core_jobs

        def sleep_body(record):
            # It reports its place FIRST, exactly as a bill run does, so the
            # proof can check that the checkpoint survives the stop.
            core_jobs.record_progress(
                record["id"], done=9_000, total=10_000, checkpoint={"after": "ACC-9000"}
            )
            seconds = float((record.get("payload") or {}).get("seconds", 60))
            time.sleep(seconds)
            return None

        core_jobs.set_job_handler("proof.sleep", sleep_body)
        core_jobs.set_job_queue("proof.sleep", "billing")


default_app_config = "proofsleep.apps.ProofConfig"
'''

PROOF_SETTINGS = '''"""Local settings plus the throwaway proof app and the limits under test."""

from config.settings.local import *  # noqa: F401,F403

INSTALLED_APPS = list(INSTALLED_APPS) + ["proofsleep.apps.ProofConfig"]  # noqa: F405
'''


def say(line: str = "") -> None:
    print(line, flush=True)


def broker_is_up() -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.4)
        return probe.connect_ex((BROKER_HOST, BROKER_PORT)) == 0


def start_broker() -> subprocess.Popen | None:
    """Start redis only if nothing is listening. We stop only what we started."""
    if broker_is_up():
        say(f"broker: already listening on {BROKER_PORT} — using it, and leaving it alone")
        return None
    if shutil.which("redis-server") is None:
        raise SystemExit(
            "no redis-server on PATH and nothing listening on 6379. This proof needs a "
            "real broker: the soft time limit is armed by the worker pool, and there is "
            "no pool without a worker."
        )
    say(f"broker: starting redis-server on {BROKER_PORT}")
    proc = subprocess.Popen(
        ["redis-server", "--port", str(BROKER_PORT), "--save", "", "--appendonly", "no"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        if broker_is_up():
            return proc
        time.sleep(0.2)
    proc.terminate()
    raise SystemExit("redis-server did not come up")


def worker_env(scratch: Path, soft: int, hard: int, settings_module: str) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "DJANGO_SETTINGS_MODULE": settings_module,
            "PYTHONPATH": f"{scratch}{os.pathsep}{BACKEND}",
            "JOBS_EAGER": "false",
            "JOBS_REQUIRE_LIVE_WORKER": "false",
            "CELERY_BROKER_URL": BROKER_URL,
            # THE TWO SETTINGS UNDER TEST. They are read by
            # config/settings/base.py through env.int and handed to Celery by
            # config/celery.py's `namespace="CELERY"` — which is the wiring
            # tc3 in the suite asserts and this script exercises for real.
            "CELERY_TASK_SOFT_TIME_LIMIT": str(soft),
            "CELERY_TASK_TIME_LIMIT": str(hard),
        }
    )
    return env


def start_worker(
    scratch: Path,
    soft: int,
    hard: int,
    settings_module: str,
    log: Path,
    *,
    cli_soft: float | None = None,
):
    """Start a worker. `cli_soft` overrides the SETTING with a sub-second limit.

    ⚠ **WHY THE OVERRIDE EXISTS, SO NOBODY READS IT AS CHEATING.** The settings
    take whole seconds (`env.int`), and Celery's smallest useful limit is
    therefore one second — but a print set over a seeded utility's ninety-odd
    bills takes about **one second in total**, so a one-second limit is a coin
    toss rather than a proof. Pass 2 is not about the settings at all (pass 1
    proves those are wired); it is about whether the PER-BILL handler swallows
    the limit. Celery's own `--soft-time-limit` takes a float and arms the same
    timer in the same pool, so a sub-second value puts the exception squarely
    inside the loop under test and nothing else about the mechanism changes.
    """
    shown = f"{cli_soft}s (worker flag)" if cli_soft is not None else f"{soft}s"
    say(f"worker: starting  -Q {BILLING_QUEUE}  soft={shown}  hard={hard}s")
    handle = log.open("wb")
    limits = (
        ["--soft-time-limit", str(cli_soft), "--time-limit", str(hard)]
        if cli_soft is not None
        else []
    )
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "config",
            "worker",
            "-Q",
            f"{BILLING_QUEUE},celery",
            "--concurrency",
            "1",
            "--loglevel",
            "INFO",
            "--without-gossip",
            "--without-mingle",
            "--without-heartbeat",
            *limits,
        ],
        cwd=str(BACKEND),
        env=worker_env(scratch, soft, hard, settings_module),
        stdout=handle,
        stderr=subprocess.STDOUT,
    )
    deadline = time.time() + 90
    while time.time() < deadline:
        if proc.poll() is not None:
            say(log.read_text(errors="replace")[-2000:])
            raise SystemExit("the worker exited before it was ready")
        if "ready." in log.read_text(errors="replace"):
            say("worker: ready")
            return proc, handle
        time.sleep(0.5)
    proc.terminate()
    raise SystemExit("the worker never reported ready")


def stop(proc, handle=None) -> None:
    if proc is None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
    if handle is not None:
        handle.close()


def wait_for_settled(models, job_id, *, timeout: float):
    """Poll the RECORD, which is the truth (B12 r1). Returns the row.

    ⚠ **IT MUST BE CALLED INSIDE A TENANT CONTEXT.** `jobs` carries RLS FORCE,
    so a poll without one reads ZERO rows on a role that cannot bypass it — and
    an absent row reads exactly like a job that never started.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        row = models.Job.objects.filter(id=job_id).first()
        if row is not None and row.status in ("succeeded", "failed"):
            return row
        time.sleep(0.5)
    row = models.Job.objects.filter(id=job_id).first()
    if row is None:
        raise SystemExit(
            f"job {job_id} cannot be read back at all. Either the poll ran outside a "
            f"tenant context (RLS returns nothing and says nothing) or the row was "
            f"removed while this was running."
        )
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--soft", type=int, default=4, help="soft limit for the FAILING passes")
    ap.add_argument("--hard", type=int, default=30, help="hard limit for the FAILING passes")
    ap.add_argument("--sleep", type=float, default=45.0, help="how long the sleeping body sleeps")
    ap.add_argument(
        "--print-set-soft",
        type=float,
        default=0.4,
        help="soft limit for pass 2, as a worker flag — see start_worker",
    )
    ap.add_argument("--skip-print-set", action="store_true", help="run only the mechanism pass")
    args = ap.parse_args()

    scratch = Path(tempfile.mkdtemp(prefix="cr051-time-limit-"))
    app_dir = scratch / "proofsleep"
    app_dir.mkdir()
    (app_dir / "__init__.py").write_text("", encoding="utf-8")
    (app_dir / "apps.py").write_text(PROOF_APP, encoding="utf-8")
    (scratch / "proofsettings.py").write_text(PROOF_SETTINGS, encoding="utf-8")

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "proofsettings")
    os.environ["JOBS_EAGER"] = "false"
    os.environ["JOBS_REQUIRE_LIVE_WORKER"] = "false"
    os.environ["CELERY_BROKER_URL"] = BROKER_URL
    sys.path.insert(0, str(scratch))
    sys.path.insert(0, str(BACKEND))

    import django

    django.setup()

    from apps.billing import models as billing_models  # noqa: E402
    from apps.tenancy import models as tenancy_models  # noqa: E402
    from core import jobs as core_jobs  # noqa: E402
    from core import tenancy as core_tenancy  # noqa: E402

    broker = None
    worker = None
    handle = None
    tenant_id = None
    written: list[str] = []
    failures: list[str] = []
    try:
        broker = start_broker()

        # ⚠ THE INVOICE COUNT IS TAKEN INSIDE A TENANT CONTEXT, NOT OUTSIDE IT.
        # `invoices` carries RLS FORCE, so a query with no `app.tenant_id` set
        # returns ZERO rows on a role that cannot bypass it — and the script
        # would report "no bills" over a database full of them (`DEF-2717`'s
        # shape, the other way round).
        tenant_id, bills = None, 0
        for candidate in tenancy_models.Tenant.objects.values_list("id", flat=True):
            with core_tenancy.tenant_context(candidate):
                found = billing_models.Invoice.objects.filter(
                    status__in=("issued", "paid")
                ).count()
            if found > bills:
                tenant_id, bills = candidate, found
        if tenant_id is None:
            tenant_id = tenancy_models.Tenant.objects.values_list("id", flat=True).first()
        if tenant_id is None:
            raise SystemExit("no tenant in this database — point DATABASE_URL at a seeded one")
        say(f"tenant: {tenant_id}  ({bills} issued or paid bill(s))")

        # ── PASS 1 · THE MECHANISM ────────────────────────────────────────
        log = scratch / "worker-tight.log"
        worker, handle = start_worker(scratch, args.soft, args.hard, "proofsettings", log)
        with core_tenancy.tenant_context(tenant_id):
            # `enqueue` dispatches to the broker itself — the worker picks it up
            # from here, records its place, and then sleeps past the limit.
            record = core_jobs.enqueue(SLEEP_KIND, payload={"seconds": args.sleep})
            written.append(record["id"])
            settled = wait_for_settled(
                tenancy_models, record["id"], timeout=args.sleep + args.hard + 60
            )

        say()
        say("PASS 1 — a body that sleeps past the soft limit")
        say(f"    status     {settled.status}")
        say(f"    error      {settled.error}")
        say(f"    checkpoint {settled.checkpoint}")
        if settled.status != "failed":
            failures.append(
                f"PASS 1: the record reads {settled.status!r}. A run that hit the limit must "
                f"not go on claiming it is working."
            )
        if not (settled.error or "").startswith("This stopped"):
            failures.append(f"PASS 1: the record's sentence is {settled.error!r}")
        if settled.checkpoint != {"after": "ACC-9000"}:
            failures.append(
                f"PASS 1: the checkpoint is {settled.checkpoint!r} — the next attempt would "
                f"re-walk every account the stopped one already billed"
            )
        stop(worker, handle)
        worker = handle = None

        # ── PASS 1b · THE CONTROL ─────────────────────────────────────────
        log = scratch / "worker-roomy.log"
        worker, handle = start_worker(scratch, 600, 900, "proofsettings", log)
        with core_tenancy.tenant_context(tenant_id):
            record = core_jobs.enqueue(SLEEP_KIND, payload={"seconds": 1})
            written.append(record["id"])
            settled = wait_for_settled(tenancy_models, record["id"], timeout=120)
        say()
        say("PASS 1b — the control: the same body, inside a generous limit")
        say(f"    status     {settled.status}")
        if settled.status != "succeeded":
            failures.append(
                f"PASS 1b: the control read {settled.status!r} ({settled.error!r}). A proof that "
                f"only ever fails cannot tell a working limit from a broken job."
            )
        stop(worker, handle)
        worker = handle = None

        # ── PASS 2 · A REAL REGISTERED JOB, ON REAL BILLS ─────────────────
        if not args.skip_print_set:
            say()
            say(
                f"PASS 2 — the print set over {bills} real bills, "
                f"soft limit {args.print_set_soft}s"
            )
            log = scratch / "worker-printset.log"
            worker, handle = start_worker(
                scratch, args.soft, args.hard, "proofsettings", log, cli_soft=args.print_set_soft
            )
            from apps.billing import print_set  # noqa: E402
            import datetime  # noqa: E402

            with core_tenancy.tenant_context(tenant_id):
                record = print_set.enqueue_print_set(
                    filters={},
                    generated_at=datetime.datetime(2026, 9, 1, 9, 0, tzinfo=datetime.timezone.utc),
                    count=bills,
                )
                written.append(record["id"])
                # ⚠ **THE ENQUEUE IS SCOPE-KEYED, SO IT CAN HAND BACK SOMEBODY
                # ELSE'S RECORD.** That is the product working (hard rule 6): a
                # double-clicked *Build the print set* is one job. But a record
                # left `running` by an earlier killed worker is ALSO active, and
                # folding onto it dispatches nothing — the poll would then report
                # `running` for ever and read exactly like a swallowed limit.
                # Say so instead of measuring it.
                if record.get("status") != core_jobs.QUEUED:
                    raise SystemExit(
                        f"a print set for this selection is already {record['status']} "
                        f"(job {record['id']}). The scope key folded this request onto it "
                        f"and nothing was dispatched. Clear that record and run again."
                    )
                settled = wait_for_settled(tenancy_models, record["id"], timeout=180)
            say(f"    status     {settled.status}")
            say(f"    error      {settled.error}")
            if settled.status != "failed":
                failures.append(
                    f"PASS 2: the print set read {settled.status!r}. Either it finished inside "
                    f"{args.print_set_soft}s — lower --print-set-soft or use a tenant with more "
                    f"bills — or the per-bill handler swallowed the limit and held it as one "
                    f"broken bill, which is the defect this pass exists for."
                )
            elif not (settled.error or "").startswith("This stopped"):
                failures.append(f"PASS 2: the record's sentence is {settled.error!r}")
            if settled.status != "failed":
                # ⚠ THE WORKER'S OWN LOG IS THE ONLY PLACE THE ANSWER IS. A job
                # record that says `running` after the limit has passed can mean
                # the limit was swallowed, or that the worker was hard-killed
                # before it could write the row (`DEF-2806`) — and those are
                # different problems with different fixes. Printing the tail
                # here is what tells them apart.
                stop(worker, handle)
                worker = handle = None
                say("    --- the worker's own log, last 40 lines ---")
                for line in log.read_text(errors="replace").splitlines()[-40:]:
                    say(f"    | {line}")
            stop(worker, handle)
            worker = handle = None

        say()
        if failures:
            for line in failures:
                say(f"FAIL  {line}")
            return 1
        say("PASS — a job that runs out of time is stopped, says so, and keeps its place.")
        return 0
    finally:
        stop(worker, handle)
        if written and tenant_id is not None:
            # ⚠ **INSIDE THE TENANT CONTEXT, AND THAT IS NOT A DETAIL.** `jobs`
            # carries RLS FORCE, so this DELETE outside one matches ZERO rows on
            # a role that cannot bypass it — and says nothing. The first draft of
            # this script did exactly that: a `running` print-set record from a
            # killed worker survived every run's cleanup, and because
            # `enqueue_print_set` is SCOPE-KEYED every later run folded onto that
            # dead record, dispatched nothing, and reported `running` for ever.
            # The proof looked broken and the product was fine. CLAUDE.md law 14's
            # neighbour: what SQLite cannot show you, PostgreSQL will.
            with core_tenancy.tenant_context(tenant_id):
                removed, _ = tenancy_models.Job.objects.filter(id__in=written).delete()
            say(f"cleanup: removed {removed} job record(s)")
        stop(broker)
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-051 task 30 (12-governance/11-change-requests.md) + BR-BIL-1030
#         (04-docs/05-modules/07-billing/02-business-rules.md) + DEF-2829
# generated: 2026-09-01 by the CR-051 task 30 / CR-053 task 14 lane
# checklist: A✔ B=n/a C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: (1) IT WRITES A THROWAWAY DJANGO APP AT RUNTIME. A worker only
#         runs a kind an installed app registered, and a sleeping job kind does
#         not belong in a billing module. Both the app and its settings module
#         live in a temp directory and are deleted in the `finally`.
#         (2) IT WRITES JOB ROWS AND DELETES THEM. Unlike
#         cr051_run_benchmark.py this cannot run inside a rolled-back
#         transaction: the whole point is that another process reads what this
#         one COMMITTED.
#         (3) IT STOPS ONLY THE REDIS IT STARTED, and uses database 9 so it
#         cannot disturb a broker somebody else is using.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
