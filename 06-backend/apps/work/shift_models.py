# ── Trace ──────────────────────────────────────────────
# Change:   CR-193-BRC10 — MQ-040 STEP 1 (decision log 2026-10-26, *"MQ-040:
#           shifts and timesheet, STEP 1 approved"*): working days per
#           technician with one-day exceptions, End shift, Submit the day.
# Rules:    CLAUDE.md hard rules 1 (RLS ENABLE + FORCE, `work/0054`), 6
#           (idempotent on the handset's key), 7 (every act audited) · NFR-5
#           (no cap: any number of exceptions and submitted days)
# Tests:    06-backend/tests/test_cr193_shifts.py ·
#           06-backend/tests/test_cr193_shifts_pg.py
# Impacts:  apps/work/models.py (one import line registers these) ·
#           apps/work/shifts.py · work/0053, work/0054
# ───────────────────────────────────────────────────────
"""A technician's WEEK and what they hand in at the end of a day.

FOUR TABLES, EACH ONE FACT
────────────────────────────────────────────────────────────────────────────
* `work_technician_working_days` — WHICH weekdays this person works. One row
  per technician, created on first save; NO ROW MEANS MONDAY TO FRIDAY (the
  PO's worked example: *"D. Ortiz Mon–Fri 07:00–15:30"*), so nobody has to
  back-fill a row per technician for the default to hold. The daily WINDOW is
  not here: it is `technicians.shift_start/shift_end`, which already exist and
  stay the one place the window lives.
* `work_technician_day_exceptions` — ONE DAY that is not like the rule: the
  person is OFF that day, or works a DIFFERENT WINDOW. At most one per person
  per date. A note is optional and is shown to the technician.
* `work_technician_shift_ends` — the technician pressed *End shift*. One per
  person per day; the handset's key makes a resend harmless.
* `work_timesheet_submissions` — *Submit the day*. A SNAPSHOT of that day's
  labour per job and travel, taken from `work_order_labour` at the moment it
  was submitted, so a correction the office makes to a clock afterwards does
  not silently rewrite what the technician handed in. One per person per day;
  a resubmission answers the first (decision log: *"a submitted timesheet day
  is not editable on the phone (the office corrects it)"*).

Nothing here is an address (hard rule 8) and nothing here is money.
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q

from core.dbfields import uuid7_pk

#: Monday … Sunday as bits 0 … 6 of `days`. Python's `date.weekday()` order.
WEEKDAY_CODES: tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
#: Monday to Friday — the default when a technician has no row.
DEFAULT_DAYS_MASK = 0b0011111

EXCEPTION_OFF = "off"
EXCEPTION_WINDOW = "window"
EXCEPTION_KINDS: tuple[str, ...] = (EXCEPTION_OFF, EXCEPTION_WINDOW)


class TechnicianWorkingDays(models.Model):
    """`work_technician_working_days` — the weekdays one technician works."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    technician = models.ForeignKey(
        "work.Technician",
        on_delete=models.PROTECT,
        db_column="technician_id",
        related_name="+",
    )
    #: Bit n set = `WEEKDAY_CODES[n]` is a working day. 0 is lawful (a person
    #: who works no fixed day — every day they work is an exception).
    days = models.PositiveSmallIntegerField(default=DEFAULT_DAYS_MASK)
    updated_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True, db_column="updated_by", related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "work_technician_working_days"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "technician"], name="uq_work_tech_working_days"),
            models.CheckConstraint(condition=Q(days__lte=127), name="ck_work_tech_working_days_mask"),
        ]


class TechnicianDayException(models.Model):
    """`work_technician_day_exceptions` — one day off, or one different window."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    technician = models.ForeignKey(
        "work.Technician",
        on_delete=models.PROTECT,
        db_column="technician_id",
        related_name="+",
    )
    day = models.DateField()
    kind = models.TextField()
    #: Only for `window`: both set and `start < end`; both NULL for `off`.
    start = models.TimeField(null=True, blank=True)
    end = models.TimeField(null=True, blank=True)
    note = models.TextField(default="", blank=True)
    created_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True, db_column="created_by", related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "work_technician_day_exceptions"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "technician", "day"], name="uq_work_tech_day_exception"),
            models.CheckConstraint(condition=Q(kind__in=EXCEPTION_KINDS), name="ck_work_tech_day_exception_kind"),
            models.CheckConstraint(
                condition=(
                    Q(kind=EXCEPTION_OFF, start__isnull=True, end__isnull=True)
                    | Q(kind=EXCEPTION_WINDOW, start__isnull=False, end__isnull=False, start__lt=models.F("end"))
                ),
                name="ck_work_tech_day_exception_window",
            ),
        ]
        indexes = [models.Index(fields=["tenant", "technician", "day"], name="ix_work_tech_day_exc_day")]


class TechnicianShiftEnd(models.Model):
    """`work_technician_shift_ends` — *End shift*, once per person per day."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    technician = models.ForeignKey(
        "work.Technician",
        on_delete=models.PROTECT,
        db_column="technician_id",
        related_name="+",
    )
    #: The technician's CALENDAR day, in the utility's zone.
    day = models.DateField()
    ended_at = models.DateTimeField()
    #: The handset's key, minted at capture (hard rule 6).
    key = models.TextField()
    #: `technicians.status` before this set it to `off_today` (R10's *who and when*).
    previous_status = models.TextField(default="")
    ended_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True, db_column="ended_by", related_name="+"
    )
    #: DEF-WRK-10615 (`work/0055`) — when this End shift STOPPED holding the
    #: technician's status: the morning return set them back to *on shift*
    #: (`shifts.morning_return`), or the office set a status by hand after it
    #: (`workforce.set_unavailable`). NULL = it still holds. Written once.
    settled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "work_technician_shift_ends"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "technician", "day"], name="uq_work_tech_shift_end_day"),
            models.UniqueConstraint(fields=["tenant", "key"], name="uq_work_tech_shift_end_key"),
        ]


class TimesheetSubmission(models.Model):
    """`work_timesheet_submissions` — one submitted day, as it was submitted."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    technician = models.ForeignKey(
        "work.Technician",
        on_delete=models.PROTECT,
        db_column="technician_id",
        related_name="+",
    )
    day = models.DateField()
    key = models.TextField()
    #: `[{order_id, order_no, labour_minutes, travel_minutes}]`, jobs in time order.
    lines = models.JSONField(default=list)
    jobs = models.PositiveIntegerField(default=0)
    labour_minutes = models.PositiveIntegerField(default=0)
    travel_minutes = models.PositiveIntegerField(default=0)
    submitted_at = models.DateTimeField()
    submitted_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True, db_column="submitted_by", related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "work_timesheet_submissions"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "technician", "day"], name="uq_work_timesheet_day"),
            models.UniqueConstraint(fields=["tenant", "key"], name="uq_work_timesheet_key"),
        ]
