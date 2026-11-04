"""billing 0044 — `bill_links` (DEF-BIL-10531), with its RLS policy.

One secret, expiring link to one issued bill's kept PDF, carried by the bill
email (PO 2026-10-22, *"b direct PDF link"*). The policy is `customers/0089`'s
word for word: hard rule 1 admits no tenant table without one; the `NULLIF`
form per DEF-639; `PostgresOnlySQL` skips honestly on sqlite.

HUMAN-OWNED (migration ordering and RLS policies are CLAUDE.md 🔒 paths).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-22 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

Rollback: reverse this migration (the table goes; every emailed link then opens
the "link has expired" page; nothing references the table by FK).
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

TABLE = "bill_links"
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
        ("billing", "0043_def_bil_10147_number_existing_correction_cases"),
        ("tenancy", "0066_def_cus_10445_service_request_settings"),
    ]

    operations = [
        migrations.CreateModel(
            name="BillLink",
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
                ("token_hash", models.CharField(max_length=64)),
                ("issued_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "invoice",
                    models.ForeignKey(
                        db_column="invoice_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bill_links",
                        to="billing.invoice",
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
                "db_table": "bill_links",
                "indexes": [
                    models.Index(fields=["tenant", "invoice"], name="ix_bill_links_invoice")
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("token_hash",), name="uq_bill_links_token"),
                    models.CheckConstraint(
                        condition=models.Q(("expires_at__gt", models.F("issued_at"))),
                        name="ck_bill_links_expires_after_issue",
                    ),
                ],
            },
        ),
        PostgresOnlySQL(POLICY, reverse_sql=REVERSE),
    ]
