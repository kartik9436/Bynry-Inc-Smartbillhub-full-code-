"""Messages a CLERK adds to a request's *What the customer is told* (`DEF-CUS-10042`).

PO 2026-10-11, on New request step 4: *"use table array componnet and allow
user to add more communcation to user"*. The five automatic rows are
`applicant_messages.py`'s and are not touched here; this is the second list,
shaped as Move-in's added messages already are (`move_in_complete.py`): send
THIS template, TO this address, by this CHANNEL, at this MOMENT.

WHAT A ROW CAN SAY, AND WHY ONLY THAT
------------------------------------
* **Template** — a published template's code from
  `notifications_seam.message_templates()`, the list Move-in's *+ Add message*
  offers. A row with none is refused by name.
* **Channel** — `email` queues. `text` is stored and recorded as NOT queued:
  no service-request wording has been written for 160 characters and no SMS
  route reaches an applicant who is not yet a customer. The row says so rather
  than pretending (`BR-NOT-013` — nothing on any channel is SENT; email reaches
  the outbound queue and stops there).
* **To** — an address, defaulting to the applicant's email on the screen.
* **When** — on submit, on approval, or on refusal: moments this product
  already reaches on a request. Nothing here schedules a date.

A ROW IS A PLAN UNTIL IT FIRES, THEN A RECORD
---------------------------------------------
`save` replaces the UNFIRED rows whole with the clerk's table and keeps every
fired one, so a message a customer has already been told is never rewritten
(hard rule 4's posture). `fire` never raises and never undoes the act it rides
on: each queue call is inside the seam's own savepoint (hard-won law 14).
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.customers import models, notifications_seam, seams
from apps.customers.applicant_messages import CLASS_ACKNOWLEDGEMENT, CLASS_ACKNOWLEDGEMENT_FEE
from apps.customers.applicant_message_models import (
    EXTRA_CHANNELS,
    EXTRA_ON_APPROVE,
    EXTRA_ON_REFUSE,
    EXTRA_ON_SUBMIT,
    EXTRA_SEND_WHEN,
    ServiceRequestExtraMessage,
)
from core import errors

BR_REF = "DEF-CUS-10042"

#: The two acknowledgement classes (`applicant_messages`' own constants, named
#: once there) — an added message in either carries the acknowledgement's facts.
ACKNOWLEDGEMENT_CLASSES = frozenset({CLASS_ACKNOWLEDGEMENT, CLASS_ACKNOWLEDGEMENT_FEE})
FIELD = "extra_messages"

STATE_PLANNED = "planned"
STATE_QUEUED = "queued"
STATE_NOT_SENT = "not_sent"

REASON_TEXT_NOT_WRITTEN = "text_not_written_for_applicants"

#: A request past these states has been decided; nothing new can wait for a
#: moment that has already happened.
_DECIDED = (
    models.ServiceRequest.APPROVED,
    models.ServiceRequest.IN_FULFILMENT,
    models.ServiceRequest.COMPLETED,
    models.ServiceRequest.REFUSED,
    models.ServiceRequest.WITHDRAWN,
    models.ServiceRequest.CLOSED,
)

_STATE_MOMENT = {
    models.ServiceRequest.APPROVED: EXTRA_ON_APPROVE,
    models.ServiceRequest.REFUSED: EXTRA_ON_REFUSE,
}


def _bad(index: int, field: str, key: str) -> errors.ValidationError:
    return errors.ValidationError(
        errors.VAL_FORMAT,
        message_key=key,
        field_errors=[
            {"field": f"{FIELD}[{index}].{field}", "code": errors.VAL_FORMAT, "message_key": key}
        ],
        params={"row": index + 1},
    )


def template_choices() -> dict[str, Any]:
    """`GET /service-requests/message-templates` — what *Add a message* may pick.

    The code is what a row sends; the name a person gave it is what the screen
    shows (B14 rule 31). `served` is false when notifications published no
    answer, so the screen says so instead of offering an empty list.
    """
    published = notifications_seam.message_templates()
    results = [
        {"code": str(row.get("code")), "name": str(row.get("name") or row.get("code"))}
        for row in published
        if row.get("code")
    ]
    return {"served": len(published) > 0, "results": results}


def _names() -> dict[str, str]:
    return {row["code"]: row["name"] for row in template_choices()["results"]}


def rows_for(request_id: Any) -> list[dict[str, Any]]:
    """The added rows in table order, each with its state. Never a queue id."""
    names = _names()
    out: list[dict[str, Any]] = []
    for row in ServiceRequestExtraMessage.objects.filter(request_id=request_id).order_by("seq"):
        out.append(
            {
                "seq": row.seq,
                "template_code": row.template_code,
                "template_name": names.get(row.template_code, row.template_code),
                "channel": row.channel,
                "to_address": row.to_address,
                "send_when": row.send_when,
                "state": row.fired_state or STATE_PLANNED,
                "reason": row.fired_reason,
                "fired": row.fired_at is not None,
            }
        )
    return out


def _clean(index: int, raw: Any, known: set[str] | None) -> dict[str, Any]:
    row = raw if isinstance(raw, dict) else {}
    template = str(row.get("template_code") or "").strip()
    if not template:
        raise _bad(index, "template_code", "customers.serviceRequest.extra.templateRequired")
    if known is not None and template not in known:
        raise _bad(index, "template_code", "customers.serviceRequest.extra.templateUnknown")
    channel = str(row.get("channel") or "email")
    if channel not in EXTRA_CHANNELS:
        raise _bad(index, "channel", "customers.serviceRequest.extra.channelUnknown")
    when = str(row.get("send_when") or EXTRA_ON_SUBMIT)
    if when not in EXTRA_SEND_WHEN:
        raise _bad(index, "send_when", "customers.serviceRequest.extra.whenUnknown")
    to_address = str(row.get("to_address") or "").strip()
    if not to_address:
        raise _bad(index, "to_address", "customers.serviceRequest.extra.addressRequired")
    return {
        "template_code": template,
        "channel": channel,
        "send_when": when,
        "to_address": to_address[:320],
    }


def save(actor: Any, request_id: Any, rows: Any) -> list[dict[str, Any]]:
    """Replace the request's UNFIRED added rows with `rows`. Fired rows stay."""
    from apps.customers import service_request_service as writes

    if not isinstance(rows, list):
        raise _bad(0, "rows", "customers.serviceRequest.extra.notAList")
    published = template_choices()
    known = {row["code"] for row in published["results"]} if published["served"] else None
    cleaned = [_clean(index, raw, known) for index, raw in enumerate(rows)]
    with transaction.atomic():
        request = writes.request_row(request_id, lock=True)
        if request.state in _DECIDED and cleaned:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref=BR_REF,
                message_key="customers.serviceRequest.extra.decided",
                params={},
            )
        ServiceRequestExtraMessage.objects.filter(
            request_id=request.id, fired_at__isnull=True
        ).delete()
        top = (
            ServiceRequestExtraMessage.objects.filter(request_id=request.id).aggregate(
                top=Max("seq")
            )["top"]
            or 0
        )
        for offset, row in enumerate(cleaned, start=1):
            ServiceRequestExtraMessage.objects.create(
                tenant_id=request.tenant_id, request_id=request.id, seq=top + offset, **row
            )
        writes._audit(
            actor,
            "service_request.extra_messages.saved",
            request.id,
            after={"rows": cleaned},
        )
    return rows_for(request_id)


def fire(actor: Any, request: Any, moment: str) -> list[dict[str, Any]]:
    """Queue every unfired row waiting for `moment`. Never raises.

    Called after the submit, the approval or the refusal has been written, from
    inside its transaction; each queue call is in the seam's own savepoint, so a
    refused message can never abort the act it rides on (hard-won law 14).
    """
    from apps.customers import service_request_service as writes

    out: list[dict[str, Any]] = []
    waiting = ServiceRequestExtraMessage.objects.filter(
        request_id=request.id, send_when=moment, fired_at__isnull=True
    ).order_by("seq")
    for row in waiting:
        if row.channel != "email":
            state, reason, ref = STATE_NOT_SENT, REASON_TEXT_NOT_WRITTEN, None
        else:
            # `DEF-CUS-10445` — an added message in an ACKNOWLEDGEMENT class
            # carries every fact the acknowledgement itself does (service type,
            # target date, the walked address); the other classes keep the
            # facts they were written for.
            facts = (
                writes.acknowledgement_facts(request)
                if row.template_code in ACKNOWLEDGEMENT_CLASSES
                else {
                    "applicant_name": request.applicant_name,
                    "service_address": writes._applicant_address(request),
                }
            )
            answer = notifications_seam.queue_request_extra_message(
                message_id=row.id,
                template_code=row.template_code,
                to_address=row.to_address,
                request_no=request.request_no,
                actor=actor,
                # PO option B, 2026-10-29: the applicant's language first,
                # the utility's default as the fallback.
                language=seams.tenant_default_language(),
                preferred_language=getattr(request, "preferred_language", None),
                **facts,
            )
            ref = answer.get("message_id")
            state = STATE_QUEUED if ref else STATE_NOT_SENT
            reason = None if ref else str(answer.get("code") or "")
        row.fired_at = timezone.now()
        row.fired_state = state
        row.fired_reason = reason
        row.notification_id = ref
        row.save(update_fields=["fired_at", "fired_state", "fired_reason", "notification_id"])
        out.append({"seq": row.seq, "state": state, "reason": reason, "sent": False})
    if out:
        writes._audit(
            actor, f"service_request.extra_messages.{moment}", request.id, after={"rows": out}
        )
    return out


def fire_for_state(actor: Any, request: Any) -> list[dict[str, Any]]:
    """The decision's rows, by the request's NEW state (approved or refused)."""
    moment = _STATE_MOMENT.get(request.state)
    return fire(actor, request, moment) if moment else []
