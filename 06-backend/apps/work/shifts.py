# ── Trace ──────────────────────────────────────────────
# Change:   CR-193-BRC10 — MQ-040 STEP 1 (decision log 2026-10-26, *"MQ-040:
#           shifts and timesheet, STEP 1 approved (working days, week view
#           with holidays, End shift, Timesheet submit)"*)
# Rules:    BR-WRK-068 (working days + one-day exceptions) · BR-WRK-069 (End
#           shift) · BR-WRK-070 (a submitted day is a snapshot, one per person
#           per day, not editable on the phone) · hard rules 1, 6, 7 · NFR-3
#           (every list paged in SQL) · NFR-5 (no cap)
# Tests:    06-backend/tests/test_cr193_shifts.py ·
#           06-backend/tests/test_cr193_shifts_pg.py
# Impacts:  apps/work/shifts_api.py (the routes) · apps/work/shift_models.py
# ───────────────────────────────────────────────────────
"""A technician's week, End shift and Submit the day — the services.

WHAT THE PO APPROVED, AND WHAT THEY DID NOT
────────────────────────────────────────────────────────────────────────────
Step 1 only: working days per technician with one-day exceptions (the office,
on the technician's page) · the phone's week — the shift window per day, the
utility's holidays in grey · today's shift with the time so far and *End
shift* · *Submit the day* to the office, and the office sees submitted days.
**Step 2 — time-off requests, approval, notifications — is NOT approved**, so
nothing here makes a time-off day: an exception is the OFFICE's word for a day.

HOW ONE DAY OF THE WEEK IS DECIDED (`_day`), in this order
────────────────────────────────────────────────────────────────────────────
1. An EXCEPTION for that date wins: `off` → off; `window` → that window.
2. Else a utility HOLIDAY (`tenancy.HolidayCalendar`, read through the seam) →
   `holiday` with its label. The office's exception beats the holiday because
   it is the narrower, later decision about ONE person (someone on call).
3. Else a WORKING weekday → `shift` with `technicians.shift_start/shift_end`
   (NULL for a contractor: a working day *by arrangement*, never midnight).
4. Else → `off`.
Worked (the PO's example): D. Ortiz Mon–Fri 07:00–15:30, Fri 30 Oct a utility
holiday → Mon–Thu `07:00–15:30`, Fri *Holiday*, Sat and Sun off.

THE SHIFT IN PROGRESS (`current`)
────────────────────────────────────────────────────────────────────────────
The server holds no clock-on moment, so the shift STARTS at today's window
start (the time so far is measured from it). It is in progress when today is a
`shift` day with a window, the window has started, it has not been ended
today, and the person is not set *unavailable*. ⚠ **`off_today` IS NOT TAKEN
AS FINAL**: *End shift* sets it (`end_shift`), and nothing yet sets it back the
next morning — so a status of `off_today` whose latest shift end is from an
EARLIER day is read as *a new day*, not as *off today*. A dispatcher who sets
`off_today` by hand on a day with no shift end is still obeyed.

THE MORNING RETURN (`morning_return`, DEF-WRK-10615 — PO 2026-10-26, *"yes
reset each morning"*)
────────────────────────────────────────────────────────────────────────────
An hourly sweep (`shift_morning.py`, one job per utility in its own tenant
context) returns a technician to *on shift* on the first run of the utility's
local day when ALL of these hold: their status is `off_today`; their LATEST
End shift is from an earlier day and has not been SETTLED (`settled_at`); that
End shift did not find them *unavailable*; and TODAY is a working day for them
by `_day` — a working weekday or a `window` exception, never a holiday, a
non-working weekday or an `off` exception. A day that is not a working day
leaves them off and leaves the End shift unsettled, so the next working
morning returns them (Friday's End shift → Saturday and Sunday off → Monday on
shift). The return SETTLES the End shift, so a second run is a no-op; so does
the office setting any status by hand after it (`workforce.set_unavailable`),
which is how an *off today* the office set is never overridden, and why the
phone's `_current` obeys an `off_today` whose latest End shift is settled.
One `audit_log` row per technician returned (`work.shift.morning_return`).
"""

from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Case, F, IntegerField, Q, Value, When
from django.utils import timezone

from apps.work import mobile, workforce
from apps.work import models as work_models
from apps.work.field_order_models import WorkOrderLabour
from apps.work.seams import tenancy_seam
from apps.work.shift_models import (
    DEFAULT_DAYS_MASK,
    EXCEPTION_KINDS,
    EXCEPTION_OFF,
    EXCEPTION_WINDOW,
    WEEKDAY_CODES,
    TechnicianDayException,
    TechnicianShiftEnd,
    TechnicianWorkingDays,
    TimesheetSubmission,
)
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy
from core.pagination import clamp_page_size

NOTE_MAX = 200
BR_DAYS = "BR-WRK-068"
BR_END = "BR-WRK-069"
BR_SHEET = "BR-WRK-070"


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def _tz() -> Any:
    return tenancy_seam.tenant_timezone()


def _local_today(now: datetime | None = None) -> date:
    return (now or timezone.now()).astimezone(_tz()).date()


def _hhmm(value: time | None) -> str | None:
    return value.strftime("%H:%M") if value is not None else None


def _page(qs: Any, page: Any, per: Any, shape: Any) -> dict[str, Any]:
    total = qs.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size))
    try:
        number = min(max(1, int(page or 1)), last)
    except (TypeError, ValueError):
        number = 1
    start = (number - 1) * size
    return {
        "rows": [shape(row) for row in qs[start : start + size]],
        "page": number,
        "per": size,
        "total": total,
        "pages": last,
    }


# ── the weekday set ────────────────────────────────────────────────────────


def mask_of(technician_id: Any) -> int:
    row = TechnicianWorkingDays.objects.filter(tenant_id=_tenant_id(), technician_id=technician_id).first()
    return row.days if row is not None else DEFAULT_DAYS_MASK


def codes_of(mask: int) -> list[str]:
    return [code for n, code in enumerate(WEEKDAY_CODES) if mask & (1 << n)]


def _mask_from(raw: Any) -> int:
    if not isinstance(raw, list) or any(not isinstance(c, str) for c in raw):
        raise errors.ValidationError(errors.VAL_FORMAT, br_ref=BR_DAYS, message_key="work.shifts.weekdays_invalid")
    mask = 0
    for code in raw:
        code = code.strip().lower()
        if code not in WEEKDAY_CODES:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP, br_ref=BR_DAYS, message_key="work.shifts.weekdays_invalid"
            )
        mask |= 1 << WEEKDAY_CODES.index(code)
    return mask


# ── the office: one technician, by slug ─────────────────────────────────────


def technician_by_slug_or_404(slug: str) -> Any:
    """The `technicians` row behind a page address. Another utility's slug is
    404, identical to one that does not exist (hard rule 1)."""
    found = workforce.technician_by_slug(slug)
    if found is None:
        raise errors.NotFoundError()
    return work_models.Technician.objects.get(tenant_id=_tenant_id(), pk=found["id"])


def working_days(slug: str) -> dict[str, Any]:
    """`GET /work/technicians/{slug}/working-days`."""
    tech = technician_by_slug_or_404(slug)
    row = TechnicianWorkingDays.objects.filter(tenant_id=_tenant_id(), technician_id=tech.id).first()
    mask = row.days if row is not None else DEFAULT_DAYS_MASK
    return {
        "weekdays": codes_of(mask),
        "is_default": row is None,
        "shift_start": _hhmm(tech.shift_start),
        "shift_end": _hhmm(tech.shift_end),
    }


def set_working_days(actor: Any, slug: str, payload: dict[str, Any]) -> dict[str, Any]:
    """`PUT /work/technicians/{slug}/working-days {weekdays: ["mon", …]}` —
    the whole set, replaced. Audited with what it replaced (hard rule 7)."""
    tech = technician_by_slug_or_404(slug)
    mask = _mask_from((payload or {}).get("weekdays"))
    with transaction.atomic():
        row = (
            TechnicianWorkingDays.objects.select_for_update()
            .filter(tenant_id=_tenant_id(), technician_id=tech.id)
            .first()
        )
        before = row.days if row is not None else DEFAULT_DAYS_MASK
        if row is None:
            row = TechnicianWorkingDays.objects.create(
                tenant_id=_tenant_id(), technician_id=tech.id, days=mask, updated_by_id=_actor_id(actor)
            )
        elif row.days != mask:
            row.days = mask
            row.updated_by_id = _actor_id(actor)
            row.save(update_fields=["days", "updated_by", "updated_at"])
        if before != mask:
            core_audit.write_row(
                action="work.shift.working_days_set",
                entity_type="technician",
                entity_id=tech.id,
                actor_user_id=_actor_id(actor),
                before={"weekdays": codes_of(before)},
                after={"weekdays": codes_of(mask), "br_ref": BR_DAYS},
            )
    return working_days(slug)


# ── the office: one-day exceptions ─────────────────────────────────────────


def _exception_row(row: TechnicianDayException) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "date": row.day.isoformat(),
        "kind": row.kind,
        "start": _hhmm(row.start),
        "end": _hhmm(row.end),
        "note": row.note or None,
    }


def _parse_date(raw: Any, br_ref: str) -> date:
    try:
        return date.fromisoformat(str(raw or "").strip()[:10])
    except ValueError:
        raise errors.ValidationError(errors.VAL_FORMAT, br_ref=br_ref, message_key="work.shifts.date_invalid") from None


def _parse_time(raw: Any) -> time:
    try:
        return time.fromisoformat(str(raw or "").strip())
    except ValueError:
        raise errors.ValidationError(errors.VAL_FORMAT, br_ref=BR_DAYS, message_key="work.shifts.window_invalid") from None


def _exception_fields(payload: dict[str, Any], current: TechnicianDayException | None) -> dict[str, Any]:
    data = payload or {}
    out: dict[str, Any] = {}
    if "date" in data or current is None:
        out["day"] = _parse_date(data.get("date"), BR_DAYS)
    kind = str(data.get("kind", current.kind if current else "") or "").strip()
    if kind not in EXCEPTION_KINDS:
        raise errors.ValidationError(errors.VAL_UNKNOWN_LOOKUP, br_ref=BR_DAYS, message_key="work.shifts.kind_invalid")
    out["kind"] = kind
    if kind == EXCEPTION_OFF:
        out["start"] = None
        out["end"] = None
    else:
        start = _parse_time(data.get("start", _hhmm(current.start) if current else None))
        end = _parse_time(data.get("end", _hhmm(current.end) if current else None))
        if end <= start:
            raise errors.ValidationError(errors.VAL_RANGE, br_ref=BR_DAYS, message_key="work.shifts.window_invalid")
        out["start"] = start
        out["end"] = end
    if "note" in data or current is None:
        note = str(data.get("note") or "").strip()
        if len(note) > NOTE_MAX:
            raise errors.ValidationError(
                errors.VAL_RANGE, br_ref=BR_DAYS, message_key="work.shifts.note_too_long", params={"max": NOTE_MAX}
            )
        out["note"] = note
    return out


def exceptions_page(slug: str, *, page: Any = 1, per: Any = 25) -> dict[str, Any]:
    """`GET /work/technicians/{slug}/exceptions` — upcoming days first (soonest
    first), then past days (most recent first). Paged in SQL (NFR-3)."""
    tech = technician_by_slug_or_404(slug)
    today = _local_today()
    qs = (
        TechnicianDayException.objects.filter(tenant_id=_tenant_id(), technician_id=tech.id)
        .annotate(
            past=Case(When(day__lt=today, then=Value(1)), default=Value(0), output_field=IntegerField()),
            upcoming_day=Case(When(day__gte=today, then=F("day")), default=None),
            past_day=Case(When(day__lt=today, then=F("day")), default=None),
        )
        .order_by("past", F("upcoming_day").asc(nulls_last=True), F("past_day").desc(nulls_last=True), "id")
    )
    return _page(qs, page, per, _exception_row)


def _exception_or_404(tech: Any, exception_id: Any) -> TechnicianDayException:
    row = TechnicianDayException.objects.filter(
        tenant_id=_tenant_id(), technician_id=tech.id, pk=exception_id
    ).first()
    if row is None:
        raise errors.NotFoundError()
    return row


def _refuse_taken_day(exc: IntegrityError) -> None:
    raise errors.BizError(
        errors.BIZ_STATE, br_ref=BR_DAYS, message_key="work.shifts.exception_exists"
    ) from exc


def add_exception(actor: Any, slug: str, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work/technicians/{slug}/exceptions {date, kind, start?, end?, note?}`."""
    tech = technician_by_slug_or_404(slug)
    fields = _exception_fields(payload, None)
    if TechnicianDayException.objects.filter(tenant_id=_tenant_id(), technician_id=tech.id, day=fields["day"]).exists():
        raise errors.BizError(errors.BIZ_STATE, br_ref=BR_DAYS, message_key="work.shifts.exception_exists")
    try:
        # A SAVEPOINT, not tidiness (hard-won law 14): two clerks adding the
        # same day at once — the loser's INSERT fails, and on PostgreSQL that
        # would poison the request's transaction without it.
        with transaction.atomic():
            row = TechnicianDayException.objects.create(
                tenant_id=_tenant_id(), technician_id=tech.id, created_by_id=_actor_id(actor), **fields
            )
    except IntegrityError as exc:
        _refuse_taken_day(exc)
    shaped = _exception_row(row)
    core_audit.write_row(
        action="work.shift.exception_added",
        entity_type="technician",
        entity_id=tech.id,
        actor_user_id=_actor_id(actor),
        after={**shaped, "br_ref": BR_DAYS},
    )
    return shaped


def edit_exception(actor: Any, slug: str, exception_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`PATCH /work/technicians/{slug}/exceptions/{id}`."""
    tech = technician_by_slug_or_404(slug)
    row = _exception_or_404(tech, exception_id)
    before = _exception_row(row)
    fields = _exception_fields(payload, row)
    for name, value in fields.items():
        setattr(row, name, value)
    try:
        with transaction.atomic():
            row.save()
    except IntegrityError as exc:
        _refuse_taken_day(exc)
    shaped = _exception_row(row)
    if shaped != before:
        core_audit.write_row(
            action="work.shift.exception_changed",
            entity_type="technician",
            entity_id=tech.id,
            actor_user_id=_actor_id(actor),
            before=before,
            after={**shaped, "br_ref": BR_DAYS},
        )
    return shaped


def remove_exception(actor: Any, slug: str, exception_id: Any) -> None:
    """`DELETE /work/technicians/{slug}/exceptions/{id}` — the day goes back to
    the rule. Not money and not a record anybody signed: a delete, audited."""
    tech = technician_by_slug_or_404(slug)
    row = _exception_or_404(tech, exception_id)
    before = _exception_row(row)
    row.delete()
    core_audit.write_row(
        action="work.shift.exception_removed",
        entity_type="technician",
        entity_id=tech.id,
        actor_user_id=_actor_id(actor),
        before=before,
        after={"br_ref": BR_DAYS},
    )


# ── the office: submitted days ─────────────────────────────────────────────


def _submission_row(row: TimesheetSubmission) -> dict[str, Any]:
    return {
        "date": row.day.isoformat(),
        "jobs": row.jobs,
        "labour_minutes": row.labour_minutes,
        "travel_minutes": row.travel_minutes,
        "lines": row.lines,
        "submitted_at": row.submitted_at.isoformat(),
    }


def timesheets_page(slug: str, *, page: Any = 1, per: Any = 25) -> dict[str, Any]:
    """`GET /work/technicians/{slug}/timesheets` — newest day first, paged."""
    tech = technician_by_slug_or_404(slug)
    qs = TimesheetSubmission.objects.filter(tenant_id=_tenant_id(), technician_id=tech.id).order_by("-day", "-id")
    return _page(qs, page, per, _submission_row)


# ── the phone ──────────────────────────────────────────────────────────────


def _technician_or_404(actor: Any) -> Any:
    technician = mobile.technician_of(actor)
    if technician is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return technician


def _holidays(start: date, end: date) -> dict[date, str]:
    return tenancy_seam.holidays_between(start, end)


def _day(day: date, tech: Any, mask: int, exception: Any, holiday: str | None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "date": day.isoformat(),
        "weekday": WEEKDAY_CODES[day.weekday()],
        "kind": "off",
        "start": None,
        "end": None,
        "holiday": holiday,
        "note": None,
        "exception": None,
    }
    if exception is not None:
        out["exception"] = exception.kind
        out["note"] = exception.note or None
        if exception.kind == EXCEPTION_WINDOW:
            out.update(kind="shift", start=_hhmm(exception.start), end=_hhmm(exception.end))
        return out
    if holiday is not None:
        out["kind"] = "holiday"
        return out
    if mask & (1 << day.weekday()):
        out.update(kind="shift", start=_hhmm(tech.shift_start), end=_hhmm(tech.shift_end))
    return out


def week(actor: Any, from_raw: Any = None, *, now: datetime | None = None) -> dict[str, Any]:
    """`GET /work/mobile/week?from=YYYY-MM-DD` — seven days from `from` (the
    Monday of this week when absent), and today's shift in progress."""
    tech = _technician_or_404(actor)
    now = now or timezone.now()
    today = _local_today(now)
    start = _parse_date(from_raw, BR_DAYS) if from_raw else today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    mask = mask_of(tech.id)
    exceptions = {
        row.day: row
        for row in TechnicianDayException.objects.filter(
            tenant_id=_tenant_id(), technician_id=tech.id, day__gte=min(start, today), day__lte=max(end, today)
        )
    }
    holidays = _holidays(min(start, today), max(end, today))
    days = [_day(start + timedelta(days=n), tech, mask, exceptions.get(start + timedelta(days=n)), holidays.get(start + timedelta(days=n))) for n in range(7)]
    today_row = _day(today, tech, mask, exceptions.get(today), holidays.get(today))
    ended = TechnicianShiftEnd.objects.filter(tenant_id=_tenant_id(), technician_id=tech.id, day=today).first()
    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "today": today.isoformat(),
        "days": days,
        "current": _current(tech, today_row, ended, now),
        "ended_at": ended.ended_at.astimezone(_tz()).isoformat() if ended is not None else None,
    }


def _current(tech: Any, today_row: dict[str, Any], ended: Any, now: datetime) -> dict[str, Any] | None:
    if ended is not None or today_row["kind"] != "shift" or not today_row["start"] or not today_row["end"]:
        return None
    if tech.status == work_models.Technician.STATUS_UNAVAILABLE:
        return None
    if tech.status == work_models.Technician.STATUS_OFF_TODAY:
        latest = (
            TechnicianShiftEnd.objects.filter(tenant_id=_tenant_id(), technician_id=tech.id)
            .order_by("-day")
            .first()
        )
        # Set by hand, or by an End shift TODAY, or set by the office after
        # the End shift (settled) → obeyed. Left over from an earlier day's
        # End shift → a new day (module header).
        if latest is None or latest.settled_at is not None or latest.day >= date.fromisoformat(today_row["date"]):
            return None
    tz = _tz()
    day = date.fromisoformat(today_row["date"])
    started = datetime.combine(day, time.fromisoformat(today_row["start"]), tzinfo=tz)
    if now < started:
        return None
    return {
        "start": today_row["start"],
        "end": today_row["end"],
        "started_at": started.isoformat(),
        "minutes_so_far": int((now - started).total_seconds() // 60),
    }


def _key(payload: dict[str, Any], br_ref: str) -> str:
    key = str((payload or {}).get("key") or "").strip()
    if not key:
        raise errors.ValidationError(errors.VAL_REQUIRED, br_ref=br_ref, message_key="work.sync.item_key_required")
    return key


def _moment_at(raw: Any, now: datetime) -> datetime:
    if raw in (None, ""):
        return now
    try:
        at = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        raise errors.ValidationError(errors.VAL_FORMAT, br_ref=BR_END, message_key="work.shifts.date_invalid") from None
    if at.tzinfo is None:
        at = at.replace(tzinfo=_tz())
    # FB-014 (DEF-FLD-10639) — the phone's clock, moved onto the server's; the
    # refusal below is left only for a send with no clock reading.
    from core import device_clock

    at = device_clock.correct(at)
    if at > now + timedelta(minutes=5):
        raise errors.ValidationError(errors.VAL_RANGE, br_ref=BR_END, message_key="work.shifts.future_day")
    return at


def _end_answer(row: TechnicianShiftEnd, duplicate: bool) -> dict[str, Any]:
    return {
        "date": row.day.isoformat(),
        "ended_at": row.ended_at.astimezone(_tz()).isoformat(),
        "status": work_models.Technician.STATUS_OFF_TODAY,
        "duplicate": duplicate,
    }


def end_shift(actor: Any, payload: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """`POST /work/mobile/shift/end {key, at?}` — BR-WRK-069.

    Records when the shift ended and sets the person *off today*. Idempotent on
    the key; a SECOND End shift the same day (another key) answers the first —
    a day has one end. `at` is the handset's moment of the press (it may have
    been captured without signal); absent → now."""
    tech = _technician_or_404(actor)
    now = now or timezone.now()
    key = _key(payload, BR_END)
    at = _moment_at((payload or {}).get("at"), now)
    day = at.astimezone(_tz()).date()
    same = TechnicianShiftEnd.objects.filter(tenant_id=_tenant_id(), key=key).first()
    if same is not None:
        return _end_answer(same, True)
    that_day = TechnicianShiftEnd.objects.filter(tenant_id=_tenant_id(), technician_id=tech.id, day=day).first()
    if that_day is not None:
        return _end_answer(that_day, True)
    try:
        with transaction.atomic():
            row = TechnicianShiftEnd.objects.create(
                tenant_id=_tenant_id(),
                technician_id=tech.id,
                day=day,
                ended_at=at,
                key=key,
                previous_status=tech.status or "",
                ended_by_id=_actor_id(actor),
            )
            # FB-033 — `status_since` is the press (*Shift ended · 17:02*).
            work_models.Technician.objects.filter(tenant_id=_tenant_id(), pk=tech.id).update(
                status=work_models.Technician.STATUS_OFF_TODAY, status_since=at
            )
    except IntegrityError:
        # A race with the same key or the same day (law 14: the savepoint above
        # is what keeps the request's transaction usable for this read).
        again = (
            TechnicianShiftEnd.objects.filter(tenant_id=_tenant_id())
            .filter(Q(key=key) | Q(technician_id=tech.id, day=day))
            .first()
        )
        if again is None:
            raise
        return _end_answer(again, True)
    core_audit.write_row(
        action="work.shift.ended",
        entity_type="technician",
        entity_id=tech.id,
        actor_user_id=_actor_id(actor),
        before={"status": row.previous_status},
        after={
            "status": work_models.Technician.STATUS_OFF_TODAY,
            "date": day.isoformat(),
            "ended_at": at.isoformat(),
            "key": key,
            "br_ref": BR_END,
        },
    )
    return _end_answer(row, False)


ACTION_MORNING_RETURN = "work.shift.morning_return"


def morning_return(*, now: datetime | None = None) -> dict[str, int]:
    """DEF-WRK-10615 — return this utility's technicians whom an EARLIER day's
    End shift left *off today* to *on shift*, if today is a working day for
    them (module header, *THE MORNING RETURN*). Runs in the caller's tenant
    context; idempotent (a returned End shift is settled)."""
    now = now or timezone.now()
    today = _local_today(now)
    tenant_id = _tenant_id()
    holiday = _holidays(today, today).get(today)
    open_ends = TechnicianShiftEnd.objects.filter(tenant_id=tenant_id, settled_at__isnull=True, day__lt=today)
    candidates = work_models.Technician.objects.filter(
        tenant_id=tenant_id,
        status=work_models.Technician.STATUS_OFF_TODAY,
        id__in=open_ends.values("technician_id"),
    ).order_by("id")
    returned = kept = 0
    for tech in candidates.iterator():
        latest = (
            TechnicianShiftEnd.objects.filter(tenant_id=tenant_id, technician_id=tech.id).order_by("-day").first()
        )
        if latest is None or latest.settled_at is not None or latest.day >= today:
            continue
        if latest.previous_status == work_models.Technician.STATUS_UNAVAILABLE:
            # End shift pressed while the office had them unavailable: that is
            # the office's word, and the morning does not overrule it.
            continue
        exception = TechnicianDayException.objects.filter(
            tenant_id=tenant_id, technician_id=tech.id, day=today
        ).first()
        if _day(today, tech, mask_of(tech.id), exception, holiday)["kind"] != "shift":
            kept += 1
            continue
        with transaction.atomic():
            moved = work_models.Technician.objects.filter(
                tenant_id=tenant_id, pk=tech.id, status=work_models.Technician.STATUS_OFF_TODAY
            ).update(status=work_models.Technician.STATUS_ON_SHIFT, status_since=now)
            TechnicianShiftEnd.objects.filter(pk=latest.pk, settled_at__isnull=True).update(settled_at=now)
            if moved:
                core_audit.write_row(
                    action=ACTION_MORNING_RETURN,
                    entity_type="technician",
                    entity_id=tech.id,
                    actor_user_id=None,
                    before={"status": work_models.Technician.STATUS_OFF_TODAY},
                    after={
                        "status": work_models.Technician.STATUS_ON_SHIFT,
                        "date": today.isoformat(),
                        "shift_ended_on": latest.day.isoformat(),
                        "br_ref": BR_END,
                    },
                )
                returned += 1
    returned += _morning_return_phone_statuses(today, now, holiday)
    return {"returned": returned, "kept_off": kept}


def _morning_return_phone_statuses(today: date, now: datetime, holiday: str | None) -> int:
    """FB-033 — *On break* and *Off duty* are a DAY's word, like End shift: a
    technician the phone left on one of them on an EARLIER day is returned to
    *on shift* on the first run of a working day (lane judgment, decision log
    *"FB-033 built"*). An office *Unavailable* is never touched. Audited as
    the End-shift return is."""
    tenant_id = _tenant_id()
    tz = _tz()
    phone = (work_models.Technician.STATUS_ON_BREAK, work_models.Technician.STATUS_OFF_DUTY)
    start_of_today = datetime.combine(today, time.min, tzinfo=tz)
    returned = 0
    for tech in work_models.Technician.objects.filter(
        tenant_id=tenant_id, status__in=phone, status_since__lt=start_of_today
    ).order_by("id").iterator():
        exception = TechnicianDayException.objects.filter(
            tenant_id=tenant_id, technician_id=tech.id, day=today
        ).first()
        if _day(today, tech, mask_of(tech.id), exception, holiday)["kind"] != "shift":
            continue
        with transaction.atomic():
            moved = work_models.Technician.objects.filter(
                tenant_id=tenant_id, pk=tech.id, status=tech.status, status_since=tech.status_since
            ).update(status=work_models.Technician.STATUS_ON_SHIFT, status_since=now)
            if moved:
                core_audit.write_row(
                    action=ACTION_MORNING_RETURN,
                    entity_type="technician",
                    entity_id=tech.id,
                    actor_user_id=None,
                    before={"status": tech.status},
                    after={
                        "status": work_models.Technician.STATUS_ON_SHIFT,
                        "date": today.isoformat(),
                        "br_ref": "FB-033",
                    },
                )
                returned += 1
    return returned


def settle_shift_ends(technician_id: Any, *, now: datetime | None = None) -> int:
    """The office set this technician's status by hand: any End shift still
    holding it stops holding it, so the morning return never overrides the
    office (DEF-WRK-10615)."""
    return TechnicianShiftEnd.objects.filter(
        tenant_id=_tenant_id(), technician_id=technician_id, settled_at__isnull=True
    ).update(settled_at=now or timezone.now())


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    tz = _tz()
    start = datetime.combine(day, time.min, tzinfo=tz)
    return start, start + timedelta(days=1)


def _minutes(start: Any, end: Any) -> int:
    if start is None or end is None:
        return 0
    seconds = (end - start).total_seconds()
    return int(round(seconds / 60)) if seconds > 0 else 0


def day_lines(tech: Any, day: date) -> list[dict[str, Any]]:
    """That day's labour per job and travel, from `work_order_labour` — every
    row of this person with a moment inside the day (the utility's zone),
    labour `start → end` or `arrive → end` (`field_labour.labour_minutes`'s
    rule), travel `depart → arrive`. A clock still running counts nothing:
    the office sees it as 0, never a guess."""
    from apps.work.field_labour import labour_minutes

    lo, hi = _day_bounds(day)
    within = Q()
    for field in ("depart_at", "arrive_at", "start_at", "end_at"):
        within |= Q(**{f"{field}__gte": lo, f"{field}__lt": hi})
    rows = (
        WorkOrderLabour.objects.filter(tenant_id=_tenant_id(), technician_id=tech.id)
        .filter(within)
        .select_related("work_order")
    )
    lines = []
    for row in rows:
        minutes, _from = labour_minutes(row)
        first = min(m for m in (row.depart_at, row.arrive_at, row.start_at, row.end_at) if m is not None)
        lines.append(
            (
                first,
                {
                    "order_id": str(row.work_order_id),
                    "order_no": row.work_order.order_no,
                    "labour_minutes": minutes or 0,
                    "travel_minutes": _minutes(row.depart_at, row.arrive_at),
                },
            )
        )
    lines.sort(key=lambda pair: (pair[0], pair[1]["order_id"]))
    return [line for _first, line in lines]


def submit_day(actor: Any, payload: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """`POST /work/mobile/timesheet/submit {date, key}` — BR-WRK-070.

    Snapshots that day's labour per job and travel and hands it to the office.
    One submission per person per day: the same key, or another key for a day
    already submitted, answers the FIRST with `duplicate: true` — never a
    second snapshot, because a submitted day is the office's to correct."""
    tech = _technician_or_404(actor)
    now = now or timezone.now()
    key = _key(payload, BR_SHEET)
    day = _parse_date((payload or {}).get("date"), BR_SHEET)
    if day > _local_today(now):
        raise errors.ValidationError(errors.VAL_RANGE, br_ref=BR_SHEET, message_key="work.shifts.future_day")
    same = TimesheetSubmission.objects.filter(tenant_id=_tenant_id(), key=key).first()
    if same is not None:
        return {**_submission_row(same), "duplicate": True}
    that_day = TimesheetSubmission.objects.filter(tenant_id=_tenant_id(), technician_id=tech.id, day=day).first()
    if that_day is not None:
        return {**_submission_row(that_day), "duplicate": True}
    lines = day_lines(tech, day)
    try:
        with transaction.atomic():
            row = TimesheetSubmission.objects.create(
                tenant_id=_tenant_id(),
                technician_id=tech.id,
                day=day,
                key=key,
                lines=lines,
                jobs=len({line["order_id"] for line in lines}),
                labour_minutes=sum(line["labour_minutes"] for line in lines),
                travel_minutes=sum(line["travel_minutes"] for line in lines),
                submitted_at=now,
                submitted_by_id=_actor_id(actor),
            )
    except IntegrityError:
        again = (
            TimesheetSubmission.objects.filter(tenant_id=_tenant_id())
            .filter(Q(key=key) | Q(technician_id=tech.id, day=day))
            .first()
        )
        if again is None:
            raise
        return {**_submission_row(again), "duplicate": True}
    core_audit.write_row(
        action="work.timesheet.submitted",
        entity_type="technician",
        entity_id=tech.id,
        actor_user_id=_actor_id(actor),
        after={
            "date": day.isoformat(),
            "jobs": row.jobs,
            "labour_minutes": row.labour_minutes,
            "travel_minutes": row.travel_minutes,
            "key": key,
            "br_ref": BR_SHEET,
        },
    )
    return {**_submission_row(row), "duplicate": False}
