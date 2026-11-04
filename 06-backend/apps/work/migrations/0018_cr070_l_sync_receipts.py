"""work 0018 — `work_sync_receipts`, the server's memory of an offline day.

CR-070 wave L, task `L1` (`US-WRK-044`, `BR-WRK-042`).

One table. Its whole job is the sentence `WM-48` states as a worked figure:
*"A technician syncs three jobs after a day with no signal; nine photographs
land once each … and a re-sync of the same three jobs adds nothing."* The
uniqueness constraint IS that promise — a second sync adds nothing because the
database refuses it, not because a caller remembered to look first.

⚠ **THE MIGRATION ORDER IS A 🔒 PATH, SO THE DEPENDENCIES ARE NAMED RATHER
THAN INFERRED.** `0017` is wave K's RLS file and the latest in this app;
`work_orders` is metering's table and `metering/0050_cr070_g_dispatch` is the
same node waves H and K both name, deliberately — depending on a LATER metering
migration would couple this file to whichever lane pushed last.

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path (`DEF-GOV-8547`).
"""

import django.db.models.deletion
from django.db import migrations, models

import core.dbfields


class Migration(migrations.Migration):
    dependencies = [
        ("work", "0017_rls_force_evidence"),
        ("metering", "0050_cr070_g_dispatch"),
        ("identity", "0005_cr070_f_field_technician"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkSyncReceipt",
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
                ("kind", models.TextField()),
                ("seq", models.IntegerField(blank=True, null=True)),
                ("captured_at", models.DateTimeField(blank=True, null=True)),
                ("accepted_at", models.DateTimeField(auto_now_add=True)),
                (
                    "accepted_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="accepted_by",
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
                        related_name="sync_receipts",
                        to="metering.workorder",
                    ),
                ),
            ],
            options={
                "db_table": "work_sync_receipts",
                "indexes": [
                    models.Index(
                        fields=["tenant", "work_order", "seq"],
                        name="ix_wo_sync_receipts_order",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "work_order", "key"),
                        name="uq_work_sync_receipts_key",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("key", ""), _negated=True),
                        name="ck_work_sync_receipts_key_present",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "kind__in",
                                (
                                    "safety_tick",
                                    "task_tick",
                                    "reading",
                                    "material",
                                    "attachment",
                                    "signature",
                                    "close",
                                ),
                            )
                        ),
                        name="ck_work_sync_receipts_kind",
                    ),
                ],
            },
        ),
    ]
