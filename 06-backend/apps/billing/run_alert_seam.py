# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-005 (the bill run's phase 5) × US-NOT-018 (ONE message per
#           bulk action)   Screens: S31 step 6 · shell-chrome (the bell) · S8
# Rules:    BR-NOT-020 (one message per bulk action, whatever the item count) ·
#           BR-NOT-021 (the ruled staff audience) · BR-NOT-019 (in-app is the
#           one channel that delivers today) · BR-NOT-017 (the utility's own
#           rule, read on the way to the queue) · BR-BIL-055 (a break never
#           blocks the release) · BR-TEN-043 (no wall clock) ·
#           CLAUDE.md rule 6 (idempotency) · hard-won law 2 (built is not wired)
# Change:   CR-048 wave B follow-up — *"give the two staff alerts their
#           callers, so they fire unattended"*. Wave B built
#           `queue_billing_run_summary` and said so plainly: *"Neither named
#           entry point has a caller yet … So 'visibly working from day one' is
#           half true."* This module is the billing half of the other half.
# Tests:    06-backend/tests/test_cr048_staff_alerts_wired.py
# Impacts:  apps/billing/release.py `release_run` (its one caller — phase 5's
#           completion point) · apps/notifications/bulk_summary.py (the entry
#           point, resolved BY NAME and never imported)
# ───────────────────────────────────────────────────────
"""billing → notifications SEAM: the ONE staff message a finished bill run sends.

╔══════════════════════════════════════════════════════════════════════════╗
║  WHAT THIS IS FOR, in one sentence a clerk would recognise:              ║
║  a bill run finishes and a message appears in the bell saying            ║
║  "Billing run finished. 1,124 processed · 3 failed".                     ║
╚══════════════════════════════════════════════════════════════════════════╝

**ONE message, whatever the run touched.** That is BR-NOT-020 and it is a
ruling, not an optimisation — *"for single notification send 1 message and for
bulk action also send 1 message only"*. The reasoning is the CR's own: without
it, a run over a thousand accounts is a thousand notifications, so the first
thing any clerk does is switch the whole event off, *"at which point the failure
they needed to see is the one they never get"*. This module cannot break that
rule even by accident: it takes TOTALS, has no per-item shape, and there is
nothing here to put in a loop.

────────────────────────────────────────────────────────────────────────────
NOTHING THIS FILE DOES MAY REACH THE BILLS — AND A `try` IS NOT ENOUGH
────────────────────────────────────────────────────────────────────────────
A run that has issued five hundred bills must not fail because a summary could
not be queued. That is obvious and it is not what makes this file interesting.

⚠ **CATCHING THE EXCEPTION IS NOT ENOUGH ON POSTGRESQL.** A statement that
errors inside a Postgres transaction ABORTS the whole transaction: the `except`
catches it, the work is already doomed, and the COMMIT fails afterwards with
*"current transaction is aborted"*. On SQLite the same code passes, because
SQLite has no such state — which is exactly how this stays invisible until it
costs a morning's billing. `apps/payments/receipts.py` records the same finding
from CR-048 B3, discovered independently by two lanes on the same day.

So the call gets its **own savepoint** (`transaction.atomic()`), and the
`@requires_postgres` cases in this seam's test drive a REAL database error
(`SELECT 1/0`) through it and then read the bills back in a NEW transaction.
When `release_run` is called outside any transaction the same block is simply a
short transaction of its own, which is harmless.

And the `except` is **BROAD on purpose.** The queue reads a tenant rule table
before it writes (CR-048 wave A), which is one more thing standing between a
clerk pressing *Release* and the bills being issued. Catching only the owner's
own refusal type would let a bug in that read take a bill run down. Nothing is
swallowed: a refusal, a suppression and a fault carry DIFFERENT codes, so a run
report and a screen can tell them apart.

────────────────────────────────────────────────────────────────────────────
WHY A SEAM FILE AND NOT A CALL INSIDE `release.py`
────────────────────────────────────────────────────────────────────────────
Billing must not import notifications (B1 · B2 §2). The entry point is resolved
BY NAME at call time — the idiom `delivery_seam.py`, `rating_seam.py` and
`apps/metering/seams.py` all use — so no import statement binds the two modules
and a lane can read the whole contract between them in one file: one module
name, one attribute name, one argument list, and a fixed set of outcome codes.

⚠ **THE EVENT KEY IS NOT SPELLED HERE, AND THAT IS DELIBERATE.** CR-048's own
task list calls the bill-run event `billing_run_finished`, which is not a row on
SET-12; a lane that typed it would have queued nothing and found out at the END
of a thousand-account run. `queue_billing_run_summary` names the event itself,
so this seam resolves a SYMBOL rather than typing a string, and the only failure
mode left is "the function is not published" — which is reported by name.
"""

from __future__ import annotations

from datetime import datetime
from importlib import import_module
from typing import Any

from django.db import transaction

#: The notifications contract this module depends on, named once so it is
#: greppable from BOTH sides of the boundary (the `delivery_seam` discipline).
STAFF_ALERT_MODULE = "notifications"
STAFF_ALERT_KIND = "bulk_summary"
STAFF_ALERT_WRITE = "queue_billing_run_summary"
#: The owner's own refusal type, resolved the same way. A refusal is the queue
#: saying no for a reason a human can act on — a scheduled run with no signed-in
#: user and nothing to report (BR-NOT-021) is the live example — and it is NOT a
#: fault. Two codes, because a screen groups on the difference.
STAFF_ALERT_REFUSAL = "BulkSummaryRefused"

#: Outcome CODES, because a run report and S31 step 6 group on them rather than
#: parsing prose. Every one of them ends up on `ReleaseOutcome.staff_alert`.
RUN_SUMMARY_QUEUED = "billing_run_summary_queued"
RUN_SUMMARY_ALREADY_QUEUED = "billing_run_summary_already_queued"
RUN_SUMMARY_SUPPRESSED = "billing_run_summary_suppressed_by_rule"
RUN_SUMMARY_UNAVAILABLE = "billing_run_summary_unavailable"
RUN_SUMMARY_REFUSED = "billing_run_summary_refused"
RUN_SUMMARY_ERROR = "billing_run_summary_error"

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
    """The bill-run summary entry point, resolved by name. Published so a test
    can assert the seam reaches a real function rather than trusting a docstring
    (hard-won law 1)."""
    return _resolve(STAFF_ALERT_WRITE)


def queue_run_summary(
    *,
    run_id: Any,
    total_count: int,
    failed_count: int,
    finished_at: datetime,
    actor: Any = None,
) -> tuple[dict[str, Any], ...]:
    """ONE staff message for one finished bill run. Returns outcome rows only.

    `run_id` is the BILL RUN's own id and that is the whole of rule 6 for this
    message: a resumed or retried release finds its own row already there and
    writes nothing — the DATABASE refuses the second, which is the only
    guarantee that survives a retry that never called this function twice.

    `finished_at` is a PARAMETER and never a clock read (BR-TEN-043), so a
    replayed release stamps the moment the run finished rather than the moment
    the retry ran.

    **This function raises nothing.** Every outcome — queued, already queued,
    suppressed by the utility's own switch, refused for want of an addressee,
    or broken outright — comes back as a row the caller carries on its result.
    """
    write = entry_point()
    if write is None:  # pragma: no cover - defensive
        return (
            {
                "code": RUN_SUMMARY_UNAVAILABLE,
                "br_ref": BR_REF,
                "detail": f"apps.{STAFF_ALERT_MODULE}.{STAFF_ALERT_KIND}."
                f"{STAFF_ALERT_WRITE} is not published, so no staff summary could be "
                "queued for this bill run. Reported rather than swallowed.",
            },
        )

    try:
        # ⚠ THE SAVEPOINT IS THE POINT. See the module docstring: on PostgreSQL
        # a `try` alone loses the whole release at COMMIT.
        with transaction.atomic():
            summary = write(
                run_id=run_id,
                total_count=total_count,
                failed_count=failed_count,
                finished_at=finished_at,
                actor=actor,
                job=None if actor is not None else "billing.release",
            )
    except Exception as failure:  # noqa: BLE001 — the one boundary where broad is right
        refusal = _resolve(STAFF_ALERT_REFUSAL)
        refused = refusal is not None and isinstance(failure, refusal)
        return (
            {
                "code": RUN_SUMMARY_REFUSED if refused else RUN_SUMMARY_ERROR,
                "br_ref": BR_REF,
                "detail": f"the bill-run summary could not be queued: {failure} The run "
                "stands — a failed notification must never fail the work it describes.",
            },
        )

    problems = tuple(getattr(summary, "problems", ()) or ())
    if getattr(summary, "message_id", None) is None:
        # The rule left no channel. A utility switching *Billing run completed*
        # off on Settings → Notifications is a CHOICE, not a fault — and the
        # reason travels, because a rule obeyed so quietly that the run report
        # cannot mention it is the settings screen lying in the other direction.
        return (
            {
                "code": RUN_SUMMARY_SUPPRESSED,
                "br_ref": BR_REF,
                "event_key": getattr(summary, "event_key", None),
                "detail": "no staff summary was queued for this bill run because this "
                "utility's own notification rule left no channel. The run completed "
                "normally.",
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
                "one staff message is on the outbound queue for this bill run — one, "
                "whatever the run touched (BR-NOT-020). In-app delivers on the next "
                "dispatch cycle."
                if created
                else "this bill run's staff summary was already queued, so nothing was "
                "written. A resumed or retried release says it once (rule 6)."
            ),
        },
        *problems,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-048 wave B follow-up (12-governance/11-change-requests.md → CR-048 · apps/notifications/bulk_summary.py queue_billing_run_summary · apps/notifications/rule_catalog.py EVENTS `billing_run_completed` · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-020 + BR-NOT-021 · apps/billing/release.py release_run)
# generated: 2026-08-30 by story-coder (CR-048 wave B wiring lane)
# checklist: A✔ B=deferred(no frontend half — the bell that READS this message is AppShell.tsx and shipped with CR-009; S31 step 6 renders `staff_alert` when a run-report lane picks it up) C✔ D=deferred(no HTTP surface of its own — reached through the existing release endpoint) E=deferred(as B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_cr048_staff_alerts_wired.py — RED PROVED FIRST: a finished 3-account bill run left `staff_rows=0 and bell=0`, quoted in the lane report; the savepoint was proved by removing it and watching a real `SELECT 1/0` take the whole release with it at COMMIT on PostgreSQL
# exceptions: (1) THE EVENT KEY IS NOT SPELLED IN THIS FILE. `queue_billing_run_summary` names it, so a mistyped key is impossible here rather than merely unlikely — the CR's own `billing_run_finished` is not a row on SET-12 and would have refused at the END of a thousand-account run. (2) THE COUNTS COME FROM `IssuedRun` AND ARE NOT RE-COUNTED HERE — a second version of "how many bills went out" that could disagree with the first is exactly what US-BIL-005 forbids. (3) NOTHING IS DISPATCHED BY THIS CALL: it queues, and `dispatcher.dispatch_cycle` delivers (BR-NOT-005).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
