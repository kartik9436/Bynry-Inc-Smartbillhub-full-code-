"""work 0003 — the template bundle: seven child collections and a version log.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-05 under the PO ruling of
2026-08-09. Its row is in `12-governance/09-human-review-ledger.md`;
`work/0004` carries the RLS policy and is the file a reviewer of a 🔒 path
reads on its own.

`CR-070` wave D task D1 · `US-WRK-014` · `US-WRK-018` · `BR-WRK-009` ·
`BR-WRK-012` · `BR-WRK-015` · `03-field-map.md` §2.2.

EIGHT TABLES, AND NOT ONE JSON COLUMN
-------------------------------------
`BR-WRK-009` — *"a template is a bundle of seven child collections stored as
ROWS, never a JSON blob"*, following `BR-MET-108`'s precedent. `US-WRK-014`
TC-5 is the negative that guards it: a `bundle jsonb` column appearing on
`work_order_templates` fails the schema test.

The eighth is `work_order_template_versions`, which `03-field-map.md` §2.2
marks `[ours]`: `WM-40` says the detail *"lists versions with what changed"*
and names no table.

⚠ **EVERY ONE OF THEM CARRIES `tenant_id` AND A FK TO THE TEMPLATE, AND THE
TEMPLATE IS METERING'S ROW.** The FK is a cross-module pointer in B2 §2's
reviewed set — the same one `work.WorkOrderType.default_template` already
declares. It points; it does not write. Nothing under `apps/work/` writes a
metering row outside the one named seam door (`BR-WRK-002`, G78).

⚠ **`tenant_id` IS DENORMALISED ONTO EVERY CHILD ROW ON PURPOSE.** It could be
reached by joining to the header. It is not, because RLS is a per-table policy
in this product (hard rule 1, B2 §3) and a policy cannot follow a join: a table
with no `tenant_id` of its own cannot be isolated at all, and the isolation
would then rest on every query remembering to join. `work/0004` puts ENABLE +
FORCE on all eight.

`on_delete=CASCADE` from the child to the header, and PROTECT from a material
to its part: deleting a template takes its own rows with it (that is what a
bundle is), and a part a template plans cannot be deleted out from under it
(`BR-TEN-034`).
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0048_cr070_d_template_bundle"),
        ("tenancy", "0038_rls_cr068_d_published_content"),
        ("work", "0002_rls_force"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkOrderTemplateAssetType",
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
                ("asset_type_id", models.UUIDField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "template",
                    models.ForeignKey(
                        db_column="template_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wot_asset_types",
                        to="metering.workordertemplate",
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
                "db_table": "wot_asset_types",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("template", "asset_type_id"), name="uq_wot_asset_types_type"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="WorkOrderTemplateDetail",
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
                ("show_account_summary", models.BooleanField(default=True)),
                ("show_asset_card", models.BooleanField(default=True)),
                ("show_access_notes", models.BooleanField(default=True)),
                ("show_appointment", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "template",
                    models.ForeignKey(
                        db_column="template_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wot_details",
                        to="metering.workordertemplate",
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
                "db_table": "wot_details",
                "constraints": [
                    models.UniqueConstraint(fields=("template",), name="uq_wot_details_template")
                ],
            },
        ),
        migrations.CreateModel(
            name="WorkOrderTemplateHelp",
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
                ("seq", models.IntegerField()),
                ("kind", models.TextField()),
                ("label", models.TextField()),
                ("ref", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "template",
                    models.ForeignKey(
                        db_column="template_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wot_help",
                        to="metering.workordertemplate",
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
                "db_table": "wot_help",
                "constraints": [
                    models.UniqueConstraint(fields=("template", "seq"), name="uq_wot_help_seq"),
                    models.CheckConstraint(
                        condition=models.Q(("kind__in", ("document", "phone", "note"))),
                        name="ck_wot_help_kind",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="WorkOrderTemplateMaterial",
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
                ("planned_qty", models.DecimalField(decimal_places=4, default=1, max_digits=18)),
                ("unit_of_measure", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "part",
                    models.ForeignKey(
                        db_column="part_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="planned_in",
                        to="work.part",
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        db_column="template_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wot_materials",
                        to="metering.workordertemplate",
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
                "db_table": "wot_materials",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("template", "part"), name="uq_wot_materials_part"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="WorkOrderTemplateReading",
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
                ("seq", models.IntegerField()),
                ("prompt", models.TextField()),
                ("unit_of_measure", models.TextField()),
                (
                    "min_value",
                    models.DecimalField(
                        blank=True,
                        db_column="min_value",
                        decimal_places=4,
                        max_digits=18,
                        null=True,
                    ),
                ),
                (
                    "max_value",
                    models.DecimalField(
                        blank=True,
                        db_column="max_value",
                        decimal_places=4,
                        max_digits=18,
                        null=True,
                    ),
                ),
                ("required", models.BooleanField(default=True)),
                ("photo_required", models.BooleanField(default=False)),
                ("posts_as_meter_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "template",
                    models.ForeignKey(
                        db_column="template_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wot_readings",
                        to="metering.workordertemplate",
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
                "db_table": "wot_readings",
                "constraints": [
                    models.UniqueConstraint(fields=("template", "seq"), name="uq_wot_readings_seq")
                ],
            },
        ),
        migrations.CreateModel(
            name="WorkOrderTemplateSafety",
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
                ("seq", models.IntegerField()),
                ("text", models.TextField()),
                ("is_mandatory", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "template",
                    models.ForeignKey(
                        db_column="template_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wot_safety",
                        to="metering.workordertemplate",
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
                "db_table": "wot_safety",
                "constraints": [
                    models.UniqueConstraint(fields=("template", "seq"), name="uq_wot_safety_seq")
                ],
            },
        ),
        migrations.CreateModel(
            name="WorkOrderTemplateTask",
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
                ("seq", models.IntegerField()),
                ("title", models.TextField()),
                ("est_minutes", models.IntegerField(default=0)),
                ("photo_required", models.BooleanField(default=False)),
                ("is_mandatory", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "template",
                    models.ForeignKey(
                        db_column="template_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wot_tasks",
                        to="metering.workordertemplate",
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
                "db_table": "wot_tasks",
                "constraints": [
                    models.UniqueConstraint(fields=("template", "seq"), name="uq_wot_tasks_seq"),
                    models.CheckConstraint(
                        condition=models.Q(("est_minutes__gte", 0)),
                        name="ck_wot_tasks_minutes_not_negative",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="WorkOrderTemplateVersion",
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
                ("version", models.IntegerField()),
                ("published_at", models.DateTimeField()),
                ("published_by", models.UUIDField(blank=True, null=True)),
                ("change_note", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "template",
                    models.ForeignKey(
                        db_column="template_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="versions",
                        to="metering.workordertemplate",
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
                "db_table": "work_order_template_versions",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("template", "version"), name="uq_wot_versions_template_version"
                    )
                ],
            },
        ),
    ]
