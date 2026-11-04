#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: the THREE-PROCESS proof that billing's named queue is really split —
#            a real Redis, a real default worker, a real billing worker.
# Change:   CR-051 task 29 (PO ruling 2026-08-31), verbatim: *"we will ahve to
#           create named worker for billing - eventually we should able to scale
#           these works on the fly itf required; but billing will need its own
#           named workers - otherwise it will slow down the system"*
# Defect:   DEF-320 (a queue nothing consumes: every 202 rested `queued` for ever)
# Rules:    CLAUDE.md hard-won law 2 (built is not wired) · law 7 (prove it goes
#           RED) · DEF-182 (a check that cannot distinguish pass from fail)
# ───────────────────────────────────────────────────────
"""Is the split REAL, or only true in a settings file? Ask a broker.

WHY THIS IS A SCRIPT AND NOT A PYTEST TEST — the same argument
`10-scripts/verify_celery_transport.py` makes, and it applies twice as hard here.
`06-backend/tests/test_cr051_billing_queue.py` proves the routing DECISION (it
asks Celery's own `app.amqp.router`, which is what `.delay()` asks) and reads the
consumer out of `docker-compose.yml`. **Neither of those is a message in a
broker.** The thing this change claims is about three processes: a web process
that enqueues, a default worker that must LEAVE the message alone, and a billing
worker that must take it. A test that could prove that would have to start a
broker and fork two workers, and a suite that does that is a suite people switch
off.

WHAT IT DOES, and each step answers exactly one question:

  1. enqueue a `billing.run.calculate` job with `JOBS_EAGER=false`, so it goes to
     the broker rather than running in-process;
  2. **`LLEN billing` == 1 and `LLEN celery` == 0** — the ROUTING half. With
     Redis as the broker a Celery queue IS a Redis list of that name, so this is
     the message itself and not a claim about it;
  3. run a **default** worker (`-Q celery`) for a while and check `LLEN billing`
     is STILL 1 — **the half that is easiest to leave out and impossible to see
     afterwards.** If the default worker drains billing the split is cosmetic:
     every job still completes, every test still passes, and the CPU limit bounds
     nothing because an uncapped worker is picking the runs up too;
  4. run a **billing** worker (`-Q billing`) and check the list empties and the
     job record leaves `queued`.

**WHAT COUNTS AS A PASS IN STEP 4, stated so a red herring does not read as a
failure.** The job record is deliberately given a `run_id` that does not exist,
so the body raises and the record ends `failed`. That is a PASS, for the reason
`verify_celery_transport.py` already gives in its own words: *"a record that reads
`failed: <a named error>` answers it as completely as `succeeded` does — the
worker took the message, entered the tenant, loaded the body and ran it.
`queued` is the ONLY failing outcome, because `queued` is what DEF-320 was."*
Using a real bill run here would prove nothing more about the QUEUE and would
make the script a bill-run test.

USAGE
    redis-server --daemonize yes --port 6399 --save "" --appendonly no
    DATABASE_URL=postgres://…/sbh_cr051perf \\
      python3 10-scripts/verify_billing_queue_split.py

It exits non-zero the moment any of the four steps fails, and prints one line per
step saying what it saw rather than only whether it liked it.
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

#: A broker of this run's own, on a port nothing else here uses. Two lanes
#: sharing one Redis would let a sibling's worker drain these messages and report
#: a false green — the same reason `verify_celery_transport.py` gives its worker a
#: unique node name.
BROKER = os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6399/0")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
# ⚠ THE WHOLE POINT. Eager dispatch would run the body in this process and prove
# nothing about any queue; this is production's own setting.
os.environ["JOBS_EAGER"] = "false"
# The probe would refuse the enqueue for want of a live worker, and at this point
# in the script there deliberately is none — that is step 3's whole subject.
os.environ["JOBS_REQUIRE_LIVE_WORKER"] = "false"

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402

settings.DEBUG = False

from apps.billing import run_jobs  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import jobs as core_jobs  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

DEFAULT_QUEUE = settings.CELERY_TASK_DEFAULT_QUEUE
BILLING_QUEUE = run_jobs.BILLING_QUEUE
DRAIN_SECONDS = 12
CONSUME_SECONDS = 25


def _redis():
    import redis  # a Celery dependency; imported here so the module loads without it

    return redis.Redis.from_url(BROKER)


def _depth(client, queue: str) -> int:
    return int(client.llen(queue))


def _worker(queues: str, name: str, log: Path) -> subprocess.Popen:
    handle = log.open("wb")
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "config.celery",
            "worker",
            "-Q",
            queues,
            "--loglevel",
            "info",
            "--concurrency",
            "1",
            "-n",
            f"{name}-{uuid.uuid4().hex[:6]}@%h",
        ],
        cwd=str(BACKEND),
        env={**os.environ},
        stdout=handle,
        stderr=subprocess.STDOUT,
    )


def main() -> int:
    client = _redis()
    try:
        client.ping()
    except Exception as problem:  # noqa: BLE001
        print(f"no broker at {BROKER}: {problem}")
        print('start one:  redis-server --daemonize yes --port 6399 --save "" --appendonly no')
        return 2
    client.delete(DEFAULT_QUEUE, BILLING_QUEUE)

    tenant = tenancy_models.Tenant.objects.order_by("created_at").first()
    if tenant is None:
        return 2 if print("no tenant on this database") else 2

    failures: list[str] = []

    # ── 1 · enqueue, under production dispatch ─────────────────────────────
    with core_tenancy.tenant_context(str(tenant.id)):
        record = core_jobs.enqueue(
            run_jobs.CALCULATE_JOB,
            payload={"run_id": str(uuid.uuid4()), "actor_user_id": None},
            scope_key=f"verify:split:{uuid.uuid4()}",
        )
    print(f"1 · enqueued {record['kind']} as {record['id']} for {tenant.subdomain}")

    # ── 2 · the ROUTING half: which Redis list is the message in? ──────────
    billing_depth, default_depth = _depth(client, BILLING_QUEUE), _depth(client, DEFAULT_QUEUE)
    print(
        f"2 · broker depth — {BILLING_QUEUE!r}: {billing_depth} · {DEFAULT_QUEUE!r}: {default_depth}"
    )
    if billing_depth != 1 or default_depth != 0:
        failures.append(
            f"the message is not on the {BILLING_QUEUE!r} queue "
            f"({BILLING_QUEUE}={billing_depth}, {DEFAULT_QUEUE}={default_depth}) — the "
            "routing half is missing, so the billing worker idles and its CPU cap "
            "applies to nothing"
        )

    # ── 3 · the DEFAULT worker must LEAVE IT ALONE ─────────────────────────
    log = Path("/tmp/verify-split-default.log")
    default_worker = _worker(DEFAULT_QUEUE, "default", log)
    time.sleep(DRAIN_SECONDS)
    after_default = _depth(client, BILLING_QUEUE)
    alive = default_worker.poll() is None
    default_worker.terminate()
    try:
        default_worker.wait(timeout=15)
    except subprocess.TimeoutExpired:
        default_worker.kill()
    print(
        f"3 · after {DRAIN_SECONDS}s of a `-Q {DEFAULT_QUEUE}` worker "
        f"(running: {alive}), {BILLING_QUEUE!r} depth is {after_default} · log {log}"
    )
    if not alive:
        failures.append(f"the default worker died — read {log}")
    if after_default != 1:
        failures.append(
            f"the default worker DRAINED the {BILLING_QUEUE!r} queue (depth "
            f"{after_default}) — the split is cosmetic: every job still completes "
            "and the CPU limit bounds nothing, because an uncapped worker is "
            "picking the runs up too"
        )

    # ── 4 · the BILLING worker must take it ────────────────────────────────
    log = Path("/tmp/verify-split-billing.log")
    billing_worker = _worker(BILLING_QUEUE, "billing", log)
    deadline, status = time.time() + CONSUME_SECONDS, "queued"
    while time.time() < deadline:
        with core_tenancy.tenant_context(str(tenant.id)):
            row = tenancy_models.Job.objects.filter(id=record["id"]).first()
        status = row.status if row is not None else "MISSING"
        if status in ("succeeded", "failed"):
            break
        time.sleep(1.0)
    after_billing = _depth(client, BILLING_QUEUE)
    billing_worker.terminate()
    try:
        billing_worker.wait(timeout=15)
    except subprocess.TimeoutExpired:
        billing_worker.kill()
    print(
        f"4 · after a `-Q {BILLING_QUEUE}` worker, {BILLING_QUEUE!r} depth is "
        f"{after_billing} and the record reads {status!r} · log {log}"
    )
    if after_billing != 0 or status == "queued":
        failures.append(
            f"the billing worker did not consume the message (depth {after_billing}, "
            f"record {status!r}) — that is DEF-320: it accepts the file, says "
            "'queued', and writes nothing, for ever"
        )

    client.delete(DEFAULT_QUEUE, BILLING_QUEUE)
    if failures:
        print("\nFAIL:")
        for one in failures:
            print(f"  · {one}")
        return 1
    print(
        "\nPASS — the message was ROUTED to the billing queue, the default worker "
        "LEFT IT THERE, and the billing worker CONSUMED it. Three processes, one "
        "broker, no simulation."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
