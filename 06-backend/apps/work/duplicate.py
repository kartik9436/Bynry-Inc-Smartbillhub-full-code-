"""`POST /work-orders/{id}/duplicate` — the same job raised again.

`CR-168-BRC10` round 8, lane FIX-8B — `DEF-WRK-9690` (beta observation #28:
*"Duplicate on orders and rules"*). P3.63 built Duplicate on a RULE and the
order half was never routed to a task.

WHAT A DUPLICATE IS, and it is our judgment (decision log *"CR-168 ROUND 8 ·
FIX-8B"*; the PO was not asked — law 13):

* **A NEW, LIVE, UNASSIGNED ORDER — not a draft.** A rule's duplicate is a
  draft because a rule acts on its own once enabled; an order does nothing
  until a dispatcher assigns it, so the queue IS its draft state.
* **The same PLACE and the same JOB:** the premises, unit, account, asset,
  service, scope, mode, job type, template and priority are copied. The
  template is re-stamped at its CURRENT published version by the one raise
  door, exactly as any new order is (`BR-WRK-008`: the copy tables freeze what
  a job involves AT ITS RAISE).
* **Not the history:** no holder, window, hold, field data, outcome, photos or
  acceptance — those are facts about the first job, not the second.
* **Never a gate, never a build's job.** A build's gate order (`is_gate`) is
  what a connection's service waits on, and a copy must not become a second
  thing to wait on, so the copy carries no connection and no gate; it stands on
  the build's premises like any other job there.
* **Raised by the office** (`source = dispatcher`, `BR-WRK-024`); the original
  order's number rides on the audit row, so *where did this come from* stays
  answerable.

It writes through metering's ONE raise door (`metering_seam.raise_work_order`)
and nowhere else, so the number, the anchor CHECK, the copy tables and the
promise (`due_at` from the priority, `BR-WRK-018`) are all the raise's own.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.work.seams import metering_seam
from core import audit as core_audit
from core import errors

#: `metering.connections.SOURCE_DISPATCHER`, by value (Work reads metering
#: through its seam, and a constant is not worth a second door).
SOURCE_DISPATCHER = "dispatcher"


def duplicate(actor: Any, order_id: Any) -> dict[str, Any]:
    order = metering_seam.work_order_row(order_id)
    if order is None:
        # Cross-tenant is indistinguishable from absent (hard rule 1).
        raise errors.NotFoundError()
    premises_id = order.premises_id
    if premises_id is None and order.connection_id is not None:
        premises_id = getattr(order.connection, "premises_id", None)
    payload = {
        "premises_id": str(premises_id) if premises_id else None,
        "account_id": str(order.account_id) if order.account_id else None,
        "asset_id": str(order.asset_id) if order.asset_id else None,
        "unit_id": str(order.unit_id) if order.unit_id else None,
        "type": order.type,
        "type_id": str(order.type_ref_id) if order.type_ref_id else None,
        "scope": order.scope,
        "service": order.service.code if order.service_id else None,
        "mode": order.mode,
        "template_id": str(order.template_id) if order.template_id else None,
        "priority_id": str(order.priority_id) if order.priority_id else None,
        "is_gate": False,
        "source": SOURCE_DISPATCHER,
    }
    with transaction.atomic():
        made = metering_seam.raise_work_order(actor, payload)
        core_audit.write_row(
            action="work.order.duplicated",
            entity_type="work_order",
            entity_id=made["id"],
            actor_user_id=getattr(actor, "id", None),
            after={"from_order_no": order.order_no, "order_no": made.get("order_no")},
        )
    return {"id": str(made["id"]), "order_no": made.get("order_no"), "from_order_no": order.order_no}
