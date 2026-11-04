# ── Trace ──────────────────────────────────────────────
# Change:   Export files move from the shared disk to S3 — PO ruling 2026-10-02
#           (decision log "EXPORT FILES MOVE FROM THE SHARED DISK TO S3 — THE
#           DESIGN IS APPROVED"): *"Once a day, for each utility, the system
#           deletes exports older than that utility's own setting (3 days by
#           default) … but make sure that you don't delete any other data"*.
# Defect:   DEF-TEN-9146 (the rule kept: a utility is required, no all-utilities form)
# Rules:    BR-REP-018 (retention, tenant-configurable) · CLAUDE.md rule 1
# Tests:    06-backend/tests/test_s3a_export_sweep.py
# ───────────────────────────────────────────────────────
"""The daily export clean-up: one celery-beat firing, one task per utility.

It replaces *"delete on the next export"* — the old sweep ran only when
somebody exported, so a utility that stopped exporting kept its files for ever,
and two of its three callers swept every utility at once (`DEF-TEN-9146`).

The shape is `apps/identity/session_cleanup.py`'s, deliberately: a beat entry
that fans out ONE task per live utility, each entering that utility's own
tenant context, each calling `export_store.sweep_tenant(tenant_id)` — which
reads that utility's own `file_retention_days` and can delete nothing outside
`t/<its web name>/export/`. One utility's slow sweep never delays another's.
"""

from __future__ import annotations

import logging
from typing import Any

from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.exports")

BEAT_ENTRY = "tenancy.export_retention_sweep"
SWEEP_TASK = "smartbillhub.tenancy.export_retention_sweep"
SWEEP_ONE_TASK = "smartbillhub.tenancy.export_retention_sweep_one"

#: 03:47 UTC daily — off the hour and the half hour, which is where every
#: other scheduled job queues (the routine-scheduling convention), and after
#: the identity session sweep's 03:20.
SWEEP_HOUR = 3
SWEEP_MINUTE = 47

# ── DEF-TEN-9190 — an export that stops writing is FAILED, with a reason ──────
# A job record says `running` until its body says otherwise, and a body that
# hangs, or a process that is killed, says nothing at all (`core.jobs.reclaim`
# argues the general case). On 2026-10-02 a real deployment's Premises export
# built 73 rows and then sat in `running` with no log line. Every ten minutes
# this finds an EXPORT job (the downloadable kinds only — never a bill run)
# whose record has not been written for `EXPORT_STALL_SECONDS` (30 minutes by
# default) and fails it with a sentence a clerk can read. A list export writes
# progress as it builds and its upload is bounded by the S3 client's own
# timeouts (minutes, `DOCUMENT_STORAGE_*_TIMEOUT`), so thirty idle minutes is
# never a live export.
STALL_ENTRY = "tenancy.export_stall_sweep"
STALL_TASK = "smartbillhub.tenancy.export_stall_sweep"
STALL_ONE_TASK = "smartbillhub.tenancy.export_stall_sweep_one"
STALL_EVERY_MINUTES = 10
STALLED_ERROR = "ExportStalled: The export stopped responding."

_SWEEP_TASK: Any = None
_SWEEP_ONE_TASK: Any = None
_STALL_TASK: Any = None
_STALL_ONE_TASK: Any = None


def stall_seconds() -> int:
    """How long an export job may go unwritten before it is failed (setting, default 1800)."""
    from django.conf import settings

    return max(60, int(getattr(settings, "EXPORT_STALL_SECONDS", 1800) or 1800))


def fail_stalled_one(subdomain: str, *, now: Any = None) -> dict[str, Any]:
    """Fail ONE utility's stalled export jobs, inside its own tenant context."""
    import datetime as dt

    from django.utils import timezone

    from apps.tenancy import exports
    from apps.tenancy import models as tenancy_models
    from core import jobs as core_jobs

    tenant_id = core_tenancy.tenant_id_for_slug(subdomain)
    if tenant_id is None:
        return {"subdomain": subdomain, "failed": 0, "reason": "no such utility"}
    moment = now or timezone.now()
    cutoff = moment - dt.timedelta(seconds=stall_seconds())
    failed = 0
    with core_tenancy.tenant_context(tenant_id):
        stalled = tenancy_models.Job.objects.filter(
            tenant_id=tenant_id,
            status=core_jobs.RUNNING,
            kind__in=exports.downloadable_kinds(),
            updated_at__lt=cutoff,
        ).values_list("id", "kind", "updated_at")
        for job_id, kind, updated_at in list(stalled):
            try:
                core_jobs.fail(str(job_id), error=STALLED_ERROR)
            except core_jobs.JobsError:
                continue  # it finished between the read and the write — fine
            failed += 1
            logger.error(
                "export %s (%s) for %s: no progress since %s, longer than %s s - "
                "marked FAILED (%s). Look in the celery log for this job id: the last "
                "stage it reached is the one that hung.",
                job_id, kind, subdomain, updated_at.isoformat(), stall_seconds(), STALLED_ERROR,
            )
    return {"subdomain": subdomain, "failed": failed}


def fail_stalled_all() -> dict[str, Any]:
    """ONE firing: each live utility gets its own stall check."""
    subdomains = _live_subdomains()
    if _STALL_ONE_TASK is None:
        return {
            "utilities": len(subdomains),
            "fanned_out": False,
            "results": [fail_stalled_one(subdomain) for subdomain in subdomains],
        }
    for subdomain in subdomains:
        _STALL_ONE_TASK.delay(subdomain)
    return {"utilities": len(subdomains), "fanned_out": True}


def sweep_one(subdomain: str) -> dict[str, Any]:
    """ONE utility's clean-up, inside its own tenant context."""
    from apps.tenancy import export_store

    tenant_id = core_tenancy.tenant_id_for_slug(subdomain)
    if tenant_id is None:
        return {"subdomain": subdomain, "swept": False, "reason": "no such utility"}
    with core_tenancy.tenant_context(tenant_id):
        result = export_store.sweep_tenant(tenant_id)
    logger.info(
        "export sweep %s: %s deleted, %s orphan(s), %s refused",
        subdomain,
        result.deleted,
        result.orphans,
        result.refused,
    )
    return {
        "subdomain": subdomain,
        "swept": True,
        "deleted": result.deleted,
        "orphans": result.orphans,
        "refused": result.refused,
    }


def _live_subdomains() -> tuple[str, ...]:
    from apps.tenancy import selectors

    try:
        return tuple(str(entry) for entry in (selectors.live_tenant_subdomains() or ()))
    except Exception:  # noqa: BLE001 — a broken read must not stop the beat
        logger.exception("the live-utility read failed; this firing swept nobody")
        return ()


def sweep_all() -> dict[str, Any]:
    """ONE firing: hand every live utility its own sweep (never one sweep of all)."""
    subdomains = _live_subdomains()
    if _SWEEP_ONE_TASK is None:
        return {
            "utilities": len(subdomains),
            "fanned_out": False,
            "results": [sweep_one(subdomain) for subdomain in subdomains],
        }
    for subdomain in subdomains:
        _SWEEP_ONE_TASK.delay(subdomain)
    return {"utilities": len(subdomains), "fanned_out": True}


def beat_schedule() -> dict[str, dict[str, Any]]:
    """The beat entry, as DATA — assertable without a broker."""
    try:
        from celery.schedules import crontab

        when: Any = crontab(hour=SWEEP_HOUR, minute=SWEEP_MINUTE)
        every: Any = crontab(minute=f"*/{STALL_EVERY_MINUTES}")
    except Exception:  # noqa: BLE001 — celery absent; see install()
        when = {"hour": SWEEP_HOUR, "minute": SWEEP_MINUTE}
        every = {"minute": f"*/{STALL_EVERY_MINUTES}"}
    return {
        BEAT_ENTRY: {
            "task": SWEEP_TASK,
            "schedule": when,
            "args": (),
            "options": {"expires": None},
        },
        STALL_ENTRY: {
            "task": STALL_TASK,
            "schedule": every,
            "args": (),
            # A firing that waited longer than its own interval is stale; the
            # next one covers it.
            "options": {"expires": STALL_EVERY_MINUTES * 60},
        },
    }


def install(app: Any = None) -> dict[str, Any]:
    """Register the two tasks and the beat entry. Idempotent; no broker needed."""
    if app is None:
        try:
            from config.celery import app as celery_app
        except Exception as problem:  # noqa: BLE001 — see session_cleanup.install
            logger.info("the export sweep was not installed: celery is not available (%s)", problem)
            return {"installed": False, "reason": str(problem)}
        app = celery_app
    # ⚠ KEEP THE RESULT: `app.task(...)(fn)` returns the task object; the plain
    # function has no `.delay` and the fan-out would run inline in beat.
    global _SWEEP_TASK, _SWEEP_ONE_TASK, _STALL_TASK, _STALL_ONE_TASK
    _SWEEP_ONE_TASK = app.task(name=SWEEP_ONE_TASK, bind=False)(sweep_one)
    _SWEEP_TASK = app.task(name=SWEEP_TASK, bind=False)(sweep_all)
    _STALL_ONE_TASK = app.task(name=STALL_ONE_TASK, bind=False)(fail_stalled_one)
    _STALL_TASK = app.task(name=STALL_TASK, bind=False)(fail_stalled_all)
    schedule = beat_schedule()
    existing = dict(getattr(app.conf, "beat_schedule", None) or {})
    existing.update(schedule)
    app.conf.beat_schedule = existing
    return {"installed": True, "entry": BEAT_ENTRY, "schedule": schedule}


__all__ = [
    "BEAT_ENTRY",
    "STALL_ENTRY",
    "beat_schedule",
    "fail_stalled_all",
    "fail_stalled_one",
    "install",
    "sweep_all",
    "sweep_one",
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: exports-to-S3 build step 6 (09-infra/04-exports-to-s3.md §6)
# generated: 2026-10-02 by the s3a lane
# checklist: A✔ B✔ C✔ D=n/a(no API) E=n/a F✔ G✔ H=n/a
# gates: tests/test_s3a_export_sweep.py
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
