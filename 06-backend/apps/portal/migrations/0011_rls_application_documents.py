# ── Trace ──────────────────────────────────────────────
# Change:   CR-158-BRC10 — a customer attaches documents to a portal
#           new-service application (PO 2026-10-01: *"save those document to
#           server for that Utility"*).
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           `app.tenant_id` set; RLS FORCE is on) · B2 §3 (the signed policy
#           template, verbatim) · 🔒 RLS policies (`human_owned.txt` glob
#           `06-backend/**/migrations/*rls*`)
# Tests:    06-backend/tests/test_cr158_portal_application_documents_pg.py (no
#           row without context under the non-superuser probe role; nothing of
#           one utility under another's context; a write into another utility
#           refused)
# Impacts:  every read of portal_application_documents
# ───────────────────────────────────────────────────────
"""portal 0011 — RLS ENABLE + FORCE on `portal_application_documents`.

HUMAN-OWNED (RLS policies are a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-01 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md. Applies the SIGNED
B2 §3 template VERBATIM through `core.rls.tenant_isolation_policy_sql`, the one
function that holds it, and invents no new policy shape — exactly as
`portal/0004` did for the draft these rows hang off.

WHY IT MATTERS: these rows hold the BYTES of a stranger's driving licence or
tenancy agreement, typed into a form that asks for no password. The PO's words
were *"save those document to server for that Utility"* — for THAT utility,
and the database is what makes it so, not a view's filter.

SQLite has no RLS. The tests that prove this migration carry
`requires_postgres` and SKIP there rather than pass vacuously (law 14).
"""

from django.db import migrations

from core.rls import tenant_isolation_policy_sql

#: A literal, not imported from models.py — a migration is a record of what was
#: done and must read the same when the model module has moved on.
TENANT_TABLES = ("portal_application_documents",)


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
        ("portal", "0010_cr158_application_documents"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
    ]
