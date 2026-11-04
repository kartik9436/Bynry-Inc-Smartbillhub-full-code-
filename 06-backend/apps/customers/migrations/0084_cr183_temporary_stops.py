"""customers 0084 — `temporary_stops` and its RLS policy (`CR-183-BRC10`).

PO rulings 2026-10-14 (decision log *"TEMPORARY STOP — FOUR PO RULINGS
(B1–B4)"*): a customer's stop-service ask becomes a typed, scheduled hold on the
account — base charge only while it lasts, an optional field visit, 10 days to
12 months, and the customer may end it early. One row per hold.

⚠ **ONE FILE, BOTH HALVES**, as `0083`: an ordinary `CreateModel` (no data step
— no hold existed before today) and the tenant policy in the `NULLIF` form
(DEF-639). `PostgresOnlySQL` skips honestly on sqlite.

HUMAN-OWNED (migration ordering and RLS policies are CLAUDE.md 🔒 paths).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-14 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.
"""

import core.dbfields
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

TABLE = "temporary_stops"
TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"

POLICY = f"""
ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY;
CREATE POLICY {TABLE}_tenant_isolation ON {TABLE}
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});
"""

REVERSE = f"""
DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE};
ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0083_cr181_move_in_reopenings"),
        ("identity", "0010_def_idn_10023_password_history"),
        ("tenancy", "0061_cr172_logo_to_document_store"),
    ]

    operations = [
        migrations.CreateModel(
            name="TemporaryStop",
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
                ("channel", models.TextField(default="customer_portal")),
                ("status", models.TextField(default="requested")),
                ("stop_from", models.DateField()),
                ("restart_on", models.DateField(blank=True, null=True)),
                ("reason", models.TextField(blank=True, null=True)),
                ("field_visit_needed", models.BooleanField(default=False)),
                ("shutoff_order_no", models.TextField(blank=True, null=True)),
                ("turnon_order_no", models.TextField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("ended_early", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.ForeignKey(
                        db_column="account_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="temporary_stops",
                        to="customers.account",
                    ),
                ),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="approved_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
                (
                    "request",
                    models.OneToOneField(
                        blank=True,
                        db_column="request_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="temporary_stop",
                        to="customers.servicerequest",
                    ),
                ),
                (
                    "restart_request",
                    models.OneToOneField(
                        blank=True,
                        db_column="restart_request_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="temporary_stop_restart",
                        to="customers.servicerequest",
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
                "db_table": "temporary_stops",
                "indexes": [
                    models.Index(fields=["tenant", "account"], name="ix_temporary_stops_account"),
                    models.Index(fields=["tenant", "status"], name="ix_temporary_stops_status"),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "status__in",
                                (
                                    "requested",
                                    "scheduled",
                                    "on_hold",
                                    "ended",
                                    "refused",
                                    "cancelled",
                                ),
                            )
                        ),
                        name="ck_temporary_stops_status",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("channel__in", ("customer_portal", "staff"))),
                        name="ck_temporary_stops_channel",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("restart_on__isnull", True),
                            ("restart_on__gt", models.F("stop_from")),
                            _connector="OR",
                        ),
                        name="ck_temporary_stops_restart_after_stop",
                    ),
                ],
            },
        ),
        PostgresOnlySQL(POLICY, reverse_sql=REVERSE),
    ]
