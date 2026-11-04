# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 5, lane SRV-4 — P5.2 (a held job's clock is
#           paused), P5.3's read (the at-risk list), P5.6 (Performance paged in
#           SQL), P5.9 (the SLA figure counts undated jobs against the default
#           target), P5.10 (a job type's own hours). Image 65.
# Rules:    BR-WRK-018 (a priority carries SLA hours; `due_at` is stamped at the
#           raise) · BR-WRK-053 (Performance's arithmetic) · PO answer (1) of
#           2026-10-04 (*"(b), so every job has a promise to measure against"* —
#           judgment J7) · NFR-3 (every list pages in SQL) · NFR-5 (no maximum)
# Tests:    06-backend/tests/test_cr168_srv4_promise.py (run on SQLite AND on
#           PostgreSQL 16 — `config.settings.pgtest`)
# ───────────────────────────────────────────────────────
"""The PROMISE a job is measured against, as SQL.

One definition, used by Performance's tiles, its by-job-type table and the
at-risk list, so the three cannot come to disagree about what *on time* means:

    target   = the job's own `due_at` (stamped at the raise from its type's or
               its priority's hours, `BR-WRK-018`/P5.10), else its raise time
               plus the DEFAULT target's hours (PO answer (1), J7 — Normal,
               72 h, a tenant setting);
    paused   = `held_seconds` (closed holds) + `now − held_at` (an open one)
               — P5.2: *four days of rain is four days of breach* no more;
    due      = target + paused.

A finished job is ON TIME when `completed_at <= due`. A job with no target at
all (no due date, and a tenant with no default) is not counted either way:
a promise nobody made cannot have been kept or broken.

⚠ **THE ARITHMETIC IS DONE IN THE DATABASE, ON BOTH ENGINES.** `held_seconds`
is an integer; it becomes an interval as `held_seconds × 1 second`, which
PostgreSQL does natively and Django's SQLite backend does through its duration
functions. Proved on both (`test_cr168_srv4_promise.py` under each engine), because a sum
that only works on SQLite is the failure hard-won law 14 exists for.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import (
    Case,
    DateTimeField,
    DurationField,
    ExpressionWrapper,
    F,
    Q,
    Value,
    When,
)
from django.db.models.functions import Coalesce, Now


def held_expr(*, open_clock: bool) -> Any:
    """The time a job has spent ON HOLD, as an interval. With `open_clock`,
    a hold still running counts up to now (an open job's due date keeps moving
    while it is held); a finished job's clock is closed by the resume or the
    close that ended it, so only `held_seconds` counts."""
    closed = ExpressionWrapper(
        F("held_seconds") * Value(timedelta(seconds=1)), output_field=DurationField()
    )
    if not open_clock:
        return closed
    running = Case(
        When(
            held_at__isnull=False,
            then=ExpressionWrapper(Now() - F("held_at"), output_field=DurationField()),
        ),
        default=Value(timedelta(0)),
        output_field=DurationField(),
    )
    return ExpressionWrapper(closed + running, output_field=DurationField())


def target_expr(default_hours: Any) -> Any:
    """The job's own `due_at`, else its raise plus the default target's hours.
    NULL when there is neither."""
    if default_hours:
        return Coalesce(
            F("due_at"),
            ExpressionWrapper(
                F("created_at") + Value(timedelta(hours=int(default_hours))),
                output_field=DateTimeField(),
            ),
            output_field=DateTimeField(),
        )
    return ExpressionWrapper(F("due_at"), output_field=DateTimeField())


def due_expr(default_hours: Any, *, open_clock: bool) -> Any:
    """`target + paused` — the moment the job is late."""
    return ExpressionWrapper(
        target_expr(default_hours) + held_expr(open_clock=open_clock),
        output_field=DateTimeField(),
    )


def target_kind_expr() -> Any:
    """`priority` when the job carries its own date, else `default`."""
    from django.db.models import CharField

    return Case(
        When(due_at__isnull=False, then=Value("priority")),
        default=Value("default"),
        output_field=CharField(),
    )


def on_time_q() -> Q:
    """A FINISHED job that met its promise — for a queryset annotated with
    `promise_due` (closed clock)."""
    return Q(promise_due__isnull=False, completed_at__lte=F("promise_due"))


def default_hours() -> Any:
    """The default target's hours for the tenant in context, or None."""
    from apps.work import workforce

    target = workforce.default_target()
    return target["hours"] if target else None


def hours_for_job(type_hours: Any, priority_hours: Any) -> Any:
    """P5.10 — a job type's OWN hours override its priority's; blank is the
    priority's. Used by the raise (`metering.connections._resolve_due_at`) and
    by a priority change, so both stamp the same promise."""
    return type_hours or priority_hours or None


__all__ = [
    "default_hours",
    "due_expr",
    "held_expr",
    "hours_for_job",
    "on_time_q",
    "target_expr",
    "target_kind_expr",
]


# ── P5.3's read · the at-risk list ──────────────────────────────────────────


def at_risk_window_hours() -> int | None:
    """The tenant's warning window (`work_settings.at_risk_window_hours`), or
    None — *at risk once the promise has passed*."""
    from apps.work import models as work_models
    from core import tenancy as core_tenancy

    row = work_models.WorkSettings.objects.filter(
        tenant_id=core_tenancy.current_tenant_id()
    ).first()
    hours = getattr(row, "at_risk_window_hours", None) if row is not None else None
    return int(hours) if hours else None


def at_risk_page(*, page: Any = 1, per: Any = None, now: Any = None) -> dict[str, Any]:
    """`GET /work/at-risk?page=&per=` — open jobs whose promise falls within
    the tenant's warning window, or has already passed; held time excluded
    (a held job's clock is paused, so it moves down the list rather than
    breaching). Soonest first, paged in SQL (NFR-3), uncapped (NFR-5).

    Each row is the dispatcher's own row plus `promise {due_at, target,
    overdue, minutes_left}` — the board draws a count-down, never a colour
    computed on the screen.
    """
    import math

    from django.utils import timezone

    from apps.work import dispatch
    from apps.work.seams import metering_seam
    from core.pagination import clamp_page_size

    moment = now or timezone.now()
    hours = default_hours()
    window = at_risk_window_hours()
    horizon = moment + timedelta(hours=window) if window else moment
    qs = (
        metering_seam.dispatch_queryset()
        .exclude(dispatch_state="cancelled")
        .annotate(promise_due=due_expr(hours, open_clock=True), promise_kind=target_kind_expr())
        .filter(promise_due__isnull=False, promise_due__lte=horizon)
        .order_by("promise_due", "order_no", "id")
    )
    total = qs.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size))
    try:
        number = max(1, min(int(page or 1), last))
    except (TypeError, ValueError):
        number = 1
    first = (number - 1) * size
    rows = []
    for order in qs[first : first + size]:
        due = order.promise_due
        row = dispatch._dispatch_row(order, hours)
        row["promise"] = {
            "due_at": due.isoformat(),
            "target": order.promise_kind,
            "overdue": due <= moment,
            "minutes_left": int((due - moment).total_seconds() // 60),
        }
        rows.append(row)
    return {
        "rows": rows,
        "page": number,
        "per": size,
        "total": total,
        "window_hours": window,
    }


# ── P5.10 · a job type's own hours ──────────────────────────────────────────


def set_job_type_sla(actor: Any, type_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`PATCH /work/job-types/{id} {sla_hours}` — a type's own promise, in whole
    hours, overriding its priority's; blank is *the priority's* (P5.10).
    Applies to jobs raised AFTER the change: a promise is stamped at the raise
    and is never re-dated by a settings edit (`BR-WRK-018`, `US-WRK-008` TC-4).
    Audited (hard rule 7)."""
    from django.db import transaction

    from apps.work import models as work_models
    from core import audit as core_audit
    from core import errors
    from core import tenancy as core_tenancy

    row = work_models.WorkOrderType.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), pk=type_id
    ).first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    raw = (payload or {}).get("sla_hours")
    if raw in (None, ""):
        hours = None
    else:
        try:
            hours = int(str(raw))
        except (TypeError, ValueError):
            raise errors.ValidationError(
                errors.VAL_FORMAT, message_key="work.priorities.sla_not_hours"
            ) from None
        if hours < 1:
            # Never 0: a promise of zero hours makes every job late the moment
            # it is raised (`work_order_types.sla_hours`' own note).
            raise errors.ValidationError(errors.VAL_RANGE, message_key="work.priorities.sla_negative")
    before = row.sla_hours
    with transaction.atomic():
        row.sla_hours = hours
        row.save(update_fields=["sla_hours", "updated_at"])
        core_audit.write_row(
            action="work.job_type.sla_set",
            entity_type="work_order_type",
            entity_id=row.id,
            actor_user_id=getattr(actor, "id", None),
            before={"sla_hours": before},
            after={"sla_hours": hours, "code": row.code},
        )
    return {"id": str(row.id), "code": row.code, "name": row.name, "sla_hours": row.sla_hours}
