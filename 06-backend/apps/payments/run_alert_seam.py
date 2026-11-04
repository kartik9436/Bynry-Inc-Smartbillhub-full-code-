# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-021 (S38 — the bank statement import and auto-match) ×
#           US-NOT-018 (ONE message per bulk action)
#           Screens: S38 step 2 · S40 · shell-chrome (the bell) · S8
# Rules:    BR-NOT-020 (one message per bulk action, whatever the item count) ·
#           BR-NOT-021 (the ruled staff audience) · BR-NOT-019 (in-app is the
#           one channel that delivers today) · BR-NOT-017 (the utility's own
#           rule, read on the way to the queue) · BR-PAY-019 (what auto-match
#           may and may not decide) · BR-TEN-043 (no wall clock) ·
#           CLAUDE.md rule 6 (idempotency) · hard-won law 2 (built is not wired)
# Change:   CR-048 wave B follow-up — *"give the two staff alerts their
#           callers, so they fire unattended"*. Wave B built
#           `queue_reconciliation_summary` and stated that nothing called it.
#           This module is the payments half of the wiring.
# Tests:    06-backend/tests/test_cr048_staff_alerts_wired.py
# Impacts:  apps/payments/reconciliation.py `import_bank_statement` (its one
#           caller — the point a reconciliation run finishes) ·
#           apps/notifications/bulk_summary.py (resolved BY NAME, never imported)
# ───────────────────────────────────────────────────────
"""payments → notifications SEAM: the ONE staff message a reconciliation sends.

╔══════════════════════════════════════════════════════════════════════════╗
║  WHAT THIS IS FOR, in one sentence a clerk would recognise:              ║
║  a bank statement is imported and a message appears in the bell saying   ║
║  "Payment reconciliation finished. 48 processed · 3 failed".             ║
╚══════════════════════════════════════════════════════════════════════════╝

**ONE message, whatever the statement carried** (BR-NOT-020). And **zero
exceptions is still one message**, which is the entry point's own reasoning and
worth repeating here: *"a clerk who sees nothing cannot tell a clean run from a
run that never happened."*

────────────────────────────────────────────────────────────────────────────
WHAT COUNTS AS A FAILURE ON THIS EVENT, AND WHY IT IS BOTH TILES
────────────────────────────────────────────────────────────────────────────
`import_bank_statement` sorts every bank line into three: matched, `needs a
look`, and `not in our system`. The event is `reconciliation_exceptions` and
`failed_count` is **the second and third together** — every line this run could
NOT match.

That is a judgment and it is written down rather than left in the code: S38's
fourth tile is money the bank credited that matches no deposit of ours at all,
and it is emphatically a clerk's to work. Counting only `needs a look` would
report a statement of pure unknown credits as a clean run, which is the failure
BR-NOT-020's *"it must say HOW MANY"* half exists to prevent, in the direction
that is easy to miss.

────────────────────────────────────────────────────────────────────────────
NOTHING THIS FILE DOES MAY REACH THE BANK LINES — AND A `try` IS NOT ENOUGH
────────────────────────────────────────────────────────────────────────────
⚠ **CATCHING THE EXCEPTION IS NOT ENOUGH ON POSTGRESQL.** A statement that
errors inside a Postgres transaction ABORTS the whole transaction: the `except`
catches it, the import is already doomed, and the COMMIT fails afterwards with
*"current transaction is aborted"*. SQLite has no such state, so a `try/except`
alone passes there and loses a whole statement here. `apps/payments/receipts.py`
records the same finding from CR-048 B3.

So the call gets its **own savepoint**, and the `@requires_postgres` case in
this seam's test drives a REAL `SELECT 1/0` through it and reads the bank lines
back in a NEW transaction. The `except` is broad for the reason `receipts.py`
gives: the queue now reads a tenant rule table before it writes, and a bug in
that read must not take a bank import down.

────────────────────────────────────────────────────────────────────────────
WHY A SEAM FILE AND NOT A CALL INSIDE `reconciliation.py`
────────────────────────────────────────────────────────────────────────────
Payments must not import notifications (B1 · B2 §2). The entry point is resolved
BY NAME at call time — the idiom `receipts.py`, `notices.py` and `ledger_seam.py`
all use — so the whole contract between the two modules reads in one file.

⚠ **THE EVENT KEY IS NOT SPELLED HERE.** `queue_reconciliation_summary` names
its own event, so this seam resolves a SYMBOL rather than typing a string, and a
mistyped key cannot refuse at the end of a run.
"""

from __future__ import annotations

from datetime import datetime
from importlib import import_module
from typing import Any

from django.db import transaction

#: The notifications contract this module depends on, named once so it is
#: greppable from BOTH sides of the boundary (the `receipts.py` discipline).
STAFF_ALERT_MODULE = "notifications"
STAFF_ALERT_KIND = "bulk_summary"
STAFF_ALERT_WRITE = "queue_reconciliation_summary"
#: The owner's own refusal type, resolved the same way — a refusal is the queue
#: saying no for a reason a human can act on (a scheduled import with no
#: signed-in user and nothing to report, BR-NOT-021), and it is not a fault.
STAFF_ALERT_REFUSAL = "BulkSummaryRefused"

#: Outcome CODES, because S38 step 2 and the import report group on them rather
#: than parsing prose. Every one ends up on `StatementImportResult.staff_alert`.
RUN_SUMMARY_QUEUED = "reconciliation_summary_queued"
RUN_SUMMARY_ALREADY_QUEUED = "reconciliation_summary_already_queued"
RUN_SUMMARY_SUPPRESSED = "reconciliation_summary_suppressed_by_rule"
RUN_SUMMARY_UNAVAILABLE = "reconciliation_summary_unavailable"
RUN_SUMMARY_REFUSED = "reconciliation_summary_refused"
RUN_SUMMARY_ERROR = "reconciliation_summary_error"

BR_REF = "BR-NOT-020"


def _resolve(attribute: str) -> Any:
    """Notifications' published callable, or None while it publishes none."""
    try:
        target = import_module(f"apps.{STAFF_ALERT_MODULE}.{STAFF_ALERT_KIND}")
    except ImportError:  # pragma: no cover - notifications ships in this repo
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def entry_point() -> Any:
    """The reconciliation summary entry point, resolved by name. Published so a
    test can assert this seam reaches a real function rather than trusting a
    docstring (hard-won law 1)."""
    return _resolve(STAFF_ALERT_WRITE)


def queue_run_summary(
    *,
    run_id: Any,
    total_count: int,
    failed_count: int,
    finished_at: datetime,
    actor: Any = None,
) -> tuple[dict[str, Any], ...]:
    """ONE staff message for one finished reconciliation run. Outcome rows only.

    `run_id` is the STATEMENT IMPORT's own id, which is what makes a replayed or
    resumed import find its own message and write nothing — the database
    refuses the second (rule 6).

    `finished_at` is a PARAMETER and never a clock read (BR-TEN-043).

    **This function raises nothing.** Queued, already queued, suppressed by the
    utility's own switch, refused for want of an addressee, or broken outright —
    each comes back as a row the caller carries on its result.
    """
    write = entry_point()
    if write is None:  # pragma: no cover - defensive
        return (
            {
                "code": RUN_SUMMARY_UNAVAILABLE,
                "br_ref": BR_REF,
                "detail": f"apps.{STAFF_ALERT_MODULE}.{STAFF_ALERT_KIND}."
                f"{STAFF_ALERT_WRITE} is not published, so no staff summary could be "
                "queued for this reconciliation run. Reported rather than swallowed.",
            },
        )

    try:
        # ⚠ THE SAVEPOINT IS THE POINT. See the module docstring: on PostgreSQL
        # a `try` alone loses the whole import at COMMIT.
        with transaction.atomic():
            summary = write(
                run_id=run_id,
                total_count=total_count,
                failed_count=failed_count,
                finished_at=finished_at,
                actor=actor,
                job=None if actor is not None else "payments.import_bank_statement",
            )
    except Exception as failure:  # noqa: BLE001 — the one boundary where broad is right
        refusal = _resolve(STAFF_ALERT_REFUSAL)
        refused = refusal is not None and isinstance(failure, refusal)
        return (
            {
                "code": RUN_SUMMARY_REFUSED if refused else RUN_SUMMARY_ERROR,
                "br_ref": BR_REF,
                "detail": f"the reconciliation summary could not be queued: {failure} The "
                "import stands — a failed notification must never fail the work it "
                "describes.",
            },
        )

    problems = tuple(getattr(summary, "problems", ()) or ())
    if getattr(summary, "message_id", None) is None:
        # The rule left no channel. A utility switching *Reconciliation
        # exceptions* off is a CHOICE, and the reason travels so the import
        # report can say so.
        return (
            {
                "code": RUN_SUMMARY_SUPPRESSED,
                "br_ref": BR_REF,
                "event_key": getattr(summary, "event_key", None),
                "detail": "no staff summary was queued for this reconciliation run "
                "because this utility's own notification rule left no channel. The "
                "import completed normally.",
            },
            *problems,
        )

    created = bool(getattr(summary, "created", False))
    return (
        {
            "code": RUN_SUMMARY_QUEUED if created else RUN_SUMMARY_ALREADY_QUEUED,
            "br_ref": BR_REF,
            "message_id": str(summary.message_id),
            "event_key": getattr(summary, "event_key", None),
            "total_count": total_count,
            "failed_count": failed_count,
            "detail": (
                "one staff message is on the outbound queue for this reconciliation run "
                "— one, whatever the statement carried (BR-NOT-020). In-app delivers on "
                "the next dispatch cycle."
                if created
                else "this run's staff summary was already queued, so nothing was "
                "written. A replayed import says it once (rule 6)."
            ),
        },
        *problems,
    )


# ══════════════════════════════════════════════════════════════════════════
# `CR-136-BRC07` `P2.11` — THE UNCLOSED TILL
# ══════════════════════════════════════════════════════════════════════════
#
# The second thing payments tells the notifications module, in the same file
# for the reason the header gives: *"the whole contract between the two modules
# reads in one file"*. Same `_resolve`, same savepoint, same never-raises
# promise; a different entry point and a different set of outcome codes,
# because a caller that groups on `reconciliation_summary_queued` must not
# start seeing counter rows under it.
#
# ⚠ **THIS SEAM TELLS. IT NEVER CLOSES** — PO ruling 2026-09-23 §3.1. Nothing
# below writes to `counter_sessions` and nothing may be added that does.

STAFF_ALERT_COUNTER_WRITE = "queue_counter_watch_summary"

COUNTER_WATCH_QUEUED = "counter_watch_summary_queued"
COUNTER_WATCH_ALREADY_QUEUED = "counter_watch_summary_already_queued"
COUNTER_WATCH_SUPPRESSED = "counter_watch_summary_suppressed_by_rule"
COUNTER_WATCH_UNAVAILABLE = "counter_watch_summary_unavailable"
COUNTER_WATCH_REFUSED = "counter_watch_summary_refused"
COUNTER_WATCH_ERROR = "counter_watch_summary_error"

#: The job name a sweep with no signed-in user queues under, so the dispatch
#: home can say what raised a message nobody started.
COUNTER_WATCH_JOB = "payments.sweep_open_counters"


def counter_watch_entry_point() -> Any:
    """The counter-watch entry point, resolved by name.

    Published for the same reason `entry_point` is: a test asserts this seam
    reaches a REAL function, rather than trusting a docstring that says it does
    (hard-won law 1). A seam that resolves to `None` reports
    `COUNTER_WATCH_UNAVAILABLE` and the sweep still finishes.
    """
    return _resolve(STAFF_ALERT_COUNTER_WRITE)


def queue_counter_watch(
    *,
    sweep_id: Any,
    total_count: int,
    failed_count: int,
    finished_at: datetime,
    actor: Any = None,
) -> tuple[dict[str, Any], ...]:
    """ONE staff message for one morning's sweep. Outcome rows only; raises nothing.

    `failed_count` is the number of tills **nobody closed**, and it is what puts
    the message in front of every active System Admin under BR-NOT-021 — which
    is the whole of `P2.11`, because a System Admin is the only person who may
    force-close somebody else's till (PO 2026-09-23 §3.1).

    `finished_at` is a PARAMETER and never a clock read (BR-TEN-043).

    **A clean night comes back REFUSED and that is a success**, not a fault:
    with no signed-in user and no failures the ruled audience is empty, so
    nothing is queued. The row says so in words rather than reporting an error
    a reader would chase.
    """
    write = counter_watch_entry_point()
    if write is None:  # pragma: no cover - defensive
        return (
            {
                "code": COUNTER_WATCH_UNAVAILABLE,
                "br_ref": BR_REF,
                "detail": f"apps.{STAFF_ALERT_MODULE}.{STAFF_ALERT_KIND}."
                f"{STAFF_ALERT_COUNTER_WRITE} is not published, so no supervisor could be "
                "told about the counters left open. Reported rather than swallowed.",
            },
        )

    try:
        # ⚠ THE SAVEPOINT IS THE POINT — hard-won law 14, and the default suite
        # runs on SQLite, which has no aborted-transaction state and therefore
        # cannot show this. The sweep walks every tenant; without the savepoint
        # one tenant's refused write aborts the transaction and the tenants
        # after it are lost at COMMIT.
        with transaction.atomic():
            summary = write(
                sweep_id=sweep_id,
                total_count=total_count,
                failed_count=failed_count,
                finished_at=finished_at,
                actor=actor,
                job=None if actor is not None else COUNTER_WATCH_JOB,
            )
    except Exception as failure:  # noqa: BLE001 — the one boundary where broad is right
        refusal = _resolve(STAFF_ALERT_REFUSAL)
        refused = refusal is not None and isinstance(failure, refusal)
        return (
            {
                "code": COUNTER_WATCH_REFUSED if refused else COUNTER_WATCH_ERROR,
                "br_ref": BR_REF,
                "total_count": total_count,
                "failed_count": failed_count,
                "detail": (
                    f"no supervisor was told: {failure} On a night when every counter was "
                    "closed this is the expected answer — an unattended sweep with nothing "
                    "to report has nobody to address (BR-NOT-021)."
                    if refused
                    else f"the counter-watch summary could not be queued: {failure} The "
                    "tills are untouched — this seam only ever tells."
                ),
            },
        )

    problems = tuple(getattr(summary, "problems", ()) or ())
    if getattr(summary, "message_id", None) is None:
        return (
            {
                "code": COUNTER_WATCH_SUPPRESSED,
                "br_ref": BR_REF,
                "event_key": getattr(summary, "event_key", None),
                "detail": "no supervisor was told about the counters left open because "
                "this utility's own notification rule left no channel. Counter left open "
                "is switched off on Settings → Notifications.",
            },
            *problems,
        )

    created = bool(getattr(summary, "created", False))
    return (
        {
            "code": COUNTER_WATCH_QUEUED if created else COUNTER_WATCH_ALREADY_QUEUED,
            "br_ref": BR_REF,
            "message_id": str(summary.message_id),
            "event_key": getattr(summary, "event_key", None),
            "total_count": total_count,
            "failed_count": failed_count,
            "detail": (
                f"one staff message is on the outbound queue: {failed_count} counter(s) "
                "nobody closed. In-app delivers on the next dispatch cycle."
                if created
                else "this morning's sweep had already told them, so nothing was written. "
                "A re-run says it once (rule 6)."
            ),
        },
        *problems,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-048 wave B follow-up (12-governance/11-change-requests.md → CR-048 · apps/notifications/bulk_summary.py queue_reconciliation_summary · apps/notifications/rule_catalog.py EVENTS `reconciliation_exceptions` · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-020 + BR-NOT-021 · apps/payments/reconciliation.py import_bank_statement)
# generated: 2026-08-30 by story-coder (CR-048 wave B wiring lane)
# checklist: A✔ B=deferred(no frontend half — the bell that READS this message is AppShell.tsx and shipped with CR-009; S38 step 2 renders `staff_alert` when an import-report lane picks it up) C✔ D=deferred(no HTTP surface of its own — reached through the existing bank-statement import endpoint) E=deferred(as B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_cr048_staff_alerts_wired.py — RED PROVED FIRST: a finished 4-line statement import left `staff_rows=0 and bell=0`, quoted in the lane report; the savepoint was proved by removing it and watching a real `SELECT 1/0` take the whole import with it at COMMIT on PostgreSQL
# exceptions: (1) `failed_count` IS `exceptions + not_in_our_system`, and the reasoning is in the module docstring — both are lines this run could not match and both are a clerk's to work. (2) THE EVENT KEY IS NOT SPELLED IN THIS FILE; the named entry point owns it. (3) NOTHING IS DISPATCHED BY THIS CALL: it queues, and `dispatcher.dispatch_cycle` delivers (BR-NOT-005).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
