# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-071 TC-10 · US-CWP-072 TC-9 · US-CWP-073 TC-8 ·
#           US-CWP-074 TC-7 — tenant isolation on all six published-content
#           tables (each story's own `tenant isolation` case).
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           `app.tenant_id` set; RLS FORCE is on) · BR-CWP-005 (the tenant is
#           resolved from the path and RLS forced BEFORE anything is read) ·
#           B2 §3 (the signed policy template, verbatim, one per table) ·
#           🔒 RLS policies (CLAUDE.md sensitive paths — `human_owned.txt`
#           glob `06-backend/**/migrations/*rls*`)
# Tests:    06-backend/tests/test_us_cwp_071_pg.py — zero rows without context
#           under the non-superuser probe role, nothing of Pine Hill under Oak
#           Ridge's context, and `relrowsecurity` AND `relforcerowsecurity`
#           both true in `pg_class` for all six
# Impacts:  every read of the six tables — under BE-01's context or nothing
# ───────────────────────────────────────────────────────
"""tenancy 0038 — RLS ENABLE + FORCE on the six published-content tables.

HUMAN-OWNED (RLS policies are a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-04 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md. Applies the SIGNED
B2 §3 template VERBATIM through `core.rls.tenant_isolation_policy_sql`, the one
function that holds it, and invents no new policy shape.

WHY ITS OWN MIGRATION
---------------------
A policy is a statement about WHO may see a row, separate from WHAT the row is;
a reviewer of the sensitive path reads one short file rather than hunting an
`ALTER TABLE` through six tables of column definitions. Every module here does
it this way, and the `rls` in the file name is what puts it under the guard
list.

WHAT IT GUARANTEES, MEASURED ON POSTGRESQL AND NOWHERE ELSE
------------------------------------------------------------
Deny-by-default: with `app.tenant_id` unset or empty, `NULLIF(…, '')::uuid` is
NULL, the predicate is NULL, and no row is visible or writable — `SELECT
count(*)` answers 0 on every one of the six. Under Oak Ridge's context, Pine
Hill's eight answers, six tips and three centres are not reachable, which is
the `tenant isolation` case each of the four stories carries. `FORCE` makes it
true for the table owner too.

⚠ **AND THE CHILD TABLES NEED IT AS MUCH AS THE PARENTS.**
`help_answer_variants`, `help_answer_feedback` and `service_centre_hours` each
carry their own `tenant_id` and their own policy rather than inheriting one
through a foreign key: a policy on the parent does not constrain a query that
starts at the child, and *"a Wednesday opening time"* is as much one utility's
business as the centre it belongs to.

SQLite has no RLS. The tests that prove this migration carry
`requires_postgres` and SKIP there rather than pass vacuously (hard-won law 14).
"""

from django.db import migrations

from core.rls import tenant_isolation_policy_sql

#: Kept as a literal here rather than imported from the models module, so this
#: migration reads the same in a year when that module has moved on — a
#: migration is a record of what was done.
TENANT_TABLES = (
    "help_answers",
    "help_answer_variants",
    "help_answer_feedback",
    "tips",
    "service_centres",
    "service_centre_hours",
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
        ("tenancy", "0037_cr068_d_published_content"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-071..074@d6d31c46 (EP-CWP-12 stories + BR-CWP-093..096 snapshot)
# generated: 2026-09-04 by the CR-068 wave D build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=PENDING(🔒 RLS policies — ledger row 09-human-review-ledger.md, plain English with the figure: six tables, zero rows without context)
# gates: G7 (HUMAN-OWNED + HUMAN-REVIEW-PENDING + ledger row) · tests/test_us_cwp_071_pg.py on PostgreSQL 16 under the non-superuser probe role · G5 isolation suite
# exceptions: SQLite has no RLS; the proof is PostgreSQL-only and never faked
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
