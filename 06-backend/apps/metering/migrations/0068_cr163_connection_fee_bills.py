"""metering 0068 — the bills a fee ADDED to a build after submission raised
(`CR-163-BRC10` item 2, 2026-10-02).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-02 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`.

ONE TABLE, ONE UNIQUE KEY, ONE INDEX, ONE RLS POLICY. No backfill: no build has
ever had a fee added after submission, because there was no door to add one.

A build's quote is issued at Create, so an added fee cannot be a line on it
(hard rule 4 — an issued line is never edited). It is a NEW issued bill, and
this table is metering's note of which build it belongs to: the invoice is
billing's, held here as an id (`connections.quote_invoice_id`'s posture — no
cross-module foreign key, B2 §2). `uq_connection_fee_bills_invoice` makes one
bill belong to at most one build.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

TABLE = "connection_fee_bills"
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
        ("metering", "0067_cr161_w4_custom_data"),
        ("tenancy", "0046_cr122_brc06_move_in_draft"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConnectionFeeBill",
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
                ("invoice_id", models.UUIDField()),
                ("charge_code", models.TextField()),
                ("created_by", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "connection",
                    models.ForeignKey(
                        db_column="connection_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="fee_bills",
                        to="metering.connection",
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
                "db_table": "connection_fee_bills",
                "indexes": [
                    models.Index(
                        fields=["tenant", "connection"], name="ix_connection_fee_bills_conn"
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "invoice_id"), name="uq_connection_fee_bills_invoice"
                    )
                ],
            },
        ),
        PostgresOnlySQL(POLICY, reverse_sql=REVERSE_POLICY),
    ]
