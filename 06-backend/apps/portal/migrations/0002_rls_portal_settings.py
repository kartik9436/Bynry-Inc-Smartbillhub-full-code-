# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-001 (EP-CWP-01) TC-5 · US-CWP-069 TC-8 · US-CWP-070 TC-7 —
#           tenant isolation on the portal's first table.
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           `app.tenant_id` set; RLS FORCE is on) · BR-CWP-005 (the tenant is
#           resolved from the path and RLS forced BEFORE anything is read) ·
#           B2 §3 (the signed policy template, verbatim, one per table) ·
#           🔒 RLS policies (CLAUDE.md sensitive paths — `human_owned.txt`
#           glob `06-backend/**/migrations/*rls*`)
# Tests:    06-backend/tests/test_us_cwp_001_pg.py (zero rows without
#           context under the non-superuser probe role; nothing of Pine Hill
#           under Oak Ridge's context; a cross-tenant write refused)
# Impacts:  every read of portal_settings — under BE-01's context or nothing
# ───────────────────────────────────────────────────────
"""portal 0002 — RLS ENABLE + FORCE on `portal_settings`, and nothing else.

HUMAN-OWNED (RLS policies are a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-03 under the PO ruling of 2026-08-09;
row in 12-governance/09-human-review-ledger.md. Applies the SIGNED B2 §3
template VERBATIM through `core.rls.tenant_isolation_policy_sql`, the one
function that holds it, and invents no new policy shape.

WHY ITS OWN MIGRATION
---------------------
A policy is a statement about WHO may see a row, separate from WHAT the row
is; a reviewer of the sensitive path reads one short file rather than hunting
an `ALTER TABLE` through the column definitions. Every module here does it
this way, and the `rls` in the file name is what puts it under the guard list.

WHAT IT GUARANTEES, MEASURED ON POSTGRESQL AND NOWHERE ELSE
-----------------------------------------------------------
Deny-by-default: with `app.tenant_id` unset or empty, `NULLIF(…, '')::uuid` is
NULL, the predicate is NULL, and no row is visible or writable — `SELECT
count(*)` answers 0. Under Oak Ridge's context, Pine Hill's row is not
reachable, so the Oak Ridge front page can carry no Pine Hill string
(US-CWP-001 TC-5). `FORCE` makes it true for the table owner too.

SQLite has no RLS. The tests that prove this migration carry
`requires_postgres` and SKIP there rather than pass vacuously (hard-won law 14).
"""

from django.db import migrations

from core.rls import tenant_isolation_policy_sql

#: Kept as a literal here rather than imported from models.py, so this
#: migration reads the same in a year when the model module has moved on — a
#: migration is a record of what was done.
TENANT_TABLES = ("portal_settings",)


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
        ("portal", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-001@87b94265 · US-CWP-069@87b94265 (EP-CWP-01/12 stories + BR-CWP-005 snapshot)
# generated: 2026-09-03 by the CR-068 wave A build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=PENDING(🔒 RLS policies — ledger row 09-human-review-ledger.md, plain English with the figure: one table, zero rows without context)
# gates: G7 (HUMAN-OWNED + HUMAN-REVIEW-PENDING + ledger row) · tests/test_us_cwp_001_pg.py on PostgreSQL 16 under the non-superuser probe role · G5 isolation suite
# exceptions: SQLite has no RLS; the proof is PostgreSQL-only and never faked
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
