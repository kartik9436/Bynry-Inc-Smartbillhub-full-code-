# ── Trace ──────────────────────────────────────────────
# Change:   CR-198-BRC10 (PO 2026-10-29) — what a text provider tells us after
#           we send: a delivery status, or a customer's STOP.
# Rules:    BR-INT-085 (a status is saved once per (message, status)) ·
#           BR-INT-086 (STOP → do-not-text list + the account's SMS tick OFF) ·
#           BR-NOT-005 (forward-only lifecycle: sent → delivered | failed) ·
#           CLAUDE.md hard rule 1 · hard rule 6 (idempotent) · hard rule 7
#           (audited) · hard-won law 14 (the savepoint)
# Tests:    06-backend/tests/test_cr198_sms_twilio.py
# ───────────────────────────────────────────────────────
"""Delivery statuses and STOP replies for text messages — landed once, applied once.

Called by `apps/integrations/platform_door.py` (through
`apps/integrations/seams/notifications.py`) AFTER Twilio's signature has been
checked and INSIDE the utility's own tenant context. Nothing here knows Twilio:
the door hands over OUR word (`in_transit` · `delivered` · `failed`), the
provider's message id and its error code.

ONCE, BY THE DATABASE
---------------------
`provider_status_events` has `UNIQUE (tenant, provider, event_key)`. The INSERT
is the duplicate verdict, under a SAVEPOINT (hard-won law 14 — on PostgreSQL a
refused INSERT aborts the transaction, and SQLite cannot show it). A retried
`delivered` is refused and nothing else happens; `sent` then `delivered` are two
keys and both land.

FORWARD ONLY
------------
`delivered` moves a `sent` row to `delivered`; `failed` moves a `sent` row to
`failed` with Twilio's error code on `last_error`. Through
`dispatcher.forward_only`, so a late `sent` can never move a delivered row back.
`in_transit` is evidence and moves nothing. A status for a message we cannot
find is still saved (the evidence) and reported as such.

STOP (PO 2026-10-29, ruling 6A — STOP only)
-------------------------------------------
The number goes on the do-not-text list (`suppression.suppress`, reason
`unsubscribed`), which also HOLDS every text already queued to it; and every
account this utility has texted at that number has its *SMS reminders* tick
turned OFF, through customers' own service, audited there. Twilio's `21610`
(*the person has opted out*) on a failed send is the same fact arriving the
other way, and is applied the same way.
"""

from __future__ import annotations

from datetime import datetime
from importlib import import_module
from typing import Any

from django.db import IntegrityError, transaction

from apps.notifications import models, suppression, suppression_models
from apps.notifications.sms_feedback_models import (
    KIND_REPLY,
    KIND_STATUS,
    ProviderStatusEvent,
)
from core import audit, errors
from core import tenancy as core_tenancy

OUTCOME_IN_TRANSIT = "in_transit"
OUTCOME_DELIVERED = "delivered"
OUTCOME_FAILED = "failed"
OUTCOME_STOP = "stop"
OUTCOMES = (OUTCOME_IN_TRANSIT, OUTCOME_DELIVERED, OUTCOME_FAILED)

#: Twilio's *the person has opted out* — the only provider code acted on here.
OPTED_OUT_CODE = "21610"

AUDIT_STATUS = "delivery.status_reported"
AUDIT_ENTITY = "outbound_message"

#: The customers callable this module asks to turn the tick off (G20 names it).
CUSTOMERS_MODULE = "customers"
SMS_OPT_OUT_KIND = "sms_opt_out"
SMS_OPT_OUT_WRITE = "turn_off_sms_reminders"


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def normalise_number(raw: Any) -> str | None:
    """`(402) 555-1049` → `+14025551049`; None when it is not a phone number."""
    from apps.identity.phones import normalise_phone

    return normalise_phone(raw)


def _land(
    *,
    provider: str,
    event_key: str,
    kind: str,
    reference: str,
    outcome: str,
    error_code: str | None,
    received_at: datetime,
    message: models.OutboundMessage | None,
) -> bool:
    """INSERT the event; True when new, False when the key already landed."""
    try:
        with transaction.atomic():
            ProviderStatusEvent.objects.create(
                tenant_id=_tenant_id(),
                provider=provider,
                event_key=event_key,
                kind=kind,
                message=message,
                provider_reference=reference,
                outcome=outcome,
                error_code=error_code,
                received_at=received_at,
            )
    except IntegrityError:
        return False
    return True


def _message_for(reference: str) -> models.OutboundMessage | None:
    if not reference:
        return None
    return (
        models.OutboundMessage.objects.filter(
            tenant_id=_tenant_id(),
            channel=models.CHANNEL_SMS,
            provider_reference=reference,
        )
        .order_by("created_at")
        .first()
    )


def _turn_off_texts(account_ids: Any, *, reason: str, at: datetime, number: str | None) -> tuple:
    try:
        target = import_module(f"apps.{CUSTOMERS_MODULE}.{SMS_OPT_OUT_KIND}")
    except ImportError:  # pragma: no cover — customers publishes it
        return ()
    write = getattr(target, SMS_OPT_OUT_WRITE, None)
    if not callable(write):  # pragma: no cover
        return ()
    return tuple(write(account_ids=account_ids, reason=reason, at=at, number=number))


def messages_to(number: str) -> list[models.OutboundMessage]:
    """This utility's texts to this number, however the number was typed.

    The address on a queue row is the snapshot a clerk typed (`(402) 555-1049`,
    `402.555.1049`), so it is matched by its LAST FOUR DIGITS in SQL — which
    every spelling of a number shares — and confirmed in E.164 here. Bounded by
    one number's texts, never the table."""
    wanted = normalise_number(number)
    if not wanted:
        return []
    rows = models.OutboundMessage.objects.filter(
        tenant_id=_tenant_id(),
        channel=models.CHANNEL_SMS,
        recipient_address__endswith=wanted[-4:],
    ).order_by("created_at")
    return [one for one in rows if normalise_number(one.recipient_address) == wanted]


def has_texted(number: str) -> bool:
    """Has this utility ever queued a text to this number? (The reply door asks.)"""
    return bool(messages_to(number))


def _apply_opt_out(
    number: str | None,
    *,
    at: datetime,
    reason: str,
    detail: str,
    source_message: models.OutboundMessage | None = None,
) -> dict[str, Any]:
    wanted = normalise_number(number)
    if not wanted:
        return {"suppressed": False, "accounts_turned_off": 0}
    write = suppression.suppress(
        channel=models.CHANNEL_SMS,
        address=wanted,
        reason=suppression_models.REASON_UNSUBSCRIBED,
        at=at,
        detail=detail,
        source_message_id=None if source_message is None else source_message.pk,
    )
    accounts = {str(one.account_id) for one in messages_to(wanted) if one.account_id}
    if source_message is not None and source_message.account_id:
        accounts.add(str(source_message.account_id))
    changed = _turn_off_texts(sorted(accounts), reason=reason, at=at, number=wanted)
    return {
        "suppressed": True,
        "suppression_created": write.created,
        "held_messages": len(write.held_message_ids),
        "accounts_turned_off": len(changed),
    }


@transaction.atomic
def record_status(
    *,
    provider: str,
    reference: str,
    outcome: str,
    received_at: datetime,
    error_code: str | None = None,
    provider_text: str | None = None,
    provider_status: str | None = None,
) -> dict[str, Any]:
    """Land ONE delivery status. Returns what happened, never raises on a repeat."""
    if outcome not in OUTCOMES:
        raise ValueError(f"{outcome!r} is not a delivery outcome; one of {OUTCOMES}")
    reference = str(reference or "").strip()
    key = f"{reference}|{str(provider_status or outcome).strip().lower()}"
    message = _message_for(reference)
    landed = _land(
        provider=provider,
        event_key=key,
        kind=KIND_STATUS,
        reference=reference,
        outcome=outcome,
        error_code=error_code,
        received_at=received_at,
        message=message,
    )
    answer: dict[str, Any] = {
        "landed": landed,
        "message_found": message is not None,
        "moved_to": None,
    }
    if not landed or message is None or outcome == OUTCOME_IN_TRANSIT:
        return answer

    from apps.notifications import dispatcher

    target = models.STATUS_DELIVERED if outcome == OUTCOME_DELIVERED else models.STATUS_FAILED
    if target not in dispatcher.ALLOWED_TRANSITIONS.get(message.status, frozenset()):
        # Forward-only: a status that would move the row backwards (a late
        # `failed` after `delivered`) is evidence and moves nothing.
        answer["moved_to"] = None
    else:
        dispatcher.forward_only(message.status, target)
        before = message.status
        message.status = target
        fields = ["status", "updated_at"]
        if target == models.STATUS_FAILED:
            words = provider_text or "The text was not delivered."
            message.last_error = f"{words} ({error_code})" if error_code else words
            fields.append("last_error")
        message.save(update_fields=fields)
        audit.money_action(
            None,
            AUDIT_STATUS,
            AUDIT_ENTITY,
            str(message.pk),
            before={"status": before},
            after={
                "status": target,
                "provider": provider,
                "error_code": error_code,
                "job": "integrations.platform_door",
            },
        )
        answer["moved_to"] = target
    if outcome == OUTCOME_FAILED and str(error_code or "") == OPTED_OUT_CODE:
        answer["opt_out"] = _apply_opt_out(
            message.recipient_address,
            at=received_at,
            reason="provider_reported_opted_out",
            detail="provider_reported_opted_out",
            source_message=message,
        )
    return answer


@transaction.atomic
def record_stop(
    *,
    provider: str,
    reference: str,
    from_number: str,
    received_at: datetime,
) -> dict[str, Any]:
    """Land ONE STOP reply and apply it: do-not-text list + the tick OFF."""
    reference = str(reference or "").strip()
    landed = _land(
        provider=provider,
        event_key=f"{reference}|reply",
        kind=KIND_REPLY,
        reference=reference,
        outcome=OUTCOME_STOP,
        error_code=None,
        received_at=received_at,
        message=None,
    )
    if not landed:
        return {"landed": False}
    applied = _apply_opt_out(
        from_number,
        at=received_at,
        reason="customer_replied_stop",
        detail="customer_replied_stop",
    )
    return {"landed": True, **applied}


def text_activity() -> dict[str, Any]:
    """The Twilio card's two facts for THIS utility: when a text last left, and
    the last text that failed with its error. Two indexed reads, never a scan
    (`ix_outbound_msgs_status` leads on tenant, status, channel)."""
    tenant_id = _tenant_id()
    sent = (
        models.OutboundMessage.objects.filter(
            tenant_id=tenant_id,
            channel=models.CHANNEL_SMS,
            status__in=(models.STATUS_SENT, models.STATUS_DELIVERED),
        )
        .order_by("-sent_at")
        .values_list("sent_at", flat=True)
        .first()
    )
    failed = (
        models.OutboundMessage.objects.filter(
            tenant_id=tenant_id,
            channel=models.CHANNEL_SMS,
            last_error__isnull=False,
        )
        .order_by("-updated_at")
        .values("updated_at", "last_error")
        .first()
    )
    return {
        "last_sent_at": sent,
        "last_error": None if failed is None else failed["last_error"],
        "last_error_at": None if failed is None else failed["updated_at"],
    }


__all__ = [
    "text_activity",
    "OUTCOME_DELIVERED",
    "OUTCOME_FAILED",
    "OUTCOME_IN_TRANSIT",
    "has_texted",
    "messages_to",
    "normalise_number",
    "record_status",
    "record_stop",
]
