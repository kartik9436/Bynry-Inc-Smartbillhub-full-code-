# ── Trace ──────────────────────────────────────────────
# Component: BE-07 jobs framework (B13 §3, W0 kernel lane — component packet)
# Contract:  TD-17 (async = Celery on Redis, all jobs idempotent + resumable, celery-beat
#            scheduling) · NFR-16 (idempotency wherever money enters/leaves) · NFR-4
#            (heavy jobs async with progress + per-item results) · B12 r1 §3-expanded
#            (202 + job_id for EVERY async op; client polls /jobs/{id})
# Change:    ⚠ AMENDED 2026-09-01 — CR-051 task 30, the TIME bound. A job that
#            runs out of its allowed time fails on the path this file already
#            had; all that is added is the SENTENCE (Celery's own message is the
#            empty string), the predicate a broad `except` must call before it
#            continues, and the release of a connection the signal interrupted.
# Rules:     BR-BIL-1030 (a background job is bounded in time as well as in size,
#            and what it does at the limit is fail honestly) · BR-BIL-015
#            (catch-up sub-runs scope-keyed, never a colliding re-run — the
#            pattern this kernel's scope_key generalizes) · BR-TEN-043 (jobs evaluate
#            config at THEIR event time — the runner receives the record, not "now")
# Defects:   DEF-2805 (a job killed by the HARD limit is left `running` for ever
#            and cannot be resumed — filed, not fixed here)
# Tests:     06-backend/tests/test_be07_jobs.py (in-memory store; fake celery module) ·
#            06-backend/tests/test_be07_job_runner.py (live store + eager runner +
#            GET /jobs/{id}, added by the job-runner lane 2026-08-10) ·
#            06-backend/tests/test_cr051_task30_time_limit.py (the time bound)
# Impacts:   bill runs (W3) · staged imports (BE-13) · outbound dispatcher (BE-16) ·
#            archival/partition jobs (BE-10) · estimation (BE-15) · FI-01 job-polling
# ───────────────────────────────────────────────────────
"""BE-07 — the ONE async-job contract: enqueue → 202 + job_id → poll /jobs/{id}.

Every async operation (B12 r1: runs, imports, dispatch, archival) is a JOB
RECORD first and a Celery task second. The record — not the broker — is the
source of truth the client polls, so a broker flush can delay work but never
lose status. The record contract (all a /jobs/{id} endpoint ever serves):

    id · tenant_id · kind · status · progress {done,total} · checkpoint ·
    result_link · error · scope_key · payload

Status vocabulary (Eng mechanics — A5 defines no job states; flagged to the
PO batch): queued → running → succeeded | failed. `failed → running` is legal:
that is the RESUME half of TD-17. `succeeded` is terminal forever.

Idempotent + resumable discipline (TD-17 / NFR-16), enforced here and owed by
every job author:
- IDEMPOTENT enqueue: a job carrying a scope_key (e.g. tenant+cycle+period for
  a bill run, file hash for an import) re-enqueued while a job with the same
  (kind, scope_key) is still active returns THE EXISTING record — no second
  job, no second dispatch. Whether the caller then answers 202-with-the-same-id
  or refuses BIZ-IDEMPOTENT is that story's law (B12 §3 carries who/when/link).
- RESUMABLE execution: tasks record progress + a `checkpoint` (last processed
  key) as they go; a retried/resumed run reads the checkpoint and skips work
  already done. Per-item effects must themselves be idempotent (scope-keyed,
  BR-BIL-015 pattern) so a replayed item is a no-op, never a double-post.

Narrow interface (same shape as core.audit): persistence is a registered store
with three duck-typed methods — save(record) upsert-by-id, get(job_id),
find_active(tenant_id, kind, scope_key). The module that lands the job table
registers it in AppConfig.ready(); until then enqueue fails LOUDLY (a 202
promising a poll URL with no row behind it would be a lie). On this deployment
apps.tenancy hosts the `jobs` table and registers the store (its models.py
records that hosting disposition).

WHO RUNS THE WORK — two paths, one code path underneath:
- A JOB BODY is a plain callable `handler(record) -> result_link | None`,
  registered by the module that owns the work: set_job_handler(kind, handler)
  in that app's AppConfig.ready(). The registry lives here so the runner can
  find a body by the record's `kind` alone (run_pending).
- EAGER (R1, no broker): the registered dispatcher runs the job in-process the
  moment it is enqueued — run_eager(record) → run_pending → run_job. This is
  what makes a 202 actually finish on a demo box with no Redis. The switch is
  the Django setting **JOBS_EAGER** (default True in base/local/dev, False in
  production, False in the test settings so a suite can enqueue and run as two
  deliberate steps); the setting is READ AT DISPATCH TIME by the registered
  dispatcher (apps.tenancy.services.dispatch_job), never here — core stays
  free of Django settings, and @override_settings(JOBS_EAGER=…) works per test.
- BROKER (TD-17, production): JOBS_EAGER off, the record rests `queued` until a
  Celery worker calls run_pending(job_id)/the task base below. Nothing is lost
  either way because the RECORD, not the broker, is the truth.

  ⚠ **THIS PARAGRAPH SAID "The worker half (celery app wiring, beat schedule)
  is still unbuilt — TD-17" AND IT HAS BEEN FALSE SINCE 2026-08-19. Corrected
  rather than left standing (CLAUDE.md hard-won law 1), and it is the exact
  hazard that law names: a comment claiming an ABSENCE outlives the absence,
  and every reader after it plans around a gap that closed.** CR-017 built the
  worker half on the PO's ruling of 2026-08-19 (*"We want Async job install
  redis and celery; Trigger after tenant creation … also add these two services
  in compose … Beat; include it"*). What exists now, all of it verifiable in one
  grep each: `config/celery.py` is the app; `docker-compose.yml` runs `redis`,
  `celery` and `celery-beat` as three services; `apps/tenancy/services.
  dispatch_job` reads JOBS_EAGER at dispatch time and hands the record to
  `apps.tenancy.tasks` when it is off; `config/settings/production.py` sets
  `JOBS_EAGER=False`; and `dispatch_is_ready()` above exists precisely because
  a worker can be DOWN, which is a different statement from unbuilt.

  The note to 09-infra/01-deployment-architecture.md still stands and is not a
  worker question: that document must state JOBS_EAGER=False plus a running
  broker as a production requirement, or 202s will silently execute inside the
  web request.

  As of 2026-08-30 TEN job kinds are registered across FIVE modules —
  `apps/tenancy` ×2, `apps/metering` ×3 (all three stages of the premises
  import), `apps/rating` ×1, `apps/audit` ×1, and `apps/billing` ×3 (CR-051:
  the bill run's calculate, findings and issue).

Celery stays a LAZY import (TD-17 adopts it; this kernel and its tests run
without the library or a broker): transport is a registered dispatcher
callable, and tenant_task_class() builds the Task base on demand. Tenant
context is NEVER ambient in a worker — run_job() re-enters it explicitly from
the record's tenant_id (B3: background jobs set context per tenant), so a
worker can never carry one tenant's context into another tenant's job.
"""

import inspect
import logging
from collections.abc import Callable
from typing import Any

from core.dbfields import uuid7
from core.tenancy import current_tenant_id, set_current_tenant, tenant_context

logger = logging.getLogger("smartbillhub.jobs")

# ── status vocabulary (kernel-defined wire values; absent from A5 — flagged) ──
QUEUED = "queued"
RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"
STATUSES = frozenset({QUEUED, RUNNING, SUCCEEDED, FAILED})
ACTIVE_STATUSES = frozenset({QUEUED, RUNNING})

# ── A JOB THAT RAN OUT OF TIME (CR-051 task 30) ─────────────────────────────
#: Celery's SOFT time limit raises INSIDE the task, which is the whole reason
#: this deployment sets one: the exception unwinds through `run_job` below and
#: lands on the SAME failure path every other job failure takes — `fail()`,
#: with the checkpoint left alone so the next attempt resumes rather than
#: re-walks. There is no second failure path and there must not be one.
#:
#: ⚠ **THE EXCEPTION'S OWN TEXT IS EMPTY, WHICH IS WHY THIS EXISTS.**
#: `str(SoftTimeLimitExceeded())` is `""`, so the record would have read
#: `SoftTimeLimitExceeded: ` — and `job.error` is drawn STRAIGHT ONTO THE
#: SCREEN by the bill-run wizard's progress band. A clerk would have been shown
#: a class name and a colon over the run they were waiting for.
#:
#: The Celery import is LAZY and its absence is not an error: this kernel and
#: its tests run without Celery installed or a broker up, which the module
#: docstring and `tenant_task_class()` both already depend on.
_time_limit_types: tuple[type[BaseException], ...] | None = None


def time_limit_exceptions() -> tuple[type[BaseException], ...]:
    """The exception types Celery raises when a task runs out of time.

    Empty when Celery is not installed, which makes every caller below a no-op
    rather than an ImportError — the same posture `tenant_task_class()` takes.
    """
    global _time_limit_types
    if _time_limit_types is None:
        try:
            from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded

            _time_limit_types = (SoftTimeLimitExceeded, TimeLimitExceeded)
        except Exception:  # noqa: BLE001 — no Celery is a valid deployment here
            _time_limit_types = ()
    return _time_limit_types


def is_time_limit(exc: BaseException) -> bool:
    """Did this job run out of its allowed time?"""
    types = time_limit_exceptions()
    return bool(types) and isinstance(exc, types)


def reraise_if_time_limit(exc: BaseException) -> None:
    """Re-raise `exc` if it is the time limit. For a broad `except` that CONTINUES.

    ⚠ **THIS IS THE HOLE A SOFT LIMIT FALLS INTO, AND IT IS SILENT.**
    `SoftTimeLimitExceeded` subclasses `Exception`, and Celery raises it EXACTLY
    ONCE, wherever the task happens to be. So a loop that says
    `except Exception: log; continue` — the shape a batch uses so one broken
    row never costs the other nine thousand their post — swallows the only
    signal the run will ever get, files it as a broken row, and carries on
    unbounded until the HARD limit kills the worker with nothing recorded.
    Nothing fails, nothing is logged as wrong, and the limit simply does not
    work: a check that cannot bite.

    Every broad handler on a job body's path calls this FIRST. It costs one
    line and it is the difference between the soft limit working and the soft
    limit being decoration.
    """
    if is_time_limit(exc):
        raise exc


def time_limit_error_text(exc: BaseException) -> str:
    """What the job record SAYS when a job ran out of time — a clerk reads this.

    `apps/billing/billRunResume.tsx` renders `job.error` verbatim in the
    progress band, so this is screen copy: plain sentences, no rule id, no
    register id, no class name (B14 rule 32, G28). It says the three things a
    person needs — that it stopped, why, and that nothing was lost.

    The limit is read from settings so the sentence and the setting can never
    disagree; a deployment that has tuned it says its own number.
    """
    how_long = "at its time limit"
    try:
        from django.conf import settings

        seconds = int(getattr(settings, "CELERY_TASK_SOFT_TIME_LIMIT", 0) or 0)
    except Exception:  # noqa: BLE001 — a sentence without the number still helps
        seconds = 0
    if 0 < seconds < 90:
        # A deployment tuned this low is almost certainly a test rig, and
        # *"after about 1 minutes"* is what rounding gave it before this
        # branch existed — wrong grammar AND a wrong number in one sentence.
        how_long = f"after about {seconds} seconds"
    elif seconds:
        how_long = f"after about {round(seconds / 60)} minutes"
    return (
        f"This stopped {how_long}, which is the longest one background job is "
        "allowed to run on this system. Everything it had already finished is kept — "
        "start it again and it carries on from where it stopped rather than beginning "
        "over. If it stops here a second time, the work is larger than this system is "
        "set up for: run a smaller batch, or ask for the limit to be raised."
    )


def release_interrupted_connection(tenant_id: Any = None) -> None:
    """Drop a database connection a SIGNAL left mid-command, so the failure row
    can still be written — and PUT THE TENANT BACK on the new one.

    ⚠ **THIS IS WHY THE SOFT LIMIT WOULD OTHERWISE RECORD NOTHING, AND IT WAS
    FOUND BY RUNNING A REAL WORKER RATHER THAN BY READING THE CODE
    (CR-051 task 30).** Celery raises `SoftTimeLimitExceeded` from a SIGNAL
    HANDLER — `billiard/pool.py: soft_timeout_sighandler` — so it lands wherever
    the task happens to be, and a long job spends most of its time inside a
    database call. Interrupted there, the psycopg connection is left with a
    command still in flight, and **the very next query on it raises**:

        django.db.utils.OperationalError: sending query failed:
        another command is already in progress

    The next query is `fail()`'s own `_load`. So the honest failure path fails,
    the record is left `running` for ever (`DEF-2805`'s shape), and the limit
    that was supposed to make the run tell the truth makes it tell nothing.
    Measured on a real Celery worker against real PostgreSQL, 2026-09-01: a
    print set stopped at 0.4 s left its job row `running` and the worker log
    carried the OperationalError above.

    This is CLAUDE.md law 14's neighbour and the same lesson: **the test suite
    runs on in-memory SQLite, which has no such state**, so every case here
    passes either way and only a real database shows it.

    Closing the connection makes Django open a fresh one for the next query,
    and the server rolls the interrupted transaction back. A connection inside
    an `atomic` block is LEFT ALONE — closing one there marks it
    `closed_in_transaction` and breaks every later query instead of one — but
    `run_job` is never inside an atomic block, and its callers own their own.

    ⚠ **AND THE FRESH CONNECTION HAS NO TENANT, WHICH IS THE HALF THAT BIT
    SECOND.** `app.tenant_id` is a SESSION setting (`core.tenancy` sets it with
    `set_config(..., is_local := false)`), so it dies with the connection it was
    set on. Under RLS FORCE the reopened session then reads ZERO rows, and
    `fail()`'s `_load` raises *"unknown job"* over a row that is sitting right
    there — the record stays `running` exactly as before, for a different
    reason. Measured the same afternoon on the same worker. So the tenant is
    re-applied here, before anything asks a question.
    """
    try:
        from django.db import connections
    except Exception:  # noqa: BLE001 — no Django is a valid caller here
        return
    closed = False
    for conn in connections.all():
        try:
            # ⚠ **POSTGRESQL ONLY, AND THAT IS A SAFETY RULE RATHER THAN A
            # NARROWING.** The state being cleared is a psycopg connection left
            # mid-command — SQLite has none, exactly as CLAUDE.md law 14 says of
            # aborted transactions. And the suite's database IS an in-memory
            # SQLite connection: closing it does not reconnect, it DESTROYS the
            # database for every test after it. A repair that can wipe the test
            # database to fix a condition that database cannot have is a bad
            # trade in both directions.
            if conn.vendor != "postgresql":
                continue
            if conn.connection is not None and not conn.in_atomic_block:
                conn.close()
                closed = True
        except Exception:  # noqa: BLE001 — a connection we cannot close is one
            # the next query will reopen anyway; the failure row matters more.
            logger.warning("could not release a database connection after a time limit")
    if closed and tenant_id is not None:
        try:
            set_current_tenant(tenant_id)
        except Exception:  # noqa: BLE001 — say so rather than fail silently
            logger.warning(
                "could not re-apply the tenant to a reopened connection; the failure "
                "row for this job may not be written"
            )


def failure_text(exc: BaseException) -> str:
    """The `error` field of a failed job record, for any exception.

    One place, so the time-limit sentence cannot be written in one caller and
    forgotten in another. Everything that is not a time limit keeps the
    `Type: message` form this file has always written — it goes to the same
    screen, and shortening it would hide the only diagnosis a support cycle has.
    """
    if is_time_limit(exc):
        return time_limit_error_text(exc)
    return f"{type(exc).__name__}: {exc}"


# The one poll path the 202 contract names (B12 r1: "poll /jobs/{id}").
# PLATFORM path — no tenant segment (PO ruling 2026-08-10, path tenancy):
# the poll is scoped by the session the caller presents, not by the URL.
POLL_PATH_TEMPLATE = "/api/jobs/{job_id}"


class JobsError(RuntimeError):
    """Kernel misuse: no store behind a 202, unknown job id, or an illegal
    status transition. Fails the calling operation loudly."""


# A job body: it receives the record and returns the result link (or None).
JobHandler = Callable[[dict[str, Any]], str | None]

# ── the store (narrow, registered by the job-table owner at AppConfig.ready) ──
_store: Any = None
_dispatcher: Callable[[dict[str, Any]], None] | None = None
_dispatch_probe: Callable[..., tuple[bool, str]] | None = None
_handlers: dict[str, JobHandler] = {}
#: kind → the NAMED BROKER QUEUE its messages are routed to. A kind with no
#: entry rides the default queue, which is what every kind did before CR-051
#: task 29. See `set_job_queue` for why this registry exists at all.
_queues: dict[str, str] = {}
#: DEF-BIL-8511 — `set_liveness_probe`: is a worker executing this job now?
_liveness_probe: Callable[[str], bool | None] | None = None


def set_job_store(store: Any) -> None:
    """Register (or clear, with None) the persistence store.

    Duck-typed contract: save(record dict) upserts by record["id"];
    get(job_id) -> record dict | None; find_active(tenant_id, kind, scope_key)
    -> record dict | None (a row in queued/running with that scope key).
    """
    global _store
    _store = store


def set_job_dispatcher(dispatcher: Callable[[dict[str, Any]], None] | None) -> None:
    """Register (or clear) the transport: dispatcher(record) sends the Celery
    task (e.g. `lambda r: bill_run_task.delay(r["id"])`). Optional — without
    one, records rest `queued` until a worker/wiring picks them up; nothing
    is lost because the record, not the broker, is the truth."""
    global _dispatcher
    _dispatcher = dispatcher


def set_dispatch_probe(probe: Callable[..., tuple[bool, str]] | None) -> None:
    """Register (or clear) the answer to *"if I enqueue right now, will anything
    actually RUN it?"*.

    ⛔ **WHY THIS EXISTS, AND WHY IT IS SEPARATE FROM THE DISPATCHER.**
    `set_job_dispatcher` above says a record can be HANDED OVER; it does not and
    cannot say a body will be EXECUTED. The transport is deliberately
    non-raising (`apps/tenancy/tasks.send` swallows a broker failure so that a
    202 over already-saved work is never turned into a 500), and `enqueue`
    itself has always answered the same whether a worker exists or not. That is
    the right posture for work that has already been RECORDED — and the wrong
    one for work a person is standing in front of waiting for.

    On a deployment with no worker running, an import handed to the queue is
    accepted, the screen says *queued*, and the accounts never appear. That is
    strictly worse than the visible 500 it replaced, and it would be OUR doing
    (CLAUDE.md law 3 — the unsafe option must be the one you type). So a caller
    that is about to promise a person something asks this FIRST and refuses when
    the answer is no.

    probe(queue=None) -> (ready, reason). `reason` is a short technical phrase
    for the log — never a sentence for a screen; the refusal's own message key
    carries that. With no probe registered the answer is
    `(True, "no probe registered")`, because a deployment that has not wired one
    has not asked for the check and must not be broken by its absence.

    ⚠ **THE ARGUMENT ARRIVED WITH THE SECOND QUEUE (CR-051 task 29).** `queue`
    is the NAMED queue the caller's job will be routed to, or None for the
    default one. A probe that ignores it answers *"is any worker alive"*, which
    stopped being the same question as *"will MY job run"* on 2026-08-31 — see
    `dispatch_is_ready`. A probe that takes no argument at all is still called
    the old way, so nothing that predates the split breaks.
    """
    global _dispatch_probe
    _dispatch_probe = probe


def dispatch_is_ready(kind: str | None = None) -> tuple[bool, str]:
    """Would a job enqueued now be executed? See `set_dispatch_probe`.

    ⚠ **A PROBE THAT RAISES MEANS NOT READY.** It is asked exactly when the
    product is about to make a promise, and "we could not tell" is not a reason
    to make one (law 3 — defaults fail closed).

    ⚠ **`kind` IS NOT OPTIONAL DECORATION — IT IS THE WHOLE QUESTION ONCE MORE
    THAN ONE QUEUE EXISTS (CR-051 task 29).** Until 2026-08-31 every job in this
    product rode ONE queue, so *"is any worker alive"* and *"will MY job run"*
    were the same sentence. Billing now has its own named queue and its own
    worker, and the two sentences have come apart: a healthy `celery` worker
    answers the broadcast ping while the `billing` queue has **no consumer at
    all**, and a caller that asked the old question would be told *ready* and
    then watch a bill run rest `queued` for ever. That is `core/jobs.py`'s own
    named failure — *"it accepts the file, says 'queued', and writes nothing,
    for ever"* — reintroduced by the very change that split the queues.

    So pass the KIND you are about to enqueue and the probe resolves it through
    `job_queue()` to the queue that must have a consumer. Passing nothing keeps
    the old broadcast question, which is still the right one for a kind that
    rides the default queue.
    """
    if _dispatch_probe is None:
        return True, "no probe registered"
    probe = _dispatch_probe
    queue = job_queue(kind) if kind else None
    try:
        # A probe written before CR-051 task 29 takes no argument. Ask it the old
        # question rather than letting an ARITY become a refusal: this answer
        # gates work a person is waiting for, and a signature mismatch is our
        # problem, not theirs. Decided by reading the signature, never by
        # catching TypeError — a TypeError raised INSIDE a probe body would be
        # indistinguishable, and "the probe is broken" must stay a refusal.
        return probe(queue) if _probe_takes_queue(probe) else probe()
    except Exception as exc:  # noqa: BLE001 — see the docstring
        logger.warning("BE-07: dispatch probe raised, treating as NOT ready: %r", exc)
        return False, f"probe raised {type(exc).__name__}"


def _probe_takes_queue(probe: Callable[..., tuple[bool, str]]) -> bool:
    """Can this probe be asked about ONE queue, or only the old broadcast
    question? Read from the signature; unreadable means no."""
    try:
        signature = inspect.signature(probe)
        signature.bind(None)
    except (TypeError, ValueError):
        return False
    return True


def set_job_handler(kind: str, handler: JobHandler | None) -> None:
    """Register (or clear, with None) the BODY of one job kind.

    The owning module registers its own body in AppConfig.ready() — the same
    posture as the store and the audit sink, so core never imports app code:

        core.jobs.set_job_handler("audit_export", exports.run_export_job)

    handler(record) -> result_link | None. It reports progress itself through
    record_progress(); start/succeed/fail bookkeeping is run_job()'s job.
    """
    if handler is None:
        _handlers.pop(kind, None)
        return
    _handlers[kind] = handler


def job_handler(kind: str) -> JobHandler | None:
    """The registered body for `kind`, or None (nothing is registered)."""
    return _handlers.get(kind)


# ── the queue registry (CR-051 task 29) ─────────────────────────────────────
def set_job_queue(kind: str, queue: str | None) -> None:
    """Register (or clear, with None) the NAMED BROKER QUEUE one kind rides.

    The owning module registers this beside its handler, in AppConfig.ready() —
    the same posture as the store, the audit sink and the body registry, so core
    never imports app code:

        core.jobs.set_job_queue("billing.run.calculate", "billing")

    **WHY A KIND NEEDS A QUEUE AT ALL, said once so nobody re-derives it.** PO
    ruling 2026-08-31, verbatim: *"we will ahve to create named worker for
    billing - eventually we should able to scale these works on the fly itf
    required; but billing will need its own named workers - otherwise it will
    slow down the system"*. Until that ruling ONE queue carried bill runs, CSV
    exports, staged imports and customers' outbound notices through the same two
    worker slots — so a CPU cap on the worker capped the notices too, and
    scaling for a bill run scaled everything. A named queue is not an
    optimisation; it is the thing that makes a cap and a replica count apply to
    billing **and only billing**.

    ⚠ **THIS REGISTRY IS ONLY HALF OF A QUEUE, AND THE OTHER HALF IS IN
    `docker-compose.yml`.** A kind routed to a queue nothing consumes is
    accepted, answers 202, and never runs — this module's own docstring names
    that shape: *"it accepts the file, says 'queued', and writes nothing, for
    ever"*. Register a queue here and a worker MUST be consuming it. `G59`
    (`10-scripts/gates/g59_billing_queue_split.py`) checks both halves against
    each other and fails when either one is missing, because either one alone is
    worse than neither.
    """
    if queue is None:
        _queues.pop(kind, None)
        return
    _queues[kind] = queue


def job_queue(kind: str) -> str | None:
    """The named queue `kind` rides, or None — it rides the default queue."""
    return _queues.get(kind)


def job_queues() -> dict[str, str]:
    """Every registered kind→queue pair. A copy: the registry is not editable
    through its own reader."""
    return dict(_queues)


# ── enqueue → 202 ───────────────────────────────────────────────────────────
def enqueue(
    kind: str,
    *,
    payload: dict[str, Any] | None = None,
    scope_key: str | None = None,
    dispatch: bool = True,
) -> dict[str, Any]:
    """Create (or idempotently return) the job record and dispatch it.

    Returns the record; the API layer answers 202 with accepted(record). The
    caller's transaction should commit the row before the worker can race it —
    dispatch-after-commit mechanics live with the registering module.

    `dispatch=False` (B28, 2026-10-01) saves the record and hands it to NO
    transport: the caller is inside a transaction holding a lock and calls
    `dispatch(record)` itself after the commit, so a worker can never read a
    record that is not yet visible, and an eager dispatcher never runs a job
    body inside the caller's lock. Every other caller keeps the default.
    """
    if not kind:
        raise JobsError("a job kind is required")
    tenant_id = current_tenant_id()
    if tenant_id is None:
        # Every W0 job kind is tenant work; platform-scoped jobs would need a
        # deliberate contract change, not a silent None.
        raise JobsError(f"no tenant context set for job {kind!r} (B3: jobs are per-tenant)")
    if _store is None:
        raise JobsError(f"no job store registered — cannot promise a poll URL for {kind!r}")

    if scope_key is not None:
        existing = _store.find_active(tenant_id, kind, scope_key)
        if existing is not None:
            # NFR-16: same scope, still active → the same job, not a second one.
            logger.info(
                "job %s re-enqueue folded into %s (scope_key=%s)", kind, existing["id"], scope_key
            )
            return existing

    record: dict[str, Any] = {
        # Canonical dashed uuidv7 (DB-2): the same string the `jobs.id` uuid
        # column stores and the `/jobs/<uuid:job_id>` route matches, so the id
        # handed out in the 202 is byte-for-byte the id the poll answers with.
        "id": str(uuid7()),
        "tenant_id": tenant_id,
        "kind": kind,
        "status": QUEUED,
        "progress": {"done": 0, "total": None},
        "checkpoint": None,
        "result_link": None,
        "error": None,
        "scope_key": scope_key,
        "payload": payload or {},
    }
    _store.save(record)
    if dispatch and _dispatcher is not None:
        _dispatcher(record)
    return record


def find_active(kind: str, scope_key: str) -> dict[str, Any] | None:
    """The CURRENT tenant's queued or running `kind` job for `scope_key`, or
    None — the same lookup `enqueue` folds a repeat press into. DEF-BIL-9010:
    a re-opened bill run asks it so a Calculate still running is shown as
    running, not as the drafts it has written so far."""
    tenant_id = current_tenant_id()
    if tenant_id is None:
        raise JobsError(f"no tenant context set to find an active {kind!r} job (B3)")
    if _store is None:
        raise JobsError("no job store registered")
    return _store.find_active(tenant_id, kind, scope_key)


def active_records(kind: str) -> list[dict[str, Any]]:
    """Every ACTIVE (queued or running) record of `kind` for the CURRENT tenant,
    oldest first — B28's per-utility cap counts its batches with it.

    Tenant-scoped like `enqueue`: the tenant comes from the context, never a
    parameter, so a caller cannot count another utility's jobs. A store with no
    `list_active` cannot answer, and that is a LOUD failure rather than an
    empty list: an empty answer would read as *nothing running* and lift every
    cap built on it."""
    tenant_id = current_tenant_id()
    if tenant_id is None:
        raise JobsError(f"no tenant context set to list active {kind!r} jobs (B3)")
    if _store is None:
        raise JobsError("no job store registered")
    lister = getattr(_store, "list_active", None)
    if lister is None:
        raise JobsError("the registered job store cannot list active jobs")
    return [dict(one) for one in lister(tenant_id, kind)]


#: B28 — what a runner returns when it has SETTLED ITS OWN RECORD, or handed its
#: completion to other jobs: `run_job` then neither succeeds nor touches the
#: record. The bulk Check's coordinator returns it after dispatching its
#: batches (the LAST batch to finish succeeds it), and each batch returns it
#: after succeeding itself inside the lock that counts the run's totals.
HANDED_OFF = object()


def accepted(record: dict[str, Any]) -> dict[str, Any]:
    """The 202 body (B12 r1): the job id + where to poll. Nothing else — status
    truth lives at the poll endpoint, never in the accept response."""
    return {"job_id": record["id"], "status_url": poll_url(record["id"])}


def poll_url(job_id: str) -> str:
    return POLL_PATH_TEMPLATE.format(job_id=job_id)


# ── status transitions (load → check → save; the record is the state machine) ──
def _load(job_id: str) -> dict[str, Any]:
    if _store is None:
        raise JobsError("no job store registered")
    record = _store.get(job_id)
    if record is None:
        raise JobsError(f"unknown job {job_id!r}")
    return record


def current(job_id: str) -> dict[str, Any]:
    """The record AS STORED NOW — read-only.

    `enqueue` returns the record it created, which says `queued` even when an
    eager dispatcher has already run it to the end. A caller that reports a
    job's state back to a person (`DEF-MET-8108`'s post receipt) asks this
    instead, so it never prints *queued* over work that has finished.
    """
    return dict(_load(job_id))


def start(job_id: str) -> dict[str, Any]:
    """queued → running, or failed → running (the TD-17 resume). Never out of
    succeeded — finished work is finished; corrections are NEW jobs."""
    record = _load(job_id)
    if record["status"] not in (QUEUED, FAILED):
        raise JobsError(
            f"job {job_id} is {record['status']} — cannot start (resume is failed→running)"
        )
    record["status"] = RUNNING
    record["error"] = None  # a resumed run gets a clean error slate; checkpoint SURVIVES
    _store.save(record)
    return record


def record_progress(
    job_id: str,
    done: int,
    total: int | None = None,
    checkpoint: Any = None,
    stage: str | None = None,
) -> dict[str, Any]:
    """NFR-4 progress + the resume marker. `checkpoint` is whatever the job
    needs to skip finished work on resume (last row id, last account no, …).

    `stage` (DEF-BIL-9010) names a FIRST pass a job counts before its main one
    — a bill run's Calculate reads every account before it drafts any — so a
    screen can say which count it shows. Omitted, progress is the two keys it
    always was."""
    record = _load(job_id)
    if record["status"] != RUNNING:
        raise JobsError(f"job {job_id} is {record['status']} — progress belongs to running jobs")
    record["progress"] = {"done": done, "total": total}
    if stage is not None:
        record["progress"]["stage"] = stage
    if checkpoint is not None:
        record["checkpoint"] = checkpoint
    _store.save(record)
    return record


def succeed(job_id: str, result_link: str | None = None) -> dict[str, Any]:
    """running → succeeded (+ the result-link the poll response hands out:
    a created resource, a per-item results page, a download — per NFR-4)."""
    record = _load(job_id)
    if record["status"] != RUNNING:
        raise JobsError(f"job {job_id} is {record['status']} — only a running job can succeed")
    record["status"] = SUCCEEDED
    record["result_link"] = result_link
    _store.save(record)
    return record


def fail(job_id: str, error: str) -> dict[str, Any]:
    """running → failed. The checkpoint stays — that is what resume reads."""
    record = _load(job_id)
    if record["status"] != RUNNING:
        raise JobsError(f"job {job_id} is {record['status']} — only a running job can fail")
    record["status"] = FAILED
    record["error"] = error
    _store.save(record)
    return record


# ── A WORKER THAT VANISHED (CR-105-BRC03) ───────────────────────────────────
#: The sentence a reclaimed record carries into `job.error`, which the bill-run
#: wizard's progress band draws STRAIGHT ONTO THE SCREEN (see
#: `time_limit_error_text` above, which exists for exactly that reason). So it
#: is written for a clerk and not for a log: no signal number, no queue name,
#: no job id.
RECLAIMED_ERROR_TEXT = "the machine working on this stopped before it finished"


def reclaim(job_id: str, *, reason: str) -> dict[str, Any]:
    """running → failed, CHECKPOINT UNTOUCHED — an ABANDONED job, taken back.

    ⚠ **WHY THIS HAD TO EXIST, AND WHY ITS ABSENCE MADE `checkpoint` DEAD
    WEIGHT (CR-105-BRC03, blueprint p050).** Every other way out of `running`
    is written BY THE RUNNER: `succeed`, `fail`, and the soft-time-limit path
    that reaches `fail` through `run_job`. **A process that is killed writes
    none of them** — `run_job` catches `Exception`, and a `SIGKILL` is not an
    exception, it is the absence of any further instruction. So the record is
    left saying `running` for ever.

    That was one hop away from being harmless and it was not harmless at all.
    `CELERY_TASK_ACKS_LATE` is on precisely so a dead worker's message is
    DELIVERED AGAIN; the redelivery reached `start()`, and `start()` refuses a
    `running` record. The re-delivered task therefore raised

        JobsError: job … is running — cannot start (resume is failed→running)

    and the run stayed `running` for ever with nobody working on it. Which
    means the `checkpoint` this kernel persists, and the careful cursor
    `apps/billing/run_resume.py` writes into it, **were reachable by nothing in
    this product**: `10-scripts/cr051_kill_and_resume.py` gets to them only by
    hand-writing `core_jobs.fail(job_id, "worker killed (SIGKILL)")` first, and
    no deployment performs that step. A blueprint sentence measured the cost at
    **22 minutes on a 10,000-account run**; the true cost was the run never
    finishing at all.

    **THE CALLER PROMISES THE PREVIOUS ATTEMPT IS GONE, and that promise is not
    rhetorical.** Reclaiming a record whose worker is still alive would put two
    passes on one job: the second reclaims, starts, and walks; the first then
    calls `succeed()` on a record it no longer owns. Nothing here can check it
    — there is no owner column and no heartbeat, and adding either is a
    migration onto a table five modules share. What makes the promise TRUE on
    this deployment is stated where it is arranged rather than here:
    `config/settings/base.py` sets the broker's `visibility_timeout` ABOVE
    `CELERY_TASK_TIME_LIMIT`, so a message cannot come back until after the
    hard limit has already killed whatever was running it. Change one of those
    two numbers without the other and this function becomes unsafe, which is
    why they are set in one place, in one expression, with each other named.

    **THE CHECKPOINT IS NOT CLEARED AND THAT IS THE WHOLE ASSET.** A reclaim
    that reset it would read as a repair and cost the 22 minutes anyway.
    """
    record = _load(job_id)
    if record["status"] != RUNNING:
        raise JobsError(
            f"job {job_id} is {record['status']} — only a running job can be reclaimed "
            "(a reclaim is what a dead worker's record needs, and nothing else)"
        )
    logger.warning(
        "BE-07: reclaiming abandoned job %s (%s) — checkpoint %s",
        job_id,
        reason,
        "kept" if record.get("checkpoint") else "none written",
    )
    record["status"] = FAILED
    record["error"] = RECLAIMED_ERROR_TEXT
    _store.save(record)
    return record


def resume(job_id: str) -> dict[str, Any]:
    """Pick one job back up — the entry point a DELIVERY uses, first or not.

    Three records reach here and each takes the branch it should:

    * **queued** — an ordinary first delivery. Straight to `run_pending`; this
      is byte-for-byte what the transport did before this function existed.
    * **failed** — a soft time limit, or a body that raised. `start()` has
      always allowed `failed → running` and the checkpoint has always survived
      it; what was missing was anything that DELIVERED such a record again.
    * **running** — the abandoned record a killed worker leaves. Reclaimed
      first (see `reclaim` for the promise that makes safe), then run.

    **`succeeded` is refused, by `start()`, and must stay refused.** A resumed
    pass over a run whose bills are already issued would be a second pass at
    financial immutability (CLAUDE.md hard rule 4). It is not special-cased
    here on purpose: one refusal, in the transition that owns the vocabulary.
    """
    record = _load(job_id)
    if record["status"] == RUNNING:
        reclaim(job_id, reason="delivered again while the record still said running")
    return run_pending(job_id)


# ── A PERSON PRESSING RESUME (DEF-BIL-8511) ─────────────────────────────────
#: The answers `redispatch` gives, one word each, for the caller's response.
REDISPATCHED = "resumed"
STILL_RUNNING = "running"
STILL_QUEUED = "waiting"
ALREADY_DONE = "finished"


def seconds_idle(job_id: str) -> float | None:
    """How long since the record was last WRITTEN — the heartbeat a running
    job gives by recording progress. None when the store cannot say (a store
    with no `seconds_idle` method), which every caller must read as *not
    stalled*: an unknown is never a licence to take a job off a live worker."""
    probe = getattr(_store, "seconds_idle", None)
    if probe is None:
        return None
    try:
        idle = probe(job_id)
    except Exception:  # noqa: BLE001 — unknown, never stalled
        logger.warning("BE-07: could not read how long job %s has been idle", job_id)
        return None
    return None if idle is None else float(idle)


def requeue(job_id: str) -> dict[str, Any]:
    """failed → queued, CHECKPOINT KEPT, error cleared — a stopped job put back
    in line for a worker. The worker's delivery then takes `resume`'s queued
    branch (`start` allows queued → running), so nothing new is learned by the
    body: it reads the checkpoint exactly as a redelivery would."""
    record = _load(job_id)
    if record["status"] != FAILED:
        raise JobsError(f"job {job_id} is {record['status']} — only a failed job can be requeued")
    record["status"] = QUEUED
    record["error"] = None
    _store.save(record)
    return record


def set_liveness_probe(probe: Callable[[str], bool | None] | None) -> None:
    """Register (or clear) the answer to *"is a worker executing this job right
    now?"* — `probe(job_id) -> True | False | None`. None means it cannot tell
    (no broker, nobody answered), and is read exactly like no probe at all."""
    global _liveness_probe
    _liveness_probe = probe


def job_is_being_worked(job_id: str) -> bool | None:
    """The liveness probe's answer, or None — never raises."""
    if _liveness_probe is None:
        return None
    try:
        return _liveness_probe(job_id)
    except Exception:  # noqa: BLE001 — unknown, never "stopped"
        logger.warning("BE-07: liveness probe raised for job %s", job_id)
        return None


def is_abandoned(job_id: str, *, stalled_after: float, stopped_floor: float) -> bool:
    """A RUNNING record whose worker is gone. Two ways to know, and both need
    the record to have gone quiet first:

    * the liveness probe says NO worker is executing it, and nothing has been
      written for `stopped_floor` seconds (a short floor, so a job that has
      only just been picked up is never taken back between two heartbeats);
    * the probe cannot tell, and nothing has been written for `stalled_after`
      seconds — the heartbeat alone, set well above the job's longest silence.

    A probe that says YES wins outright. An idle time the store cannot give is
    never abandoned: an unknown is not a licence to take a job off a worker."""
    record = _load(job_id)
    if record["status"] != RUNNING:
        return False
    idle = seconds_idle(job_id)
    if idle is None:
        return False
    working = job_is_being_worked(job_id)
    if working is True:
        return False
    if working is False:
        return idle >= stopped_floor
    return idle >= stalled_after


def take_back(
    job_id: str, *, stalled_after: float, stopped_floor: float
) -> tuple[dict[str, Any], str]:
    """The record half of `redispatch`: decide, reclaim and requeue — no
    dispatch. A caller holding a lock dispatches after its commit
    (`dispatch`), so a worker can never read the record before it says
    `queued`. Returns the record and one of the four answers below."""
    record = _load(job_id)
    status = record["status"]
    if status == SUCCEEDED:
        return record, ALREADY_DONE
    if status == QUEUED:
        return record, STILL_QUEUED
    if status == RUNNING:
        if not is_abandoned(job_id, stalled_after=stalled_after, stopped_floor=stopped_floor):
            return record, STILL_RUNNING
        reclaim(job_id, reason="no worker is executing it and it has written nothing since")
    return requeue(job_id), REDISPATCHED


def dispatch(record: dict[str, Any]) -> None:
    """Hand one record to the registered transport — the same one `enqueue`
    uses. Raises when none is registered: a resume that silently went nowhere
    would be the queued-for-ever lie `set_dispatch_probe` exists to prevent."""
    if _dispatcher is None:
        raise JobsError(f"no dispatcher registered — cannot hand job {record['id']} to a worker")
    _dispatcher(record)


def redispatch(
    job_id: str, *, stalled_after: float, stopped_floor: float = 0.0
) -> tuple[dict[str, Any], str]:
    """Hand a STOPPED job back to the transport — never run it in the caller.

    ⚠ **WHY THIS EXISTS BESIDE `resume` (DEF-BIL-8511).** `resume` is what a
    DELIVERY calls: it runs the body right here, which is correct inside a
    worker and wrong inside a web request. The bulk bill run's *Resume* button
    called it from the request, so a Check killed at 1,000 of 10,000 accounts
    ran the other 9,000 inside a request a web worker is given 60 seconds for
    (`GUNICORN_TIMEOUT`); the request was killed and the job was left
    `running` again. This function writes the record and hands it to the
    registered dispatcher, and the dispatcher decides where the body runs —
    the billing queue on a real deployment, in-process only under
    `JOBS_EAGER`, which is the demo box's own choice.

    What each status does (the answer is returned beside the record):

    * **succeeded** — nothing (`ALREADY_DONE`). Finished work is finished.
    * **queued** — nothing (`STILL_QUEUED`): a message is already waiting for
      a worker, and a second one would put two passes on one job.
    * **running** and still worked (`is_abandoned` says no) — nothing
      (`STILL_RUNNING`); taking it back would be two passes on one job, the
      hazard `reclaim` states.
    * **running** and abandoned — reclaimed, requeued, dispatched.
    * **failed** — requeued and dispatched (`REDISPATCHED`); the checkpoint
      survives, so it carries on after the last item it saved.

    **THE LATE REDELIVERY STAYS SAFE.** A killed worker's own message comes
    back after the broker's `visibility_timeout`, which `config/settings/
    base.py` sets above `CELERY_TASK_TIME_LIMIT`. The pass this dispatches
    started AFTER the kill, so by the time that message returns the hard limit
    has already ended this pass — `reclaim`'s promise holds for it too.
    """
    record, outcome = take_back(job_id, stalled_after=stalled_after, stopped_floor=stopped_floor)
    if outcome == REDISPATCHED:
        dispatch(record)
        record = current(job_id)
    return record, outcome


# ── execution harness (workers, management commands, tests — one code path) ──
def run_job(job_id: str, runner: Callable[[dict[str, Any]], str | None]) -> dict[str, Any]:
    """Run one job under ITS tenant's context: load → start → runner(record) →
    succeed(result_link) — or fail + re-raise (re-raising lets Celery's own
    retry policy see the error; the record already says failed either way).

    The runner gets the fresh record (payload, checkpoint for resume) and
    returns the result link (or None). It reports progress itself via
    record_progress(). Context is entered from record["tenant_id"] and cleared
    on exit even on error — a worker never leaks one tenant into the next task.
    """
    record = _load(job_id)
    with tenant_context(record["tenant_id"]):
        started = start(job_id)
        try:
            result_link = runner(started)
            if result_link is HANDED_OFF:
                return current(job_id)
        except Exception as exc:
            # CR-051 task 30 — a SOFT time limit arrives here like any other
            # exception, which is the point: the run fails on the path it
            # already had, the record stops saying `running`, and the
            # checkpoint is untouched so `start()`'s failed→running resume
            # picks the work back up. `failure_text` is what turns Celery's
            # empty `SoftTimeLimitExceeded()` into a sentence a clerk can read.
            if is_time_limit(exc):
                # The signal may have landed mid-query; without this, `fail()`
                # raises `another command is already in progress` and the row
                # stays `running`. See `release_interrupted_connection`.
                release_interrupted_connection(record["tenant_id"])
            fail(job_id, error=failure_text(exc))
            raise
        return succeed(job_id, result_link=result_link)


def run_pending(job_id: str) -> dict[str, Any]:
    """Run a queued/failed job by looking its BODY up from the record's kind.

    The one entry point a worker, a management command, the eager dispatcher
    and a test all share — nobody has to know which function belongs to which
    kind, only that the owning module registered it.
    """
    record = _load(job_id)
    handler = _handlers.get(record["kind"])
    if handler is None:
        raise JobsError(
            f"no handler registered for job kind {record['kind']!r} "
            f"(the owning module registers it in AppConfig.ready)"
        )
    return run_job(job_id, handler)


def run_eager(record: dict[str, Any]) -> None:
    """JOBS_EAGER transport: execute the job HERE, inside the caller's request.

    Registered as the dispatcher (see the module docstring) so a deployment
    without a broker still completes what its 202 promised. Three deliberate
    properties:

    - It never raises into the caller. The enqueueing endpoint already answered
      "accepted"; a job body that blows up is a FAILED RECORD (the poll is
      where that truth belongs), not a 500 on the accept call.
    - It puts the caller's tenant context BACK. run_job() clears context on
      exit (B3 — a worker must not leak one tenant into the next task), but
      here the caller is mid-request and still needs its own context, e.g. to
      write the audit row that follows its enqueue.
    - A body that never started (nothing registered for the kind) is recorded
      as failed rather than left `queued`: in eager mode no worker is coming,
      so a queued record would be a lie of a different shape.
    """
    job_id = record["id"]
    caller_tenant = current_tenant_id()
    try:
        try:
            run_pending(job_id)
        finally:
            if caller_tenant is not None:
                set_current_tenant(caller_tenant)
    except Exception as exc:  # noqa: BLE001 — the record carries the failure
        logger.exception("eager job %s (%s) failed", job_id, record.get("kind"))
        _record_unstarted_failure(job_id, exc)


def _record_unstarted_failure(job_id: str, exc: Exception) -> None:
    """Mark a still-`queued` record failed (run_job never got to start it)."""
    current = _store.get(job_id) if _store is not None else None
    if current is None or current["status"] != QUEUED:
        return  # run_job already wrote the failure
    start(job_id)
    fail(job_id, error=failure_text(exc))


def tenant_task_class() -> type:
    """Build the Celery Task base LAZILY (TD-17) — the import lives in here so
    the kernel and its tests run without Celery installed or a broker up.

    Usage in a module's tasks file (Celery wiring is that module's story):

        @app.task(base=jobs.tenant_task_class(), bind=False)
        def bill_run_task(record): ...   # receives the job record, in-context

    Every task's single queue argument is the job_id; __call__ routes through
    run_job(), so tenant context, start/succeed/fail bookkeeping, and resume
    semantics are identical on a worker, in a management command, and in tests.
    """
    import celery

    harness_run = run_job

    class TenantJobTask(celery.Task):
        def __call__(self, job_id: str) -> dict[str, Any]:
            return harness_run(job_id, lambda record: self.run(record))

    return TenantJobTask


# ── Lifecycle ─────────────────────────────────────────────
# packet: BE-07@05736ee (component packet — B13 §3 row + signed contracts; hash = sha256/7 of B12)
# generated: 2026-08-09 by story-coder v1 (W0 kernel lane, B13 rows BE-06..BE-09) · AMENDED 2026-08-10 by story-coder (job-runner lane: handler registry + eager execution path) · AMENDED 2026-08-10 by story-coder (path-tenancy lane — PO ruling 2026-08-10)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-08)
# gates: ruff✔ black✔ pytest tests/test_be07_jobs.py 17/17✔ (live table + worker TCs land with the job-table story) · suite 147/147✔ · run_gates 10-PASS/0-FAIL✔ · trace_lint✔ · mypy NOT run — B8 strict scope is services/engines · [job-runner lane 2026-08-10] ruff✔ black✔ · pytest tests/test_be07_jobs.py 17/17✔ + tests/test_be07_job_runner.py✔ · suite `pytest tests -m "not golden and not isolation"` 713 passed / 7 skipped / 47 deselected (682 was the baseline when this lane started; the 31 new TCs are this lane's) · `-m isolation` 14 passed / 22 postgres-only skipped · migrate from empty✔ makemigrations --check --dry-run clean✔ · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy NOT INSTALLED in this environment (recorded, not skipped silently) · [path-tenancy lane 2026-08-10] ruff✔ black✔ · suite `pytest tests -m "not golden and not isolation"` 818 passed / 9 skipped (788 baseline) · `-m isolation` 32 passed / 12 skipped (29 baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · no migration in this lane
# exceptions: none stubbed; E2-candidates reported to the PO batch via the build report (A5 defines no job-status vocabulary — queued/running/succeeded/failed is kernel-defined Eng mechanics pending ratification) · [job-runner lane 2026-08-10] the record id is now a canonical dashed uuidv7 (was uuid4().hex) so the 202's job_id, the `jobs.id` column and the `<uuid:job_id>` route are one string — behavior change to a VERIFIED file, REPORTED · run_job() still LOADS the record before entering tenant context; under RLS FORCE a broker worker will have to resolve its tenant before that load (eager mode is already in context, so R1 is unaffected) — REPORTED for the TD-17 worker lane · JOBS_EAGER runs job bodies inside the web request: acceptable for the R1 demo, and the reason the deployment doc must set it False in production (docstring note for 09-infra/01-deployment-architecture.md, out of this lane's territory) · [path-tenancy lane 2026-08-10] POLL_PATH_TEMPLATE is now `/api/jobs/{job_id}` — a PLATFORM path with no tenant segment (the fixed 2026-08-10 contract), scoped by the caller's session rather than the URL
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
