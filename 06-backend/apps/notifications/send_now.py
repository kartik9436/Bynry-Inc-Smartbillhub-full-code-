# ── Trace ──────────────────────────────────────────────
# Change:   CR-188-BRC10 — PO 2026-10-22, decision log *"Account-access emails
#           are sent instantly, at the highest priority"*
# Rules:    BR-NOT-005 (one dispatch path; retries bounded) · BR-NOT-009
#           (quiet hours — NARROWED by that ruling for account-access rows) ·
#           CLAUDE.md hard rule 1 (the job runs under its record's tenant)
# Tests:    06-backend/tests/test_cr188_send_now.py
# Impacts:  services.send_now (the seam) · dispatcher.dispatch_messages ·
#           config/celery_routes.py (reads the queue registry) ·
#           docker-compose.yml `celery-account-access` (`-Q account_access`)
# ───────────────────────────────────────────────────────
"""The immediate send of an account-access email, as ONE background job.

`services.send_now` registers, on commit, `enqueue_send_now` — which writes a
`notifications.send_now` job record and hands it to the transport. The job body
`run_send_now_job` calls `dispatcher.dispatch_messages` for exactly the named
rows: the dispatcher's own route, claim, render, freeze, hand-off and audit,
with the quiet-hours hold skipped (the ruling's narrowing).

⚠ **A NAMED QUEUE IS TWO HALVES** (`core.jobs.set_job_queue`'s own warning,
`G59`): the routing is registered here and the CONSUMER is
`docker-compose.yml`'s `celery-account-access` service, `-Q account_access`.
**Law 4: a host already running does not get that service from this commit** —
its compose file / task definitions must add it, or every job rests `queued`
and the ordinary cycle (which claims these rows first, by priority) delivers
them on its next tick instead of at once.

Why its own queue: the ruling — *"no latency"* — cannot be kept on a queue a
bill run or a large export can fill; a sign-in link a person is waiting for
would sit behind them.
"""

from __future__ import annotations

import logging
from typing import Any

from django.utils import timezone

from core import jobs as core_jobs
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.notifications")

SEND_NOW_JOB = "notifications.send_now"
ACCOUNT_ACCESS_QUEUE = "account_access"


def enqueue_send_now(tenant_id: Any, message_ids: list[str], *, actor_user_id: Any = None) -> None:
    """Write and dispatch the job. Never raises — see `services.send_now`."""
    payload = {"message_ids": list(message_ids), "actor_user_id": str(actor_user_id or "") or None}
    try:
        if str(core_tenancy.current_tenant_id() or "") == str(tenant_id):
            core_jobs.enqueue(SEND_NOW_JOB, payload=payload)
        else:
            with core_tenancy.tenant_context(tenant_id):
                core_jobs.enqueue(SEND_NOW_JOB, payload=payload)
    except Exception:  # noqa: BLE001 — the ordinary cycle is the fallback, by ruling
        logger.exception(
            "notifications.send_now: could not enqueue the immediate send of %s; the rows "
            "stay queued at the highest priority for the next dispatch cycle",
            message_ids,
        )


def run_send_now_job(record: dict[str, Any]) -> str | None:
    """The body: dispatch exactly these rows, now, under the record's tenant."""
    from apps.notifications import dispatcher

    ids = tuple(record.get("payload", {}).get("message_ids") or ())
    result = dispatcher.dispatch_messages(ids, now=timezone.now(), job=SEND_NOW_JOB)
    sent = sum(batch.sent for batch in result.batches)
    codes = sorted({str(problem.get("code")) for problem in result.problems if problem.get("code")})
    return f"{sent} of {len(ids)} sent" + (f" · {', '.join(codes)}" if codes else "")


def register() -> None:
    """Both halves of the routing statement, beside the body they route.
    Called from `NotificationsConfig.ready()`."""
    core_jobs.set_job_handler(SEND_NOW_JOB, run_send_now_job)
    core_jobs.set_job_queue(SEND_NOW_JOB, ACCOUNT_ACCESS_QUEUE)


__all__ = ["ACCOUNT_ACCESS_QUEUE", "SEND_NOW_JOB", "enqueue_send_now", "register"]
