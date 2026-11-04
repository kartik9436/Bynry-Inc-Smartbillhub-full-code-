# ── Trace ──────────────────────────────────────────────
# Component: BE-07 jobs framework — THE CELERY TRANSPORT (TD-17's worker half)
# Change:   PO ruling 2026-08-19, verbatim: *"We want Async job install redis
#           and celery; Trigger after tenant creation; also add these two
#           services in docker compose"* (12-governance/02-decision-log.md)
# Defect:   DEF-320 (four job kinds enqueue and production dispatched none of
#           them, so every 202 rested `queued` forever) · DEF-326 (the bulk
#           rate change answered 202 and never applied a price)
# Contract: TD-17 (async = Celery on Redis) · B12 r1 §3 (202 + job_id, poll
#           /jobs/{id}) · NFR-16 (idempotent + resumable) · B3 (a worker sets
#           tenant context EXPLICITLY, never ambiently)
# Rules:    BR-TEN-063 (the plant's failure never rolls back a tenant — which is
#           why the enqueue is after the commit and this task is what picks it up)
# Tests:    06-backend/tests/test_cr017_celery_transport.py
# Impacts:  apps/tenancy/services.dispatch_job (the registered dispatcher) ·
#           docker-compose.yml (the `celery` service runs this) · core/jobs.py
#           (unchanged: enqueue → dispatcher → run_pending → run_job)
# ───────────────────────────────────────────────────────
"""ONE task for EVERY job kind, because the record already says which kind it is.

WHY ONE TASK AND NOT ONE PER KIND. `core.jobs.run_pending(job_id)` loads the
record, reads its `kind`, and looks the BODY up in the handler registry that
each owning module fills in its own `AppConfig.ready()`. So the broker never
needs to know what a job does — it needs to know that a job exists. A task per
kind would duplicate that registry in a second place, in a process that imports
every app anyway, and the two would drift the first time a kind was added and
its task was not.

⚠ THE TENANT TRAVELS IN THE MESSAGE, AND IT HAS TO (B3, and RLS FORCE).
`run_job` enters tenant context from the record — but it has to LOAD the record
first, and on Postgres `jobs` carries RLS FORCE, so a worker with no
`app.tenant_id` set reads ZERO rows and the load fails with "unknown job". In
eager dispatch this never bit, because the caller is mid-request and already in
context; `core/jobs.py`'s own lifecycle trailer has carried that warning as a
REPORTED gap for the worker lane since 2026-08-10, and this is that lane. The
dispatcher therefore sends `tenant_id` beside `job_id` and the task enters the
context before anything touches the database.

**The tenant id is not trusted input** — it is written by `enqueue()` from
`current_tenant_id()` at the moment the record was created, travels only between
our own dispatcher and our own worker, and the record's own `tenant_id` is what
`run_job` re-enters with for the body itself. A message naming the wrong tenant
would read a `jobs` row that RLS does not admit and fail loudly, which is the
correct outcome and is asserted in the tests.

WHAT A FAILURE LOOKS LIKE. `run_job` marks the record `failed` with the error
and re-raises, so Celery's own retry policy sees it and the poll endpoint tells
the client the truth either way. `CELERY_TASK_ACKS_LATE` is on (base.py), so a
worker killed mid-job re-delivers the message; every job body owes idempotence
and a checkpoint for exactly that (NFR-16/TD-17), and the sample plant is
scope-keyed so a re-delivery folds into the same record rather than seeding a
second copy.
"""

from __future__ import annotations

import logging
from typing import Any

from config.celery import app
from core import jobs as core_jobs
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.jobs")

#: The routing name. Pinned as a literal rather than derived from the module
#: path so a file move cannot silently orphan every message already in the
#: queue — a renamed task is a message nobody consumes, and the queue says
#: nothing about it.
RUN_PENDING_TASK = "smartbillhub.jobs.run_pending"


@app.task(name=RUN_PENDING_TASK, bind=False)
def run_pending_job(job_id: str, tenant_id: str, kind: str | None = None) -> None:
    """Run one queued BE-07 job, under its own tenant's context.

    Returns nothing: the RECORD is the truth (B12 r1), and a return value would
    be a second place for a client to look.

    ⚠ **`kind` IS FOR ROUTING AND IS NOT READ HERE (CR-051 task 29).** It exists
    so `config.celery_routes.route_job` can tell a bill run from a CSV export
    while both are riding the same task, and the body deliberately ignores it:
    `run_pending` reads the kind from the RECORD, which is the truth. It
    defaults to None so that a message enqueued before the split — one already
    sitting in the broker during a deploy — still runs.
    """
    with core_tenancy.tenant_context(tenant_id):
        logger.info("celery: running job %s for tenant %s", job_id, tenant_id)
        # ⚠ **`resume`, NOT `run_pending` — CR-105-BRC03, and the one hop that
        # made every checkpoint in this product dead weight.** A first delivery
        # takes the identical path (`resume` on a `queued` record is
        # `run_pending`). A REDELIVERY is the case this line exists for: the
        # module docstring above already promises *"a worker killed mid-job
        # re-delivers the message; every job body owes idempotence and a
        # checkpoint for exactly that"*, and until today the redelivery reached
        # `start()`, found a record still saying `running` — because a killed
        # process writes no failure — and raised *"cannot start (resume is
        # failed→running)"*. The message was consumed, the record stayed
        # `running` for ever, and the checkpoint was read by nothing.
        # `core.jobs.reclaim` states the promise this call makes; the broker's
        # `visibility_timeout` in `config/settings/base.py` is what keeps it.
        core_jobs.resume(job_id)


def send(record: dict[str, Any]) -> None:
    """Hand one job record to the broker. Called by the registered dispatcher.

    It NEVER raises into the caller. `enqueue()` has already saved the record,
    and the API layer is about to answer 202 with its poll URL: a broker that is
    down must leave a `queued` record a later worker or a repair run can pick
    up, not a 500 over work that is already recorded. The failure is logged with
    the job id so it is findable, and the poll endpoint keeps telling the client
    `queued`, which is exactly what is true.
    """
    try:
        # ⚠ THE KIND IS PASSED AS A KEYWORD AND THAT IS LOAD-BEARING (CR-051 task
        # 29). `config.celery_routes.route_job` reads it out of the message's
        # kwargs to choose the queue; passed positionally it would still reach
        # the body and the router would see an empty `kwargs` — so every bill
        # run would quietly ride the default queue, the billing worker would sit
        # idle, and its CPU cap would apply to nothing. Nothing would fail.
        run_pending_job.delay(
            str(record["id"]), str(record["tenant_id"]), kind=str(record.get("kind") or "")
        )
    except Exception:  # noqa: BLE001 — a queued record is the honest outcome
        logger.exception(
            "celery: could not dispatch job %s (%s) — the record stays queued and "
            "is picked up by the next worker that sees it, or by "
            "`manage.py run_pending_jobs`",
            record.get("id"),
            record.get("kind"),
        )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-017 async-jobs slice (PO ruling 2026-08-19) + BE-07@05736ee
# generated: 2026-08-19 by story-coder (CR-017 Redis/Celery lane)
# checklist: A✔ B=deferred(no-API-half — this is TRANSPORT: it adds no endpoint, and the one endpoint involved, GET /api/jobs/{id}, already exists and is unchanged) C✔ D=deferred(no-API-half, as above) E=deferred(no-frontend-half — the CR-017 screen polls the job RECORD, so which process ran the body is invisible to it and nothing on a screen changes) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the test module's trailer
# exceptions: `tenant_task_class()` in core/jobs.py is NOT used — it builds a Task base whose `run` receives the RECORD, which suits a task-per-kind design. This transport is kind-agnostic on purpose (see the docstring), so it calls `run_pending` directly and enters context itself. The helper is left in place because it is a published kernel contract and a later per-kind task may want it; that it now has no caller is REPORTED here rather than deleted from a kernel this lane does not own · celery BEAT is deliberately not configured: 09-infra lists it as decided for partition archival, report retention and dispatcher pacing, all with a run-exactly-once constraint, and the PO named two services. Raised in the decision log, not built by inference
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
