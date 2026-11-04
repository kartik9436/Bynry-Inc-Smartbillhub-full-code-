# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 3, lane SRV-2 — the raise: P2.5 (assign at the
#           raise), P2.9 (the five fields write existing columns), P2.12 (raise
#           many in one press), P2.16 (the assets on the ticked units), P2.21
#           (an asset is offered its own service's templates)
# Rules:    ruling 19 (raise in bulk on units, one job per unit) · ruling 20
#           (an asset type chosen means the asset must be chosen) · ruling 22
#           (the assets list has a search) · ruling 24 (no Area on the raise) ·
#           ruling 25 (assign at the raise, or leave blank) · OQ-WRK-1497
#           CLOSED (separate jobs, no batch number) · BR-WRK-027 (a result PER
#           job) · CLAUDE.md hard rule 6 (idempotency) · hard-won law 14 (one
#           savepoint per job, proved on PostgreSQL) · NFR-3/NFR-5
# Tests:    06-backend/tests/test_cr168_srv2_raise.py ·
#           tests/test_cr168_srv2_bulk_raise_pg.py (PostgreSQL)
# Impacts:  apps/work/api.py (`POST /work-orders`, `POST /work-orders/bulk-raise`,
#           `GET /work/candidates`, `GET /work/raise/assets`) ·
#           apps/work/services.py (`raise_work_order` delegates here)
# ───────────────────────────────────────────────────────
"""The raise — one job, or one job per unit (or per asset), assigned or not.

THREE DECISIONS WORTH READING BEFORE CHANGING ANYTHING HERE
-----------------------------------------------------------
**1 · A JOB ASSIGNED AT ITS RAISE IS TWO WRITES IN ONE TRANSACTION.** The order
row is metering's (`create_work_order`, called by name through the seam) and the
assignment row is Work's (`dispatch.record_act`). They commit together or not at
all: an order that exists with a half-written assignment would read *Nobody
yet* on the list while a technician's phone was being told about it. The PUSH
waits for the commit (`DEF-WRK-4041`'s rule) — `record_act(push=False)` hands
back what to push, and this module pushes after the outermost commit.

**2 · ONE SAVEPOINT PER JOB (hard-won law 14).** Ticking six units where one is
refused must raise the other five. On PostgreSQL a failed statement aborts the
whole transaction, so `try/except IntegrityError: continue` inside one
`atomic()` loses every job at COMMIT — and the default suite runs on SQLite,
which has no aborted-transaction state, so the broken version passes it.
`tests/test_cr168_srv2_bulk_raise_pg.py` proves the savepoint on PostgreSQL with
a refusal that comes FROM THE DATABASE (a `NotFoundError` is a SELECT that
found nothing, and cannot fail the transaction at all).

**3 · A REPEATED PRESS RETURNS THE FIRST ANSWER.** The key is the screen's,
minted once per press; the row that remembers the answer is CLAIMED before the
first job is raised, inside the same transaction, so a second press racing the
first blocks on the unique index until the first commits and then reads its
answer. 🔒 HUMAN-REVIEW-PENDING (idempotency keys are a sensitive path).
"""

from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta
from typing import Any

from django.db import IntegrityError, transaction

from apps.work import advice, dispatch
from apps.work import models as work_models
from apps.work.seams import assets_seam, metering_seam, tenancy_seam
from core import errors
from core import tenancy as core_tenancy
from core.pagination import DEFAULT_PAGE_SIZE, clamp_page_size

#: What a raise may carry beside the anchors — passed to metering's
#: `create_work_order` untouched. The schedule and the assignee are taken off
#: first: they are ACTS (Work's history rows), never columns metering writes.
RAISE_ACT_FIELDS = ("assignee", "window_start", "window_end", "due_on")


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None)


def _due_at_of(due_on: Any) -> datetime | None:
    """Image 16's *Due date* is a calendar DAY (ruling 23, a date picker). It
    is stored as the END of that day in the utility's own zone — *due 27 Sep*
    means the job is late from 28 Sep 00:00 there, not from a UTC midnight
    (`DEF-CUS-6363`'s shape). Judgment, decision log *"CR-168 ROUND 3 ·
    SRV-2"* (5)."""
    if due_on in (None, ""):
        return None
    try:
        day = due_on if isinstance(due_on, date) else date.fromisoformat(str(due_on)[:10])
    except ValueError as exc:
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="work.moment_format", params={"field": "due_on"}
        ) from exc
    zone = tenancy_seam.tenant_timezone()
    return datetime.combine(day, time.min).replace(tzinfo=zone) + timedelta(days=1, seconds=-1)


def _assignee(raw: Any) -> dict[str, Any] | None:
    """`{technician_id}` or `{crew_id}` (a crew and a contractor are both
    crews), or None for *Nobody yet — assign later* (ruling 25)."""
    if not raw:
        return None
    if not isinstance(raw, dict):
        raise errors.ValidationError(
            errors.VAL_FORMAT, message_key="work.field_required", params={"field": "assignee"}
        )
    if raw.get("technician_id"):
        return {"technician_id": str(raw["technician_id"])}
    if raw.get("crew_id"):
        return {"crew_id": str(raw["crew_id"])}
    return None


def raise_one(actor: Any, payload: Any, *, pending: list[Any]) -> dict[str, Any]:
    """One job, and — when asked — who goes and when. Runs INSIDE the caller's
    transaction; appends any push it owes to `pending` (decision 1 above)."""
    data = dict(payload or {})
    assignee = _assignee(data.pop("assignee", None))
    window_start = data.pop("window_start", None)
    window_end = data.pop("window_end", None)
    due_on = data.pop("due_on", None)
    if due_on not in (None, "") and not data.get("due_at"):
        data["due_at"] = _due_at_of(due_on).isoformat()
    # Ruling 24 — the job takes its building's area; the raise never asks.
    data.pop("area_id", None)
    created = metering_seam.raise_work_order(actor, data)
    assignment = None
    if assignee is not None:
        assignment = dispatch.record_act(
            actor,
            created["id"],
            {"act": "assign", **assignee, "window_start": window_start, "window_end": window_end},
            push=False,
            pending=pending,
        )
    elif window_start or window_end:
        # A visit promised to nobody yet — the `schedule` act, holder-less.
        assignment = dispatch.record_act(
            actor,
            created["id"],
            {"act": "schedule", "window_start": window_start, "window_end": window_end},
            push=False,
            pending=pending,
        )
    if assignment is not None:
        created = {
            **created,
            "dispatch_state": assignment["dispatch_state"],
            "technician": assignment["technician"],
            "against_advice": assignment.get("against_advice"),
        }
    return created


def _push_all(pending: list[Any], actor: Any) -> None:
    for row, order, act, technician in pending:
        dispatch.push_after_assign(row, order, act, technician, actor)


def _tell_logged(order_ids: list[Any], actor: Any) -> None:
    """`DEF-WRK-10652` (PO 2026-10-29, ruling 1A) — AFTER the raise commits,
    each job raised without a visit window tells its customer *Work order
    logged*. The same posture as the push: outside the transaction, through
    `visit_notices` (which never raises), so a message can never undo a job.
    A job with no customer is answered `visit_message_no_customer` and
    nothing is written; the technician is told by the push alone (ruling 2A)."""
    from apps.work import visit_notices

    for order_id in order_ids:
        order = metering_seam.work_order_row(order_id)
        if order is not None:
            visit_notices.after_raise(order, actor=actor)


def raise_work_order(actor: Any, payload: Any) -> dict[str, Any]:
    """`POST /work-orders` — ONE job, the one raise every door uses, now with
    an optional `assignee` and visit window (P2.5, ruling 25)."""
    pending: list[Any] = []
    with transaction.atomic():
        created = raise_one(actor, payload, pending=pending)
    _push_all(pending, actor)
    _tell_logged([created["id"]], actor)
    return created


# ══════════════════════════════════════════════════════════════════════════
# BULK — ruling 19: one job per unit (or per asset, ruling 20)
# ══════════════════════════════════════════════════════════════════════════


def _refusal_key(exc: Exception) -> str:
    return getattr(exc, "message_key", None) or "work.dispatch.refused"


def bulk_raise(actor: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work-orders/bulk-raise` — one job per ticked unit, or per ticked
    asset when an asset type was chosen. `{results[], done, failed, replayed}`;
    each result `{unit_id, unit {label}, asset_id, asset {asset_no}, ok, id,
    order_no, reason}` (image 18: *6 jobs raised*, one row each)."""
    body = dict(payload or {})
    key = str(body.pop("idempotency_key", None) or "").strip()
    if not key:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="work.raise.key_required", br_ref="BR-WRK-027"
        )
    unit_ids = [str(u) for u in (body.pop("unit_ids", None) or []) if u]
    asset_ids = [str(a) for a in (body.pop("asset_ids", None) or []) if a]
    if not unit_ids and not asset_ids:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="work.raise.selection_empty", br_ref="BR-WRK-027"
        )
    if body.get("asset_type_id") and not asset_ids:
        # Ruling 20 — every unit must say which asset; the selection is assets.
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="work.order.asset_required", br_ref="BR-WRK-006"
        )
    for bad in ("unit_id", "asset_id"):
        body.pop(bad, None)

    tenant_id = _tenant_id()
    first = work_models.WorkBulkRaise.objects.filter(
        tenant_id=tenant_id, idempotency_key=key
    ).first()
    if first is not None:
        return {**first.answer, "replayed": True}

    targets: list[dict[str, Any]]
    if asset_ids:
        targets = [{"asset_id": a} for a in asset_ids]
    else:
        targets = [{"unit_id": u} for u in unit_ids]
    labels = metering_seam.unit_labels(unit_ids) if unit_ids else {}

    pending: list[Any] = []
    with transaction.atomic():
        # ── CLAIM THE KEY FIRST (decision 3). In its own savepoint: a racing
        # press loses here, and on PostgreSQL its failed INSERT must not poison
        # the transaction it then reads the winner's answer in.
        try:
            with transaction.atomic():
                claim = work_models.WorkBulkRaise.objects.create(
                    tenant_id=tenant_id, idempotency_key=key, actor_id=_actor_id(actor), answer={}
                )
        except IntegrityError:
            claim = None
        if claim is None:
            winner = work_models.WorkBulkRaise.objects.filter(
                tenant_id=tenant_id, idempotency_key=key
            ).first()
            return {**(winner.answer if winner is not None else {}), "replayed": True}

        results: list[dict[str, Any]] = []
        for target in targets:
            row: dict[str, Any] = {
                "unit_id": target.get("unit_id"),
                "unit": (
                    {"label": labels.get(target["unit_id"])} if target.get("unit_id") else None
                ),
                "asset_id": target.get("asset_id"),
                "asset": None,
            }
            # ⚠ THE SAVEPOINT (hard-won law 14). See the module docstring.
            try:
                with transaction.atomic():
                    created = raise_one(actor, {**body, **target}, pending=pending)
            except (errors.ValidationError, errors.BizError) as exc:
                results.append({**row, "ok": False, "id": None, "order_no": None,
                                "reason": _refusal_key(exc)})
                continue
            except errors.NotFoundError:
                results.append({**row, "ok": False, "id": None, "order_no": None,
                                "reason": "work.dispatch.not_found"})
                continue
            except IntegrityError:
                # The database refused this one job. The savepoint rolled it
                # back; without it every later job would raise on PostgreSQL.
                results.append({**row, "ok": False, "id": None, "order_no": None,
                                "reason": "work.dispatch.refused"})
                continue
            results.append(
                {
                    **row,
                    "ok": True,
                    "id": created["id"],
                    "order_no": created["order_no"],
                    "reason": None,
                }
            )
        _name_assets(results)
        answer = {
            "results": results,
            "done": sum(1 for r in results if r["ok"]),
            "failed": sum(1 for r in results if not r["ok"]),
        }
        claim.answer = answer
        claim.save(update_fields=["answer"])
    _push_all(pending, actor)
    _tell_logged([r["id"] for r in results if r["ok"]], actor)
    return {**answer, "replayed": False}


def _name_assets(results: list[dict[str, Any]]) -> None:
    """Fill `asset {asset_no}` and, for an asset row, its unit's label — names
    on the answer, never ids (B14 rule 31)."""
    for row in results:
        if row.get("asset_id"):
            found = assets_seam.asset(row["asset_id"])
            row["asset"] = {"asset_no": found["asset_no"]} if found else None


# ══════════════════════════════════════════════════════════════════════════
# READS the raise's steps need
# ══════════════════════════════════════════════════════════════════════════


def raise_candidates(
    *,
    template_id: Any = None,
    premises_id: Any = None,
    unit_ids: list[str] | None = None,
    on: Any = None,
    q: str | None = None,
    page: Any = 1,
    per: Any = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """`GET /work/candidates` — the advice BEFORE the job exists (P2.5): the
    template names the skill, the premises names the area (ruling 24, walked),
    `on` is the visit day (the utility's calendar; today when blank)."""
    skill_id = None
    if template_id:
        found = metering_seam.template(template_id)
        if found is None:
            raise errors.NotFoundError()
        skill_id = (found.get("skill") or {}).get("id")
    if premises_id is None and unit_ids:
        premises_id = metering_seam.premises_id_of_unit(unit_ids[0])
    area_id = metering_seam.premises_area_id(premises_id) if premises_id else None
    day = None
    if on:
        try:
            day = date.fromisoformat(str(on)[:10])
        except ValueError as exc:
            raise errors.ValidationError(
                errors.VAL_FORMAT, message_key="work.moment_format", params={"field": "on"}
            ) from exc
    return advice.candidates_page(
        skill_id=skill_id, area_id=area_id, on=day, q=q, page=page, per=per
    )


def raise_assets(
    *,
    unit_ids: list[str],
    asset_type_id: Any = None,
    service: str | None = None,
    q: str | None = None,
    page: Any = 1,
    per: Any = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """`GET /work/raise/assets` — the assets standing on the ticked units
    (image 15, ruling 22), paged in SQL. Each row says where it is by NAME and
    whether its unit holds another asset of the same filter (`shares_unit`,
    image 15's *Choose one*)."""
    from django.db.models import Count

    points = metering_seam.service_points_of_units(unit_ids, service) if unit_ids else {}
    qs = assets_seam.assets_on_points_queryset(
        list(points), asset_type_id=asset_type_id, q=(q or "").strip() or None
    )
    total = qs.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size))
    try:
        number = max(1, min(int(page or 1), last))
    except (TypeError, ValueError):
        number = 1
    start = (number - 1) * size
    page_rows = [assets_seam.asset_raise_row(row) for row in qs[start : start + size]]
    # *Choose one* — two assets of this filter on one UNIT, counted over the
    # whole filtered set (not the page), grouped by service point and folded
    # to units here (several points may stand on one unit).
    per_point = dict(
        qs.order_by().values("service_point_id").annotate(n=Count("id")).values_list(
            "service_point_id", "n"
        )
    )
    per_unit: dict[str, int] = {}
    for point_id, n in per_point.items():
        unit = (points.get(str(point_id)) or {}).get("unit")
        if unit is not None:
            per_unit[unit["id"]] = per_unit.get(unit["id"], 0) + n
    reads = metering_seam.last_reads([row["id"] for row in page_rows])
    rows = []
    for row in page_rows:
        where = points.get(row.pop("service_point_id") or "") or {}
        row["last_read"] = reads.get(row["id"])
        unit = where.get("unit")
        rows.append(
            {
                **row,
                "service": where.get("service"),
                "unit": None if unit is None else {"id": unit["id"], "label": unit["label"]},
                "premises": where.get("premises"),
                "shares_unit": unit is not None and per_unit.get(unit["id"], 0) > 1,
            }
        )
    return {"rows": rows, "page": number, "per": size, "total": total}


def templates_for_asset(asset_id: Any, *, page: Any = 1, per: Any = DEFAULT_PAGE_SIZE) -> dict[str, Any]:
    """`GET /assets/{id}/work-order-templates` — P2.21: the templates for this
    asset's TYPE (a template naming no type applies to every one) AND its
    SERVICE (a water meter is never offered an electric template), active and
    published, paged in SQL. Replaces `asset_door.templates_for_asset`'s
    unpaged Python loop with two seam calls per template."""
    from django.db.models import Exists, OuterRef, Q

    found = assets_seam.meter(asset_id)
    if found is None:
        return {"asset": None, "rows": [], "page": 1, "per": clamp_page_size(per), "total": 0}
    asset_type_id = assets_seam.asset_type_id(asset_id)
    anchor = (
        metering_seam.service_point_anchor(found["service_point_id"])
        if found.get("service_point_id")
        else None
    )
    service_code = (anchor or {}).get("service_code")

    tenant_id = _tenant_id()
    named = work_models.WorkOrderTemplateAssetType.objects.filter(
        tenant_id=tenant_id, template_id=OuterRef("pk")
    )
    qs = metering_seam.templates_queryset().filter(active=True, version__gte=1)
    qs = qs.annotate(restricted=Exists(named))
    type_ok = Q(restricted=False)
    if asset_type_id:
        type_ok |= Exists(named.filter(asset_type_id=asset_type_id))
    qs = qs.filter(type_ok)
    if service_code:
        qs = qs.filter(service__code=service_code)
    qs = qs.order_by("name", "id")
    total = qs.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size))
    try:
        number = max(1, min(int(page or 1), last))
    except (TypeError, ValueError):
        number = 1
    start = (number - 1) * size
    rows = [
        {
            "id": str(t.id),
            "name": t.name,
            "scope": t.scope,
            "restricted": bool(t.restricted),
            "service": {"code": t.service.code, "name": t.service.name} if t.service_id else None,
        }
        for t in qs[start : start + size]
    ]
    return {
        "asset": {
            "id": found["id"],
            "asset_no": found["asset_no"],
            "asset_type_id": str(asset_type_id) if asset_type_id else None,
            "service_code": service_code,
        },
        "rows": rows,
        "page": number,
        "per": size,
        "total": total,
    }


__all__ = [
    "bulk_raise",
    "raise_assets",
    "raise_candidates",
    "raise_one",
    "raise_work_order",
    "templates_for_asset",
]
