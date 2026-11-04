# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-014 (DEF-NOT-5632 — tenant isolation for the do-not-send
#           list)   Screens: S8 · S30
# Rules:    CLAUDE.md rule 1 (never touch a tenant table without app.tenant_id;
#           RLS FORCE is on) · B2 §3 policy template · DB-1 · BR-CUS-045 (every
#           contact column is PII) · NFR-10 (isolation — release blocker)
# ───────────────────────────────────────────────────────
"""notifications 0020 — tenant isolation for `suppressed_addresses`.

HUMAN-OWNED (RLS policies are a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-09-17 under the PO ruling of 2026-08-09. Applies the SIGNED
B2 §3 policy template from `06-backend/db/rls_notifications_suppression.sql`
verbatim and invents no new policy shape. Row in
12-governance/09-human-review-ledger.md.

Deny-by-default, not filter-by-default: with `app.tenant_id` unset the
template's `::uuid` cast of `''` raises and NO row is visible. FORCE applies the
policy to the table owner too — without it the application role (a superuser in
dev/CI) would be exempt and the guarantee would exist only in this docstring.

⚠ **THIS TABLE IS WORTH MORE TO AN ATTACKER THAN MOST IN THIS SCHEMA**, which
the .sql file states at length: every row pairs a customer's email address or
phone number with the fact that they bounced, complained or unsubscribed. And a
WRITE that landed in the wrong tenant would silently stop a different utility
sending to that address — nothing errors, nothing is lost, and a customer simply
stops receiving email. That is why the policy ships in the same commit as the
table rather than in a follow-up.

It is applied as a SEPARATE migration from 0019 rather than folded into it, for
the reason every RLS migration in this module is separate (0002, 0004, 0006,
0010, 0012): the policy is a 🔒 human-owned artifact read from a signed .sql
file, and keeping it on its own numbered step is what makes it reviewable as
one.

Postgres only — SQLite has no RLS, so the unit tier proves SHAPE (the `tenant`
column every policy depends on, and the fact that the service's own reads are
scoped through `suppression.active()`) and says so rather than implying
coverage.
"""

from pathlib import Path

from django.db import migrations

RLS_SQL = Path(__file__).resolve().parents[3] / "db" / "rls_notifications_suppression.sql"

TABLES = ("suppressed_addresses",)


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
        ("notifications", "0019_def_not_5632_suppressed_addresses"),
    ]

    operations = [
        migrations.RunPython(apply_rls, drop_rls),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-NOT-5632 (12-governance/10-defect-log.csv) · 04-docs/02-decisions/02-database-design-brief.md §3 (the policy template) · apps/notifications/migrations/0012_rls_cr009_in_app_messages.py, whose shape this repeats verbatim · db/rls_notifications_suppression.sql
# generated: 2026-09-17 by an AI lane (SendGrid/Postmark gap 4 — the do-not-send list)
# checklist: A✔ B=deferred(no frontend half) C✔ D=deferred(no API call — a migration) E=deferred(as B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: applied against a real PostgreSQL 16 and the policy read back from pg_policies; tests/test_def_not_5632_suppression.py asserts the SHAPE on sqlite (the `tenant` column and the service's own scoping) and says so rather than implying RLS coverage
# exceptions: (1) TENANT isolation only — there is no per-user dimension to this table and no second session variable is introduced. (2) `address` IS NOT ENCRYPTED and the .sql file argues why: the same value sits in clear in `outbound_messages.recipient_address` on the same deployment, and an encrypted column could not be compared against it in the dispatcher's predicate. If DB-15 ever covers a delivery address it covers both tables at once.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
