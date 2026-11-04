"""work 0012 — the order's own copies of its template: six tables.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-05 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*). Its row is in
`12-governance/09-human-review-ledger.md` (task `H4`); not RATIFIED without a
recorded sign-off.

`CR-070` wave H task `H1` · `US-WRK-032` · `BR-WRK-008` · `WM-18` ·
`03-field-map.md` §2.4 · hard rules 1 and 3.

WHAT THESE SIX TABLES ARE FOR
-----------------------------
`BR-WRK-008`, verbatim: *"**Copy, never link.** When an order is raised it takes
its OWN copies of the template's details, safety rows, tasks, materials,
readings and help, and stamps the template version. **Editing or publishing a
template afterwards changes no order already raised.**"*

A template is a live document — a utility edits it and publishes v2, v3, v4. An
order is a record of one job that happened once. If the order read its checklist
through `template_id`, publishing v2 would rewrite the steps a technician
followed in January, the parts they were told to bring and the readings they
were asked for, on every completed order that used it — with no row changed, no
audit entry, and nothing anywhere to notice. These six tables are what stop
that.

THE ABSENCE THAT IS THE POINT
-----------------------------
⚠ **NOT ONE OF THESE TABLES HAS A FOREIGN KEY TO ANY `wot_*` TABLE.** That is
not an oversight to be tidied up by a later lane adding a helpful join: it IS
`BR-WRK-008`. The only reference an order keeps to the template it came from is
`work_orders.template_id` + `work_orders.template_version`, which say where it
came from without letting it move. `US-WRK-032` TC-6 asserts the absence against
the live schema rather than against this docstring (hard-won law 1).

WHY SIX AND NOT THE CARD'S THREE
--------------------------------
`WM-18`'s card names three (tasks, readings, materials); the `WS-08` caption
says *"the six order instance tables"*. The decision-log row of 2026-09-03
settles it at six, and `03-field-map.md` §5 records the discrepancy for §16.
Copying five of six would leave a technician's SAFETY LIST reading through a
live template — the one collection whose staleness `BR-WRK-037` makes a safety
question rather than a bookkeeping one.

WHY THE FK TO `work_orders` IS CASCADE AND THE FK TO `parts` IS PROTECT
-----------------------------------------------------------------------
A copy has no life away from the order it was copied onto, so it goes with it.
A part is a catalogue entry that outlives every job that used one, so a job
naming `MTR-W58` keeps it from being deleted (`BR-TEN-034` in the schema, the
posture `wot_materials` already takes).

⚠ **CROSS-MODULE FK work → metering**, the direction `work/0008` already
established and that nine template columns in this app already take.
`work_orders` is metering's table until the blueprint's §16 settles the move
(`03-field-map.md` §4); these six FKs move with it when it does.

RLS IS `work/0013`, DELIBERATELY THE NEXT MIGRATION AND NOT THIS ONE
--------------------------------------------------------------------
Same reason `work/0008` and `work/0009` are two files: the policies land in
their own migration so a database can never exist in a state where the tables
are there and the isolation is not.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0005_cr070_f_field_technician"),
        ("metering", "0050_cr070_g_dispatch"),
        ("tenancy", "0038_rls_cr068_d_published_content"),
        ("work", "0011_rls_force_costing"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkOrderDetail",
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
                ("access_notes", models.TextField(blank=True, null=True)),
                ("hazards", models.TextField(blank=True, null=True)),
                ("gate_code", models.TextField(blank=True, null=True)),
                ("show_account_summary", models.BooleanField(default=True)),
                ("show_asset_card", models.BooleanField(default=True)),
                ("show_access_notes", models.BooleanField(default=True)),
                ("show_appointment", models.BooleanField(default=True)),
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
                (
                    "work_order",
                    models.ForeignKey(
                        db_column="work_order_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="detail_rows",
                        to="metering.workorder",
                    ),
                ),
            ],
            options={
                "db_table": "work_order_details",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("work_order",), name="uq_work_order_details_order"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="WorkOrderHelp",
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
                        related_name="help_rows",
                        to="metering.workorder",
                    ),
                ),
            ],
            options={
                "db_table": "work_order_help",
                "indexes": [
                    models.Index(fields=["tenant", "work_order", "seq"], name="ix_wo_help_order")
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("work_order", "seq"), name="uq_work_order_help_seq"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("kind__in", ("document", "phone", "note"))),
                        name="ck_work_order_help_kind",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="WorkOrderMaterial",
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
                ("planned_qty", models.DecimalField(decimal_places=4, default=0, max_digits=18)),
                (
                    "used_qty",
                    models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
                ),
                ("unit_of_measure", models.TextField()),
                ("issued_at", models.DateTimeField(blank=True, null=True)),
                ("unplanned", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "issued_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="issued_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
                (
                    "part",
                    models.ForeignKey(
                        db_column="part_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="used_in",
                        to="work.part",
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
                        related_name="material_rows",
                        to="metering.workorder",
                    ),
                ),
            ],
            options={
                "db_table": "work_order_materials",
                "indexes": [
                    models.Index(fields=["tenant", "work_order"], name="ix_wo_materials_order")
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("work_order", "part"), name="uq_work_order_materials_part"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="WorkOrderReading",
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
                (
                    "value",
                    models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
                ),
                ("captured_at", models.DateTimeField(blank=True, null=True)),
                ("photo_attachment_id", models.UUIDField(blank=True, null=True)),
                ("in_range", models.BooleanField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
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
                        related_name="reading_rows",
                        to="metering.workorder",
                    ),
                ),
            ],
            options={
                "db_table": "work_order_readings",
                "indexes": [
                    models.Index(
                        fields=["tenant", "work_order", "seq"], name="ix_wo_readings_order"
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("work_order", "seq"), name="uq_work_order_readings_seq"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="WorkOrderSafety",
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
                ("ticked_at", models.DateTimeField(blank=True, null=True)),
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
                (
                    "ticked_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="ticked_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
                (
                    "work_order",
                    models.ForeignKey(
                        db_column="work_order_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="safety_rows",
                        to="metering.workorder",
                    ),
                ),
            ],
            options={
                "db_table": "work_order_safety",
                "indexes": [
                    models.Index(fields=["tenant", "work_order", "seq"], name="ix_wo_safety_order")
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("work_order", "seq"), name="uq_work_order_safety_seq"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="WorkOrderTask",
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
                ("ticked_at", models.DateTimeField(blank=True, null=True)),
                ("photo_attachment_id", models.UUIDField(blank=True, null=True)),
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
                (
                    "ticked_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="ticked_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
                (
                    "work_order",
                    models.ForeignKey(
                        db_column="work_order_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="task_rows",
                        to="metering.workorder",
                    ),
                ),
            ],
            options={
                "db_table": "work_order_tasks",
                "indexes": [
                    models.Index(fields=["tenant", "work_order", "seq"], name="ix_wo_tasks_order")
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("work_order", "seq"), name="uq_work_order_tasks_seq"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("est_minutes__gte", 0)),
                        name="ck_work_order_tasks_minutes_not_negative",
                    ),
                ],
            },
        ),
    ]
