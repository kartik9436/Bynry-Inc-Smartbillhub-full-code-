# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-016 (EP-INT-05) — job kinds and a dedicated queue, and the
#           consuming worker, or neither. US-INT-015 (the bodies call the
#           four methods). Screens: S141 (the 202 and its poll url) · S142
# Rules:    BR-INT-041 (P5 — its own named queue WITH its own consuming
#           worker; a route with no consumer accepts work and never runs) ·
#           BR-INT-022 (a slow provider degrades to a queue, never to an
#           outage — the body runs in a different process from the request) ·
#           BR-INT-019 (`test()` is the smallest real instance) · BR-INT-018
#           (the outcome is computed by `services.finish_run`) · BR-INT-003
#           (the plaintext exists at one point, for one call) · TD-17 · B12
#           r1 §3 (202 + job id) · DEF-320 (the queue nothing drained) ·
#           CLAUDE.md hard-won law 2 (built is not wired)
# Tests:    06-backend/tests/test_us_int_016_queue.py (TC-1 the row before
#           the message · TC-2 the gate · TC-6 two tenants, two scope keys) ·
#           10-scripts/gates/g80_integrations_queue_split.py
# Impacts:  apps/integrations/apps.py (calls `register()` at ready()) ·
#           config/celery_routes.py (already routes by kind through
#           `core.jobs.job_queue`) · docker-compose.yml (`celery-integrations`,
#           `-Q integrations` — the CONSUMER half, in the same commit)
# ───────────────────────────────────────────────────────
"""Integration work rides its own queue — five kinds, one worker, two bodies today.

THE TWO ORDERINGS THAT CARRY THE DESIGN (Figure 16)
---------------------------------------------------
1. **The job ROW is written before the broker message and before the 202.**
   That is `core.jobs.enqueue`'s own order — `_store.save(record)` and only
   then `_dispatcher(record)` — and `services.request_test` answers 202 from
   the record it got back. A broker that loses the message loses nothing
   durable: the row rests `queued` and the due sweep (wave G) re-enqueues by
   scope key, folding into the SAME row (NFR-16). TC-1 asserts the order with
   a dispatcher double that reads the `jobs` table at the moment it is called.
2. **The adapter call happens in a different process from the request.**
   `JOBS_EAGER=False` in production hands the record to Celery; the worker on
   `-Q integrations` runs `core.jobs.run_pending(job_id)` → the body below.
   A ninety-second mail server holds an integrations worker, never a web
   worker and never the billing queue (US-INT-016 TC-3, wave F's breaker).

ONE QUEUE, TWO HALVES, ONE COMMIT (BR-INT-041, `DEF-320`)
---------------------------------------------------------
`register()` maps every kind to the `integrations` queue through
`core.jobs.set_job_queue`, which `config/celery_routes.py` already reads.
That is the ROUTING half. The CONSUMER half is `docker-compose.yml`'s
`celery-integrations` service running `-Q integrations`, and the default
worker stays `-Q celery` — it must NOT drain this queue too, or the split is
cosmetic. `G80` refuses a tree with one half and not the other, exactly as
`G59` does for billing; it was proved RED by taking `-Q integrations` off the
worker's command line.

FIVE KINDS, TWO BODIES
----------------------
    integration.test              this file — the smallest real instance
    integration.run               this file — one attempt, one WALK, or a
                                  submit-poll-collect: the shape is read off
                                  the operation (wave K)
    integration.sweep_due         wave G (US-INT-029) — the nightly cadence
    integration.sweep_expiry      this file — the dated warning (wave H)
    integration.inbound_process   wave N (US-INT-044) — the door

THREE have bodies since wave H; the remaining two are ROUTED so a message
for a later kind lands on this queue
and fails there by name (`core.jobs.run_pending`: *no handler registered for
job kind …*) rather than riding the default queue in silence. A handler is
registered only where a body exists — a stub that swallowed the message would
be DEF-320 wearing a different coat.

Retry is the framework's: a body that raises is marked failed by
`core.jobs.run_job` and re-raised, so Celery's backoff-with-jitter policy
re-delivers the SAME job — never a second row (BR-INT-041, `CELERY_TASK_ACKS_LATE`).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.integrations import models, services
from apps.integrations.adapters.base import TestResult
from apps.integrations.registry import REGISTRY, Manifest, Operation
from apps.integrations.runners import runner_for
from apps.integrations.runners.deliver import RUN_DIRECTION, view_of
from core import jobs as core_jobs

INTEGRATIONS_QUEUE = "integrations"

TEST_JOB = "integration.test"
RUN_JOB = "integration.run"
SWEEP_DUE_JOB = "integration.sweep_due"
SWEEP_EXPIRY_JOB = "integration.sweep_expiry"
INBOUND_PROCESS_JOB = "integration.inbound_process"
JOB_KINDS = (TEST_JOB, RUN_JOB, SWEEP_DUE_JOB, SWEEP_EXPIRY_JOB, INBOUND_PROCESS_JOB)

#: The sentence a clerk reads when a test was queued before the adapter
#: existed — the API refuses the request today (`services.request_test`), so
#: this is the belt for a message already on the queue. ≤ 6 words (rule 33).
NO_ADAPTER_SENTENCE = "This connection cannot be tested yet."
UNREACHABLE_SENTENCE = "The provider could not be reached."


def testable_operation(manifest: Manifest) -> Operation | None:
    """The operation `test()` exercises — the first one declaring a safe
    instance. None means the card reads *cannot be tested until first use*
    (BR-INT-019) and the API refuses the request before a job exists."""
    for one in manifest.operations:
        if one.test_action is not None:
            return one
    return None


def _connection(record: dict[str, Any]) -> models.IntegrationConnection:
    # `core.jobs.run_job` entered THIS tenant's context before calling the body
    # (RLS FORCE hides every other tenant's rows); the explicit filter is the
    # second guard for SQLite.
    return models.IntegrationConnection.objects.get(
        id=record["payload"]["connection_id"], tenant_id=record["tenant_id"]
    )


def run_test_job(record: dict[str, Any]) -> str | None:
    """`integration.test` — one real instance, one run row, one sentence."""
    connection = _connection(record)
    manifest = REGISTRY.require(connection.provider_key)
    operation = testable_operation(manifest)
    if operation is None:
        # Refused at the API; a queued message for it still closes honestly.
        operation = manifest.operations[0]
    run = services.start_run(
        connection=connection,
        operation=operation.name,
        direction=RUN_DIRECTION[(operation.direction, operation.initiative)],
        trigger="manual",
        job_id=record["id"],
    )
    adapter_cls = REGISTRY.adapter_for(connection.provider_key)
    if adapter_cls is None:
        result = TestResult(ok=False, sentence=NO_ADAPTER_SENTENCE)
    else:
        secrets = services.credential_secrets(connection)  # the ONE point (BR-INT-003)
        recipient = record["payload"].get("recipient")
        try:
            # ⚠ THE TEST BUTTON IS DIALLED UNDER THE GUARD TOO, AND THAT IS A
            # CHOICE WORTH READING. A clerk pressing *Test it now* against a
            # mail server that is hanging is the single easiest way to put a
            # worker to sleep for ninety seconds — one click, and it is the
            # click somebody makes precisely BECAUSE the provider is sick. So
            # the test gets the same timeout and the same cap as a bill run.
            outcome = services.guarded_adapter_call(
                connection=connection,
                operation=operation,
                call=lambda _secrets=secrets: adapter_cls().test(
                    view_of(connection), _secrets, recipient=recipient
                ),
            )
        except Exception as exc:  # noqa: BLE001 — a test's failure is its outcome, not a job failure
            result = TestResult(
                ok=False, sentence=UNREACHABLE_SENTENCE, provider_text=services.scrub(str(exc))
            )
        else:
            if outcome.skipped or outcome.timed_out:
                # We did not reach the server, and we say which of the two it
                # was in the sentence the guard produced — *the mail server is
                # not answering* for a breaker that is open, *too many calls at
                # once* for a connection whose slots are full. Never `ok`.
                result = TestResult(ok=False, sentence=outcome.sentence or UNREACHABLE_SENTENCE)
            else:
                result = outcome.value
        finally:
            del secrets
    actor = SimpleNamespace(id=record["payload"].get("actor_user_id"))
    services.record_test_result(actor=actor, connection=connection, run=run, result=result)
    return None


def run_run_job(record: dict[str, Any]) -> str | None:
    """`integration.run` — one manual attempt at one operation's batch."""
    connection = _connection(record)
    manifest = REGISTRY.require(connection.provider_key)
    name = record["payload"]["operation"]
    operation = next(one for one in manifest.operations if one.name == name)
    adapter_cls = REGISTRY.adapter_for(connection.provider_key)
    work = list(record["payload"].get("work") or [])
    if adapter_cls is None:
        # Refused at the API; the belt for a message already queued.
        run = services.start_run(
            connection=connection,
            operation=operation.name,
            direction=RUN_DIRECTION[(operation.direction, operation.initiative)],
            trigger="manual",
            job_id=record["id"],
        )
        services.finish_run(
            run,
            attempted=len(work),
            succeeded=0,
            failed=0,
            skipped=0,
            confirmed=False,
            summary=NO_ADAPTER_SENTENCE,
        )
        return None
    # ⚠ **THE SHAPE OF THE RUN IS READ OFF THE OPERATION, NOT OFF THE PROVIDER**
    # (`CR-069` wave K, `BR-INT-037`). Three shapes and no per-provider branch:
    #
    #   completion == submit_poll_collect  →  they build it while we wait
    #   a fetch plan, and we start it      →  windows × pages, checkpointed
    #   anything else                      →  one attempt, the wave-B shape
    #
    # ⚠ AND WITHOUT THIS BLOCK THE WHOLE OF WAVE K IS DEAD CODE — hard-won law
    # 2. `walk()` and `submit_poll_collect()` would exist, be tested, and be
    # reached by nothing a clerk can press: `POST /integrations/{key}/run`
    # would go on calling the one-attempt runner, the token cache would never
    # be exercised, and every test in the wave would still pass.
    from apps.integrations.runners import fetch as fetch_runner

    payload = record["payload"]
    parameters = dict(payload.get("parameters") or {})
    if operation.completion == "submit_poll_collect":
        fetch_runner.submit_poll_collect(
            connection=connection,
            operation=operation,
            adapter=adapter_cls(),
            parameters=parameters,
            request_key=payload.get("request_key") or None,
            trigger="manual",
            job_id=record["id"],
            progress=core_jobs.record_progress,
        )
        return None
    if operation.fetch_plan is not None and not operation.they_call_us:
        start = _walk_date(payload.get("from"))
        end = _walk_date(payload.get("to"))
        if start is not None and end is not None:
            # ⚠ THE CHECKPOINT IS READ FROM THE RECORD, WHICH IS WHAT MAKES A
            # RESUME A RESUME. `core.jobs.start()` moves a FAILED job back to
            # running and leaves the checkpoint alone precisely so this line
            # can find it; a walk that always began at window 1 would re-fetch
            # two hours of work every time a provider hiccuped.
            checkpoint = record.get("checkpoint")
            reached = 0
            if isinstance(checkpoint, dict):
                reached = int(checkpoint.get("window") or 0)
            fetch_runner.walk(
                connection=connection,
                operation=operation,
                adapter=adapter_cls(),
                start=start,
                end=end,
                parameters=parameters,
                trigger="manual",
                job_id=record["id"],
                resume_from=reached,
                progress=core_jobs.record_progress,
            )
            return None
    runner_for(operation).execute_run(
        connection=connection,
        operation=operation,
        adapter=adapter_cls(),
        work=work,
        trigger="manual",
        job_id=record["id"],
    )
    return None


def _walk_date(value: Any) -> Any:
    """`2024-09-01` off the payload, or `None`.

    ⚠ `None` MEANS *NO WALK WAS ASKED FOR*, and the caller then falls through to
    the one-attempt runner rather than inventing a window. A default of *the
    last seven days* here would be this module deciding WHEN to collect, which
    is scheduling and is Runbooks' under `BR-INT-054` as amended 2026-09-06.
    """
    if not value:
        return None
    parsed = parse_date(str(value))
    return parsed


def run_sweep_expiry_job(record: dict[str, Any]) -> str | None:
    """`integration.sweep_expiry` — the dated warning (US-INT-027, wave H).

    ⚠ **THIS IS THE INVOCATION, NOT THE SCHEDULE.** `expiry.sweep_expiry` is a
    callable; something has to hand it a moment, and today that something is a
    queued job. Under `BR-INT-054` as amended 2026-09-06, deciding that the job
    should be enqueued tonight is **scheduling and belongs to Runbooks** — this
    handler holds no cron, no `next_run_at` and no opinion about nightly. When
    wave G's scheduler moves to Runbooks it will enqueue THIS kind, unchanged.

    `run_at` rides on the payload rather than being read from a clock here, so
    a replay sweeps the moment it was queued for (BR-TEN-043) and a test needs
    no frozen clock.
    """
    from apps.integrations import expiry

    stamped = record["payload"].get("run_at")
    moment = parse_datetime(stamped) if stamped else timezone.now()
    outcome = expiry.sweep_expiry(
        actor=SimpleNamespace(id=record["payload"].get("actor_user_id")),
        now=moment or timezone.now(),
    )
    # The job's own note. Counts only — no provider name, no hint, no date of
    # any one credential, because a job record is read in bulk by support.
    return (
        f"{outcome.looked_at} looked at · {outcome.warned} warned · "
        f"{outcome.already_warned_today} already warned today · {outcome.lapsed} lapsed"
    )


def register() -> None:
    """Both halves of the routing statement, beside the bodies they route.

    Called from `IntegrationsConfig.ready()`. Every kind is routed; only the
    kinds with a body get a handler (see the module docstring).
    """
    core_jobs.set_job_handler(TEST_JOB, run_test_job)
    core_jobs.set_job_handler(RUN_JOB, run_run_job)
    core_jobs.set_job_handler(SWEEP_EXPIRY_JOB, run_sweep_expiry_job)
    for kind in JOB_KINDS:
        core_jobs.set_job_queue(kind, INTEGRATIONS_QUEUE)


__all__ = [
    "INTEGRATIONS_QUEUE",
    "JOB_KINDS",
    "TEST_JOB",
    "RUN_JOB",
    "SWEEP_DUE_JOB",
    "SWEEP_EXPIRY_JOB",
    "INBOUND_PROCESS_JOB",
    "register",
    "run_test_job",
    "run_run_job",
    "run_sweep_expiry_job",
    "testable_operation",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-016@62d3643 (EP-INT-05 story + BR-INT-018..053 snapshot; co-packet US-INT-015@62d3643)
# generated: 2026-09-03 by the CR-069 wave B build lane
# checklist: A✔ B✔ C✔ D✔(POST /integrations/{key}/test and /run enqueue these kinds) E✔(the modal's Test it now shows the 202's poll) F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_016_queue.py · G80 (routing ⇄ celery-integrations consumer; default worker not draining it; entrypoint cleared; healthcheck form) · G77
# exceptions: three of the five kinds are routed with no body until their waves (G, H, N) — a message for one fails by name at run_pending rather than being swallowed
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
