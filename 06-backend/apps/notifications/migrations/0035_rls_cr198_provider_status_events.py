"""notifications 0035 — tenant isolation for `provider_status_events` (`CR-198-BRC10`).

HUMAN-OWNED (RLS policies are a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-10-29 under the PO ruling of 2026-08-09. Applies the SIGNED
B2 §3 policy template from `06-backend/db/rls_notifications_provider_status.sql`
verbatim and invents no new policy shape. Row in
12-governance/09-human-review-ledger.md.

A row here moves a utility's queue row to `delivered` or `failed`; landing it
under the wrong tenant would move another utility's message. So the policy
ships in the same change as the table. Postgres only — SQLite has no RLS.
"""

from pathlib import Path

from django.db import migrations

RLS_SQL = Path(__file__).resolve().parents[3] / "db" / "rls_notifications_provider_status.sql"

TABLES = ("provider_status_events",)


def apply_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(RLS_SQL.read_text(encoding="utf-8"))


def drop_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in TABLES:
        schema_editor.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};")
        schema_editor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        schema_editor.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0034_cr198_provider_status_events"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
    ]
