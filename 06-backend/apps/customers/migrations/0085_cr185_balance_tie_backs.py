"""customers 0085 — `balance_tie_backs` (CR-185-BRC10), with its RLS policy.

A residue a clerk tied back to the owner, PENDING until the final bill that
puts it in the books is issued, then `posted` (naming the journal entry) or
`nothing_owed` (coordinator ruling 2026-10-14: *"the transfer must move only
money that is IN THE BOOKS"*). The policy is `0083`'s word for word: hard rule 1
admits no tenant table without one; the `NULLIF` form per DEF-639;
`PostgresOnlySQL` skips honestly on sqlite.

HUMAN-OWNED (migration ordering and RLS policies are CLAUDE.md 🔒 paths).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-14 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

Rollback: reverse this migration (the table goes; no other table references it).
"""


import core.dbfields
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

TABLE = "balance_tie_backs"
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
        ("customers", "0084_cr183_temporary_stops"),
        ("tenancy", "0063_def_bil_10147_correction_case_series"),
    ]

    operations = [
        migrations.CreateModel(
            name="BalanceTieBack",
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
                ("status", models.TextField(default="pending")),
                (
                    "preview_amount",
                    models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
                ),
                ("currency", models.CharField(max_length=3)),
                ("final_invoice_id", models.UUIDField(blank=True, null=True)),
                (
                    "posted_amount",
                    models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
                ),
                ("journal_entry_id", models.UUIDField(blank=True, null=True)),
                ("decided_by", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("settled_at", models.DateTimeField(blank=True, null=True)),
                (
                    "account",
                    models.ForeignKey(
                        db_column="account_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="balance_tie_backs",
                        to="customers.account",
                    ),
                ),
                (
                    "owner_account",
                    models.ForeignKey(
                        db_column="owner_account_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="customers.account",
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
                "db_table": "balance_tie_backs",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "account"), name="uq_balance_tie_backs_account"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("status__in", ("pending", "posted", "nothing_owed"))),
                        name="ck_balance_tie_backs_status",
                    ),
                ],
            },
        ),
        PostgresOnlySQL(POLICY, reverse_sql=REVERSE),
    ]
