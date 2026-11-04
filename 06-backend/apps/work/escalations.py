# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 5, lane SRV-4 — P3.57 (the seven escalations
#           fire), P3.36's second half (step 4 is READ), P3.59 (the two
#           reminders Notifications gained are written here). Images 59, 61, 62.
# Rules:    Ruling 34 (24 Sep) · the PO's 26 Sep ruling (escalations are rows;
#           *Also tell* ADDS) · BR-NOT-021 narrowed for Work escalations (PO
#           2026-10-04) · BR-WRK-002 (Work writes no other module's table; the
#           message is queued through notifications' own door) · CLAUDE.md
#           hard rule 7 (audited) · hard-won law 14 (a SAVEPOINT per fire)
# Tests:    06-backend/tests/test_cr168_srv4_escalations.py (SQLite and
#           PostgreSQL 16)
# ───────────────────────────────────────────────────────
"""`work.escalations_sweep` — a job that stalls is told about, once per kind.

A rule's *When it stalls* rows (`work_order_rules.escalation`, a list since
round 5) are read against the jobs THAT RULE raised or shaped:

    unassigned        nobody holds it N hours after it was raised
    not_accepted      held, and the technician has not accepted it N hours
                      after it was given to them
    running_late      its appointment window ended N hours ago and nobody is
                      on site
    overdue           N hours past its promise (held time excluded — P5.2)
    on_hold_too_long  on hold for more than N hours
    failed            closed *Failed* N hours ago and still not accepted
    not_approved      closed N hours ago and still not accepted by the office

Each fires ONCE per job per kind — `work_order_rule_escalation_fires`' unique
key is the guarantee (an INSERT inside a SAVEPOINT; a second sweep's refusal is
the sweep being idempotent, law 14). The fire writes `audit_log` and queues ONE
in-app message through `notifications.work_escalations` (by name, through the
seam): whoever sent the job to the field and every System Admin, plus the row's
*Also tell* people (BR-NOT-021 narrowed for Work escalations, PO 2026-10-04).

**The clock starts when the JOB is raised** (the blueprint, P3.65: *"never from
which trigger raised it"*); each kind measures from its own moment above.

The same sweep writes P3.59's two reminders, which belong to Notifications
now (a rule may not carry reminders — `rules._clean_rule` refuses the key):
a certificate running out within the certification watch's 30 days (every
System Admin, once per certificate per expiry date), and a technician's day
(the technician, once a day, with how many jobs they hold today).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from apps.work import models as work_models
from apps.work import promise
from apps.work.seams import metering_seam, notifications_seam
from core import audit as core_audit
from core import jobs as core_jobs
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.work.escalations")

ESCALATIONS_SWEEP_JOB = "work.escalations_sweep"
WORK_QUEUE = "work"
BEAT_ENTRY = "work.escalations_sweep"
SWEEP_TASK = "work.escalations_sweep.all"
#: Hourly: the smallest *After* a rule can hold is one hour.
SWEEP_EVERY_SECONDS = 60 * 60

ACTION_ESCALATED = "work.order.escalated"

#: The certification watch's own window (`workforce.certification_watch`,
#: `DEF-WRK-9639`: *expiring only inside 30 days*) — one figure, two readers.
CERTIFICATE_REMINDER_DAYS = 30

_OPEN = ("planned", "in_progress", "blocked")


def _stalled(kind: str, hours: int, now: datetime) -> Q:
    """The SQL test for one escalation kind at `hours` (see the docstring)."""
    cutoff = now - timedelta(hours=int(hours))
    held = Q(assignee_technician__isnull=False) | Q(assignee_crew__isnull=False)
    open_job = Q(state__in=_OPEN) & ~Q(dispatch_state="cancelled")
    if kind == "unassigned":
        return open_job & ~held & Q(created_at__lte=cutoff)
    if kind == "not_accepted":
        return (
            open_job & held & Q(accepted_at_technician__isnull=True, declined_at__isnull=True)
            & Q(assigned_at__lte=cutoff)
        )
    if kind == "running_late":
        return (
            open_job & Q(window_end__isnull=False, window_end__lte=cutoff)
            & ~Q(dispatch_state__in=("on_site", "complete"))
        )
    if kind == "overdue":
        return open_job & Q(promise_due__isnull=False, promise_due__lte=cutoff)
    if kind == "on_hold_too_long":
        return open_job & Q(held_at__isnull=False, held_at__lte=cutoff)
    if kind == "failed":
        return Q(state="completed", outcome="failed", accepted_at__isnull=True,
                 completed_at__lte=cutoff)
    if kind == "not_approved":
        return Q(state="completed", accepted_at__isnull=True, completed_at__lte=cutoff)
    raise ValueError(kind)


def _fire(actor: Any, rule: Any, row: dict[str, Any], order: Any, now: datetime) -> bool:
    """One escalation of one job: the fire row and the audit row in ONE
    savepoint (the unique key refuses a second), then the message. Returns True
    when this call fired it."""
    try:
        with transaction.atomic():
            work_models.WorkOrderRuleEscalationFire.objects.create(
                tenant_id=rule.tenant_id, work_order_id=order.id, kind=row["kind"]
            )
            core_audit.write_row(
                action=ACTION_ESCALATED,
                entity_type="work_order",
                entity_id=order.id,
                after={
                    "rule": rule.name,
                    "kind": row["kind"],
                    "after_hours": row.get("after_hours"),
                    "order_no": order.order_no,
                    "also_tell": len(row.get("also_tell") or []),
                },
            )
    except IntegrityError:
        return False
    told = notifications_seam.queue_work_escalation(
        kind=row["kind"],
        order_id=order.id,
        order_no=order.order_no,
        acted_user_id=order.assigned_by_id,
        also_tell=row.get("also_tell") or [],
        after_hours=row.get("after_hours") or 0,
        occurred_at=now,
    )
    if not told or told.get("code") not in ("escalation_queued", "escalation_already_queued"):
        logger.info(
            "escalation %s of %s fired but nobody was told: %s", row["kind"], order.order_no, told
        )
    return True


def escalate(actor: Any = None, *, now: datetime | None = None) -> dict[str, Any]:
    """Run every enabled rule's escalation rows against the jobs it raised."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise RuntimeError("work.escalations_sweep ran with no app.tenant_id set")
    moment = now or timezone.now()
    hours_default = promise.default_hours()
    fired: list[dict[str, Any]] = []
    for rule in work_models.WorkOrderRule.objects.filter(tenant_id=tenant_id, enabled=True):
        rows = rule.escalation if isinstance(rule.escalation, list) else []
        for row in rows:
            if not row.get("kind") or not row.get("after_hours"):
                continue
            already = work_models.WorkOrderRuleEscalationFire.objects.filter(
                tenant_id=tenant_id, work_order_id=OuterRef("pk"), kind=row["kind"]
            )
            qs = (
                metering_seam.orders_raised_by_rule_queryset(rule.id)
                .annotate(promise_due=promise.due_expr(hours_default, open_clock=True))
                .filter(_stalled(row["kind"], int(row["after_hours"]), moment))
                .exclude(Exists(already))
                .order_by("created_at", "id")
            )
            for order in qs:
                if _fire(actor, rule, row, order, moment):
                    fired.append({"rule": rule.name, "kind": row["kind"], "order_no": order.order_no})
    reminders = remind(now=moment)
    # `CR-168-BRC10` P6.2 (lane SRV-5) — the office told a job is AT RISK, on
    # every job (no rule row), once per promise.
    from apps.work import visit_notices

    at_risk = visit_notices.at_risk_sweep(now=moment)
    return {"fired": fired, "count": len(fired), "reminders": reminders,
            "at_risk": at_risk, "tenant_id": str(tenant_id)}


def remind(*, now: datetime | None = None) -> dict[str, int]:
    """P3.59 — the two reminders Notifications owns, written here once each."""
    from apps.work import workforce
    from apps.work.seams import tenancy_seam

    moment = now or timezone.now()
    today = moment.astimezone(tenancy_seam.tenant_timezone()).date()
    tenant_id = core_tenancy.current_tenant_id()
    names = {kind["id"]: kind["name"] for kind in tenancy_seam.certification_types()}
    certificates = 0
    for cert in work_models.TechnicianCertification.objects.filter(
        tenant_id=tenant_id,
        expires_on__gt=today,
        expires_on__lte=today + timedelta(days=CERTIFICATE_REMINDER_DAYS),
    ).select_related("technician__user"):
        person = cert.technician.user.full_name or cert.technician.user.email
        told = notifications_seam.queue_work_reminder(
            reminder="certificate_expiring",
            subject_id=cert.id,
            title=f"{person} · {names.get(str(cert.certification_type_id)) or '—'}",
            count=(cert.expires_on - today).days,
            discriminator=cert.expires_on.isoformat(),
            occurred_at=moment,
        )
        certificates += 1 if (told or {}).get("code") == "escalation_queued" else 0
    days = 0
    start = datetime.combine(today, datetime.min.time()).replace(
        tzinfo=tenancy_seam.tenant_timezone()
    )
    end = start + timedelta(days=1)
    held_today = (
        metering_seam.open_work_orders_queryset()
        .filter(assignee_technician__isnull=False)
        .filter(
            Q(window_start__gte=start, window_start__lt=end)
            | Q(window_start__isnull=True, due_at__gte=start, due_at__lt=end)
        )
    )
    counts: dict[Any, int] = {}
    for technician_id in held_today.values_list("assignee_technician_id", flat=True):
        counts[technician_id] = counts.get(technician_id, 0) + 1
    for technician in work_models.Technician.objects.filter(
        tenant_id=tenant_id, pk__in=list(counts)
    ).select_related("user"):
        told = notifications_seam.queue_work_reminder(
            reminder="technician_day",
            subject_id=technician.id,
            title=workforce.technician_slug(technician),
            count=counts[technician.id],
            discriminator=today.isoformat(),
            user_id=technician.user_id,
            occurred_at=moment,
        )
        days += 1 if (told or {}).get("code") == "escalation_queued" else 0
    return {"certificates": certificates, "technician_days": days}


# ── The job, its queue and the beat entry (the rules sweep's shape) ─────────


def run_escalations_job(record: dict[str, Any]) -> dict[str, Any]:
    payload = dict(record.get("payload") or {})
    tenant_id = record.get("tenant_id") or payload.get("tenant_id")
    with core_tenancy.tenant_context(tenant_id):
        return escalate(None)


def scope_key(tenant_id: Any, when: datetime | None = None) -> str:
    """One sweep per tenant per HOUR (`core.jobs` folds a duplicate firing)."""
    moment = when or datetime.now(dt_timezone.utc)
    return f"{tenant_id}:{ESCALATIONS_SWEEP_JOB}:{moment.strftime('%Y-%m-%dT%H')}"


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
    """ONE firing: enqueue a sweep for every live utility (the rules sweep's
    fan-out, for its reason — one utility's slow hour must not delay another's)."""
    from importlib import import_module

    try:
        listed = import_module("apps.tenancy.selectors").live_tenant_subdomains()
    except Exception:  # noqa: BLE001 — a broken read must not stop the beat
        logger.exception("the live-utility read failed; no escalation sweep this hour")
        return {"tenants": 0, "queued": []}
    queued: list[str] = []
    for slug in listed or ():
        tenant_id = core_tenancy.tenant_id_for_slug(str(slug))
        if tenant_id is None:
            continue
        with core_tenancy.tenant_context(tenant_id):
            record = core_jobs.enqueue(
                ESCALATIONS_SWEEP_JOB,
                scope_key=scope_key(tenant_id),
                payload={"tenant_id": str(tenant_id)},
            )
        queued.append(str(record["id"]))
    return {"tenants": len(queued), "queued": queued}


_SWEEP_ALL_TASK: Any = None


def install(app: Any = None) -> dict[str, Any]:
    """Register the beat entry and the fan-out task. Idempotent; never raises
    (a deployment without celery starts, `rules.install`'s reasoning)."""
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
    core_jobs.set_job_handler(ESCALATIONS_SWEEP_JOB, run_escalations_job)
    core_jobs.set_job_queue(ESCALATIONS_SWEEP_JOB, WORK_QUEUE)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-168-BRC10 §7.3 (escalations) · P3.57 · P3.59 · images 59, 61, 62
# generated: 2026-10-04 by CR-168 round 5 lane SRV-4
# checklist: A✔ B✔ C✔ D=n/a(no endpoint) E=n/a F✔ G✔ H=n/a(no migration — `work/0029` landed the fires table)
# gates: G78 · G109 (the `work` queue) · pytest on SQLite and PostgreSQL 16
# status: AI-AUTHORED
# ──────────────────────────────────────────────────────────
