# ── Trace ──────────────────────────────────────────────
# Change:  CR-171-BRC10 lane RULINGS — `deposit_releases`' row-level security
#          (`payments/0047` creates the table; this file is its policy, the
#          `payments/0039` precedent).
# Rules:   CLAUDE.md hard rule 1 (never touch a tenant table without
#          `app.tenant_id` set; RLS `FORCE` is on) · B2 §3's template
#          (`core.rls.TENANT_ISOLATION_TEMPLATE`, the NULLIF form of DEF-639)
# Tests:   06-backend/tests/test_cr171_deposit_releases_rls_pg.py — PostgreSQL
#          ONLY.
# ───────────────────────────────────────────────────────
"""payments 0048 — row-level security on `deposit_releases`.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — RLS policies are named by CLAUDE.md's 🔒
list. AI-authored 2026-10-05 under the PO ruling of 2026-08-09; a row in
`12-governance/09-human-review-ledger.md` states what a reviewer is owed.

The policy text is `core.rls.tenant_isolation_policy_sql`'s — the signed B2 §3
template with `{table}` its only substitution — rather than a copy, so this file
cannot drift from the template. `FORCE` binds the table's owner too; without it
the application role, which owns the table, would bypass the policy.
"""

from django.db import migrations

from core.rls import tenant_isolation_policy_sql

TABLE = "deposit_releases"


def apply_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        # SQLite has no row-level security; the proof is the PostgreSQL-only
        # test named above, never a green SQLite run (hard-won law 7).
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
        ("payments", "0047_cr171_oq_cus_12790_deposit_releases"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
    ]
