# ── Trace ──────────────────────────────────────────────
# Change:   CR-183-BRC10 T4 — a temporary stop starts and ends on its dates by
#           itself (PO rulings B1–B4, 2026-10-14).
# Rules:    BR-CUS-1120 · BR-TEN-043 (beat owns a DURATION; the moment is the
#           utility's own business day, named by `seams.tenant_today()`) ·
#           CLAUDE.md hard rule 1 (every read and write inside
#           `tenant_context`) · hard-won law 2 (built is not wired — `apps.py`
#           calls `install()`, and G132 reads that call)
# Tests:    06-backend/tests/test_cr183_temporary_stop.py
# Impacts:  apps/customers/apps.py (`ready()` installs the entry) ·
#           apps/customers/temporary_stop.py (`apply_due`, the one mover)
# ───────────────────────────────────────────────────────
"""The temporary-stop clock — once a day, per utility, `temporary_stop.apply_due`.

The SHAPE is `disconnect_schedule`'s, deliberately: one fan-out task on the
shared queue that hands each live utility its own task, each of which enters
that utility's `tenant_context` and asks `apply_due(as_of=<its business day>)`.

⚠ **IDEMPOTENT, SO A SECOND FIRING IS HARMLESS.** `apply_due` moves a hold only
out of the status it is due to leave (`scheduled → on_hold`,
`on_hold → ended`), each under a row lock, so the same day fired twice writes
nothing the second time — and a firing missed for a day catches up on the next
(`stop_from <= today`, `restart_on <= today`).

⚠ **THE DAY IS THE UTILITY'S.** A hold due back on 16 Oct ends on 16 Oct in
the utility's own zone (BR-TEN-043), never on the server's UTC date.
"""

from __future__ import annotations

import logging
import os
from datetime import date
from importlib import import_module
from typing import Any

logger = logging.getLogger("smartbillhub.customers.temporary_stop_schedule")

ONE_TASK = "smartbillhub.customers.temporary_stop_clock"
FANOUT_TASK = "smartbillhub.customers.temporary_stop_clock_all"
BEAT_ENTRY = "customers.temporary_stop_clock"
DEFAULT_EVERY_SECONDS = 60 * 60
EVERY_SECONDS_ENV = "TEMPORARY_STOP_CLOCK_EVERY_SECONDS"

_ONE: Any = None


def every_seconds() -> int:
    """HOURLY by default, so a hold due today moves within the hour after the
    utility's midnight rather than up to a day late; a bad value falls back."""
    raw = os.environ.get(EVERY_SECONDS_ENV, "").strip()
    try:
        seconds = int(raw) if raw else DEFAULT_EVERY_SECONDS
    except ValueError:
        seconds = 0
    return seconds if seconds > 0 else DEFAULT_EVERY_SECONDS


def beat_schedule(*, seconds: int | None = None) -> dict[str, dict[str, Any]]:
    return {
        BEAT_ENTRY: {
            "task": FANOUT_TASK,
            "schedule": float(seconds if seconds is not None else every_seconds()),
            "args": (),
            "options": {"expires": None},
        }
    }


def install(app: Any = None) -> dict[str, Any]:
    """Register both tasks and add the beat entry. Never raises: a deployment
    without celery logs `installed: False` and the application starts."""
    if app is None:
        try:
            from config.celery import app as celery_app
        except Exception as problem:  # noqa: BLE001 - see the docstring
            logger.info("the temporary-stop clock was not installed: %s", problem)
            return {"installed": False, "reason": str(problem)}
        app = celery_app
    global _ONE
    _ONE = app.task(name=ONE_TASK, bind=False)(run_one)
    app.task(name=FANOUT_TASK, bind=False)(run_all)
    schedule = beat_schedule()
    existing = dict(getattr(app.conf, "beat_schedule", None) or {})
    existing.update(schedule)
    app.conf.beat_schedule = existing
    return {"installed": True, "entry": BEAT_ENTRY, "schedule": schedule}


def run_all() -> dict[str, Any]:
    """Hand every live utility its own firing (the cut-date watch's list)."""
    from apps.customers import disconnect_schedule

    subdomains = disconnect_schedule.watched_subdomains()
    for subdomain in subdomains:
        try:
            if _ONE is not None:
                _ONE.delay(subdomain)
            else:
                run_one(subdomain)
        except Exception:  # noqa: BLE001 - one tenant's broker error is not all of them
            logger.exception("could not hand %s its temporary-stop clock", subdomain)
    return {"tenants": list(subdomains), "dispatched": len(subdomains)}


def run_one(subdomain: str, *, as_of: date | None = None) -> dict[str, Any]:
    """One utility: enter its tenant, name its business day, move what is due."""
    from core import tenancy as core_tenancy

    selectors = import_module("apps.tenancy.selectors")
    tenant_id = selectors.tenant_id_for_subdomain(subdomain)
    if tenant_id is None:
        logger.error("the temporary-stop clock has no utility called %r", subdomain)
        return {"subdomain": subdomain, "ran": False, "reason": "unknown_tenant"}
    with core_tenancy.tenant_context(tenant_id):
        from apps.customers import temporary_stop

        report = temporary_stop.apply_due(as_of=as_of)
    return {"subdomain": subdomain, "ran": True, **report}
