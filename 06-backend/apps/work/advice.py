# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 3, lane SRV-2 — P2.5 (assign at the raise),
#           P4.5 (the match ADVISES, never blocks), P4.6 (an override is
#           audited), NFR-5 (no cap on who may be offered a job)
# Rules:    ruling 2 (2026-09-23, "a guideline, never a block") — SUPERSEDES
#           BR-WRK-029 · PO answer 2 (2026-10-04, "(a) Warn only, the same as
#           skills") — SUPERSEDES BR-WRK-030 · ruling 25 (assign at raise or
#           leave blank) · NFR-3 (server paging) · NFR-5 (no hard caps) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 7 (audit)
# Tests:    06-backend/tests/test_cr168_srv2_assign.py ·
#           tests/test_cr168_round1_held_defects.py (DEF-WRK-9531, 9533)
# Impacts:  apps/work/dispatch.py (assign_candidates, the write's advice) ·
#           apps/work/api.py (`GET /work/candidates`,
#           `GET /work-orders/{id}/candidates`) · 07-frontend workEndpoints.ts
# ───────────────────────────────────────────────────────
"""Who could take a job, and what a dispatcher should know about each of them.

WHAT CHANGED, AND WHY THIS IS A NEW FILE RATHER THAN AN EDIT
------------------------------------------------------------
Until `CR-168-BRC10` round 3 the assign picker was `workforce.skill_match`: it
returned ONLY the people holding the template's skill, and `dispatch` refused a
write naming anybody else (`work.dispatch.skill_mismatch`, `BR-WRK-029`). The PO
ruled the opposite on 2026-09-23 (ruling 2, *"a guideline, never a block"*) and
again for certifications on 2026-10-04 (*"(a) Warn only, the same as skills"*).
So the question is no longer *who MAY take this* but *what should the
dispatcher know about everybody who could* — a different function with a
different shape, and every holder is a row.

**EVERY TECHNICIAN, CREW AND CONTRACTOR IS OFFERED, PAGED IN SQL, WITH NO
MAXIMUM** (NFR-5, `DEF-WRK-9531`). The old no-skill path read ONE page of 200
from `workforce.crews_page` and called it the whole list; the 201st holder was
silently never offered. Here technicians and crews are a SQL `UNION`, ordered
and sliced in the database, and the advice that cannot be expressed as a column
(certifications lapsed, the area the person is already working in that day) is
computed for the PAGE's rows only, in batched reads — never a Python walk of
the workforce.

THE ADVICE, FIELD BY FIELD (image 16's grey line beside each name)
-----------------------------------------------------------------
  * ``skill`` / ``has_skill`` — the template's skill and whether this holder
    has it. A template naming no skill: ``skill`` is null and every holder
    ``has_skill`` (nothing is asked of them).
  * ``area_match`` — the holder is ALREADY working in this job's area that day
    (another open job whose premises carries the same area). ⚠ **Judgment
    (decision log *"CR-168 ROUND 3 · SRV-2"* (3)):** no technician or crew
    carries a home area — no column, no form, no drawn field (images 25–34) —
    so the only area fact the product holds about a person is where their
    other jobs are. ``False`` when the job has no area.
  * ``off_that_day`` — a technician set *Unavailable* is off every day until
    set back; *Off today* is off only when the day asked about is today. A
    crew or contractor is never off (no such fact is stored for them).
  * ``jobs_that_day`` — open jobs held that day (by their window, else their
    due time, in the UTILITY's zone).
  * ``certifications_lapsed`` — the person's certifications expired before
    the day asked about. A crew holds none (certifications are per person).
  * ``daily_job_limit`` / ``over_daily_limit`` — `CR-168-BRC10` §30 (PO
    answer (2), 2026-10-05: *"(b) Add a daily limit per technician (default
    6), editable on the technician's page."*). The person's limit and whether
    ``jobs_that_day`` exceeds it — limit 6, seven jobs, over. Null / False for
    a crew or contractor. Advice like every field here: it refuses nothing.

``best_fit`` marks AT MOST ONE row across every page: the first holder, in the
list's own order, who has the skill, is not off, holds no lapsed
certification — the order putting technicians before crews before contractors
and, within those, the fewest jobs that day first. It is advice; nothing reads
it at the write.

**NONE OF THIS IS A REFUSAL.** The one-round ``eligible`` (always ``True``)
and ``lapsed`` twins are gone (lane SRV-3, 2026-10-04): lane ASSIGN reads only
``advice`` from 2.501.1.
"""

from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta
from typing import Any

from django.db.models import (
    BooleanField,
    Case,
    TextField,
    Count,
    Exists,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Cast, Coalesce, Lower, NullIf
from django.utils import timezone

from apps.work import models as work_models
from apps.work.seams import metering_seam, tenancy_seam
from core import tenancy as core_tenancy
from core.pagination import DEFAULT_PAGE_SIZE, clamp_page_size

#: Technicians, then crews, then contractors — image 16's three groups.
KIND_RANK = {"person": 0, work_models.Crew.KIND_CREW: 1}
CONTRACTOR_RANK = 2


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _day_bounds(on: date) -> tuple[datetime, datetime]:
    """The utility's calendar day as two instants — a dispatcher in Texas asks
    about *26 Sep*, not about a UTC midnight."""
    zone = tenancy_seam.tenant_timezone()
    start = datetime.combine(on, time.min).replace(tzinfo=zone)
    return start, start + timedelta(days=1)


def _jobs_that_day_q(on: date) -> Q:
    start, end = _day_bounds(on)
    return Q(window_start__gte=start, window_start__lt=end) | Q(
        window_start__isnull=True, due_at__gte=start, due_at__lt=end
    )


def _area_q(area_id: Any) -> Q:
    """An order stands in an area through its premises — WALKED, never read
    off `work_orders.area_id` (P2.17). The column is kept as the first leg so a
    job raised before this round, which carried it, still counts."""
    return (
        Q(area_id=area_id)
        | Q(premises__area_id=area_id)
        | Q(connection__premises__area_id=area_id)
        | Q(unit__premises__area_id=area_id)
    )


def _jobs_subquery(holder_field: str, on: date) -> Any:
    orders = (
        metering_seam.open_work_orders_queryset()
        .filter(_jobs_that_day_q(on))
        .filter(**{holder_field: OuterRef("pk")})
        .order_by()
        .values(holder_field)
        .annotate(n=Count("id"))
        .values("n")
    )
    return Coalesce(Subquery(orders, output_field=IntegerField()), Value(0))


def _local_today() -> date:
    """TODAY IN THE UTILITY'S ZONE (FB-033, DEF-FLD-10799). This read
    `date.today()` — the SERVER's calendar — so from 19:00 in Texas (midnight
    UTC) *off today* was asked about tomorrow and a technician who had ended
    their shift read as free."""
    return timezone.now().astimezone(tenancy_seam.tenant_timezone()).date()


def _technicians(skill_id: Any, on: date, q: str | None) -> Any:
    tenant_id = _tenant_id()
    today = _local_today()
    off = Q(status=work_models.Technician.STATUS_UNAVAILABLE)
    if on == today:
        # FB-033 — the phone's *Off duty* is off for the day it was said on.
        off |= Q(status__in=(work_models.Technician.STATUS_OFF_TODAY, work_models.Technician.STATUS_OFF_DUTY))
    has_skill: Any = Value(True, output_field=BooleanField())
    if skill_id is not None:
        has_skill = Exists(
            work_models.TechnicianSkill.objects.filter(
                tenant_id=tenant_id, technician_id=OuterRef("pk"), skill_id=skill_id
            )
        )
    lapsed = Exists(
        work_models.TechnicianCertification.objects.filter(
            tenant_id=tenant_id, technician_id=OuterRef("pk"), expires_on__lt=on
        )
    )
    qs = work_models.Technician.objects.filter(tenant_id=tenant_id)
    if q:
        qs = qs.filter(
            Q(user__full_name__icontains=q)
            | Q(user__email__icontains=q)
            | Exists(
                work_models.TechnicianSkill.objects.filter(
                    tenant_id=tenant_id, technician_id=OuterRef("pk"), skill__name__icontains=q
                )
            )
        )
    name = Coalesce(
        NullIf("user__full_name", Value("", output_field=TextField())),
        "user__email",
        output_field=TextField(),
    )
    return qs.annotate(
        kind_rank=Value(0, output_field=IntegerField()),
        holder_kind=Value("person", output_field=TextField()),
        holder_name=name,
        sort_name=Lower(name),
        has_skill=has_skill,
        is_off=Case(When(off, then=Value(True)), default=Value(False), output_field=BooleanField()),
        any_lapsed=lapsed,
        jobs=_jobs_subquery("assignee_technician_id", on),
        job_limit=Cast("daily_job_limit", output_field=IntegerField()),
    ).values(
        "kind_rank", "holder_kind", "id", "holder_name", "sort_name", "has_skill", "is_off",
        "any_lapsed", "jobs", "job_limit",
    )


#: FB-033 — the technician's own word from the phone, shown whatever day is
#: asked about (D1: *Off duty at 16:10, WO-4830 for tomorrow → red "Off
#: duty"*). Advice only: nothing refuses the assignment (ruling 2).
PHONE_STATUSES = (work_models.Technician.STATUS_OFF_DUTY, work_models.Technician.STATUS_ON_BREAK)


def _availability_by_technician(ids: list[Any]) -> dict[str, dict[str, Any]]:
    if not ids:
        return {}
    zone = tenancy_seam.tenant_timezone()
    out: dict[str, dict[str, Any]] = {}
    for tech_id, status, since in work_models.Technician.objects.filter(
        tenant_id=_tenant_id(), id__in=ids, status__in=PHONE_STATUSES
    ).values_list("id", "status", "status_since"):
        out[str(tech_id)] = {
            "status": status,
            "since": since.astimezone(zone).isoformat() if since is not None else None,
        }
    return out


def _crews(skill_id: Any, on: date, q: str | None) -> Any:
    tenant_id = _tenant_id()
    qs = work_models.Crew.objects.filter(tenant_id=tenant_id, active=True)
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Exists(
                work_models.CrewSkill.objects.filter(
                    tenant_id=tenant_id, crew_id=OuterRef("pk"), skill__name__icontains=q
                )
            )
        )
    has_skill: Any = Value(True, output_field=BooleanField())
    if skill_id is not None:
        has_skill = Exists(
            work_models.CrewSkill.objects.filter(
                tenant_id=tenant_id, crew_id=OuterRef("pk"), skill_id=skill_id
            )
        )
    return qs.annotate(
        kind_rank=Case(
            When(kind=work_models.Crew.KIND_CREW, then=Value(1)),
            default=Value(CONTRACTOR_RANK),
            output_field=IntegerField(),
        ),
        holder_kind=Cast("kind", output_field=TextField()),
        holder_name=Cast("name", output_field=TextField()),
        sort_name=Lower("name"),
        has_skill=has_skill,
        is_off=Value(False, output_field=BooleanField()),
        any_lapsed=Value(False, output_field=BooleanField()),
        jobs=_jobs_subquery("assignee_crew_id", on),
        # A crew or contractor carries no daily limit (§30 is per technician).
        job_limit=Value(None, output_field=IntegerField()),
    ).values(
        "kind_rank", "holder_kind", "id", "holder_name", "sort_name", "has_skill", "is_off",
        "any_lapsed", "jobs", "job_limit",
    )


#: The list's one order. `has_skill` and the two "not" columns DESCENDING/
#: ascending so the best candidates of each group come first.
ORDERING = ("kind_rank", "-has_skill", "is_off", "any_lapsed", "jobs", "sort_name", "id")


def _union(skill_id: Any, on: date, q: str | None) -> Any:
    return _technicians(skill_id, on, q).union(_crews(skill_id, on, q), all=True)


def _best_fit_key(skill_id: Any, on: date) -> tuple[str, str] | None:
    """The ONE best fit across every page, ignoring the search box — so the
    flag does not move from row to row as a dispatcher types."""
    techs = _technicians(skill_id, on, None).filter(
        has_skill=True, is_off=False, any_lapsed=False
    )
    crews = _crews(skill_id, on, None).filter(has_skill=True)
    first = list(techs.union(crews, all=True).order_by(*ORDERING)[:1])
    if not first:
        return None
    return (first[0]["holder_kind"], str(first[0]["id"]))


def _lapsed_by_technician(ids: list[Any], on: date) -> dict[str, list[dict[str, Any]]]:
    if not ids:
        return {}
    names = {row["id"]: row["name"] for row in tenancy_seam.certification_types()}
    out: dict[str, list[dict[str, Any]]] = {}
    for cert in work_models.TechnicianCertification.objects.filter(
        tenant_id=_tenant_id(), technician_id__in=ids, expires_on__lt=on
    ).order_by("expires_on"):
        out.setdefault(str(cert.technician_id), []).append(
            {
                "name": names.get(str(cert.certification_type_id)),
                "expired_on": cert.expires_on.isoformat(),
            }
        )
    return out


def _areas_worked(tech_ids: list[Any], crew_ids: list[Any], on: date, area_id: Any) -> set[str]:
    """Which of the page's holders already hold an open job in this area that day."""
    if area_id is None or not (tech_ids or crew_ids):
        return set()
    rows = (
        metering_seam.open_work_orders_queryset()
        .filter(_jobs_that_day_q(on))
        .filter(_area_q(area_id))
        .filter(Q(assignee_technician_id__in=tech_ids) | Q(assignee_crew_id__in=crew_ids))
        .values_list("assignee_technician_id", "assignee_crew_id")
    )
    worked: set[str] = set()
    for tech, crew in rows:
        worked.add(str(tech or crew))
    return worked


def _members(crew_ids: list[Any]) -> dict[str, int]:
    if not crew_ids:
        return {}
    return {
        str(row["crew_id"]): row["n"]
        for row in work_models.Technician.objects.filter(tenant_id=_tenant_id(), crew_id__in=crew_ids)
        .values("crew_id")
        .annotate(n=Count("id"))
    }


def skill_of(skill_id: Any) -> dict[str, Any] | None:
    if skill_id is None:
        return None
    row = work_models.WorkSkill.objects.filter(tenant_id=_tenant_id(), pk=skill_id).first()
    return {"id": str(row.id), "name": row.name} if row is not None else None


def candidates_page(
    *,
    skill_id: Any = None,
    area_id: Any = None,
    on: date | None = None,
    q: str | None = None,
    page: Any = 1,
    per: Any = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """Every technician, crew and contractor, best first, PAGED IN SQL and
    UNCAPPED — `{rows, page, per, total, skill, on}` for `api._envelope`."""
    on = on or _local_today()
    q = (q or "").strip() or None
    union = _union(skill_id, on, q)
    total = union.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size))
    try:
        number = max(1, min(int(page or 1), last))
    except (TypeError, ValueError):
        number = 1
    start = (number - 1) * size
    keys = list(union.order_by(*ORDERING)[start : start + size])

    tech_ids = [k["id"] for k in keys if k["holder_kind"] == "person"]
    crew_ids = [k["id"] for k in keys if k["holder_kind"] != "person"]
    lapsed = _lapsed_by_technician(tech_ids, on)
    availability = _availability_by_technician(tech_ids)
    worked = _areas_worked(tech_ids, crew_ids, on, area_id)
    members = _members(crew_ids)
    best = _best_fit_key(skill_id, on)
    skill = skill_of(skill_id)

    rows = []
    for key in keys:
        holder_id = str(key["id"])
        row_lapsed = lapsed.get(holder_id, []) if key["holder_kind"] == "person" else []
        advice = {
            "skill": {"name": skill["name"]} if skill else None,
            "has_skill": bool(key["has_skill"]),
            "area_match": holder_id in worked,
            "off_that_day": bool(key["is_off"]),
            "jobs_that_day": int(key["jobs"] or 0),
            # CR-168-BRC10 §30 — the technician's daily job limit (PO answer
            # (2), 2026-10-05, default 6) and whether that day's jobs exceed
            # it. ADVICE: nothing refuses the job (ruling 2). Null for a crew.
            "daily_job_limit": key["job_limit"],
            "over_daily_limit": key["job_limit"] is not None
            and int(key["jobs"] or 0) > int(key["job_limit"]),
            "certifications_lapsed": row_lapsed,
            # FB-033 D1/D2 — `{status: off_duty|on_break, since}` or null.
            "availability": availability.get(holder_id) if key["holder_kind"] == "person" else None,
        }
        row = {
            "kind": key["holder_kind"],
            "id": holder_id,
            "name": key["holder_name"],
            "advice": advice,
            "best_fit": best is not None and best == (key["holder_kind"], holder_id),
            # The one-round `lapsed` and `eligible: true` twins are RETIRED
            # (lane SRV-3, 2026-10-04) — lane ASSIGN read only `advice` from
            # 2.501.1 (`2c0a86b22`).
        }
        if key["holder_kind"] != "person":
            row["members"] = members.get(holder_id, 0)
        rows.append(row)
    return {
        "rows": rows,
        "page": number,
        "per": size,
        "total": total,
        "skill": skill,
        "on": on.isoformat(),
    }


def advice_for(*, technician: Any = None, crew: Any = None, skill_id: Any, on: date) -> dict[str, Any]:
    """The same advice for ONE holder — what the write checks before it records
    an override (P4.6). Never a refusal."""
    if technician is not None:
        has = skill_id is None or work_models.TechnicianSkill.objects.filter(
            tenant_id=_tenant_id(), technician_id=technician.id, skill_id=skill_id
        ).exists()
        lapsed = _lapsed_by_technician([technician.id], on).get(str(technician.id), [])
    else:
        has = skill_id is None or work_models.CrewSkill.objects.filter(
            tenant_id=_tenant_id(), crew_id=crew.id, skill_id=skill_id
        ).exists()
        lapsed = []
    skill = skill_of(skill_id)
    return {
        "skill": {"name": skill["name"]} if skill else None,
        "has_skill": bool(has),
        "certifications_lapsed": lapsed,
        "availability": _availability_by_technician([technician.id]).get(str(technician.id))
        if technician is not None
        else None,
    }


def order_day(order: Any) -> date:
    """The day a job's advice is asked about: its window, else its due time, in
    the utility's zone; else today."""
    moment = order.window_start or order.due_at
    if moment is None:
        return _local_today()
    return moment.astimezone(tenancy_seam.tenant_timezone()).date()


def order_area_id(order: Any) -> Any:
    """The job's area, walked from its premises (P2.17)."""
    if order.area_id:
        return order.area_id
    for premises in (
        getattr(order, "premises", None),
        getattr(getattr(order, "connection", None), "premises", None),
        getattr(getattr(order, "unit", None), "premises", None),
    ):
        if premises is not None and premises.area_id:
            return premises.area_id
    return None


__all__ = ["candidates_page", "advice_for", "order_day", "order_area_id", "skill_of"]
