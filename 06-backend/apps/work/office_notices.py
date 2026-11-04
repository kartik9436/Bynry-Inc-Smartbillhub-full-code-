# ── Trace ──────────────────────────────────────────────
# Change:   CR-168-BRC10 §F — TECHNICIAN SYNC DESIGN (5): "Phone → office: the
#           office is told when a job closes, when its photos are complete
#           (Accept unlocks), and when anything is flagged Needs review."
#           Lane FIELD-2.
# Rules:    BR-WRK-062 (Accept waits for every REQUIRED photo) · BR-WRK-063
#           (held for review) · BR-NOT-021 (recipients — notifications' rule) ·
#           BR-WRK-002 (work writes nobody else's table: it NAMES the event,
#           notifications queues it)
# Tests:    06-backend/tests/test_cr168_field_work_notifications.py
# ───────────────────────────────────────────────────────
"""Work's half of telling the office: WHICH event happened, on WHICH job.

Everything about the message — who receives it, its words, the queue row — is
the notifications module's (`field_work_events`). This file decides only when
an event has happened, from facts work owns: a close accepted in a sync page,
items held for review in a sync page, and the last REQUIRED photo of a closed
job landing.

The initiator is the user who SENT THE JOB TO THE FIELD (`assigned_by`) —
BR-NOT-021's *"the user who started the action"* read for field work.

⚠ **NOTHING HERE MAY FAIL THE FIELD DATA.** Each call runs after the sync's
own transaction has committed its items, and the notifications seam never
raises; a broad catch here as well, because a sync page of 200 readings must
not answer 500 because the bell could not be rung.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from django.utils import timezone

from apps.work.seams import metering_seam, notifications_seam

log = logging.getLogger(__name__)


def _order(order_id: Any) -> Any:
    return metering_seam.work_order_row(order_id)


def _tell(order: Any, event: str, *, count: int = 0, discriminator: str = "") -> Any:
    try:
        return notifications_seam.queue_field_work_event(
            event=event,
            order_id=order.id,
            order_no=order.order_no,
            office_user_id=getattr(order, "assigned_by_id", None),
            occurred_at=timezone.now(),
            count=count,
            discriminator=discriminator,
        )
    except Exception as exc:  # noqa: BLE001 — a notice never fails field data
        log.warning("field work notice %s for %s not queued: %s", event, order.order_no, exc)
        return None


def after_sync(order_id: Any, results: list[dict[str, Any]]) -> dict[str, Any]:
    """After one sync page: a close that was APPLIED, and items HELD."""
    from apps.work import photo_links

    told: dict[str, Any] = {}
    order = _order(order_id)
    if order is None:
        return told
    if any(r.get("kind") == "close" and r.get("result") == "accepted" for r in results):
        # FB-013 (`DEF-WRK-10641`, PO ruling (b) 2026-10-28) — a close *Not done
        # — payment received* is told as THAT, in place of the plain *closed*:
        # one bell per close, never two (decision log judgment 6).
        from apps.work import connection_models as work_tables

        event = "not_done_paid" if order.outcome == work_tables.OUTCOME_NOT_DONE_PAID else "closed"
        told[event] = _tell(order, event, count=photo_links.pending_required(order.id))
    held = sorted(str(r.get("key")) for r in results if r.get("result") == "held_for_review")
    if held:
        # One message per PAGE carrying the count (BR-NOT-020), and the same
        # page replayed answers duplicates — nothing held twice, nothing told twice.
        digest = hashlib.sha256("|".join(held).encode()).hexdigest()[:16]
        told["needs_review"] = _tell(order, "needs_review", count=len(held), discriminator=digest)
    return told


def after_photo_landed(order_id: Any, *, required: bool) -> Any:
    """The last REQUIRED photo of a CLOSED job landed: Accept is available."""
    from apps.work import photo_links

    if not required:
        return None  # optional photos never hold Accept, so never release it
    order = _order(order_id)
    if order is None or getattr(order, "state", None) != "completed" or order.accepted_by_id:
        return None
    if photo_links.pending_required(order.id):
        return None
    return _tell(order, "photos_complete")
