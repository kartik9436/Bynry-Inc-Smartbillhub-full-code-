# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 (the native field app) · Phase 13 · T-41 — lane S-FIND
# Screens:  FF-42 Alerts · FF-43 Emergency (04-docs/05-modules/18-field-app/
#           wireframes/phone/FF-42-alerts.png, FF-43-emergency.png)
# Rules:    BR-FLD-00028 (R28 — an emergency must be acknowledged; no
#           acknowledgement in 5 minutes and dispatch is told) · BR-FLD-00029
#           (R29 — dispatch messages only, no crew-to-crew chat) · BR-WRK-034
#           (the push) · BR-NOT-021 (who in the office is told of a failure) ·
#           CLAUDE.md hard rules 1 and 7 · hard-won law 14 (a SAVEPOINT per fire)
# Endpoints: 07-endpoints.md §5 N25
# Tests:    06-backend/tests/test_cr187_find_alerts.py (SQLite) ·
#           tests/test_cr187_find_pg.py (PostgreSQL 16)
# ───────────────────────────────────────────────────────
"""Alerts a dispatcher sends to a handset, and the emergency's five minutes.

THE FOUR KINDS (T-41), AND WHO SENDS THEM
-----------------------------------------
*Urgent assignment · emergency · schedule change · dispatch message* — each with
its own sound and Android channel (`push.PUSH_KINDS`). A dispatcher SENDS one
(`POST /work/field-alerts`): E2E-22 is *"A gas odour is dispatched to the
nearest crew"* — a person decides it is an emergency. ⚠ **NOTHING HERE DECIDES
THAT AN ORDER IS AN EMERGENCY ON ITS OWN.** No column, priority or type in this
product means *emergency*, and choosing one (P1? a type named *Gas leak*?)
would be inventing a business answer.

⚠ **SINCE 2026-10-21 THE TENANT'S OWN PRIORITY SETTING DOES, AND THE SENTENCE
ABOVE IS ABOUT THIS PRODUCT, NOT THE UTILITY.** PO answer 9 (decision log
*"Field app: ten PO answers"*): *"yes"* — a job MAY be pushed as urgent or
emergency automatically. Our judgment for how: `work_priorities.push_kind`, a
tenant setting per priority (seeded: most urgent active priority `emergency`,
the next `urgent_assignment`, the rest `new_job`), and a dispatcher may still
choose per assignment (`push_kind` on `POST /work-orders/{id}/assignments`).
⚠ **AND THE PO CORRECTED IT THE SAME DAY: IT IS AN OPTION.** The mapping is
read only while the tenant's `work_settings.push_by_priority` is ON (`GET|POST
/work/settings/push`, seeded OFF for every tenant — our judgment); OFF, only a
dispatcher's explicit choice sends urgent or emergency.
An assignment that rings as one of these two writes THE SAME ALERT ROW a
dispatcher's send of that kind writes — `record_assignment_alert` below — so an
automatic emergency is acknowledged on FF-43 and escalated by the same sweep
after the same five minutes (R28). Nothing here guesses: the utility chose the
mapping on Settings, or kept the seeded one.

R29 — *"Dispatch messages only. No crew-to-crew chat"*: the only sender is an
office login; the handset has no route to send one.

R28 — THE FIVE MINUTES
----------------------
An emergency row is written with `ack_due_at = sent_at + 5 min`. The technician
answers with `POST /work/mobile/alerts/{id}/ack`. A sweep (`work.alerts_sweep`)
runs every MINUTE through the beat this module installs — the same three
statements `escalations.py` uses (job body, the `work` queue, the beat entry),
never a second scheduler — and for every emergency past its due time and still
unanswered it, ONCE (a conditional UPDATE inside a savepoint is the guarantee):

1. stamps `escalated_at` and writes `audit_log` (`work.alert.emergency_unacknowledged`);
2. asks notifications to tell the office (`notifications_seam.queue_work_office_notice`,
   kind `emergency_unacknowledged`) and records notifications' own answer in
   `dispatch_told`;
3. leaves the row on the office list `GET /work/field-alerts?state=overdue`.

So dispatch is told within a minute of the five minutes running out (the sweep's
granularity), and the fan-out enqueues a tenant's sweep ONLY when that tenant
has an emergency due — a beat that wrote a job row per tenant per minute for
nothing would fill the jobs table with noise.

THE OFFICE MESSAGE (`DEF-WRK-10350`, 2026-10-21). Before that fix notifications
refused `emergency_unacknowledged` by name and `dispatch_told` read
`escalation_refused`, so only the audit row and the office list told dispatch.
Notifications now carries it as a fourth back-office kind beside *at risk,
declined, blocked*: its own catalogue switch (`work_emergency_unacknowledged`),
the sender and every active System Admin told, and the bell reads the job
number and the technician who did not answer
(`notifications.workOffice.emergency_unacknowledged`). `dispatch_told` records
notifications' own answer — `escalation_queued`, or `escalation_suppressed_by_rule`
when the utility has switched the notice off — and
`test_cr187_find_alerts.py` asserts the bell end to end.

A LATE ANSWER IS STILL AN ANSWER
--------------------------------
An acknowledgement after `ack_due_at` is recorded, marked `late`, and does not
un-tell dispatch: the office has already started phoning, and a person needs to
see both facts.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone

from apps.work import mobile, push
from apps.work import models as work_models
from apps.work.alert_models import (
    ALERT_KINDS,
    KIND_DISPATCH_MESSAGE,
    KIND_EMERGENCY,
    KIND_URGENT_ASSIGNMENT,
)
from apps.work.seams import metering_seam, notifications_seam
from core import audit as core_audit
from core import errors
from core import jobs as core_jobs
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.work.field_alerts")

#: R28 — *"No acknowledgement in 5 minutes and dispatch is told"*.
ACK_WINDOW = timedelta(minutes=5)
BR_REF = "BR-FLD-00028"

ACTION_SENT = "work.alert.sent"
ACTION_ACKNOWLEDGED = "work.alert.acknowledged"
ACTION_UNACKNOWLEDGED = "work.alert.emergency_unacknowledged"
#: The office notice kind asked of notifications (`OFFICE_EVENT_BY_KIND` there,
#: `DEF-WRK-10350`).
OFFICE_NOTICE_KIND = "emergency_unacknowledged"

ALERTS_SWEEP_JOB = "work.alerts_sweep"
WORK_QUEUE = "work"
BEAT_ENTRY = "work.alerts_sweep"
SWEEP_TASK = "work.alerts_sweep.all"
#: Every minute: the window is five, and dispatch must hear within the sixth.
SWEEP_EVERY_SECONDS = 60

OFFICE_STATES: tuple[str, ...] = ("all", "awaiting_ack", "overdue")


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def _uuid_or_404(raw: Any) -> Any:
    """An id from a body: absent → None; not a uuid → the same 404 as an id
    that names nothing (never a 500 from the ORM's own parse)."""
    import uuid

    if raw is None or str(raw).strip() == "":
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except ValueError:
        raise errors.deny_as_not_found("BR-TEN-003") from None


def _alert_row(alert: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """One alert as FF-42 lists it and FF-43 draws it. Names and numbers, never
    a uuid on screen (B14 rule 31); `id` is for the acknowledgement."""
    from apps.work import dispatch as work_dispatch

    moment = now or timezone.now()
    order = alert.work_order
    late = bool(
        alert.ack_required
        and alert.ack_due_at is not None
        and (
            (alert.acknowledged_at is not None and alert.acknowledged_at > alert.ack_due_at)
            or (alert.acknowledged_at is None and moment > alert.ack_due_at)
        )
    )
    return {
        "id": str(alert.id),
        "kind": alert.kind,
        "work_order_id": str(alert.work_order_id) if alert.work_order_id else None,
        "order_no": getattr(order, "order_no", None),
        "premise": work_dispatch._premise_of(order) if order is not None else None,
        "technician": mobile._technician_name(alert.technician) or None,
        "message": alert.message,
        "sent_at": alert.sent_at.isoformat(),
        "ack_required": alert.ack_required,
        "ack_due_at": alert.ack_due_at.isoformat() if alert.ack_due_at else None,
        "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
        "late": late,
        "dispatch_told": alert.escalated_at is not None,
        "escalated_at": alert.escalated_at.isoformat() if alert.escalated_at else None,
        "devices_attempted": alert.devices_attempted,
        # FF-43's countdown — whole seconds left, computed HERE so the phone's
        # clock (which may be wrong, E2E-23) never decides when dispatch is told.
        "seconds_to_ack": (
            max(0, int((alert.ack_due_at - moment).total_seconds()))
            if alert.ack_required and alert.ack_due_at and alert.acknowledged_at is None
            else None
        ),
        "server_now": moment.isoformat(),
    }


def _alerts() -> Any:
    return work_models.WorkFieldAlert.objects.filter(tenant_id=_tenant_id()).select_related(
        "technician__user", "work_order"
    )


# ══════════════════════════════════════════════════════════════════════════
# The office: send (N25)
# ══════════════════════════════════════════════════════════════════════════


def send_alert(actor: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work/field-alerts` — `{kind, work_order_id?, technician_id?,
    message?, key?}`.

    * `kind` — one of the four (`alert_models.ALERT_KINDS`).
    * `work_order_id` — required for every kind but a dispatch message.
    * `technician_id` — whom to alert; defaults to the order's technician. A job
      held by a CREW and no technician is refused by name: an alert rings ONE
      handset's owner, and choosing a crew member is dispatch's decision.
    * `message` — required for a dispatch message (R29), optional otherwise.
    * `key` — the sender's idempotency key; a repeat returns the first alert.

    The row is written first, then the push is enqueued (`core.jobs.enqueue`
    saves before it dispatches), so a dead broker loses a doorbell and never an
    alert or its five-minute clock.
    """
    kind = str(payload.get("kind") or "").strip()
    if kind not in ALERT_KINDS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            br_ref="BR-FLD-00029",
            params={"reason": "kind_unknown", "kind": kind or "—"},
        )
    message = str(payload.get("message") or "").strip()
    if kind == KIND_DISPATCH_MESSAGE and not message:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            br_ref="BR-FLD-00029",
            params={"reason": "message_required", "field": "message"},
        )
    key = str(payload.get("key") or "").strip() or None
    if key is not None:
        existing = _alerts().filter(key=key).first()
        if existing is not None:
            return {**_alert_row(existing), "duplicate": True, "push": None, "job_id": None}

    order = None
    order_id = _uuid_or_404(payload.get("work_order_id"))
    if order_id:
        order = metering_seam.work_order_row(order_id)
        if order is None:
            raise errors.deny_as_not_found("BR-TEN-003")
    elif kind != KIND_DISPATCH_MESSAGE:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            br_ref=BR_REF,
            params={"reason": "order_required", "field": "work_order_id"},
        )

    technician_id = _uuid_or_404(payload.get("technician_id")) or (
        order.assignee_technician_id if order is not None else None
    )
    if not technician_id:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref=BR_REF,
            params={"reason": "no_technician", "order_no": getattr(order, "order_no", None) or "—"},
        )
    technician = work_models.Technician.objects.filter(
        tenant_id=_tenant_id(), pk=technician_id
    ).select_related("user").first()
    if technician is None:
        raise errors.deny_as_not_found("BR-TEN-003")

    now = timezone.now()
    ack_required = kind == KIND_EMERGENCY
    try:
        with transaction.atomic():
            alert = work_models.WorkFieldAlert.objects.create(
                tenant_id=_tenant_id(),
                kind=kind,
                work_order_id=getattr(order, "id", None),
                technician_id=technician.id,
                message=message,
                sent_by_id=_actor_id(actor),
                sent_at=now,
                key=key,
                ack_required=ack_required,
                ack_due_at=(now + ACK_WINDOW) if ack_required else None,
            )
            core_audit.write_row(
                action=ACTION_SENT,
                entity_type="work_field_alert",
                entity_id=alert.id,
                actor_user_id=_actor_id(actor),
                after={
                    "kind": kind,
                    "order_no": getattr(order, "order_no", None),
                    "technician": mobile._technician_name(technician) or None,
                    "ack_due_at": alert.ack_due_at.isoformat() if alert.ack_due_at else None,
                },
            )
    except IntegrityError:
        # Two presses of *Send* raced on the same key: the other one won.
        existing = _alerts().filter(key=key).first() if key else None
        if existing is None:
            raise
        return {**_alert_row(existing), "duplicate": True, "push": None, "job_id": None}

    data = {
        "alert_id": alert.id,
        "work_order_id": getattr(order, "id", None),
        "order_no": getattr(order, "order_no", None),
    }
    job_id = None
    try:
        record = core_jobs.enqueue(
            push.ALERT_PUSH_JOB,
            payload={k: (None if v is None else str(v)) for k, v in data.items()},
            scope_key=f"alert:{alert.id}",
        )
        job_id = str(record["id"])
    except Exception as exc:  # noqa: BLE001 — the alert stands; the next sync carries it
        logger.warning("work.alert_push could not be enqueued for alert %s: %r", alert.id, exc)
    alert = _alerts().get(pk=alert.pk)
    return {
        **_alert_row(alert, now=now),
        "duplicate": False,
        "push": push.push_message(kind, data),
        "job_id": job_id,
    }


def record_assignment_alert(
    actor: Any, order: Any, technician: Any, kind: str, *, assignment_id: Any
) -> Any:
    """The alert an ASSIGNMENT writes when it rings as `urgent_assignment` or
    `emergency` (PO answer 9, 2026-10-21) — the SAME row `send_alert` writes
    for a dispatcher's send of that kind, so FF-42 lists it, an emergency
    carries `ack_due_at = sent_at + 5 min` and the R28 sweep escalates it
    exactly as it escalates a dispatcher's.

    Keyed `assignment:<row id>` — one alert per assignment row, the push's own
    scope (`push.scope_key`), so a replay of the same assignment starts one
    five-minute clock and never two. Called AFTER the assignment commits
    (`dispatch.push_after_assign`); the caller decides what a failure costs.
    Audited `work.alert.sent` with `automatic: true` and the assignment, so a
    reader can tell the setting rang it rather than a person.
    """
    if kind not in (KIND_EMERGENCY, KIND_URGENT_ASSIGNMENT):
        raise ValueError(f"an assignment does not raise a {kind!r} alert")
    key = f"assignment:{assignment_id}"
    existing = _alerts().filter(key=key).first()
    if existing is not None:
        return existing
    now = timezone.now()
    ack_required = kind == KIND_EMERGENCY
    try:
        with transaction.atomic():
            alert = work_models.WorkFieldAlert.objects.create(
                tenant_id=_tenant_id(),
                kind=kind,
                work_order_id=order.id,
                technician_id=technician.id,
                message="",
                sent_by_id=_actor_id(actor),
                sent_at=now,
                key=key,
                ack_required=ack_required,
                ack_due_at=(now + ACK_WINDOW) if ack_required else None,
            )
            core_audit.write_row(
                action=ACTION_SENT,
                entity_type="work_field_alert",
                entity_id=alert.id,
                actor_user_id=_actor_id(actor),
                after={
                    "kind": kind,
                    "order_no": getattr(order, "order_no", None),
                    "technician": mobile._technician_name(technician) or None,
                    "ack_due_at": alert.ack_due_at.isoformat() if alert.ack_due_at else None,
                    "automatic": True,
                    "assignment_id": str(assignment_id),
                },
            )
    except IntegrityError:
        # A replay of the same assignment raced this one; the savepoint rolled
        # this insert back whole (law 14) and the other row stands.
        existing = _alerts().filter(key=key).first()
        if existing is None:
            raise
        return existing
    return alert


def office_alerts(*, state: Any = None, page: Any = 1, per: Any = 50) -> dict[str, Any]:
    """`GET /work/field-alerts?state=all|awaiting_ack|overdue&page=&per=` — the
    dispatcher's view. `overdue` is R28's list: emergencies past their five
    minutes and still unanswered — the office side of *dispatch is told*.
    Paged, no cap (NFR-3, NFR-5); oldest due first for the two ack states,
    newest sent first for `all`."""
    from apps.work.field_find import _page

    chosen = str(state or "all").strip().lower() or "all"
    if chosen not in OFFICE_STATES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            br_ref=BR_REF,
            params={"reason": "state_unknown", "state": chosen},
        )
    now = timezone.now()
    qs = _alerts()
    if chosen == "all":
        qs = qs.order_by("-sent_at", "-id")
    else:
        qs = qs.filter(ack_required=True, acknowledged_at__isnull=True)
        if chosen == "overdue":
            qs = qs.filter(ack_due_at__lte=now)
        qs = qs.order_by("ack_due_at", "id")
    rows, figures = _page(qs, page, per)
    return {**figures, "results": [_alert_row(a, now=now) for a in rows], "state": chosen}


# ══════════════════════════════════════════════════════════════════════════
# The handset: list and acknowledge
# ══════════════════════════════════════════════════════════════════════════


def my_alerts(actor: Any, *, page: Any = 1, per: Any = 50) -> dict[str, Any]:
    """`GET /work/mobile/alerts?page=&per=` — THIS technician's alerts (FF-42).
    An unanswered emergency first (FF-42 draws it at the top, *EMERGENCY · NOT
    ACKNOWLEDGED*), then newest first. No technician id is taken: the caller's
    own profile, or an empty page (07-endpoints.md §0 rule 10)."""
    from apps.work.field_find import _page

    technician = mobile.technician_of(actor)
    qs = _alerts().filter(technician_id=getattr(technician, "id", None)) if technician else _alerts().none()
    qs = qs.annotate(
        open_emergency=Case(
            When(Q(ack_required=True, acknowledged_at__isnull=True), then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by("open_emergency", "-sent_at", "-id")
    now = timezone.now()
    rows, figures = _page(qs, page, per)
    return {
        **figures,
        "results": [_alert_row(a, now=now) for a in rows],
        "unacknowledged": qs.filter(open_emergency=0).count(),
    }


def acknowledge(actor: Any, alert_id: Any) -> dict[str, Any]:
    """`POST /work/mobile/alerts/{id}/ack` — the technician answers.

    Idempotent: a second press returns the first answer's time. Another
    technician's alert — or another utility's — is a 404 byte-identical to one
    that does not exist (HR-1). An answer after the five minutes is kept and
    marked `late`; dispatch, already told, stays told.
    """
    technician = mobile.technician_of(actor)
    if technician is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    alert = _alerts().filter(pk=alert_id, technician_id=technician.id).first()
    if alert is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    now = timezone.now()
    with transaction.atomic():
        took = work_models.WorkFieldAlert.objects.filter(
            pk=alert.pk, acknowledged_at__isnull=True
        ).update(acknowledged_at=now, acknowledged_by_id=_actor_id(actor))
        if took:
            late = bool(alert.ack_due_at is not None and now > alert.ack_due_at)
            core_audit.write_row(
                action=ACTION_ACKNOWLEDGED,
                entity_type="work_field_alert",
                entity_id=alert.id,
                actor_user_id=_actor_id(actor),
                after={
                    "kind": alert.kind,
                    "order_no": getattr(alert.work_order, "order_no", None),
                    "late": late,
                    "dispatch_already_told": alert.escalated_at is not None,
                },
            )
    alert = _alerts().get(pk=alert.pk)
    return {**_alert_row(alert, now=now), "already_acknowledged": not took}


# ══════════════════════════════════════════════════════════════════════════
# R28 — the sweep: no answer in five minutes, dispatch is told
# ══════════════════════════════════════════════════════════════════════════


def _due(now: datetime) -> Any:
    return work_models.WorkFieldAlert.objects.filter(
        tenant_id=_tenant_id(),
        ack_required=True,
        acknowledged_at__isnull=True,
        escalated_at__isnull=True,
        ack_due_at__lte=now,
    )


def escalate_unacknowledged(*, now: datetime | None = None) -> dict[str, Any]:
    """Tell dispatch about every emergency of the tenant in context whose five
    minutes ran out unanswered. Each fires ONCE: the conditional UPDATE on
    `escalated_at IS NULL AND acknowledged_at IS NULL`, inside a savepoint, is
    the guarantee — two sweeps racing, or an acknowledgement landing in the same
    instant, cannot both win (law 14: a savepoint per fire, so one failure does
    not poison the rest on PostgreSQL)."""
    moment = now or timezone.now()
    fired: list[dict[str, Any]] = []
    for alert in (
        _due(moment).select_related("work_order", "technician__user").order_by("ack_due_at", "id").iterator()
    ):
        try:
            with transaction.atomic():
                took = work_models.WorkFieldAlert.objects.filter(
                    pk=alert.pk, escalated_at__isnull=True, acknowledged_at__isnull=True
                ).update(escalated_at=moment)
                if not took:
                    continue
                core_audit.write_row(
                    action=ACTION_UNACKNOWLEDGED,
                    entity_type="work_field_alert",
                    entity_id=alert.id,
                    after={
                        "order_no": getattr(alert.work_order, "order_no", None),
                        "sent_at": alert.sent_at.isoformat(),
                        "ack_due_at": alert.ack_due_at.isoformat() if alert.ack_due_at else None,
                    },
                )
        except Exception:  # noqa: BLE001 — one alert's failure must not stop the others
            logger.exception("emergency %s could not be escalated this sweep", alert.id)
            continue
        told = notifications_seam.queue_work_office_notice(
            kind=OFFICE_NOTICE_KIND,
            order_id=alert.work_order_id or alert.id,
            order_no=getattr(alert.work_order, "order_no", None) or "",
            acted_user_id=alert.sent_by_id,
            discriminator=str(alert.id),
            occurred_at=moment,
            # The bell names who did not answer — a name, never an id (B14 rule 31).
            technician=mobile._technician_name(alert.technician) or "",
        )
        code = (told or {}).get("code") if isinstance(told, dict) else None
        work_models.WorkFieldAlert.objects.filter(pk=alert.pk).update(dispatch_told=code or "unwired")
        fired.append({"id": str(alert.id), "dispatch_told": code or "unwired"})
    return {"count": len(fired), "fired": fired}


# ── The job, its queue and the beat entry (`escalations.py`'s shape) ────────


def run_alerts_sweep_job(record: dict[str, Any]) -> dict[str, Any]:
    payload = dict(record.get("payload") or {})
    tenant_id = record.get("tenant_id") or payload.get("tenant_id")
    with core_tenancy.tenant_context(tenant_id):
        return escalate_unacknowledged()


def scope_key(tenant_id: Any, when: datetime | None = None) -> str:
    """One sweep per tenant per MINUTE (`core.jobs` folds a duplicate firing)."""
    moment = when or timezone.now()
    return f"{tenant_id}:{ALERTS_SWEEP_JOB}:{moment.strftime('%Y-%m-%dT%H:%M')}"


def beat_schedule(*, every_seconds: int | None = None) -> dict[str, dict[str, Any]]:
    return {
        BEAT_ENTRY: {
            "task": SWEEP_TASK,
            "schedule": float(every_seconds if every_seconds is not None else SWEEP_EVERY_SECONDS),
            "args": (),
            "options": {"expires": None},
        }
    }


def sweep_all_tenants(*, now: datetime | None = None) -> dict[str, Any]:
    """ONE firing: for every live utility WITH AN EMERGENCY DUE, enqueue its
    sweep. A utility with nothing due costs one indexed `EXISTS` and no job row
    (`ix_work_field_alerts_due`)."""
    from importlib import import_module

    moment = now or timezone.now()
    try:
        listed = import_module("apps.tenancy.selectors").live_tenant_subdomains()
    except Exception:  # noqa: BLE001 — a broken read must not stop the beat
        logger.exception("the live-utility read failed; no emergency sweep this minute")
        return {"tenants": 0, "queued": []}
    queued: list[str] = []
    for slug in listed or ():
        tenant_id = core_tenancy.tenant_id_for_slug(str(slug))
        if tenant_id is None:
            continue
        with core_tenancy.tenant_context(tenant_id):
            if not _due(moment).exists():
                continue
            record = core_jobs.enqueue(
                ALERTS_SWEEP_JOB,
                scope_key=scope_key(tenant_id, moment),
                payload={"tenant_id": str(tenant_id)},
            )
        queued.append(str(record["id"]))
    return {"tenants": len(queued), "queued": queued}


_SWEEP_ALL_TASK: Any = None


def install(app: Any = None) -> dict[str, Any]:
    """Register the beat entry and the fan-out task. Idempotent; never raises
    (a deployment without celery starts — `escalations.install`'s reasoning)."""
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
    core_jobs.set_job_handler(ALERTS_SWEEP_JOB, run_alerts_sweep_job)
    core_jobs.set_job_queue(ALERTS_SWEEP_JOB, WORK_QUEUE)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-187-BRC10 · 07-endpoints.md N25 · 10-execution-plan.md T-41
# generated: 2026-10-21 by lane S-FIND
# checklist: A✔ B✔ C✔ D✔ E=n/a(no screen — FF-42/FF-43 are the native app's) F✔ G✔ H✔(work/0039 + work/0040 RLS — 🔒, HUMAN-REVIEW-PENDING)
# gates: G78 · G109 (the `work` queue) · pytest tests/test_cr187_find_* on SQLite and PostgreSQL 16
# exceptions: none — the office message is notifications' `emergency_unacknowledged` kind since DEF-WRK-10350
# status: AI-AUTHORED
# ──────────────────────────────────────────────────────────
