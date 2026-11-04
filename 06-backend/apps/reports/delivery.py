# ── Trace ──────────────────────────────────────────────
# Story:    US-REP-015 (email delivery rides the outbound queue) ×
#           US-REP-014 (scheduled execution)   Screens: 4·1 · 5·1 · 5·2
# Change:   CR-142-BRC07 — the Reports Build Brief, Phase 4 task `P4.10`
#           (*"Deliver the file · The outbound queue carries the link, not the
#           file"*). Drawing p15 (the task table) and p39 (screen `5·1`, where
#           the link goes), read as IMAGES per B14 rule 42.
# Rules:    BR-NOT-005 (queue only) · BR-REP-007 (scheduled-report email rides
#           the outbound queue) · BR-REP-017 CONFIRMED (dispatch is W6; the
#           ROWS are written now) · BR-REP-018 (the file is kept three days) ·
#           BR-REP-020 CONFIRMED (internal staff only) · BR-TEN-043 (no wall
#           clock where a caller holds the date) · CLAUDE.md hard rule 1
#           (tenant scoping — this runs OUT OF REQUEST) · rule 6 (idempotency)
#           · hard-won law 2 and its mirror · law 5 (one record, never two)
# Tests:    06-backend/tests/test_cr142_p4_10_delivery.py
# Impacts:  apps/reports/schedules.py (`sweep_all_tenants` calls this after it
#           fires) · apps/reports/notifications_seam.py (the boundary) ·
#           apps/reports/run_history.py (the run's presented row — READ, not
#           edited)
# ───────────────────────────────────────────────────────
"""Delivery: the half of a schedule that happens after the file exists.

╔══════════════════════════════════════════════════════════════════════════╗
║  THE PHASE'S DONE-WHEN, from the brief's p14:                            ║
║  *"A schedule set on Friday produces a file on Monday, **delivered to    ║
║   named internal staff**."*                                              ║
╚══════════════════════════════════════════════════════════════════════════╝

⚠ **UNTIL THIS FILE THE PRODUCT STOPPED AT THE COMMA, AND EVERY CHECK WAS
GREEN OVER IT.** `schedules.py` fires the run; the file lands on screen `5·1`;
`report_schedules.recipients` holds the people the schedule names, refused by
name if they are not staff (`BR-REP-020`) — and **nothing ever read that list
again.** That is hard-won law 2's mirror on the server: not a control with no
screen behind it, but a stored list with no delivery behind it. Both halves are
correct on their own, and the question *does anything consume this* belonged to
nobody.

════════════════════════════════════════════════════════════════════════════
WHY THIS RECONCILES RATHER THAN HOOKS THE JOB
════════════════════════════════════════════════════════════════════════════
The obvious place to queue the message is *when the export job finishes*. That
point is **`apps/tenancy/exports.run_list_export_job`**, which belongs to the
platform's export kernel and is the same handler a clerk's Export button runs.
Reaching into it from here would mean either editing another module's job body
or wrapping the platform's `list_export` handler from `ReportsConfig.ready()`
— a registration whose correctness depends on `INSTALLED_APPS` order, which is
hard-won law 7's *structurally incapable of failing* waiting to happen.

So this module reconciles instead, on the beat entry reports already owns:
**for every schedule of this utility, look at the run it last started; if that
run is READY and its message is not on the queue, put it there.** It needs no
foreign hook, it is idempotent by the queue's own key, and a worker that was
down for an hour delivers when it comes back rather than losing the message.

⚠ **AND IT CANNOT ANNOUNCE A RUN THAT FAILED.** The status it reads is the one
screen `5·1` draws — `run_history.present` — so *failing* on `4·1` and *no
email* are the same fact read from the same place. A hook at enqueue time would
have emailed *"your report is ready"* about a run that errored four seconds
later.

════════════════════════════════════════════════════════════════════════════
THERE IS NO `delivered_at` COLUMN, AND THAT IS A DECISION
════════════════════════════════════════════════════════════════════════════
A column would let this skip the queue lookup on the runs it has already
delivered. It is not built, for hard-won law 5's reason: **the queue row IS the
record of delivery**, and a second column recording the same fact is a second
copy free to disagree with it — a schedule marked delivered whose message was
suppressed by the utility's own SET-12 rule, or the reverse after a restore.

The cost is stated rather than hidden: one `SELECT` over `outbound_messages`
per enabled schedule per minute, for the three days its run's file survives
(`BR-REP-018`). At the top of the ICP — `T5`, forty thousand accounts — a
utility with fifty schedules is fifty indexed lookups a minute on a unique key.
Measured against the alternative, that is the cheaper mistake to be making.

════════════════════════════════════════════════════════════════════════════
THE LINK IS AN ADDRESS ON THIS PRODUCT, AND IT NEEDS THE UTILITY'S SLUG
════════════════════════════════════════════════════════════════════════════
`P4.10`'s outcome is *"recipients get a link that respects their permissions"*,
and the address that does is screen `5·2` — `/{tenant}/reports/history/{run}`,
behind the same sign-in as every other screen. Opening it as somebody who is
not staff of that utility gets them nothing.

⚠ **THE SLUG IS AN ARGUMENT AND IS NEVER GUESSED.** `core.tenancy` resolves a
slug to an id and publishes no reverse, and `report_seams.py` — the file that
would carry such a read — is not this lane's to edit. `sweep_all_tenants`
already holds the slug: it is what its outer loop iterates. So it is passed
down. **A caller that cannot supply one gets NO message rather than a link
with a hole in it**, and the reason is returned rather than logged and lost.
"""

from __future__ import annotations

import logging
from typing import Any

from django.utils import timezone

from apps.reports import notifications_seam, run_history, schedules
from apps.reports.models import ReportSchedule

logger = logging.getLogger(__name__)

#: The only run status that has a file behind it. `run_history.present`
#: derives it, and `expired` is the fifth thing a row can say — a run whose
#: three days are up, whose link would open onto a disabled download.
STATUS_READY = "ready"

#: Screen `5·2`'s address, as the front end builds it
#: (`ReportRunsPage.tsx`: ``${historyBase}/${row.id}``). Spelled once, here,
#: because a link is the one thing in this file a person will actually click.
RUN_PATH = "/{tenant}/reports/history/{run}"

#: What `deliver_ready_runs` says about a schedule it did not deliver for.
NOT_DELIVERED_NO_RUN = "schedule_has_not_run_yet"
NOT_DELIVERED_NOT_READY = "run_has_no_file"
NOT_DELIVERED_NO_RECIPIENTS = "schedule_names_nobody"
NOT_DELIVERED_NO_TENANT_SLUG = "no_tenant_slug_so_no_link"


def run_link(tenant_slug: str, run_id: Any) -> str:
    """Screen `5·2`'s address for one run. A PATH, never a whole URL.

    ⚠ **NO HOST AND NO SCHEME.** This product is deployed under a host nothing
    in the backend is told about reliably, and a message carrying
    `http://localhost:8000/...` to a utility's finance manager is worse than
    one carrying a path — the path is at least correct wherever it is read
    from. The dispatcher that ships at W6 is the layer that knows the public
    origin, and it is the layer that must prepend it.
    """
    return RUN_PATH.format(tenant=tenant_slug, run=run_id)


def _presented(schedule: ReportSchedule) -> dict[str, Any] | None:
    """The run this schedule last started, as screen `5·1` draws it.

    `None` when the schedule has never fired, or when its job is one this
    module cannot see — `run_history.run` filters by the report resources and
    the run kinds, so a job of another kind answers `None` rather than being
    presented as a report run it is not.
    """
    if not schedule.last_job_id:
        return None
    try:
        return run_history.run(schedule.last_job_id)
    except Exception:  # noqa: BLE001 — one unreadable run must not stop the rest
        logger.exception(
            "the run behind report schedule %s could not be read, so no message was "
            "queued for it. Nothing is lost: the next sweep reads it again.",
            schedule.pk,
        )
        return None


def deliver_for(
    schedule: ReportSchedule,
    *,
    tenant_slug: str | None,
    actor: Any = None,
) -> dict[str, Any]:
    """Queue the message for ONE schedule's last run, if there is one to queue.

    Always returns a dict with a `code`; it never raises. The sweep records it
    and moves on, because one utility's broken template must not stop another
    utility's month-end pack.
    """
    row = _presented(schedule)
    if row is None:
        return {"code": NOT_DELIVERED_NO_RUN, "schedule": str(schedule.pk)}
    if row.get("status") != STATUS_READY:
        # Running, queued, failed or expired. `4·1` already says *failing* for
        # the third of those (`P4.8`) and this silence is the same fact.
        return {
            "code": NOT_DELIVERED_NOT_READY,
            "schedule": str(schedule.pk),
            "status": row.get("status"),
        }
    if not tenant_slug:
        return {"code": NOT_DELIVERED_NO_TENANT_SLUG, "schedule": str(schedule.pk)}
    try:
        people = schedules.resolve_recipients(schedule.tenant_id, schedule.recipients or ())
    except schedules.RecipientError as refused:
        # A person who has left the utility since the schedule was written.
        # The run still happened and is still on `5·1`; what is gone is the
        # envelope, and saying so is the whole point of returning a code.
        return {
            "code": NOT_DELIVERED_NO_RECIPIENTS,
            "schedule": str(schedule.pk),
            "detail": str(refused),
        }
    answer = notifications_seam.queue_scheduled_report(
        run_id=row["id"],
        report_name=_report_name(schedule),
        ran_at=str(row.get("ran_at") or ""),
        report_link=run_link(tenant_slug, row["id"]),
        expires_on=str(row.get("expires_at") or "") or None,
        recipients=tuple((person.name, person.email) for person in people),
        actor=actor,
        job="reports.schedule",
    )
    return {**answer, "schedule": str(schedule.pk), "run": str(row["id"])}


def _report_name(schedule: ReportSchedule) -> str:
    """The report's own NAME, never its key and never a database id.

    B14 rule 31 is about screens, and this is an email — but the reasoning
    reaches further than the rule's wording: *AR Ageing* is what the schedule
    says on `4·1` and what Dana asked for, and `ar_aging` is a spelling only
    this codebase uses.
    """
    definition = getattr(schedule, "definition", None)
    return str(getattr(definition, "name", "") or "").strip() or str(
        (schedule.params or {}).get("resource") or ""
    )


def deliver_ready_runs(*, tenant_slug: str | None, actor: Any = None) -> dict[str, Any]:
    """Every schedule of the CURRENT tenant whose last run has a file.

    Context must be set — `report_schedules` is RLS FORCE and there is no
    `.filter(tenant_id=…)` here, for the reason `schedules.due` states in full:
    a belt-and-braces filter in Python makes a missing context look like an
    empty result instead of like the bug it is.

    ⚠ **PAUSED SCHEDULES ARE INCLUDED, AND THAT IS DELIBERATE.** A clerk who
    pauses a schedule at 06:05 has not asked to be denied the file that ran at
    06:00. `enabled` decides whether a schedule FIRES; it does not decide
    whether a run that already happened is delivered.

    ⚠ **AND A RUN WHOSE FILE HAS ALREADY BEEN SWEPT IS NEVER ANNOUNCED.** After
    `BR-REP-018`'s three days `run_history.present` calls the run `expired`, so
    it stops being READY and no message is queued for it. The consequence is
    stated rather than discovered: **a worker down for longer than the
    retention window loses that run's message**, and the right answer is that
    it should — the link would open onto a row with no download on it, which is
    the dead control this phase spent `P3.5` removing.
    """
    outcomes: list[dict[str, Any]] = []
    queued = 0
    sent = 0
    for schedule in ReportSchedule.objects.select_related(
        "definition", "destination"
    ).exclude(last_job_id=None):
        outcome = deliver_for(schedule, tenant_slug=tenant_slug, actor=actor)
        outcomes.append(outcome)
        if outcome.get("code") == notifications_seam.REPORT_MESSAGE_QUEUED:
            queued += 1
        if deliver_to_destination(schedule, outcome, actor=actor) is not None:
            sent += 1
    return {"queued": queued, "sent": sent, "outcomes": outcomes}


def deliver_to_destination(
    schedule: ReportSchedule, outcome: dict[str, Any], *, actor: Any = None
) -> Any | None:
    """`P4.14` — the SAME ready run, also pushed to an admin-set destination.

    ⚠ **IT RIDES ON THIS SWEEP RATHER THAN ON A SECOND ONE**, which is §7.8's
    own word for the tier: *"Rides on schedules."* A separate beat would be a
    second opinion about whether a run is READY, and the two would disagree the
    first time a retention sweep landed between them.

    ⚠ **IT READS THIS FUNCTION'S OWN `outcome` AND RE-DERIVES NOTHING.** The
    run's readiness has already been decided one line up, by `run_history`,
    which is the same place screen `5·1` reads it from. Asking again here would
    be a second reading of *did it work* — the `bell_events` shape this
    module's own class docstring refuses.

    ⚠ **A SCHEDULE WITH NO DESTINATION IS THE ORDINARY CASE AND IS NOT A
    FAILURE.** `destination_id` is NULL on every schedule written before
    `P4.14` and on every one nobody pointed at a destination, and those keep
    behaving exactly as `P4.10` left them: the outbound queue and nothing else.

    ⚠ **A DESTINATION FAILURE NEVER STOPS THE EMAIL, AND NEVER STOPS THE NEXT
    UTILITY.** This is called AFTER `deliver_for` has already queued the
    message, and it swallows its own errors into a `failed` delivery row for
    the same reason `deliver_for` never raises: *"one utility's broken template
    must not stop another utility's month-end pack."*
    """
    from apps.reports import destinations as reports_destinations
    from apps.reports import models as reports_models

    if schedule.destination_id is None:
        return None
    if outcome.get("code") == notifications_seam.REPORT_MESSAGE_QUEUED:
        run_id = outcome.get("run")
    elif outcome.get("code") == NOT_DELIVERED_NO_RECIPIENTS:
        # ⚠ **A SCHEDULE MAY NAME A DESTINATION AND NOBODY ELSE**, which is
        # exactly the BI case: a machine collects the file and no person is
        # emailed. `NOT_DELIVERED_NO_RECIPIENTS` is not a reason to withhold
        # the file from a destination an administrator set up.
        row = _presented(schedule)
        run_id = row["id"] if row and row.get("status") == STATUS_READY else None
    else:
        return None
    if run_id is None:
        return None

    try:
        return reports_destinations.deliver(
            schedule,
            job_id=run_id,
            now=timezone.now(),
            actor_user_id=getattr(actor, "user_id", None),
        )
    except Exception as failure:  # noqa: BLE001 — recorded, never raised
        # ⚠ **THE FAILURE IS A ROW, NOT A LOG LINE.** *"Every delivery logged"*
        # is the ruling's third condition and a delivery that did not happen is
        # the one a person most needs to find afterwards.
        reports_models.ReportDelivery.objects.get_or_create(
            tenant_id=schedule.tenant_id,
            destination_id=schedule.destination_id,
            schedule=schedule,
            job_id=run_id,
            defaults={
                "status": reports_models.DELIVERY_FAILED,
                "detail": str(failure)[:500],
            },
        )
        return None


__all__ = [
    "NOT_DELIVERED_NOT_READY",
    "deliver_to_destination",
    "NOT_DELIVERED_NO_RECIPIENTS",
    "NOT_DELIVERED_NO_RUN",
    "NOT_DELIVERED_NO_TENANT_SLUG",
    "RUN_PATH",
    "STATUS_READY",
    "deliver_for",
    "deliver_ready_runs",
    "run_link",
]

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P4.10 (05-prototype/09 Reports Build Brief.pdf pp14–15 and p39, read as images per B14 rule 42) · 04-docs/05-modules/12-reports/06-epics/EP-REP-04-scheduler.md US-REP-014/US-REP-015 · 04-docs/05-modules/12-reports/02-business-rules.md BR-REP-007/017/018/020 · apps/reports/schedules.py · apps/reports/run_history.py
# screens: 4·1 · 5·1 · 5·2
# generated: 2026-09-27 by lane REP-P4-REST
# checklist: A✔ B=n/a(delivery has no drawn surface in this brief — p40's `4·1` draws no delivery column) C✔ D=deferred(no new API surface) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_cr142_p4_10_delivery.py was run before this file existed and reported `ModuleNotFoundError: No module named 'apps.reports.delivery'`.
# exceptions: (1) RECONCILE, NOT A JOB HOOK — the completion point is `apps/tenancy/exports.run_list_export_job`, another module's kernel, and wrapping the platform's `list_export` handler from `ready()` would depend on INSTALLED_APPS order. Stated in the docstring with the law-7 reasoning · (2) NO `delivered_at` COLUMN — the queue row is the record (law 5); the per-minute lookup this costs is measured and stated · (3) THE LINK IS A PATH, not a URL: nothing in the backend is reliably told the public origin, and the W6 dispatcher is the layer that knows it · (4) PAUSED schedules still deliver a run that already finished. Stated, not implied.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
