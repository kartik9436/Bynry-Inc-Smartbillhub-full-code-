# ── Trace ──────────────────────────────────────────────
# Story:    US-REP-015 (email delivery rides the outbound queue)
#           Screens: 4·1 · 5·1
# Change:   CR-142-BRC07 — the Reports Build Brief, Phase 4 task `P4.10`.
#           Drawing p15, read as an IMAGE per B14 rule 42.
# Rules:    B1 / B2 §2 (cross-module WRITES are forbidden — reports never
#           touches `outbound_messages`; it resolves the owner's published
#           callable BY NAME) · BR-TEN-013 (a cross-module read resolves the
#           owner's published callable, never its ORM) · BR-NOT-005 (queue
#           only) · BR-REP-017 (dispatch is W6) · CLAUDE.md hard-won law 14
#           (a failed statement poisons the whole PostgreSQL transaction, and
#           the suite runs on SQLite, which does not)
# Tests:    06-backend/tests/test_cr142_p4_10_delivery.py
# Impacts:  apps/reports/delivery.py (its only caller) ·
#           apps/notifications/report_events.py (resolved BY NAME, never
#           imported)
# ───────────────────────────────────────────────────────
"""reports → notifications SEAM: the one message a scheduled run sends.

╔══════════════════════════════════════════════════════════════════════════╗
║  Dana schedules the AR ageing for the first of the month. On 1 October   ║
║  at 06:00 it runs, and Dana — who is not at her desk — gets an email     ║
║  with a LINK to it.                                                      ║
╚══════════════════════════════════════════════════════════════════════════╝

────────────────────────────────────────────────────────────────────────────
WHY A SEAM FILE AND NOT A CALL INSIDE `delivery.py`
────────────────────────────────────────────────────────────────────────────
Reports must not import notifications (B1 · B2 §2), and `outbound_messages` is
notifications' table — a write to it from here would be the cross-module write
the module map forbids outright. The entry point is resolved BY NAME at call
time, the idiom `apps/customers/notifications_seam.py` and
`apps/payments/receipts.py` both use, so the whole contract between the two
modules reads in one file. **`G20` harvests this file** and fails the day
`apps.notifications.report_events.queue_scheduled_report` is renamed, moved or
never authored — which is DEF-075's shape and the reason the register exists.

⚠ **THE EVENT KEY AND THE TEMPLATE CODE ARE NOT SPELLED HERE.**
`report_events.queue_scheduled_report` names its own event and pins its own
template, so this file resolves a SYMBOL rather than typing a string. A
mistyped key would refuse at the END of a sweep that had already advanced every
schedule's next-run date.

────────────────────────────────────────────────────────────────────────────
NOTHING THIS FILE DOES MAY REACH THE SWEEP — AND A `try` IS NOT ENOUGH
────────────────────────────────────────────────────────────────────────────
⚠ **CATCHING THE EXCEPTION IS NOT ENOUGH ON POSTGRESQL** (hard-won law 14). A
statement that errors inside a Postgres transaction ABORTS the whole
transaction: the `except` catches it, the sweep's own writes are already
doomed, and the COMMIT fails afterwards with *"current transaction is
aborted"*. SQLite has no such state, so a bare `try/except` passes the entire
suite and loses a tenant's advanced `next_run_at` rows the first time the queue
refuses a row in production — which would re-fire every schedule on the next
tick.

**The savepoint is not the tidy option, it is the only one**, and it must not
be "simplified" away. `apps/customers/notifications_seam.py` and
`apps/payments/receipts.py` record the same finding from the same day.

The `except` is broad for the reason those files give: the queue now reads a
tenant rule table before it writes, and a bug in that read must not stop a
utility's whole schedule sweep.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from django.db import transaction

#: The notifications contract this module depends on, named once so it is
#: greppable from BOTH sides of the boundary (the `receipts.py` discipline).
MESSAGE_MODULE = "notifications"
MESSAGE_KIND = "report_events"
WRITE_SCHEDULED_REPORT = "queue_scheduled_report"
#: The owner's own refusal type, resolved the same way. A refusal is the queue
#: saying no for a reason a human can act on, and it is not a fault.
MESSAGE_REFUSAL = "ScheduledReportRefused"

#: Outcome CODES, because the sweep's result and its log group on them rather
#: than parsing prose. Every one ends up on `deliver_ready_runs`' own answer.
REPORT_MESSAGE_QUEUED = "scheduled_report_message_queued"
REPORT_MESSAGE_ALREADY_QUEUED = "scheduled_report_message_already_queued"
REPORT_MESSAGE_SUPPRESSED = "scheduled_report_message_suppressed_by_rule"
REPORT_MESSAGE_UNAVAILABLE = "scheduled_report_message_unavailable"
REPORT_MESSAGE_REFUSED = "scheduled_report_message_refused"
REPORT_MESSAGE_ERROR = "scheduled_report_message_error"

BR_REF = "BR-REP-007"


def _resolve(name: str) -> Any:
    """`apps.notifications.report_events.<name>`, or `None` while unauthored.

    getattr AT CALL TIME, never at import — `report_seams.resolve`'s twin, and
    DEF-035 is why the KIND is a constant rather than a guess: a seam pointing
    at the wrong FILE returned `None` on every call for weeks and silently
    recorded a guard as *not checked* on every move-out.
    """
    try:
        published = import_module(f"apps.{MESSAGE_MODULE}.{MESSAGE_KIND}")
    except ImportError:  # pragma: no cover — notifications is always installed
        return None
    return getattr(published, name, None)


def queue_scheduled_report(**fields: Any) -> dict[str, Any]:
    """Queue ONE *your report is ready* email. Never raises.

    Returns a dict carrying an outcome CODE and whatever the queue answered.
    The caller — `delivery.deliver_ready_runs` — records it against the run and
    carries on to the next schedule; one utility's broken template must not
    stop another utility's month-end pack.

    ⚠ **THE WHOLE CALL IS INSIDE A SAVEPOINT.** See the module docstring: on
    PostgreSQL the `except` alone is not a containment, it is a delayed
    failure of the caller's own transaction.
    """
    write = _resolve(WRITE_SCHEDULED_REPORT)
    if write is None:  # pragma: no cover — defensive; G20 fails this at merge
        return {
            "code": REPORT_MESSAGE_UNAVAILABLE,
            "detail": (
                f"apps.{MESSAGE_MODULE}.{MESSAGE_KIND}.{WRITE_SCHEDULED_REPORT} is not "
                "published, so this run was produced and nobody was told. The file is "
                "still on the History tab."
            ),
        }
    refusal = _resolve(MESSAGE_REFUSAL)
    try:
        with transaction.atomic():  # SAVEPOINT — law 14, not tidiness
            answer = write(**fields)
    except Exception as problem:  # noqa: BLE001 — see the module docstring
        if refusal is not None and isinstance(problem, refusal):
            return {"code": REPORT_MESSAGE_REFUSED, "detail": str(problem)}
        return {"code": REPORT_MESSAGE_ERROR, "detail": str(problem)}
    if answer.message_id is None:
        # The utility's own SET-12 rule left no channel. Not a fault, and the
        # reason travels so the sweep's answer can say so rather than reporting
        # a delivery that did not happen.
        return {
            "code": REPORT_MESSAGE_SUPPRESSED,
            "problems": list(answer.problems),
        }
    return {
        "code": (REPORT_MESSAGE_QUEUED if answer.created else REPORT_MESSAGE_ALREADY_QUEUED),
        "message_id": answer.message_id,
        "recipients": list(answer.recipients),
        "problems": list(answer.problems),
    }


__all__ = [
    "BR_REF",
    "MESSAGE_KIND",
    "MESSAGE_MODULE",
    "MESSAGE_REFUSAL",
    "REPORT_MESSAGE_ALREADY_QUEUED",
    "REPORT_MESSAGE_ERROR",
    "REPORT_MESSAGE_QUEUED",
    "REPORT_MESSAGE_REFUSED",
    "REPORT_MESSAGE_SUPPRESSED",
    "REPORT_MESSAGE_UNAVAILABLE",
    "WRITE_SCHEDULED_REPORT",
    "queue_scheduled_report",
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P4.10 (05-prototype/09 Reports Build Brief.pdf p15, read as an image per B14 rule 42) · 04-docs/05-modules/12-reports/06-epics/EP-REP-04-scheduler.md US-REP-015 · apps/customers/notifications_seam.py (the idiom this copies)
# screens: 4·1 · 5·1
# generated: 2026-09-27 by lane REP-P4-REST
# checklist: A✔ B=n/a(no screen half) C✔ D=deferred(no new API surface) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_cr142_p4_10_delivery.py was run before this file existed and reported `ModuleNotFoundError: No module named 'apps.reports.notifications_seam'`.
# exceptions: (1) the savepoint is LAW 14 and not style; a reviewer "simplifying" it to a bare try/except would pass the whole suite on SQLite and abort a real sweep's transaction on PostgreSQL.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
