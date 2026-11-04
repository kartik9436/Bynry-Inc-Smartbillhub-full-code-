# ── Trace ──────────────────────────────────────────────
# Change:   CR-158-BRC10 — its "not done" item: an abandoned application's
#           files were never cleared. Ruled by the PO on 2026-10-02 (option A).
# Rules:    PO ruling 2026-10-02, verbatim: "A · Delete it 30 days after her
#           last visit. Her draft and the photo are deleted on 31 October, and
#           the deletion is logged. If she returns on 20 October, the 30 days
#           start again." · CLAUDE.md hard rule 1 (one tenant context per
#           utility, RLS FORCE) · hard rule 7 (every deletion writes
#           audit_log) · BR-AUD-006 (no personal content in the trail) ·
#           BR-TEN-081 (the utility's own clock decides what day it is) ·
#           hard-won law 2 (a schedule that is correct and one that is
#           INSTALLED are two claims)
# Tests:    06-backend/tests/test_cr158_draft_cleanup_pg.py (PostgreSQL, a
#           frozen clock — law 14)
# Impacts:  apps/portal/apps.py (ready() installs the beat entry) ·
#           apps/portal/write_points.py (STAFF_WRITE_MODULES +
#           MODULE_WRITE_TABLES name this file and the two models it deletes) ·
#           apps/portal/applications.py (stamps last_visited_at) ·
#           G81 · G84 · G132
# ───────────────────────────────────────────────────────
"""Delete UNSENT portal applications 30 days after the applicant's last visit,
with the files attached to them. Nightly, per utility.

THE RULING, AND THE WORKED FIGURE IT WAS GIVEN ON
──────────────────────────────────────────────────
Maria starts an application for water at 22 Elm St on **1 October** and
uploads a photo of her driver's licence. She never presses Send and never
comes back. **Her draft and the photo are deleted on 31 October** and the
deletion is logged. **If she returns on 20 October, the 30 days start again**
— so they go on 19 November instead.

So the rule is counted in the utility's own CALENDAR DAYS, not in 720-hour
blocks: a draft last visited on day D is deleted by the run on day D + 30, in
the utility's own timezone (`BR-TEN-081`). Counting hours would put Maria's
1 October 14:00 visit beyond the 31 October 03:40 run, and she would be
deleted on 1 November — a day later than the PO was shown.

WHAT IS DELETED, AND IT IS EXACTLY ONE KIND
───────────────────────────────────────────
A `portal_application_drafts` row that was **never sent** (`submitted_at` IS
NULL) and whose **last visit** is on or before *today − 30* — together with
every `portal_application_documents` row on it, which is where the uploaded
BYTES live (`PortalApplicationDocument.payload`; nothing of a draft is in the
document store). So deleting the rows deletes the bytes; there is no second
copy to chase.

**The last visit** is `last_visited_at` — stamped by `applications.py` when the
link is opened, saved, or a file is added or removed — or, on a draft that
predates that column (`portal/0012`), `updated_at`, its last save.

⚠ **NEVER TOUCHED, AND EACH IS ASSERTED:**
  * a **sent** application, its draft row, and its documents in the utility's
    document store — the store is write-once under its own retention
    (`NFR-35`), and a sent draft is a record of what was submitted;
  * a draft **visited within the 30 days**;
  * **another utility's** drafts — each utility runs in its own tenant context
    and the filter names the tenant as well (RLS is the second lock).

**SAFE TO RUN TWICE.** A second run finds nothing that matches and writes no
audit row. Each draft is re-read under a row lock before it goes, so an
applicant who opens her link while the job is running is not deleted under her.

THE AUDIT ROW — WHAT IS AND IS NOT WRITTEN
───────────────────────────────────────────
One row per deleted draft: `portal.application_draft.deleted_unsent`, naming
the draft by its own id (a draft has no reference — `US-CWP-013` §2), when it
was last visited, how many files went with it, and the reason
`"unsent 30 days"`. **Never** a file's name or contents, never the applicant's
name, contact details, date of birth or tax ID, and never the token, which is
the link that opens the draft and is never logged anywhere.

⚠ **NOT A PERMANENT RECORD.** `audit_log` has ONE retention rule and no row is
exempt (PO ruling 2026-09-23); this row is pruned with everything else.
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta
from importlib import import_module
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db import transaction
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.portal import models
from apps.portal.seams import tenancy_seam
from core import audit as core_audit
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.portal")

#: The PO's figure (2026-10-02, option A). Not a setting: a utility cannot
#: choose to keep a stranger's driving licence longer than the ruling says.
KEEP_DAYS = 30

#: What the audit row says, verbatim from the ruling's own words.
REASON = "unsent 30 days"
AUDIT_ACTION = "portal.application_draft.deleted_unsent"
ACTOR = core_audit.AutomationActor(
    kind=core_audit.ACTOR_KIND_JOB, name="Unsent application clean-up"
)

#: ONE beat key — two modules sharing a key means whichever `ready()` runs last
#: silently erases the other's schedule (G132 clause 3).
BEAT_ENTRY = "portal.draft_cleanup"
CLEANUP_TASK = "smartbillhub.portal.draft_cleanup"
CLEANUP_ONE_TASK = "smartbillhub.portal.draft_cleanup_one"

_CLEANUP_TASK: Any = None
_CLEANUP_ONE_TASK: Any = None

#: 03:40 UTC daily — after `identity.session_cleanup` (03:20), off the hour.
#: ⚠ **THE TIME DOES NOT DECIDE THE DAY.** Every run computes *today* in each
#: utility's own zone, so whichever run falls on the utility's 31 October is
#: the one that deletes Maria's draft. A 23-hour DST day can fall between two
#: runs, which deletes a day LATE and never early.
CLEANUP_HOUR = 3
CLEANUP_MINUTE = 40


def _zone(tenant_id: Any) -> ZoneInfo:
    """The utility's own zone, or UTC — tenancy's own answer for a utility that
    has not chosen one (`apps.tenancy.selectors.tenant_timezone`, BR-TEN-081),
    inherited rather than re-chosen."""
    name = tenancy_seam.regional(tenant_id).get("timezone")
    try:
        return ZoneInfo(name) if name else ZoneInfo("UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def cutoff(tenant_id: Any, now: datetime | None = None) -> datetime:
    """The instant before which a last visit is more than 30 days old.

    A visit on local day D is deleted on local day D + 30, so on local *today*
    every visit on or before *today − 30* goes — i.e. every visit BEFORE the
    start of *today − 29*, local midnight. Built local and then converted.
    """
    zone = _zone(tenant_id)
    today = timezone.localtime(now or timezone.now(), zone).date()
    first_kept_day = today - timedelta(days=KEEP_DAYS - 1)
    return datetime.combine(first_kept_day, time.min, tzinfo=zone)


def _expired(tenant_id: Any, before: datetime):
    return (
        models.PortalApplicationDraft.objects.filter(
            tenant_id=tenant_id, submitted_at__isnull=True
        )
        # 🔒 DEF-PAY-10554 — never a draft holding a card approval it did not
        # record: it is our record that the applicant paid (decision log
        # 2026-10-23, "one charge per application", judgment 5).
        .filter(fee_charge_approved__isnull=True)
        .annotate(last_visit=Coalesce("last_visited_at", "updated_at"))
        .filter(last_visit__lt=before)
    )


def purge_unsent_drafts(tenant_id: Any, *, now: datetime | None = None) -> dict[str, int]:
    """Delete this utility's unsent drafts last visited 30+ days ago, and their
    files. Returns `{"drafts": n, "files": m}`.

    The caller has entered this tenant's context; the tenant predicate is the
    second lock over RLS, not instead of it.
    """
    before = cutoff(tenant_id, now)
    drafts = files = 0
    for draft_id in list(_expired(tenant_id, before).values_list("pk", flat=True)):
        with transaction.atomic():
            # Re-read under a lock: the applicant may have opened her link
            # between the list and now, and then she is not deleted.
            draft = (
                _expired(tenant_id, before)
                .select_for_update(of=("self",))
                .filter(pk=draft_id)
                .first()
            )
            if draft is None:
                continue
            last_visit = draft.last_visit
            removed, _ = models.PortalApplicationDocument.objects.filter(
                tenant_id=tenant_id, draft_id=draft.pk
            ).delete()
            models.PortalApplicationDraft.objects.filter(
                tenant_id=tenant_id, pk=draft.pk
            ).delete()
            core_audit.write_row(
                action=AUDIT_ACTION,
                entity_type="portal_application_draft",
                entity_id=draft_id,
                automation=ACTOR,
                before={
                    "last_visited_at": last_visit.isoformat() if last_visit else None,
                    "files_deleted": int(removed),
                    "reason": REASON,
                },
            )
        drafts += 1
        files += int(removed)
    return {"drafts": drafts, "files": files}


def cleanup_one(subdomain: str, *, now: datetime | None = None) -> dict[str, Any]:
    """One utility's clean-up, inside its own tenant context (hard rule 1)."""
    tenant_id = core_tenancy.tenant_id_for_slug(subdomain)
    if tenant_id is None:
        return {"subdomain": subdomain, "swept": False, "reason": "no such utility"}
    with core_tenancy.tenant_context(tenant_id):
        done = purge_unsent_drafts(tenant_id, now=now)
    return {"subdomain": subdomain, "swept": True, **done}


def _live_subdomains() -> tuple[str, ...]:
    """Every live utility, through tenancy's OWN published read, resolved by
    name (BR-TEN-013 — the pattern `identity/session_cleanup.py` uses)."""
    try:
        found = getattr(import_module("apps.tenancy.selectors"), "live_tenant_subdomains", None)
    except ImportError:  # pragma: no cover
        return ()
    if not callable(found):
        return ()
    try:
        return tuple(str(entry) for entry in (found() or ()))
    except Exception:  # noqa: BLE001 — a broken read must not stop the beat
        logger.exception(
            "the live-utility read failed, so no unsent application was deleted "
            "this firing; the next firing tries again"
        )
        return ()


def cleanup_all() -> dict[str, Any]:
    """ONE firing: every live utility gets its own task and its own context."""
    subdomains = _live_subdomains()
    if _CLEANUP_ONE_TASK is None:
        return {
            "utilities": len(subdomains),
            "fanned_out": False,
            "results": [cleanup_one(subdomain) for subdomain in subdomains],
        }
    for subdomain in subdomains:
        _CLEANUP_ONE_TASK.delay(subdomain)
    return {"utilities": len(subdomains), "fanned_out": True}


def beat_schedule() -> dict[str, dict[str, Any]]:
    """The beat entry, as DATA — assertable without starting celery."""
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
    """Register the schedule and the two tasks. Idempotent; never raises.

    Called from `PortalConfig.ready()`. Without celery it returns
    `installed: False` and the application still starts — no draft is
    deleted, which is the state the product was in before this ruling.
    """
    if app is None:
        try:
            from config.celery import app as celery_app
        except Exception as problem:  # noqa: BLE001
            logger.info(
                "the unsent-application clean-up was not installed: celery is "
                "not available here (%s)",
                problem,
            )
            return {"installed": False, "reason": str(problem)}
        app = celery_app

    # The RESULT is kept: `app.task(...)(fn)` returns a new task object, and the
    # bare function has no `.delay`.
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
    "KEEP_DAYS",
    "REASON",
    "beat_schedule",
    "cleanup_all",
    "cleanup_one",
    "cutoff",
    "install",
    "purge_unsent_drafts",
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-158-BRC10 "not done" item, ruled 2026-10-02 (decision log, option A)
# generated: 2026-10-02 by lane draftgc
# checklist: A✔ B✔ C✔ D=n/a(no API surface — a scheduled job) E=n/a(no UI) F✔ G✔ H=pending(HUMAN-REVIEW-PENDING is on portal/0012)
# gates: G81 · G84 · G132 · pytest tests/test_cr158_draft_cleanup_pg.py
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
