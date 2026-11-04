# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-013 (EP-CWP-04) TC-6 — a draft started on `/pine-hill`
#           opened under `/oak-ridge` is NOT FOUND · US-CWP-014 TC-6 — the
#           consent row is scoped to the tenant, RLS FORCE on `portal_consent`.
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           `app.tenant_id` set; RLS FORCE is on) · BR-CWP-005 (the tenant is
#           resolved from the path and RLS forced BEFORE anything is read) ·
#           B2 §3 (the signed policy template, verbatim, one per table) ·
#           🔒 RLS policies (CLAUDE.md sensitive paths — `human_owned.txt`
#           glob `06-backend/**/migrations/*rls*`)
# Tests:    06-backend/tests/test_us_cwp_014_pg.py (zero rows without context
#           under the non-superuser probe role; nothing of Pine Hill under Oak
#           Ridge's context; the future-dated consent refused by the database)
# Impacts:  every read of portal_application_drafts and portal_consent —
#           under BE-01's context or nothing
# ───────────────────────────────────────────────────────
"""portal 0004 — RLS ENABLE + FORCE on the two tables wave C adds.

HUMAN-OWNED (RLS policies are a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-04 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md. Applies the SIGNED
B2 §3 template VERBATIM through `core.rls.tenant_isolation_policy_sql`, the one
function that holds it, and invents no new policy shape.

WHY IT MATTERS MORE HERE THAN ON A SETTINGS ROW
-----------------------------------------------
`portal_application_drafts` holds a stranger's name, email, mobile and — until
the moment it is used and blanked — their date of birth, typed into a form that
asks for no password. The URL token is the only thing standing between one
applicant and another **inside a tenant**; the tenant boundary is this policy's,
and it is the database's rather than the view's. `US-CWP-013` TC-6 is exactly
that test: a draft started on `/pine-hill` and opened under `/oak-ridge` is not
found, and it is not found because no row is visible, not because a view checked.

SQLite has no RLS. The tests that prove this migration carry
`requires_postgres` and SKIP there rather than pass vacuously (law 14).
"""

from django.db import migrations

from core.rls import tenant_isolation_policy_sql

#: Kept as a literal here rather than imported from models.py, so this
#: migration reads the same in a year when the model module has moved on — a
#: migration is a record of what was done.
TENANT_TABLES = ("portal_application_drafts", "portal_consent")


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
        ("portal", "0003_consent_draft_quick_service"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-013@d6d31c46 · US-CWP-014@d6d31c46 (EP-CWP-04 stories + BR-CWP-005 snapshot)
# generated: 2026-09-04 by the CR-068 wave C build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=PENDING(🔒 RLS policies — ledger row 09-human-review-ledger.md, plain English with the figure: two tables, zero rows without context)
# gates: G7 (HUMAN-OWNED + HUMAN-REVIEW-PENDING + ledger row) · tests/test_us_cwp_014_pg.py on PostgreSQL 16 under the non-superuser probe role · G5 isolation suite
# exceptions: SQLite has no RLS; the proof is PostgreSQL-only and never faked
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────
