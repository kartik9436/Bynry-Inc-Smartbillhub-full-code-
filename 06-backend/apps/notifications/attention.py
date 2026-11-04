# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-013 (the delivery dashboard + re-queue, row AND bulk) —
#           DEF-NOT-10650 (PO 2026-10-29, ruled "1A 2A 3B 4B, start")
#           Screens: S8 (Settings → Notifications → Messages needing attention)
# Rules:    BR-NOT-005 (queueing is not sending; a re-queue never bypasses
#           batching) · BR-PAY-018 (held rows release by address verification
#           only) · BR-TEN-017 (the recipient is snapshotted; the contact record
#           is the customers module's) · BR-AUD-006 (customer email/phone are
#           MED class and may enter a payload) · CLAUDE.md rules 1, 6, 7
# Tests:    06-backend/tests/test_def_not_10650_attention_queue.py
# Impacts:  apps/notifications/api.py (the only caller) · selectors.py
# ───────────────────────────────────────────────────────
"""Messages needing attention: the view, the safe bulk selection, and the
one-message address correction — DEF-NOT-10650.

THE FOUR RULINGS (PO 2026-10-29, verbatim *"1A 2A 3B 4B, start"*; decision log
of that date):

1A  The screen OPENS on *Needing attention*, with a count. **Attention is
    `models.ATTENTION_STATUSES` and nothing else** — the tuple the triage sort,
    the partial index and `delivery_ops.failures` already read, so the view,
    the sort and the count cannot come to disagree. `held` is not added: a held
    letter is released by address verification on the ACCOUNT (BR-PAY-018).
2A  *"Select all N matching"* — resolved HERE, from the same filter the list
    used, never from an empty list. Capped at `SELECTION_CAP`; above it the
    answer is a refusal and NO ids, so a clerk can never re-queue a selection
    they did not see the size of. ⚠ **THE CAP IS PER ACTION, NOT PER TENANT**
    (NFR-5): narrowing the view and repeating reaches every row.
3B  *Fix address and retry* changes ONLY this message's delivery. A NEW row
    goes to the corrected address; the failed row is untouched and stays the
    record; the customer's contact is NOT written (this module could not write
    it anyway — B1, and BR-TEN-017 makes the recipient a snapshot); the audit
    row carries old → new, who and when.
4B  The last attempt only — served on the row by `selectors.queue_row`. There
    is no per-attempt history store and none is implied.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Exists, Max, OuterRef, QuerySet, Value
from django.db.models.functions import Coalesce

from apps.notifications import delivery_ops, models, rendering, services
from core import audit
from core import tenancy as core_tenancy
from core import errors

#: The `f.*` name the list and the selection both read (`selectors.QUEUE_FILTERS`).
ATTENTION_FILTER = "attention"

#: 2A — the most rows ONE "Select all N matching" may carry (PO 2026-10-29).
SELECTION_CAP = 500

#: 3B — the channels a clerk can TYPE an address for. Print's address is the
#: premises' (hard rule 8) and is corrected there; in-app and portal are
#: addressed to a person's own login, which is not a thing to retype.
RETRY_TO_CHANNELS = (models.CHANNEL_EMAIL, models.CHANNEL_SMS)

#: 3B — the statuses a corrected address can help. NOT `sent`/`delivered` (the
#: customer has it), NOT `queued` (the original would still go out — two
#: messages), NOT `complained`/`unsubscribed` (the person asked not to be
#: mailed). A hard bounce IS here: a wrong mailbox is exactly what a typed
#: correction fixes, even though a re-queue to the SAME mailbox is refused.
RETRY_TO_STATUSES = (
    models.STATUS_FAILED,
    models.STATUS_BOUNCED,
    models.STATUS_BOUNCED_HARD,
    models.STATUS_BOUNCED_SOFT,
)

#: Hard rule 7 — the one trail row that links the new message to the old one.
AUDIT_RETRIED_TO = "delivery.retried_to_new_address"

#: Why a retry was refused — CODES, which the API turns into one catalogue key.
REFUSED_CHANNEL = "channel_has_no_typed_address"
REFUSED_HELD = "held_row_releases_by_address_verification"
REFUSED_STATUS = "status_not_retryable"


class RetryToRefused(Exception):
    """This message cannot be retried to another address, and `code` says why."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code


class SelectionTooLarge(Exception):
    """More rows match than one action may carry."""

    def __init__(self, count: int) -> None:
        super().__init__(f"{count} rows match; one action carries at most {SELECTION_CAP}.")
        self.count = count


@dataclass(frozen=True)
class Selection:
    message_ids: tuple[str, ...]
    count: int


@dataclass(frozen=True)
class RetryOutcome:
    message_id: str
    channel: str
    status: str
    created: bool
    held: bool


def _tenant_id() -> Any:
    """Hard rule 1: no tenant table is touched without `app.tenant_id` set."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def retried_to_new_address() -> Exists:
    """`DEF-NOT-10665` (PO 2026-10-29, D1 A) — has a LATER copy of this same
    message (same source, same channel, a higher `copy_no`) gone to a DIFFERENT
    address? That is what *Fix address and retry* (3B) leaves behind: the
    failed row untouched as the record, and a new row beside it. Such a row
    shows *Retried to a new address* and LEAVES *Needing attention* — the clerk
    already acted on it — while staying under *All messages*.

    Read from the queue itself, never from the audit row 3B writes: `audit_log`
    is pruned on a retention schedule (hard rule 4, `OQ-1340`), and a link read
    from it would put the message back into *Needing attention* the day it went.
    A later copy to the SAME address is a resend that fixed nothing, so it does
    not count. Used as an annotation and as a filter, so the list, the filter
    and the count cannot disagree.
    """
    return Exists(
        models.OutboundMessage.objects.filter(
            tenant_id=OuterRef("tenant_id"),
            source_type=OuterRef("source_type"),
            source_id=OuterRef("source_id"),
            channel=OuterRef("channel"),
            copy_no__gt=OuterRef("copy_no"),
            recipient_address__isnull=False,
        ).exclude(recipient_address=Coalesce(OuterRef("recipient_address"), Value("")))
    )


def needing_attention(rows: QuerySet) -> QuerySet:
    """1A, as amended by D1 A — a fault status, and not already retried to a
    new address. The ONE definition the list filter and the count both use."""
    return rows.filter(status__in=models.ATTENTION_STATUSES).exclude(retried_to_new_address())


def attention_count() -> int:
    """1A — how many of THIS tenant's messages need attention, whatever view."""
    return needing_attention(
        models.OutboundMessage.objects.filter(tenant_id=_tenant_id())
    ).count()


def resolve_selection(rows: QuerySet) -> Selection:
    """2A — every id the filtered list matches, or a refusal above the cap.

    `rows` is the list's OWN queryset (`selectors.queue_list_queryset`), so the
    selection is the view a clerk is looking at and not a second idea of it.
    It returns re-queueable and non-re-queueable rows alike: the re-queue's
    per-row tally then says what could not move and why, which is the toast
    the PO asked for (*"2 could not be: already sent"*).
    """
    count = rows.count()
    if count > SELECTION_CAP:
        raise SelectionTooLarge(count)
    return Selection(
        message_ids=tuple(str(pk) for pk in rows.values_list("pk", flat=True)),
        count=count,
    )


def normalise_typed_address(channel: str, raw: Any) -> str | None:
    """The address as it will be stored, or None when it is not one.

    Email by Django's own `validate_email` — the check `apps/portal/credentials`
    and the customers service-request form already use, so no screen in the
    product accepts an address another refuses. A phone the way the portal's
    `phone_ok` reads one (ten digits, or eleven starting with 1), stored in
    E.164 like `identity.phones.normalise_phone` — copied rather than imported
    because notifications may not depend on either module (B2 §2).
    """
    text = str(raw or "").strip()
    if not text:
        return None
    if channel == models.CHANNEL_EMAIL:
        try:
            validate_email(text)
        except DjangoValidationError:
            return None
        return text
    if channel == models.CHANNEL_SMS:
        if "@" in text:
            return None
        digits = "".join(ch for ch in text if ch.isdigit())
        if len(digits) == 10 and not text.startswith("+"):
            return f"+1{digits}"
        if len(digits) == 11 and digits.startswith("1"):
            return f"+{digits}"
        return None
    return None


def refusal_for(row: models.OutboundMessage) -> tuple[str, str] | None:
    """(code, detail) when this row cannot be retried to a new address."""
    if row.channel not in RETRY_TO_CHANNELS:
        return (
            REFUSED_CHANNEL,
            f"a {row.channel} message has no address a clerk can type; print is "
            "addressed from the premises (hard rule 8) and in-app/portal from a login.",
        )
    if row.held:
        return (
            REFUSED_HELD,
            "this row is HELD; held rows are released by address verification on the "
            "account and by nothing else (BR-PAY-018).",
        )
    if row.status not in RETRY_TO_STATUSES:
        return (
            REFUSED_STATUS,
            f"a {row.status!r} message cannot be retried to another address: sent and "
            "delivered reached the customer, queued would still go out (two messages), "
            "and complained/unsubscribed are the person's own choice.",
        )
    return None


@transaction.atomic
def retry_to_address(*, row: models.OutboundMessage, address: str, actor: Any) -> RetryOutcome:
    """3B — queue a NEW copy of this message to `address`; change nothing else.

    `address` is already normalised (`normalise_typed_address`). The new row is
    the SAME document — source, template pin and stored figures — at the next
    free `copy_no`, through `services.queue_document` (the ONE write path, B1)
    with the print floor OFF: the paper copy went out at copy 0 and a
    correction of one email is not a second letter.

    ⚠ **A DOUBLE CLICK QUEUES ONE MESSAGE (rule 6).** A queued copy of this
    document on this channel to this exact address, numbered after the
    original, is the earlier click's row and is returned as it is.

    ⚠ **NOTHING ON THE FAILED ROW MOVES** — not its status, not its address,
    not its attempts. It is the record of what happened; the audit row is the
    link from it to the new message.
    """
    found = refusal_for(row)
    if found is not None:
        raise RetryToRefused(*found)

    tenant_id = _tenant_id()
    same_document = models.OutboundMessage.objects.filter(
        tenant_id=tenant_id,
        source_type=row.source_type,
        source_id=row.source_id,
        channel=row.channel,
    )
    earlier = (
        same_document.filter(
            copy_no__gt=row.copy_no,
            recipient_address=address,
            status=models.STATUS_QUEUED,
        )
        .order_by("copy_no")
        .first()
    )
    if earlier is not None:
        return RetryOutcome(
            message_id=str(earlier.pk),
            channel=earlier.channel,
            status=earlier.status,
            created=False,
            held=earlier.held,
        )

    next_copy = (same_document.aggregate(top=Max("copy_no"))["top"] or 0) + 1
    write = services.queue_document(
        source_type=row.source_type,
        source_id=row.source_id,
        channels=(row.channel,),
        template=services.TemplatePin(
            code=row.template_code,
            template_id=row.template_id,
            version=row.template_version,
            language=row.template_language,
        ),
        account_id=row.account_id,
        recipients=(
            services.Recipient(
                channel=row.channel,
                address=address,
                snapshot=row.recipient_snapshot,
            ),
        ),
        copy_no=next_copy,
        actor=actor,
        # The same figures the failed message carried (`DEF-NOT-4449`'s rule
        # for a resend, for the same reason): decoded because the write encodes.
        render_context=rendering.decode_context(row.render_context) or None,
        with_floor=False,
    )
    message = next(m for m in write.messages if m.channel == row.channel)
    new_row = models.OutboundMessage.objects.get(pk=message.id)
    audit.money_action(
        actor,
        AUDIT_RETRIED_TO,
        delivery_ops.AUDIT_ENTITY,
        str(row.pk),
        before={
            "message_id": str(row.pk),
            "channel": row.channel,
            "status": row.status,
            "copy_no": row.copy_no,
            "recipient_address": row.recipient_address,
        },
        after={
            "message_id": str(new_row.pk),
            "copy_no": new_row.copy_no,
            "status": new_row.status,
            "recipient_address": new_row.recipient_address,
            "held": new_row.held,
            # 3B, stated as a value: the customer's contact is not written.
            "contact_record_changed": False,
            "dispatched": False,
        },
    )
    return RetryOutcome(
        message_id=str(new_row.pk),
        channel=new_row.channel,
        status=new_row.status,
        created=message.created,
        held=new_row.held,
    )
