# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-014 (EP-INT-05) — all five tables under RLS FORCE, in their
#           own migration (TC-2: with no `app.tenant_id`, zero rows on all five).
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           `app.tenant_id` set; RLS FORCE is on) · B2 §3 (the signed policy
#           template, verbatim, one per table) · 🔒 RLS policies (CLAUDE.md
#           sensitive paths — `human_owned.txt` glob `**/migrations/*rls*`)
# Tests:    06-backend/tests/test_us_int_014_pg.py (TC-2 — the probe role sees
#           nothing without context; nothing of Brazos Bend under Lone Star
#           Ridge's context; a cross-tenant write is refused by the policy)
# Impacts:  every read and write in apps/integrations — all run under BE-01's
#           tenant context or see nothing
# ───────────────────────────────────────────────────────
"""integrations 0002 — RLS ENABLE + FORCE on the five tables, and nothing else.

HUMAN-OWNED (RLS policies are a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-03 under the PO ruling of 2026-08-09;
row in 12-governance/09-human-review-ledger.md. Applies the SIGNED B2 §3
template VERBATIM through `core.rls.tenant_isolation_policy_sql`, the one
function that holds it, and invents no new policy shape.

WHY ITS OWN MIGRATION
---------------------
The brief says so — *"migration 0002 · RLS FORCE on all five, in its own
migration"* — and the reason is the same one every RLS migration in this repo
records: a policy is a statement about WHO may see a row, separate from WHAT
the row is, and a reviewer of the sensitive path reads one short file with
five identical blocks rather than hunting five `ALTER TABLE`s through four
hundred lines of column definitions.

WHAT IT GUARANTEES, MEASURED ON POSTGRESQL AND NOWHERE ELSE
-----------------------------------------------------------
Deny-by-default: with `app.tenant_id` unset or empty, `NULLIF(…, '')::uuid` is
NULL, the predicate is NULL, and NO row of any of the five is visible or
writable — `SELECT count(*)` answers 0 on every one (US-INT-014 TC-2). Under
Lone Star Ridge's context, not one of Brazos Bend's connections, credentials,
runs, references or consents is reachable. `FORCE` makes it true for the table
owner too.

The partitions of `integration_run` carry their OWN copy of the policy —
`create_partition_sql` wrote it in the same statement that created each one
(0001; DEF-027) — because PostgreSQL applies a parent's policies only when rows
are reached THROUGH the parent, and a partition queried directly consults only
its own. This migration guards the parent; the machinery guards the children.

SQLite has no RLS. The tests that prove this migration carry
`requires_postgres` and SKIP there rather than pass vacuously (hard-won law 14).
"""

from django.db import migrations

from core.rls import tenant_isolation_policy_sql

#: The five, as the brief lists them. Kept as a literal here rather than
#: imported from models.py, so this migration reads the same in a year when the
#: model module has moved on — a migration is a record of what was done.
TENANT_TABLES = (
    "integration_connection",
    "integration_credential",
    "integration_run",
    "integration_target_reference",
    "integration_consent",
)


def apply_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in TENANT_TABLES:
        schema_editor.execute(tenant_isolation_policy_sql(table))


def drop_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in TENANT_TABLES:
        schema_editor.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};")
        schema_editor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        schema_editor.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-014@62d3643 (EP-INT-05 story + BR-INT-018..053 snapshot)
# generated: 2026-09-03 by the CR-069 wave A build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=PENDING(🔒 RLS policies — ledger row 09-human-review-ledger.md, plain English with the figure: five tables, zero rows without context)
# gates: G7 (HUMAN-OWNED + HUMAN-REVIEW-PENDING + ledger row) · tests/test_us_int_014_pg.py TC-2 on PostgreSQL 16 under the non-superuser probe role · G5 isolation suite
# exceptions: SQLite has no RLS; the proof is PostgreSQL-only and never faked
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
