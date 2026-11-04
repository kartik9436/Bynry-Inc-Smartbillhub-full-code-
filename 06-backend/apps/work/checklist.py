# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-033 (the six-tab detail; the Checklist tab) · US-WRK-032
#           (what it reads is the order's own copy) · US-WRK-043 (safety
#           blocks the task list — on the phone AND the server).
#           Screens: Work-008, Work-011
# Rules:    BR-WRK-037 (the safety lock; *two of three ticked is locked, not
#           two-thirds unlocked*) · BR-WRK-008 (everything here is the order's
#           copy) · CLAUDE.md hard rule 1 (tenant scope) · 7 (audit_log) ·
#           B14 rule 33 (a refusal caps at five or six words)
# Tests:    06-backend/tests/test_us_wrk_033_checklist.py (TC-1..TC-7) ·
#           06-backend/tests/test_us_wrk_032_copies_pg.py (RLS, PostgreSQL)
# Impacts:  apps/work/api.py (#71, #72, #73, #75) · wave J's phone call, which
#           reads THIS function rather than repeating the condition ·
#           apps/work/sync.py, whose `_apply_material` now calls #75's service
#           rather than being a second writer of `used_qty`
# ───────────────────────────────────────────────────────
"""**The one lock**, read by the staff screen and by the phone — `BR-WRK-037`.

THE RULE, VERBATIM
------------------
*"**Safety checks block the task list on the phone AND the server refuses a
completion carrying an unticked mandatory safety row, naming the row.** Two of
three ticked is locked, not two-thirds unlocked."*

WHY ONE FUNCTION AND NOT TWO
----------------------------
`Work-008` is a desktop screen a supervisor uses and `Work-011` is a phone
screen a technician uses, and the temptation is to give each its own check
because each renders its own list. **That is how the two surfaces come to
disagree about whether a job may proceed** — one gets a fix, the other does not,
and a technician is allowed to start work the office believes is blocked. So
`safety_lock()` is the single evaluator, `tick_task` refuses through it, and
wave J's phone call reads it rather than restating the condition.

⚠ **AND THE LOCK IS THE SERVER'S, NOT THE SCREEN'S.** A greyed-out control is a
courtesy; `POST /work-orders/{id}/tasks/{tid}/tick` refuses on its own, so the
rule holds for a replayed request, a sync batch that arrived out of order, and
anything the phone does while offline and hopeful. Hard-won law 1: a disabled
button claiming a guarantee is not the guarantee.

⚠ **TWO OF THREE IS LOCKED.** The rule says so in its own words because the
plausible bug is a proportion — *most of the safety list is done, let them get
on* — and a partially-completed safety list is exactly the state in which
somebody gets hurt. `remaining` is the count and `locked` is `remaining > 0`;
there is no threshold anywhere in this file.

⚠ **ONLY *MANDATORY* ROWS LOCK.** A template may carry an advisory safety line;
`is_mandatory` is what the copy brought across and what this reads. A list with
no mandatory rows at all does not lock — which is a template's choice, made when
somebody wrote it, not a hole in this function.

THE REFUSAL SENTENCE
--------------------
B14 rule 33 caps a refusal at five or six words. It is *"Finish safety first."*
— three — and the row that is still outstanding is carried in `params` so the
screen can name it beside the sentence rather than inside it. `BR-WRK-037` says
the server names the row; naming it in a longer sentence would break rule 33,
and naming it nowhere would break the rule the sentence serves.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.work import models
from apps.work.evidence import unable_reason_label
from apps.work.seams import metering_seam
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _order_or_404(order_id: Any) -> Any:
    """The order, scoped to this tenant, or a 404.

    ⚠ **A 404 AND NEVER A 403** (HR-1: existence must not leak). `US-WRK-032`
    TC-5 and `US-WRK-033` TC-6 both assert that Lone Star Ridge reading a Brazos
    Bend order gets `404` — a 403 would confirm the order exists, which is the
    one thing a stranger must not learn from a refusal.

    Read through the seam because `work_orders` is metering's table
    (`BR-WRK-002`, G78).
    """
    from apps.work.seams import metering_seam

    row = metering_seam.work_order(order_id)
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def safety_lock(order_id: Any, *, tenant_id: Any = None) -> dict[str, Any]:
    """**THE condition** — is this order's task list locked, and by what.

    Returns `locked`, `remaining` (how many mandatory safety rows are still
    unticked), `first_outstanding` (the row a screen names beside the refusal),
    `ticked` and `total`.

    Callers: the checklist read, `tick_task` below, and wave J's phone call.
    Nobody restates the condition — see the module docstring for why that
    matters more than it looks.
    """
    tenant_id = tenant_id or _tenant_id()
    rows = list(
        models.WorkOrderSafety.objects.filter(
            tenant_id=tenant_id, work_order_id=order_id
        ).order_by("seq")
    )
    mandatory = [row for row in rows if row.is_mandatory]
    outstanding = [row for row in mandatory if row.ticked_at is None]
    return {
        # `remaining > 0`, never a proportion — BR-WRK-037's own sentence.
        "locked": bool(outstanding),
        "remaining": len(outstanding),
        "first_outstanding": outstanding[0].text if outstanding else None,
        "ticked": len([row for row in rows if row.ticked_at is not None]),
        "total": len(rows),
        "mandatory_total": len(mandatory),
    }


def _actor_name(user: Any) -> str | None:
    """A person as a clerk reads them — full name, else email; never an id."""
    if user is None:
        return None
    return (getattr(user, "full_name", "") or getattr(user, "email", "") or "").strip() or None


def checklist(order_id: Any) -> dict[str, Any]:
    """`GET /work-orders/{id}/checklist` — the order's six copy collections.

    Everything here is the ORDER's copy (`BR-WRK-008`). Nothing in this function
    reads a `wot_*` row, and that is not an accident to be optimised away by a
    later lane adding a helpful join: the moment this read walks to the template,
    publishing v2 changes what a completed job says it involved.
    """
    order = _order_or_404(order_id)
    tenant_id = _tenant_id()
    order_id = order["id"]
    lock = safety_lock(order_id, tenant_id=tenant_id)

    def _rows(model: Any) -> list[Any]:
        qs = model.objects.filter(tenant_id=tenant_id, work_order_id=order_id)
        if any(f.name == "ticked_by" for f in model._meta.get_fields()):
            qs = qs.select_related("ticked_by")
        return list(qs.order_by("seq"))

    tasks = _rows(models.WorkOrderTask)
    reading_rows = _rows(models.WorkOrderReading)
    # `DEF-MET-10609` — one read of the can't-read list, only when a reading
    # names a reason (Work reads metering's list through its seam).
    reasons = (
        metering_seam.cant_read_reason_index()
        if any(r.unable_to_read and r.unable_reason for r in reading_rows)
        else {}
    )
    detail = models.WorkOrderDetail.objects.filter(
        tenant_id=tenant_id, work_order_id=order_id
    ).first()
    return {
        "order_id": str(order_id),
        # B14 rule 31 — the VISIBLE reference is the human one, never a uuid.
        "order_no": order.get("order_no"),
        "template_id": str(order["template_id"]) if order.get("template_id") else None,
        "template_version": order.get("template_version"),
        "safety": [
            {
                "id": str(row.id),
                "seq": row.seq,
                "text": row.text,
                "is_mandatory": row.is_mandatory,
                "ticked_at": row.ticked_at.isoformat() if row.ticked_at else None,
                "ticked_by": str(row.ticked_by_id) if row.ticked_by_id else None,
                # CR-168-BRC10 round 2 (lane ORDER-PAGE, appended to §7.3): the
                # NAME of whoever ticked the line on the phone, for the
                # completed job's record (image 06, *✓ D. Ortiz · 9:41*).
                # `ticked_by` is an id and is never drawn (B14 rule 31).
                "ticked_by_name": _actor_name(row.ticked_by) if row.ticked_by_id else None,
            }
            for row in _rows(models.WorkOrderSafety)
        ],
        "safety_lock": lock,
        "tasks": [
            {
                "id": str(row.id),
                "seq": row.seq,
                "title": row.title,
                # PO answer (3) of 2026-10-04 — the instruction the template
                # gave this task, as COPIED onto the job (`BR-WRK-008`).
                "instruction": row.instruction or None,
                # CR-187-BRC10 T-35 — the step's money bar (NULL = no money
                # check) and charge code, as copied onto the job.
                "money_fresh_minutes": row.money_fresh_minutes,
                "money_charge_code": row.money_charge_code or None,
                "money_unverified": row.money_unverified,
                "est_minutes": row.est_minutes,
                "photo_required": row.photo_required,
                "is_mandatory": row.is_mandatory,
                "ticked_at": row.ticked_at.isoformat() if row.ticked_at else None,
                "ticked_by": str(row.ticked_by_id) if row.ticked_by_id else None,
                # CR-168-BRC10 round 2 (lane ORDER-PAGE, appended to §7.3): the
                # NAME of whoever ticked the line on the phone, for the
                # completed job's record (image 06, *✓ D. Ortiz · 9:41*).
                # `ticked_by` is an id and is never drawn (B14 rule 31).
                "ticked_by_name": _actor_name(row.ticked_by) if row.ticked_by_id else None,
                "photo_attachment_id": (
                    str(row.photo_attachment_id) if row.photo_attachment_id else None
                ),
            }
            for row in tasks
        ],
        # `Work-008`'s *TASKS — 7 STEPS · 45 MIN ESTIMATED* header, and the
        # *3 of 7* the acceptance names. Counted server-side because a count
        # built in the front end is a plural nobody can translate.
        "tasks_total": len(tasks),
        "tasks_ticked": len([row for row in tasks if row.ticked_at is not None]),
        "tasks_est_minutes": sum(row.est_minutes or 0 for row in tasks),
        "readings": [
            {
                "id": str(row.id),
                "seq": row.seq,
                "prompt": row.prompt,
                # Hard rule 3 — the unit travels with the number, always.
                "unit_of_measure": row.unit_of_measure,
                "min_value": str(row.min_value) if row.min_value is not None else None,
                "max_value": str(row.max_value) if row.max_value is not None else None,
                "required": row.required,
                "photo_required": row.photo_required,
                "posts_as_meter_read": row.posts_as_meter_read,
                "value": str(row.value) if row.value is not None else None,
                # `CR-168-BRC10` P1.33 — a reading that is words.
                "kind": row.kind,
                "value_text": row.value_text,
                # `DEF-WRK-10601` — *Unable to read*, with the phone's words.
                "unable_to_read": row.unable_to_read,
                "unable_reason": row.unable_reason,
                # `DEF-MET-10609` — *Unable to read · Dog*: the reason's name
                # from the one can't-read list, and the technician's note.
                "unable_reason_name": unable_reason_label(row.unable_reason, reasons),
                "unable_note": row.unable_note,
                "captured_at": row.captured_at.isoformat() if row.captured_at else None,
                # The Thumbnail cell arrives in wave K — a dash until then.
                "photo_attachment_id": (
                    str(row.photo_attachment_id) if row.photo_attachment_id else None
                ),
                "in_range": row.in_range,
            }
            for row in reading_rows
        ],
        "materials": [
            {
                "id": str(row.id),
                "part_id": str(row.part_id),
                "part_no": row.part.part_no,
                "part_name": row.part.name,
                "planned_qty": str(row.planned_qty),
                "used_qty": str(row.used_qty) if row.used_qty is not None else None,
                "unit_of_measure": row.unit_of_measure,
                "unplanned": row.unplanned,
            }
            for row in models.WorkOrderMaterial.objects.filter(
                tenant_id=tenant_id, work_order_id=order_id
            )
            .select_related("part")
            .order_by("part__part_no")
        ],
        "help": [
            {
                "id": str(row.id),
                "seq": row.seq,
                "kind": row.kind,
                "label": row.label,
                "ref": row.ref,
            }
            for row in _rows(models.WorkOrderHelp)
        ],
        "details": (
            {
                "access_notes": detail.access_notes,
                "hazards": detail.hazards,
                "gate_code": detail.gate_code,
                "show_account_summary": detail.show_account_summary,
                "show_asset_card": detail.show_asset_card,
                "show_access_notes": detail.show_access_notes,
                "show_appointment": detail.show_appointment,
                # FB-023 F4 — the phone hides the balance card and payment
                # facts when off; FB-013's stop still reads the balance.
                "show_balance_payments": detail.show_balance_payments,
                # FB-028 (PO 2026-10-31) — the job's copy of its template's
                # Reconnect limit, 4 places; the phone gates a raised
                # reconnect's step on it (null = no limit set).
                "reconnect_limit": (
                    None if detail.reconnect_limit is None else f"{detail.reconnect_limit:.4f}"
                ),
            }
            if detail is not None
            else None
        ),
    }


def _tick_row(actor: Any, model: Any, order_id: Any, row_id: Any, tenant_id: Any) -> Any:
    row = model.objects.filter(
        tenant_id=tenant_id, work_order_id=order_id, pk=row_id
    ).first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    if row.ticked_at is None:
        row.ticked_at = timezone.now()
        row.ticked_by_id = getattr(actor, "id", None) or getattr(actor, "pk", None)
        row.save(update_fields=["ticked_at", "ticked_by", "updated_at"])
    return row


def tick_safety(actor: Any, order_id: Any, safety_id: Any) -> dict[str, Any]:
    """`POST /work-orders/{id}/safety/{sid}/tick` — never refused by the lock.

    A safety row is what LIFTS the lock, so nothing here consults it. Ticking an
    already-ticked row is a no-op that returns the same state rather than an
    error: the phone replays a sync batch, and a replay must not become a
    failure a technician has to understand while standing in a basement.
    """
    order = _order_or_404(order_id)
    tenant_id = _tenant_id()
    with transaction.atomic():
        row = _tick_row(actor, models.WorkOrderSafety, order["id"], safety_id, tenant_id)
        lock = safety_lock(order["id"], tenant_id=tenant_id)
        core_audit.write_row(
            action="work_order.safety_ticked",
            entity_type="work_order",
            entity_id=order["id"],
            actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
            after={"safety_seq": row.seq, "text": row.text, "remaining": lock["remaining"]},
        )
    return {"id": str(row.id), "ticked_at": row.ticked_at.isoformat(), "safety_lock": lock}


def tick_task(actor: Any, order_id: Any, task_id: Any) -> dict[str, Any]:
    """`POST /work-orders/{id}/tasks/{tid}/tick` — **refused while the lock
    holds** (`BR-WRK-037`).

    The refusal is `BIZ_LOCKED` → 409, which is what a state that will change
    on its own deserves: nothing is wrong with the request, the job is simply
    not ready for it yet.
    """
    order = _order_or_404(order_id)
    tenant_id = _tenant_id()
    lock = safety_lock(order["id"], tenant_id=tenant_id)
    if lock["locked"]:
        raise errors.BizError(
            errors.BIZ_LOCKED,
            br_ref="BR-WRK-037",
            # Three words. B14 rule 33 caps a refusal at five or six, so the
            # outstanding row is named in `params` and rendered beside the
            # sentence rather than swallowed into it.
            message_key="work.order.finish_safety_first",
            params={"safety": lock["first_outstanding"], "remaining": lock["remaining"]},
        )
    with transaction.atomic():
        row = _tick_row(actor, models.WorkOrderTask, order["id"], task_id, tenant_id)
        core_audit.write_row(
            action="work_order.task_ticked",
            entity_type="work_order",
            entity_id=order["id"],
            actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
            after={"task_seq": row.seq, "title": row.title},
        )
    ticked = models.WorkOrderTask.objects.filter(
        tenant_id=tenant_id, work_order_id=order["id"], ticked_at__isnull=False
    ).count()
    total = models.WorkOrderTask.objects.filter(
        tenant_id=tenant_id, work_order_id=order["id"]
    ).count()
    return {
        "id": str(row.id),
        "ticked_at": row.ticked_at.isoformat(),
        # `Work-008`'s *3 of 7*, counted here — see `checklist` above.
        "tasks_ticked": ticked,
        "tasks_total": total,
    }


def set_material_used(
    actor: Any, order_id: Any, material_id: Any, payload: dict[str, Any]
) -> dict[str, Any]:
    """`PUT /work-orders/{id}/materials/{mid}/used` — used-of-planned, who, when.

    **`07-endpoints.md` §6 #75, and it is the route wave `N` left unwritten.**
    Wave `N`'s own stamp said so in as many words — *"wave `H`'s table landed
    mid-build and the route was not written"* — which is an OMISSION and not an
    open question: `work_order_materials` exists (`work/0012`), `costing.py`
    already reads `used_qty`, and the phone has been writing that one column
    since wave `L`.

    ⚠ **THIS IS NOW THE ONLY WRITER OF `used_qty`, AND THAT IS THE POINT.**
    `sync._apply_material` implemented these same semantics inline while this
    route did not exist, and said in its own docstring: *"When
    `PUT /work-orders/{id}/materials/{mid}/used` lands, this should call it
    rather than keep a second writer — two writers for one column is how a rule
    gets forgotten in one of them."* It now calls this. The rule that was
    already forgotten in one of them is the next paragraph.

    ⚠ **WHO AND WHEN, WHICH THE PHONE'S WRITER NEVER RECORDED.** `N1` asks this
    route for *"used-of-planned, who, when"* and `work_order_materials` carries
    `issued_by` and `issued_at` for exactly that; `_apply_material` set neither,
    so every part a technician reported through the phone landed with the
    quantity and no attribution, and `Work-008`'s Parts tab had nothing to show
    beside it. Both doors stamp it now because there is only one door left.

    ⚠ **`used_qty` IS NULLABLE AND NULL IS NOT ZERO — the distinction is
    `costing.py`'s and this route must not blur it.** NULL means *nobody has
    said*; `0` means *asked for and not used*, which is a real outcome a
    supervisor reads on the screen (`US-WRK-050` TC-2) and which contributes no
    cost line rather than a `$0.00` one. So a missing `used_qty` is REFUSED
    rather than defaulted — a route that defaulted it to zero would silently
    convert *unreported* into *reported as unused*.

    ⚠ **NO ON-HAND COUNT MOVES, AND THAT IS RULED RATHER THAN MISSING** —
    `OQ-WRK-1490`, closed 2026-09-04 to option (a): *"stock control is an
    inventory system"*. This function deducts nothing from anywhere because
    there is nowhere to deduct from, and there is not meant to be.

    ⚠ **A NEGATIVE QUANTITY IS REFUSED, AND WITH NO NEW SENTENCE.** The column
    has no CHECK and a negative would reach `costing.py` as a negative cost line
    on a report that is frozen at acceptance — money that cannot be corrected in
    place (hard rule 4). The refusal carries no `message_key`, so it resolves
    through `errors.val-003` — *"That value is out of range."* — which already
    exists in all eleven catalogues; inventing a twelfth sentence for it would
    be prose this lane was not asked for.
    """
    order = _order_or_404(order_id)
    tenant_id = _tenant_id()
    row = models.WorkOrderMaterial.objects.filter(
        tenant_id=tenant_id, work_order_id=order["id"], id=material_id
    ).first()
    if row is None:
        # HR-1 — a row of another tenant's job and a row that does not exist get
        # the SAME answer, or existence leaks through the difference.
        raise errors.deny_as_not_found("BR-TEN-003")
    if "used_qty" not in payload:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="work.material.used_qty_required",
            br_ref="BR-WRK-049",
        )
    try:
        used = Decimal(str(payload["used_qty"]))
    except (InvalidOperation, TypeError, ValueError):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="work.material.used_qty_not_a_number",
            params={"field": "used_qty", "value": str(payload["used_qty"])},
        ) from None
    if used < 0:
        raise errors.ValidationError(errors.VAL_RANGE, br_ref="BR-WRK-049")

    before = {"used_qty": str(row.used_qty) if row.used_qty is not None else None}
    actor_id = getattr(actor, "id", None) or getattr(actor, "pk", None)
    with transaction.atomic():
        row.used_qty = used
        row.issued_by_id = actor_id
        # WHEN IT WAS REPORTED. `BR-TEN-043`'s event-date argument does not
        # reach here: nothing in the payload carries a field time, so inventing
        # one from a client clock would be worse than stamping the one moment
        # this row is known to have happened at — the write itself.
        row.issued_at = timezone.now()
        row.save(update_fields=["used_qty", "issued_by", "issued_at", "updated_at"])
        core_audit.write_row(
            action="work.material.used",
            entity_type="work_order_material",
            entity_id=row.id,
            actor_user_id=actor_id,
            before=before,
            after={"used_qty": str(used)},
        )
    return {
        "id": str(row.id),
        "part_no": row.part.part_no,
        "planned_qty": str(row.planned_qty),
        "used_qty": str(used),
        "unit_of_measure": row.unit_of_measure,
        "issued_at": row.issued_at.isoformat(),
    }
