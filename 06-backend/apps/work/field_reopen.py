# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 Phase 13 task T-37, lane S-ORDER — reopen versus
#           follow-on: the same order reopened, or a new order linked to it,
#           with the OFFICE deciding which (FF-35, FF-36; E2E-17, E2E-18).
# Rules:    BR-FLD-00021 (R21 — a reconnect is a new work order, never a
#           reopen) · BR-FLD-00022 (R22 — a technician may reopen their own job
#           before the office accepts it; after acceptance it is a correction
#           and the office owns it) · BR-FLD-00010 (R10 — who and when) ·
#           BR-MET-110 (the office's send-back is metering's, unchanged) ·
#           BR-WRK-008 / BR-FLD-00112 (a follow-on is raised from a template and
#           takes its own copy) · hard rules 1, 4's shape (history appended,
#           never rewritten), 7
# Tests:    06-backend/tests/test_cr187_order_reopen.py
# Impacts:  apps/work/field_orders_api.py (three routes) · work_order_reopens
# ───────────────────────────────────────────────────────
"""A closed job comes back — reopened, or followed on — and both are recorded.

THE THREE DOORS, AND WHICH SIDE OWNS EACH
-----------------------------------------
1. **The technician reopens their own job** (FF-36; R22). Only while the office
   has NOT accepted it; the close is undone (state back to *in progress*, the
   job back on their list as *scheduled*, outcome and completion time cleared)
   and every reading, tick and photograph STAYS — the same undo the office's
   send-back does (`send_back_field_result`, judgment J9), now pressable by
   the person who closed it. FF-36 draws three reasons and this is the whole
   vocabulary: *Wrong outcome · Missed a step · Photo or reading missing*.
2. **The office reopens the same order** (E2E-17) — that IS metering's
   send-back, called by name through the seam, with the reopen RECORDED here
   beside it so the order's history says it came back and what it said before.
3. **The office raises a linked follow-on** (E2E-18; R21) — a NEW order,
   raised from a template on the original's own anchors, linked by a
   `follow_on` row. A reconnect is always this, never door 1 or 2.

*"Reopen and follow-on are distinguishable, and the office chooses which"* is
`work_order_reopens.kind`, read back by `history()`.

⚠ **THE OFFICE MAY REOPEN AN ACCEPTED JOB — RULED 2026-10-21.** This used to
be refused `work.reopen.after_acceptance_unruled`, naming the collision between
R22/E2E-17 (*"it is a correction and the office owns it"*) and judgment J9
(*"Nothing accepted is ever re-opened"*). PO answer 11 (decision log *"Field
app: ten PO answers"*): *"yes"*. J9 is SUPERSEDED **for the office**; a
TECHNICIAN still cannot reopen after acceptance (`work.reopen.office_owns_it`,
door 1). The refusal and its catalogue key are removed. What happens:

* it goes through metering's send-back exactly as the office's other reopen
  does, with `after_acceptance=True` — the one caller that may — which also
  clears `accepted_at`/`accepted_by` so the job can be accepted again, and
  audits `work.order.sent_back` with `after_acceptance: true`;
* the `office_reopen` history row keeps what the close AND the acceptance said
  (`prior.accepted_at`), and this module audits
  `work.order.reopened_after_acceptance` naming the report version it
  supersedes;
* **the frozen report is not touched.** The next acceptance writes the next
  version beside it, with its own cost lines
  (`services.generate_work_order_report`, `work/0045`'s `report_version`), and
  the cost section reads the latest version;
* what the first acceptance posted — meter reads, a fitted meter's install —
  stands and is not posted again (`accept_field_result`'s re-acceptance
  branch); a wrong reading is corrected through metering's read correction.

⚠ **A FOLLOW-ON IS NOT `follows_order_id` AND CARRIES NO `source`.** See
`field_order_models.py`: that column is FAILURE provenance and FIRST-TIME FIX
counts it. There is also no `source` token meaning *followed on* or *raised in
the field* — `ck_work_orders_source` holds seventeen and a new one is a
metering migration. The order is raised with `source` NULL, which the CHECK
admits, and the link lives in `work_order_reopens`. Reported as a gap.

⚠ **ONLINE ONLY FOR NOW.** A sync item for a COMPLETED order is held for review
(`mobile.order_state_reason` → `work.sync.job_already_closed`), so an offline
`reopen` outbox kind would be held rather than applied. Making it an outbox
kind is the sync lane's (`sync.py` is not this lane's file); the route here is
the act, and is idempotent on the handset's `key` so the outbox can call it.
"""

from __future__ import annotations

from typing import Any

from django.db import IntegrityError, transaction

from apps.work import mobile
from apps.work.field_order_models import (
    FOLLOW_ON,
    REOPEN_BY_OFFICE,
    REOPEN_BY_TECHNICIAN,
    WorkOrderReopen,
)
from apps.work.seams import identity_seam, metering_seam
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy

#: FF-36's three reasons — the WHOLE vocabulary of a technician's reopen.
TECHNICIAN_REASONS: tuple[str, ...] = ("wrong_outcome", "missed_step", "missing_evidence")

#: Words that make a reopen a reconnect, refused BY NAME (R21). A reconnect is
#: a new order: two visits, two days, two sets of safety checks, two labour
#: records.
RECONNECT_WORDS: tuple[str, ...] = ("reconnect", "reconnection", "restore", "restoration")

DECISION_REOPEN = "reopen"
DECISION_FOLLOW_ON = "follow_on"
DECISIONS: tuple[str, ...] = (DECISION_REOPEN, DECISION_FOLLOW_ON)


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def _prior(order: Any) -> dict[str, Any]:
    """What the close said, kept on the history row because the order's own
    columns are about to be cleared."""
    return {
        "state": order.state,
        "dispatch_state": order.dispatch_state,
        "outcome": order.outcome,
        "completed_at": order.completed_at.isoformat() if order.completed_at else None,
        "accepted_at": order.accepted_at.isoformat() if order.accepted_at else None,
    }


def _refuse_reconnect(*words: Any) -> None:
    for word in words:
        if str(word or "").strip().lower() in RECONNECT_WORDS:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-FLD-00021",
                message_key="work.reopen.reconnect_is_a_new_order",
            )


def _by_key(key: str | None) -> Any:
    if not key:
        return None
    return WorkOrderReopen.objects.filter(tenant_id=_tenant_id(), key=key).first()


def _answer(row: Any, order: Any, *, duplicate: bool = False) -> dict[str, Any]:
    follow = row.follow_on_order if row.follow_on_order_id else None
    return {
        "id": str(row.id),
        "order_id": str(order.id),
        "order_no": order.order_no,
        "kind": row.kind,
        "reason": row.reason,
        "state": order.state,
        "dispatch_state": order.dispatch_state,
        "prior": row.prior,
        "follow_on": (
            {"id": str(follow.id), "order_no": follow.order_no} if follow is not None else None
        ),
        "duplicate": duplicate,
    }


# ── door 1 · the technician (R22) ─────────────────────────────────────────
def technician_reopen(actor: Any, order_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work/mobile/jobs/{id}/reopen` — `{reason, note?, key?}` (FF-36).

    Their OWN job only (another technician's is a 404, HR-1). Refused while
    the job is not closed (`work.reopen.not_closed`) and once the office has
    accepted it (`work.reopen.office_owns_it`, R22). `reason` is one of FF-36's
    three; *reconnect* is refused by name (R21). A replay of the same `key`
    answers the first reopen with `duplicate: true` and changes nothing.
    Audited `work.order.reopened_by_technician`.
    """
    data = payload or {}
    key = str(data.get("key") or "").strip() or None
    order = mobile._own_job_or_404(actor, order_id)
    seen = _by_key(key)
    if seen is not None:
        if seen.work_order_id != order.id:
            raise errors.deny_as_not_found("BR-TEN-003")
        return _answer(seen, order, duplicate=True)
    reason = str(data.get("reason") or "").strip().lower()
    _refuse_reconnect(reason)
    if reason not in TECHNICIAN_REASONS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP if reason else errors.VAL_REQUIRED,
            br_ref="BR-FLD-00022",
            message_key="work.reopen.reason_unknown",
            params={"reason": reason or "—", "allowed": ", ".join(TECHNICIAN_REASONS)},
        )
    tokens = metering_seam.work_order_state_tokens()
    if order.accepted_at is not None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-FLD-00022",
            message_key="work.reopen.office_owns_it",
            params={"order_no": order.order_no or ""},
        )
    if order.state != tokens.COMPLETED:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-FLD-00022",
            message_key="work.reopen.not_closed",
            params={"order_no": order.order_no or "", "state": order.state},
        )
    technician = mobile.technician_of(actor)
    note = str(data.get("note") or "").strip() or None
    prior = _prior(order)
    try:
        with transaction.atomic():
            row = WorkOrderReopen.objects.create(
                tenant_id=_tenant_id(),
                work_order_id=order.id,
                kind=REOPEN_BY_TECHNICIAN,
                reason=reason,
                note=note,
                by_user_id=_actor_id(actor),
                by_technician=technician,
                prior=prior,
                key=key,
            )
            order.state = tokens.IN_PROGRESS
            # Back on the run as *Scheduled* — unless a person put it On hold,
            # which a reopen must not overrule (`dispatch._refresh_cache`'s rule).
            dispatch = metering_seam.dispatch_tokens()
            if order.dispatch_state == dispatch.COMPLETE:
                order.dispatch_state = dispatch.SCHEDULED
            order.completed_at = None
            order.outcome = None
            metering_seam.save_order_fields(
                order, ["state", "dispatch_state", "completed_at", "outcome"]
            )
            metering_seam.refresh_build_state(order)
            core_audit.write_row(
                action="work.order.reopened_by_technician",
                entity_type="work_order",
                entity_id=order.id,
                actor_user_id=_actor_id(actor),
                before=prior,
                after={
                    "state": order.state,
                    "dispatch_state": order.dispatch_state,
                    "order_no": order.order_no,
                    "reason": reason,
                    "br_ref": "BR-FLD-00022",
                },
            )
    except IntegrityError:
        # A lost race on the key: the other request wrote the reopen. The
        # savepoint rolled this one back whole (law 14).
        seen = _by_key(key)
        if seen is None:
            raise
        order = metering_seam.work_order_row(order.id)
        return _answer(seen, order, duplicate=True)
    return _answer(row, order)


# ── doors 2 and 3 · the office decides (E2E-17, E2E-18) ───────────────────
def _require_office(actor: Any) -> None:
    """The roles that may ACCEPT may also send back or follow on — the act is
    the other answer to the same question (`send_back_field_result`'s own
    rule). A field technician does not hold `work_accept` (`BR-WRK-044`)."""
    if not identity_seam.may(actor, "work_accept"):
        raise errors.AuthError(
            errors.AUTH_PERMISSION_DENIED,
            br_ref="BR-WRK-044",
            message_key="metering.work_order_accept_not_permitted",
        )


def office_decide(actor: Any, order_id: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """`POST /work-orders/{id}/come-back` — `{decision, reason, note?,
    template_id?, key?}`: the office chooses REOPEN or FOLLOW-ON.

    * `decision: "reopen"` — metering's send-back, plus an `office_reopen`
      history row with what the close said — before OR after acceptance (PO
      answer 11, 2026-10-21; see the header for what an after-acceptance
      reopen also does).
    * `decision: "follow_on"` — a NEW order from `template_id` on the
      original's anchors (premises, account, asset, unit, build, service),
      linked by a `follow_on` row; allowed before or after acceptance. A
      reconnect is ALWAYS this (R21).

    Idempotent on `key`: a replay answers the first decision and raises no
    second order.
    """
    _require_office(actor)
    data = payload or {}
    key = str(data.get("key") or "").strip() or None
    order = metering_seam.work_order_row(order_id)
    if order is None:
        raise errors.NotFoundError()
    seen = _by_key(key)
    if seen is not None:
        if seen.work_order_id != order.id:
            raise errors.NotFoundError()
        return _answer(seen, order, duplicate=True)
    decision = str(data.get("decision") or "").strip().lower()
    if decision not in DECISIONS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP if decision else errors.VAL_REQUIRED,
            br_ref="BR-FLD-00022",
            message_key="work.reopen.decision_unknown",
            params={"decision": decision or "—", "allowed": ", ".join(DECISIONS)},
        )
    reason = str(data.get("reason") or "").strip()
    if not reason:
        raise errors.ValidationError(
            errors.VAL_REQUIRED, br_ref="BR-FLD-00022", message_key="work.reopen.reason_required"
        )
    tokens = metering_seam.work_order_state_tokens()
    if order.state != tokens.COMPLETED:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-FLD-00022",
            message_key="work.reopen.not_closed",
            params={"order_no": order.order_no or "", "state": order.state},
        )
    note = str(data.get("note") or "").strip() or None
    if decision == DECISION_REOPEN:
        _refuse_reconnect(reason, data.get("need"))
        return _office_reopen(actor, order, reason, note, key)
    return _follow_on(actor, order, reason, note, key, data.get("template_id"))


def _office_reopen(
    actor: Any, order: Any, reason: str, note: str | None, key: str | None
) -> dict[str, Any]:
    after_acceptance = order.accepted_at is not None
    prior = _prior(order)
    superseded = None
    if after_acceptance:
        from apps.work.models import WorkOrderReport

        superseded = (
            WorkOrderReport.objects.filter(tenant_id=_tenant_id(), work_order_id=order.id)
            .order_by("-version")
            .values_list("version", flat=True)
            .first()
        )
    with transaction.atomic():
        row = WorkOrderReopen.objects.create(
            tenant_id=_tenant_id(),
            work_order_id=order.id,
            kind=REOPEN_BY_OFFICE,
            reason=reason,
            note=note,
            by_user_id=_actor_id(actor),
            prior=prior,
            key=key,
        )
        # metering's own door: it moves `state`, re-derives the build, writes
        # its own `work.order.sent_back` audit row (hard rule 7) — and, after
        # an acceptance (PO answer 11), clears the acceptance so the job can be
        # accepted again.
        metering_seam.send_back_field_result(
            actor, order.id, reason, after_acceptance=after_acceptance
        )
        if after_acceptance:
            core_audit.write_row(
                action="work.order.reopened_after_acceptance",
                entity_type="work_order",
                entity_id=order.id,
                actor_user_id=_actor_id(actor),
                before=prior,
                after={
                    "order_no": order.order_no,
                    "reason": reason,
                    # The frozen report this reopen supersedes; the next
                    # acceptance writes the version after it. None when the
                    # first acceptance produced no report.
                    "supersedes_report_version": superseded,
                    "br_ref": "BR-FLD-00022",
                },
            )
    order = metering_seam.work_order_row(order.id)
    return _answer(row, order)


def _follow_on(
    actor: Any, order: Any, reason: str, note: str | None, key: str | None, template_id: Any
) -> dict[str, Any]:
    if not template_id:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            br_ref="BR-FLD-00112",
            message_key="work.reopen.follow_on_template_required",
        )
    payload = {
        "template_id": str(template_id),
        "connection_id": str(order.connection_id) if order.connection_id else None,
        "premises_id": str(order.premises_id) if order.premises_id else None,
        "account_id": str(order.account_id) if order.account_id else None,
        "asset_id": str(order.asset_id) if order.asset_id else None,
        "unit_id": str(order.unit_id) if order.unit_id else None,
        "technician_notes": note,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    prior = _prior(order)
    with transaction.atomic():
        created = metering_seam.raise_work_order(actor, payload)
        row = WorkOrderReopen.objects.create(
            tenant_id=_tenant_id(),
            work_order_id=order.id,
            kind=FOLLOW_ON,
            reason=reason,
            note=note,
            by_user_id=_actor_id(actor),
            prior=prior,
            follow_on_order_id=created["id"],
            key=key,
        )
        core_audit.write_row(
            action="work.order.followed_on",
            entity_type="work_order",
            entity_id=order.id,
            actor_user_id=_actor_id(actor),
            before=None,
            after={
                "order_no": order.order_no,
                "follow_on_order_no": created.get("order_no"),
                "reason": reason,
                "br_ref": "BR-FLD-00021",
            },
        )
    return _answer(row, order)


# ── the history (both sides read it) ──────────────────────────────────────
def history(order_id: Any) -> dict[str, Any]:
    """`GET /work-orders/{id}/come-backs` — every reopen and follow-on of this
    order, oldest first, and the order it was itself followed on FROM (if any).
    `kind` is what makes reopen and follow-on distinguishable (E2E-17/18)."""
    order = metering_seam.work_order_row(order_id)
    if order is None:
        raise errors.NotFoundError()
    rows = (
        WorkOrderReopen.objects.filter(tenant_id=_tenant_id(), work_order_id=order.id)
        .select_related("follow_on_order", "by_user", "by_technician__user")
        .order_by("at", "id")
    )
    parent = (
        WorkOrderReopen.objects.filter(
            tenant_id=_tenant_id(), follow_on_order_id=order.id, kind=FOLLOW_ON
        )
        .select_related("work_order")
        .first()
    )
    return {
        "order_id": str(order.id),
        "order_no": order.order_no,
        "followed_on_from": (
            {"id": str(parent.work_order_id), "order_no": parent.work_order.order_no}
            if parent is not None
            else None
        ),
        "events": [
            {
                "id": str(r.id),
                "kind": r.kind,
                "reason": r.reason,
                "note": r.note,
                "at": r.at.isoformat(),
                "by": (getattr(r.by_user, "full_name", None) or None) if r.by_user_id else None,
                "prior": r.prior,
                "follow_on": (
                    {"id": str(r.follow_on_order_id), "order_no": r.follow_on_order.order_no}
                    if r.follow_on_order_id
                    else None
                ),
            }
            for r in rows
        ],
    }
