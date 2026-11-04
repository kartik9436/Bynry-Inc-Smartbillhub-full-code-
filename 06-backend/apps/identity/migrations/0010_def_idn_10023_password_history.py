"""identity 0010 — `password_history` + its RLS (ENABLE + FORCE).

HUMAN-OWNED (RLS policies are a CLAUDE.md hard-rule-1 🔒 path; credentials are
🔒 identity). HUMAN-REVIEW-PENDING — AI-authored 2026-10-08 under the PO ruling
of 2026-08-09 (*"AI will do it; we will review it later as human"*) and the PO
ruling of 2026-10-08 that orders the table built (*"go - build the last 5
passwords check"*, `DEF-IDN-10023`). Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

The policy is `work/0036`'s character for character — the `NULLIF` form
(`DEF-639`): deny by default without erroring on an unset GUC — and FORCE as
well as ENABLE, because the migration role owns the table and ENABLE alone
exempts the owner. Postgres only: SQLite has no row-level security.

Depends on `tenancy/0001` and not on tenancy's newest migration on purpose: the
FK needs the `tenants` table and nothing after it, and naming the newest would
tie this file to whichever tenancy lane landed last.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
TABLE = "password_history"

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
        ("identity", "0009_def_idn_9748_technicians_to_the_field_app"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PasswordHistory",
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
                ("password_hash", models.TextField()),
                ("created_at", models.DateTimeField()),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        db_column="user_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="password_history",
                        to="identity.user",
                    ),
                ),
            ],
            options={
                "db_table": "password_history",
                "indexes": [
                    models.Index(fields=["user", "-created_at"], name="ix_password_history_user")
                ],
            },
        ),
        PostgresOnlySQL(POLICY, reverse_sql=REVERSE),
    ]
