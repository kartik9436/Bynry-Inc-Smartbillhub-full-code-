# ── Trace ──────────────────────────────────────────────
# Change:   FB-023 F5 (decision log 2026-10-31, PO: *"A yes, disconnect jobs
#           only"*) — payment-plan status and the disconnect notice on the
#           field app's money read, for disconnect jobs and no other.
# Rules:    R18 (`money.py` keys off the step's columns and never off what a
#           job IS — `test_no_code_in_work_names_a_disconnect` holds it, so the
#           one place that DOES ask lives here, outside that file) · BR-WRK-002
#           / G78 (payments and customers read through their seams only)
#           FB-028 (decision log 2026-10-31, the two FB-028 rulings and
#           *"Field-raised disconnects go to the technician with the live
#           checks"*) — `field_gate`: what a job RAISED ON SITE needs for its
#           reconnect and disconnect steps to gate themselves on the phone.
# Tests:    06-backend/tests/test_fb023_field_money.py ·
#           06-backend/tests/test_fb028_step_gates.py
# ───────────────────────────────────────────────────────
"""What a job's REASON adds to its money read — FB-023 F5.

`money.money_read` stays ignorant of disconnects (R18): it asks this module
for the facts a job's flow adds and merges whatever comes back. Today the only
flow that adds any is a disconnect, and it adds two: whether the customer is on
a payment plan and keeping to it, and the latest disconnect notice.
"""

from __future__ import annotations

from typing import Any

from apps.work import connection_models
from apps.work.seams import customers_seam, payments_seam

#: The key on the money read. Null on every job that is not a disconnect.
KEY = "disconnect"

#: Why a job exists, as `work_orders.source` says it: the disconnect wizard's
#: cut visit, or the non-pay rule. A dispatcher's hand-raised disconnect reads
#: `dispatcher` and gets nothing — the server does not guess from a type name
#: (decision log 2026-10-31, *"FB-023 built"* item 2).
DISCONNECT_SOURCES = (connection_models.SOURCE_DISCONNECT, connection_models.SOURCE_DUNNING_AUTO)


def is_disconnect_job(order: Any) -> bool:
    return getattr(order, "source", None) in DISCONNECT_SOURCES


def empty() -> dict[str, Any]:
    """The shape every answer carries, before anything is read."""
    return {KEY: None, GATE_KEY: None}


#: FB-028 — the key the raised-on-site gate facts ride on. Null on a job the
#: office raised: the office-requested reconnect (2026-10-29 C1) is never
#: refused for owing, and that ruling is unchanged.
GATE_KEY = "field_gate"


def field_gate(order: Any, account_id: Any, *, as_of: Any) -> dict[str, Any]:
    """`{field_gate: {...}}` on a job RAISED ON SITE, `{field_gate: None}` else.

    PO 2026-10-31 — a raised reconnect is the technician's, and *"if outstanding
    balance … reduces below 25 dollors (for example) then techncinan should able
    to perform reconnect"*; a raised disconnect *"stops if the bill is paid, the
    notice period isn't over, or the account is protected"*. The phone decides
    the step from the money read it already makes (fresh, F1) plus these facts:

    * `reconnect_limit` — the job's copy of its template's limit, `{amount (4dp),
      display (2dp)}`, or None when the template carries no payment check;
    * `notice` — `{tier, issued_on, ends_on}` from customers, or None;
    * `notice_open` — True while `as_of` is on or before `ends_on`;
    * `protected` — any protection in force (medical, kept plan, moratorium).

    Which of the two steps a job IS stays the template's business (R18): the
    phone applies the reconnect facts on FF-61 and the disconnect facts on
    FF-27. READ-ONLY.
    """
    from decimal import Decimal

    from apps.work import models
    from apps.work.field_order_models import WorkFieldRaise
    from core import money as core_money
    from core import tenancy as core_tenancy

    tenant_id = core_tenancy.current_tenant_id()
    if not WorkFieldRaise.objects.filter(tenant_id=tenant_id, work_order_id=order.id).exists():
        return {GATE_KEY: None}
    detail = models.WorkOrderDetail.objects.filter(
        tenant_id=tenant_id, work_order_id=order.id
    ).first()
    limit = getattr(detail, "reconnect_limit", None)
    notice = customers_seam.disconnect_notice_period(account_id) if account_id else None
    ends_on = (notice or {}).get("ends_on")
    return {
        GATE_KEY: {
            "raised_on_site": True,
            "reconnect_limit": (
                None
                if limit is None
                else {
                    "amount": str(Decimal(limit).quantize(Decimal("0.0001"))),
                    "display": str(core_money.finalize(Decimal(limit))),
                }
            ),
            "notice": notice,
            "notice_open": bool(ends_on) and str(as_of) <= ends_on,
            "protected": customers_seam.protected_account(account_id, as_of=as_of)
            if account_id
            else False,
        }
    }


def facts_for(order: Any, account_id: Any, *, as_of: Any) -> dict[str, Any]:
    """`{disconnect: {plan, notice}}` on a disconnect job, `{disconnect: None}`
    otherwise. READ-ONLY, through the seams."""
    if account_id is None or not is_disconnect_job(order):
        return {KEY: None}
    return {
        KEY: {
            "plan": payments_seam.plan_status(account_id, as_of=as_of),
            "notice": customers_seam.latest_disconnect_notice(account_id),
        }
    }
