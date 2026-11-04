# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 4, lane SRV-3 — P3.46 (a technician's figures:
#           today, this month, the by-job-type table) and the read behind
#           P3.45 (a technician's Jobs tab). Images 31, 32, 34.
# Rules:    PO rulings 27/28 (24 Sep: *"view the orders that crew had worked
#           on"*, *"view the crew performance"*) · PO answer (1) 2026-10-04 (an
#           undated job is measured against the DEFAULT target) · NFR-3 (every
#           list pages in SQL) · NFR-5 (no maximum) · BR-WRK-053 (Performance's
#           arithmetic) · CLAUDE.md hard rule 1 (tenant-scoped reads)
# Tests:    06-backend/tests/test_cr168_srv3_crews.py
# ───────────────────────────────────────────────────────
"""One technician's work, counted — the figures `UNSERVED_UNTIL_WAVE_G` held.

⚠ **"THEIR JOBS" HAS TWO READINGS AND EACH SCREEN TAKES ONE ON PURPOSE.**

* The **Jobs tab** (image 32) lists every job the person HOLDS now **or was
  ever given** (an assignment row names them) — P3.45: *"plus the jobs the
  assignment history says they had, so a job moved away stays on the list"*.
  A dispatcher looking for the job D. Ortiz started and R. Patel finished must
  find it on both people.
* The **figures** (images 31 and 34) count only jobs the person HOLDS — the
  current holder is who closed it (ruling 18: only the job's technician closes
  it). Counting a reassigned job for both people would credit one closure twice.

**On time** is the Performance page's own test (PO answer (1), judgment J7): a
job carrying a `due_at` is measured against it; one carrying none is measured
from its raise against the DEFAULT target's hours; held time is added back
(P5.2). The arithmetic is `dispatch._sla_of`'s, called rather than restated.
"""

from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db.models import Count, Q

from apps.work import models as work_models
from apps.work.seams import metering_seam, tenancy_seam
from core import errors
from core import tenancy as core_tenancy
from core.pagination import clamp_page_size

#: Image 32's three segments. `all` is the default.
JOB_STATES = ("all", "open", "done")


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _pct(part: int, whole: int) -> str | None:
    """One decimal, or None when nothing was measured — a technician with no
    closed job this month has no first-visit rate, and *0.0%* would read as a
    rate of zero rather than as an absence."""
    if not whole:
        return None
    return f"{(Decimal(part) * 100 / Decimal(whole)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}"


def _month_bounds(today: date) -> tuple[datetime, datetime]:
    """The utility's calendar month as two instants."""
    zone = tenancy_seam.tenant_timezone()
    start = datetime.combine(today.replace(day=1), time.min).replace(tzinfo=zone)
    following = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
    return start, datetime.combine(following, time.min).replace(tzinfo=zone)


def _local_today() -> date:
    zone = tenancy_seam.tenant_timezone()
    return datetime.now(tz=zone).date()


def _default_hours() -> Any:
    from apps.work import workforce

    target = workforce.default_target()
    return target["hours"] if target else None


def _on_time(order: Any, default_hours: Any) -> bool | None:
    """True / False against the job's target, None when it has none at all."""
    from apps.work import dispatch

    sla = dispatch._sla_of(order, default_hours)
    if not sla["due_at"] or order.completed_at is None:
        return None
    return order.completed_at <= datetime.fromisoformat(sla["due_at"])


def _est_minutes(order: Any) -> int | None:
    if order.est_duration is None:
        return None
    return int(order.est_duration.total_seconds() // 60)


def tally(orders: Any, *, default_hours: Any, followed: set[Any]) -> dict[str, Any]:
    """`{closed, on_time, on_time_of, first_visit_pct, vs_estimate_pct,
    vs_estimate_minutes}` over a queryset of FINISHED jobs.

    `vs_estimate_pct` is (time on site − estimate) ÷ estimate over the jobs
    that carry both, so *−4%* means a little quicker than planned; the minutes
    figure is the same comparison as an average per job (image 31's *Avg vs
    estimate −4 min*). Both are None until a job carries both numbers — P3.47
    is what gives a job its estimate.

    Iterates the finished jobs once through `.iterator()`; nothing is returned
    unpaged and no list of rows is built.
    """
    closed = on_time = measured = first_visit = 0
    est_total = site_total = paired = 0
    for order in orders.iterator():
        closed += 1
        verdict = _on_time(order, default_hours)
        if verdict is not None:
            measured += 1
            on_time += 1 if verdict else 0
        if order.id not in followed:
            first_visit += 1
        est = _est_minutes(order)
        if est and order.minutes_on_site is not None:
            paired += 1
            est_total += est
            site_total += int(order.minutes_on_site)
    vs_pct = None
    vs_minutes = None
    if paired:
        vs_pct = f"{(Decimal(site_total - est_total) * 100 / Decimal(est_total)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)}"
        vs_minutes = int(
            (Decimal(site_total - est_total) / Decimal(paired)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
    return {
        "closed": closed,
        "on_time": on_time,
        "on_time_of": measured,
        "first_visit_pct": _pct(first_visit, closed),
        "vs_estimate_pct": vs_pct,
        "vs_estimate_minutes": vs_minutes,
    }


def _held_finished(technician_id: Any) -> Any:
    return metering_seam.completed_work_orders_queryset().filter(
        assignee_technician_id=technician_id
    )


def figures(technician_id: Any, *, today: date | None = None) -> dict[str, Any]:
    """`today {jobs}` and `this_month {…}` for image 31's header.

    *Today* is the open jobs the person holds whose window (else due time)
    falls on the utility's today — the advice list's own `jobs_that_day`, so
    the number beside a name on the assign dialog and the one on this page are
    one figure.
    """
    from apps.work import advice

    on = today or _local_today()
    jobs_today = (
        metering_seam.open_work_orders_queryset()
        .filter(assignee_technician_id=technician_id)
        .filter(advice._jobs_that_day_q(on))
        .count()
    )
    start, end = _month_bounds(on)
    month = _held_finished(technician_id).filter(completed_at__gte=start, completed_at__lt=end)
    return {
        "today": {"jobs": jobs_today, "on": on.isoformat()},
        "this_month": {
            "month": on.strftime("%Y-%m"),
            **tally(month, default_hours=_default_hours(), followed=metering_seam.followed_order_ids()),
        },
    }


def _technician_or_404(slug: str) -> Any:
    from apps.work import workforce

    row = workforce.technician_by_slug(slug)
    if row is None:
        raise errors.NotFoundError()
    return row


def jobs_page(
    slug: str,
    *,
    state: str | None = None,
    q: str | None = None,
    page: Any = 1,
    per: Any = None,
) -> dict[str, Any]:
    """`GET /work/technicians/{slug}/jobs?f.state=open|done&q=&page=&per=` —
    image 32, paged in SQL, newest raise first.

    Each row is the dispatcher's own row (`dispatch._dispatch_row`) plus
    `still_holds`: false for a job that has since moved to somebody else, so
    the tab can say so rather than leaving the reader to compare names.
    """
    from apps.work import dispatch

    person = _technician_or_404(slug)
    technician_id = person["id"]
    state = (state or "all").strip().lower()
    if state not in JOB_STATES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="work.technician.jobs_state_unknown",
            params={"state": state},
        )
    given = work_models.WorkOrderAssignment.objects.filter(
        tenant_id=_tenant_id(), technician_id=technician_id
    ).values("work_order_id")
    qs = metering_seam.every_dispatch_queryset().filter(
        Q(assignee_technician_id=technician_id) | Q(id__in=given)
    )
    finished = metering_seam.completed_work_order_state()
    if state == "done":
        qs = qs.filter(state=finished)
    elif state == "open":
        qs = qs.exclude(state=finished).exclude(dispatch_state="cancelled")
    qs = dispatch._search(qs, q)
    total = qs.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size))
    number = max(1, min(int(page or 1), last))
    start = (number - 1) * size
    default_hours = _default_hours()
    rows = []
    for order in qs.order_by("-created_at", "-id")[start : start + size]:
        row = dispatch._dispatch_row(order, default_hours)
        row["still_holds"] = str(order.assignee_technician_id or "") == str(technician_id)
        rows.append(row)
    return {"rows": rows, "page": number, "per": size, "total": total}


def performance(
    slug: str, *, period: str | None = None, page: Any = 1, per: Any = None
) -> dict[str, Any]:
    """`GET /work/technicians/{slug}/performance?period=&page=&per=` — image 34:
    the Performance arithmetic filtered to one person.

    `tiles` over the whole period; `by_job_type` GROUPED AND PAGED IN SQL
    (volume first, then the type), each page's buckets tallied by the same
    `tally` the header uses, so the tiles and the rows cannot disagree.
    `period` is `YYYY-MM` or `YYYY`, else everything (Performance's own
    grammar, `selectors._period_bounds`).
    """
    from apps.work import selectors as work_selectors

    person = _technician_or_404(slug)
    orders = _held_finished(person["id"])
    start, end = work_selectors._period_bounds(period)
    if start is not None:
        orders = orders.filter(completed_at__gte=start)
    if end is not None:
        orders = orders.filter(completed_at__lt=end)
    default_hours = _default_hours()
    followed = metering_seam.followed_order_ids()
    grouped = (
        orders.order_by()
        .values("type")
        .annotate(volume=Count("id"))
        .order_by("-volume", "type")
    )
    total = grouped.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size))
    number = max(1, min(int(page or 1), last))
    first = (number - 1) * size
    rows = []
    for bucket in grouped[first : first + size]:
        figures_of = tally(
            orders.filter(type=bucket["type"]), default_hours=default_hours, followed=followed
        )
        rows.append({"job_type": bucket["type"] or None, "volume": bucket["volume"], **figures_of})
    return {
        "period": period or "",
        "technician": {"name": person["name"], "slug": person["slug"]},
        "tiles": tally(orders, default_hours=default_hours, followed=followed),
        "rows": rows,
        "page": number,
        "per": size,
        "total": total,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-168-BRC10 §7.3 (rows GET /work/technicians/{slug}, …/jobs, …/performance) · §8 R4 SRV-3
# generated: 2026-10-04 by CR-168 round 4 lane SRV-3
# checklist: A✔ B✔ C=n/a D✔ E=n/a F✔ G✔ H=n/a
# gates: G78 (reads through metering_seam only) · pytest on SQLite and PostgreSQL 16
# exceptions: UTILISATION is not served (no image of the redesign draws it)
# status: AI-AUTHORED
# ──────────────────────────────────────────────────────────
