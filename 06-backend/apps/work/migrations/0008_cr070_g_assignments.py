"""work 0008 — `work_order_assignments`: who had this job, and when.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-05 under the PO ruling of
2026-08-09. Its row is in `12-governance/09-human-review-ledger.md` (task `G5`).

`CR-070` wave G task `G1` · `US-WRK-025` · `BR-WRK-025` · `WM-15` ·
`03-field-map.md` §2.4 · hard rule 1.

ONE TABLE, AND IT IS A HISTORY
------------------------------
`BR-WRK-025`, verbatim: *"Assignment is an APPEND-ONLY history — assign,
unassign, schedule, depart, arrive are rows in `work_order_assignments`. **Never
an UPDATE.**"* The order carries three cache columns (`metering/0050`) that say
who has it NOW; these rows say who had it before, when it came off them, and
what time the van actually left.

The refusal itself is `work/0009`, which is where the trigger and the RLS
policy live together — a table that could be rewritten across a tenant boundary
and a table that could be rewritten at all are the same failure with different
blast radii, and separating them into two migrations would let a database exist
in a state where one holds and the other does not.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0004_rls_security_policies"),
        ("metering", "0050_cr070_g_dispatch"),
        ("tenancy", "0038_rls_cr068_d_published_content"),
        ("work", "0007_rls_force_workforce"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkOrderAssignment",
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
                ("act", models.TextField()),
                ("scheduled_for", models.DateTimeField(blank=True, null=True)),
                ("window_start", models.DateTimeField(blank=True, null=True)),
                ("window_end", models.DateTimeField(blank=True, null=True)),
                ("at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        db_column="actor_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
                (
                    "crew",
                    models.ForeignKey(
                        blank=True,
                        db_column="crew_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="assignments",
                        to="work.crew",
                    ),
                ),
                (
                    "technician",
                    models.ForeignKey(
                        blank=True,
                        db_column="technician_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="assignments",
                        to="work.technician",
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
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="assignments",
                        to="metering.workorder",
                    ),
                ),
            ],
            options={"db_table": "work_order_assignments"},
        ),
        migrations.AddIndex(
            model_name="workorderassignment",
            index=models.Index(
                fields=["tenant", "work_order", "at"], name="ix_wo_assignments_order"
            ),
        ),
        migrations.AddConstraint(
            model_name="workorderassignment",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    act__in=("assign", "unassign", "schedule", "depart", "arrive")
                ),
                name="ck_work_order_assignments_act",
            ),
        ),
        migrations.AddConstraint(
            model_name="workorderassignment",
            constraint=models.CheckConstraint(
                condition=models.Q(technician__isnull=True) | models.Q(crew__isnull=True),
                name="ck_work_order_assignments_one_holder",
            ),
        ),
    ]
