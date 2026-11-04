"""metering 0079 — a ROUTE photograph's link (`DEF-FLD-10357`, `CR-187-BRC10`,
lane INTEGRATE-2, 2026-10-21).

HUMAN-OWNED (migration ordering and RLS are CLAUDE.md 🔒 paths).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-21 under the PO ruling of
2026-08-09; the `12-governance/09-human-review-ledger.md` row is owed by the
coordinator (this lane may not edit shared registers).

ONE TABLE, ONE RLS POLICY (FORCE), NO BACKFILL, NOTHING ELSE TOUCHED.

  * `field_read_photos` — the link a route photograph's bytes land at, made in
                          the savepoint of the reads-door item that DECLARES it
                          (`field_reads._judge_photo`); the bytes are kept on
                          the row once they arrive
                          (`field_read_photos.receive_bytes`). Unique
                          `(tenant, photo_id)`.

No backfill: before this, a route photograph had no door — its declaration was
stored as a held `field_reads` row of kind `photo` (that is the defect) and its
bytes were refused by the job door. Those rows stay as they are; nothing here
reads or rewrites them.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

TABLE = "field_read_photos"
#: The same expression every other policy in this module uses (0077).
TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

POLICY = f"""
ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;
CREATE POLICY {TABLE}_tenant_isolation ON {TABLE}
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});
"""

REVERSE_POLICY = f"""
DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE};
ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0013_cr187_phone_sign_in"),
        ("metering", "0078_t43_release_the_six_work_tables"),
        ("tenancy", "0064_def_rat_10220_size_class_capacity"),
    ]

    operations = [
        migrations.CreateModel(
            name="FieldReadPhoto",
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
                ("key", models.TextField()),
                ("state", models.TextField(default="pending")),
                ("content_type", models.TextField(blank=True, null=True)),
                ("data", models.BinaryField(blank=True, null=True)),
                ("bytes_received", models.IntegerField(blank=True, null=True)),
                ("device_captured_at", models.DateTimeField(blank=True, null=True)),
                ("declared_at", models.DateTimeField(auto_now_add=True)),
                ("landed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "reader",
                    models.ForeignKey(
                        blank=True,
                        db_column="reader_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="field_read_photos",
                        to="identity.user",
                    ),
                ),
                (
                    "route",
                    models.ForeignKey(
                        blank=True,
                        db_column="route_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="metering.route",
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
            ],
            options={
                "db_table": "field_read_photos",
                "indexes": [
                    models.Index(
                        fields=["tenant", "route", "declared_at"], name="ix_field_read_photos_route"
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "photo_id"), name="uq_field_read_photos_photo"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("state__in", ("pending", "landed"))),
                        name="ck_field_read_photos_state",
                    ),
                ],
            },
        ),
        PostgresOnlySQL(POLICY, reverse_sql=REVERSE_POLICY),
    ]
