# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-044 (offline capture and one sync) · US-WRK-045 (the close
#           inside the batch).  Screens: Work-012, Work-010
# Rules:    BR-WRK-042 (queued locally with a per-item idempotency key; a
#           re-sync adds nothing) · BR-WRK-036 (the marker says what is
#           waiting) · CLAUDE.md hard rule 1 (tenant scoping; RLS FORCE in
#           work/0019) · hard rule 14 (a savepoint per item — sync.py)
# Tests:    06-backend/tests/test_us_wrk_044_sync.py ·
#           06-backend/tests/test_us_wrk_044_sync_pg.py (the ONLY place the
#           savepoint is real — see the class docstring)
# Impacts:  apps/work/sync.py (the only writer) · apps/work/models.py (imports
#           this so Django registers it) · apps/work/migrations/0018, 0019
# ───────────────────────────────────────────────────────
"""`work_sync_receipts` — the server's memory of what it has already accepted.

A NEW FILE RATHER THAN A NEW BLOCK IN `models.py`, for wave K's reason
────────────────────────────────────────────────────────────────────────────
`models.py` is 1,900 lines with several CR-070 lanes editing it, and a pathspec
commit takes the WHOLE working-tree content of every path it names (hard-won law
11, mechanism two). One new table does not need to carry that risk.
"""

from django.db import models

from core.dbfields import uuid7_pk

#: Every act a phone can queue. The vocabulary is a CONSTANT and deliberately
#: closed: a kind the server does not recognise is an item nothing will ever
#: apply, and answering *accepted* over one would be the exact lie
#: `queue_document`'s own docstring is written against.
#:
#: ⚠ **THE ORDER OF THIS TUPLE IS NOT THE ORDER OF APPLICATION.** The batch is
#: applied in the phone's CAPTURE order, never sorted by kind — `US-WRK-044`
#: TC-5 and `BR-WRK-037` between them mean the server must be able to REFUSE a
#: close that arrives before the safety row it is gated on, and a server that
#: helpfully re-sorted the batch would silently repair a tampered client and
#: prove nothing.
ITEM_KINDS = (
    "safety_tick",
    "task_tick",
    "reading",
    "material",
    "attachment",
    "signature",
    "close",
    # CR-168-BRC10 §F (PO 2026-10-04): a photo DECLARATION travels in the data
    # page; the server creates its link in the same save (`photo_links`).
    "photo",
)
#: What a RECEIPT may name: every item kind, plus `unrecognised` — an item
#: whose kind the server did not know is STORED as received and flagged, never
#: dropped (TECHNICIAN SYNC DESIGN (2)); its real kind is in `received`.
RECEIPT_KINDS = (*ITEM_KINDS, "unrecognised")

#: What one item's application ended as. Three values and no boolean, because
#: `US-WRK-044` TC-3 needs *this one was a duplicate* and *this one was refused*
#: to be different answers: a duplicate is the offline queue working correctly
#: and a refusal is something the technician has to see.
RESULT_ACCEPTED = "accepted"
RESULT_DUPLICATE = "duplicate"
RESULT_REFUSED = "refused"


class WorkSyncReceipt(models.Model):
    """One item the server accepted, and the proof it will not accept it twice.

    ⚠ **THIS TABLE IS THE WHOLE OF `BR-WRK-042` AND THE ROW IS WRITTEN INSIDE
    THE SAME SAVEPOINT AS THE ACT IT RECORDS.** Written after, in a second
    statement outside the item's savepoint, and a crash between the two makes
    the act happen twice on the next sync — which is the failure the column
    exists to prevent, reintroduced by the code that was supposed to prevent it.

    ⚠ **SCOPED `(tenant, work_order, key)`, THE SHAPE WAVE K CHOSE FOR
    `work_order_attachments` AND FOR ITS REASONS.** Two handsets can
    independently mint the same short key, and the order is the natural
    boundary because a key only ever means *this act, on this job*. It is also
    what `J65` step 13 asserts across tenants: a Lone Star Ridge key equal to a
    Brazos Bend key is **not** a duplicate, and the tenant column plus the RLS
    policy in `work/0019` are the two layers that make that true.

    ⚠ **`seq` IS THE PHONE'S POSITION IN ITS OWN QUEUE AND IS RECORDED, NEVER
    TRUSTED.** It is what a supervisor reads when a batch half-applied — *item
    5 of 20 was the duplicate* — and it is NOT used to order anything: the
    server applies the list in the order the list arrived. Storing it lets the
    two disagree visibly instead of silently.

    ⚠ **`captured_at` (THE HANDSET) AND `created_at` (THE SERVER) ARE TWO
    COLUMNS**, for `work_order_attachments.taken_at`'s reason one level up:
    after an offline day they are 16:07 and 17:40, and every question a
    supervisor asks about a disputed close is about the first one.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    work_order = models.ForeignKey(
        "work.WorkOrder",
        on_delete=models.CASCADE,
        db_column="work_order_id",
        related_name="sync_receipts",
    )
    #: Minted on the handset at capture. See the class docstring.
    key = models.TextField()
    kind = models.TextField()  # ITEM_KINDS
    #: The phone's own position for this item in this job's queue.
    seq = models.IntegerField(null=True, blank=True)
    #: The shutter/tap moment on the handset — never the moment of arrival.
    captured_at = models.DateTimeField(null=True, blank=True)
    #: When the server accepted it. `auto_now_add`, so it cannot be back-dated
    #: by a payload.
    accepted_at = models.DateTimeField(auto_now_add=True)
    accepted_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="accepted_by",
        related_name="+",
    )

    # ── CR-168-BRC10 §F · the technician API (`work/0035`) ─────────────────
    #: `BR-WRK-059` — WHO captured this item, from THAT technician's capture
    #: token, never from whoever was signed in when the batch arrived. On a
    #: shared tablet X captures, signs out, Y signs in and the batch syncs
    #: under Y's session: this column says X. NULL on a batch sent with no
    #: token (the session path, where the sender IS the captor).
    captured_by_technician = models.ForeignKey(
        "work.Technician",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="captured_by_technician_id",
        related_name="+",
    )
    #: `BR-WRK-061` — WHERE, with the fix's own accuracy BESIDE the point and
    #: the moment the fix was taken (which is not `captured_at`: a precise fix
    #: can arrive ~180 s after it was asked for). All four NULL when the item
    #: carried no location.
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    accuracy_m = models.DecimalField(max_digits=9, decimal_places=1, null=True, blank=True)
    fix_at = models.DateTimeField(null=True, blank=True)
    #: TECHNICIAN SYNC DESIGN (2) — *no data record is ever dropped*. An item
    #: that could not be applied for a STATE reason (the job was reassigned,
    #: cancelled or accepted while the phone was offline; the captor is not
    #: the assignee) or that arrived malformed is STORED here as received and
    #: flagged with the reason for the office — never refused, never lost.
    #: NULL for an item that was applied normally.
    needs_review = models.TextField(null=True, blank=True)
    #: The item exactly as it arrived, kept only when `needs_review` is set so
    #: the office can see what the technician sent.
    received = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "work_sync_receipts"
        constraints = [
            #: `BR-WRK-042`. The uniqueness IS the promise — a re-sync of the
            #: same queue adds nothing because this constraint refuses it, not
            #: because any caller remembered to check first.
            models.UniqueConstraint(
                fields=["tenant", "work_order", "key"],
                name="uq_work_sync_receipts_key",
            ),
            #: An empty key is the shape a client takes when it did not think
            #: about this, and it would defeat the uniqueness above by making
            #: every unkeyed item collide with every other (wave K's own
            #: reasoning for `ck_work_order_attachments_key_present`).
            models.CheckConstraint(
                condition=~models.Q(key=""),
                name="ck_work_sync_receipts_key_present",
            ),
            models.CheckConstraint(
                condition=models.Q(kind__in=RECEIPT_KINDS),
                name="ck_work_sync_receipts_kind",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "work_order", "seq"], name="ix_wo_sync_receipts_order"),
        ]
