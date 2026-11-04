"""`provider_status_events` — every delivery status a text provider told us, once.

`CR-198-BRC10` (PO 2026-10-29). Twilio posts a callback for each status a text
passes through — `queued`, `sent`, `delivered` — and RETRIES a callback it did
not get a 200 for. So the same `(message, status)` can arrive many times and a
message has several statuses. This table is what makes *saved once* true:

    UNIQUE (tenant, provider, event_key)    event_key = "<MessageSid>|<status>"

`sent` then `delivered` are two keys and both land; a second `delivered` is the
same key and the INSERT is refused — which IS the duplicate verdict, under a
savepoint (hard-won law 14), never a SELECT-then-INSERT.

A STOP reply is recorded here too (`event_key = "<MessageSid>|reply"`), so a
retried reply is applied once.

Written ONLY by `apps/notifications/sms_feedback.py`. RLS FORCED in migration
0035 (`db/rls_notifications_provider_status.sql`) — a write landing under the
wrong tenant would move another utility's message.
"""

from __future__ import annotations

from django.db import models

from core.dbfields import uuid7_pk

KIND_STATUS = "status"
KIND_REPLY = "reply"


class ProviderStatusEvent(models.Model):
    """One status (or one STOP reply) a text provider reported, landed once."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: The manifest key (`sms_twilio`), so two providers' ids never collide.
    provider = models.TextField()
    #: `<MessageSid>|<status>` or `<MessageSid>|reply` — the dedupe key.
    event_key = models.TextField()
    kind = models.TextField(default=KIND_STATUS)
    #: The queue row the status is about, when we sent it. SET_NULL: the event
    #: is evidence and outlives a pruned row.
    message = models.ForeignKey(
        "notifications.OutboundMessage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="message_id",
        related_name="+",
    )
    provider_reference = models.TextField()
    #: OUR word (`in_transit` · `delivered` · `failed`), or `stop` for a reply.
    #: Twilio's own vocabulary never leaves the adapter.
    outcome = models.TextField()
    #: Twilio's `ErrorCode` on a failure (`30003`, `21610`) — kept verbatim,
    #: because support quotes it back to them.
    error_code = models.TextField(null=True, blank=True)
    received_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "provider_status_events"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "provider", "event_key"],
                name="uq_provider_status_events_key",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "provider_reference"],
                name="ix_provider_status_ref",
            ),
        ]
