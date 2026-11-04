"""identity 0011 — `native_tokens` + `activation_codes`, each with RLS ENABLE + FORCE.

`CR-187-BRC10` (the native field app, Security §1 / AD-21, `07-endpoints.md`
N24): the native app's bearer sign-in, additive beside the web's cookie
session, and the six-character activation code the office hands a technician.

HUMAN-OWNED (RLS policies are a CLAUDE.md hard-rule-1 🔒 path; credentials are
🔒 identity). HUMAN-REVIEW-PENDING — AI-authored 2026-10-21 under the PO ruling
of 2026-08-09 (*"AI will do it; we will review it later as human"*). The
review-ledger row is owed by the coordinator; not RATIFIED without a sign-off.

The policy is `identity/0010`'s character for character — the `NULLIF` form
(`DEF-639`): deny by default without erroring on an unset GUC — and FORCE as
well as ENABLE, because the migration role owns the table and ENABLE alone
exempts the owner. Postgres only: SQLite has no row-level security.

⚠ **NO RLS EXEMPTION IS TAKEN, UNLIKE `sessions`.** A native token is only ever
presented on a `/api/{tenant}/…` path and its plaintext names its tenant, so it
is looked up UNDER the path tenant's context after the tenant comparison
(`apps/identity/native_auth.py`). `core.rls_guard.TENANT_TABLE_EXEMPTIONS` is
therefore unchanged.

Depends on `tenancy/0001` and not on tenancy's newest migration on purpose, as
`identity/0010` does: the FKs need the `tenants` table and nothing after it.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
TABLES = ("native_tokens", "activation_codes")

POLICY = "".join(
    f"""
ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {t} FORCE ROW LEVEL SECURITY;
CREATE POLICY {t}_tenant_isolation ON {t}
  USING      (tenant_id = {TENANT})
  WITH CHECK (tenant_id = {TENANT});
"""
    for t in TABLES
)

REVERSE = "".join(
    f"""
DROP POLICY IF EXISTS {t}_tenant_isolation ON {t};
ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY;
ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;
"""
    for t in TABLES
)


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0010_def_idn_10023_password_history"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ActivationCode",
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
                ("code_hmac", models.CharField(max_length=64)),
                ("issued_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField()),
                ("issued_by", models.UUIDField(blank=True, null=True)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("failed_attempts", models.IntegerField(default=0)),
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
                        related_name="activation_codes",
                        to="identity.user",
                    ),
                ),
            ],
            options={
                "db_table": "activation_codes",
                "indexes": [
                    models.Index(fields=["user", "used_at"], name="ix_activation_codes_user")
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "code_hmac"), name="uq_activation_codes_tenant_code"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="NativeToken",
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
                ("family_id", models.UUIDField()),
                ("kind", models.TextField()),
                ("token_hash", models.CharField(max_length=64, unique=True)),
                ("device_uid", models.TextField()),
                ("device_name", models.TextField(default="")),
                ("issued_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField()),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_reason", models.TextField(default="")),
                ("ip", models.GenericIPAddressField(blank=True, null=True)),
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
                        related_name="native_tokens",
                        to="identity.user",
                    ),
                ),
            ],
            options={
                "db_table": "native_tokens",
                "indexes": [
                    models.Index(fields=["tenant", "device_uid"], name="ix_native_tokens_device"),
                    models.Index(fields=["family_id"], name="ix_native_tokens_family"),
                    models.Index(fields=["user", "revoked_at"], name="ix_native_tokens_user_live"),
                ],
            },
        ),
        PostgresOnlySQL(POLICY, reverse_sql=REVERSE),
    ]
