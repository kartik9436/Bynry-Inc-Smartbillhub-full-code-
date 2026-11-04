# ── Trace ──────────────────────────────────────────────
# Change:   CR-183-BRC10 — temporary stop (PO rulings B1–B4, 2026-10-14).
# Rules:    BR-CUS-1120 (a temporary stop: base charge only during the hold, an
#           optional field visit, the customer may end it early) · BR-CUS-1121
#           (at least 10 days, at most 12 months — tenant settings) · BR-CUS-055
#           (`vacation_hold` is class `billable_base_only`) · CLAUDE.md hard
#           rule 1 (tenant scoped, RLS in `0084`)
# Tests:    06-backend/tests/test_cr183_temporary_stop.py
# ───────────────────────────────────────────────────────
"""**`temporary_stops` — one row per hold on an account: asked, scheduled, on, ended.**

⚠ **WHY A TABLE AND NOT COLUMNS ON `service_requests`.** A hold outlives the
request that asked for it: it is scheduled, it starts on its own, a clerk may
move its dates, and a SECOND request (*Restart my service now*, B4) may end it.
A clerk may also start one at the counter with no request at all (T7). So the
hold is its own record and the requests POINT at it — `request` is the ask that
started it, `restart_request` the ask that ended it early.

⚠ **THE PORTAL ASK'S FACTS LIVE HERE, NOT ONLY IN A SENTENCE.** Until
`CR-183-BRC10` the account, the dates and the reason travelled only inside
`service_requests.what_they_said`, so staff saw *Not yet classified* and could
approve the ask only as a New connection or a Move-in. The sentence still goes
to the clerk; the row is what the product reads.

STATUS, and the only moves between them (`temporary_stop.py` is the one writer):

    requested ──approve──▶ scheduled ──stop date──▶ on_hold ──restart date──▶ ended
        │                      │                       │
        └─refuse─▶ refused     └─cancel─▶ cancelled    └─end early─▶ ended

`requested` exists only for a portal ask; a clerk's own stop starts `scheduled`.
⚠ **THE ACCOUNT STAYS OPEN THE WHOLE TIME AND NO SERVICE AGREEMENT IS TOUCHED.**
The only account column a hold writes is `status` (`vacation_hold` and back).
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.dbfields import uuid7_pk

STATUS_REQUESTED = "requested"
STATUS_SCHEDULED = "scheduled"
STATUS_ON_HOLD = "on_hold"
STATUS_ENDED = "ended"
STATUS_REFUSED = "refused"
STATUS_CANCELLED = "cancelled"
STATUSES: tuple[str, ...] = (
    STATUS_REQUESTED,
    STATUS_SCHEDULED,
    STATUS_ON_HOLD,
    STATUS_ENDED,
    STATUS_REFUSED,
    STATUS_CANCELLED,
)
#: The statuses in which a hold is still going to happen or is happening.
LIVE_STATUSES: tuple[str, ...] = (STATUS_SCHEDULED, STATUS_ON_HOLD)

CHANNEL_PORTAL = "customer_portal"
CHANNEL_STAFF = "staff"
CHANNELS: tuple[str, ...] = (CHANNEL_PORTAL, CHANNEL_STAFF)


class TemporaryStop(models.Model):
    """One hold on one account. See the module docstring."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    account = models.ForeignKey(
        "customers.Account",
        on_delete=models.PROTECT,
        db_column="account_id",
        related_name="temporary_stops",
    )
    #: The ask that started it — NULL for a stop a clerk started at the counter.
    request = models.OneToOneField(
        "customers.ServiceRequest",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="request_id",
        related_name="temporary_stop",
    )
    #: B4 — the *Restart my service now* ask, while it waits and after.
    restart_request = models.OneToOneField(
        "customers.ServiceRequest",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="restart_request_id",
        related_name="temporary_stop_restart",
    )
    channel = models.TextField(default=CHANNEL_PORTAL)
    status = models.TextField(default=STATUS_REQUESTED)
    #: The first day on hold.
    stop_from = models.DateField()
    #: The first day back on. NULL only on a portal ask that gave none —
    #: approval refuses a hold with no restart date (BR-CUS-1121's maximum).
    restart_on = models.DateField(null=True, blank=True)
    #: The customer's own words, verbatim.
    reason = models.TextField(null=True, blank=True)
    #: B2 — the clerk's tick on approval.
    field_visit_needed = models.BooleanField(default=False)
    #: The two work orders B2 raises, by NUMBER (B14 rule 31).
    shutoff_order_no = models.TextField(null=True, blank=True)
    turnon_order_no = models.TextField(null=True, blank=True)
    approved_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="approved_by",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    #: When the job (or an approval dated today) actually moved the account.
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    #: True when it ended before `restart_on` was first set to — a clerk's
    #: *End now* or an approved *Restart my service now*.
    ended_early = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "customers"
        db_table = "temporary_stops"
        indexes = [
            models.Index(fields=["tenant", "account"], name="ix_temporary_stops_account"),
            models.Index(fields=["tenant", "status"], name="ix_temporary_stops_status"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=STATUSES), name="ck_temporary_stops_status"
            ),
            models.CheckConstraint(
                condition=Q(channel__in=CHANNELS), name="ck_temporary_stops_channel"
            ),
            models.CheckConstraint(
                condition=Q(restart_on__isnull=True) | Q(restart_on__gt=models.F("stop_from")),
                name="ck_temporary_stops_restart_after_stop",
            ),
        ]
