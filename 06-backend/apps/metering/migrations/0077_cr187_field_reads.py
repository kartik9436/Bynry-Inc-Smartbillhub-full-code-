"""metering 0077 — the native field app's ROUTE READING tables (`CR-187-BRC10`,
2026-10-21).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-21 under the PO ruling of
2026-08-09; the `12-governance/09-human-review-ledger.md` row is owed by the
coordinator (this lane may not edit shared registers).

FOUR TABLES, FOUR RLS POLICIES, NO BACKFILL, NOTHING ELSE TOUCHED.

  * `field_reads`           — one row per item a handset sent from a route; the
                              receipt (unique `(tenant, key)`, hard rule 6) AND
                              the record of what the reader did (R88–R96).
  * `cant_read_reasons`     — R82's tenant vocabulary; eight seeded LAZILY by
                              `field_reads.ensure_cant_read_reasons()` on first
                              use (the `unit_types` posture), never here.
  * `field_meter_proposals` — R85's pending meter; no `assets` row exists until
                              the office accepts it, so it bills nothing.
  * `field_route_turn_ins`  — RW-25 … RW-27; a record, never a gate.

⚠ **`meter_reads` IS NOT ALTERED.** It is partitioned on `read_at`, append-only
and written by one function; why the capture facts sit beside it rather than on
it is argued in `apps/metering/field_read_models.py`'s docstring.

No backfill: no route reading has ever reached the server, because there was no
door for one (`07-endpoints.md` N1).
"""

import core.dbfields
import django.db.models.deletion
import django.db.models.functions.text
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

TABLES = ("field_reads", "cant_read_reasons", "field_meter_proposals", "field_route_turn_ins")
#: The same expression every other policy in this module uses — NULLIF so an
#: unset `app.tenant_id` is NULL and matches nothing, rather than raising.
TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

POLICY = "".join(
    f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY {table}_tenant_isolation ON {table}
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});
"""
    for table in TABLES
)

REVERSE_POLICY = "".join(
    f"""
DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};
ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;
"""
    for table in TABLES
)


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0013_def_ast_4690_fire_line_type"),
        ("identity", "0010_def_idn_10023_password_history"),
        ("metering", "0076_def_wrk_6737_outcome_check"),
        ("tenancy", "0064_def_rat_10220_size_class_capacity"),
    ]

    operations = [
        migrations.CreateModel(
            name="FieldMeterProposal",
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
                ("key", models.TextField()),
                ("service_code", models.TextField()),
                ("size_class", models.TextField(blank=True, null=True)),
                ("badge", models.TextField(blank=True, null=True)),
                ("serial_no", models.TextField(blank=True, null=True)),
                ("unit_of_measure", models.TextField(blank=True, null=True)),
                ("lat", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("lng", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                (
                    "accuracy_m",
                    models.DecimalField(blank=True, decimal_places=2, max_digits=9, null=True),
                ),
                ("photo_ids", models.JSONField(blank=True, default=list)),
                ("remark", models.TextField(blank=True, null=True)),
                ("status", models.TextField(default="pending")),
                ("accepted_asset_id", models.UUIDField(blank=True, null=True)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("device_captured_at", models.DateTimeField(blank=True, null=True)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                (
                    "decided_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="decided_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="decided_field_meter_proposals",
                        to="identity.user",
                    ),
                ),
                (
                    "premises",
                    models.ForeignKey(
                        db_column="premises_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="metering.premises",
                    ),
                ),
                (
                    "proposed_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="proposed_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="field_meter_proposals",
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
                (
                    "unit",
                    models.ForeignKey(
                        blank=True,
                        db_column="unit_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="metering.unit",
                    ),
                ),
            ],
            options={
                "db_table": "field_meter_proposals",
            },
        ),
        migrations.CreateModel(
            name="FieldRead",
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
                ("key", models.TextField()),
                ("kind", models.TextField(default="reading")),
                ("channel", models.TextField(default="total")),
                (
                    "value",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                ("unit", models.TextField(blank=True, null=True)),
                ("reader_status", models.TextField(blank=True, null=True)),
                ("cant_read_reason", models.TextField(blank=True, null=True)),
                ("accepted_anyway", models.BooleanField(default=False)),
                ("lat", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("lng", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                (
                    "accuracy_m",
                    models.DecimalField(blank=True, decimal_places=2, max_digits=9, null=True),
                ),
                ("fix_quality", models.TextField(blank=True, null=True)),
                (
                    "metres_from_record",
                    models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
                ),
                ("device_captured_at", models.DateTimeField(blank=True, null=True)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("identified_by", models.TextField(blank=True, null=True)),
                ("scanned_code", models.TextField(blank=True, null=True)),
                ("mismatch_answer", models.TextField(blank=True, null=True)),
                ("off_route", models.BooleanField(default=False)),
                ("read_method", models.TextField(blank=True, null=True)),
                ("remark", models.TextField(blank=True, null=True)),
                ("remark_source", models.TextField(blank=True, null=True)),
                ("photo_ids", models.JSONField(blank=True, default=list)),
                ("outcome", models.TextField(default="held")),
                ("held_reason", models.TextField(blank=True, null=True)),
                ("held_detail", models.JSONField(blank=True, null=True)),
                ("meter_read_id", models.UUIDField(blank=True, null=True)),
                ("read_import_batch_id", models.UUIDField(blank=True, null=True)),
                ("received_payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "asset",
                    models.ForeignKey(
                        blank=True,
                        db_column="asset_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="field_reads",
                        to="assets.asset",
                    ),
                ),
                (
                    "expected_asset",
                    models.ForeignKey(
                        blank=True,
                        db_column="expected_asset_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="field_reads_expected",
                        to="assets.asset",
                    ),
                ),
                (
                    "premises",
                    models.ForeignKey(
                        blank=True,
                        db_column="premises_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="metering.premises",
                    ),
                ),
                (
                    "proposal",
                    models.ForeignKey(
                        blank=True,
                        db_column="proposal_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="readings",
                        to="metering.fieldmeterproposal",
                    ),
                ),
                (
                    "reader",
                    models.ForeignKey(
                        blank=True,
                        db_column="reader_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="field_reads",
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
                "db_table": "field_reads",
            },
        ),
        migrations.CreateModel(
            name="FieldRouteTurnIn",
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
                ("key", models.TextField()),
                ("period_start", models.DateField(blank=True, null=True)),
                ("period_end", models.DateField(blank=True, null=True)),
                ("handset_counts", models.JSONField(blank=True, default=dict)),
                ("device_captured_at", models.DateTimeField(blank=True, null=True)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                (
                    "reader",
                    models.ForeignKey(
                        blank=True,
                        db_column="reader_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="field_route_turn_ins",
                        to="identity.user",
                    ),
                ),
                (
                    "route",
                    models.ForeignKey(
                        db_column="route_id",
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
                "db_table": "field_route_turn_ins",
            },
        ),
        migrations.CreateModel(
            name="CantReadReason",
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
                ("code", models.TextField()),
                ("name", models.TextField()),
                ("sort_order", models.IntegerField(default=0)),
                ("is_system", models.BooleanField(default=False)),
                ("active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
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
                "db_table": "cant_read_reasons",
                "constraints": [
                    models.UniqueConstraint(
                        models.F("tenant"),
                        django.db.models.functions.text.Lower("code"),
                        name="uq_cant_read_reasons_tenant_code_ci",
                    )
                ],
            },
        ),
        migrations.AddIndex(
            model_name="fieldmeterproposal",
            index=models.Index(fields=["tenant", "status"], name="ix_field_proposals_status"),
        ),
        migrations.AddConstraint(
            model_name="fieldmeterproposal",
            constraint=models.UniqueConstraint(
                fields=("tenant", "key"), name="uq_field_meter_proposals_key"
            ),
        ),
        migrations.AddConstraint(
            model_name="fieldmeterproposal",
            constraint=models.CheckConstraint(
                condition=models.Q(("status__in", ("pending", "accepted", "declined"))),
                name="ck_field_meter_proposals_status",
            ),
        ),
        migrations.AddIndex(
            model_name="fieldread",
            index=models.Index(
                fields=["tenant", "route", "received_at"], name="ix_field_reads_route"
            ),
        ),
        migrations.AddIndex(
            model_name="fieldread",
            index=models.Index(fields=["tenant", "outcome"], name="ix_field_reads_outcome"),
        ),
        migrations.AddConstraint(
            model_name="fieldread",
            constraint=models.UniqueConstraint(fields=("tenant", "key"), name="uq_field_reads_key"),
        ),
        migrations.AddConstraint(
            model_name="fieldread",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("outcome__in", ("posted", "recorded", "awaiting_acceptance", "held"))
                ),
                name="ck_field_reads_outcome",
            ),
        ),
        migrations.AddIndex(
            model_name="fieldrouteturnin",
            index=models.Index(
                fields=["tenant", "route", "received_at"], name="ix_field_turn_ins_route"
            ),
        ),
        migrations.AddConstraint(
            model_name="fieldrouteturnin",
            constraint=models.UniqueConstraint(
                fields=("tenant", "key"), name="uq_field_route_turn_ins_key"
            ),
        ),
        PostgresOnlySQL(POLICY, reverse_sql=REVERSE_POLICY),
    ]
