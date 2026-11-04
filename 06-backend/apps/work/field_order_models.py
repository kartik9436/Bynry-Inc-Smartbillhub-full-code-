# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 Phase 13, lane S-ORDER — T-37 (reopen versus
#           follow-on), T-38 (a second technician with their own labour
#           record), T-42 (field-raised orders).
# Rules:    BR-FLD-00008 (R8 labour per person, cost is the sum, the lead
#           closes) · BR-FLD-00009 (R9 travel and labour are separate clocks,
#           both correctable) · BR-FLD-00021/22 (R21 a reconnect is a new
#           order; R22 reopen only before the office accepts) · BR-FLD-00023/24
#           (R23 a field-raised reconnect lands pending; R24 no number until it
#           syncs) · BR-FLD-00112 (R112 the order takes its own copy and stamps
#           the version) · hard rule 1 (tenant scope; RLS FORCE in work/0039) ·
#           hard rule 6's shape (idempotent on a key minted at capture)
# Tests:    06-backend/tests/test_cr187_order_*.py
# Impacts:  apps/work/field_labour.py · field_reopen.py · field_raise.py ·
#           migrations/0039_cr187_field_orders.py
# ───────────────────────────────────────────────────────
"""Three tables the field app's order acts need, and none of them is a bill.

Kept beside `models.py` and imported from it, the way `evidence_models.py`,
`rules_models.py` and `sync_models.py` already are, so Django registers them
and `G78` reads them as Work's own (it reads every `ClassDef` under
`apps/work`, `DEF-WRK-4032`).

WHY THESE ARE WORK'S TABLES AND NOT COLUMNS ON `work_orders`
------------------------------------------------------------
`work_orders` lives in `apps/metering/connections.py` (`03-field-map.md` §4,
task T-43 moves it) and its CHECK constraints are metering's migrations. A
column added there is a metering migration written from a Work lane. Each fact
below is ALSO genuinely many-to-one against an order, which a column cannot
hold:

* **`work_order_labour`** — one row PER PERSON on a job (R8). Two technicians
  on one order are two time records; a single `minutes_on_site` column is the
  thing R8 says is wrong.
* **`work_order_reopens`** — the history of a job coming back: reopened by the
  technician before acceptance, sent back by the office, or followed on by a
  NEW linked order (R21, R22; E2E-17/18). Append-only, so the original order
  *"carries its history and its new work, with nothing overwritten"*.
  ⚠ **A FOLLOW-ON IS NOT `work_orders.follows_order_id`.** That column is
  provenance for a FAILURE (`BR-WRK-054`) and `EP-WRK-10`'s FIRST-TIME FIX
  counts it as a return visit; a reconnect after a disconnect is not a failed
  first visit, and writing it there would put it in the one report measuring
  failures.
* **`work_field_raises`** — an order raised on the handset: who, where (the
  position and its accuracy), what was needed, how urgent, what it was carried
  from, which template version the technician PICKED versus the one the server
  STAMPED, and the office's acceptance (E2E-16: *"appears in the office queue as
  raised in the field, pending acceptance"*).
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q

from core.dbfields import uuid7_pk

# ── work_order_labour ─────────────────────────────────────────────────────
LABOUR_ROLE_LEAD = "lead"
LABOUR_ROLE_HELPER = "helper"
LABOUR_ROLES: tuple[str, ...] = (LABOUR_ROLE_LEAD, LABOUR_ROLE_HELPER)


class WorkOrderLabour(models.Model):
    """`work_order_labour` — ONE PERSON's time on ONE job (R8, R9).

    The four moments are the design's three clocks plus the end of the work:
    `depart_at → arrive_at` is TRAVEL, `start_at → end_at` is LABOUR, and they
    are separate clocks (R9) — a person who sat in the van for twenty minutes
    waiting for a dog to be shut in is not twenty minutes of labour.

    ⚠ **THE LEAD'S ROW DOES NOT REPLACE THE ORDER'S OWN LABOUR LINE.** The
    order's `minutes_on_site` × `labour_rate_snapshot` is still the lead's
    priced line (`BR-WRK-020`, stamped at close by
    `services.snapshot_labour_rate_at_close`). A HELPER's row adds a SECOND
    priced line to the job's cost (`costing.work_order_cost_lines`), so the
    cost is the sum (R8). Pricing the lead twice — once from the order and once
    from this table — is the mistake this paragraph exists to stop.

    `rate_snapshot` / `labour_role` are stamped AT CLOSE for a helper, the
    moment `BR-WRK-020` fixes a rate, so a rate superseded next April cannot
    move a report signed today.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    work_order = models.ForeignKey(
        "work.WorkOrder",
        on_delete=models.PROTECT,
        db_column="work_order_id",
        related_name="labour_rows",
    )
    technician = models.ForeignKey(
        "work.Technician",
        on_delete=models.PROTECT,
        db_column="technician_id",
        related_name="labour_rows",
    )
    role = models.TextField(default=LABOUR_ROLE_HELPER)
    added_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="added_by",
        related_name="+",
    )
    #: The handset's key for the ADD (idempotency minted at capture, R45).
    key = models.TextField(null=True, blank=True)
    depart_at = models.DateTimeField(null=True, blank=True)
    arrive_at = models.DateTimeField(null=True, blank=True)
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)
    #: Stamped at close for a helper (`BR-WRK-020`); NULL means the line is not
    #: priced — *we cannot say*, never *free* (`costing.py`'s posture).
    rate_snapshot = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    labour_role = models.TextField(null=True, blank=True)
    #: How many times the person corrected their own clocks (R9). The values
    #: each correction replaced are in `audit_log` (`work.labour.corrected`).
    corrections = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "work_order_labour"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "work_order", "technician"],
                name="uq_work_order_labour_person",
            ),
            models.UniqueConstraint(
                fields=["tenant", "key"],
                condition=Q(key__isnull=False),
                name="uq_work_order_labour_key",
            ),
            models.CheckConstraint(
                condition=Q(role__in=LABOUR_ROLES), name="ck_work_order_labour_role"
            ),
            models.CheckConstraint(
                condition=Q(arrive_at__isnull=True)
                | Q(depart_at__isnull=True)
                | Q(arrive_at__gte=models.F("depart_at")),
                name="ck_work_order_labour_travel_forward",
            ),
            models.CheckConstraint(
                condition=Q(end_at__isnull=True)
                | Q(start_at__isnull=True)
                | Q(end_at__gt=models.F("start_at")),
                name="ck_work_order_labour_work_forward",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "work_order"], name="ix_wo_labour_order"),
        ]


# ── work_order_reopens ────────────────────────────────────────────────────
REOPEN_BY_TECHNICIAN = "technician_reopen"
REOPEN_BY_OFFICE = "office_reopen"
FOLLOW_ON = "follow_on"
REOPEN_KINDS: tuple[str, ...] = (REOPEN_BY_TECHNICIAN, REOPEN_BY_OFFICE, FOLLOW_ON)


class WorkOrderReopen(models.Model):
    """`work_order_reopens` — a job came back, and which of the two ways (R21,
    R22, E2E-17, E2E-18). **APPEND-ONLY**: `work/0039` puts a `BEFORE UPDATE OR
    DELETE` trigger on it, the `work/0009` shape, so *"nothing overwritten"* is a
    database fact rather than a sentence here (hard-won law 1).

    `prior` is what the close said BEFORE it was undone — state, dispatch
    state, outcome, completion time — because a reopen clears those on the
    order and the history must still be able to say *it was closed Passed at
    09:58 and reopened at 10:14 for a missed step*.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    work_order = models.ForeignKey(
        "work.WorkOrder",
        on_delete=models.PROTECT,
        db_column="work_order_id",
        related_name="reopen_rows",
    )
    kind = models.TextField()
    reason = models.TextField()
    note = models.TextField(null=True, blank=True)
    by_user = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="by_user",
        related_name="+",
    )
    by_technician = models.ForeignKey(
        "work.Technician",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="by_technician_id",
        related_name="+",
    )
    prior = models.JSONField(default=dict, blank=True)
    follow_on_order = models.ForeignKey(
        "work.WorkOrder",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="follow_on_order_id",
        related_name="follows_on_from",
    )
    key = models.TextField(null=True, blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "work_order_reopens"
        constraints = [
            models.CheckConstraint(
                condition=Q(kind__in=REOPEN_KINDS), name="ck_work_order_reopens_kind"
            ),
            models.CheckConstraint(
                condition=~Q(kind=FOLLOW_ON) | Q(follow_on_order__isnull=False),
                name="ck_work_order_reopens_follow_on_names_order",
            ),
            models.UniqueConstraint(
                fields=["tenant", "key"],
                condition=Q(key__isnull=False),
                name="uq_work_order_reopens_key",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "work_order", "at"], name="ix_wo_reopens_order"),
        ]


# ── work_field_raises ─────────────────────────────────────────────────────
FIELD_RAISE_PENDING = "pending"
FIELD_RAISE_ACCEPTED = "accepted"
FIELD_RAISE_REFUSED = "refused"
FIELD_RAISE_STATUSES: tuple[str, ...] = (
    FIELD_RAISE_PENDING,
    FIELD_RAISE_ACCEPTED,
    FIELD_RAISE_REFUSED,
)

URGENCY_NORMAL = "normal"
URGENCY_SAME_DAY = "same_day"
URGENCY_EMERGENCY = "emergency"
#: FF-37's *How urgent* — the three words it draws. Stored as SAID; they do
#: NOT set the order's priority (which tenant priority *Same day* means is
#: unruled — see `field_raise.py`).
URGENCIES: tuple[str, ...] = (URGENCY_NORMAL, URGENCY_SAME_DAY, URGENCY_EMERGENCY)


class WorkFieldRaise(models.Model):
    """`work_field_raises` — an order raised on the handset (T-42, E2E-16).

    One row per order raised in the field, written in the SAME transaction as
    the order. `key` is the handset's own idempotency key minted at capture: a
    re-send after a crash answers the FIRST order, with its number, and raises
    nothing (R45; R24 — *"never mint a number the server might not honour"*,
    so the number exists only from the first successful send).

    `status` is the office's acceptance and is the field-raised QUEUE: every
    field raise lands `pending` and the office accepts or refuses it. A pending
    raise cannot be CLAIMED from the field (`field_claim.py`), which is what
    makes R23 hold for a reconnect — *"it lands as pending, never
    auto-scheduled, because it is a money decision"*.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    work_order = models.OneToOneField(
        "work.WorkOrder",
        on_delete=models.PROTECT,
        db_column="work_order_id",
        related_name="field_raise",
    )
    key = models.TextField()
    raised_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="raised_by",
        related_name="+",
    )
    raised_by_technician = models.ForeignKey(
        "work.Technician",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="raised_by_technician_id",
        related_name="+",
    )
    captured_at = models.DateTimeField(null=True, blank=True)
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    accuracy_m = models.DecimalField(max_digits=8, decimal_places=1, null=True, blank=True)
    need = models.TextField(null=True, blank=True)
    urgency = models.TextField(default=URGENCY_NORMAL)
    note = models.TextField(null=True, blank=True)
    carried_from = models.ForeignKey(
        "work.WorkOrder",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="carried_from_id",
        related_name="+",
    )
    template_version_picked = models.IntegerField(null=True, blank=True)
    template_version_stamped = models.IntegerField(null=True, blank=True)
    status = models.TextField(default=FIELD_RAISE_PENDING)
    decided_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="decided_by",
        related_name="+",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "work_field_raises"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "key"], name="uq_work_field_raises_key"),
            models.CheckConstraint(
                condition=Q(status__in=FIELD_RAISE_STATUSES), name="ck_work_field_raises_status"
            ),
            models.CheckConstraint(
                condition=Q(urgency__in=URGENCIES), name="ck_work_field_raises_urgency"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "created_at"], name="ix_field_raises_queue"),
        ]
