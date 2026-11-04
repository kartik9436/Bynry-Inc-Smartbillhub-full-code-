# ── Trace ──────────────────────────────────────────────
# Change:  CR-173-BRC10 — the New World / Logos receipt file placed in the
#          City's SFTP folder. PO 2026-10-07: Q1 (*"it will be in conenctor
#          itself specific to that utility/tenent"*) · Q4 (*"(a) refuse if
#          already sent"*).
# Rules:   CLAUDE.md hard rule 1 (RLS FORCE on every tenant table) · hard rule
#          6 (idempotency by a unique key) · BR-INT-025 (one ACTIVE credential,
#          enforced by the database) · 🔒 migration ordering + 🔒 RLS policies +
#          🔒 idempotency keys (CLAUDE.md sensitive paths)
# Tests:   06-backend/tests/test_cr173_newworld_sftp.py ·
#          06-backend/tests/test_cr173_newworld_sftp_pg.py (PostgreSQL 16: the
#          per-slot guard, the one-per-day refusal under a real second
#          transaction, and the isolation probe)
# ───────────────────────────────────────────────────────
"""integrations 0015 — a second credential SLOT, and `integration_file_delivery` with its policy.

HUMAN-OWNED (🔒 RLS policies + idempotency keys + migration ordering).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-07 under the PO ruling of
2026-08-09; the review-ledger row is in `12-governance/09-human-review-ledger.md`.

TWO CHANGES, BOTH FORCED BY ONE FACT
------------------------------------
New World / Logos is the first connector that holds BOTH a key WE issue (the
City dials `/partner/v1/receipts`) AND a password THEY gave us (we dial their
SFTP folder). Until now a connection held one active credential, by the
database (`0001`: `EXCLUDE (connection_id WITH =) WHERE is_active`), so storing
the SFTP password through `record_credential` would have **deactivated the
partner's key** — the City's next pull refused, with nothing on any screen to
say why.

**1 · `slot` on `integration_credential`, and the guard becomes per (connection,
slot).** Every existing row is `primary` by the column default, so nothing that
exists moves and every existing reader — which now names `primary` — reads
exactly the row it read before. Exactly one active credential per connection
PER SLOT is still enforced by the database, on both vendors.

**2 · `integration_file_delivery`**, with its RLS policy in this same file (a
tenant table that exists for one migration without a policy is a hard-rule-1
breach with a window in it — `0009` and `0014` set the precedent). Its partial
unique index is the *one file per utility per day* refusal; see the model's
docstring for why it cannot live on the partitioned `integration_run`.

SQLite has no RLS and no EXCLUDE; it gets the partial unique index form of the
guard, exactly as `0001` did, and the probe that proves the PostgreSQL half
carries `requires_postgres` and SKIPS there rather than passing vacuously.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models

from core.rls import tenant_isolation_policy_sql

TABLE = "integration_file_delivery"

OLD_GUARD_PG_DROP = (
    "ALTER TABLE integration_credential "
    "DROP CONSTRAINT IF EXISTS ex_integration_credential_one_active;"
)
OLD_GUARD_PG_ADD = """
ALTER TABLE integration_credential
  ADD CONSTRAINT ex_integration_credential_one_active
  EXCLUDE USING btree (connection_id WITH =) WHERE (is_active);
"""
NEW_GUARD_PG = """
ALTER TABLE integration_credential
  ADD CONSTRAINT ex_integration_credential_one_active_slot
  EXCLUDE USING btree (connection_id WITH =, slot WITH =) WHERE (is_active);
"""
NEW_GUARD_PG_DROP = (
    "ALTER TABLE integration_credential "
    "DROP CONSTRAINT IF EXISTS ex_integration_credential_one_active_slot;"
)
OLD_GUARD_SQLITE_DROP = "DROP INDEX IF EXISTS ux_integration_credential_one_active;"
OLD_GUARD_SQLITE_ADD = (
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_integration_credential_one_active "
    "ON integration_credential (connection_id) WHERE is_active;"
)
NEW_GUARD_SQLITE = (
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_integration_credential_one_active_slot "
    "ON integration_credential (connection_id, slot) WHERE is_active;"
)
NEW_GUARD_SQLITE_DROP = "DROP INDEX IF EXISTS ux_integration_credential_one_active_slot;"


def swap_guard(apps_registry, schema_editor):
    """The old one-per-connection guard OUT, the one-per-(connection, slot) guard IN.

    Dropped and added in one migration, which on PostgreSQL is one transaction:
    there is no instant at which the table holds no guard at all.
    """
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(OLD_GUARD_PG_DROP)
        schema_editor.execute(NEW_GUARD_PG)
    else:
        schema_editor.execute(OLD_GUARD_SQLITE_DROP)
        schema_editor.execute(NEW_GUARD_SQLITE)


def restore_guard(apps_registry, schema_editor):
    """Reverse. ⚠ It fails — correctly — if any connection holds two active
    credentials in different slots, because the old guard cannot hold that
    state. Deactivate the second slot first; the error names the constraint."""
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(NEW_GUARD_PG_DROP)
        schema_editor.execute(OLD_GUARD_PG_ADD)
    else:
        schema_editor.execute(NEW_GUARD_SQLITE_DROP)
        schema_editor.execute(OLD_GUARD_SQLITE_ADD)


def apply_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(tenant_isolation_policy_sql(TABLE))


def drop_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(f"DROP POLICY IF EXISTS {TABLE}_tenant_isolation ON {TABLE};")
    schema_editor.execute(f"ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY;")
    schema_editor.execute(f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;")


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0014_cr115_custom_apis"),
        ("tenancy", "0044_cr094_i_account_document_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="integrationcredential",
            name="slot",
            field=models.TextField(default="primary"),
        ),
        migrations.RunPython(swap_guard, restore_guard),
        migrations.CreateModel(
            name="IntegrationFileDelivery",
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
                ("operation", models.TextField()),
                ("data_day", models.DateField()),
                ("filename", models.TextField()),
                ("folder", models.TextField()),
                (
                    "status",
                    models.TextField(
                        choices=[("sending", "sending"), ("sent", "sent"), ("failed", "failed")]
                    ),
                ),
                ("is_resend", models.BooleanField(default=False)),
                (
                    "trigger",
                    models.TextField(
                        choices=[
                            ("manual", "manual"),
                            ("scheduled", "scheduled"),
                            ("dispatcher", "dispatcher"),
                            ("webhook", "webhook"),
                            ("partner", "partner"),
                            ("inline", "inline"),
                        ]
                    ),
                ),
                ("started_by_name", models.TextField(blank=True, null=True)),
                ("reason", models.TextField(blank=True, null=True)),
                ("receipt_count", models.IntegerField(default=0)),
                ("unbalanced_count", models.IntegerField(default=0)),
                ("unresolved_gl_count", models.IntegerField(default=0)),
                ("byte_count", models.IntegerField(default=0)),
                ("failure", models.TextField(blank=True, null=True)),
                ("run_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "connection",
                    models.ForeignKey(
                        db_column="connection_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="file_deliveries",
                        to="integrations.integrationconnection",
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
                "db_table": "integration_file_delivery",
                "indexes": [
                    models.Index(
                        fields=["tenant", "connection", "-data_day"],
                        name="ix_intg_file_delivery_day",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("is_resend", False), ("status__in", ("sending", "sent"))),
                        fields=("tenant", "connection", "operation", "data_day"),
                        name="uq_intg_file_delivery_one_per_day",
                    )
                ],
            },
        ),
        migrations.RunPython(apply_rls, drop_rls),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-173-BRC10 (the 2026-10-07 rulings verbatim) + B2 §3 + hard rules 1, 6
# generated: 2026-10-07 by the CR-173-BRC10 lane NW-SFTP
# checklist: A✔ B=n/a C✔ D=n/a E=n/a F✔ G✔ H=deferred(🔒 row in 09-human-review-ledger.md)
# gates: makemigrations --check clean · pytest tests/test_cr173_newworld_sftp.py · tests/test_cr173_newworld_sftp_pg.py on PostgreSQL 16
# exceptions: none
# status: VERIFIED-UNRATIFIED · HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────
