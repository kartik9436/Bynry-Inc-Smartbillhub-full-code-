# ── Trace ──────────────────────────────────────────────
# Component: BE-07 jobs framework — THE ROUTING HALF of billing's named queue.
# Change:   CR-051 task 29 (PO ruling 2026-08-31), verbatim: *"we will ahve to
#           create named worker for billing - eventually we should able to scale
#           these works on the fly itf required; but billing will need its own
#           named workers - otherwise it will slow down the system"*
#           (12-governance/02-decision-log.md).
# Defect:   DEF-320 (four job kinds enqueued and production dispatched none of
#           them — the shape a route with no consumer recreates exactly)
# Contract: TD-17 (async = Celery on Redis) · B12 r1 §3 (202 + job_id)
# Rules:    CLAUDE.md hard-won law 2 (built is not wired) · law 7 (prove a guard
#           RED first)
# Tests:    06-backend/tests/test_cr051_billing_queue.py
# Impacts:  config/settings/base.py (CELERY_TASK_ROUTES) · apps/tenancy/tasks.py
#           (the message carries the kind so this can read it) ·
#           docker-compose.yml (the CONSUMER half — `celery-billing`) ·
#           10-scripts/gates/g59_billing_queue_split.py
# ───────────────────────────────────────────────────────
"""Which named queue does this message belong on? Ask the job kind.

WHY A ROUTER FUNCTION AND NOT A `{task name: queue}` DICT
---------------------------------------------------------
The usual Celery shape is `task_routes = {"app.tasks.heavy": {"queue": "heavy"}}`.
**It cannot work here, and the reason is a deliberate design decision made by
the transport lane in 2026-08-19 that is still right.** This deployment runs
ONE task for EVERY job kind — `apps.tenancy.tasks.run_pending_job`, whose own
docstring explains why: *"`core.jobs.run_pending(job_id)` loads the record,
reads its `kind`, and looks the BODY up in the handler registry… A task per kind
would duplicate that registry in a second place."* So every message in this
product has the same task name, and a name-keyed dict would route a bill run and
a CSV export identically.

A router function is Celery's own answer to that: it is handed the task name,
the args and the kwargs, and returns the route. The KIND travels in the message
(`apps.tenancy.tasks.send` puts it there) purely so this function can read it.

⚠ **THE KIND IN THE MESSAGE IS FOR ROUTING AND FOR NOTHING ELSE.** The worker
still reads the kind from the RECORD, which is the truth (B12 r1). If the two
ever disagreed — an impossible state today, since one function writes both — the
record wins and the only cost is a message on the wrong queue. Nothing decides
what work is done from this value.

WHERE THE MAP LIVES, AND WHY NOT HERE
-------------------------------------
`core.jobs.job_queue(kind)`. The kind→queue pairs are registered by the module
that OWNS the work, in its own `AppConfig.ready()`, exactly as its job BODY is
(`core.jobs.set_job_handler`). Putting the pairs in this file would mean billing
renames a kind in `apps/billing/run_jobs.py` and the routing silently keeps
pointing at the old string — a class of drift this repo has recorded more than
once. A kind with no registered queue returns None and rides the default queue,
which is what every kind did before CR-051 task 29.

⚠ **THIS FILE IS ONE HALF OF A QUEUE.** The other half is a worker consuming it
(`docker-compose.yml` → `celery-billing`, `-Q billing`). Ship the routing alone
and a bill run is enqueued where nothing drains it: accepted, `queued`, for
ever. `G59` refuses a tree with one half and not the other.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("smartbillhub.jobs")

#: The one task every BE-07 job rides. Pinned as a literal here rather than
#: imported from `apps.tenancy.tasks`: a router is consulted from inside
#: `apply_async`, and importing an app module from a routing hook is an import
#: cycle waiting to happen. `tests/test_cr051_billing_queue.py` asserts the two
#: literals are the same string, so a rename cannot leave this one behind — which
#: is the whole risk of pinning it.
RUN_PENDING_TASK = "smartbillhub.jobs.run_pending"


def route_job(
    name: str,
    args: tuple[Any, ...] | None = None,
    kwargs: dict[str, Any] | None = None,
    options: dict[str, Any] | None = None,
    task: Any = None,
    **_ignored: Any,
) -> dict[str, str] | None:
    """Celery router: `{"queue": …}` for a kind with a named queue, else None.

    Returning None means *"I have no opinion"* — Celery falls through to the
    next router and finally to `CELERY_TASK_DEFAULT_QUEUE`. That is the correct
    failure mode and it is chosen deliberately: if this function ever stops
    recognising a kind, the job lands on the default queue where the default
    worker will run it. Slower and un-capped, which is exactly where this
    product was on 2026-08-30 — never lost.
    """
    if name != RUN_PENDING_TASK:
        return None
    kind = (kwargs or {}).get("kind")
    if not kind:
        return None
    # Imported at CALL time, not module scope: settings are read before the app
    # registry is ready, and this module is named in `CELERY_TASK_ROUTES`.
    from core import jobs as core_jobs

    queue = core_jobs.job_queue(str(kind))
    if not queue:
        return None
    logger.debug("celery: routing %s to the %r queue", kind, queue)
    return {"queue": queue}


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-051 task 29 (PO ruling 2026-08-31) + BE-07 kernel core/jobs.py
# generated: 2026-08-31 by story-coder (CR-051 task 29 named-billing-worker lane)
# checklist: A✔ B=deferred(no-API-half — this is ROUTING: it adds no endpoint and changes no response) C✔ D=deferred(no-API-half, as above) E=deferred(no-frontend-half — a screen polls the job RECORD, so which queue carried the message is invisible to it) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see 06-backend/tests/test_cr051_billing_queue.py's trailer
# exceptions: the task name is pinned as a literal here AND in apps/tenancy/tasks.py; a test asserts they are equal, because a router that imports an app module is an import cycle and a router that silently stops matching is a cap that silently stops applying
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
