# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-017 (CR-009 SET-12/SET-12D — tenant isolation for the
#           notification rule tables)   Screens: S8
# Rules:    CLAUDE.md rule 1 (never touch a tenant table without app.tenant_id;
#           RLS FORCE is on) · B2 §3 policy template · DB-1 ·
#           BR-NOT-017 (these rows are the ONE home of every notification rule,
#           so they govern what every customer of a utility receives) ·
#           NFR-10 (isolation — release blocker)
# ───────────────────────────────────────────────────────
"""notifications 0010 — tenant isolation for the CR-009 rule tables.

HUMAN-OWNED (RLS policies are a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-17 under the PO ruling of 2026-08-09. Applies the SIGNED
B2 §3 policy template from `06-backend/db/rls_notifications_cr009_rules.sql`
verbatim and invents no new policy shape. Row in
12-governance/09-human-review-ledger.md.

Deny-by-default, not filter-by-default: with `app.tenant_id` unset the
template's `::uuid` cast of `''` raises and NO row is visible. FORCE applies the
policy to the table owner too — without it the application role (a superuser in
dev/CI) would be exempt and the guarantee would exist only in this docstring.

Postgres only — SQLite has no RLS, so the unit tier proves SHAPE (the `tenant`
column every policy depends on) and says so rather than implying coverage.
"""

from pathlib import Path

from django.db import migrations

RLS_SQL = Path(__file__).resolve().parents[3] / "db" / "rls_notifications_cr009_rules.sql"

TABLES = ("notification_rules", "notification_rule_channels")


def apply_rls(apps_registry, schema_editor):
    """Apply the signed B2 §3 template, read from the .sql file verbatim."""
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
        ("notifications", "0009_cr009_notification_rules"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-017@cr009a17 (12-governance/11-change-requests.md → CR-009 in full including the three PO ruling sets of 2026-08-17 · 04-docs/02-decisions/02-database-design-brief.md §3 (the policy template) · apps/notifications/migrations/0004_rls_w3_notification_settings.py, whose shape this repeats verbatim)
# generated: 2026-08-17 by story-coder (CR-009 SET-12/SET-12D lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: the isolation tier (tests/test_cr_009_notification_rules_isolation.py) is what proves this; on SQLite it asserts SHAPE and says so rather than implying coverage
# exceptions: (1) the child table carries its OWN `tenant_id` rather than inheriting through the FK — see the .sql file's own reasoning. (2) NO partition, no extra index: `notification_rules` holds one row per tenant per event, fifteen today, and NFR-24's born-partitioned rule names five mandatory tables and not this one.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
