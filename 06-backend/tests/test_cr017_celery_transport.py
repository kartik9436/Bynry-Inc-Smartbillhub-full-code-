# ── Trace ──────────────────────────────────────────────
# Component: BE-07 jobs framework — the Celery transport (apps/tenancy/tasks.py)
#            and the dispatcher that now reaches it (apps/tenancy/services.dispatch_job)
# Change:   PO ruling 2026-08-19 — *"We want Async job install redis and celery;
#           Trigger after tenant creation; also add these two services in docker
#           compose"*, and its addendum *"we need Beat ; include it"*
# Defect:   DEF-320 (four job kinds enqueued and production dispatched none of
#           them — every 202 rested `queued` forever) · DEF-326 (the bulk rate
#           change answered 202 and applied no price)
# Rules:    B3 (a worker sets tenant context EXPLICITLY) · B12 r1 §3 (202 +
#           job_id, the RECORD is the truth) · NFR-16 (idempotent + resumable)
# ───────────────────────────────────────────────────────
"""What one process can prove about a three-process transport, and what it cannot.

**It cannot prove that a worker consumes the queue** — that needs a broker and a
second process, and it is proved by `10-scripts/verify_celery_transport.py`,
which runs a real `celery worker` against a real Redis under `JOBS_EAGER=false`
and asserts all four job kinds leave `queued`. Read that script's docstring for
why it is not a pytest test.

**It can prove the four things that made DEF-320 possible in the first place**,
and each of these is a place the wiring could silently go back to doing nothing:

1. the dispatcher on the NON-eager branch actually sends something (it used to
   be a comment describing a worker that did not exist);
2. the message carries the TENANT, because `run_job` has to load the record
   before it can read the tenant off it, and `jobs` carries RLS FORCE — a worker
   with no `app.tenant_id` reads zero rows;
3. a broker that is down leaves a `queued` record and does NOT raise into the
   caller, because `enqueue` has already saved the record and the endpoint is
   about to answer 202 over work that is genuinely recorded;
4. eager dispatch is untouched, so every existing test keeps its shape.
"""

import uuid

import pytest
from django.test import override_settings

from apps.tenancy import services as tenancy_services
from apps.tenancy import tasks as tenancy_tasks
from core import jobs as core_jobs
from core import tenancy as core_tenancy

from tests.test_us_idn_helpers import idn  # noqa: F401 (fixture import)

pytestmark = pytest.mark.django_db


@pytest.fixture()
def live_store():
    previous = core_jobs._store
    core_jobs.set_job_store(tenancy_services.JobStore())
    yield
    core_jobs.set_job_store(previous)


@pytest.fixture()
def dispatcher():
    previous = core_jobs._dispatcher
    core_jobs.set_job_dispatcher(tenancy_services.dispatch_job)
    yield
    core_jobs.set_job_dispatcher(previous)


# ── 1 · the non-eager branch reaches the broker ─────────────────────────────
@override_settings(JOBS_EAGER=False)
def test_cr017_tc1__production_dispatch_hands_the_job_to_celery(
    idn, live_store, dispatcher, monkeypatch
):
    """RED-PROVED: restoring `dispatch_job`'s old body — `if JOBS_EAGER: run_eager`
    and nothing else — leaves `sent` empty and this fails with
    `AssertionError: nothing was dispatched`. That empty list IS DEF-320: four
    job kinds, a 202 each, and no consumer."""
    idn.seed_silvercreek()
    sent: list[tuple] = []
    # ⚠ `**kwargs` ADDED 2026-08-31 (CR-051 task 29). `send()` now passes the
    # job KIND as a keyword so `config.celery_routes.route_job` can pick the
    # queue. A `lambda *args` fake raises TypeError on it, `send()` swallows
    # every exception by design, and this test would fail with the DEF-320
    # message over a transport that is working perfectly. The positional pair
    # below is unchanged, which is the point of recording only `args`.
    monkeypatch.setattr(
        tenancy_tasks.run_pending_job, "delay", lambda *args, **kwargs: sent.append(args)
    )

    with core_tenancy.tenant_context(idn.silvercreek.id):
        record = core_jobs.enqueue("audit_export", payload={"filters": {}})

    assert sent, "nothing was dispatched — the queue has no consumer (DEF-320)"
    assert len(sent) == 1, "one enqueue is one message, never two"
    job_id, tenant_id = sent[0]
    assert job_id == str(record["id"])
    # The record must still be QUEUED here: the broker has the message and no
    # worker has run in this process. A `succeeded` record would mean the body
    # ran inside the web request, which is the thing JOBS_EAGER=False turns off.
    assert record["status"] == core_jobs.QUEUED


# ── 2 · the tenant travels in the message (B3, and RLS FORCE) ───────────────
@override_settings(JOBS_EAGER=False)
def test_cr017_tc2__the_message_carries_the_tenant_so_the_worker_can_load_the_record(
    idn, live_store, dispatcher, monkeypatch
):
    """`run_job` reads the tenant OFF the record — so something has to make the
    record readable first. On Postgres `jobs` is RLS FORCE, and a worker with no
    `app.tenant_id` set reads zero rows and fails with "unknown job". core/jobs.py's
    own trailer has carried this as a reported gap for the worker lane since
    2026-08-10.

    RED-PROVED: dropping `tenant_id` from `send()` fails here with a TypeError on
    the task's second argument, and dropping the `tenant_context` from
    `run_pending_job` fails TC-3 below."""
    idn.seed_silvercreek()
    sent: list[tuple] = []
    # ⚠ `**kwargs` ADDED 2026-08-31 (CR-051 task 29). `send()` now passes the
    # job KIND as a keyword so `config.celery_routes.route_job` can pick the
    # queue. A `lambda *args` fake raises TypeError on it, `send()` swallows
    # every exception by design, and this test would fail with the DEF-320
    # message over a transport that is working perfectly. The positional pair
    # below is unchanged, which is the point of recording only `args`.
    monkeypatch.setattr(
        tenancy_tasks.run_pending_job, "delay", lambda *args, **kwargs: sent.append(args)
    )

    with core_tenancy.tenant_context(idn.silvercreek.id):
        core_jobs.enqueue("audit_export", payload={"filters": {}})

    _job_id, tenant_id = sent[0]
    assert tenant_id == str(idn.silvercreek.id)
    assert uuid.UUID(tenant_id)  # a real uuid, not a repr of one


# ── 3 · the task body enters that tenant's context BEFORE loading ──────────
def test_cr017_tc3__the_task_enters_the_tenant_before_it_touches_the_database(
    idn, live_store, monkeypatch
):
    """The task is called with NO ambient context — exactly as a worker is.

    ⚠ **THE ASSERTION IS ON THE CONTEXT AT THE MOMENT `run_pending` IS CALLED,
    and it has to be.** The obvious version of this test — run the job and check
    the body saw the right tenant — is VACUOUS on this tier, and that was proved
    rather than assumed: deleting the `tenant_context` from `run_pending_job`
    left it GREEN. On sqlite there is no RLS, `JobStore.get` carries no tenant
    filter by design (its docstring says RLS is what keeps it honest), and
    `run_job` then enters the context from the record it just loaded. So the
    body sees the right tenant either way and the check cannot tell the two
    apart. What it CAN see, on every tier, is whether the context was already
    set when the load began — which is the whole property, because on Postgres
    that load is the one RLS refuses.

    RED-PROVED: removing the `with core_tenancy.tenant_context(...)` from
    `run_pending_job` fails here with `at_load == None`."""
    idn.seed_silvercreek()
    with core_tenancy.tenant_context(idn.silvercreek.id):
        record = core_jobs.enqueue("cr017.probe", payload={})

    at_load: list = []
    real_run_pending = core_jobs.run_pending

    def watched(job_id):
        at_load.append(core_tenancy.current_tenant_id())
        return real_run_pending(job_id)

    monkeypatch.setattr(tenancy_tasks.core_jobs, "run_pending", watched)

    seen: list = []
    core_jobs.set_job_handler(
        "cr017.probe", lambda r: seen.append(core_tenancy.current_tenant_id())
    )
    try:
        core_tenancy.clear_current_tenant()
        assert core_tenancy.current_tenant_id() is None, "the worker starts with no tenant"
        tenancy_tasks.run_pending_job(str(record["id"]), str(idn.silvercreek.id))
    finally:
        core_jobs.set_job_handler("cr017.probe", None)

    assert at_load == [idn.silvercreek.id], (
        "the record was loaded with NO app.tenant_id set — on Postgres RLS FORCE "
        "returns zero rows there and every worker-run job fails as 'unknown job'"
    )
    assert seen == [idn.silvercreek.id], "the body ran under the record's own tenant (B3)"
    with core_tenancy.tenant_context(idn.silvercreek.id):
        assert core_jobs._store.get(record["id"])["status"] == core_jobs.SUCCEEDED
    # …and it left no context behind for the next task on this worker (B3).
    assert core_tenancy.current_tenant_id() is None


# ── 4 · a broker that is down leaves a queued record, never a 500 ───────────
@override_settings(JOBS_EAGER=False)
def test_cr017_tc4__a_dead_broker_leaves_the_record_queued_and_does_not_raise(
    idn, live_store, dispatcher, monkeypatch
):
    """`enqueue` has already SAVED the record when the dispatcher runs, and the
    endpoint is about to answer 202 with its poll URL. A 500 there would discard
    a promise over work that is genuinely recorded; a `queued` record is the
    truth and a later worker or repair run picks it up."""
    idn.seed_silvercreek()

    def dead(*_args, **_kwargs):  # **kwargs: CR-051 task 29 passes `kind=`
        raise OSError("Error 111 connecting to redis:6379. Connection refused.")

    monkeypatch.setattr(tenancy_tasks.run_pending_job, "delay", dead)

    with core_tenancy.tenant_context(idn.silvercreek.id):
        record = core_jobs.enqueue("audit_export", payload={"filters": {}})
        stored = core_jobs._store.get(record["id"])

    assert stored["status"] == core_jobs.QUEUED
    assert stored["error"] is None, "a transport failure is not the JOB's failure"


# ── 5 · eager dispatch is untouched ────────────────────────────────────────
@override_settings(JOBS_EAGER=True)
def test_cr017_tc5__eager_dispatch_still_runs_the_body_in_process(idn, live_store, dispatcher):
    """Local, dev, demo and every test that turns JOBS_EAGER on keep their shape:
    the body runs at dispatch and the record is terminal when enqueue returns.
    If this ever went the other way, a hundred existing tests would need rewriting
    and the CR-017 walkthrough would stop finishing inside its own request."""
    idn.seed_silvercreek()
    ran: list = []
    core_jobs.set_job_handler("cr017.probe", lambda record: ran.append(record["id"]) or None)
    try:
        with core_tenancy.tenant_context(idn.silvercreek.id):
            record = core_jobs.enqueue("cr017.probe", payload={})
            assert core_jobs._store.get(record["id"])["status"] == core_jobs.SUCCEEDED
    finally:
        core_jobs.set_job_handler("cr017.probe", None)
    assert ran == [record["id"]]


# ── 6 · the transport is kind-agnostic, which is why it covers all four ────
def test_cr017_tc6__one_task_serves_every_registered_kind(idn):
    """DEF-320 was four kinds, not one. The task takes a job id and asks the
    registry what to run, so a kind added tomorrow is dispatched by the same
    message with no new task and no new compose service.

    This asserts the four kinds the PO was shown are all REGISTERED — a kind
    with an enqueue and no handler is a record no worker can run, which is a
    different way to arrive at the same silence."""
    from apps.audit import services as audit_services
    from apps.rating import services as rating_services
    from apps.tenancy import exports as tenancy_exports
    from apps.tenancy import sample_data as tenancy_sample_data

    for kind in (
        tenancy_sample_data.PLANT_JOB_KIND,
        rating_services.RATE_CHANGE_JOB,
        audit_services.EXPORT_JOB,
        tenancy_exports.LIST_EXPORT_JOB,
    ):
        assert core_jobs.job_handler(kind) is not None, f"{kind} has no registered body"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-017 async-jobs slice (PO ruling 2026-08-19) + BE-07@05736ee
# generated: 2026-08-19 by story-coder (CR-017 Redis/Celery lane)
# checklist: A✔ B=deferred(no-API-half — the module under test is transport, not an endpoint) C✔ D=deferred(no-API-half, as above) E=deferred(no-frontend-half — nothing on a screen changes) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/test_cr017_celery_transport.py — result quoted in the lane report · the three-process proof is 10-scripts/verify_celery_transport.py, which ran a live `celery -A config.celery worker` against a live Redis under JOBS_EAGER=false and left all FOUR kinds `succeeded` (the sample plant with progress 10/10, which is what the CR-017 screen polls)
# exceptions: TC-1/2/4 monkeypatch `run_pending_job.delay` rather than standing up a broker — the assertion is about WHAT IS SENT and about the caller surviving a dead broker, and a real broker would prove neither more clearly · TC-3 calls the task body directly, which is exactly how Celery calls it (`__call__(job_id, tenant_id)`), so nothing about the shape is simulated
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
