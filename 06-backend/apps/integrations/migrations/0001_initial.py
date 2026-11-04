# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-014 (EP-INT-05) — the five tables, anchored in the schema
#           brief FIRST (C34; B2 §2 "Module: integrations" + Addendum r22 landed
#           in the commit before this one — TC-7 asserts the order).
# Rules:    BR-INT-025 (exactly one active credential, enforced by the database)
#           · BR-INT-026 (UNIQUE tenant × provider × environment) · BR-INT-032
#           (UNIQUE on the external side) · BR-INT-039 (the run table is
#           append-only and partitioned yearly) · CLAUDE.md hard rule 4's shape
#           (no UPDATE after finish, no DELETE, corrections are new rows) ·
#           🔒 migration ordering (CLAUDE.md sensitive paths)
# Tests:    06-backend/tests/test_us_int_014_tables.py (SQLite: the UNIQUEs,
#           the one-active guard as a partial index, TC-5, TC-7) ·
#           06-backend/tests/test_us_int_014_pg.py (PostgreSQL: TC-1 the
#           EXCLUDE, TC-4 the append-only trigger, the partition shape)
# Impacts:  core/partitioning.py (integration_run is in REGISTRY and
#           ACTIVE_TABLES so the create-ahead job renews it) · 0002_rls_force
#           (RLS on all five, its own migration)
# ───────────────────────────────────────────────────────
"""integrations 0001 — the five tables. HUMAN-OWNED (migration ordering is a
CLAUDE.md 🔒 sensitive path; this is the module's FIRST migration).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-03 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"), implementing the SIGNED
schema only: B2 §2 `Module: integrations` + Addendum r22, written the commit
before this one. Row in 12-governance/09-human-review-ledger.md; not RATIFIED
without a recorded human sign-off.

WHAT THIS CREATES, ON BOTH VENDORS
----------------------------------
Five tables through Django's own `CreateModel`, so the SQLite test database has
every column, every UNIQUE and every index the models declare. Then three
things PostgreSQL does that SQLite cannot, each behind a vendor check and each
asserted live in `tests/test_us_int_014_pg.py` rather than faked:

  1. **`integration_credential` — exactly one active row per connection, by the
     DATABASE** (BR-INT-025). On PostgreSQL an `EXCLUDE USING btree
     (connection_id WITH =) WHERE (is_active)` — the shape the design names.
     On SQLite a partial UNIQUE index, which is the same guarantee in the only
     form that engine has. One guard per vendor, never two on one.
  2. **`integration_run` — a PARTITIONED PARENT**, yearly on `started_at`
     (BR-INT-039; `core/partitioning.py`, which already knows the table). The
     Django-created plain table is dropped and re-created with `PARTITION BY
     RANGE (started_at)`, the current year and one ahead are bootstrapped, and
     every partition is born WITH its tenant policy in the same statement
     (DEF-027 — `create_partition_sql` is the only producer of `PARTITION OF`
     DDL in this codebase, and it emits the guard in the same string).
  3. **`integration_run` is APPEND-ONLY once finished.** A trigger refuses
     every DELETE and every UPDATE of a row whose `finished_at` is set —
     corrections are new rows, hard rule 4's shape one module along. A run that
     is still open (`finished_at IS NULL`) may be finished exactly once.

⚠ THE FOREIGN KEYS OF THE PARTITIONED PARENT COME FROM DJANGO, NOT FROM THE RAW
DDL, AND THAT IS DELIBERATE. `CreateModel` DEFERS its FK constraints to the end
of the migration — after this `RunPython` — so the re-created parent receives
`tenant_id → tenants` and `connection_id → integration_connection` from
Django's own deferred `ALTER TABLE … ADD CONSTRAINT`, with Django's names.
Writing `REFERENCES` into the raw DDL as well would leave the table with two
constraints on each column, one of them nameless to the ORM. The same is true
of the Meta indexes: Django creates them after this operation, on the
partitioned parent, and PostgreSQL propagates a parent index to every existing
and future partition. `apps/audit/0001` records the identical reasoning.

⚠ NOTE ON `%%` in the trigger: `schema_editor.execute(sql)` hands the string to
psycopg with an EMPTY params tuple, so a lone `%` is read as a placeholder and
the migration dies with `incomplete placeholder` (DEF-064). Every `%` below
is doubled and arrives at the server as one.

Ordering: after tenancy, identity and customers — the three modules whose
tables these reference (B2 r22 names the two cross-module FKs). RLS ENABLE +
FORCE on all five rides `0002_rls_force`, in its own migration as the brief
requires.
"""

from datetime import date

from django.db import migrations, models

import core.crypto
import core.dbfields
from core import partitioning

RUN_TABLE = "integration_run"

#: The parent DDL mirrors the CreateModel columns EXACTLY (B2 §2 Module:
#: integrations). No REFERENCES here — see the module docstring.
PARTITIONED_PARENT_SQL = """
DROP TABLE IF EXISTS integration_run;
CREATE TABLE integration_run (
  id             uuid        NOT NULL,
  tenant_id      uuid        NOT NULL,
  connection_id  uuid        NOT NULL,
  operation      text        NOT NULL,
  job_id         uuid,
  direction      text        NOT NULL,
  trigger        text        NOT NULL,
  attempted      integer     NOT NULL DEFAULT 0,
  succeeded      integer     NOT NULL DEFAULT 0,
  failed         integer     NOT NULL DEFAULT 0,
  skipped        integer     NOT NULL DEFAULT 0,
  changed        integer     NOT NULL DEFAULT 0,
  outcome        text,
  summary        text,
  provider_error text,
  input_hash     text,
  artifact_link  text,
  trace_id       text        NOT NULL,
  started_at     timestamptz NOT NULL DEFAULT now(),   -- the partition key (B2 r22)
  finished_at    timestamptz,
  PRIMARY KEY (tenant_id, started_at, id)              -- includes the partition key
) PARTITION BY RANGE (started_at);

-- BR-INT-039 / hard rule 4's shape: a FINISHED run is never updated, and no
-- run is ever deleted. Corrections are new rows.
CREATE OR REPLACE FUNCTION integration_run_append_only() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'BR-INT-039: integration_run is append-only — a run is never deleted (attempted %%)', lower(TG_OP);
  END IF;
  IF OLD.finished_at IS NOT NULL THEN
    RAISE EXCEPTION 'BR-INT-039: integration_run %% finished at %% is append-only — corrections are new rows', OLD.id, OLD.finished_at;
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_integration_run_append_only ON integration_run;
CREATE TRIGGER trg_integration_run_append_only
  BEFORE UPDATE OR DELETE ON integration_run
  FOR EACH ROW EXECUTE FUNCTION integration_run_append_only();
"""

#: The same columns as a PLAIN table — what the reverse hands back to Django so
#: its own `DeleteModel` has something to drop (see `drop_partitioned_parent`).
PLAIN_PARENT_SQL = """
CREATE TABLE integration_run (
  id             uuid        NOT NULL,
  tenant_id      uuid        NOT NULL,
  connection_id  uuid        NOT NULL,
  operation      text        NOT NULL,
  job_id         uuid,
  direction      text        NOT NULL,
  trigger        text        NOT NULL,
  attempted      integer     NOT NULL DEFAULT 0,
  succeeded      integer     NOT NULL DEFAULT 0,
  failed         integer     NOT NULL DEFAULT 0,
  skipped        integer     NOT NULL DEFAULT 0,
  changed        integer     NOT NULL DEFAULT 0,
  outcome        text,
  summary        text,
  provider_error text,
  input_hash     text,
  artifact_link  text,
  trace_id       text        NOT NULL,
  started_at     timestamptz NOT NULL DEFAULT now(),
  finished_at    timestamptz,
  PRIMARY KEY (tenant_id, started_at, id)
);
"""

#: BR-INT-025 — exactly one active credential per connection, by the database.
ONE_ACTIVE_PG = """
ALTER TABLE integration_credential
  ADD CONSTRAINT ex_integration_credential_one_active
  EXCLUDE USING btree (connection_id WITH =) WHERE (is_active);
"""
ONE_ACTIVE_SQLITE = """
CREATE UNIQUE INDEX IF NOT EXISTS ux_integration_credential_one_active
  ON integration_credential (connection_id) WHERE is_active;
"""


def create_partitioned_parent(apps_registry, schema_editor):
    """PostgreSQL only: swap the plain run table for the partitioned parent,
    bootstrap this year and next (create_ahead = 1), and install the
    append-only trigger. SQLite keeps the plain table — recorded above."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(PARTITIONED_PARENT_SQL)
    this_year = partitioning.year_start(date.today())
    for offset in range(2):  # the current year + 1 ahead (REGISTRY.create_ahead)
        period = partitioning.add_years(this_year, offset)
        schema_editor.execute(partitioning.create_partition_sql(RUN_TABLE, period))


def drop_partitioned_parent(apps_registry, schema_editor):
    """Reverse: the parent goes with its partitions and its trigger function,
    and a PLAIN table with the same columns is put back in its place — because
    Django's own reverse of `CreateModel` runs AFTER this and drops
    `integration_run` by name, so the table has to exist for the reverse of the
    whole migration to complete. Measured 2026-09-03: without the re-create,
    `migrate integrations zero` died with `table "integration_run" does not
    exist` and PostgreSQL rolled the reverse back."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("DROP TABLE IF EXISTS integration_run CASCADE;")
    schema_editor.execute("DROP FUNCTION IF EXISTS integration_run_append_only();")
    schema_editor.execute(PLAIN_PARENT_SQL)


def add_one_active_guard(apps_registry, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(ONE_ACTIVE_PG)
    else:
        schema_editor.execute(ONE_ACTIVE_SQLITE)


def drop_one_active_guard(apps_registry, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(
            "ALTER TABLE integration_credential "
            "DROP CONSTRAINT IF EXISTS ex_integration_credential_one_active;"
        )
    else:
        schema_editor.execute("DROP INDEX IF EXISTS ux_integration_credential_one_active;")


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("tenancy", "0036_def3422_drop_bell_events"),
        ("identity", "0004_rls_security_policies"),
        ("customers", "0039_def2847_mailing_address_line2_country"),
    ]

    operations = [
        migrations.CreateModel(
            name="IntegrationConnection",
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
                ("provider_key", models.TextField()),
                ("label", models.TextField(blank=True, null=True)),
                (
                    "environment",
                    models.TextField(
                        choices=[("production", "production"), ("sandbox", "sandbox")]
                    ),
                ),
                (
                    "status",
                    models.TextField(
                        choices=[
                            ("not_set_up", "not_set_up"),
                            ("untested", "untested"),
                            ("working", "working"),
                            ("not_working", "not_working"),
                            ("off", "off"),
                        ]
                    ),
                ),
                ("enabled", models.BooleanField(default=True)),
                (
                    "cadence",
                    models.TextField(
                        choices=[
                            ("nightly", "nightly"),
                            ("hourly", "hourly"),
                            ("manual", "manual"),
                        ],
                        default="manual",
                    ),
                ),
                ("next_run_at", models.DateTimeField(blank=True, null=True)),
                ("config", models.JSONField(blank=True, default=dict)),
                ("last_test_at", models.DateTimeField(blank=True, null=True)),
                ("last_test_ok", models.BooleanField(blank=True, null=True)),
                ("last_test_text", models.TextField(blank=True, null=True)),
                ("connected_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "connected_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="connected_by",
                        null=True,
                        on_delete=models.deletion.PROTECT,
                        related_name="+",
                        to="identity.user",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "integration_connection",
                "indexes": [
                    models.Index(
                        fields=["tenant", "provider_key"], name="ix_intg_connection_provider"
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "provider_key", "environment"),
                        name="uq_integration_connection_key_env",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="IntegrationCredential",
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
                ("version", models.IntegerField()),
                ("is_active", models.BooleanField()),
                (
                    "payload_enc",
                    core.crypto.EncryptedTextField(
                        crypto_context="integration_credential.payload_enc"
                    ),
                ),
                ("blind_index", models.TextField(blank=True, null=True)),
                ("masked_hint", models.TextField()),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("rotated_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "connection",
                    models.ForeignKey(
                        db_column="connection_id",
                        on_delete=models.deletion.PROTECT,
                        related_name="credentials",
                        to="integrations.integrationconnection",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "integration_credential",
                "indexes": [
                    models.Index(fields=["tenant", "blind_index"], name="ix_intg_credential_blind")
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("connection", "version"),
                        name="uq_integration_credential_version",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="IntegrationTargetReference",
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
                ("target_key", models.TextField()),
                (
                    "entity_type",
                    models.TextField(
                        choices=[
                            ("ledger_account", "ledger_account"),
                            ("tender", "tender"),
                            ("route", "route"),
                            ("reversal_reason", "reversal_reason"),
                            ("meter_type", "meter_type"),
                            ("service", "service"),
                        ]
                    ),
                ),
                ("entity_id", models.UUIDField(blank=True, null=True)),
                ("local_value", models.TextField(blank=True, null=True)),
                ("external_value", models.TextField()),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "integration_target_reference",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant", "target_key", "entity_type", "external_value"),
                        name="uq_integration_target_ref_external",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="IntegrationConsent",
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
                ("grantee", models.TextField()),
                ("scope", models.JSONField()),
                ("granted_at", models.DateTimeField()),
                ("granted_by", models.UUIDField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_by", models.UUIDField(blank=True, null=True)),
                (
                    "account",
                    models.ForeignKey(
                        db_column="account_id",
                        on_delete=models.deletion.PROTECT,
                        related_name="+",
                        to="customers.account",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "integration_consent",
            },
        ),
        migrations.CreateModel(
            name="IntegrationRun",
            fields=[
                (
                    "pk",
                    models.CompositePrimaryKey(
                        "tenant_id",
                        "started_at",
                        "id",
                        blank=True,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("id", models.UUIDField(default=core.dbfields.uuid7, editable=False)),
                ("operation", models.TextField()),
                ("job_id", models.UUIDField(blank=True, null=True)),
                (
                    "direction",
                    models.TextField(
                        choices=[
                            ("outbound", "outbound"),
                            ("inbound", "inbound"),
                            ("inbound_read", "inbound_read"),
                        ]
                    ),
                ),
                (
                    "trigger",
                    models.TextField(
                        choices=[
                            ("manual", "manual"),
                            ("scheduled", "scheduled"),
                            ("dispatcher", "dispatcher"),
                            ("webhook", "webhook"),
                            ("partner", "partner"),
                        ]
                    ),
                ),
                ("attempted", models.IntegerField(default=0)),
                ("succeeded", models.IntegerField(default=0)),
                ("failed", models.IntegerField(default=0)),
                ("skipped", models.IntegerField(default=0)),
                ("changed", models.IntegerField(default=0)),
                (
                    "outcome",
                    models.TextField(
                        blank=True,
                        choices=[
                            ("queued", "queued"),
                            ("running", "running"),
                            ("succeeded", "succeeded"),
                            ("partial", "partial"),
                            ("failed", "failed"),
                            ("unconfirmed", "unconfirmed"),
                            ("indeterminate", "indeterminate"),
                        ],
                        null=True,
                    ),
                ),
                ("summary", models.TextField(blank=True, null=True)),
                ("provider_error", models.TextField(blank=True, null=True)),
                ("input_hash", models.TextField(blank=True, null=True)),
                ("artifact_link", models.TextField(blank=True, null=True)),
                ("trace_id", models.TextField()),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "connection",
                    models.ForeignKey(
                        db_column="connection_id",
                        on_delete=models.deletion.PROTECT,
                        related_name="runs",
                        to="integrations.integrationconnection",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "integration_run",
                "indexes": [
                    models.Index(
                        fields=["tenant", "connection", "operation", "-started_at"],
                        name="ix_intg_run_latest_per_op",
                    ),
                    models.Index(fields=["tenant", "trace_id"], name="ix_intg_run_trace"),
                    models.Index(fields=["tenant", "input_hash"], name="ix_intg_run_input_hash"),
                ],
            },
        ),
        # PostgreSQL: the run table becomes a partitioned parent with its
        # append-only trigger and two bootstrap partitions, each born guarded.
        migrations.RunPython(create_partitioned_parent, drop_partitioned_parent),
        # Both vendors: exactly one active credential per connection.
        migrations.RunPython(add_one_active_guard, drop_one_active_guard),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-014@62d3643 (EP-INT-05 story + BR-INT-018..053 snapshot)
# generated: 2026-09-03 by the CR-069 wave A build lane
# checklist: A✔ B✔ C✔ D✔(selectors/api read these) E✔(IntegrationsTab.tsx) F✔ G✔ H=PENDING(🔒 migration ordering — ledger row 09-human-review-ledger.md)
# gates: applied forward and backward on PostgreSQL 16 on an empty database (createdb → migrate → migrate integrations zero) · makemigrations --check clean on SQLite · G16 (integration_run created PARTITION BY and present in ACTIVE_TABLES) · tests/test_us_int_014_pg.py · tests/test_def_027_partition_rls_create_ahead.py (every partition carries its policy)
# exceptions: SQLite keeps the plain run table (no partition, no trigger) — recorded in the docstring, asserted on PostgreSQL only · the FKs of the partitioned parent come from Django's deferred SQL, not the raw DDL, so there is exactly one constraint per column
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
