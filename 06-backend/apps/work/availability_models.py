# ── Trace ──────────────────────────────────────────────
# Change:   FB-033 — availability from the phone reaches the office (decision
#           log 2026-10-31, *"FB-033: availability from the phone reaches the
#           office (PO, D1–D4)"*) · DEF-FLD-10799
# Rules:    CLAUDE.md hard rules 1 (RLS ENABLE + FORCE, `work/0063`), 6
#           (idempotent on the handset's key), 7 (every change audited)
# Tests:    06-backend/tests/test_fb033_availability.py ·
#           06-backend/tests/test_fb033_availability_pg.py
# Impacts:  apps/work/models.py (one import line registers this) ·
#           apps/work/availability.py · work/0062, work/0063
# ───────────────────────────────────────────────────────
"""`technician_availability_changes` — every Available / On break / Off duty
the technician chose on the phone, as it was chosen.

ONE ROW PER TAP THAT REACHED THE SERVER, APPLIED OR NOT
────────────────────────────────────────────────────────────────────────────
`technicians.status` + `status_since` hold what is TRUE NOW; this table is the
HISTORY. A tap that did not change the status is still a row, with
`applied = false` and the reason — so the office can see that Dana pressed
*Available* at 14:05 while it had her *Unavailable* (the office's word wins,
decision log FB-033), or that an offline *On break* from 10:42 arrived after
the office's 11:00 change and was kept out of the status (a late tap never
overwrites a newer change).

`at` is the moment of the TAP, moved onto the server's clock (FB-014,
`core.device_clock`) — never the moment it arrived. `key` is the handset's
key minted at capture: a resend answers the first row and writes nothing.

Off duty here is NOT End shift (D4 = B): End shift keeps its own record
(`work_technician_shift_ends`, BR-WRK-069). Nothing here is an address and
nothing here is money.
"""

from __future__ import annotations

from django.db import models

from core.dbfields import uuid7_pk

#: The three things the phone may say, as the server stores them.
VALUE_AVAILABLE = "available"
VALUE_ON_BREAK = "on_break"
VALUE_OFF_DUTY = "off_duty"
VALUES = (VALUE_AVAILABLE, VALUE_ON_BREAK, VALUE_OFF_DUTY)

#: Why a tap did not move the status.
NOT_APPLIED_OFFICE_UNAVAILABLE = "office_unavailable"
NOT_APPLIED_NEWER_CHANGE = "newer_change"
NOT_APPLIED_SHIFT_ENDED = "shift_ended"
NOT_APPLIED_REASONS = (NOT_APPLIED_OFFICE_UNAVAILABLE, NOT_APPLIED_NEWER_CHANGE, NOT_APPLIED_SHIFT_ENDED)


class TechnicianAvailabilityChange(models.Model):
    """One availability tap from the phone."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    technician = models.ForeignKey(
        "work.Technician",
        on_delete=models.PROTECT,
        db_column="technician_id",
        related_name="+",
    )
    #: `available` · `on_break` · `off_duty`.
    value = models.TextField()
    #: The tap, on the server's clock.
    at = models.DateTimeField()
    #: The handset's key, minted at capture (hard rule 6).
    key = models.TextField()
    #: `technicians.status` when this arrived.
    previous_status = models.TextField(default="")
    #: Did this tap move `technicians.status`?
    applied = models.BooleanField(default=True)
    #: Empty when applied; else one of `NOT_APPLIED_REASONS`.
    not_applied_reason = models.TextField(default="", blank=True)
    changed_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True, db_column="changed_by", related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "technician_availability_changes"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "key"], name="uq_tech_availability_key"),
            models.CheckConstraint(condition=models.Q(value__in=VALUES), name="ck_tech_availability_value"),
        ]
        indexes = [
            models.Index(fields=["tenant", "technician", "at"], name="ix_tech_availability_at"),
        ]
