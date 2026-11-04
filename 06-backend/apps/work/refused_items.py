# ── Trace ──────────────────────────────────────────────
# Change:   CR-194-BRC10 — refused field work kept on BOTH the phone and the
#           server (PO 2026-10-26, *"store on both"*; plan approved *"start
#           this"*)
# Rules:    BR-WRK-063 (as amended 2026-10-26) · BR-WRK-071 · BR-WRK-042 (the
#           key is spent ONLY by a receipt) · BR-WRK-059 (the captor) ·
#           CLAUDE.md hard rules 1, 6, 7 · **hard-won law 14 (the copy's own
#           savepoint)** · NFR-3 (paged, no cap) · B14 rule 31 (no id shown)
# Tests:    06-backend/tests/test_cr194_refused_field_work.py ·
#           06-backend/tests/test_cr194_refused_field_work_pg.py
# Impacts:  apps/work/sync.py (keep + close) · apps/metering/field_reads.py
#           (through `metering.seams.work_refused_items`) ·
#           apps/work/refused_items_api.py
# ───────────────────────────────────────────────────────
"""The office's copy of every field item the server refused, and what the
office does with it.

WHY A COPY EXISTS AT ALL
────────────────────────────────────────────────────────────────────────────
From 2026-10-21 (*"back to the technician"*) a refused item was answered
`refused` and NOTHING was stored: the phone kept it. On 2026-10-26 the PO
amended that — *"store on both"* — because work on a reassigned or cancelled
job, or on a phone that is lost, was otherwise lost to the office. Worked
example: D. Ortiz's three readings on WO-0028, captured offline after the job
went to M. Chen, are refused back to Ortiz's phone AND listed for the office.

⚠ **THE COPY IS WRITTEN IN ITS OWN SAVEPOINT — HARD-WON LAW 14.**
`keep()` runs AFTER the item's own savepoint has rolled back (or before one
was ever opened), inside the sync's outer transaction. On PostgreSQL a failed
statement there would abort the WHOLE batch — every later item, and the items
already applied, lost at COMMIT — and SQLite cannot see it. So the write is a
nested `transaction.atomic()`, and any failure is logged and answered as
*not kept*: the item is still refused back exactly as before, just without
`kept_for_office`. A copy can never cost the batch.

⚠ **NEVER A RECEIPT.** A receipt spends the key (`BR-WRK-042`); the copy must
not, or the technician's fixed resend would read as a duplicate and be
dropped. The sync's duplicate read never looks at this table.

WHEN THE KEY LATER APPLIES
────────────────────────────────────────────────────────────────────────────
`close_applied()` is called INSIDE the applying item's savepoint, beside its
receipt, so the copy reads `applied_later` (the phone's fixed resend) or
`applied` (the office's *Apply to the job*) if and only if the receipt exists.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.work import mobile
from apps.work import models as work_models
from apps.work.evidence_models import WorkOrderAttachment, WorkPhotoLink
from apps.work.refused_models import (
    DOOR_JOB,
    DOOR_READS,
    DOORS,
    STATUS_APPLIED,
    STATUS_APPLIED_LATER,
    STATUS_OPEN,
    STATUS_REVIEWED,
    STATUSES,
    STATUSES_ACTIONABLE,
    WorkRefusedItem,
)
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy
from core.pagination import DEFAULT_PAGE_SIZE, clamp_page_size

log = logging.getLogger("smartbillhub.work.refused_items")

#: The longest note the office may write on a copy.
NOTE_MAX = 2000


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def _moment(value: Any) -> Any:
    if value in (None, ""):
        return None
    from apps.work.seams import metering_seam

    from core import device_clock

    try:
        # FB-014 — kept on the server's clock, the same time the sync would
        # have stored; the office's *Apply to the job* replays this column.
        return device_clock.correct(metering_seam.parse_moment(value, field="captured_at"))
    except Exception:  # noqa: BLE001 — a malformed time is WHY it was refused; keep it in the payload
        return None


def _point(raw: Any) -> tuple[Any, Any]:
    """`(lat, lng)` from a location/position block, or `(None, None)` —
    where the PHONE was (`BR-MET-1202`), never an address."""
    block = raw if isinstance(raw, dict) else {}
    try:
        from decimal import Decimal

        lat, lng = block.get("lat"), block.get("lng")
        if lat in (None, "") or lng in (None, ""):
            return None, None
        lat_d, lng_d = Decimal(str(lat)), Decimal(str(lng))
        if abs(lat_d) > 90 or abs(lng_d) > 180:
            return None, None
        return lat_d.quantize(Decimal("0.000001")), lng_d.quantize(Decimal("0.000001"))
    except Exception:  # noqa: BLE001
        return None, None


def _captor(item: dict[str, Any], courier: Any) -> tuple[Any, Any]:
    """`(user_id, technician)` — the CAPTOR from the item's token (an expired
    one still names its technician), else the courier who sent it."""
    token = item.get("capture_token")
    if token:
        try:
            actor, technician = mobile.captor_from_token(token, allow_expired=True)
            return _actor_id(actor), technician
        except Exception:  # noqa: BLE001 — an unverifiable token names nobody
            pass
    if courier is None:
        return None, None
    return _actor_id(courier), mobile.technician_of(courier)


def _refusal_words(refusal: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    detail = refusal.get("detail") if isinstance(refusal.get("detail"), dict) else {}
    message_key = str(detail.get("message_key") or refusal.get("message_key") or "")
    reason = str(detail.get("reason") or refusal.get("reason") or "")
    if not reason and message_key:
        reason = message_key.rsplit(".", 1)[-1]
    params = detail.get("params") if isinstance(detail.get("params"), dict) else {}
    return reason, message_key, params


def _photos_of(door: str, kind: str, payload: dict[str, Any], order_id: Any) -> tuple[list[str], list[str]]:
    """The photographs refused WITH this item: declared photo ids (bytes still
    on the phone), and delivered attachments (bytes on the server, kept)."""
    photo_ids: list[str] = []
    attachment_ids: list[str] = []
    if door == DOOR_READS:
        photo_ids = [str(p) for p in (payload.get("photos") or []) if p]
        return photo_ids, attachment_ids
    if kind == "photo" and payload.get("photo_id"):
        photo_ids = [str(payload.get("photo_id"))]
    if kind == "attachment" and order_id and payload.get("idempotency_key"):
        attachment_ids = [
            str(a)
            for a in WorkOrderAttachment.objects.filter(
                tenant_id=_tenant_id(),
                work_order_id=order_id,
                idempotency_key=str(payload.get("idempotency_key")),
            ).values_list("id", flat=True)
        ]
    return photo_ids, attachment_ids


def keep(
    *,
    door: str,
    item: Any,
    refusal: dict[str, Any],
    work_order_id: Any = None,
    courier: Any = None,
) -> bool:
    """Store (or refresh) the office's copy of ONE refused item. True when kept.

    ⚠ LAW 14: its OWN savepoint; never raises. Called after the item's own
    savepoint rolled back, so nothing the item tried is in the database."""
    raw = item if isinstance(item, dict) else {}
    key = str(raw.get("key") or "").strip()
    if not key or door not in DOORS:
        return False
    if door == DOOR_JOB:
        payload = dict(raw.get("payload")) if isinstance(raw.get("payload"), dict) else {}
        location = raw.get("location")
    else:
        payload = {k: v for k, v in raw.items() if k not in ("capture_token", "key")}
        location = raw.get("position")
    payload.pop("capture_token", None)
    kind = str(raw.get("kind") or "").strip() or "unknown"
    reason, message_key, params = _refusal_words(refusal)
    now = timezone.now()
    try:
        # ── THE COPY'S OWN SAVEPOINT. LAW 14. DO NOT REMOVE. ──────────────
        with transaction.atomic():
            tenant_id = _tenant_id()
            order = None
            if work_order_id:
                from apps.work.seams import metering_seam

                order = metering_seam.work_order_row(work_order_id)
            captor_id, technician = _captor(raw, courier)
            photo_ids, attachment_ids = _photos_of(door, kind, payload, getattr(order, "id", None))
            lat, lng = _point(location)
            fields = {
                "door": door,
                "kind": kind,
                "work_order_id": getattr(order, "id", None),
                "captor_id": captor_id,
                "captor_technician": technician,
                "payload": payload,
                "captured_at": _moment(raw.get("captured_at")),
                "lat": lat,
                "lng": lng,
                "reason_code": reason,
                "message_key": message_key,
                "params": params,
                "photo_ids": photo_ids,
                "attachment_ids": attachment_ids,
                "last_refused_at": now,
            }
            row = WorkRefusedItem.objects.filter(tenant_id=tenant_id, key=key).first()
            if row is None:
                WorkRefusedItem.objects.create(
                    tenant_id=tenant_id, key=key, first_refused_at=now, refusal_count=1, **fields
                )
            elif row.status in STATUSES_ACTIONABLE:
                # A resend refused again: the newest words and payload, one
                # more refusal. A copy the office already marked reviewed STAYS
                # reviewed — the same work coming back is not new news.
                for name, value in fields.items():
                    setattr(row, name, value)
                row.refusal_count = (row.refusal_count or 0) + 1
                row.save()
            else:
                # Applied already — nothing to keep; the phone's resend of an
                # applied key is a duplicate and never reaches here.
                return False
        return True
    except Exception:  # noqa: BLE001 — telling the office never costs the batch
        log.exception("work.refused_items: copy of %s not kept", key)
        return False


def mark_kept(answer: dict[str, Any]) -> dict[str, Any]:
    """The refusal answer, saying the office holds a copy."""
    detail = answer.get("detail") if isinstance(answer.get("detail"), dict) else {}
    answer["detail"] = {**detail, "kept_for_office": True}
    return answer


def close_applied(*, key: str, door: str, work_order_id: Any = None, by_office: Any = None) -> int:
    """Close the copy of `key` because the same key has now APPLIED.

    Called INSIDE the applying item's savepoint, beside its receipt, so the
    copy and the receipt can never disagree. `applied` when the office applied
    it, `applied_later` when the technician's resend did."""
    if not key:
        return 0
    query = WorkRefusedItem.objects.filter(
        tenant_id=_tenant_id(), key=key, door=door, status__in=STATUSES_ACTIONABLE
    )
    if work_order_id is not None:
        query = query.filter(Q(work_order_id=work_order_id) | Q(work_order_id__isnull=True))
    now = timezone.now()
    if by_office is not None:
        return query.update(
            status=STATUS_APPLIED,
            applied_by_id=_actor_id(by_office),
            applied_at=now,
            applied_work_order_id=work_order_id,
        )
    return query.update(status=STATUS_APPLIED_LATER, applied_at=now, applied_work_order_id=work_order_id)


# ══════════════════════════════════════════════════════════════════════════
# The office's reads
# ══════════════════════════════════════════════════════════════════════════


def _base() -> Any:
    return WorkRefusedItem.objects.filter(tenant_id=_tenant_id()).select_related(
        "work_order", "captor", "captor_technician__user", "reviewed_by", "applied_by"
    )


def _name(user: Any) -> str | None:
    for attribute in ("display_name", "full_name", "name", "email"):
        value = getattr(user, attribute, None)
        if value:
            return str(value)
    return None


def _technician_name(row: WorkRefusedItem) -> str | None:
    if row.captor_technician_id is not None:
        name = _name(getattr(row.captor_technician, "user", None))
        if name:
            return name
    return _name(row.captor) if row.captor_id else None


def answer(row: WorkRefusedItem) -> dict[str, Any]:
    """One copy as the office list reads it. `id`s are ADDRESSES; every value
    a screen draws is a word, a number a clerk quotes or a count (rule 31)."""
    order = row.work_order if row.work_order_id else None
    return {
        "id": str(row.id),
        "door": row.door,
        "kind": row.kind,
        "status": row.status,
        "reason": row.reason_code,
        "message_key": row.message_key,
        "params": row.params or {},
        "technician": _technician_name(row),
        "technician_id": str(row.captor_technician_id) if row.captor_technician_id else None,
        "work_order": {"id": str(order.id), "order_no": order.order_no} if order is not None else None,
        "captured_at": row.captured_at.isoformat() if row.captured_at else None,
        "first_refused_at": row.first_refused_at.isoformat(),
        "last_refused_at": row.last_refused_at.isoformat(),
        "refusal_count": row.refusal_count,
        "photographs": len(row.photo_ids or []) + len(row.attachment_ids or []),
        "note": row.note or "",
        "reviewed_by": _name(row.reviewed_by) if row.reviewed_by_id else None,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "applied_by": _name(row.applied_by) if row.applied_by_id else None,
        "applied_at": row.applied_at.isoformat() if row.applied_at else None,
    }


def _wanted(value: Any, allowed: tuple[str, ...], message_key: str) -> str | None:
    word = str(value or "").strip().lower()
    if word in ("", "all"):
        return None
    if word not in allowed:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key=message_key,
            params={"value": word, "allowed": ", ".join((*allowed, "all"))},
        )
    return word


def office_page(
    *,
    status: Any = None,
    reason: Any = None,
    technician: Any = None,
    kind: Any = None,
    q: Any = None,
    page: Any = 1,
    per: Any = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """`GET /work/refused-items` — newest refusal first, paged with no cap
    (NFR-3). `status` defaults to `open` (that is the work); `all` clears it.
    `counts` is per status over the OTHER filters, never the page; `facets`
    are the reasons, kinds and technicians present, for the filter menus."""
    base = _base()
    reason_word = str(reason or "").strip()
    if reason_word and reason_word != "all":
        base = base.filter(reason_code=reason_word)
    kind_word = str(kind or "").strip()
    if kind_word and kind_word != "all":
        base = base.filter(kind=kind_word)
    tech = str(technician or "").strip()
    if tech and tech != "all":
        try:
            from uuid import UUID

            base = base.filter(captor_technician_id=UUID(tech))
        except ValueError:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="work.refused.technician_unknown",
                params={"value": tech},
            ) from None
    search = str(q or "").strip()
    if search:
        base = base.filter(work_order__order_no__icontains=search)

    counts = {word: 0 for word in STATUSES}
    for item in base.order_by().values("status").annotate(n=Count("id")):
        counts[item["status"]] = int(item["n"])

    wanted = _wanted(status or STATUS_OPEN, STATUSES, "work.refused.status_unknown")
    query = base.filter(status=wanted) if wanted else base
    query = query.order_by("-last_refused_at", "-id")
    total = query.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size)) if total else 1
    try:
        number = min(max(int(str(page)), 1), last)
    except (TypeError, ValueError):
        number = 1
    start = (number - 1) * size
    rows = [answer(row) for row in query[start : start + size]]

    every = WorkRefusedItem.objects.filter(tenant_id=_tenant_id())
    facets = {
        "reasons": sorted(
            {(r, m) for r, m in every.order_by().values_list("reason_code", "message_key").distinct()}
        ),
        "kinds": sorted(set(every.order_by().values_list("kind", flat=True).distinct())),
        "technicians": [],
    }
    facets["reasons"] = [{"reason": r, "message_key": m} for r, m in facets["reasons"]]
    tech_ids = {t for t in every.order_by().values_list("captor_technician_id", flat=True).distinct() if t}
    for row in work_models.Technician.objects.filter(
        tenant_id=_tenant_id(), id__in=tech_ids
    ).select_related("user"):
        facets["technicians"].append({"id": str(row.id), "name": _name(row.user) or ""})
    facets["technicians"].sort(key=lambda t: t["name"])
    return {"rows": rows, "page": number, "per": size, "total": total, "counts": counts, "facets": facets}


def _row_or_404(item_id: Any) -> WorkRefusedItem:
    row = _base().filter(pk=item_id).first()
    if row is None:
        raise errors.NotFoundError()
    return row


def _work_of(row: WorkRefusedItem) -> dict[str, Any]:
    """The payload rendered as its kind's FIELDS — words and numbers a clerk
    reads, never the raw JSON and never an id (rule 31)."""
    p = row.payload or {}
    oid = row.work_order_id
    work: dict[str, Any] = {"kind": row.kind}
    note = p.get("note") or p.get("remark") or p.get("unable_note")
    if note:
        work["note"] = str(note)
    if row.door == DOOR_READS:
        work["reading"] = {
            "meter_no": p.get("meter_no") or p.get("scanned_code"),
            "value": p.get("value"),
            "unit": p.get("unit"),
            "reader_status": p.get("reader_status"),
            "cant_read_reason": p.get("cant_read_reason"),
        }
        return work
    if row.kind == "reading":
        target = work_models.WorkOrderReading.objects.filter(
            tenant_id=row.tenant_id, work_order_id=oid, id=p.get("reading_id")
        ).first() if oid and p.get("reading_id") else None
        work["reading"] = {
            "prompt": getattr(target, "prompt", None) or p.get("prompt"),
            "value": p.get("value"),
            "unit": p.get("unit"),
            "value_text": p.get("value_text"),
            "unable_to_read": bool(p.get("unable_to_read")),
            "unable_reason": p.get("unable_reason"),
            "flagged": bool(p.get("flagged")),
        }
    elif row.kind == "task_tick":
        target = work_models.WorkOrderTask.objects.filter(
            tenant_id=row.tenant_id, work_order_id=oid, id=p.get("task_id")
        ).first() if oid and p.get("task_id") else None
        work["task"] = {"title": getattr(target, "title", None)}
    elif row.kind == "safety_tick":
        target = work_models.WorkOrderSafety.objects.filter(
            tenant_id=row.tenant_id, work_order_id=oid, id=p.get("safety_id")
        ).first() if oid and p.get("safety_id") else None
        work["safety"] = {"text": getattr(target, "text", None)}
    elif row.kind == "material":
        target = work_models.WorkOrderMaterial.objects.filter(
            tenant_id=row.tenant_id, work_order_id=oid, id=p.get("material_id")
        ).select_related("part").first() if oid and p.get("material_id") else None
        part = getattr(target, "part", None)
        work["material"] = {
            "part": getattr(part, "name", None) if part is not None else None,
            "qty": p.get("used_qty") if p.get("used_qty") is not None else p.get("qty"),
            "unit": getattr(target, "unit_of_measure", None),
        }
    elif row.kind == "close":
        work["close"] = {"outcome": p.get("outcome")}
    return work


def _photos(row: WorkRefusedItem) -> list[dict[str, Any]]:
    """Every photograph refused with this item: delivered ones (bytes on the
    server — `attachment_id`, the office's viewer reads them) and declared
    ones still on the phone. For a reading or a task, the photographs refused
    for the SAME row on the same job are gathered here."""
    tenant_id = row.tenant_id
    oid = row.work_order_id
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    def delivered(attachment_id: Any) -> None:
        if str(attachment_id) in seen:
            return
        seen.add(str(attachment_id))
        out.append({"state": "uploaded", "attachment_id": str(attachment_id), "work_order_id": str(oid)})

    def declared(photo_id: Any) -> None:
        link = WorkPhotoLink.objects.filter(tenant_id=tenant_id, photo_id=photo_id).first() if oid else None
        if link is not None and link.attachment_id:
            delivered(link.attachment_id)
            return
        if f"p:{photo_id}" in seen:
            return
        seen.add(f"p:{photo_id}")
        out.append({"state": "on_phone"})

    for aid in row.attachment_ids or []:
        delivered(aid)
    for pid in row.photo_ids or []:
        declared(pid)
    p = row.payload or {}
    for field in ("reading_id", "task_id"):
        target = p.get(field)
        if not (oid and target and row.kind in ("reading", "task_tick")):
            continue
        siblings = WorkRefusedItem.objects.filter(
            tenant_id=tenant_id, work_order_id=oid, kind__in=("photo", "attachment")
        ).exclude(pk=row.pk)
        for sibling in siblings:
            if str((sibling.payload or {}).get(field) or "") != str(target):
                continue
            for aid in sibling.attachment_ids or []:
                delivered(aid)
            for pid in sibling.photo_ids or []:
                declared(pid)
    return out


def office_detail(item_id: Any) -> dict[str, Any]:
    """`GET /work/refused-items/{id}` — the list's row, the work as sent, its
    photographs, and whether *Apply to the job* can be offered."""
    row = _row_or_404(item_id)
    return {
        **answer(row),
        "work": _work_of(row),
        "photos": _photos(row),
        "can_apply": row.status in STATUSES_ACTIONABLE and row.door == DOOR_JOB and row.work_order_id is not None,
    }


# ══════════════════════════════════════════════════════════════════════════
# The office's acts — each audited (hard rule 7)
# ══════════════════════════════════════════════════════════════════════════


def mark_reviewed(actor: Any, item_id: Any, data: Any) -> dict[str, Any]:
    """`POST /work/refused-items/{id}/review` — `{note?}`. The office has
    looked; the job is not touched. Once applied, a copy is settled."""
    body = data if isinstance(data, dict) else {}
    note = str(body.get("note") or "").strip()
    if len(note) > NOTE_MAX:
        raise errors.ValidationError(
            errors.VAL_RANGE, message_key="work.refused.note_too_long", params={"max": NOTE_MAX}
        )
    with transaction.atomic():
        row = _row_or_404(item_id)
        if row.status not in STATUSES_ACTIONABLE:
            raise errors.BizError(
                errors.BIZ_STATE, message_key="work.refused.already_applied", br_ref="BR-WRK-071"
            )
        before = {"status": row.status, "note": row.note}
        row.status = STATUS_REVIEWED
        row.note = note or row.note
        row.reviewed_by_id = _actor_id(actor)
        row.reviewed_at = timezone.now()
        row.save(update_fields=["status", "note", "reviewed_by", "reviewed_at"])
        core_audit.write_row(
            action="work.refused_item.reviewed",
            entity_type="work_refused_item",
            entity_id=row.id,
            actor_user_id=_actor_id(actor),
            before=before,
            after={"status": row.status, "note": row.note, "br_ref": "BR-WRK-071"},
        )
    return office_detail(row.id)


def apply_to_job(actor: Any, item_id: Any) -> dict[str, Any]:
    """`POST /work/refused-items/{id}/apply` — re-run the kind's NORMAL apply
    path, as the office person, under the item's own key.

    Conservative by design (CR-194-BRC10 §3.7): applied only when the service
    accepts it NOW. Refused, with the reason, when the copy came through the
    route-reads door (the reads pipeline posts a route reading, never this),
    when the job is closed, cancelled or accepted, or when the service refuses
    it. A receipt is written under the item's key inside the same savepoint,
    so the phone's later resend is a duplicate and leaves its outbox."""
    from apps.work import sync
    from apps.work.sync_models import ITEM_KINDS, WorkSyncReceipt

    row = _row_or_404(item_id)
    if row.status not in STATUSES_ACTIONABLE:
        raise errors.BizError(errors.BIZ_STATE, message_key="work.refused.already_applied", br_ref="BR-WRK-071")
    if row.door != DOOR_JOB or row.work_order_id is None or row.kind not in ITEM_KINDS:
        raise errors.BizError(errors.BIZ_STATE, message_key="work.refused.apply_job_only", br_ref="BR-WRK-071")
    state = mobile.order_state_reason(row.work_order_id, row.kind)
    if state is not None:
        raise errors.BizError(errors.BIZ_STATE, message_key=state, br_ref="BR-WRK-071")
    tenant_id = _tenant_id()
    if WorkSyncReceipt.objects.filter(tenant_id=tenant_id, work_order_id=row.work_order_id, key=row.key).exists():
        # The key landed some other way meanwhile: close the copy and say so.
        close_applied(key=row.key, door=DOOR_JOB, work_order_id=row.work_order_id)
        raise errors.BizError(errors.BIZ_STATE, message_key="work.refused.already_applied", br_ref="BR-WRK-071")
    try:
        with transaction.atomic():
            WorkSyncReceipt.objects.create(
                tenant_id=tenant_id,
                work_order_id=row.work_order_id,
                key=row.key,
                kind=row.kind,
                seq=0,
                captured_at=row.captured_at,
                accepted_by_id=row.captor_id or _actor_id(actor),
                captured_by_technician=row.captor_technician,
                lat=row.lat,
                lng=row.lng,
            )
            applied = sync.apply_kind(actor, row.work_order_id, row.kind, dict(row.payload or {}), row.captured_at)
            close_applied(key=row.key, door=DOOR_JOB, work_order_id=row.work_order_id, by_office=actor)
            core_audit.write_row(
                action="work.refused_item.applied",
                entity_type="work_refused_item",
                entity_id=row.id,
                actor_user_id=_actor_id(actor),
                before={"status": row.status},
                after={
                    "status": STATUS_APPLIED,
                    "work_order_id": str(row.work_order_id),
                    "kind": row.kind,
                    "key": row.key,
                    "br_ref": "BR-WRK-071",
                },
            )
    except errors.ApiError as exc:
        raise errors.BizError(
            errors.BIZ_STATE,
            message_key=getattr(exc, "message_key", None) or "work.refused.not_applied",
            params=getattr(exc, "params", None) or {},
            br_ref="BR-WRK-071",
        ) from None
    except Exception:  # noqa: BLE001 — the service could not apply it; nothing moved
        log.exception("work.refused_items: apply of %s failed", row.key)
        raise errors.BizError(
            errors.BIZ_STATE, message_key="work.refused.not_applied", br_ref="BR-WRK-071"
        ) from None
    out = office_detail(row.id)
    out["applied"] = applied if isinstance(applied, dict) else None
    return out


__all__ = [
    "DOOR_JOB",
    "DOOR_READS",
    "STATUS_OPEN",
    "keep",
    "mark_kept",
    "close_applied",
    "office_page",
    "office_detail",
    "mark_reviewed",
    "apply_to_job",
]
