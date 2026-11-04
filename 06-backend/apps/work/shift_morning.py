# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-10615 — End shift left the technician off on the board the
#           next day (decision log 2026-10-26, PO *"yes reset each morning, and
#           use web words — start"*).
# Rules:    BR-WRK-069 (End shift) · CLAUDE.md hard rules 1 (one tenant context
#           per utility, never a cross-tenant queryset) and 7 (each return is
#           audited) · hard-won law 2 (a schedule that is correct and one that
#           is INSTALLED are two claims — `apps.py` installs it)
# Tests:    06-backend/tests/test_def_wrk_10615_shift_morning_return.py
# Impacts:  apps/work/apps.py (the `ready()` wiring) · apps/work/shifts.py
#           (`morning_return`, the body)
# ───────────────────────────────────────────────────────
"""`work.shift_morning_return` — the morning half of End shift.

End shift (`CR-193-BRC10`) sets a technician *off today*; this returns them to
*on shift* at the start of their next working day, so the dispatch board does
not keep showing them off. The rule itself is `shifts.morning_return`'s.

WHY HOURLY AND NOT ONCE A DAY AT A FIXED HOUR: each utility has its own time
zone and *the start of the day* is local midnight there. An hourly firing
reaches every utility within the first hour of its own day, and the body is
idempotent (a returned End shift is settled), so the other twenty-three runs
of the day change nothing. The fan-out is the escalation sweep's: one job per
live utility, each entering that utility's own tenant context.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone as dt_timezone
from importlib import import_module
from typing import Any

from core import jobs as core_jobs
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.work.shift_morning")

MORNING_RETURN_JOB = "work.shift_morning_return"
WORK_QUEUE = "work"
BEAT_ENTRY = "work.shift_morning_return"
SWEEP_TASK = "work.shift_morning_return.all"
SWEEP_EVERY_SECONDS = 60 * 60


def run_morning_return_job(record: dict[str, Any]) -> dict[str, Any]:
    from apps.work import shifts

    payload = dict(record.get("payload") or {})
    tenant_id = record.get("tenant_id") or payload.get("tenant_id")
    with core_tenancy.tenant_context(tenant_id):
        return shifts.morning_return()


def scope_key(tenant_id: Any, when: datetime | None = None) -> str:
    """One run per utility per HOUR (`core.jobs` folds a duplicate firing)."""
    moment = when or datetime.now(dt_timezone.utc)
    return f"{tenant_id}:{MORNING_RETURN_JOB}:{moment.strftime('%Y-%m-%dT%H')}"


def beat_schedule(*, every_seconds: int | None = None) -> dict[str, dict[str, Any]]:
    return {
        BEAT_ENTRY: {
            "task": SWEEP_TASK,
            "schedule": float(every_seconds if every_seconds is not None else SWEEP_EVERY_SECONDS),
            "args": (),
            "options": {"expires": None},
        }
    }


def sweep_all_tenants() -> dict[str, Any]:
    """ONE firing: enqueue a morning return for every live utility."""
    try:
        listed = import_module("apps.tenancy.selectors").live_tenant_subdomains()
    except Exception:  # noqa: BLE001 — a broken read must not stop the beat
        logger.exception("the live-utility read failed; no morning return this hour")
        return {"tenants": 0, "queued": []}
    queued: list[str] = []
    for slug in listed or ():
        tenant_id = core_tenancy.tenant_id_for_slug(str(slug))
        if tenant_id is None:
            continue
        with core_tenancy.tenant_context(tenant_id):
            record = core_jobs.enqueue(
                MORNING_RETURN_JOB,
                scope_key=scope_key(tenant_id),
                payload={"tenant_id": str(tenant_id)},
            )
        queued.append(str(record["id"]))
    return {"tenants": len(queued), "queued": queued}


_SWEEP_ALL_TASK: Any = None


def install(app: Any = None) -> dict[str, Any]:
    """Register the beat entry and the fan-out task. Idempotent; never raises
    (a deployment without celery starts — `rules.install`'s reasoning)."""
    if app is None:
        try:
            from config.celery import app as celery_app
        except Exception as problem:  # noqa: BLE001
            return {"installed": False, "reason": str(problem)}
        app = celery_app
    global _SWEEP_ALL_TASK
    _SWEEP_ALL_TASK = app.task(name=SWEEP_TASK, bind=False)(sweep_all_tenants)
    schedule = beat_schedule()
    existing = dict(getattr(app.conf, "beat_schedule", None) or {})
    existing.update(schedule)
    app.conf.beat_schedule = existing
    return {"installed": True, "entry": BEAT_ENTRY, "schedule": schedule}


def register() -> None:
    core_jobs.set_job_handler(MORNING_RETURN_JOB, run_morning_return_job)
    core_jobs.set_job_queue(MORNING_RETURN_JOB, WORK_QUEUE)


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-WRK-10615 · decision log 2026-10-26 (*"yes reset each morning"*)
# generated: 2026-10-26 by the morning-return lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint) E=n/a(no screen) F✔ G✔ H✔(`work/0055`, ledger row)
# gates: G78 · G109 (the `work` queue) · pytest on SQLite and PostgreSQL 16
# status: AI-AUTHORED
# ──────────────────────────────────────────────────────────
