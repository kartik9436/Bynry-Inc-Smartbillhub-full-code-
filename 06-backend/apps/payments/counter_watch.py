# ── Trace ──────────────────────────────────────────────
# Change:  CR-136-BRC07 task `P2.11` — *"Notification: the unclosed till. Tells
#          a supervisor; never closes"*. Blueprint p017, Outcome: *"Nobody has
#          to notice a missing count by looking."*
# Rules:   PO ruling 2026-09-23 §3.1 (**no auto-close** — *"A System Admin
#          closes it. Dana cannot work Tuesday until someone is free to do
#          that"*) · BR-NOT-020 (ONE message per bulk action) · BR-NOT-021 (the
#          ruled staff audience: the initiator, plus every active System Admin
#          on failure) · BR-TEN-043 (a business date is an INPUT, never a
#          clock) · BR-TEN-074 (per-tenant context, failures isolated) ·
#          CLAUDE.md hard rule 1 (tenant scoping; RLS FORCE is on) · hard rule 6
#          (idempotency) · hard-won law 14 (a savepoint, not a bare try)
# Tests:   06-backend/tests/test_cr136_p2_10_11_wire.py
# Impacts: apps/payments/run_alert_seam.py (`queue_counter_watch` — the only
#          way out of this module) · apps/payments/management/commands/
#          sweep_open_counters.py (the by-hand caller) ·
#          apps/payments/counter_watch_schedule.py (the scheduled caller, added
#          2026-09-23 for DEF-PAY-6268 — it TELLS on a clock and closes
#          nothing) ·
#          apps/notifications/rule_catalog.py (owns the event key) ·
#          apps/payments/counter_session_models.py (`STILL_OPEN` — the one
#          expression this reads)
# ───────────────────────────────────────────────────────
"""Find the tills nobody closed, and TELL somebody. `P2.11`.

╔══════════════════════════════════════════════════════════════════════════╗
║  IT TELLS. IT NEVER CLOSES.                                             ║
║  PO ruling 2026-09-23 §3.1, verbatim:                                   ║
║  "(a) Your ruling stands — no auto-close. A System Admin closes it.     ║
║   Dana cannot work Tuesday until someone is free to do that"            ║
╚══════════════════════════════════════════════════════════════════════════╝

**THE BLUEPRINT DREW A MIDNIGHT AUTO-CLOSE AND THE PO STRUCK IT.** `P2.18`'s
journey read *"home without closing → auto-close at midnight → Not counted"*
and screen 3·3d still draws the sentence *"Closed by the system on 09/18
23:59"*. Under §3.1 the journey becomes *"home without closing → **a System
Admin force-closes** → Not counted"*, and **no scheduled job may close a
till.** This module contains no write to `counter_sessions` and none may be
added: a `CounterSession` is only ever SELECTed here, and the only thing this
file writes is one message, through a seam, to another module.

That is also why it matters that somebody is told promptly. With the auto-close
gone, an unclosed till stays open until a human seals it, `uq_counter_sessions_
open_owner` refuses its owner a second one, and **Dana cannot take money on
Tuesday morning**. The PO accepted that cost explicitly. This sweep is what
stops it being discovered by Dana at the counter with a customer in front of
her.

────────────────────────────────────────────────────────────────────────────
WHICH STATE IT FIRES ON — "STILL OPEN", NOT "NOT COUNTED"
────────────────────────────────────────────────────────────────────────────
There are two states in this phase and they are a day and a person apart:

    STILL OPEN    `closed_at IS NULL`                       nobody sealed it
    NOT COUNTED   `close_kind='forced' AND declared_at IS NULL`  sealed, uncounted

This fires on the FIRST. The blueprint's own task row names it — *"the
**unclosed** till"* — and screen 3·1 renders exactly this state as the words
*"still open"* in its CLOSED column (p051). *Not counted* is what a till
becomes AFTER a supervisor acts on this message, it already has its three
readers on 3·1 (the list, the filter chip, the phase's done-when), and the
blueprint's acts table gives it a different message to a different person:
*"the row lands on 3·1 filtered as Not counted, and **the owner is told**"*
(p059). A notice about *Not counted* would be telling a supervisor about work
they had just finished.

The expression is `counter_session_models.STILL_OPEN` and it is written ONCE
there, beside the model — `CR-136-BRC07` §3.2's rule for its sibling state,
applied to this one (B14 rule 43).

**SYSTEM TILLS ANSWER NO FOR FREE.** `reconciliation._system_session` creates
them CLOSED, so `closed_at IS NULL` never matches one; its docstring calls that
*"what keeps it off the supervisor's screen"*. There is no exception list in
this file and there must not be one — an exception list is a thing a future
lane has to remember.

────────────────────────────────────────────────────────────────────────────
WHEN IT FIRES — A JUDGMENT, WRITTEN DOWN
────────────────────────────────────────────────────────────────────────────
**The blueprint gives no time for the notice**, only for the auto-close it no
longer has. So this is a lane judgment and it is in `12-governance/
02-decision-log.md` at 2026-09-23 with its reasoning; the short form:

**A till is "left open" when it was opened before the banking day being swept
began.** Open at 08:55 and still open at 23:00 the same day is a clerk at work,
not a problem. Open since yesterday is the problem, and the blueprint's own
boundary for *the day is over* was midnight — §3.1 struck the CLOSING at
midnight, not the MOMENT.

Two consequences worth stating, because both are deliberate:

  * **The cut-off is a MOMENT, never a truncated date.** `opened_at < cutoff`,
    where `cutoff` is midnight of the swept day in the tenant's own timezone.
    Comparing `opened_at::date` to a day would walk straight into `OQ-153` —
    *a tenant west of UTC banking at 6pm lands on the next UTC day* — which
    `bankrec_read._posting_day` already names and this avoids rather than
    inherits.
  * **The day is an INPUT** (BR-TEN-043). Nothing in this module reads a
    clock; `sweep_open_counters` resolves the day per tenant and passes it, so
    an operator can re-run any morning and get that morning's answer.

────────────────────────────────────────────────────────────────────────────
THE ZERO THAT WOULD HAVE MEANT NOTHING
────────────────────────────────────────────────────────────────────────────
⚠ **A QUERY WITH NO `app.tenant_id` SET MATCHES ZERO ROWS AND REPORTS
SUCCESS.** `counter_sessions` is under `FORCE ROW LEVEL SECURITY`
(`payments/0032`), and a sweep runs outside a request, so there is no ambient
context to inherit. A first draft that queried without entering a tenant would
have reported *"0 counters left open"* for every utility, every morning, for
ever — truthfully, and about nothing.

So the sweep enters each tenant's context explicitly, and `SweepResult` carries
`tenants_examined` beside `tills_left_open`: **the second figure is only
readable next to the first.** A reader who sees `0 left open across 0 tenants`
knows the sweep did nothing; `0 left open across 4 tenants` is a clean night.
Hard-won law 7 — *"a declared blind spot with no NUMBER attached is
indistinguishable from an empty one"* — applied to the scope rather than to the
result.

`tenants_failed` is the third figure and it is never folded into the other two.
"""

from __future__ import annotations

import datetime as dt
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from django.db import transaction

from core import tenancy as tenancy_kernel

from apps.payments import counter_session_models as tills
from apps.payments import run_alert_seam

logger = logging.getLogger(__name__)

#: A fixed namespace so `sweep_id` is a pure function of (tenant, day) and the
#: same morning re-run reaches the same `outbound_messages` row — which the
#: queue's own unique key then refuses (CLAUDE.md rule 6). A random uuid4 here
#: would send a supervisor the same message every time anybody re-ran the sweep,
#: which is BR-NOT-020 broken by the back door.
SWEEP_NAMESPACE = uuid.UUID("6f1d0a52-9a3d-5c61-9a2f-2b1c0d4e7a11")


def sweep_id(tenant_id: Any, day: dt.date) -> uuid.UUID:
    """The idempotency key for one tenant's sweep of one banking day.

    Derived and never stored: two callers that mean the same sweep compute the
    same uuid without having to find each other's row first.
    """
    return uuid.uuid5(SWEEP_NAMESPACE, f"counter-watch:{tenant_id}:{day.isoformat()}")


@dataclass(frozen=True)
class TenantSweep:
    """What one tenant's sweep found, and what came of telling somebody."""

    tenant_id: str
    day: dt.date
    #: Tills that were still running when the banking day ended.
    open_at_cutoff: int
    #: Of those, the ones nobody has closed yet. This is `failed_count`.
    still_open: int
    #: The seam's own outcome rows — queued, already queued, suppressed by the
    #: utility's rule, refused for want of an addressee, or broken.
    outcomes: tuple[dict[str, Any], ...] = ()


@dataclass
class SweepResult:
    """Every tenant's answer, and the two numbers that make the zero readable."""

    tenants_examined: int = 0
    tills_left_open: int = 0
    by_tenant: list[TenantSweep] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)

    def sentence(self) -> str:
        """One line a reader can tell a pass from a fail by (hard-won law 7).

        It prints the SCOPE beside the RESULT on purpose: *"0 counters left
        open"* alone is what a sweep that entered no tenant would also print.
        """
        return (
            f"{self.tills_left_open} counter(s) left open across "
            f"{self.tenants_examined} tenant(s) examined; "
            f"{len(self.failed)} tenant(s) failed and were skipped. "
            "No till was closed by this sweep (PO ruling 2026-09-23)."
        )


def find_open_tills(*, tenant_id: Any, cutoff: dt.datetime) -> tuple[int, int]:
    """`(open_at_cutoff, still_open)` for ONE tenant, inside its context already.

    * `open_at_cutoff` — tills that had opened before `cutoff` and had not been
      closed by then: the shifts that were still running when the day ended.
    * `still_open` — of those, the ones `closed_at IS NULL` right now. The
      difference is somebody who closed late, this morning, before the sweep
      ran — a real and harmless thing that should not be reported as a problem.

    Both figures describe the SAME SET of tills — the second query is scoped to
    the ids the first returned — so the pair a supervisor reads cannot be about
    two different populations (`bankrec_read.batch_kpis`' discipline).

    ⚠ **THE SECOND FIGURE ASKS `still_open`, NOT `row.closed_at is None`.** The
    Python line is shorter and it is a SECOND COPY of
    `counter_session_models.STILL_OPEN` in a second language, free to drift the
    day that expression gains a clause — the drift `CR-136-BRC07` §3.2 forbids
    by name for its sibling state, and the same argument `bankrec.is_bankable`
    makes one module over. One extra indexed query against `ix_counter_
    sessions_open`, on a job that runs once a morning, is the whole cost.

    A till closed BETWEEN the two queries simply moves out of the second, which
    is the right answer: somebody closed it, so it is not a supervisor's
    problem.
    """
    open_at_cutoff_ids = list(
        tills.CounterSession.objects.filter(tenant_id=tenant_id, opened_at__lt=cutoff)
        .exclude(closed_at__lt=cutoff)
        .values_list("id", flat=True)
    )
    if not open_at_cutoff_ids:
        return 0, 0
    still = tills.still_open(
        tills.CounterSession.objects.filter(tenant_id=tenant_id, id__in=open_at_cutoff_ids)
    ).count()
    return len(open_at_cutoff_ids), still


def sweep(
    tenant_days: Any,
    *,
    finished_at: dt.datetime,
    actor: Any = None,
) -> SweepResult:
    """Walk `(tenant_id, cutoff, day)` triples and tell a supervisor about each.

    `tenant_days` is an iterable the CALLER builds, exactly as
    `apps/audit/diagnostics.sweep_expired` takes its tenant ids: this module
    never reads the tenant registry `apps.tenancy` owns, and it never decides
    what day it is (BR-TEN-043).

    ⚠ **ONE TENANT'S FAILURE MUST NOT STOP THE REST, AND ON POSTGRESQL THAT
    TAKES A SAVEPOINT** (hard-won law 14). The nested `atomic()` here and the
    one inside `run_alert_seam.queue_counter_watch` are both load-bearing on the
    database the default suite does not run on. Do not "simplify" either away.

    ⚠ **`tenant_context` CLEARS ON EXIT rather than restoring what was there
    before** (`core/tenancy.py` — a job's normal shape is to have no ambient
    context). This loop enters it once per tenant, so without the save and
    restore below the sweep would return having silently emptied its CALLER's
    context, and every query after it would be denied with nothing visibly
    wrong. `apps/audit/diagnostics.sweep_expired` records the same trap.
    """
    result = SweepResult()
    previous = tenancy_kernel.current_tenant_id()
    for tenant_id, cutoff, day in tenant_days:
        key = str(tenant_id)
        try:
            with tenancy_kernel.tenant_context(tenant_id):
                # THE SAVEPOINT. See the docstring — law 14.
                with transaction.atomic():
                    open_at_cutoff, still = find_open_tills(tenant_id=tenant_id, cutoff=cutoff)
                outcomes = run_alert_seam.queue_counter_watch(
                    sweep_id=sweep_id(tenant_id, day),
                    total_count=open_at_cutoff,
                    failed_count=still,
                    finished_at=finished_at,
                    actor=actor,
                )
        except Exception as exc:  # noqa: BLE001 — one tenant must not stop the rest
            logger.exception("counter watch failed for tenant %s", key)
            result.failed[key] = type(exc).__name__
            continue
        result.tenants_examined += 1
        result.tills_left_open += still
        result.by_tenant.append(
            TenantSweep(
                tenant_id=key,
                day=day,
                open_at_cutoff=open_at_cutoff,
                still_open=still,
                outcomes=tuple(outcomes),
            )
        )
    if previous is not None:
        tenancy_kernel.set_current_tenant(previous)
    logger.info("counter watch: %s", result.sentence())
    return result


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-136-BRC07 §3.1 + task `P2.11` (12-governance/change-requests/CR-136-BRC07-payments-phase-2-the-counter.md) · 05-prototype "06 Payments Page Blueprint.pdf" p017 (the task row) + p051 (screen 3·1, the words "still open") + p059 (the acts table, where the OWNER is told on a force close) · 12-governance/02-decision-log.md 2026-09-23 (when it fires, and why this state) · apps/audit/diagnostics.sweep_expired (the per-tenant sweep precedent) · apps/payments/run_alert_seam.py (the seam) · apps/notifications/bulk_summary.py queue_counter_watch_summary
# generated: 2026-09-23 by lane P2-WIRE
# checklist: A✔ B=deferred(no screen of its own — the message lands in the AppShell bell, which shipped with CR-009; screen 3·1 is P2.6's) C✔ D=deferred(no endpoint — a management command, like every other sweep here) E=deferred(as B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report
# exceptions: (1) IT WRITES NOTHING TO `counter_sessions` — PO ruling 2026-09-23 §3.1 struck the auto-close, and the absence of a write is the deliverable rather than an omission. A test asserts a swept till is byte-identical afterwards. (2) [AMENDED 2026-09-23, DEF-PAY-6268] IT IS SCHEDULED — `apps/payments/counter_watch_schedule.py` fires this sweep at 06:00 on each utility's own clock, installed from `PaymentsConfig.ready()`. This exception read *"IT IS NOT SCHEDULED BY THIS LANE — … this repo has no beat schedule to add it to"*, and that second clause was false when written: five entries were already installed from five `ready()` methods, one of them in this app. The schedule CLOSES NOTHING either — it calls this module and this module writes nothing. (3) IT WRITES NO `audit_log` ROW: hard rule 7 attaches the trail to a MONEY action and this reads and tells; the queued message is itself the record. (4) `total_count` IS "open when the day ended" AND NOT "every till" — the reasoning is in `find_open_tills`, and it is what keeps a late close off the failure count.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
