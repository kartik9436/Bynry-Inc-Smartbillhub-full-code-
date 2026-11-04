# ── Trace ──────────────────────────────────────────────
# Change:   FB-033 — availability from the phone reaches the office (decision
#           log 2026-10-31, *"FB-033: availability from the phone reaches the
#           office (PO, D1–D4)"*) · DEF-FLD-10799
# Rules:    D1–D4 of that entry · BR-WRK-069 (End shift, unchanged) · hard
#           rules 1, 6 (idempotent on the handset's key), 7 (audited)
# Tests:    06-backend/tests/test_fb033_availability.py ·
#           06-backend/tests/test_fb033_availability_pg.py
# Impacts:  apps/work/shifts_api.py (`work/mobile/availability`, the route) ·
#           apps/work/availability_models.py · apps/work/advice.py (reads the
#           status) · apps/work/workforce.py (Crews and the technician page)
# ───────────────────────────────────────────────────────
"""What the technician says on the phone — *Available · On break · Off duty* —
reaching the office.

    POST /work/mobile/availability {key, at, value}   one tap, from the outbox
    GET  /work/mobile/availability                     the status as the office holds it

WHAT A TAP DOES (`record`)
────────────────────────────────────────────────────────────────────────────
`value` is `available` · `on_break` · `off_duty`; they set `technicians.status`
to `on_shift` · `on_break` · `off_duty` and `status_since` to the TAP's moment
(`at`, moved onto the server's clock — FB-014). Every tap that reaches the
server is one `technician_availability_changes` row and one `audit_log` row;
a resend under the same key answers the first and writes nothing.

A tap does NOT move the status, and its row says why, when:

1. **The office has the technician *Unavailable*** (`office_unavailable`).
   The office's word beats anything the phone sends (decision log FB-033).
   Only the office sets them back (`workforce.set_unavailable`).
2. **A newer change is already held** (`newer_change`): the tap's moment is
   EARLIER than `status_since`. A late offline tap counts from when it was
   pressed, and never overwrites what the office (or a later tap) said after
   it. Worked: *On break* pressed at 10:42 with no signal; at 11:00 the office
   sets the status; the tap arrives at 11:20 → recorded, status untouched.
3. **The shift was ended today and the tap is not *Available***
   (`shift_ended`): End shift already says *off*, and `off_today` is the more
   specific fact (D4 = B: Off duty and End shift are separate records). An
   *Available* after End shift IS applied — the technician has come back.

D1–D3 ARE THE ADVICE'S, NOT THIS FILE'S: assigning to an Off-duty technician
warns and is allowed (`advice.py`), On break is a warning only, and jobs
already held stay where they are — nothing here moves a job.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.work import models as work_models
from apps.work.availability_models import (
    NOT_APPLIED_NEWER_CHANGE,
    NOT_APPLIED_OFFICE_UNAVAILABLE,
    NOT_APPLIED_SHIFT_ENDED,
    VALUE_AVAILABLE,
    VALUE_OFF_DUTY,
    VALUE_ON_BREAK,
    VALUES,
    TechnicianAvailabilityChange,
)
from apps.work.seams import tenancy_seam
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy

BR_REF = "FB-033"
ACTION = "work.technician.availability_changed"
#: A tap stamped this far ahead of the server is refused (End shift's bound).
FUTURE_TOLERANCE = timedelta(minutes=5)

T = work_models.Technician
STATUS_OF = {
    VALUE_AVAILABLE: T.STATUS_ON_SHIFT,
    VALUE_ON_BREAK: T.STATUS_ON_BREAK,
    VALUE_OFF_DUTY: T.STATUS_OFF_DUTY,
}


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def _tz() -> Any:
    return tenancy_seam.tenant_timezone()


def _local(moment: datetime | None) -> str | None:
    """A moment as the UTILITY's wall clock with its offset — the screens read
    the time of day off it (*since 15:30*) with no zone arithmetic of their own."""
    return moment.astimezone(_tz()).isoformat() if moment is not None else None


def _technician(actor: Any) -> Any:
    from apps.work import mobile

    technician = mobile.technician_of(actor)
    if technician is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return technician


def _key(payload: dict[str, Any]) -> str:
    key = str((payload or {}).get("key") or "").strip()
    if not key:
        raise errors.ValidationError(errors.VAL_REQUIRED, br_ref=BR_REF, message_key="work.sync.item_key_required")
    return key


def _value(payload: dict[str, Any]) -> str:
    value = str((payload or {}).get("value") or "").strip()
    if value not in VALUES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP, br_ref=BR_REF, message_key="work.technician_status_unknown",
            params={"status": value},
        )
    return value


def _moment(raw: Any, now: datetime) -> datetime:
    """The tap's moment on the server's clock. Absent → now. A time still
    ahead of the server after the correction is REFUSED: a tap cannot have
    happened in the future, and storing one would make every later change
    look older than it (rule 2 of the module header)."""
    if raw in (None, ""):
        return now
    try:
        at = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        raise errors.ValidationError(errors.VAL_FORMAT, br_ref=BR_REF, message_key="work.shifts.date_invalid") from None
    if at.tzinfo is None:
        at = at.replace(tzinfo=_tz())
    from core import device_clock

    at = device_clock.correct(at)
    if at > now + FUTURE_TOLERANCE:
        raise errors.ValidationError(errors.VAL_RANGE, br_ref=BR_REF, message_key="work.availability.future_time")
    return at


def _answer(row: TechnicianAvailabilityChange, tech: Any, duplicate: bool) -> dict[str, Any]:
    return {
        "value": row.value,
        "at": _local(row.at),
        "applied": row.applied,
        "not_applied_reason": row.not_applied_reason or None,
        "status": tech.status,
        "status_since": _local(tech.status_since),
        "duplicate": duplicate,
    }


def _ended_today(tech: Any, at: datetime) -> bool:
    from apps.work.shift_models import TechnicianShiftEnd

    return TechnicianShiftEnd.objects.filter(
        tenant_id=_tenant_id(), technician_id=tech.id, day=at.astimezone(_tz()).date()
    ).exists()


def _decide(tech: Any, value: str, at: datetime) -> str:
    """'' when the tap moves the status, else why it does not (module header)."""
    if tech.status == T.STATUS_UNAVAILABLE:
        return NOT_APPLIED_OFFICE_UNAVAILABLE
    if tech.status_since is not None and at < tech.status_since:
        return NOT_APPLIED_NEWER_CHANGE
    if tech.status == T.STATUS_OFF_TODAY and value != VALUE_AVAILABLE and _ended_today(tech, at):
        return NOT_APPLIED_SHIFT_ENDED
    return ""


def record(actor: Any, payload: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """`POST /work/mobile/availability {key, at, value}` — one tap."""
    tech = _technician(actor)
    now = now or timezone.now()
    key = _key(payload)
    value = _value(payload)
    at = _moment((payload or {}).get("at"), now)
    same = TechnicianAvailabilityChange.objects.filter(tenant_id=_tenant_id(), key=key).first()
    if same is not None:
        return _answer(same, T.objects.get(tenant_id=_tenant_id(), pk=same.technician_id), True)
    try:
        # A SAVEPOINT, not tidiness (hard-won law 14): two sends of one key at
        # once — the loser's INSERT fails, and on PostgreSQL that would poison
        # the request's transaction without it.
        with transaction.atomic():
            locked = T.objects.select_for_update().get(tenant_id=_tenant_id(), pk=tech.id)
            reason = _decide(locked, value, at)
            before = {"status": locked.status, "status_since": _local(locked.status_since)}
            row = TechnicianAvailabilityChange.objects.create(
                tenant_id=_tenant_id(),
                technician_id=locked.id,
                value=value,
                at=at,
                key=key,
                previous_status=locked.status or "",
                applied=reason == "",
                not_applied_reason=reason,
                changed_by_id=_actor_id(actor),
            )
            if reason == "" and (locked.status != STATUS_OF[value] or locked.status_since is None):
                locked.status = STATUS_OF[value]
                locked.status_since = at
                locked.save(update_fields=["status", "status_since", "updated_at"])
    except IntegrityError:
        again = TechnicianAvailabilityChange.objects.filter(tenant_id=_tenant_id(), key=key).first()
        if again is None:
            raise
        return _answer(again, T.objects.get(tenant_id=_tenant_id(), pk=again.technician_id), True)
    core_audit.write_row(
        action=ACTION,
        entity_type="technician",
        entity_id=locked.id,
        actor_user_id=_actor_id(actor),
        before=before,
        after={
            "value": value,
            "at": at.isoformat(),
            "applied": row.applied,
            "not_applied_reason": reason or None,
            "status": locked.status,
            "status_since": _local(locked.status_since),
            "key": key,
            "br_ref": BR_REF,
        },
    )
    return _answer(row, locked, False)


def current(actor: Any) -> dict[str, Any]:
    """`GET /work/mobile/availability` — the status the office holds, read back
    by the phone after each sync (an office *Unavailable* then shows there)."""
    tech = _technician(actor)
    return {"status": tech.status, "status_since": _local(tech.status_since)}


__all__ = ["record", "current", "ACTION"]
