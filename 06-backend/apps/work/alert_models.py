# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 (the native field app) · Phase 13 · T-41 — lane S-FIND
# Rules:    BR-FLD-00028 (R28 — an emergency must be acknowledged; no
#           acknowledgement in 5 minutes and dispatch is told) · BR-FLD-00029
#           (R29 — dispatch messages only) · BR-WRK-034 (the push) ·
#           CLAUDE.md hard rules 1 and 7
# Migration: work/0039 (table) · work/0040 (RLS ENABLE + FORCE)
# ───────────────────────────────────────────────────────
"""`work_field_alerts` — one alert sent to one technician's handset.

Declared in its own file and imported by `models.py`, for the reason
`evidence_models.py` gives: `models.py` is ~2,400 lines with several lanes
editing it, and a pathspec commit takes the whole file (hard-won law 11).

WHY A ROW AND NOT ONLY A PUSH
-----------------------------
R28 makes an emergency something that must be ANSWERED, and an answer needs a
question to attach to. The push itself is the doorbell (`push.py`'s own words):
whether a handset rang is the provider's answer, out of band. What this product
can know — and so what this row holds — is that an alert was SENT, to whom, how
many devices were addressed, when it must be acknowledged by, when it was, and
whether dispatch had to be told. FF-42 Alerts lists these rows; FF-43's
countdown reads `ack_due_at`.

⚠ **`ack_due_at` IS STORED, NOT DERIVED AT READ.** It is `sent_at + 5 minutes`
(R28) written once at send, so the sweep and the countdown read ONE instant and
a later change to the five minutes cannot move an alert already in flight.
"""

from __future__ import annotations

from django.db import models

from core.dbfields import uuid7_pk

#: The four kinds T-41 names — *urgent assignment, emergency, schedule change,
#: dispatch message* — that a dispatcher SENDS. (The automatic push on every
#: assignment is `push.py`'s `new_job`, which writes no alert row: it is the
#: doorbell for the next sync, and nothing waits for an answer to it.)
KIND_URGENT_ASSIGNMENT = "urgent_assignment"
KIND_EMERGENCY = "emergency"
KIND_SCHEDULE_CHANGE = "schedule_change"
KIND_DISPATCH_MESSAGE = "dispatch_message"
ALERT_KINDS: tuple[str, ...] = (
    KIND_URGENT_ASSIGNMENT,
    KIND_EMERGENCY,
    KIND_SCHEDULE_CHANGE,
    KIND_DISPATCH_MESSAGE,
)


class WorkFieldAlert(models.Model):
    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    kind = models.TextField()
    #: NULL only for a dispatch message about no job (FF-42: *"Depot closes at
    #: 16:30 on Friday"*). Every other kind is about an order.
    work_order = models.ForeignKey(
        "work.WorkOrder",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_column="work_order_id",
        related_name="field_alerts",
    )
    technician = models.ForeignKey(
        "work.Technician", on_delete=models.PROTECT, db_column="technician_id", related_name="field_alerts"
    )
    #: What dispatch typed — required for a dispatch message, optional context
    #: otherwise (FF-43's *What was said*).
    message = models.TextField(blank=True, default="")
    sent_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True, db_column="sent_by", related_name="+"
    )
    sent_at = models.DateTimeField()
    #: The sender's idempotency key — a dispatcher pressing *Send* twice sends
    #: one alert, not two (and starts one five-minute clock, not two).
    key = models.TextField(null=True, blank=True)
    ack_required = models.BooleanField(default=False)
    ack_due_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True, db_column="acknowledged_by", related_name="+"
    )
    #: Set ONCE by the sweep when `ack_due_at` passed unanswered (R28).
    escalated_at = models.DateTimeField(null=True, blank=True)
    #: What notifications answered when dispatch was told — its own code
    #: (`escalation_queued`, `escalation_refused`, …), or `unwired`. Kept so a
    #: reader can see whether the office message was actually queued.
    dispatch_told = models.TextField(null=True, blank=True)
    #: Devices the push job addressed — the count, never an optimistic constant
    #: (`push.py`). NULL until the job runs.
    devices_attempted = models.IntegerField(null=True, blank=True)
    pushed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "work_field_alerts"
        constraints = [
            models.CheckConstraint(condition=models.Q(kind__in=ALERT_KINDS), name="ck_work_field_alerts_kind"),
            models.UniqueConstraint(
                fields=["tenant", "key"],
                condition=models.Q(key__isnull=False),
                name="uq_work_field_alerts_tenant_key",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "technician", "sent_at"], name="ix_work_field_alerts_tech"),
            models.Index(
                fields=["tenant", "ack_due_at"],
                condition=models.Q(ack_required=True, acknowledged_at__isnull=True, escalated_at__isnull=True),
                name="ix_work_field_alerts_due",
            ),
        ]
