# ── Trace ──────────────────────────────────────────────
# Change:   CR-168-BRC10 §F — TECHNICIAN SYNC DESIGN (5), PO 2026-10-04 (design
#           delegated, recorded): "Phone → office: the office is told when a
#           job closes, when its photos are complete (Accept unlocks), and when
#           anything is flagged Needs review." Lane FIELD-2.
# Rules:    BR-NOT-021 (who receives a staff notification — the user who
#           started the action, plus every System Admin for a failure) ·
#           BR-NOT-019 (in-app is a real channel) · BR-NOT-005 (queue only) ·
#           BR-NOT-020 (one message per event, never per item) · CLAUDE.md
#           rule 6 (idempotent) · hard rule 7 (the queue write is audited by
#           `queue_document`) · hard-won law 14 (the savepoint)
# Tests:    06-backend/tests/test_cr168_field_work_notifications.py
# Impacts:  apps/notifications/models.py (`field_work` joins SOURCE_TYPES) ·
#           catalogs.py + seed_templates.py (`staff_field_work`) · in_app.py
#           (the bell item carries a message key, rendered in eleven
#           catalogues) · apps/work/seams/notifications_seam.py (the caller)
# ───────────────────────────────────────────────────────
"""The office is told about the field: a close, photos complete, Needs review.

THE THREE EVENTS
────────────────────────────────────────────────────────────────────────────
* ``closed`` — a technician's close reached the server. If REQUIRED photos are
  still uploading, the message says how many (the office cannot Accept yet).
* ``photos_complete`` — the last REQUIRED photo of a CLOSED job landed, so
  Accept is now available (the PO's (a): *"Accept stays unavailable until
  they've all arrived"* — this is the moment it stops being unavailable).
* ``not_done_paid`` — FB-013 (PO 2026-10-28): the technician closed *Not done —
  payment received* after a fresh read showed the balance cleared. Told in
  place of ``closed`` — *"WO-0171 · Not disconnected — payment received"*.
* ``needs_review`` — one sync page carried items the server STORED but could
  not apply (a job cancelled or reassigned while the phone was offline, a bad
  unit…). One message per page, carrying the count — never one per item
  (BR-NOT-020's reasoning: a message per item is the one a clerk switches off).

WHO IS TOLD — BR-NOT-021, UNCHANGED
────────────────────────────────────────────────────────────────────────────
The rule addresses a staff event to *"the user who started the action"*. For
field work the office action that started it is SENDING THE JOB TO THE FIELD:
the user who assigned it (`work_orders.assigned_by`) is the initiator, and the
work module passes that user's id. ``needs_review`` is a FAILURE — something
the field sent could not be applied — so it ALSO reaches every active System
Admin, exactly as the rule's clause (b) says. **No other recipient is added.**
The 2026-10-04 narrowing of BR-NOT-021 is for Work ESCALATIONS (a rule's
escalation step naming an area supervisor) and is not stretched to cover this.

⚠ **A JOB NOBODY ASSIGNED (a rule assigned it) reaches nobody on a close or
photos-complete** — BR-NOT-021 clause (e)'s answer for an event with no
initiator and no failure. It is returned as ``field_work_no_addressee`` with
the ruling quoted, never guessed. Its Needs review still reaches the System
Admins. The office still sees the job on the approvals queue either way.

WHY THE BELL SHOWS A MESSAGE KEY AS WELL AS THE BODY
────────────────────────────────────────────────────────────────────────────
The rendered body is the utility's own template (``staff_field_work``, English
by default, editable on Settings → Templates) and is what the dispatch home and
the delivery record show. The BELL renders the event from the frozen render
context in the clerk's own language — ``notifications.fieldWork.*`` in all
eleven catalogues — because "WO-0051 closed in the field" is product copy, not
a letter the utility wrote. ``in_app.inbox`` derives the key from the queue
row's ``source_type`` and ``render_context``; nothing new is stored.

IT NEVER RAISES
────────────────────────────────────────────────────────────────────────────
A failed notification must never fail the field data it reports — a sync page
of 200 readings does not roll back because the office could not be told. Every
path returns an outcome row, and the write runs in its own SAVEPOINT (law 14:
on PostgreSQL a bare try/except would poison the caller's transaction).
"""

from __future__ import annotations

import uuid
from importlib import import_module
from types import SimpleNamespace
from typing import Any

from django.db import transaction

from apps.notifications import models, services, staff_recipients
from core import tenancy as core_tenancy

#: The queue's kind for these three messages (`models.SOURCE_TYPES`).
SOURCE_FIELD_WORK = "field_work"
#: The template class every one of them renders from.
TEMPLATE_CODE = "staff_field_work"

EVENT_CLOSED = "closed"
EVENT_PHOTOS_COMPLETE = "photos_complete"
EVENT_NEEDS_REVIEW = "needs_review"
#: FB-013 (`DEF-WRK-10641`, PO ruling (b) 2026-10-28) — a close *Not done —
#: payment received*: the office is told THIS in place of the plain *closed*
#: (one bell per close). Same initiator and audience as a close (BR-NOT-021).
EVENT_NOT_DONE_PAID = "not_done_paid"
EVENTS = (EVENT_CLOSED, EVENT_PHOTOS_COMPLETE, EVENT_NEEDS_REVIEW, EVENT_NOT_DONE_PAID)

#: The English phrase the seeded body prints for `{event}` — the template is
#: tenant data in the default language; the bell uses the catalogue key below.
EVENT_PHRASE = {
    EVENT_CLOSED: "closed in the field",
    EVENT_PHOTOS_COMPLETE: "photos all arrived, ready to accept",
    EVENT_NEEDS_REVIEW: "has field items that need review",
    EVENT_NOT_DONE_PAID: "not disconnected — payment received",
}

#: The bell's catalogue key per event (`07-frontend/src/i18n/locales/*.json`).
#: A close with required photos still uploading reads differently, because the
#: one thing the office needs from it is "not yet".
BELL_KEY = {
    EVENT_CLOSED: "notifications.fieldWork.closed",
    "closed_uploading": "notifications.fieldWork.closedUploading",
    EVENT_PHOTOS_COMPLETE: "notifications.fieldWork.photosComplete",
    EVENT_NEEDS_REVIEW: "notifications.fieldWork.needsReview",
    EVENT_NOT_DONE_PAID: "notifications.fieldWork.notDonePaid",
}

QUEUED = "field_work_queued"
ALREADY_QUEUED = "field_work_already_queued"
NO_ADDRESSEE = "field_work_no_addressee"
REFUSED = "field_work_refused"
ERROR = "field_work_error"

BR_REF = "BR-NOT-021"

#: Namespace for the derived source ids. A uuid5 of (order, event, discriminator)
#: makes a replayed sync page or a re-run photo job find its own row and write
#: nothing (CLAUDE.md rule 6) — the queue's unique key does the refusing.
_NAMESPACE = uuid.UUID("5b0f6f0e-6a1d-5c9e-9a57-1c4f1e2d7a68")


def source_id_for(order_id: Any, event: str, discriminator: str = "") -> uuid.UUID:
    return uuid.uuid5(_NAMESPACE, f"{order_id}|{event}|{discriminator}")


def bell_key_for(context: dict[str, Any] | None) -> tuple[str | None, dict[str, Any]]:
    """The catalogue key and its params for one queued field-work message.

    Read by `in_app.inbox` from the queue row's frozen `render_context` — the
    same snapshot the body was rendered from, so the two cannot disagree.
    """
    ctx = context or {}
    event = str(ctx.get("event_code") or "")
    count = int(ctx.get("count") or 0)
    if event.startswith(("escalation_", "office_")) or event in (
        "certificate_expiring",
        "technician_day",
    ):
        # `CR-168-BRC10` P3.57/P3.59 (lane SRV-4) — a Work escalation or
        # reminder rides this kind and template; its words are its own module's.
        # P6.2 (lane SRV-5) — so do the three back-office notices (`office_*`).
        from apps.notifications import work_escalations

        return work_escalations.bell_key(ctx)
    if event == EVENT_CLOSED and count > 0:
        key = BELL_KEY["closed_uploading"]
    else:
        key = BELL_KEY.get(event)
    return key, {"order": str(ctx.get("order_no") or ""), "count": count}


def _office_user(user_id: Any) -> Any | None:
    """The initiator as an actor `staff_recipients` can address — through
    identity's published read (BR-TEN-013), never its ORM."""
    if not user_id:
        return None
    try:
        reader = getattr(import_module("apps.identity.selectors"), "user_in_tenant", None)
    except ImportError:  # pragma: no cover - defensive
        reader = None
    user = reader(core_tenancy.current_tenant_id(), user_id) if callable(reader) else None
    if user is not None:
        return user
    # Identity could not name them; the id alone still addresses the inbox.
    return SimpleNamespace(id=user_id, full_name=None, email=None)


def queue_field_work_event(
    *,
    event: str,
    order_id: Any,
    order_no: str,
    office_user_id: Any,
    occurred_at: Any,
    count: int = 0,
    discriminator: str = "",
) -> dict[str, Any]:
    """Queue ONE in-app message telling the office about a field event.

    `count` is the photos still uploading (``closed``) or the items held
    (``needs_review``). `discriminator` separates two genuinely different
    events of the same kind on one job (two sync pages with held items); a
    replay passes the same value and writes nothing.

    Returns ONE outcome row (`code`, `note`, `message_id`). Never raises.
    """
    if event not in EVENTS:
        return {"code": REFUSED, "br_ref": BR_REF, "message_id": None,
                "note": f"{event!r} is not one of the three field events {EVENTS}."}
    failure = event == EVENT_NEEDS_REVIEW
    audience = staff_recipients.resolve_staff_recipients(
        actor=_office_user(office_user_id), failure=failure
    )
    if audience.primary is None:
        return {
            "code": NO_ADDRESSEE,
            "br_ref": BR_REF,
            "message_id": None,
            "note": (
                f"{order_no} was not sent to the field by a person, and this event is not a "
                f"failure, so under the ruled recipient policy — {staff_recipients.RULING} — "
                "there is nobody to tell. Nothing is queued and nothing is guessed."
            ),
        }
    phrase = EVENT_PHRASE[event]
    if event == EVENT_CLOSED and count:
        phrase = f"{phrase}; {int(count)} required photo(s) still uploading"
    elif event == EVENT_NEEDS_REVIEW:
        phrase = f"{phrase} ({int(count or 0)})"
    context = {
        "order_no": order_no,
        "event": phrase,
        "event_code": event,
        "count": int(count or 0),
        "at": occurred_at,
    }
    try:
        with transaction.atomic():  # the savepoint — law 14
            write = services.queue_document(
                source_type=SOURCE_FIELD_WORK,
                source_id=source_id_for(order_id, event, discriminator),
                channels=(models.CHANNEL_IN_APP,),
                template=services.TemplatePin(code=TEMPLATE_CODE),
                recipients=(
                    services.Recipient(
                        channel=models.CHANNEL_IN_APP,
                        address=audience.primary.user_id,
                        snapshot={
                            "user_id": audience.primary.user_id,
                            "display_name": audience.primary.display_name,
                            "recipients": audience.snapshot_entries(),
                            "recipient_problems": list(audience.problems),
                            "work_order_id": str(order_id),
                        },
                    ),
                ),
                render_context=context,
                actor=None,
                job="field_work_event",
            )
    except Exception as failure_exc:  # noqa: BLE001 — the one boundary where broad is right
        return {
            "code": ERROR,
            "br_ref": BR_REF,
            "message_id": None,
            "note": (
                f"the office could not be told: {failure_exc} The field data stands — a "
                "failed notification never fails the work it reports."
            ),
        }
    message = write.messages[0] if write.messages else None
    if message is None:
        return {"code": REFUSED, "br_ref": BR_REF, "message_id": None,
                "note": "nothing was queued", "problems": list(write.problems)}
    return {
        "code": QUEUED if message.created else ALREADY_QUEUED,
        "br_ref": BR_REF,
        "message_id": str(message.id),
        "mailboxes": len(audience.recipients),
        "note": "the office has been told" if message.created else "already told; nothing written twice",
    }
