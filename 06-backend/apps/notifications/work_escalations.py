# ── Trace ──────────────────────────────────────────────
# Change:   CR-168-BRC10 round 5, lane SRV-4 — P3.57 (the seven escalations
#           fire), P3.58 (their messages live in Notifications, one home),
#           P3.59 (two reminders join Notifications: a certificate running
#           out, and a technician's day). Ruling 34 (24 Sep): *"add all these
#           escalations in the wireframe. if reminders can be managed in
#           notifications then remove if needed"*.
# Rules:    BR-NOT-021 (who receives a staff notification) — ⚠ NARROWED FOR
#           WORK ESCALATIONS ONLY, PO 2026-10-04, verbatim *"(a) Allow the extra
#           people, for Work escalations only."* (decision log *"A WORK RULE MAY
#           NAME EXTRA PEOPLE"*) · BR-NOT-017 (one home: every message is a
#           catalogue row with a tenant switch) · BR-NOT-020 (one message per
#           event) · BR-NOT-005 (queue only) · CLAUDE.md rule 6 (idempotent) ·
#           hard-won law 14 (the savepoint)
# Tests:    06-backend/tests/test_cr168_srv4_escalations.py
# Impacts:  rule_catalog.py (eight rows; `sla_breach` gains its writer) ·
#           field_work_events.bell_key_for (the bell's key per escalation) ·
#           apps/work/escalations.py (the caller, through
#           apps/work/seams/notifications_seam.py)
# ───────────────────────────────────────────────────────
"""A stalled job, told — and two reminders that used to be a rule's.

WHO IS TOLD, AND THE ONE PLACE `BR-NOT-021` IS NARROWED
────────────────────────────────────────────────────────────────────────────
An escalation is a FAILURE in `BR-NOT-021`'s sense — a promise the field is
about to break, or has — so it reaches **whoever acted on the job** (the person
who sent it to the field, `work_orders.assigned_by`) **and every active System
Admin**, exactly as the ruled policy says. The ONE narrowing: a rule's
escalation row may name **Also tell** people — a role or a person — who are
ADDED to that audience and never replace it (PO 2026-10-04, *"(a) Allow the
extra people, for Work escalations only."*). Worked, as put to the PO: a job
raised 08:00 and unassigned at 12:00 tells the raiser, every System Admin AND
the area supervisor. **No other staff notification may carry extra people**;
`also_tell` is a parameter of THIS function and of nothing else.

ONE MESSAGE PER JOB PER KIND
────────────────────────────────────────────────────────────────────────────
`source_id` is derived from (job, kind), so a sweep that runs every hour finds
its own message and writes nothing (rule 6); Work's own
`work_order_rule_escalation_fires` unique key is the first guarantee, this the
second. The queue row is `field_work` — FIELD-2's kind, rendered by the same
`staff_field_work` template — and the bell reads the clerk's language from
`notifications.workEscalation.<kind>`.

IT NEVER RAISES. A failed notification never fails the sweep that found the
stall; every path answers an outcome row, the write in its own SAVEPOINT.
"""

from __future__ import annotations

import uuid
from importlib import import_module
from types import SimpleNamespace
from typing import Any

from django.db import transaction

from apps.notifications import models, services, staff_recipients
from core import tenancy as core_tenancy

SOURCE_FIELD_WORK = "field_work"
TEMPLATE_CODE = "staff_field_work"

#: The seven escalation kinds (Work's `rules.ESCALATION_KINDS`) → the SET-12
#: event each is governed by. `overdue` IS the platform's long-drawn `sla_breach`
#: (it had no writer: *"There is no SLA concept anywhere in this codebase"* was
#: false from `BR-WRK-018` on, and is corrected in this commit).
EVENT_BY_KIND: dict[str, str] = {
    "unassigned": "work_job_not_assigned",
    "not_accepted": "work_job_not_accepted",
    "running_late": "work_job_running_late",
    "overdue": "sla_breach",
    "on_hold_too_long": "work_hold_overdue",
    "failed": "work_job_failed",
    "not_approved": "work_approval_overdue",
}

#: The English phrase the seeded body prints; the bell uses the catalogue key.
PHRASE_BY_KIND: dict[str, str] = {
    "unassigned": "has nobody assigned after {hours} h",
    "not_accepted": "is not accepted after {hours} h",
    "running_late": "is running late",
    "overdue": "is past its promise",
    "on_hold_too_long": "has been on hold over {hours} h",
    "failed": "failed and is still unhandled",
    "not_approved": "has waited over {hours} h for approval",
}

#: `CR-168-BRC10` P6.2 (lane SRV-5) — ruling 3's three back-office kinds:
#: *at risk, declined, blocked*. They fire on EVERY job from the act itself
#: (no Work rule row), each under its own catalogue switch. A fourth joined
#: with `DEF-WRK-10350`: R28's unacknowledged emergency.
OFFICE_EVENT_BY_KIND: dict[str, str] = {
    "at_risk": "work_job_at_risk",
    "declined": "work_job_declined",
    "blocked": "work_job_blocked",
    # `DEF-WRK-10350` — R28 (`BR-FLD-00028`, PO ruled): *"No acknowledgement in
    # 5 minutes and dispatch is told"*. Written by Work's `work.alerts_sweep`
    # (`apps/work/field_alerts.py`), once per emergency alert.
    "emergency_unacknowledged": "work_emergency_unacknowledged",
}

#: The English phrase the seeded `staff_field_work` body prints.
OFFICE_PHRASE_BY_KIND: dict[str, str] = {
    "at_risk": "is due within {hours} h and is not finished",
    "declined": "was declined by the technician",
    "blocked": "is on hold",
    "emergency_unacknowledged": "emergency was not acknowledged by {technician}",
}

#: P3.59's two reminders, which Notifications now owns.
REMINDER_CERTIFICATE = "certificate_expiring"
REMINDER_TECHNICIAN_DAY = "technician_day"
REMINDER_EVENTS = (REMINDER_CERTIFICATE, REMINDER_TECHNICIAN_DAY)

QUEUED = "escalation_queued"
ALREADY_QUEUED = "escalation_already_queued"
SUPPRESSED = "escalation_suppressed_by_rule"
NO_ADDRESSEE = "escalation_no_addressee"
REFUSED = "escalation_refused"
ERROR = "escalation_error"

BR_REF = "BR-NOT-021"

_NAMESPACE = uuid.UUID("0d7f4b4e-31c2-5a6e-8f3e-6c2a8b1f9e44")


def source_id_for(subject_id: Any, kind: str, discriminator: str = "") -> uuid.UUID:
    return uuid.uuid5(_NAMESPACE, f"{subject_id}|{kind}|{discriminator}")


def bell_key(context: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    """The bell's catalogue key for an escalation or a reminder, from the
    frozen render context (`field_work_events.bell_key_for` delegates here)."""
    code = str(context.get("event_code") or "")
    params = {"order": str(context.get("order_no") or ""), "count": int(context.get("count") or 0)}
    if context.get("technician"):
        # R28's notice names who did not answer (`DEF-WRK-10350`).
        params["technician"] = str(context.get("technician"))
    if code.startswith("escalation_"):
        kind = code[len("escalation_"):]
        if kind in EVENT_BY_KIND:
            return f"notifications.workEscalation.{kind}", params
    if code.startswith("office_"):
        kind = code[len("office_"):]
        if kind in OFFICE_EVENT_BY_KIND:
            return f"notifications.workOffice.{kind}", params
    if code == REMINDER_CERTIFICATE:
        return "notifications.workReminder.certificateExpiring", {
            "name": str(context.get("order_no") or ""),
            "count": params["count"],
        }
    if code == REMINDER_TECHNICIAN_DAY:
        return "notifications.workReminder.technicianDay", {"count": params["count"]}
    return None, params


def _user(user_id: Any) -> Any | None:
    if not user_id:
        return None
    try:
        reader = getattr(import_module("apps.identity.selectors"), "user_in_tenant", None)
    except ImportError:  # pragma: no cover - defensive
        reader = None
    user = reader(core_tenancy.current_tenant_id(), user_id) if callable(reader) else None
    return user if user is not None else SimpleNamespace(id=user_id, full_name=None, email=None)


def _also_tell(entries: Any) -> list[dict[str, Any]]:
    """`also_tell[] {kind: role|user, id}` → mailbox entries, through
    identity's published reads. A role names every active member holding it."""
    out: list[dict[str, Any]] = []
    try:
        selectors = import_module("apps.identity.selectors")
    except ImportError:  # pragma: no cover
        return out
    tenant_id = core_tenancy.current_tenant_id()
    for entry in entries or []:
        kind = (entry or {}).get("kind")
        ident = str((entry or {}).get("id") or "")
        if kind == "user" and ident:
            user = selectors.user_in_tenant(tenant_id, ident)
            if user is not None:
                out.append({"user_id": str(user.id),
                            "display_name": user.full_name or user.email,
                            "reason": "also_tell"})
        elif kind == "role" and ident:
            for membership in selectors.user_list(tenant_id, sort=None, direction="asc"):
                role = getattr(membership, "role", None)
                if getattr(role, "code", None) != ident or getattr(membership, "status", "") == "deactivated":
                    continue
                user = membership.user
                out.append({"user_id": str(user.id),
                            "display_name": user.full_name or user.email,
                            "reason": "also_tell"})
    return out


def _queue(
    *,
    event_key: str | None,
    event_code: str,
    subject_id: Any,
    discriminator: str,
    title: str,
    phrase: str,
    count: int,
    occurred_at: Any,
    actor_user_id: Any,
    failure: bool,
    extra: list[dict[str, Any]],
    work_order_id: Any = None,
    technician: str = "",
) -> dict[str, Any]:
    audience = staff_recipients.resolve_staff_recipients(
        actor=_user(actor_user_id), failure=failure
    )
    entries = audience.snapshot_entries()
    seen = {entry["user_id"] for entry in entries}
    for person in extra:
        if person["user_id"] not in seen:
            entries.append(person)
            seen.add(person["user_id"])
    if not entries:
        return {
            "code": NO_ADDRESSEE, "br_ref": BR_REF, "message_id": None,
            "note": f"nobody to tell under {staff_recipients.RULING}; nothing queued or guessed.",
        }
    primary = entries[0]
    context = {
        "order_no": title,
        "event": phrase,
        "event_code": event_code,
        "count": int(count or 0),
        "at": occurred_at,
    }
    if technician:
        context["technician"] = technician
    snapshot = {
        "user_id": primary["user_id"],
        "display_name": primary.get("display_name"),
        "recipients": entries,
        "recipient_problems": list(audience.problems),
    }
    if work_order_id is not None:
        snapshot["work_order_id"] = str(work_order_id)
    try:
        with transaction.atomic():  # the savepoint — law 14
            write = services.queue_document(
                source_type=SOURCE_FIELD_WORK,
                source_id=source_id_for(subject_id, event_code, discriminator),
                channels=(models.CHANNEL_IN_APP,),
                template=services.TemplatePin(code=TEMPLATE_CODE),
                recipients=(
                    services.Recipient(
                        channel=models.CHANNEL_IN_APP, address=primary["user_id"], snapshot=snapshot
                    ),
                ),
                render_context=context,
                actor=None,
                job="work_escalation",
                # BR-NOT-017 — the utility's own switch on Settings → Notifications.
                event_key=event_key,
            )
    except Exception as failure_exc:  # noqa: BLE001 — never fail the sweep
        return {"code": ERROR, "br_ref": BR_REF, "message_id": None,
                "note": f"could not be told: {failure_exc}"}
    message = write.messages[0] if write.messages else None
    if message is None:
        code = SUPPRESSED if write.problems else REFUSED
        return {"code": code, "br_ref": BR_REF, "message_id": None,
                "problems": [dict(p) for p in write.problems]}
    return {
        "code": QUEUED if message.created else ALREADY_QUEUED,
        "br_ref": BR_REF,
        "message_id": str(message.id),
        "mailboxes": len(entries),
    }


def queue_work_escalation(
    *,
    kind: str,
    order_id: Any,
    order_no: str,
    acted_user_id: Any,
    also_tell: Any = (),
    after_hours: int = 0,
    occurred_at: Any = None,
) -> dict[str, Any]:
    """ONE in-app message for one escalation of one job. Never raises.

    `acted_user_id` is whoever sent the job to the field (may be None — a
    rule-raised job nobody assigned); the System Admins are always told (an
    escalation is a failure); `also_tell` ADDS people, never removes the
    derived ones (`BR-NOT-021` narrowed for Work escalations, PO 2026-10-04).
    """
    event_key = EVENT_BY_KIND.get(kind)
    if event_key is None:
        return {"code": REFUSED, "br_ref": BR_REF, "message_id": None,
                "note": f"{kind!r} is not one of the seven escalations"}
    return _queue(
        event_key=event_key,
        event_code=f"escalation_{kind}",
        subject_id=order_id,
        discriminator="",
        title=order_no,
        phrase=PHRASE_BY_KIND[kind].format(hours=int(after_hours or 0)),
        count=int(after_hours or 0),
        occurred_at=occurred_at,
        actor_user_id=acted_user_id,
        failure=True,
        extra=_also_tell(also_tell),
        work_order_id=order_id,
    )


def queue_work_office_notice(
    *,
    kind: str,
    order_id: Any,
    order_no: str,
    acted_user_id: Any,
    discriminator: str = "",
    hours: int = 0,
    occurred_at: Any = None,
    technician: str = "",
) -> dict[str, Any]:
    """ONE in-app message telling the office a job is at risk, declined or
    blocked (P6.2) — or that an emergency alert went unacknowledged for five
    minutes (R28, `DEF-WRK-10350`; `technician` names who did not answer).
    Never raises.

    Each is a FAILURE in `BR-NOT-021`'s sense — the job will not happen as it
    was sent — so whoever sent it to the field AND every active System Admin
    are told; nothing is ADDED (the *Also tell* narrowing is for a rule's
    escalations only). `discriminator` separates two genuine occasions on one
    job (held, resumed, held again); a replay passes the same value and writes
    nothing (rule 6).
    """
    event_key = OFFICE_EVENT_BY_KIND.get(kind)
    if event_key is None:
        return {"code": REFUSED, "br_ref": BR_REF, "message_id": None,
                "note": f"{kind!r} is not one of the four back-office notices"}
    return _queue(
        event_key=event_key,
        event_code=f"office_{kind}",
        subject_id=order_id,
        discriminator=discriminator,
        title=order_no,
        phrase=OFFICE_PHRASE_BY_KIND[kind].format(
            hours=int(hours or 0), technician=technician or "the technician"
        ),
        count=int(hours or 0),
        occurred_at=occurred_at,
        actor_user_id=acted_user_id,
        failure=True,
        extra=[],
        work_order_id=order_id,
        technician=technician or "",
    )


def queue_work_reminder(
    *,
    reminder: str,
    subject_id: Any,
    title: str,
    count: int,
    discriminator: str,
    user_id: Any = None,
    occurred_at: Any = None,
) -> dict[str, Any]:
    """P3.59's reminders. `certificate_expiring` reaches every System Admin
    (the supervisor — a certificate running out is a failure-in-waiting);
    `technician_day` reaches the technician alone (their own day, as the
    initiator of nothing — so it is addressed to them directly). Never raises."""
    if reminder not in REMINDER_EVENTS:
        return {"code": REFUSED, "br_ref": BR_REF, "message_id": None}
    if reminder == REMINDER_CERTIFICATE:
        return _queue(
            event_key=REMINDER_CERTIFICATE, event_code=REMINDER_CERTIFICATE,
            subject_id=subject_id, discriminator=discriminator, title=title,
            phrase=f"certificate runs out in {int(count)} days", count=count,
            occurred_at=occurred_at, actor_user_id=None, failure=True, extra=[],
        )
    person = _user(user_id)
    extra = (
        [{"user_id": str(person.id), "display_name": getattr(person, "full_name", None),
          "reason": "technician"}]
        if person is not None
        else []
    )
    return _queue(
        event_key=REMINDER_TECHNICIAN_DAY, event_code=REMINDER_TECHNICIAN_DAY,
        subject_id=subject_id, discriminator=discriminator, title=title,
        phrase=f"{int(count)} job(s) today", count=count, occurred_at=occurred_at,
        actor_user_id=None, failure=False, extra=extra,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-168-BRC10 §7.3 (escalations, `also_tell`) · P3.57–P3.59 · decision log "A WORK RULE MAY NAME EXTRA PEOPLE"
# generated: 2026-10-04 by CR-168 round 5 lane SRV-4
# checklist: A✔ B✔ C✔ D=n/a(no HTTP surface — Work's sweep calls it) E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_cr168_srv4_escalations.py on SQLite and PostgreSQL 16
# status: AI-AUTHORED
# ──────────────────────────────────────────────────────────
