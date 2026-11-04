# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 §F — the technician API (PO 2026-10-04: the API
#           ruling, the shared-device / offline / location ruling, the two
#           consequences ruled, the photo-link correction and the TECHNICIAN
#           SYNC DESIGN)
# Rules:    BR-WRK-059 · BR-WRK-060 · BR-WRK-061 · BR-WRK-062 · CLAUDE.md 🔒
#           migration ordering
# Tests:    06-backend/tests/test_cr168_technician_api.py
# ───────────────────────────────────────────────────────
"""work 0035 — who captured a synced item, where, how precisely; items kept
for review; and the photo LINK created with the record.

* `work_sync_receipts`: `captured_by_technician_id` (FK, NULL), `lat`/`lng`
  NUMERIC(9,6), `accuracy_m` NUMERIC(9,1), `fix_at`, `needs_review` TEXT,
  `received` JSONB — all NULL on every existing row, which is the fact.
* `work_settings.location_accuracy_m` INTEGER DEFAULT 50.
* `ck_work_sync_receipts_kind` widens by `photo` and `unrecognised`.
* NEW `work_photo_links` — unique `(tenant, photo_id)`; RLS + FORCE in
  `work/0036`, the next migration, the repo's convention for a new table.

**Down:** drops the columns and the table (refused while any link holds
staged bytes not yet filed, so a rollback cannot lose a photograph).

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md 🔒
sensitive path. AI-authored 2026-10-04 under the PO ruling of 2026-08-09; row in
`12-governance/09-human-review-ledger.md`.
"""


import core.dbfields
import django.db.models.deletion
from django.db import migrations, models

#: Frozen here, never imported: a migration states the schema of its day.
RECEIPT_KINDS = (
    "safety_tick", "task_tick", "reading", "material", "attachment", "signature",
    "close", "photo", "unrecognised",
)


def _refuse_rollback_over_staged(apps, schema_editor):
    model = apps.get_model("work", "WorkPhotoLink")
    stuck = model.objects.filter(state="staged").count()
    if stuck:
        raise RuntimeError(
            f"refusing to roll back work/0035: {stuck} photo link(s) hold bytes not yet filed. "
            "Run the pending photo jobs first; dropping the table would lose those photographs."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0008_cr145_withdraw_long_timeouts_per_tenant"),
        ("metering", "0073_cr168_est_duration_from_task_minutes"),
        ("tenancy", "0059_cr168_work_template_help_document"),
        ("work", "0034_cr168_task_instruction_copy_and_help_link"),
    ]

    operations = [
        # The receipt kinds widen: `photo` (a declaration in a data page) and
        # `unrecognised` (an item of unknown kind, STORED and flagged rather
        # than dropped — TECHNICIAN SYNC DESIGN (2)).
        migrations.RemoveConstraint(model_name="worksyncreceipt", name="ck_work_sync_receipts_kind"),
        migrations.AddConstraint(
            model_name="worksyncreceipt",
            constraint=models.CheckConstraint(
                condition=models.Q(kind__in=RECEIPT_KINDS),
                name="ck_work_sync_receipts_kind",
            ),
        ),
        migrations.AddField(
            model_name="worksettings",
            name="location_accuracy_m",
            field=models.IntegerField(default=50),
        ),
        migrations.AddField(
            model_name="worksyncreceipt",
            name="accuracy_m",
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name="worksyncreceipt",
            name="captured_by_technician",
            field=models.ForeignKey(
                blank=True,
                db_column="captured_by_technician_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="work.technician",
            ),
        ),
        migrations.AddField(
            model_name="worksyncreceipt",
            name="fix_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="worksyncreceipt",
            name="lat",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name="worksyncreceipt",
            name="lng",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name="worksyncreceipt",
            name="needs_review",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="worksyncreceipt",
            name="received",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="WorkPhotoLink",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=core.dbfields.uuid7,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("photo_id", models.UUIDField()),
                ("sha256", models.TextField()),
                ("reading_id", models.UUIDField(blank=True, null=True)),
                ("task_id", models.UUIDField(blank=True, null=True)),
                ("required", models.BooleanField(default=False)),
                ("state", models.TextField(default="pending")),
                ("taken_at", models.DateTimeField(blank=True, null=True)),
                ("staged", models.BinaryField(blank=True, null=True)),
                ("content_type", models.TextField(blank=True, default="")),
                ("bytes_received", models.IntegerField(blank=True, null=True)),
                ("bytes_stored", models.IntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("landed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "attachment",
                    models.ForeignKey(
                        blank=True,
                        db_column="attachment_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="work.workorderattachment",
                    ),
                ),
                (
                    "captured_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="captured_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
                (
                    "work_order",
                    models.ForeignKey(
                        db_column="work_order_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="photo_links",
                        to="metering.workorder",
                    ),
                ),
            ],
            options={
                "db_table": "work_photo_links",
                "indexes": [
                    models.Index(
                        fields=["tenant", "work_order", "state"], name="ix_photo_links_order_state"
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "photo_id"), name="uq_work_photo_links_photo"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("state__in", ("pending", "staged", "landed"))),
                        name="ck_work_photo_links_state",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("reading_id__isnull", True), ("task_id__isnull", True), _connector="OR"
                        ),
                        name="ck_work_photo_links_one_owner",
                    ),
                ],
            },
        ),
        # LAST, so that on the way DOWN it runs FIRST, while the table exists.
        migrations.RunPython(migrations.RunPython.noop, _refuse_rollback_over_staged),
    ]
