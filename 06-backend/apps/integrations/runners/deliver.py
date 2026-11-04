# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-016 (EP-INT-05) — the runtime around one adapter call, in
#           a different process from the request. US-INT-015 (the four
#           methods it calls). Screens: S142 (the run row this writes)
# Rules:    BR-INT-038 (the adapter translates; the runtime owns the run row,
#           the counts and the secret's lifetime) · BR-INT-018 (the outcome
#           word is computed from the counts by `services.finish_run`, never
#           typed here or by an adapter) · BR-INT-003 (the plaintext exists in
#           memory for the length of one call and is dropped) · BR-INT-041
#           (retry is the framework's — a failed attempt re-raises so Celery's
#           backoff-with-jitter sees it; never a new job)
# Tests:    06-backend/tests/test_us_int_016_queue.py · test_us_int_015_adapters.py
# Impacts:  apps/integrations/jobs.py (calls `execute_run`) · services.py
#           (`start_run` · `finish_run` · `credential_secrets`)
# ───────────────────────────────────────────────────────
"""DELIVER — we send them something (`out · us`): bills to a mail server, a file to a folder.

One attempt at one batch: open the run row, build the view, hold the secrets
for exactly the length of `adapter.execute()`, close the run row with the
per-item counts. The OUTCOME word is `services.finish_run`'s to choose.

⚠ AN ADAPTER THAT ANSWERS A BOOLEAN IS RECORDED AS `unconfirmed` (US-INT-015
TC-3). `True` says nothing about how many the far end accepted, and *"the
provider did not say how many"* is the honest sentence; the conformance kit
fails such an adapter before it is ever registered, and this is the second
guard for the one that slipped through.

Retry: an exception out of the adapter propagates. `core.jobs.run_job` marks
the job failed and re-raises, Celery's retry policy sees it and re-delivers
with backoff and jitter — the same job id, never a second job row (BR-INT-041,
`CELERY_TASK_ACKS_LATE`). The run row for the failed attempt is closed first,
so every attempt is a durable record (BR-INT-039).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from apps.integrations import models, services
from apps.integrations.adapters.base import Adapter, ConnectionView, RunResult
from apps.integrations.registry import Operation
from apps.integrations.runtime import ProviderTimeout

#: Manifest direction × initiative → the run row's direction word.
RUN_DIRECTION = {
    ("out", "us"): models.RUN_DIRECTION_OUTBOUND,
    ("in", "us"): models.RUN_DIRECTION_INBOUND,
    ("out", "them"): models.RUN_DIRECTION_INBOUND_READ,
    ("in", "them"): models.RUN_DIRECTION_INBOUND,
}


def view_of(connection: models.IntegrationConnection) -> ConnectionView:
    """What the adapter may see. No secret is on the connection row to leak."""
    return ConnectionView(
        provider_key=connection.provider_key,
        environment=connection.environment,
        config=dict(connection.config or {}),
        label=connection.label,
    )


def execute_run(
    *,
    connection: models.IntegrationConnection,
    operation: Operation,
    adapter: Adapter,
    work: Sequence[Mapping[str, Any]],
    trigger: str,
    job_id: Any = None,
) -> models.IntegrationRun:
    """One attempt. Returns the closed run row."""
    run = services.start_run(
        connection=connection,
        operation=operation.name,
        direction=RUN_DIRECTION[(operation.direction, operation.initiative)],
        trigger=trigger,
        job_id=job_id,
    )
    secrets = services.credential_secrets(connection)  # the ONE point (BR-INT-003)
    try:
        # ⚠ EVERY DIAL GOES THROUGH THE GUARD (`BR-INT-022`, `BR-INT-041`).
        # Calling `adapter.execute` directly here is what `DEF-INT-4015` was:
        # correct policy in `runtime.py` with no caller, so one utility's
        # ninety-second hang held a worker every other utility was queueing for.
        outcome = services.guarded_adapter_call(
            connection=connection,
            operation=operation,
            # ⚠ BOUND AS A DEFAULT, NOT CLOSED OVER. `finally` below deletes
            # `secrets` (BR-INT-003 — the plaintext lives for one call), and a
            # closure would read the name AFTER that `del` if anything ever
            # called this lambda late. Binding it here means the value is
            # captured now and dies with the lambda.
            call=lambda _secrets=secrets: adapter.execute(view_of(connection), _secrets, work),
        )
    except Exception as exc:  # noqa: BLE001 — recorded, then re-raised for the framework's retry
        services.finish_run(
            run,
            attempted=len(work),
            succeeded=0,
            failed=0,
            skipped=0,
            confirmed=False,
            summary="The provider could not be reached.",
            provider_error=services.scrub(str(exc)),
        )
        raise
    finally:
        del secrets
    if outcome.skipped:
        # The breaker is open, or every slot on this connection is busy. The
        # call was NEVER PLACED, so the row says `skipped` and carries the
        # reason in words (`BR-INT-024`). It is deliberately not re-raised:
        # retrying a connection we are refusing to dial is the retry storm the
        # breaker exists to prevent.
        return services.finish_run(
            run,
            attempted=0,
            succeeded=0,
            failed=0,
            skipped=0,
            confirmed=True,
            never_dialled=True,
            summary=outcome.sentence,
        )
    if outcome.timed_out:
        # We stopped waiting. Whether the far end took the batch is UNKNOWN,
        # and `indeterminate` is the word for that (`BR-INT-052`) — never
        # `failed`, which would claim we know it did not. Re-raised so the
        # framework retries with backoff and jitter.
        services.finish_run(
            run,
            attempted=len(work),
            succeeded=0,
            failed=0,
            skipped=0,
            confirmed=False,
            indeterminate=True,
            summary=outcome.sentence,
        )
        raise ProviderTimeout(outcome.sentence or "the provider did not answer") from None
    result = outcome.value
    if not isinstance(result, RunResult):
        # TC-3: a boolean is not a count. Unconfirmed, and the sentence says why.
        return services.finish_run(
            run,
            attempted=len(work),
            succeeded=0,
            failed=0,
            skipped=0,
            confirmed=False,
            summary="The provider did not say how many it accepted.",
        )
    counts = result.counts
    return services.finish_run(
        run,
        confirmed=result.confirmed,
        summary=None,
        provider_error=services.scrub(result.provider_text) if result.provider_text else None,
        **counts,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-016@62d3643 (EP-INT-05 story + BR-INT-018..053 snapshot; co-packet US-INT-015@62d3643)
# generated: 2026-09-03 by the CR-069 wave B build lane
# checklist: A✔ B✔ C✔ D✔(reached from POST /integrations/{key}/run through the job body) E=deferred(S142 draws the run rows in wave C) F✔ G✔ H=n/a
# gates: pytest tests/test_us_int_016_queue.py · G77 (no provider_key branch)
# exceptions: `summary` for a confirmed run is None here — wave C's C1 owns the plain-language sentence (*86 of 93 · 7 bad addresses*) and the scrubbing rule for provider_error (scrub() is a placeholder that masks nothing yet — stated, not implied)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
