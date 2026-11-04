"""audit 0001 — `audit_log`, LAST in the B2 §7 migration order. HUMAN-OWNED
(migration ordering is a CLAUDE.md 🔒 sensitive path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-09 under PO ruling 2026-08-09
("AI will do it; we will review it later as human"), implementing the SIGNED
schema only: B2 §audit DDL verbatim (US-AUD-001 §1) + NFR-24/28 monthly
partitioning (r16 #1 supersedes the stale §5 do-not-partition note) +
BR-AUD-002 append-only + BR-AUD-015 no-FK tenant_id. Row per file in
12-governance/09-human-review-ledger.md; not RATIFIED without human sign-off.

Ordering: depends on identity 0001 so the global chain is
tenancy → identity → audit exactly as B2 §7 orders modules (audit last).

Two-vendor reality, recorded honestly:
- Postgres: the Django-created plain table is dropped and re-created as the
  PARTITIONED parent — `PARTITION BY RANGE (created_at)`, PK
  (tenant_id, created_at, id) including the partition key, `DEFAULT now()`
  stamped at INSERT (US-AUD-001 §5), the append-only trigger and bootstrap
  partitions; the ix_audit_entity lookup index is created by Django's own
  deferred Meta-index statement AFTER this operation (see the SQL note below), the
  append-only trigger (no row mutation path exists anywhere, BR-AUD-002 /
  B2 §3 trigger family), and bootstrap partitions current month + 3 ahead
  (B2 §5; steady-state create-ahead = core/partitioning.py BE-10 job).
- sqlite (test DB): the plain table stands so model/constraint tests run;
  partitioning, the trigger, and RLS are untestable there — those assertions
  live in the G5 isolation suite against live Postgres, never faked.

RLS (ENABLE+FORCE per the B2 §3 template) rides 0002_rls_w0_policies.
"""

from datetime import date

import core.dbfields
from django.db import migrations, models

# The parent DDL mirrors the CreateModel columns EXACTLY (B2 §audit).
PARTITIONED_PARENT_SQL = """
DROP TABLE IF EXISTS audit_log;
CREATE TABLE audit_log (
  id            uuid NOT NULL,
  tenant_id     uuid NOT NULL,               -- no FK: no cascade from tenants (BR-AUD-015).
                                             -- NOT a retention promise — the day-91 purge
                                             -- deletes these rows (BR-TEN-044, PO 2026-08-10)
  actor_user_id uuid,                        -- null = system job (BR-AUD-003)
  action        text NOT NULL,
  entity_type   text NOT NULL,
  entity_id     uuid,
  before        jsonb,
  after         jsonb,
  created_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, created_at, id)    -- includes the partition key
) PARTITION BY RANGE (created_at);
-- ix_audit_entity is deliberately NOT created here: Django DEFERS the CreateModel
-- Meta index to the end of the migration, i.e. AFTER this RunPython, so creating it
-- here collides ("relation already exists" — Postgres-only; sqlite never shows it).
-- Letting Django's own deferred statement build it on the PARTITIONED parent is
-- correct: PG11+ propagates a parent index to every existing and future partition.

-- BR-AUD-002: append-only — block row mutation outright (B2 §3 trigger family).
CREATE OR REPLACE FUNCTION audit_log_forbid_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'audit_log is append-only; corrections are new rows (BR-AUD-002)';
END $$ LANGUAGE plpgsql;
CREATE TRIGGER audit_log_append_only
  BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION audit_log_forbid_mutation();
"""


def create_partitioned_parent(apps_registry, schema_editor):
    """Postgres only: swap the plain table for the partitioned parent and
    bootstrap current + 3 monthly partitions (B2 §5 / US-AUD-001 TC-1)."""
    if schema_editor.connection.vendor != "postgresql":
        return  # sqlite test DB keeps the plain table — recorded in the docstring
    from core import partitioning

    schema_editor.execute(PARTITIONED_PARENT_SQL)
    today = date.today()
    for offset in range(4):  # current month + 3 ahead
        month = partitioning.add_months(partitioning.month_start(today), offset)
        schema_editor.execute(partitioning.create_partition_sql("audit_log", month))


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        # B2 §7 ordering law: audit migrates last (tenancy → identity → audit).
        ("identity", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                (
                    "pk",
                    models.CompositePrimaryKey(
                        "tenant_id",
                        "created_at",
                        "id",
                        blank=True,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("id", models.UUIDField(default=core.dbfields.uuid7, editable=False)),
                ("tenant_id", models.UUIDField()),
                ("actor_user_id", models.UUIDField(blank=True, null=True)),
                ("action", models.TextField()),
                ("entity_type", models.TextField()),
                ("entity_id", models.UUIDField(blank=True, null=True)),
                ("before", models.JSONField(blank=True, null=True)),
                ("after", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "audit_log",
                "indexes": [
                    models.Index(
                        fields=["tenant_id", "entity_type", "entity_id", "created_at"],
                        name="ix_audit_entity",
                    )
                ],
            },
        ),
        migrations.RunPython(create_partitioned_parent, migrations.RunPython.noop),
    ]
