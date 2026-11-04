# ── Trace ──────────────────────────────────────────────
# Change:   FB-030 (PO 2026-10-31, decision log *"FB-030: a technician's
#           history is the last 14 days, kept on the phone"* and its *"photos
#           3 days"* follow-up) — the reader's own turned-in route readings of
#           the last 14 days, so a new phone, a reinstall or a remote sign-out
#           is refilled with RW-28's reference; and a route photograph's bytes,
#           loaded on tap once the phone has deleted its file.
# Rules:    BR-FLD-00061 (R61, SUPERSEDED in part 2026-10-31) · BR-FLD-00062
#           (R62, retention) · BR-FLD-00120 (R120 — what was read, never how
#           fast) · hard rule 1 (tenant scope; `field_reads` is FORCE RLS) ·
#           hard rule 3 (a figure travels with its unit) · hard rule 8 (the
#           address from the premises) · NFR-3 / NFR-5 (paged in SQL, no cap)
# Tests:    06-backend/tests/test_fb030_history.py ·
#           06-backend/tests/test_fb030_history_pg.py
# ───────────────────────────────────────────────────────
"""The reader's own history: their turned-in readings of the last 14 days.

WHAT IS "MINE" — the reading's `reader_id` is the caller, and the route it was
taken on was turned in BY THE CALLER inside the window (`field_route_turn_ins`).
A route somebody else turned in is not this reader's history, and there is no
parameter that names another reader: a route with no such parameter cannot be
asked the question (the `mobile.today` posture).

NO MONEY AND NO SPEED FIGURES (R120, PO 2026-10-31): a reading's value, unit,
status and reason — never a rate, a count per hour or a ranking.

PAGED IN SQL, NO CAP: `(received_at, id)` order, a page sized by
`clamp_page_size`, the count beside it. The read goes by READER — the index
`field_reads.reader_id` already carries as a foreign key; no new index was
needed (measured on PostgreSQL 16, `tests/test_fb030_history_pg.py`).
"""

from __future__ import annotations

import math
from datetime import timedelta
from typing import Any
from uuid import UUID

from django.db.models import Max
from django.utils import timezone

from apps.metering.field_read_models import FieldRead, FieldReadPhoto, FieldRouteTurnIn
from core import errors
from core import permissions as core_permissions
from core import tenancy as core_tenancy
from core.pagination import clamp_page_size

#: FB-030 — the same 14 days the work module's history reaches
#: (`apps/work/mobile.py` `HISTORY_DAYS`). Kept here rather than imported:
#: metering does not read the work module.
HISTORY_DAYS = 14

#: BR-MET-052 / FB-022 — the meter read's status when the figure was lower
#: than the last one; such a reading posts with this flag and does not bill.
NEGATIVE_USAGE = "negative_usage"


def _tenant_id() -> UUID:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def history_since(now: Any = None) -> Any:
    return (now or timezone.now()) - timedelta(days=HISTORY_DAYS)


def reads_history(actor: Any, *, page: Any = 1, per: Any = None) -> dict[str, Any]:
    """`GET work/mobile/reads/history?page=&per=` — one page of the caller's
    own readings on routes they turned in during the last 14 days."""
    from apps.metering import field_reads
    from apps.metering.models import MeterRead

    tenant_id = _tenant_id()
    me = _actor_id(actor)
    since = history_since()
    turned = FieldRouteTurnIn.objects.filter(
        tenant_id=tenant_id, reader_id=me, received_at__gte=since
    )
    qs = (
        FieldRead.objects.filter(
            tenant_id=tenant_id,
            reader_id=me,
            kind=field_reads.KIND_READING,
            received_at__gte=since,
            route_id__in=turned.values("route_id"),
        )
        .select_related("route", "route__cycle", "asset", "premises")
        .order_by("received_at", "id")
    )
    size = clamp_page_size(per)
    total = qs.count()
    last = max(1, math.ceil(total / size))
    try:
        number = int(page or 1)
    except (TypeError, ValueError):
        number = 1
    number = max(1, min(number, last))
    rows = list(qs[(number - 1) * size : number * size])

    route_ids = {row.route_id for row in rows}
    turned_at = {
        r["route_id"]: r["at"]
        for r in turned.filter(route_id__in=route_ids).values("route_id").annotate(at=Max("received_at"))
    }
    read_ids = [row.meter_read_id for row in rows if row.meter_read_id]
    lower = set(
        MeterRead.objects.filter(tenant_id=tenant_id, id__in=read_ids, status=NEGATIVE_USAGE).values_list(
            "id", flat=True
        )
    ) if read_ids else set()
    reasons = field_reads.cant_read_reason_index()

    def reason_name(code: str | None) -> str | None:
        if not code:
            return None
        found = reasons.get(code.casefold())
        return found["name"] if found else None

    results = []
    for row in rows:
        route = row.route
        asset = row.asset
        place = row.premises
        results.append(
            {
                "key": row.key,
                "route": {
                    "id": str(row.route_id),
                    "code": getattr(route, "code", None),
                    "name": getattr(route, "name", None),
                    "cycle": getattr(getattr(route, "cycle", None), "code", None),
                    "turned_in_at": turned_at[row.route_id].isoformat()
                    if turned_at.get(row.route_id)
                    else None,
                },
                "asset_id": str(row.asset_id) if row.asset_id else None,
                "meter_no": getattr(asset, "asset_no", None),
                "serial_no": getattr(asset, "serial_no", None),
                "premises_id": str(row.premises_id) if row.premises_id else None,
                "premise_no": getattr(place, "premise_no", None),
                # Hard rule 8 — the address walked from the premises.
                "address": getattr(place, "address_line", None),
                "register": row.channel,
                # Hard rule 3 — the unit travels with the figure.
                "value": str(row.value) if row.value is not None else None,
                "unit": row.unit,
                "reader_status": row.reader_status,
                "cant_read_reason": row.cant_read_reason,
                "cant_read_reason_name": reason_name(row.cant_read_reason),
                "remark": row.remark,
                "captured_at": (row.device_captured_at or row.received_at).isoformat(),
                # FB-022 — posted with its flag, waiting for a clerk.
                "lower_than_last": row.meter_read_id in lower,
                "photo_ids": [str(p) for p in (row.photo_ids or [])],
            }
        )
    return {
        "count": total,
        "page": number,
        "pages": last,
        "next_page": number + 1 if number < last else None,
        "results": results,
        "br_ref": "BR-FLD-00062",
    }


def route_photo_content(actor: Any, photo_id: Any) -> tuple[bytes, str]:
    """`GET work/mobile/reads/photos/{photo_id}/content` — FB-030: a ROUTE
    photograph's bytes, loaded on tap once the phone deleted its file (3 days
    after the turn-in). A field technician reaches their OWN photographs only
    — another reader's is the same 404 as one that does not exist (HR-1). An
    office role is not narrowed. Shown, never kept (`private, no-store`)."""
    qs = FieldReadPhoto.objects.filter(
        tenant_id=_tenant_id(), photo_id=photo_id, state=FieldReadPhoto.STATE_LANDED
    )
    if getattr(actor, "role", None) == core_permissions.FIELD_TECHNICIAN:
        qs = qs.filter(reader_id=_actor_id(actor))
    link = qs.first()
    if link is None or link.data is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return bytes(link.data), link.content_type or "image/jpeg"
