# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 Phase 13 task T-42, lane S-ORDER — field-raised orders
#           from the handset, auto-filled with premise, account, customer and
#           position, starting from a picked template (FF-37 Raise, FF-62 Pick
#           a template, RW-21; E2E-16), the office's field-raised queue, and
#           the template catalogue a technician may read (`07-endpoints.md` N8,
#           N16).
# Rules:    BR-FLD-00112 (R112 — raising starts with a template; every published
#           template is offered, recently used first, search behind it; the
#           order takes its own copy and stamps the version) · BR-FLD-00024
#           (R24 — no number until it syncs) · BR-FLD-00023 (R23 — SUPERSEDED
#           2026-10-31, FB-028: a raised order is assigned to its raiser in the
#           same act; the money decision moved onto the job's step) ·
#           BR-WRK-006 (an order stands on an anchor) · BR-WRK-008 (the copy) ·
#           BR-WRK-061 (a position carries its accuracy) · hard rules 1, 6's
#           shape (idempotent on the key minted at capture), 7
# Tests:    06-backend/tests/test_cr187_order_raise.py ·
#           06-backend/tests/test_fb028_raise_assigns.py (FB-028, DEF-WRK-10800)
# Impacts:  apps/work/field_orders_api.py · work_field_raises ·
#           work_order_assignments (one `assign` row per raise)
# ───────────────────────────────────────────────────────
"""An order raised where the technician is standing — and the office's queue of them.

THE ORDER IS METERING'S, RAISED THROUGH THE ONE DOOR
----------------------------------------------------
`metering_seam.raise_work_order` → `create_work_order`, exactly the door the
office's raise uses: it allocates the `WO-` number from the tenant's series
(R24 — the number exists from the first successful send, never on the
handset), copies the template's seven collections onto the order and stamps
`template_version` (R112, `BR-WRK-008` — editing the template later changes
nothing already raised), refuses an unpublished template, and writes its own
audit row. This file adds the FIELD half beside it, in the same transaction:
one `work_field_raises` row with the position, the need, the urgency, what it
was carried from and the version the technician PICKED.

⚠ **THE VERSION PICKED AND THE VERSION STAMPED CAN DIFFER, AND THE ANSWER SAYS
SO.** The handset picked *Leak investigation v3* from a catalogue it synced
this morning; if the office published v4 at noon, the server copies v4 —
`create_work_order` copies the template AS IT STANDS, and no older version's
body is kept to copy from. The order is still one honest copy of one stamped
version; `version_moved: true` tells the handset (and the office row) that it
is not the one that was on the screen.

AUTO-FILLED (E2E-16)
--------------------
With `carried_from` (FF-37 *Carried from WO-4801*), the new order stands on
the SAME anchors as that order — its premises, account, asset and unit — and
the technician types none of them. Without it, the handset sends the anchors
it is standing on (`premises_id`, `account_id`, `asset_id`, `unit_id`), at
least one (`BR-WRK-006`). The answer names the premise, the account and the
customer, so FF-37's card can be confirmed against the server's reading.

THE RAISER'S JOB, AT ONCE (FB-028, PO 2026-10-31 — R23 SUPERSEDED)
-------------------------------------------------------------------
⚠ **THIS SECTION READ *"PENDING, ALWAYS … never assigned, never scheduled from
here"* UNTIL 2026-10-31.** The PO asked why a raised order should wait for the
back office at all and ruled, for every template — reconnects and disconnects
included — that it goes to the technician who raised it (decision log
*"FB-028: raised reconnects go to the technician…"* W1, W3 = C, and
*"Field-raised disconnects go to the technician with the live checks"*). So in
the SAME transaction as the order and its field row, the order is ASSIGNED to
the raiser through the one history writer (`dispatch.append_act`, act
`assign`, reason `raised_on_site`) and accepted as a claim is — one audit row,
`work.order.raised_in_field`, naming the technician and the assignment; no push
(the raiser's own phone is the one asking, and it fetches the job after this
answer). A template whose skill the raiser lacks is STILL assigned: the miss is
recorded as advice (`dispatch._audit_against_advice`, ruling 2 of 2026-09-23)
and the answer carries `advice` so the phone warns before Start.

What used to be the office's approval is now a REVIEW: the row still lands
`pending` in the field-raised queue, *Accept* records that the office has seen
it, and the dispatcher may reassign the order at any time like any other. The
MONEY decision R23 kept for the office moved onto the job itself — the
reconnect step is gated by the live balance against the template's *Reconnect
limit*, and a disconnect step stops on a cleared balance, an unexpired notice
or a protected account (`money_flow_facts.field_gate`).

⚠ **WHAT IS NOT DONE, AND WHY — EACH A GAP FOR THE REPORT, NOT A GUESS:**
* **No `source` token.** `ck_work_orders_source` holds seventeen and none means
  *raised in the field*; a new one is a metering migration (`metering/0076`'s
  CHECK). `source` stays NULL, which the CHECK admits; the queue is this
  table, not a source filter.
* **Urgency does not set priority.** FF-37 draws *Normal · Same day ·
  Emergency*; the tenant's priorities are *Urgent · High · Normal · Low*. Which
  priority *Same day* means is unruled, so the order takes its type's default
  priority (`create_work_order`'s own rule) and the urgency is stored AS SAID
  for the office to act on.
* **Photographs** ride the existing evidence routes against the new order's id
  once it has one (`POST work-orders/{id}/attachments`, the photo links) —
  the order exists from this call's answer.
"""

from __future__ import annotations

import math
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import F, Max, OuterRef, Q, Subquery
from django.utils import timezone

from apps.work import mobile
from apps.work.field_order_models import (
    FIELD_RAISE_ACCEPTED,
    FIELD_RAISE_PENDING,
    FIELD_RAISE_REFUSED,
    FIELD_RAISE_STATUSES,
    URGENCIES,
    URGENCY_NORMAL,
    WorkFieldRaise,
    WorkOrderLabour,
)
from apps.work.seams import customers_seam, identity_seam, metering_seam
from core import audit as core_audit
from core import device_clock, errors
from core import tenancy as core_tenancy
from core.pagination import DEFAULT_PAGE_SIZE, clamp_page_size

#: The longest *What is needed* label kept. FF-37's chips are one or two words.
NEED_CHARS = 60
#: A need word the handset may send. Kept on the answer as `is_reconnect` for
#: the office row; since FB-028 it decides nothing (every raise is assigned).
RECONNECT_NEEDS: tuple[str, ...] = ("reconnect", "reconnection")
ANCHORS: tuple[str, ...] = ("premises_id", "account_id", "asset_id", "unit_id")
#: FB-028 — the reason on the `assign` history row a raise writes, beside
#: `claimed` (`field_dispatch.claim`). The board and the Audit tab read it.
RAISED_ON_SITE = "raised_on_site"


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def _page(qs: Any, page: Any, per: Any) -> tuple[list[Any], int, int, int]:
    total = qs.count()
    size = clamp_page_size(per)
    last = max(1, math.ceil(total / size)) if total else 1
    try:
        number = min(max(int(str(page)), 1), last)
    except (TypeError, ValueError):
        number = 1
    start = (number - 1) * size
    return list(qs[start : start + size]), number, size, total


# ══════════════════════════════════════════════════════════════════════════
# The template catalogue a technician may read (N8, FF-62)
# ══════════════════════════════════════════════════════════════════════════
def templates_catalogue(
    actor: Any, *, q: Any = None, page: Any = 1, per: Any = DEFAULT_PAGE_SIZE
) -> dict[str, Any]:
    """`GET /work/mobile/templates?q=&page=&page_size=` — every PUBLISHED,
    ACTIVE template (R112: *"every published template is offered"*), the
    caller's recently used first, then by name; search behind it. Paged, no cap.

    `GET /work/templates` stays the office's list under `WorkTemplateListRead`,
    which does not admit the technician (`07-endpoints.md` N8); this route is
    `FieldAppRole` and READS only. *Recently used* is THIS technician's own
    field raises — never another person's — so a shared catalogue still opens
    on each person's own habits.
    """
    from apps.work import selectors as work_selectors

    qs = metering_seam.templates_queryset().filter(active=True, version__gte=1)
    term = str(q or "").strip()
    if len(term) >= 2:
        qs = qs.filter(Q(name__icontains=term) | Q(type__name__icontains=term))
    technician = mobile.technician_of(actor)
    last_used = None
    if technician is not None:
        last_used = (
            WorkFieldRaise.objects.filter(
                tenant_id=_tenant_id(),
                raised_by_technician_id=technician.id,
                work_order__template_id=OuterRef("pk"),
            )
            .order_by()
            .values("work_order__template_id")
            .annotate(at=Max("created_at"))
            .values("at")
        )
        qs = qs.annotate(last_used_at=Subquery(last_used))
        ordering = [F("last_used_at").desc(nulls_last=True), "name", "id"]
    else:
        ordering = ["name", "id"]
    qs = qs.annotate(**work_selectors._content_annotations()).order_by(*ordering)
    rows, number, size, total = _page(qs, page, per)
    out = []
    for row in rows:
        header = metering_seam._template_row(row)
        used = getattr(row, "last_used_at", None)
        out.append(
            {
                "id": header["id"],
                "name": header["name"],
                "version": header["version"],
                "service": header["service"],
                "job_type": header["job_type"],
                "steps": int(row.contents_tasks or 0),
                "safety_checks": int(row.contents_safety or 0),
                "readings": int(row.contents_readings or 0),
                "materials": int(row.contents_parts or 0),
                "help": int(row.contents_help or 0),
                "last_used_at": used.isoformat() if used else None,
                "recent": used is not None,
            }
        )
    return {"rows": out, "page": number, "per": size, "total": total}


def template_body(template_id: Any) -> dict[str, Any]:
    """`GET /work/mobile/templates/{id}` — one published template WHOLE, the
    seven collections in `seq` order, so FF-37 can show what the order will
    carry before it is sent. A draft or inactive template is a 404 here (the
    catalogue does not offer it)."""
    from apps.work import selectors as work_selectors

    header = metering_seam.template(template_id)
    if header is None or not header.get("active") or int(header.get("version") or 0) < 1:
        raise errors.NotFoundError()
    return {**header, **work_selectors._collection_rows(template_id)}


# ══════════════════════════════════════════════════════════════════════════
# The raise (N16, FF-37)
# ══════════════════════════════════════════════════════════════════════════
def _carried_from(technician: Any, order_id: Any) -> Any:
    """The order FF-37 carries from — one the caller held or worked on. Any
    other is a 404 (HR-1, and a technician raising off a colleague's job is
    reading a job they were never given)."""
    order = metering_seam.work_order_row(order_id)
    if order is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    held = order.assignee_technician_id == technician.id or (
        order.assignee_crew_id and technician.crew_id == order.assignee_crew_id
    )
    worked = WorkOrderLabour.objects.filter(
        tenant_id=_tenant_id(), work_order_id=order.id, technician_id=technician.id
    ).exists()
    if not (held or worked):
        raise errors.deny_as_not_found("BR-TEN-003")
    return order


def _answer(raise_row: Any, *, duplicate: bool = False) -> dict[str, Any]:
    from apps.work import selectors as work_selectors

    order = metering_seam.orders_by_ids_queryset([raise_row.work_order_id]).first()
    account = customers_seam.account(order.account_id) if order.account_id else None
    template = order.template if order.template_id else None
    picked = raise_row.template_version_picked
    stamped = raise_row.template_version_stamped
    return {
        "order_id": str(order.id),
        # R24 — the number the server allocated; the handset shows it from now.
        "order_no": order.order_no,
        "status": raise_row.status,
        "dispatch_state": order.dispatch_state,
        "assigned": bool(order.assignee_technician_id or order.assignee_crew_id),
        # FB-028 — who holds it now: the raiser at first, whoever the office
        # reassigned it to after. A name, never an id on screen (B14 rule 31).
        "assigned_to": _holder_of(order),
        "template": (
            {
                "id": str(template.id),
                "name": template.name,
                "version_stamped": stamped,
                "version_picked": picked,
                "version_moved": picked is not None and stamped is not None and picked != stamped,
            }
            if template is not None
            else None
        ),
        "carried_from": (
            {"id": str(raise_row.carried_from_id), "order_no": raise_row.carried_from.order_no}
            if raise_row.carried_from_id
            else None
        ),
        "premise": work_selectors._premise_of(order),
        "account": (
            {"id": account["id"], "account_no": account["account_no"]} if account else None
        ),
        "customer": (
            {"name": account["name"], "customer_no": account["customer_no"]} if account else None
        ),
        "position": (
            {
                "lat": f"{raise_row.lat}",
                "lng": f"{raise_row.lng}",
                "accuracy_m": f"{raise_row.accuracy_m}",
            }
            if raise_row.lat is not None
            else None
        ),
        "need": raise_row.need,
        "urgency": raise_row.urgency,
        "is_reconnect": (raise_row.need or "").strip().lower() in RECONNECT_NEEDS,
        "note": raise_row.note,
        "captured_at": raise_row.captured_at.isoformat() if raise_row.captured_at else None,
        "duplicate": duplicate,
    }


def _holder_of(order: Any) -> dict[str, Any] | None:
    technician = (
        getattr(order, "assignee_technician", None) if order.assignee_technician_id else None
    )
    if technician is None:
        return None
    user = getattr(technician, "user", None)
    return {"id": str(technician.id), "name": (getattr(user, "full_name", None) or None)}


def _advice_of(order: Any, technician: Any) -> dict[str, Any]:
    """FB-028 W3 = C — does the raiser hold the skill the template asks for?
    The phone warns before Start when `has_skill` is false; nothing refuses."""
    from apps.work import advice

    skill_id = order.template.skill_id if order.template_id else None
    seen = advice.advice_for(technician=technician, skill_id=skill_id, on=advice.order_day(order))
    return {
        "skill": seen["skill"],
        "has_skill": seen["has_skill"],
        "certifications_lapsed": seen["certifications_lapsed"],
    }


def _assign_to_raiser(actor: Any, order_id: Any, technician: Any) -> tuple[Any, Any, Any]:
    """FB-028 (PO 2026-10-31, W1 / W3 = C / field-raised disconnects = B) — the
    raised order is the raiser's: one `assign` history row (`raised_on_site`),
    accepted as a claim is, the skill miss recorded as advice. INSIDE the
    raise's transaction. No push: the raiser's own phone made this call."""
    from apps.work import dispatch

    order = metering_seam.work_order_row_for_update(order_id)
    row = dispatch.append_act(actor, order, "assign", technician=technician, reason=RAISED_ON_SITE)
    order.accepted_by_technician_id = technician.id
    order.accepted_at_technician = timezone.now()
    metering_seam.save_order_fields(order, ["accepted_by_technician", "accepted_at_technician"])
    against = dispatch._audit_against_advice(actor, order, row, technician, None)
    return order, row, against


def raise_from_field(actor: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work/mobile/orders` — FF-37's *Send*.

    Body: `{key, template_id, template_version?, carried_from?, premises_id?,
    account_id?, asset_id?, unit_id?, need?, urgency?, note?, captured_at?,
    location?: {lat, lng, accuracy_m, fix_at}}`. `key` is minted on the handset
    at capture and is REQUIRED: a replay answers the first order, number and
    all, with `duplicate: true`, and raises nothing (R45; the outbox re-sends
    after a crash). Only a login with a technician profile raises here — the
    office has its own raise (`POST /work-orders`).
    """
    technician = mobile.technician_of(actor)
    if technician is None:
        raise errors.AuthError(
            errors.AUTH_PERMISSION_DENIED,
            br_ref="BR-FLD-00024",
            message_key="work.raise.field_only",
        )
    data = payload or {}
    key = str(data.get("key") or "").strip()
    if not key:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            br_ref="BR-FLD-00024",
            message_key="work.raise.capture_key_required",
        )
    seen = WorkFieldRaise.objects.filter(tenant_id=_tenant_id(), key=key).first()
    if seen is not None:
        return _answer(seen, duplicate=True)

    template_id = str(data.get("template_id") or "").strip()
    if not template_id:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, br_ref="BR-FLD-00112", message_key="work.raise.template_required"
        )
    header = metering_seam.template(template_id)
    if header is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    if not header.get("active"):
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-FLD-00112",
            message_key="work.raise.template_inactive",
            params={"template": header.get("name") or ""},
        )
    picked = data.get("template_version")
    try:
        picked = int(picked) if picked not in (None, "") else None
    except (TypeError, ValueError):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            br_ref="BR-FLD-00112",
            message_key="work.raise.template_version_not_a_number",
        ) from None

    urgency = str(data.get("urgency") or URGENCY_NORMAL).strip().lower()
    if urgency not in URGENCIES:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            br_ref="BR-FLD-00023",
            message_key="work.raise.urgency_unknown",
            params={"urgency": urgency, "allowed": ", ".join(URGENCIES)},
        )
    need = str(data.get("need") or "").strip() or None
    if need is not None and len(need) > NEED_CHARS:
        raise errors.ValidationError(
            errors.VAL_RANGE,
            br_ref="BR-FLD-00023",
            message_key="work.raise.need_too_long",
            params={"max": NEED_CHARS},
        )
    note = str(data.get("note") or "").strip() or None
    location = mobile.parse_location(data.get("location"))
    captured_at = None
    if data.get("captured_at"):
        # FB-014 (DEF-FLD-10639) — onto the server's clock; with the phone's
        # clock reading on the request this is never ahead, and the refusal
        # below is left only for a send with no reading, > 5 minutes ahead.
        captured_at = device_clock.correct(
            metering_seam.parse_moment(data.get("captured_at"), field="captured_at")
        )
        if captured_at is not None and captured_at > timezone.now():
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                br_ref="BR-TEN-043",
                message_key="work.raise.captured_in_future",
            )

    carried = None
    if data.get("carried_from"):
        carried = _carried_from(technician, data.get("carried_from"))
        anchors = {
            "premises_id": carried.premises_id,
            "account_id": carried.account_id,
            "asset_id": carried.asset_id,
            "unit_id": carried.unit_id,
            "connection_id": carried.connection_id if not carried.premises_id else None,
        }
    else:
        anchors = {name: data.get(name) for name in ANCHORS}
    order_payload = {name: str(value) for name, value in anchors.items() if value not in (None, "")}
    order_payload["template_id"] = template_id
    if note:
        order_payload["technician_notes"] = note

    try:
        # ⚠ ONE TRANSACTION, AND A SAVEPOINT — hard-won law 14. The order and
        # its field row are one act: a raise whose field row fails must not
        # leave an order nobody can find in the field-raised queue. A lost race
        # on `key` (two sends of one outbox item) is caught OUTSIDE the
        # savepoint, which rolled the second order back whole — number and all.
        with transaction.atomic():
            created = metering_seam.raise_work_order(actor, order_payload)
            assigned, assignment, against = _assign_to_raiser(actor, created["id"], technician)
            row = WorkFieldRaise.objects.create(
                tenant_id=_tenant_id(),
                work_order_id=created["id"],
                key=key,
                raised_by_id=_actor_id(actor),
                raised_by_technician=technician,
                captured_at=captured_at,
                lat=(location or {}).get("lat"),
                lng=(location or {}).get("lng"),
                accuracy_m=(location or {}).get("accuracy_m"),
                need=need,
                urgency=urgency,
                note=note,
                carried_from=carried,
                template_version_picked=picked,
                template_version_stamped=metering_seam.work_order_row(
                    created["id"]
                ).template_version,
                status=FIELD_RAISE_PENDING,
            )
            core_audit.write_row(
                action="work.order.raised_in_field",
                entity_type="work_order",
                entity_id=created["id"],
                actor_user_id=_actor_id(actor),
                before=None,
                after={
                    "order_no": created.get("order_no"),
                    "template": header.get("name"),
                    "template_version": row.template_version_stamped,
                    "carried_from": carried.order_no if carried is not None else None,
                    "need": need,
                    "urgency": urgency,
                    "status": FIELD_RAISE_PENDING,
                    # FB-028 — the assignment is part of the one act.
                    "technician": (_holder_of(assigned) or {}).get("name"),
                    "dispatch_state": assigned.dispatch_state,
                    "assignment_id": str(assignment.id),
                    "against_advice": against,
                    "br_ref": "BR-FLD-00024",
                },
            )
    except IntegrityError:
        seen = WorkFieldRaise.objects.filter(tenant_id=_tenant_id(), key=key).first()
        if seen is None:
            raise
        return _answer(seen, duplicate=True)
    answer = _answer(row)
    answer["advice"] = _advice_of(assigned, technician)
    return answer


# ══════════════════════════════════════════════════════════════════════════
# The office's field-raised queue (Walkthrough §4, E2E-16)
# ══════════════════════════════════════════════════════════════════════════
def raised_in_field_ids(order_ids: list[Any]) -> set[str]:
    """Which of these orders were raised in the field — for other queues'
    rows (`field_outcomes.office_queue`)."""
    if not order_ids:
        return set()
    return {
        str(v)
        for v in WorkFieldRaise.objects.filter(
            tenant_id=_tenant_id(), work_order_id__in=list(order_ids)
        ).values_list("work_order_id", flat=True)
    }


def field_raised_queue(
    *, status: Any = None, page: Any = 1, per: Any = DEFAULT_PAGE_SIZE
) -> dict[str, Any]:
    """`GET /work/field-raised?status=pending|accepted|refused|all` — orders
    raised on site, oldest first, with their position and photographs.
    Default `pending`. `counts` is over every status, never the page."""
    from django.db.models import Count

    from apps.work.evidence_models import WorkOrderAttachment

    base = WorkFieldRaise.objects.filter(tenant_id=_tenant_id())
    counts = {s: 0 for s in FIELD_RAISE_STATUSES}
    for row in base.order_by().values("status").annotate(n=Count("id")):
        counts[row["status"]] = int(row["n"])
    wanted = str(status or FIELD_RAISE_PENDING).strip().lower()
    if wanted != "all":
        if wanted not in FIELD_RAISE_STATUSES:
            raise errors.ValidationError(
                errors.VAL_UNKNOWN_LOOKUP,
                message_key="work.raise.status_unknown",
                params={"status": wanted, "allowed": ", ".join((*FIELD_RAISE_STATUSES, "all"))},
            )
        base = base.filter(status=wanted)
    qs = base.select_related(
        "raised_by", "raised_by_technician__user", "carried_from", "decided_by"
    ).order_by("created_at", "id")
    rows, number, size, total = _page(qs, page, per)
    photos = {
        str(r["work_order_id"]): int(r["n"])
        for r in WorkOrderAttachment.objects.filter(
            tenant_id=_tenant_id(), work_order_id__in=[r.work_order_id for r in rows]
        )
        .values("work_order_id")
        .annotate(n=Count("id"))
    }
    out = []
    for row in rows:
        shaped = _answer(row)
        raiser = row.raised_by_technician
        shaped.update(
            {
                "raised_by": (
                    (getattr(raiser.user, "full_name", None) or None)
                    if raiser is not None
                    else None
                ),
                "raised_at": row.created_at.isoformat(),
                "photographs": photos.get(str(row.work_order_id), 0),
                "decided_by": ((row.decided_by.full_name or None) if row.decided_by_id else None),
                "decided_at": row.decided_at.isoformat() if row.decided_at else None,
                "decision_reason": row.decision_reason,
            }
        )
        out.append(shaped)
    return {"rows": out, "page": number, "per": size, "total": total, "counts": counts}


def decide(actor: Any, order_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work-orders/{id}/field-raise` — `{decision: accept | refuse,
    reason?}`: the office's acceptance of an order raised in the field.

    *Accept* records that the office has SEEN it (FB-028: the order is already
    the raiser's; the dispatcher may reassign it at any time, as any other). *Refuse* needs a reason and takes
    the order off the run as *Cancelled*, nothing deleted (the `cancel` door's
    own posture; it keeps its number and history). The same decision twice
    answers the first; the other decision after one is made is refused
    `work.raise.already_decided`. The office roles that accept field work make
    this call (`work_accept`).
    """
    if not identity_seam.may(actor, "work_accept"):
        raise errors.AuthError(
            errors.AUTH_PERMISSION_DENIED,
            br_ref="BR-WRK-044",
            message_key="metering.work_order_accept_not_permitted",
        )
    row = WorkFieldRaise.objects.filter(tenant_id=_tenant_id(), work_order_id=order_id).first()
    if row is None:
        raise errors.NotFoundError()
    data = payload or {}
    decision = str(data.get("decision") or "").strip().lower()
    target = {"accept": FIELD_RAISE_ACCEPTED, "refuse": FIELD_RAISE_REFUSED}.get(decision)
    if target is None:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP if decision else errors.VAL_REQUIRED,
            message_key="work.raise.decision_unknown",
            params={"decision": decision or "—", "allowed": "accept, refuse"},
        )
    if row.status == target:
        return _answer(row, duplicate=True)
    if row.status != FIELD_RAISE_PENDING:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-FLD-00023",
            message_key="work.raise.already_decided",
            params={"status": row.status},
        )
    reason = str(data.get("reason") or "").strip() or None
    if target == FIELD_RAISE_REFUSED and reason is None:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="work.raise.refuse_reason_required"
        )
    from apps.work import dispatch

    with transaction.atomic():
        row.status = target
        row.decided_by_id = _actor_id(actor)
        row.decided_at = timezone.now()
        row.decision_reason = reason
        row.save(update_fields=["status", "decided_by", "decided_at", "decision_reason"])
        core_audit.write_row(
            action=f"work.order.field_raise_{'accepted' if target == FIELD_RAISE_ACCEPTED else 'refused'}",
            entity_type="work_order",
            entity_id=row.work_order_id,
            actor_user_id=_actor_id(actor),
            before={"status": FIELD_RAISE_PENDING},
            after={"status": target, "reason": reason, "br_ref": "BR-FLD-00023"},
        )
        if target == FIELD_RAISE_REFUSED:
            dispatch.set_dispatch_state(
                actor,
                row.work_order_id,
                metering_seam.dispatch_tokens().CANCELLED,
                "work.order.cancel",
            )
    return _answer(row)
