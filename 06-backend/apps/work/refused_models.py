# ── Trace ──────────────────────────────────────────────
# Change:   CR-194-BRC10 — refused field work is kept on BOTH the phone and the
#           server (PO 2026-10-26, *"store on both"*, amending 2026-10-21
#           *"back to the technician"* item 4)
# Rules:    BR-WRK-063 (as amended 2026-10-26) · BR-WRK-071 · CLAUDE.md hard
#           rules 1 (RLS ENABLE + FORCE, `work/0057`), 6 (one copy per key), 7
#           (every office act audited) · NFR-5 (no cap)
# Tests:    06-backend/tests/test_cr194_refused_field_work.py ·
#           06-backend/tests/test_cr194_refused_field_work_pg.py
# Impacts:  apps/work/models.py (one import line registers this) ·
#           apps/work/refused_items.py · work/0056, work/0057
# ───────────────────────────────────────────────────────
"""`work_refused_items` — the server's COPY of a field item it refused.

⚠ **A COPY, NEVER A RECEIPT.** `work_sync_receipts` is the duplicate check: a
key there answers *duplicate* and the phone drops the item. A refused item
must stay on the phone to be fixed and resent and must post exactly once when
it is (2026-10-21, which stands), so its copy lives in a table the sync's
duplicate read never looks at. Writing it as a receipt would spend the key and
silently lose the fixed work.

ONE ROW PER KEY, AND WHAT EACH COLUMN IS FOR
────────────────────────────────────────────────────────────────────────────
* `key` — the handset's key minted at capture (hard rule 6); unique per tenant,
  so a resend refused again updates this row (`refusal_count`,
  `last_refused_at`, the newest reason and payload) rather than adding one.
* `door` — `job` (#90 / the batch across jobs) or `reads` (a route reading).
* `payload` — what the phone sent, as sent, WITHOUT its `capture_token` (a
  credential is never stored).
* `status` — `open` (nobody has looked) · `reviewed` (the office looked and
  noted it) · `applied` (the office applied it to the job) · `applied_later`
  (the technician's fixed resend posted under the same key).
* `photo_ids` / `attachment_ids` — the photographs refused with it: declared
  ids still on the phone, and delivered attachments whose bytes are kept.

⚠ **NO ADDRESS COLUMN** (hard rule 8): `lat`/`lng` are where the PHONE was
(`BR-MET-1202`), never the property's place.
"""

from __future__ import annotations

from django.db import models
from django.db.models import Q

from core.dbfields import uuid7_pk

DOOR_JOB = "job"
DOOR_READS = "reads"
DOORS: tuple[str, ...] = (DOOR_JOB, DOOR_READS)

STATUS_OPEN = "open"
STATUS_REVIEWED = "reviewed"
STATUS_APPLIED = "applied"
STATUS_APPLIED_LATER = "applied_later"
STATUSES: tuple[str, ...] = (STATUS_OPEN, STATUS_REVIEWED, STATUS_APPLIED, STATUS_APPLIED_LATER)
#: A copy the office can still act on.
STATUSES_ACTIONABLE: tuple[str, ...] = (STATUS_OPEN, STATUS_REVIEWED)


class WorkRefusedItem(models.Model):
    """`work_refused_items` — one refused field item, kept for the office."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    key = models.TextField()
    door = models.TextField(default=DOOR_JOB)
    kind = models.TextField()
    #: The job it was for — null for a route reading, and for an item that
    #: named no job of this tenant (nothing to hang it on).
    work_order = models.ForeignKey(
        "work.WorkOrder", on_delete=models.PROTECT, null=True, blank=True,
        db_column="work_order_id", related_name="+",
    )
    #: WHO captured it — from the item's capture token (an expired one too),
    #: else the courier who sent it. Never inferred from the job's assignee.
    captor = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True,
        db_column="captor_id", related_name="+",
    )
    captor_technician = models.ForeignKey(
        "work.Technician", on_delete=models.PROTECT, null=True, blank=True,
        db_column="captor_technician_id", related_name="+",
    )
    payload = models.JSONField(default=dict, blank=True)
    captured_at = models.DateTimeField(null=True, blank=True)
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    reason_code = models.TextField(default="", blank=True)
    message_key = models.TextField(default="", blank=True)
    params = models.JSONField(default=dict, blank=True)
    photo_ids = models.JSONField(default=list, blank=True)
    attachment_ids = models.JSONField(default=list, blank=True)
    first_refused_at = models.DateTimeField()
    last_refused_at = models.DateTimeField()
    refusal_count = models.PositiveIntegerField(default=1)
    status = models.TextField(default=STATUS_OPEN)
    reviewed_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True,
        db_column="reviewed_by", related_name="+",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(default="", blank=True)
    applied_by = models.ForeignKey(
        "identity.User", on_delete=models.PROTECT, null=True, blank=True,
        db_column="applied_by", related_name="+",
    )
    applied_at = models.DateTimeField(null=True, blank=True)
    applied_work_order = models.ForeignKey(
        "work.WorkOrder", on_delete=models.PROTECT, null=True, blank=True,
        db_column="applied_work_order_id", related_name="+",
    )

    class Meta:
        db_table = "work_refused_items"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "key"], name="uq_work_refused_items_key"),
            models.CheckConstraint(
                condition=Q(status__in=list(STATUSES)), name="ck_work_refused_items_status"
            ),
            models.CheckConstraint(condition=Q(door__in=list(DOORS)), name="ck_work_refused_items_door"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "-last_refused_at"], name="ix_work_refused_status"),
        ]
