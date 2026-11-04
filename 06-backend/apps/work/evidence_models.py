# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-048 (three document kinds, and the compression that pays for
#           them) · US-WRK-036 (the signature, or the refusal) · US-WRK-049 (a
#           reading's photograph: the rule and the file are different columns) ·
#           US-WRK-047 (out-of-range flags, never refuses).  Screens: Work-033,
#           Work-012, Work-008
# Rules:    BR-WRK-046 (a signature is a printed name plus an image, with who
#           and when; a refusal records the decline reason and a photograph of
#           the door hanger INSTEAD) · BR-WRK-047 (three kinds; the row is
#           written on sync with a per-image idempotency key; compressed at
#           capture to 100 KB max) · BR-WRK-047a (the upload goes through the
#           application, not straight to the object store) · BR-WRK-048 (twelve
#           months, then an export before deletion — OQ-WRK-1496, PO 2026-09-04)
#           · CLAUDE.md hard rule 1 (tenant-scoped; RLS FORCE in work/0017) ·
#           hard rule 3 (a quantity carries its unit)
# Tests:    06-backend/tests/test_us_wrk_047_049_evidence.py ·
#           tests/test_us_wrk_048_evidence_pg.py (PostgreSQL 16)
# Impacts:  apps/work/migrations/0016_cr070_k_evidence.py + 0017_rls_force_evidence.py
#           · apps/work/work_documents.py · apps/work/evidence.py · apps/work/api.py
#           · apps/tenancy/document_models.py (33 → 36 kinds, 6 → 7 sources)
# ───────────────────────────────────────────────────────
"""What the phone sends back — a photograph, and a signature or a refusal.

WHY THIS IS ITS OWN FILE AND NOT THE END OF `models.py`
────────────────────────────────────────────────────────────────────────────
`apps/work/models.py` is 1,935 lines and three other CR-070 lanes are editing it
right now. A pathspec commit takes the WHOLE working-tree content of every path
it names (CLAUDE.md hard-won law 11, mechanism two), so appending two classes
there would put this lane's copy of a 1,935-line shared file on the branch and
silently revert whatever a sibling had pushed into it meanwhile — with a correct
file count, this lane's own hunks present, and nothing in the diff to notice.
Two new tables owe nobody that risk. `models.py` imports this module in one
line, which is the smallest edit that registers the models.

⚠ **BOTH TABLES ARE APPEND-ONLY, AND NOT BECAUSE HARD RULE 4 SAYS SO.**
Hard rule 4 names invoices, invoice lines, payments and journal entries; none of
these is a financial row and the rule does not reach them. They are append-only
because they are EVIDENCE, which is a different argument and a stronger one
here: the whole worth of a photograph of a meter dial is that it is what the
camera saw at 16:02 on 15 March. A row that can be edited afterwards answers
*what does somebody say was there now*, which is not a question anybody needs
answered. The refusal is enforced by a trigger in `work/0016` rather than by
this class, for the reason law 1 gives — a docstring claiming a guarantee is not
the guarantee.

⚠ **THE CORRECTION PATH IS A NEW ROW, AND IT ALREADY EXISTS.** Nothing here is
a dead end for a technician who photographs the wrong meter: they take another
photograph, which is another row with a later `taken_at`, and the checklist row
points at the new one. The mistake stays in the record, which is the point.
"""

from __future__ import annotations

from django.db import models

from core.dbfields import uuid7_pk


class WorkOrderAttachment(models.Model):
    """`work_order_attachments` — one file the phone sent, and where it belongs.

    ⚠ **`idempotency_key` IS WHAT MAKES A DAY OFFLINE SAFE, AND IT IS SCOPED TO
    THE ORDER RATHER THAN THE TENANT.** A technician works nine jobs with no
    signal; the phone queues nine photographs and syncs them when the signal
    returns; the sync is retried because the first attempt timed out halfway.
    Without this column the retry writes nine more rows and the supervisor sees
    every photograph twice. The key is minted ON THE HANDSET at capture — it
    has to be, because the server has no way to tell a retry of yesterday's
    photograph from a genuinely new one taken of the same dial.
    **(tenant, work_order, idempotency_key)** and not (tenant, key): two phones
    can independently mint the same short key, and the order is the natural
    boundary because a key only ever means *this file, on this job*.

    ⚠ **`taken_at` IS NOT `created_at`, AND CONFLATING THEM WOULD BE A LIE
    ABOUT A DISPUTED READING.** `taken_at` is the moment the shutter closed on
    the handset — 16:02, in a meter cupboard, with no signal. `created_at` is
    when the row reached the server, which after an offline day is 17:40. The
    supervisor reviewing a disputed final read is asking the first question and
    the thumbnail shows the first answer.

    ⚠ **`reading` AND `task` ARE BOTH NULLABLE AND AT MOST ONE IS SET.** A
    photograph can belong to a reading (*the dial you read*), to a task (*the
    seal you fitted*), or to the job at large (*the state of the cupboard*).
    The third is why neither is required, and it is a real case: the door-hanger
    photograph that stands in for a refused signature belongs to no checklist
    row at all.

    ⚠ **`kind` IS STORED HERE AS WELL AS ON THE DOCUMENT, AND THAT IS A
    DELIBERATE COPY.** `Work-033` asks *how many photographs does this job
    have*, which is a filter on the order's own rows; reading it off the joined
    `stored_documents` row would make the commonest query on this table a join
    to another module's table through the seam. The document remains the
    authority and the two cannot disagree, because `evidence.record_attachment`
    is the only writer and it takes the kind FROM the document it just stored.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")

    #: ⚠ CROSS-MODULE FK work → metering, the direction `work_order_readings`
    #: and `work_order_assignments` already established. `work_orders` is
    #: metering's table until `03-field-map.md` §4 settles the move; this FK
    #: travels with it when it does. CASCADE and not PROTECT: an attachment has
    #: no life away from the job it was taken on.
    work_order = models.ForeignKey(
        "work.WorkOrder",
        on_delete=models.CASCADE,
        db_column="work_order_id",
        related_name="attachment_rows",
    )

    #: ⚠ CROSS-MODULE FK work → tenancy, and PROTECT rather than CASCADE. The
    #: bytes are the evidence; deleting the document row while a job still
    #: points at it would leave the order claiming a photograph that cannot be
    #: fetched. When the twelve-month prune is finally built (`BR-WRK-048`) it
    #: will have to clear both ends deliberately, which is exactly the pause
    #: this PROTECT exists to force.
    document = models.ForeignKey(
        "tenancy.StoredDocument",
        on_delete=models.PROTECT,
        db_column="document_id",
        related_name="+",
    )

    #: `work_order_photo` or `work_order_signature`. See the class docstring for
    #: why it is copied. `work_order_report` never appears here — a report is
    #: generated by `accept_field_result` and read through `for_source`, not
    #: sent by a phone.
    kind = models.TextField()

    #: The shutter, not the sync. See the class docstring.
    taken_at = models.DateTimeField()

    #: Which handset. A free-text label the phone supplies (*"Pixel 7a ·
    #: D. Ortiz"*), NOT a FK to `technician_devices`: a device row can be
    #: deleted when a technician's phone is replaced, and the answer to *which
    #: phone took this* must survive that. It is shown on the lightbox.
    device = models.TextField(blank=True, default="")

    added_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="added_by",
        related_name="+",
    )

    #: Which checklist row this belongs to, when it belongs to one. Plain uuids
    #: and not FKs for the B11 F-3 reason wave H's own columns give: these point
    #: INTO `work_order_readings` / `work_order_tasks`, and `evidence.py`
    #: verifies the row exists, belongs to this tenant AND belongs to THIS
    #: ORDER before writing — which is a stronger check than a foreign key,
    #: since an FK cannot express the last of those three.
    reading_id = models.UUIDField(null=True, blank=True)
    task_id = models.UUIDField(null=True, blank=True)

    #: Minted on the handset at capture. See the class docstring.
    idempotency_key = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "work_order_attachments"
        constraints = [
            #: `BR-WRK-047`. The uniqueness is what makes a re-sync a no-op.
            models.UniqueConstraint(
                fields=["tenant", "work_order", "idempotency_key"],
                name="uq_work_order_attachments_key",
            ),
            #: A photograph belongs to a reading, or to a task, or to neither —
            #: never to both. One file cannot be evidence of two different
            #: checklist rows, and a row claiming it would make `Work-033`'s
            #: count wrong in two places at once.
            models.CheckConstraint(
                condition=models.Q(reading_id__isnull=True) | models.Q(task_id__isnull=True),
                name="ck_work_order_attachments_one_owner",
            ),
            #: An empty key is the shape a client takes when it did not think
            #: about this, and it would defeat the uniqueness above by making
            #: every unkeyed upload collide with every other.
            models.CheckConstraint(
                condition=~models.Q(idempotency_key=""),
                name="ck_work_order_attachments_key_present",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    kind__in=("work_order_photo", "work_order_signature")
                ),
                name="ck_work_order_attachments_kind",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "work_order", "taken_at"], name="ix_wo_attach_order_taken"
            ),
        ]


class WorkOrderSignature(models.Model):
    """`work_order_signatures` — the customer signed, or the customer did not.

    ⚠ **A SIGNATURE AND A REFUSAL ARE ONE ROW WITH TWO SHAPES, AND THE CHECK
    CONSTRAINT IS THE RULE ITSELF** (`BR-WRK-046`, r10 verbatim: *"if refused,
    record decline reason and photo of door hanger"*). They are not two tables
    because they answer ONE question — *what happened when the crew asked the
    customer to sign* — and a supervisor reading a job wants that answer in one
    place, present or absent. They are not one nullable shape either: a row
    carrying both a signature image and a decline reason is not a record of
    anything that happened, and the database refuses it by name.

      * **signed**  — `printed_name` and the mark (`image`, or the phone's
        `image_photo_id`) present; `decline_reason`, `door_hanger` and
        `door_hanger_photo_id` NULL.
      * **refused** — `decline_reason` present and a door-hanger photograph
        (`door_hanger`, or the phone's `door_hanger_photo_id`); `printed_name`,
        `image` and `image_photo_id` NULL.

    ⚠ **THE PHONE NAMES ITS PHOTOGRAPH BY ITS OWN PHOTO ID, NOT BY A FILE
    (`DEF-WRK-10625`, PO 2026-10-27).** The field app declares every photograph
    with the data and uploads the bytes later on signal (`WorkPhotoLink`,
    BR-WRK-062), so at the moment the signature arrives there is no attachment
    and no stored document to point at. Before this, the server refused every
    refusal recorded on a phone (*"A refusal needs a door-hanger photo."*) and
    a signed mark could not travel at all. `door_hanger_photo_id` and
    `image_photo_id` hold the phone's id; the file is READ THROUGH the link
    once it lands (`evidence.signature_for_order`), never copied back onto this
    row. The web's path — an existing attachment, multipart bytes — is unchanged.

    ⚠ **`printed_name` IS NOT DECORATION AND IS REQUIRED WHEN SIGNED.** A
    signature image is a squiggle on glass; six months later, in a dispute, the
    only thing that says WHO made it is the name they typed beside it. r10 asks
    for both and `BR-WRK-046` names both.

    ⚠ **THE DOOR HANGER POINTS AT AN ATTACHMENT, NOT AT A DOCUMENT, AND THAT IS
    A DELIBERATE DIVERGENCE FROM `US-WRK-048` §5's `door_hanger_document_id`.**
    A photograph of a door hanger IS one of the job's photographs: the crew
    took it on the same phone, on the same visit, for the same reason. Pointing
    at `stored_documents` directly would make it the ONE photograph that never
    appears in the job's own evidence list on `Work-033` — visible in the
    signature panel and nowhere else — and a supervisor counting *three
    photographs* would be looking at a screen that disagrees with the store.
    Same file, one chain.

    ⚠ **ONE ROW PER ORDER, ENFORCED.** A second signature would raise *which of
    these two is the customer's answer*, and there is no lawful reading of that.
    A crew who captured the wrong thing gets a supervisor to reopen the job;
    they do not get to sign it twice.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    work_order = models.ForeignKey(
        "work.WorkOrder",
        on_delete=models.CASCADE,
        db_column="work_order_id",
        related_name="signature_rows",
    )

    #: The fork. Everything else on this row is decided by it.
    refused = models.BooleanField(default=False)

    #: ── the SIGNED shape ──────────────────────────────────────────────────
    printed_name = models.TextField(null=True, blank=True)
    image = models.ForeignKey(
        "tenancy.StoredDocument",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="image_document_id",
        related_name="+",
    )

    #: ── the REFUSED shape ─────────────────────────────────────────────────
    decline_reason = models.TextField(null=True, blank=True)
    door_hanger = models.ForeignKey(
        WorkOrderAttachment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="door_hanger_attachment_id",
        related_name="+",
    )

    #: ── the phone's photographs, by the phone's own photo id ──────────────
    #: `WorkPhotoLink.photo_id` on this order (DEF-WRK-10625). Plain uuids,
    #: like the link's own `reading_id`/`task_id`: the link is resolved under
    #: the tenant AND the order by `evidence`, which a foreign key could not do.
    image_photo_id = models.UUIDField(null=True, blank=True)
    door_hanger_photo_id = models.UUIDField(null=True, blank=True)

    #: ── both shapes ───────────────────────────────────────────────────────
    #: When the customer signed or refused, on the handset — the same
    #: shutter-versus-sync distinction `WorkOrderAttachment.taken_at` carries.
    signed_at = models.DateTimeField()
    captured_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="captured_by",
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "work_order_signatures"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "work_order"], name="uq_work_order_signatures_order"
            ),
            #: `BR-WRK-046` as a CHECK. Read it as the two shapes in the class
            #: docstring; anything else is refused by the database rather than
            #: by a validator somebody can forget to call.
            models.CheckConstraint(
                condition=(
                    (
                        models.Q(
                            refused=False,
                            printed_name__isnull=False,
                            decline_reason__isnull=True,
                            door_hanger__isnull=True,
                            door_hanger_photo_id__isnull=True,
                        )
                        & (models.Q(image__isnull=False) | models.Q(image_photo_id__isnull=False))
                    )
                    | (
                        models.Q(
                            refused=True,
                            printed_name__isnull=True,
                            image__isnull=True,
                            image_photo_id__isnull=True,
                            decline_reason__isnull=False,
                        )
                        & (models.Q(door_hanger__isnull=False) | models.Q(door_hanger_photo_id__isnull=False))
                    )
                ),
                name="ck_work_order_signatures_shape",
            ),
            #: An empty string is not a name and not a reason. Without this the
            #: shape check above passes on `printed_name = ''`, which is the
            #: shape a form takes when the customer walked away mid-signature.
            models.CheckConstraint(
                condition=~models.Q(printed_name="") & ~models.Q(decline_reason=""),
                name="ck_work_order_signatures_not_blank",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "work_order"], name="ix_wo_signature_order"),
        ]


class WorkPhotoLink(models.Model):
    """`work_photo_links` — the LINK a photograph will land at, created WITH the
    record that needs it (`CR-168-BRC10` §F, TECHNICIAN SYNC DESIGN and the
    PO's correction of 2026-10-04, verbatim: *"link you ahve to create along
    with data record and pass it to async job - otherway round"*).

    The phone declares a photo in its data page — its OWN photo id (a client
    uuid), the sha256 of the bytes it will send, and the task or reading it is
    for. The server saves that declaration HERE in the same save, and answers
    the link (`upload_url`). The bytes then travel in the background to that
    link; the server checks their hash against `sha256`, compresses them if
    they are over the ceiling (never refuses for size), and files them as a
    `work_order_attachments` row. Until then the link is PENDING, never
    MISSING: the record holds it from the first moment.

    ⚠ **NOT APPEND-ONLY, UNLIKE `work_order_attachments`.** The link is the
    one row that changes — `staged` holds the landed bytes until the job files
    them, then is cleared (only the compressed copy is kept), and `attachment`
    is filled. The evidence itself, once filed, is append-only as before.

    Idempotent on `(tenant, photo_id)`: re-sending the page returns THIS link,
    never a new one; re-uploading to a filled link adds nothing.
    """

    STATE_PENDING = "pending"
    STATE_STAGED = "staged"
    STATE_LANDED = "landed"

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    work_order = models.ForeignKey(
        "work.WorkOrder",
        on_delete=models.CASCADE,
        db_column="work_order_id",
        related_name="photo_links",
    )
    #: The PHONE's id for this photograph, minted at capture.
    photo_id = models.UUIDField()
    #: Hex sha256 the phone declared for the bytes it will send.
    sha256 = models.TextField()
    reading_id = models.UUIDField(null=True, blank=True)
    task_id = models.UUIDField(null=True, blank=True)
    #: Whether the template asked for it — copied from the row at declaration,
    #: so *"required photos still uploading"* is one query.
    required = models.BooleanField(default=False)
    state = models.TextField(default=STATE_PENDING)
    taken_at = models.DateTimeField(null=True, blank=True)
    captured_by = models.ForeignKey(
        "identity.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="captured_by",
        related_name="+",
    )
    #: The landed bytes, held only until the background job files them.
    staged = models.BinaryField(null=True, blank=True)
    content_type = models.TextField(blank=True, default="")
    bytes_received = models.IntegerField(null=True, blank=True)
    bytes_stored = models.IntegerField(null=True, blank=True)
    attachment = models.ForeignKey(
        "work.WorkOrderAttachment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="attachment_id",
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    landed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "work_photo_links"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "photo_id"], name="uq_work_photo_links_photo"),
            models.CheckConstraint(
                condition=models.Q(state__in=("pending", "staged", "landed")),
                name="ck_work_photo_links_state",
            ),
            models.CheckConstraint(
                condition=models.Q(reading_id__isnull=True) | models.Q(task_id__isnull=True),
                name="ck_work_photo_links_one_owner",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "work_order", "state"], name="ix_photo_links_order_state"),
        ]
