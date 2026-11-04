# ── Trace ──────────────────────────────────────────────
# Change:   CR-145-BRC08 task B10 — the nightly sweep of dead session rows.
# Rules:    BR-IDN-006 (sessions are server-side rows; revocation immediate) ·
#           BR-IDN-026 (the utility's own hard limit decides when a row is
#           dead) · CLAUDE.md rule 1 (tenant context per tenant, never a
#           cross-tenant queryset) · B1 module boundary (identity deletes
#           `sessions`; the portal deletes `portal_session`, through its own
#           published function, resolved BY NAME) · hard-won law 2 (a schedule
#           that is correct and a schedule that is INSTALLED are two claims)
# Tests:    06-backend/tests/test_cr145_session_settings.py — the four `test_t9_*`
#           cases (this line named a separate "session cleanup" test file that never
#           existed until the backend lane checked it, 2026-09-28)
# Impacts:  apps/identity/apps.py (the `ready()` call is the wiring) ·
#           docker-compose.yml's beat service · apps/portal/session.py
# ───────────────────────────────────────────────────────
"""Delete session rows that are finished with. Nightly, per utility.

**NOTHING HAS EVER DELETED A SESSION ROW IN THIS PRODUCT.** `sign_out` sets
`revoked_at`, `revoke_sessions` sets it in bulk, and expiry is a comparison
against `expires_at` that nobody follows up. So `sessions` and
`portal_session` have grown monotonically since the day each shipped, and
every row a customer or a clerk has ever held is still there — which is a
table that only gets slower and a set of device fingerprints and IP addresses
kept for no stated reason.

WHAT IS DELETED, AND IT IS EXACTLY TWO KINDS
─────────────────────────────────────────────
  * **EXPIRED** — `expires_at` is in the past. The hard limit has run out and
    no authentication path will ever accept this row again.
  * **SIGNED OUT** — `revoked_at` is set. The person left, or an admin
    deactivated them, or a password change revoked their other sessions.

⚠ **AND NOTHING ELSE. A LIVE SESSION IS NEVER TOUCHED**, and that is `T9`'s
whole assertion. The failure mode this sweep could have is signing the
product's users out in the middle of the night, so the filter is written as
the UNION of two positive conditions rather than as the negation of *live* —
a `NOT (…)` over three nullable columns is one `OR` away from matching
everything, and on this table that is every session in the product.

⚠ **AN IDLE SESSION IS NOT EXPIRED AND IS NOT DELETED HERE.** Idleness is a
sliding comparison of `last_seen_at` against the utility's inactivity setting,
made per request by `auth.IdentitySessionAuthentication`; a persistent session
sitting idle past that window is *refreshed*, not killed (`BR-IDN-026`). A
sweep that read the idle rule would be deleting rows the authenticator is
still willing to renew — the mirror of hard-won law 2, a dead row under a live
control. Idle rows leave through `expires_at` when the hard limit catches up
with them, which it always does.

⚠ **NO RETENTION PERIOD, AND THAT IS DELIBERATE.** There is no *"keep dead
sessions for 90 days"* here, because nobody has ruled one. `audit_log` already
holds `auth.sign_in`, `auth.sign_out` and `auth.lockout` for every session
that ever mattered, under its own retention rule — which the PO ruled on
2026-09-23 applies to every row with no exemptions. The session row itself is
a live credential, not a record; once it is dead it is neither.

THE MODULE BOUNDARY, AND WHY THE PORTAL HALF IS NOT AN IMPORT
──────────────────────────────────────────────────────────────
B1: a module writes its own tables and nobody else's. `identity` owns
`sessions`; `portal` owns `portal_session`. So this module deletes the first
and ASKS `portal` to delete the second, resolving the function BY NAME at call
time (`BR-TEN-013`'s pattern, the same one `notifications/schedule.py` uses to
reach tenancy) — no import statement binds identity to the portal's models,
and the DELETE on `portal_session` is executed by the portal's own code.

⚠ **AND THE REVERSE IMPORT IS GATED, WHICH IS THE OTHER HALF OF THE REASON.**
`G91` refuses any file under `apps/portal/` that imports `apps.identity`
except its one declared seam. The portal cannot come to us, so the sweep comes
to it — one beat entry, one fan-out, two owners.
"""

from __future__ import annotations

import logging
from importlib import import_module
from typing import Any

from django.utils import timezone

from apps.identity.models import Session
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.identity")

#: The beat entry's own name. ONE key: every installer does
#: `existing.update(schedule)`, so two modules sharing a key means whichever
#: `ready()` runs last silently erases the other's schedule (G132 clause 3).
BEAT_ENTRY = "identity.session_cleanup"

#: Registered by NAME so the routing name in `beat_schedule()` and the
#: registered task cannot drift — that drift is a message beat publishes and
#: no worker consumes, and the broker reports it as success.
CLEANUP_TASK = "smartbillhub.identity.session_cleanup"
CLEANUP_ONE_TASK = "smartbillhub.identity.session_cleanup_one"

_CLEANUP_TASK: Any = None
_CLEANUP_ONE_TASK: Any = None

#: 03:20, every day. A DURATION would drift across the day; a clock time keeps
#: it in the quiet hours, which is where a bulk DELETE on a hot table belongs.
#: The minute is not `:00` for the reason this repo's Routines are not: most
#: schedules run on the hour, and a job that fights every other job for the
#: same minute is a job that runs late.
CLEANUP_HOUR = 3
CLEANUP_MINUTE = 20

#: Where the portal's half lives. Resolved by NAME at call time — see the
#: module docstring for why this is three strings and not an import.
PORTAL_MODULE = "apps.portal.session"
PORTAL_PURGE = "purge_dead_sessions"


def purge_staff_sessions(tenant_id: Any) -> int:
    """Delete this utility's expired and signed-out staff sessions. Returns how many.

    ⚠ **THE FILTER IS A UNION OF TWO POSITIVE CONDITIONS.** See the module
    docstring: the negation of *live* is one `OR` away from matching every row
    in the table, and this is a DELETE.
    """
    now = timezone.now()
    expired = Session.objects.filter(tenant_id=tenant_id, expires_at__lt=now)
    signed_out = Session.objects.filter(tenant_id=tenant_id, revoked_at__isnull=False)
    deleted, _by_model = (expired | signed_out).distinct().delete()
    return int(deleted)


def _purge_portal_sessions(tenant_id: Any) -> int:
    """The portal's half, through the portal's OWN function, resolved by name.

    A portal that publishes no such function is not an error and not a
    failure of this sweep: it returns 0 and says so once, and the staff half
    still runs. A sweep that refused to run because a sibling module had not
    shipped its half would be a sweep nobody could land incrementally.
    """
    try:
        target = import_module(PORTAL_MODULE)
    except ImportError:  # pragma: no cover — the portal ships in this repo
        return 0
    found = getattr(target, PORTAL_PURGE, None)
    if not callable(found):
        logger.info(
            "%s.%s is not published, so no portal sessions were swept. The "
            "staff half still ran.",
            PORTAL_MODULE,
            PORTAL_PURGE,
        )
        return 0
    return int(found(tenant_id) or 0)


def cleanup_one(subdomain: str) -> dict[str, Any]:
    """One utility's sweep, inside its own tenant context.

    ⚠ **THE CONTEXT IS SET PER UTILITY AND CLEARED ON THE WAY OUT**, which is
    `core.tenancy.tenant_context`'s whole job and CLAUDE.md rule 1: a sweep
    that carried one utility's context into the next utility's iteration would
    be deleting the wrong rows under RLS's nose, and the fan-out below hands
    each utility its own task partly so that cannot happen by accident.
    """
    tenant_id = core_tenancy.tenant_id_for_slug(subdomain)
    if tenant_id is None:
        return {"subdomain": subdomain, "swept": False, "reason": "no such utility"}
    with core_tenancy.tenant_context(tenant_id):
        staff = purge_staff_sessions(tenant_id)
        portal = _purge_portal_sessions(tenant_id)
    return {
        "subdomain": subdomain,
        "swept": True,
        "staff_sessions_deleted": staff,
        "portal_sessions_deleted": portal,
    }


def _live_subdomains() -> tuple[str, ...]:
    """Every live utility, through tenancy's OWN published read (BR-TEN-013)."""
    try:
        target = import_module("apps.tenancy.selectors")
    except ImportError:  # pragma: no cover
        return ()
    found = getattr(target, "live_tenant_subdomains", None)
    if not callable(found):
        return ()
    try:
        return tuple(str(entry) for entry in (found() or ()))
    except Exception:  # noqa: BLE001 — a broken read must not stop the beat
        logger.exception(
            "the live-utility read could not be made, so this firing swept "
            "nobody. Nothing is deleted and the next firing tries again."
        )
        return ()


def cleanup_all() -> dict[str, Any]:
    """ONE firing: hand every live utility its own sweep.

    A fan-out and not a loop, for the same reason `notifications.dispatch_all`
    is one: one utility's slow DELETE cannot delay another's, and each task
    carries exactly one tenant context.
    """
    subdomains = _live_subdomains()
    if _CLEANUP_ONE_TASK is None:
        # No celery here (a management command, a test, `manage.py check`).
        # Run them in line rather than reporting a fan-out that never happened.
        return {
            "utilities": len(subdomains),
            "fanned_out": False,
            "results": [cleanup_one(subdomain) for subdomain in subdomains],
        }
    for subdomain in subdomains:
        _CLEANUP_ONE_TASK.delay(subdomain)
    return {"utilities": len(subdomains), "fanned_out": True}


def beat_schedule() -> dict[str, dict[str, Any]]:
    """The beat entry, as DATA. No side effects, no clock, no broker.

    Published as a function returning a plain dict so it can be asserted
    without starting celery — the schedule being CORRECT and the schedule
    being INSTALLED are two different claims (hard-won law 2), and
    `install()` below is the second one.
    """
    try:
        from celery.schedules import crontab

        when: Any = crontab(hour=CLEANUP_HOUR, minute=CLEANUP_MINUTE)
    except Exception:  # noqa: BLE001 — celery absent; see install()
        when = {"hour": CLEANUP_HOUR, "minute": CLEANUP_MINUTE}
    return {
        BEAT_ENTRY: {
            "task": CLEANUP_TASK,
            "schedule": when,
            "args": (),
            "options": {"expires": None},
        }
    }


def install(app: Any = None) -> dict[str, Any]:
    """Register the schedule and the two tasks on the celery app. Idempotent.

    Called from `IdentityConfig.ready()`. Returns what it did, so a caller and
    a test can tell *installed* from *celery is not importable here* — the two
    look identical from outside and only one of them is a problem. A failure
    to import celery is NOT an error: `manage.py check`, a migration and the
    test suite all run without a broker, and a Django app that refuses to
    start because a scheduler is absent would be a worse product than one
    whose dead rows are swept a day later.
    """
    if app is None:
        try:
            from config.celery import app as celery_app
        except Exception as problem:  # noqa: BLE001 — see the docstring
            logger.info(
                "the session cleanup schedule was not installed: celery is "
                "not available here (%s). Nothing is broken — no session row "
                "is deleted, which is the state this product has always been "
                "in.",
                problem,
            )
            return {"installed": False, "reason": str(problem)}
        app = celery_app

    # ⚠ THE RESULT IS KEPT, and that is not tidiness. `app.task(...)(fn)`
    # returns a NEW task object and leaves the module-level name bound to the
    # plain function, which has no `.delay` — so the fan-out would run every
    # utility's sweep INLINE inside beat's own process.
    global _CLEANUP_TASK, _CLEANUP_ONE_TASK
    _CLEANUP_ONE_TASK = app.task(name=CLEANUP_ONE_TASK, bind=False)(cleanup_one)
    _CLEANUP_TASK = app.task(name=CLEANUP_TASK, bind=False)(cleanup_all)

    schedule = beat_schedule()
    existing = dict(getattr(app.conf, "beat_schedule", None) or {})
    existing.update(schedule)
    app.conf.beat_schedule = existing
    return {"installed": True, "entry": BEAT_ENTRY, "schedule": schedule}


__all__ = [
    "BEAT_ENTRY",
    "beat_schedule",
    "cleanup_all",
    "cleanup_one",
    "install",
    "purge_staff_sessions",
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-145-BRC08 task B10 (the change request's own text, verbatim: "nightly cleanup deleting expired and signed-out session rows, staff and portal. Session rows are never deleted today. Scheduler entry goes to celery-beat.")
# generated: 2026-09-28 by lane SESS-BACKEND
# checklist: A✔ B✔ C✔ D=n/a(no API surface — a scheduled job) E=n/a(no UI) F✔ G✔ H=pending(HUMAN-REVIEW-PENDING is on the migrations; this file writes no policy and touches no money)
# gates: G132 (a declared beat entry is an installed one) · pytest tests/test_cr145_session_settings.py -k t9
# exceptions: the portal half is resolved BY NAME rather than imported — B1 forbids a cross-module write and G91 forbids the reverse import, so the DELETE on `portal_session` is executed by the portal's own `purge_dead_sessions`. A portal that has not shipped it returns 0 and logs once rather than failing the sweep.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
