# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 Phase 13, lane S-ORDER — task T-39 (a contractor
#           claims unassigned work, within the tenant) and the FF-58 hand-back
#           (`07-endpoints.md` N15, N20).
# Rules:    BR-FLD-00027 (R27 — contractors may claim unassigned nearby work) ·
#           BR-WRK-029 SUPERSEDED 2026-09-23 (the skill match ADVISES and never
#           blocks) · BR-FLD-00106 (R106 — handing back returns the job to
#           Queued, unassigned, with the technician's name and reason; no eighth
#           dispatch state) · BR-FLD-00107 (R107 — an emergency cannot be
#           handed back from the app) · BR-FLD-00023 (R23 — SUPERSEDED
#           2026-10-31 by FB-028; no claim refusal remains) · BR-WRK-023/025 (seven
#           dispatch states; assignment is an append-only history) · hard
#           rules 1, 7
# Tests:    06-backend/tests/test_cr187_order_claim.py ·
#           06-backend/tests/test_cr187_order_handback.py
# Impacts:  apps/work/field_orders_api.py (two routes) · work_order_assignments rows
# ───────────────────────────────────────────────────────
"""Two dispatch acts a technician makes on their own: TAKE a job, GIVE one back.

Both write the SAME append-only history the dispatcher writes
(`dispatch.append_act`, `BR-WRK-025`) — a claim is an `assign` row, a hand-back
is an `unassign` row — so the board, the Audit tab, the change feed's
tombstone (`mobile.changes` already emits `removed` for an `unassign`) and the
first-time-fix figures all read them with no new vocabulary. **No eighth
dispatch state, and no sixth `act` token** (R106; `ck_work_order_assignments_
act` holds five and is untouched). Who did it is the row's `actor` and
`technician`; why is its `reason`.

THE CLAIM (T-39, R27, E2E-19)
------------------------------
Any technician of the tenant — employee or contractor — may take an order
that NOBODY holds: open (`planned`), on the run (`queued`), no technician and
no crew. The row is LOCKED for the check, so two people pressing *Claim* at
once get one assignment and one `work.claim.already_taken`. The claim is also
the technician's acceptance (*I'll take it* is what claiming says), so
`accepted_at_technician` is stamped with it.

⚠ **THE SKILL MATCH ADVISES AND NEVER BLOCKS — AND THAT IS A NAMED COLLISION.**
E2E-19 reads *"within their skills"* and T-39 repeats it; the signed
`BR-WRK-029` was SUPERSEDED on 2026-09-23 by PO ruling 2 — *"a guideline, never
a block"* — and the office's assignment has refused nobody for a skill since
`2.500.0`. The signed rule stands until the Product Owner rules otherwise
(`US-FLD-023` §8 names the question; it is unruled). So a claim outside the
person's skills SUCCEEDS, the answer carries the advice, and the override is
recorded exactly as an office override is — `work.order.assigned_against_
advice`, written by `dispatch._audit_against_advice`, the one writer.
`test_cr187_order_claim.py` asserts the claim succeeds AND the audit row
exists, so a ruling that flips this goes red in one named place.

⚠ **A FIELD-RAISED ORDER IS NO LONGER REFUSED HERE (FB-028, 2026-10-31).**
Until then a raise still *pending* the office was refused
`work.claim.pending_office`, which is what kept R23 true. The PO superseded
R23: a raised order is assigned to its raiser in the raise itself
(`field_raise._assign_to_raiser`), so it is never unassigned-and-pending, and a
raise the office later hands back to the run is ordinary open work.

THE HAND-BACK (FF-58, R106, R107)
---------------------------------
The job goes back to *Queued*, unassigned, carrying the name (the row's
`technician`) and the reason. It differs from `decline` (which keeps the job
with the technician until dispatch moves it): this MOVES it. The technician's
own acceptance and decline stamps are cleared, because the next person
assigned starts fresh. The office is told with the existing *declined* notice
(`visit_notices.tell_office`, ruling 3's three kinds) — the closest of the
three in meaning; a kind of its own is the notifications module's call.

⚠ **WHAT MAKES A JOB AN EMERGENCY IS NOT A STORED FACT, SO IT IS DERIVED — AND
THE DERIVATION FAILS CLOSED.** No column says *emergency*. FF-43 draws an
emergency as *EMERGENCY · P1* — the top of the priority list. So: an order
whose priority is the tenant's MOST URGENT active priority (lowest `rank`) is
an emergency for R107. On the seeded list that is *Urgent* (4 h — gas leak,
odour, no water, outage). Wrong in the safe direction: a job that is not
really an emergency is refused a hand-back and the technician rings dispatch,
which is R107's own remedy. Reported for the decision log.
"""

from __future__ import annotations

from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.work import dispatch, mobile
from apps.work import models as work_models
from apps.work.seams import metering_seam
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def _name(technician: Any) -> str | None:
    user = getattr(technician, "user", None)
    return (getattr(user, "full_name", None) or None) if user is not None else None


def is_emergency(order: Any) -> bool:
    """R107 — see the header: the tenant's most urgent active priority."""
    if not getattr(order, "priority_id", None):
        return False
    # `work_priorities` is Work's own table, read here directly.
    top = (
        work_models.WorkPriority.objects.filter(tenant_id=_tenant_id(), active=True)
        .order_by("rank")
        .values_list("id", flat=True)
        .first()
    )
    return top is not None and str(top) == str(order.priority_id)


# ── the claim ─────────────────────────────────────────────────────────────
def claim(actor: Any, order_id: Any) -> dict[str, Any]:
    """`POST /work/mobile/jobs/{id}/claim` — take an unassigned job (R27).

    Refusals, each by name: not a technician / another tenant's job / no such
    job → 404 (HR-1); held by somebody → `work.claim.already_taken`; not open
    or not on the run → `work.claim.not_open`. Online only (`AD-04`): there is no
    outbox kind for it, because a claim made offline is a claim two people can
    both believe they made.
    """
    technician = mobile.technician_of(actor)
    if technician is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    tokens = metering_seam.work_order_state_tokens()
    queued = metering_seam.dispatch_tokens().QUEUED
    with transaction.atomic():
        order = metering_seam.work_order_row_for_update(order_id)
        if order is None:
            raise errors.deny_as_not_found("BR-TEN-003")
        if order.assignee_technician_id or order.assignee_crew_id:
            if order.assignee_technician_id == technician.id:
                # Already theirs — a replayed tap, answered, not refused.
                return _claim_answer(order, technician, None, already=True)
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-FLD-00027",
                message_key="work.claim.already_taken",
                params={"order_no": order.order_no or ""},
            )
        # Open = planned or in progress (a job handed back mid-visit is still
        # open work); blocked, completed and cancelled are not claimable.
        if (
            order.state not in (tokens.PLANNED, tokens.IN_PROGRESS)
            or order.dispatch_state != queued
        ):
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-FLD-00027",
                message_key="work.claim.not_open",
                params={"order_no": order.order_no or "", "dispatch_state": order.dispatch_state},
            )
        row = dispatch.append_act(actor, order, "assign", technician=technician, reason="claimed")
        order.accepted_by_technician_id = technician.id
        order.accepted_at_technician = timezone.now()
        order.declined_at = None
        order.declined_reason = None
        metering_seam.save_order_fields(
            order,
            ["accepted_by_technician", "accepted_at_technician", "declined_at", "declined_reason"],
        )
        core_audit.write_row(
            action="work.order.claimed",
            entity_type="work_order",
            entity_id=order.id,
            actor_user_id=_actor_id(actor),
            before={"dispatch_state": queued, "technician": None},
            after={
                "order_no": order.order_no,
                "dispatch_state": order.dispatch_state,
                "technician": _name(technician),
                "crew": getattr(technician.crew, "name", None) if technician.crew_id else None,
                "assignment_id": str(row.id),
                "br_ref": "BR-FLD-00027",
            },
        )
        # BR-WRK-029 SUPERSEDED: advice, recorded when overridden, never a refusal.
        against = dispatch._audit_against_advice(actor, order, row, technician, None)
    return _claim_answer(order, technician, against)


def _claim_answer(
    order: Any, technician: Any, against: Any, *, already: bool = False
) -> dict[str, Any]:
    from apps.work import advice

    skill_id = order.template.skill_id if order.template_id else None
    seen = advice.advice_for(technician=technician, skill_id=skill_id, on=advice.order_day(order))
    return {
        "order_id": str(order.id),
        "order_no": order.order_no,
        "dispatch_state": order.dispatch_state,
        "technician": {"id": str(technician.id), "name": _name(technician)},
        "already_yours": already,
        # The advice, ALWAYS present: `has_skill: false` is a claim the skill
        # match argued against and the claim stands (BR-WRK-029 superseded).
        "advice": {
            "skill": seen["skill"],
            "has_skill": seen["has_skill"],
            "certifications_lapsed": seen["certifications_lapsed"],
        },
        "against_advice": against,
    }


# ── the hand-back ─────────────────────────────────────────────────────────
def hand_back(actor: Any, order_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work/mobile/jobs/{id}/hand-back` — `{reason, note?, key?}` (FF-58).

    The caller's OWN job (404 otherwise). Refused: no reason
    (`work.handback.reason_required`); finished or cancelled
    (`work.mobile.job_finished`); an emergency
    (`work.handback.emergency_needs_a_call`, R107). Writes an `unassign` row
    naming the technician and the reason, moves the job to Queued and clears
    the assignee (R106), audits `work.order.handed_back`, and tells the office.

    ⚠ **IDEMPOTENT ON `key` (`CR-187-BRC10`, lane S-GAPS; `07-endpoints.md` §0
    rule 7).** The handset sends the outbox item's key, stored on the
    `unassign` row this writes (`work/0047`). A resend after a lost answer
    used to meet a job that was no longer the technician's and get a 404 —
    shown on FF-50 as a failure over a hand-back that had worked. Now the key
    is looked up FIRST, before the ownership check that the first send itself
    made false, and the first answer comes back with `duplicate: true`. The
    key must be this technician's hand-back of THIS job; anything else is the
    not-found (HR-1).
    """
    data = payload or {}
    key = str(data.get("key") or "").strip() or None
    if key is not None:
        seen = mobile.assignment_by_key(key)
        if seen is not None:
            return _hand_back_duplicate(actor, order_id, seen)
    order = mobile._own_job_or_404(actor, order_id)
    technician = mobile.technician_of(actor)
    mobile._refuse_if_finished(order)
    reason = str(data.get("reason") or "").strip()
    if not reason:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, br_ref="BR-FLD-00106", message_key="work.handback.reason_required"
        )
    if is_emergency(order):
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-FLD-00107",
            message_key="work.handback.emergency_needs_a_call",
            params={"order_no": order.order_no or ""},
        )
    note = str(data.get("note") or "").strip() or None
    said = reason if note is None else f"{reason} — {note}"
    before = {"dispatch_state": order.dispatch_state, "technician": _name(technician)}
    try:
        row = _hand_back_rows(actor, order, technician, said, before, key)
    except IntegrityError:
        # The lost race on `uq_work_order_assignments_key`: the other send
        # wrote it, and the `atomic()` took this one's rows with it (law 14).
        seen = mobile.assignment_by_key(key) if key is not None else None
        if seen is None:
            raise
        return _hand_back_duplicate(actor, order_id, seen)
    from apps.work import visit_notices

    visit_notices.tell_office(order, "declined", discriminator=str(row.id))
    return {
        "order_id": str(order.id),
        "order_no": order.order_no,
        "dispatch_state": order.dispatch_state,
        "assigned": False,
        "handed_back_by": {"id": str(technician.id), "name": _name(technician)},
        "reason": said,
        "at": row.at.isoformat(),
        "duplicate": False,
    }


def _hand_back_duplicate(actor: Any, order_id: Any, seen: Any) -> dict[str, Any]:
    """The first hand-back's answer again, `duplicate: true` — only for this
    technician's own `unassign` of this job; otherwise the not-found."""
    technician = mobile.technician_of(actor)
    if (
        technician is None
        or seen.act != "unassign"
        or str(seen.work_order_id) != str(order_id)
        or str(seen.technician_id) != str(technician.id)
    ):
        raise errors.deny_as_not_found("BR-TEN-003")
    order = metering_seam.work_order_row(order_id)
    return {
        "order_id": str(order_id),
        "order_no": getattr(order, "order_no", None),
        "dispatch_state": getattr(order, "dispatch_state", None),
        "assigned": bool(order is not None and order.assignee_technician_id),
        "handed_back_by": {"id": str(technician.id), "name": _name(technician)},
        "reason": seen.reason,
        "at": seen.at.isoformat() if seen.at else None,
        "duplicate": True,
    }


def _hand_back_rows(
    actor: Any, order: Any, technician: Any, said: str, before: dict[str, Any], key: str | None
) -> Any:
    """The `unassign` row, the cleared acceptance and the audit row — one
    transaction, so a refused key leaves none of them behind."""
    with transaction.atomic():
        row = dispatch.append_act(
            actor, order, "unassign", technician=technician, reason=said, key=key
        )
        order.accepted_by_technician_id = None
        order.accepted_at_technician = None
        order.declined_at = None
        order.declined_reason = None
        metering_seam.save_order_fields(
            order,
            ["accepted_by_technician", "accepted_at_technician", "declined_at", "declined_reason"],
        )
        core_audit.write_row(
            action="work.order.handed_back",
            entity_type="work_order",
            entity_id=order.id,
            actor_user_id=_actor_id(actor),
            before=before,
            after={
                "order_no": order.order_no,
                "dispatch_state": order.dispatch_state,
                "handed_back_by": _name(technician),
                "reason": said,
                "assignment_id": str(row.id),
                "br_ref": "BR-FLD-00106",
            },
        )
    return row
