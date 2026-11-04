"""identity 0014 — `password_links`, with RLS ENABLE + FORCE.

Also `security_policies.password_link_valid_days` (default 7).

`CR-188-BRC10` (PO 2026-10-22, answer 1: *"email a one-time sign-in link
instead, no password."*). The one-time sign-in link a staff invitation or reset
email carries; only its SHA-256 digest is stored (`models.PasswordLink`).

HUMAN-OWNED (RLS policies are a CLAUDE.md hard-rule-1 🔒 path; credentials are
🔒 identity). HUMAN-REVIEW-PENDING — AI-authored 2026-10-22 under the PO ruling
of 2026-08-09 (*"AI will do it; we will review it later as human"*); row in
12-governance/09-human-review-ledger.md. Not RATIFIED without a sign-off.

The policy is `identity/0011`'s character for character — the `NULLIF` form
(`DEF-639`) and FORCE as well as ENABLE. Postgres only: SQLite has no RLS.
No RLS exemption is taken: the public set-password door reads this table only
after `require_tenant` has set the path tenant's context, exactly as the
activation-code door does.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
T = "password_links"

POLICY = f"""
ALTER TABLE {T} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {T} FORCE ROW LEVEL SECURITY;
CREATE POLICY {T}_tenant_isolation ON {T}
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});
"""

REVERSE = f"""
DROP POLICY IF EXISTS {T}_tenant_isolation ON {T};
ALTER TABLE {T} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {T} DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0013_cr187_phone_sign_in"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PasswordLink",
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
                ("purpose", models.TextField()),
                ("token_hash", models.CharField(max_length=64, unique=True)),
                ("issued_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField()),
                ("issued_by", models.UUIDField(blank=True, null=True)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_reason", models.TextField(default="")),
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
                        related_name="password_links",
                        to="identity.user",
                    ),
                ),
            ],
            options={
                "db_table": "password_links",
                "indexes": [
                    models.Index(fields=["user", "used_at"], name="ix_password_links_user")
                ],
            },
        ),
        PostgresOnlySQL(POLICY, reverse_sql=REVERSE),
        # PO 2026-10-22 (*"don't do any hardcoding"*): the link's life is a
        # Security setting, seeded at today's 7 days (BR-IDN-025) so nothing
        # moves the day it ships.
        migrations.AddField(
            model_name="securitypolicy",
            name="password_link_valid_days",
            field=models.IntegerField(default=7),
        ),
    ]
