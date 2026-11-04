# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 — the native field app's ROUTE READING server half
#           (`04-docs/05-modules/18-field-app/07-endpoints.md` N1, N5, N6, N12;
#           `03-field-map.md` §2.4–§2.5, the columns marked NEW).
# Story:    US-FLD-040 (1,000 readings captured offline, sent at once) ·
#           US-FLD-042 (an answer per item) · US-FLD-054 (a route downloaded
#           whole) · US-FLD-060 (eight seeded can't-read reasons, the
#           utility's own list) · US-FLD-061 (a meter not on the route) ·
#           US-FLD-062 (one reader per route, nothing that forbids splitting)
#           Screens: RW-01, RW-03, RW-06, RW-09, RW-13, RW-15, RW-17, RW-18,
#           RW-19, RW-20, RW-25, RW-27
# Rules:    BR-FLD-00082 (R82 — the reasons are DATA, eight seeded) ·
#           BR-FLD-00084 (R84 — off-route is accepted and marked) ·
#           BR-FLD-00085 (R85 — a field-added meter is PENDING, photo
#           required, bills nothing until accepted) · BR-FLD-00087 (R87) ·
#           BR-FLD-00088 … 00096 (R88–R96 — what a reading carries; two
#           statuses never merged) · BR-WRK-063 (TECHNICIAN SYNC DESIGN (2) —
#           no field record is ever dropped) · CLAUDE.md hard rules 1, 3, 6, 8
# Tests:    06-backend/tests/test_cr187_reads_sync.py ·
#           06-backend/tests/test_cr187_reads_routes.py ·
#           06-backend/tests/test_cr187_reads_pg.py (law 14, real PostgreSQL)
# Impacts:  apps/metering/models.py (registers these by importing this file) ·
#           apps/metering/migrations/0077_cr187_field_reads.py
# ───────────────────────────────────────────────────────
"""What a reader did on a route, kept as the reader did it.

WHY A TABLE BESIDE `meter_reads` AND NOT THIRTEEN COLUMNS ON IT
────────────────────────────────────────────────────────────────────────────
`03-field-map.md` §2.5 lists the NEW facts against `meter_reads` (position,
accuracy, both clocks, the reader's status, a can't-read reason, accepted-anyway,
off-route, how the meter was identified, a remark, an idempotency key). They
land HERE, in `field_reads`, one row per item a handset sent, and the committed
reading is pointed at by `meter_read_id`. Four facts decide it, each a rule
already signed:

  1. **A can't-read has no reading.** `meter_reads.current_value` NULL already
     MEANS an estimate (BR-MET-028). A *could not read — dog* written there
     would be read by every consumer as an estimate nobody made. So the reader's
     answer needs a home that is not a reading.
  2. **The idempotency key must be UNIQUE, and `meter_reads` cannot carry a
     unique key that omits `read_at`** — it is partitioned on it (DB-7), so
     every unique index must include the partition key. A key per handset item
     is unique on its own or it is not a key (hard rule 6).
  3. **`meter_reads` is append-only and is written by ONE function**
     (`services._post_row`) from a STAGED row. Thirteen capture columns would
     have to be threaded through `read_import_rows` and `_post_row` for a
     source no file and no clerk ever has, which widens the one money-adjacent
     write path in this module for the sake of evidence nothing bills from.
  4. **No field record is ever dropped** (`BR-WRK-063`, PO 2026-10-04: *"we
     cant drop data record in sync process both ways"*). An item the read
     pipeline will not post — a figure below the last one, a unit that is not
     the register's, a meter the reader could not name — must still be STORED.
     It cannot be stored in `meter_reads` without being a reading. Here it is
     stored with `outcome = held` and the reason, for the office.

So the two statuses `R96` keeps apart live in two tables by construction:
`reader_status` here (*read · could_not_read · read_with_problem*) is what the
READER said; `meter_reads.status` is what the ENGINE decided. Nothing copies
one into the other.

A FIELD-ADDED METER IS A ROW HERE, NOT AN ASSET (R85)
────────────────────────────────────────────────────────────────────────────
`FieldMeterProposal` is the pending meter. No `assets` row exists until the
office accepts it, so it **bills nothing by construction** — there is no asset
for a bill run to find, no service point to stamp, no plan to price. This
module writes no other module's table (B1/B8, `BR-WRK-002`'s spirit): the
`assets` row is created by the assets module's own door when the office
accepts, and the readings held against the proposal then post. That acceptance
door is NOT built in this change (reported).

ONE READER PER ROUTE, AND NOTHING THAT FORBIDS TWO (R87)
────────────────────────────────────────────────────────────────────────────
No row here is unique on a route. A turn-in is keyed by the handset's own key,
not by (route, window), so two readers splitting a route each turn in their
half. `routes.assigned_to` is still the one FK it was; nothing here reads it as
"the only reader".
"""

from __future__ import annotations

from django.db import models
from django.db.models.functions import Lower

from core.dbfields import uuid7_pk

#: R96 — what the READER says happened. Three words, from the RW-13 board
#: (*READ*) and RW-17 (*Why not?*). The ENGINE's verdict is `meter_reads.status`.
READER_STATUSES: tuple[str, ...] = ("read", "could_not_read", "read_with_problem")
READER_READ = "read"
READER_COULD_NOT_READ = "could_not_read"
READER_READ_WITH_PROBLEM = "read_with_problem"

#: R83 — how the meter was identified. RW-11 scan, typed fallback, or picked
#: from the downloaded list.
IDENTIFIED_BY: tuple[str, ...] = ("scan", "typed", "listed")

#: R91 — the handset's own grading of its fix. Stored as sent; never a gate.
FIX_QUALITIES: tuple[str, ...] = ("good", "poor", "none")

#: R95 — a remark is spoken by default, typed as the fallback.
REMARK_SOURCES: tuple[str, ...] = ("voice", "typed")

#: RW-18 — the reader's answer when the meter in front of them is not the one
#: on the list. *I am at the wrong address* is a navigation on the handset and
#: never reaches the server as an answer.
MISMATCH_ANSWERS: tuple[str, ...] = ("swapped", "cannot_tell")

#: What the server did with the item. `posted` — a committed `meter_reads` row
#: exists (`meter_read_id`). `recorded` — a could-not-read with its reason; no
#: reading exists and none is invented. `awaiting_acceptance` — a reading on a
#: meter added in the field, kept until the office accepts the meter (R85).
#: `held` — stored as received and flagged for the office (BR-WRK-063).
OUTCOMES: tuple[str, ...] = ("posted", "recorded", "awaiting_acceptance", "held")
OUTCOME_POSTED = "posted"
OUTCOME_RECORDED = "recorded"
OUTCOME_AWAITING = "awaiting_acceptance"
OUTCOME_HELD = "held"

#: R85 — a proposal's life. Only `pending` is written by this change.
PROPOSAL_STATUSES: tuple[str, ...] = ("pending", "accepted", "declined")


class CantReadReason(models.Model):
    """R82 / BR-FLD-00082 — *"The reasons a meter cannot be read are DATA. Eight
    seeded, tenant-extensible, and never counted in code."*

    Built the way this module's other tenant vocabularies are (`premises_types`,
    `unit_types`, BR-TEN-036's lookup shape): seeded `is_system` rows that a
    utility may deactivate and never delete, plus the utility's own rows. The
    seed is `field_reads.SEED_CANT_READ_REASONS`, in the RW-17 board's order.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()  # BR-TEN-030: unique per tenant, case-insensitive
    name = models.TextField()
    sort_order = models.IntegerField(default=0)
    is_system = models.BooleanField(default=False)  # seeded: deactivatable, never deletable
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "metering"
        db_table = "cant_read_reasons"
        constraints = [
            models.UniqueConstraint(
                models.F("tenant"), Lower("code"), name="uq_cant_read_reasons_tenant_code_ci"
            ),
        ]


class FieldMeterProposal(models.Model):
    """R85 / BR-FLD-00085 — a meter a reader found that the system does not hold
    (RW-20 *Add a meter*: *"The office accepts it before it bills"*).

    ⚠ **NO ADDRESS COLUMN** (hard rule 8, `BR-FLD-00086`). The meter's place is
    the PREMISES the reader stood at, and its address is reached by walking to
    it — the same as every other entity. `unit` refines it by label when the
    reader knew which unit.

    ⚠ **A PHOTOGRAPH IS REQUIRED** (R85) and the server asks, so a handset that
    skipped it cannot create a proposal nobody can check: such an item is HELD
    rather than proposed.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: The handset's key for the add-meter item (hard rule 6).
    key = models.TextField()
    proposed_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="proposed_by",
        related_name="field_meter_proposals",
    )
    route = models.ForeignKey(
        "metering.Route", on_delete=models.PROTECT, null=True, blank=True, db_column="route_id"
    )
    premises = models.ForeignKey(
        "metering.Premises", on_delete=models.PROTECT, db_column="premises_id"
    )
    unit = models.ForeignKey(
        "metering.Unit", on_delete=models.PROTECT, null=True, blank=True, db_column="unit_id"
    )
    service_code = models.TextField()
    size_class = models.TextField(null=True, blank=True)
    badge = models.TextField(null=True, blank=True)
    serial_no = models.TextField(null=True, blank=True)
    #: The meter's own unit of measure as the reader recorded it (hard rule 3).
    unit_of_measure = models.TextField(null=True, blank=True)
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    accuracy_m = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    photo_ids = models.JSONField(default=list, blank=True)
    remark = models.TextField(null=True, blank=True)
    status = models.TextField(default="pending")
    #: Set by the acceptance door (NOT built in this change) — the assets row
    #: the office created from this proposal. Bare uuid: metering does not
    #: write assets, and the id arrives from the assets module's own door.
    accepted_asset_id = models.UUIDField(null=True, blank=True)
    decided_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="decided_by",
        related_name="decided_field_meter_proposals",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    device_captured_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "metering"
        db_table = "field_meter_proposals"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "key"], name="uq_field_meter_proposals_key"),
            models.CheckConstraint(
                condition=models.Q(status__in=PROPOSAL_STATUSES),
                name="ck_field_meter_proposals_status",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="ix_field_proposals_status"),
        ]


class FieldRead(models.Model):
    """One item a handset sent from a route — the receipt AND the record.

    The row is inserted FIRST, inside the item's own savepoint, and its unique
    `(tenant, key)` IS the duplicate check (hard rule 6): a retried batch, or
    two batches in flight carrying the same item, cannot both insert it. The
    `apps/work/sync.py` reasoning, applied unchanged.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: The idempotency key minted ON THE HANDSET at capture (hard rule 6).
    key = models.TextField()
    kind = models.TextField(default="reading")
    #: Who captured it — the signed-in reader. `imported_by` on `meter_reads` is
    #: an importer, not a reader (`03-field-map.md` §2.5).
    reader = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="reader_id",
        related_name="field_reads",
    )
    route = models.ForeignKey(
        "metering.Route", on_delete=models.PROTECT, null=True, blank=True, db_column="route_id"
    )
    #: The STOP — a premises, never a meter (R74 / BR-MET-033).
    premises = models.ForeignKey(
        "metering.Premises", on_delete=models.PROTECT, null=True, blank=True, db_column="premises_id"
    )
    #: The meter actually read. NULL when it could not be named (held).
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="asset_id",
        related_name="field_reads",
    )
    #: RW-18 — the meter the LIST said was here, when the reader found another.
    expected_asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="expected_asset_id",
        related_name="field_reads_expected",
    )
    proposal = models.ForeignKey(
        FieldMeterProposal,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="proposal_id",
        related_name="readings",
    )
    channel = models.TextField(default="total")
    #: The dial figure as the reader entered it. NULL on a could-not-read.
    value = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    #: The unit the handset SAID (hard rule 3). Compared with the register's own
    #: unit; the committed read is stamped with the register's, never this.
    unit = models.TextField(null=True, blank=True)
    reader_status = models.TextField(null=True, blank=True)
    #: A `cant_read_reasons.code` of this tenant.
    cant_read_reason = models.TextField(null=True, blank=True)
    #: R80 / R11 — the reader saw the out-of-range warning and took it anyway.
    accepted_anyway = models.BooleanField(default=False)
    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    accuracy_m = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    fix_quality = models.TextField(null=True, blank=True)
    #: R90 — computed HERE from the stored point of the unit (or its premises),
    #: never trusted from the payload.
    metres_from_record = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    #: R92 — the phone's clock at capture …
    device_captured_at = models.DateTimeField(null=True, blank=True)
    #: … and the server's on arrival.
    received_at = models.DateTimeField(auto_now_add=True)
    identified_by = models.TextField(null=True, blank=True)
    scanned_code = models.TextField(null=True, blank=True)
    mismatch_answer = models.TextField(null=True, blank=True)
    #: R84 — decided by the SERVER against the route's current meters.
    off_route = models.BooleanField(default=False)
    read_method = models.TextField(null=True, blank=True)
    remark = models.TextField(null=True, blank=True)
    remark_source = models.TextField(null=True, blank=True)
    photo_ids = models.JSONField(default=list, blank=True)
    outcome = models.TextField(default=OUTCOME_HELD)
    held_reason = models.TextField(null=True, blank=True)
    held_detail = models.JSONField(null=True, blank=True)
    #: The committed reading. Bare uuid: `meter_reads` is partitioned and has
    #: no unique index on `id` alone (the `superseded_by_id` disposition).
    meter_read_id = models.UUIDField(null=True, blank=True)
    read_import_batch_id = models.UUIDField(null=True, blank=True)
    #: Everything the handset sent, as sent — an older or newer build's extra
    #: fields survive (`07-endpoints.md` §0 rule 1, additive only).
    received_payload = models.JSONField(default=dict, blank=True)
    #: MQ-033 (`CR-192-BRC10`, `BR-MET-1215`) — the read-format VERSION this
    #: reading's answers were asked under, as the handset named it (NULL: no
    #: format, or one this server does not hold). The answers are `read_answers`.
    read_format_version = models.ForeignKey(
        "metering.ReadFormatVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="read_format_version_id",
        related_name="+",
    )
    #: MQ-033 — *"never cause a reading to be dropped (stored and flagged
    #: instead)"*: True when any answer carries an `issue`. The READING is
    #: judged exactly as before; this flag is about its answers only.
    answers_need_review = models.BooleanField(default=False)
    #: FB-003 (`DEF-MET-10633`, PO 2026-10-27) — on a row of kind `position`
    #: only: the READING or route PHOTO this late position belongs to. The
    #: reading's own `lat`/`lng` stay as they were sent (none) — a position
    #: that arrived after the save is a SEPARATE fact with its own time
    #: (`device_captured_at` = the fix's), never written as if present at save.
    #: At most ONE per target (`uq_field_reads_one_late_position`): the first
    #: fix within 5 minutes is the one kept.
    position_for = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="position_for_id",
        related_name="late_positions",
    )
    #: FB-019 (`DEF-FLD-10637`, PO report 2026-10-28) — on a row of kind
    #: `photo` only: the READING a photograph was added to AFTER it was saved,
    #: named by the declaration's `reading_key`. A photo saved WITH its reading
    #: is in that reading's `photo_ids` and leaves this NULL; the reading's own
    #: row is never touched. Many photos may name one reading.
    photo_for = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="photo_for_id",
        related_name="added_photos",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "metering"
        db_table = "field_reads"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "key"], name="uq_field_reads_key"),
            models.UniqueConstraint(
                fields=["tenant", "position_for"],
                condition=models.Q(position_for__isnull=False),
                name="uq_field_reads_one_late_position",
            ),
            models.CheckConstraint(
                condition=models.Q(outcome__in=OUTCOMES), name="ck_field_reads_outcome"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "route", "received_at"], name="ix_field_reads_route"),
            models.Index(fields=["tenant", "outcome"], name="ix_field_reads_outcome"),
        ]


class FieldRouteTurnIn(models.Model):
    """RW-25 … RW-27 — a reader turned a route in. **Not a gate**: *"Turning in
    does not close the cycle. The office chases whatever is missing"*. The row
    records that it happened and what the handset said it held; the receipt is
    recomputed from `field_reads` every time it is asked for."""

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    key = models.TextField()
    route = models.ForeignKey("metering.Route", on_delete=models.PROTECT, db_column="route_id")
    reader = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="reader_id",
        related_name="field_route_turn_ins",
    )
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    handset_counts = models.JSONField(default=dict, blank=True)
    device_captured_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "metering"
        db_table = "field_route_turn_ins"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "key"], name="uq_field_route_turn_ins_key"),
        ]
        indexes = [
            models.Index(fields=["tenant", "route", "received_at"], name="ix_field_turn_ins_route"),
        ]



class FieldReadPhoto(models.Model):
    """A ROUTE photograph's link — `DEF-FLD-10357` (lane INTEGRATE-2,
    2026-10-21). Before it, a route photo had no door: the handset declared it
    to the reads door as a `photo` item, the door stored that declaration as a
    held *reading* with no reader status (one bogus reading in the office's
    queue per photograph), and the bytes were refused by the job door
    (`work/mobile/photos/{id}` knows only a job's links, `work_photo_links`
    requires a work order). A route has no work order, so the job door's table
    cannot hold it.

    THE SAME TWO-STEP SHAPE AS THE JOB DOOR (`apps/work/photo_links.py`, PO
    2026-10-04: *"link you ahve to create along with data record and pass it to
    async job"*): the photograph is DECLARED in the data — a reads-door item of
    kind `photo` carrying the phone's own `photo_id` and the `sha256` of the
    bytes it will send — and this row is created in that item's savepoint and
    answered with its `upload_url`. The bytes follow to
    `PUT work/mobile/reads/photos/{photo_id}`, are checked against `sha256`,
    and are KEPT HERE (`data`) and the link marked `landed`; the reading that
    names the photograph carries its id in `field_reads.photo_ids`.

    ⚠ **THE BYTES STAY ON THIS ROW; NOTHING FILES THEM INTO THE DOCUMENT
    STORE YET.** `tenancy.document_store` has no document kind or source type
    for a route photograph, and adding one is that module's change, not this
    one. Reported. The bytes are durable (committed in PostgreSQL), which is
    what lets the handset delete its copy (R61, R125).

    Idempotent on `(tenant, photo_id)`: a re-declaration answers the same link;
    a second upload to a landed link adds nothing.
    """

    STATE_PENDING = "pending"
    STATE_LANDED = "landed"
    STATES = (STATE_PENDING, STATE_LANDED)

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: The PHONE's id for the photograph, minted at capture.
    photo_id = models.UUIDField()
    #: Hex sha256 the phone declared for the bytes it will send.
    sha256 = models.TextField()
    #: The declaring item's key (hard rule 6) — its `field_reads` receipt.
    key = models.TextField()
    #: Whose photograph — the CAPTOR (the item's capture token), never the courier.
    reader = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="reader_id",
        related_name="field_read_photos",
    )
    route = models.ForeignKey(
        "metering.Route", on_delete=models.PROTECT, null=True, blank=True, db_column="route_id"
    )
    state = models.TextField(default=STATE_PENDING)
    content_type = models.TextField(null=True, blank=True)
    data = models.BinaryField(null=True, blank=True)
    bytes_received = models.IntegerField(null=True, blank=True)
    device_captured_at = models.DateTimeField(null=True, blank=True)
    declared_at = models.DateTimeField(auto_now_add=True)
    landed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "metering"
        db_table = "field_read_photos"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "photo_id"], name="uq_field_read_photos_photo"),
            models.CheckConstraint(
                condition=models.Q(state__in=("pending", "landed")), name="ck_field_read_photos_state"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "route", "declared_at"], name="ix_field_read_photos_route"),
        ]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-FLD-040@fa5746815 (CR-187-BRC10 route-reading server lane — field map §2.4–§2.5)
# generated: 2026-10-21 by the CR-187 reads server lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(the native app lanes build the screens) F✔ G✔ H=deferred(PO 2026-08-09 — migration 0077 is 🔒 migration ordering, HUMAN-REVIEW-PENDING; ledger row owed by the coordinator)
# gates: see the lane report
# exceptions: capture facts live in `field_reads` beside `meter_reads`, not as columns on it — the four reasons are in the module docstring, REPORTED
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
