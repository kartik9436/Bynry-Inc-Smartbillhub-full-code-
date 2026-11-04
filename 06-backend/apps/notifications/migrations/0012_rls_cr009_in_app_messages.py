# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-018 (CR-009 — tenant isolation for the in-app message store)
#           Screens: shell-chrome · S8
# Rules:    CLAUDE.md rule 1 (never touch a tenant table without app.tenant_id;
#           RLS FORCE is on) · B2 §3 policy template · DB-1 · BR-NOT-019 (in-app
#           is a real channel and every row here is a rendered message body) ·
#           NFR-10 (isolation — release blocker)
# ───────────────────────────────────────────────────────
"""notifications 0012 — tenant isolation for `in_app_messages`.

HUMAN-OWNED (RLS policies are a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-17 under the PO ruling of 2026-08-09. Applies the SIGNED
B2 §3 policy template from `06-backend/db/rls_notifications_in_app.sql`
verbatim and invents no new policy shape. Row in
12-governance/09-human-review-ledger.md.

Deny-by-default, not filter-by-default: with `app.tenant_id` unset the
template's `::uuid` cast of `''` raises and NO row is visible. FORCE applies the
policy to the table owner too — without it the application role (a superuser in
dev/CI) would be exempt and the guarantee would exist only in this docstring.

Postgres only — SQLite has no RLS, so the unit tier proves SHAPE (the `tenant`
column every policy depends on, and the fact that the service's own reads are
scoped) and says so rather than implying coverage.
"""

from pathlib import Path

from django.db import migrations

RLS_SQL = Path(__file__).resolve().parents[3] / "db" / "rls_notifications_in_app.sql"

TABLES = ("in_app_messages",)


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
        ("notifications", "0011_cr009_in_app_messages"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-018@cr009inapp (12-governance/11-change-requests.md → CR-009 fourth ruling set · 04-docs/02-decisions/02-database-design-brief.md §3 (the policy template) · apps/notifications/migrations/0010_rls_cr009_notification_rules.py, whose shape this repeats verbatim)
# generated: 2026-08-17 by story-coder (CR-009 in-app channel lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: tests/test_cr_009_in_app_isolation.py is what proves this; on SQLite it asserts SHAPE and the per-user scoping of every read, and says so rather than implying RLS coverage
# exceptions: (1) TENANT isolation only — WHOSE inbox is enforced in `apps/notifications/in_app.py`, which has no callable that accepts a user id from a request. The reasoning against a second `app.user_id` session variable is in the .sql file. (2) No index or partition is added here: 0011 carries both indexes this table has.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
