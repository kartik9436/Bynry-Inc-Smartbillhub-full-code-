# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 Phase 13 task T-38, lane S-ORDER — a second
#           technician on an order, with their own labour record (FF-29,
#           E2E-20: *"Dana adds Marco to a job at 11:20; he records 90
#           minutes; she closes it"*).
# Rules:    BR-FLD-00008 (R8 — labour is per person, not per job; two
#           technicians are two time records and the cost is their sum; the
#           lead closes it) · BR-FLD-00009 (R9 — travel and labour are separate
#           clocks, depart · arrive · start; both correctable by the
#           technician) · BR-FLD-00010 (R10 — every change stamped who and
#           when) · BR-WRK-020 (the rate is fixed AT CLOSE) · BR-WRK-051 (one
#           named cost function) · hard rules 1, 2, 7
# Tests:    06-backend/tests/test_cr187_order_labour.py
# Impacts:  apps/work/costing.py (helper lines added to the job's cost) ·
#           apps/work/services.py (`snapshot_labour_rate_at_close` stamps the
#           helpers' rates too) · apps/work/field_orders_api.py (three routes)
# ───────────────────────────────────────────────────────
"""Labour per PERSON on a job — the lead's and every helper's own clocks.

WHO IS WHO, AND WHY THE LEAD IS NOT A NEW CONCEPT
--------------------------------------------------
The LEAD is whoever the job is assigned to — `work_orders.assignee_technician`
— which is exactly the person `submit_field_result` already admits to close it
(`_refuse_unless_field`, ruling 18). So R8's *"the lead closes it"* needs no
new code: a helper is not the assignee and the close refuses them by the rule
that already exists. `test_cr187_order_labour.py` asserts that refusal by
name, so a future widening of the close door goes red here.

A HELPER is a technician the lead adds (`add_technician`). They get a row in
`work_order_labour` and may record and correct THEIR OWN four moments.

⚠ **AND THE LEAD MAY CORRECT A HELPER'S, AND STOP A HELPER'S CLOCK — NOBODY
ELSE MAY TOUCH ANOTHER PERSON'S TIME** (`CR-187-BRC10`, lane S-GAPS). This
file read *"nobody records another person's time"* until then, reading R9's
*"correctable by the technician"* as *only by that technician*. The drawing
says otherwise and the drawing is the specification (B14 rules 41, 42): FF-29
puts **Correct their time** and a **×** on the HELPER's card, seen by the
LEAD, and `US-FLD-020` TC-3 is *"Correct their time on M. Chen → corrected
and stamped who and when (R10)"*. So `record_time` takes an optional
`technician_id` — honoured only from the lead, only for a person already on
the lead's job — and `member_leaves` stops a helper's labour at the moment the
lead says (FF-29's ×: *"their clocks stop now; their time so far stays
theirs"*). A helper naming anybody but themselves is refused
`work.labour.lead_changes_others_only`. Each act is audited with BOTH names:
whose time it is and who changed it (R10).

THE COST IS THE SUM — AND THE LEAD IS NOT COUNTED TWICE
-------------------------------------------------------
The lead's line is still the order's own `minutes_on_site × labour_rate_
snapshot`, stamped at close (`BR-WRK-020`, `services.snapshot_labour_rate_at_
close`). A helper adds a SECOND line, priced from THEIR role's rate, stamped at
the same close (`snapshot_rates_at_close` below). `costing.work_order_cost_
lines` appends `helper_inputs(order)` — and reads only HELPER rows, which is
what keeps the lead from being priced twice.

Worked (E2E-20, rates illustrative per B14 rule 37): Dana on site 120 min at
`48.5000` → `2.00 h × 48.5000 = 97.00`; Marco 90 min at `40.0000` → `1.50 h ×
40.0000 = 60.00`; the job's labour is `157.00`, two lines.

⚠ **A HELPER WITH NO RATE FOR THEIR ROLE CARRIES NO LINE**, never a line at
`$0.00` — `costing.py`'s *we cannot say* rather than *free*. The read below
says `priced: false` so the office can see the gap.

THE TWO CLOCKS (R9)
-------------------
`depart_at → arrive_at` is TRAVEL; `start_at → end_at` is LABOUR. Where a
person records no `start_at`, their labour runs from `arrive_at` — the lead's
own rule since `DEF-WRK-4127` (on site = arrival to finish) — and the read says
which it used (`labour_from`). A finish not after its start or an arrival before
its departure is refused. ⚠ **A MOMENT AHEAD OF THE SERVER IS NO LONGER
REFUSED (FB-014, PO 2026-10-28).** This read *"or any moment in the FUTURE is
refused"* until then — zero tolerance against a phone's own clock, so a phone 5
minutes fast had its time refused until the server caught up. Every moment is
now shifted onto the server's clock by the offset the request measured
(`core/device_clock.py`); only a send with no clock reading and a time more
than 5 minutes ahead is still refused.

THE OUTBOX KIND `time` (`07-endpoints.md` N17)
-----------------------------------------------
`apply_time_item(actor, order_id, body)` is the applier a sync `time` item
needs, written here so the sync lane registers it in `sync._APPLIERS` rather
than re-implementing it. This lane does not edit `sync.py` (lane S-SYNC owns
the outbox kinds); the direct route `PUT work/mobile/jobs/{id}/labour` is the
same function, idempotent by nature (it SETS the four moments).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.work import mobile
from apps.work import models as work_models
from apps.work.field_order_models import (
    LABOUR_ROLE_HELPER,
    LABOUR_ROLE_LEAD,
    WorkOrderLabour,
)
from apps.work.seams import metering_seam
from core import audit as core_audit
from core import device_clock, errors
from core import tenancy as core_tenancy

#: The four moments, in the order a day runs them.
MOMENTS: tuple[str, ...] = ("depart_at", "arrive_at", "start_at", "end_at")


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def _technician_or_404(actor: Any) -> Any:
    technician = mobile.technician_of(actor)
    if technician is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return technician


def _is_lead(order: Any, technician: Any) -> bool:
    return bool(
        (order.assignee_technician_id and order.assignee_technician_id == technician.id)
        or (
            order.assignee_crew_id
            and technician.crew_id
            and order.assignee_crew_id == technician.crew_id
        )
    )


def member_order_or_404(actor: Any, order_id: Any) -> tuple[Any, Any, str]:
    """`(order, technician, role)` for a person ON this job, else a 404.

    On the job = the lead (the assignee, or a member of the crew that holds
    it) or a helper with a labour row. Anyone else — another technician of the
    same utility included — gets the not-found an absent job gets (HR-1,
    `US-WRK-041` TC-6).
    """
    technician = _technician_or_404(actor)
    order = metering_seam.work_order_row(order_id)
    if order is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    if _is_lead(order, technician):
        return order, technician, LABOUR_ROLE_LEAD
    if WorkOrderLabour.objects.filter(
        tenant_id=_tenant_id(), work_order_id=order.id, technician_id=technician.id
    ).exists():
        return order, technician, LABOUR_ROLE_HELPER
    raise errors.deny_as_not_found("BR-TEN-003")


def _refuse_if_closed(order: Any) -> None:
    """Accepted is final for labour: the report and its cost lines are frozen
    (`work/0011`), so a clock changed afterwards would disagree with a signed
    total. A job completed and NOT yet accepted still takes corrections — that
    is the window R9's *correctable* lives in."""
    if order.accepted_at is not None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-FLD-00009",
            message_key="work.labour.order_accepted",
            params={"order_no": order.order_no or ""},
        )
    if order.dispatch_state == metering_seam.dispatch_tokens().CANCELLED:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-FLD-00009",
            message_key="work.mobile.job_finished",
            params={"order_no": order.order_no or ""},
        )


def _name_of(technician: Any) -> str | None:
    user = getattr(technician, "user", None)
    return (getattr(user, "full_name", None) or None) if user is not None else None


def _ensure_lead_row(order: Any, actor: Any) -> Any:
    """The lead's own row, created on first need. Never PRICED (see header)."""
    lead = order.assignee_technician
    if lead is None:
        return None
    row, _ = WorkOrderLabour.objects.get_or_create(
        tenant_id=_tenant_id(),
        work_order_id=order.id,
        technician=lead,
        defaults={"role": LABOUR_ROLE_LEAD, "added_by_id": _actor_id(actor)},
    )
    return row


def add_technician(actor: Any, order_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work/mobile/jobs/{id}/crew` — `{technician_id, key?}`: the LEAD
    adds a second (or third) technician to their job (FF-29, E2E-20).

    Only the lead may add (a helper adding a third person would be a job
    growing a crew nobody assigned). Idempotent twice over: the same `key`
    answers the first row, and the same person added again answers their
    existing row — both with `created: false`. Another utility's technician
    is a 404, indistinguishable from none (HR-1). Audited
    `work.labour.member_added` (hard rule 7's shape; R10).
    """
    order, technician, role = member_order_or_404(actor, order_id)
    if role != LABOUR_ROLE_LEAD:
        raise errors.AuthError(
            errors.AUTH_PERMISSION_DENIED,
            br_ref="BR-FLD-00008",
            message_key="work.labour.lead_adds_only",
            params={"order_no": order.order_no or ""},
        )
    _refuse_if_closed(order)
    data = payload or {}
    key = str(data.get("key") or "").strip() or None
    if key is not None:
        existing = WorkOrderLabour.objects.filter(tenant_id=_tenant_id(), key=key).first()
        if existing is not None:
            if existing.work_order_id != order.id:
                raise errors.deny_as_not_found("BR-TEN-003")
            return {**_row(existing), "created": False}
    wanted = str(data.get("technician_id") or "").strip()
    if not wanted:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            br_ref="BR-FLD-00008",
            message_key="work.labour.technician_required",
        )
    helper = (
        work_models.Technician.objects.filter(tenant_id=_tenant_id(), pk=wanted)
        .select_related("user")
        .first()
        if _looks_like_uuid(wanted)
        else None
    )
    if helper is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    if helper.id == technician.id or _is_lead(order, helper):
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            br_ref="BR-FLD-00008",
            message_key="work.labour.already_lead",
            params={"order_no": order.order_no or ""},
        )
    already = WorkOrderLabour.objects.filter(
        tenant_id=_tenant_id(), work_order_id=order.id, technician_id=helper.id
    ).first()
    if already is not None:
        return {**_row(already), "created": False}
    try:
        # A SAVEPOINT, not decoration (hard-won law 14): a lost race on the
        # (order, technician) or key unique must not poison the caller's
        # transaction on PostgreSQL. Proved in test_cr187_order_labour_pg.py.
        with transaction.atomic():
            _ensure_lead_row(order, actor)
            row = WorkOrderLabour.objects.create(
                tenant_id=_tenant_id(),
                work_order_id=order.id,
                technician=helper,
                role=LABOUR_ROLE_HELPER,
                added_by_id=_actor_id(actor),
                key=key,
            )
            core_audit.write_row(
                action="work.labour.member_added",
                entity_type="work_order",
                entity_id=order.id,
                actor_user_id=_actor_id(actor),
                before=None,
                after={
                    "order_no": order.order_no,
                    "technician": _name_of(helper),
                    "labour_id": str(row.id),
                    "br_ref": "BR-FLD-00008",
                },
            )
    except IntegrityError:
        row = WorkOrderLabour.objects.filter(
            tenant_id=_tenant_id(), work_order_id=order.id, technician_id=helper.id
        ).first()
        if row is None and key is not None:
            row = WorkOrderLabour.objects.filter(tenant_id=_tenant_id(), key=key).first()
        if row is None:
            raise
        return {**_row(row), "created": False}
    return {**_row(row), "created": True}


def _looks_like_uuid(value: str) -> bool:
    import uuid

    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def _moment(raw: Any, field: str) -> Any:
    if raw in (None, ""):
        return None
    # FB-014 (DEF-FLD-10639): onto the server's clock first. With the phone's
    # clock reading on the request this is never in the future (a time still
    # ahead is clamped to now); the refusal below is reached only by a send
    # with NO reading and a time more than 5 minutes ahead (`core/device_clock`).
    when = device_clock.correct(metering_seam.parse_moment(raw, field=field))
    if when is not None and when > timezone.now():
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            br_ref="BR-TEN-043",
            message_key="work.labour.moment_in_future",
            params={"field": field},
        )
    return when


def record_time(actor: Any, order_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`PUT /work/mobile/jobs/{id}/labour` — the caller's OWN four moments, or
    (the LEAD only) a helper's: `{depart_at?, arrive_at?, start_at?, end_at?,
    technician_id?}`.

    Any subset of `depart_at · arrive_at · start_at · end_at` (ISO-8601). A
    moment already recorded and now DIFFERENT is a correction (R9): it counts,
    and the value it replaced is written to `audit_log`
    (`work.labour.corrected`) — R10's *who and when*. Setting the same value
    again changes nothing and writes nothing, which is what makes a replayed
    outbox `time` item harmless.

    `technician_id` naming somebody else is FF-29's *Correct their time*
    (header): honoured from the lead for a person with a row on this job (a
    404 for anybody else, HR-1); refused `work.labour.lead_changes_others_only`
    from a helper. The handset's correction is TYPED AS MINUTES and sent as
    the moments those minutes mean (`field-app/src/sync/doors.ts`), so the
    server keeps one model — four moments — and one set of checks.

    The lead's own row is created on first use. Refused after the office has
    ACCEPTED the job (the report is frozen) and for a cancelled job.
    """
    order, caller, role = member_order_or_404(actor, order_id)
    _refuse_if_closed(order)
    data = payload or {}
    technician = _whose_time(order, caller, role, data.get("technician_id"))
    if technician.id != caller.id:
        role = LABOUR_ROLE_HELPER
    sent = {field: _moment(data.get(field), field) for field in MOMENTS if field in data}
    if not sent:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            br_ref="BR-FLD-00009",
            message_key="work.labour.nothing_to_record",
            params={"fields": ", ".join(MOMENTS)},
        )
    with transaction.atomic():
        row = (
            WorkOrderLabour.objects.select_for_update()
            .filter(tenant_id=_tenant_id(), work_order_id=order.id, technician_id=technician.id)
            .first()
        )
        if row is None:
            row = WorkOrderLabour.objects.create(
                tenant_id=_tenant_id(),
                work_order_id=order.id,
                technician=technician,
                role=role,
                added_by_id=_actor_id(actor),
            )
        before = {f: _iso(getattr(row, f)) for f in MOMENTS}
        corrected = [
            f for f, v in sent.items() if getattr(row, f) is not None and getattr(row, f) != v
        ]
        changed = [f for f, v in sent.items() if getattr(row, f) != v]
        for field, value in sent.items():
            setattr(row, field, value)
        _refuse_backwards(row)
        if changed:
            if corrected:
                row.corrections = int(row.corrections or 0) + 1
            row.save(update_fields=[*changed, "corrections", "updated_at"])
            core_audit.write_row(
                action="work.labour.corrected" if corrected else "work.labour.recorded",
                entity_type="work_order",
                entity_id=order.id,
                actor_user_id=_actor_id(actor),
                before={f: before[f] for f in changed},
                after={
                    **{f: _iso(getattr(row, f)) for f in changed},
                    "order_no": order.order_no,
                    "technician": _name_of(technician),
                    "labour_id": str(row.id),
                    **(
                        {"changed_by": _name_of(caller)}
                        if technician.id != caller.id
                        else {}
                    ),
                    "br_ref": "BR-FLD-00009",
                    # FB-014 — the phone's own clock and the shift applied.
                    **device_clock.audit_fields(),
                },
            )
    return {**_row(row), "changed": changed, "corrected": corrected}


def _whose_time(order: Any, caller: Any, role: str, wanted: Any) -> Any:
    """The technician whose clocks this request changes: the caller, or — the
    LEAD only — a person already on this job (module header)."""
    wanted = str(wanted or "").strip()
    if not wanted or wanted == str(caller.id):
        return caller
    if role != LABOUR_ROLE_LEAD:
        raise errors.AuthError(
            errors.AUTH_PERMISSION_DENIED,
            br_ref="BR-FLD-00009",
            message_key="work.labour.lead_changes_others_only",
            params={"order_no": order.order_no or ""},
        )
    row = (
        WorkOrderLabour.objects.filter(
            tenant_id=_tenant_id(), work_order_id=order.id, technician_id=wanted
        )
        .select_related("technician__user")
        .first()
        if _looks_like_uuid(wanted)
        else None
    )
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row.technician


def member_leaves(actor: Any, order_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work/mobile/jobs/{id}/crew` with `{act: "leave", technician_id,
    ended_at?, key?}` — FF-29's **×** (`CR-187-BRC10`, lane S-GAPS).

    The LEAD stops a helper's labour: `end_at` is set to `ended_at` (the
    moment captured on the handset; now when absent) **only if the helper has
    no finish yet** — *"their time so far stays theirs"*, so a finish the
    helper recorded themselves is never overwritten. Nothing is deleted: the
    helper's row, their minutes and their cost line stay on the job, and the
    helper can still correct their own time (R9).

    Idempotent by nature: a resend finds the finish already set, changes
    nothing, writes nothing and answers `duplicate: true`. Refused: a helper
    asking (`work.labour.lead_changes_others_only`); the lead naming
    themselves (`work.labour.already_lead`, the same refusal `add_technician`
    gives the lead adding themselves — the lead closes the job, R8, and hands
    it back through FF-58 if they cannot); a person not on the
    job (404, HR-1); an accepted or cancelled job; a finish before the
    helper's start or arrival. Audited `work.labour.member_left` (R10).
    """
    order, caller, role = member_order_or_404(actor, order_id)
    data = payload or {}
    wanted = str(data.get("technician_id") or "").strip()
    if not wanted:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            br_ref="BR-FLD-00008",
            message_key="work.labour.technician_required",
        )
    if role != LABOUR_ROLE_LEAD:
        raise errors.AuthError(
            errors.AUTH_PERMISSION_DENIED,
            br_ref="BR-FLD-00008",
            message_key="work.labour.lead_changes_others_only",
            params={"order_no": order.order_no or ""},
        )
    if wanted == str(caller.id):
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            br_ref="BR-FLD-00008",
            message_key="work.labour.already_lead",
            params={"order_no": order.order_no or ""},
        )
    _refuse_if_closed(order)
    ended = _moment(data.get("ended_at"), "ended_at") or timezone.now()
    with transaction.atomic():
        row = (
            WorkOrderLabour.objects.select_for_update()
            .filter(
                tenant_id=_tenant_id(),
                work_order_id=order.id,
                technician_id=wanted if _looks_like_uuid(wanted) else None,
                role=LABOUR_ROLE_HELPER,
            )
            .select_related("technician__user")
            .first()
        )
        if row is None:
            raise errors.deny_as_not_found("BR-TEN-003")
        if row.end_at is not None:
            return {**_row(row), "changed": [], "duplicate": True}
        row.end_at = ended
        _refuse_backwards(row)
        row.save(update_fields=["end_at", "updated_at"])
        core_audit.write_row(
            action="work.labour.member_left",
            entity_type="work_order",
            entity_id=order.id,
            actor_user_id=_actor_id(actor),
            before={"end_at": None},
            after={
                "end_at": _iso(row.end_at),
                "order_no": order.order_no,
                "technician": _name_of(row.technician),
                "changed_by": _name_of(caller),
                "labour_id": str(row.id),
                "br_ref": "BR-FLD-00008",
            },
        )
    return {**_row(row), "changed": ["end_at"], "duplicate": False}


def crew_door(actor: Any, order_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work/mobile/jobs/{id}/crew` — `act` absent or `join` adds a
    person (`add_technician`); `leave` stops a helper's clock
    (`member_leaves`). Any other word is refused by name. One door because
    FF-29 is one screen and the handset's outbox kind is one (`crew_time`)."""
    act = str((payload or {}).get("act") or "join").strip()
    if act == "leave":
        return member_leaves(actor, order_id, payload)
    if act != "join":
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            br_ref="BR-FLD-00008",
            message_key="work.labour.crew_act_unknown",
            params={"act": act, "allowed": "join, leave"},
        )
    return add_technician(actor, order_id, payload)


def apply_time_item(actor: Any, order_id: Any, body: dict[str, Any]) -> dict[str, Any]:
    """The applier for an outbox `time` item (`07-endpoints.md` N17) — for the
    sync lane to register in `sync._APPLIERS`. The same function as the route."""
    return record_time(actor, order_id, body or {})


def _refuse_backwards(row: Any) -> None:
    """R9's two clocks must each run forwards; the database CHECKs are the
    backstop and this is the sentence."""
    if row.depart_at and row.arrive_at and row.arrive_at < row.depart_at:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            br_ref="BR-FLD-00009",
            message_key="work.labour.arrived_before_departing",
        )
    if row.start_at and row.end_at and row.end_at <= row.start_at:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            br_ref="BR-FLD-00009",
            message_key="work.labour.finished_before_starting",
        )
    if row.arrive_at and row.end_at and not row.start_at and row.end_at <= row.arrive_at:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            br_ref="BR-FLD-00009",
            message_key="work.labour.finished_before_starting",
        )


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _minutes(start: Any, end: Any) -> int | None:
    if start is None or end is None:
        return None
    seconds = (end - start).total_seconds()
    return int(round(seconds / 60)) if seconds > 0 else None


def labour_minutes(row: Any) -> tuple[int | None, str | None]:
    """`(minutes, from)` — `start_at → end_at`, or `arrive_at → end_at` when no
    start was recorded (see header). `from` names which, or None."""
    if row.start_at is not None:
        return _minutes(row.start_at, row.end_at), "start_at"
    if row.arrive_at is not None:
        return _minutes(row.arrive_at, row.end_at), "arrive_at"
    return None, None


def _row(row: Any) -> dict[str, Any]:
    minutes, labour_from = labour_minutes(row)
    technician = row.technician
    return {
        "id": str(row.id),
        "technician": {"id": str(technician.id), "name": _name_of(technician)},
        "role": row.role,
        **{f: _iso(getattr(row, f)) for f in MOMENTS},
        "travel_minutes": _minutes(row.depart_at, row.arrive_at),
        "labour_minutes": minutes,
        "labour_from": labour_from,
        "corrections": row.corrections,
        "priced": row.rate_snapshot is not None,
    }


def labour_of(actor: Any, order_id: Any) -> dict[str, Any]:
    """`GET /work/mobile/jobs/{id}/labour` — everybody's time on this job and
    what it costs, for a person ON the job. The cost is `BR-WRK-051`'s one
    function, so it is the same figure the report will freeze."""
    order, _technician, _role = member_order_or_404(actor, order_id)
    return labour_summary(order)


def labour_summary(order: Any) -> dict[str, Any]:
    from apps.work import field_outcomes

    rows = list(
        WorkOrderLabour.objects.filter(tenant_id=_tenant_id(), work_order_id=order.id)
        .select_related("technician__user")
        .order_by("role", "created_at", "id")
    )
    shaped = [_row(r) for r in rows]
    return {
        "order_id": str(order.id),
        "order_no": order.order_no,
        "people": shaped,
        "people_count": max(len(shaped), 1 if order.assignee_technician_id else 0),
        "labour_minutes": sum(r["labour_minutes"] or 0 for r in shaped),
        "travel_minutes": sum(r["travel_minutes"] or 0 for r in shaped),
        "cost": field_outcomes.cost_of(order),
    }


# ── the cost and the rate (called from costing.py and services.py) ────────


def snapshot_rates_at_close(order: Any) -> None:
    """Stamp each HELPER's rate at the close — `BR-WRK-020`'s moment.

    Called from `services.snapshot_labour_rate_at_close`, which the close
    already calls. The role is derived from the helper's typed `role_label`
    exactly as the lead's is (that function's judgment, decision log
    2026-09-05); no rate for the role → nothing stamped → no line. A rate
    already stamped stays (a re-close after a send-back keeps the first
    close's rate, the lead's rule).
    """
    rows = WorkOrderLabour.objects.filter(
        tenant_id=_tenant_id(),
        work_order_id=order.id,
        role=LABOUR_ROLE_HELPER,
        rate_snapshot__isnull=True,
    ).select_related("technician")
    for row in rows:
        label = (row.technician.role_label or "").strip().lower().replace(" ", "_")
        if not label:
            continue
        rate = work_models.LabourRate.objects.filter(
            tenant_id=_tenant_id(), role=label, superseded_on__isnull=True
        ).first()
        if rate is None:
            continue
        row.rate_snapshot = rate.hourly
        row.labour_role = label
        row.save(update_fields=["rate_snapshot", "labour_role", "updated_at"])


def helper_inputs(order: Any) -> list[Any]:
    """`costing.LabourInput` per HELPER with a stamped rate and a labour span
    — what `costing.work_order_cost_lines` adds to the lead's line. Helpers
    only: the lead is the order's own line and is never read here."""
    from apps.work import costing

    # A pure-arithmetic caller (`test_us_wrk_053_costing.py` hands
    # `work_order_cost_lines` a bare object with no id) has no rows to read.
    if getattr(order, "id", None) is None:
        return []
    out = []
    rows = (
        WorkOrderLabour.objects.filter(
            tenant_id=_tenant_id(), work_order_id=order.id, role=LABOUR_ROLE_HELPER
        )
        .select_related("technician__user")
        .order_by("created_at", "id")
    )
    for row in rows:
        minutes, _from = labour_minutes(row)
        if row.rate_snapshot is None or minutes is None:
            continue
        role_label = costing._role_label(row.labour_role or "")
        name = _name_of(row.technician)
        out.append(
            costing.LabourInput(
                minutes=minutes,
                role_label=f"{role_label} — {name}" if name else role_label,
                rate=Decimal(row.rate_snapshot),
            )
        )
    return out
