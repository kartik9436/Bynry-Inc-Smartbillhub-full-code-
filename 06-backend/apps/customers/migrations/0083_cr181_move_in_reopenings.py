"""customers 0083 — `move_in_reopenings` and its RLS policy (`CR-181-BRC10`).

PO rulings 2026-10-13 (decision log *"RETURNING CUSTOMER AT MOVE-IN — FOUR PO
RULINGS"*): a returning customer's closed account on THIS unit may be REOPENED
at move-in (Q2), and the clerk chooses whether its old balance is paid first or
carried (Q3). One row per move-in that reopened, written once at Complete.

⚠ **ONE FILE, BOTH HALVES.** An ordinary `CreateModel` — no data step, no
backfill, no move-in before today reopened anything — and then the tenant
policy, word for word as `0082`'s: hard rule 1 admits no tenant table without
one. The `NULLIF` form per DEF-639 (deny-by-default without erroring on an unset
GUC); `PostgresOnlySQL` skips honestly on sqlite.

HUMAN-OWNED (migration ordering and RLS policies are CLAUDE.md 🔒 paths).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-13 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.
"""

import core.dbfields
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

TABLE = "move_in_reopenings"
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
        ("customers", "0082_rls_def_cus_10042_request_extra_messages"),
        ("tenancy", "0061_cr172_logo_to_document_store"),
    ]

    operations = [
        migrations.CreateModel(
            name="MoveInReopening",
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
                ("previous_opened_at", models.DateField(blank=True, null=True)),
                ("previous_closed_at", models.DateField()),
                ("balance_choice", models.TextField(blank=True, null=True)),
                (
                    "balance_at_complete",
                    models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
                ),
                ("currency", models.CharField(blank=True, max_length=3, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "account",
                    models.ForeignKey(
                        db_column="account_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reopenings",
                        to="customers.account",
                    ),
                ),
                (
                    "move_record",
                    models.OneToOneField(
                        db_column="move_record_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reopening",
                        to="customers.moverecord",
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
                "db_table": "move_in_reopenings",
                "indexes": [
                    models.Index(fields=["tenant", "account"], name="ix_move_in_reopenings_account")
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            ("balance_choice__isnull", True),
                            ("balance_choice__in", ("pay_first", "carry")),
                            _connector="OR",
                        ),
                        name="ck_move_in_reopenings_choice",
                    )
                ],
            },
        ),
        PostgresOnlySQL(POLICY, reverse_sql=REVERSE),
    ]
