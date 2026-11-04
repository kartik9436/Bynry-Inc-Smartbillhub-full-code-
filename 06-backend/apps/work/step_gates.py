# ── Trace ──────────────────────────────────────────────
# Change:   FB-028 (DEF-FLD-10803) — the office is told when a raised job's
#           reconnect or disconnect step stops on the phone.
# Rules:    PO 2026-10-31 (decision log): *"above it the step stops ("Still
#           owes $X. Leave it off.") and the office is told"*; *"Each stop
#           names its reason on the phone; the office is told."* · hard rule 7
#           (every money decision writes `audit_log`) · R16 (the field app
#           reads money and never writes it) · HR-1 (own job only)
# Tests:    06-backend/tests/test_fb028_step_gates.py
# Impacts:  apps/work/api.py (`POST work/mobile/jobs/{id}/step-stopped`)
# ───────────────────────────────────────────────────────
"""A step that stopped on the phone, told to the office.

The phone decides the stop itself, from the money read it has just made
(`money.money_read`, fresh) and the job's gate facts
(`money_flow_facts.field_gate`) — the same rule on the same figures, so the
server does not re-decide it here. What this door does is the two things a
phone cannot: write the record (`work.order.step_stopped`, one `audit_log`
row naming the reason and the figure the phone saw) and tell the office.

⚠ **THE OFFICE NOTICE IS THE EXISTING *BLOCKED* KIND — A JUDGMENT, RECORDED.**
Notifications holds four back-office kinds (at risk, declined, blocked,
emergency unacknowledged); a stopped step means the job will not happen as it
was sent, which is what *blocked* says. A fifth kind is a notifications event,
a settings switch and eleven catalogues — the notifications module's call, not
this lane's. The reason travels in the audit row and the discriminator, so the
notice is written ONCE per job and reason (a second stop for the same reason
writes the record again and tells nobody twice).
"""

from __future__ import annotations

from typing import Any

from apps.work import money
from core import audit as core_audit
from core import errors

#: The four stops the PO named, as tokens the phone sends.
OWES_OVER_LIMIT = "owes_over_limit"
BALANCE_CLEARED = "balance_cleared"
NOTICE_OPEN = "notice_open"
PROTECTED = "protected"
STOP_REASONS: tuple[str, ...] = (OWES_OVER_LIMIT, BALANCE_CLEARED, NOTICE_OPEN, PROTECTED)

ACTION_STEP_STOPPED = "work.order.step_stopped"


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def record_stop(actor: Any, order_id: Any, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """`POST /work/mobile/jobs/{id}/step-stopped` — `{reason, owing?, limit?,
    money_as_at?, ends_on?}`. The caller's own job (404 otherwise, HR-1). An
    unknown reason is refused by name. Writes one audit row and tells the
    office once per job and reason. Reads nothing of payments (R16)."""
    from apps.work import visit_notices

    data = dict(body or {})
    order = money._job_for(actor, order_id)
    reason = str(data.get("reason") or "").strip().lower()
    if reason not in STOP_REASONS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP if reason else errors.VAL_REQUIRED,
            message_key="work.mobile.step_stop_reason_unknown",
            params={"reason": reason or "—", "allowed": ", ".join(STOP_REASONS)},
        )
    seen = {
        k: (None if data.get(k) in (None, "") else str(data.get(k)))
        for k in ("owing", "limit", "money_as_at", "ends_on")
    }
    core_audit.write_row(
        action=ACTION_STEP_STOPPED,
        entity_type="work_order",
        entity_id=order.id,
        actor_user_id=_actor_id(actor),
        before=None,
        after={"order_no": order.order_no, "reason": reason, **seen, "br_ref": "FB-028"},
    )
    told = visit_notices.tell_office(order, "blocked", discriminator=f"step_stopped:{reason}")
    return {
        "order_id": str(order.id),
        "order_no": order.order_no,
        "reason": reason,
        "recorded": True,
        "office_told": told is not None,
    }
