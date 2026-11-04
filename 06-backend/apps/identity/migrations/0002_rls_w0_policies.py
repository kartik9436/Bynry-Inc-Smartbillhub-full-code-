"""identity 0002 — RLS ENABLE+FORCE on users + tenant_memberships.
HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 sensitive path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-09 under PO ruling 2026-08-09
("AI will do it; we will review it later as human"), applying the SIGNED B2
§3 policy template verbatim from 06-backend/db/rls_identity_w0.sql. `users`
is in the apply-list per B2 r16 #2 (r11 per-tenant identity voids the stale
§3 no-RLS listing). Row per file in 12-governance/09-human-review-ledger.md;
not RATIFIED without human sign-off.

Postgres only — sqlite cannot exercise RLS (G5 isolation suite owns the live
assertions, NFR-10 zero tolerance).
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL, load_db_sql


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0001_initial"),
    ]

    operations = [
        PostgresOnlySQL(
            sql=load_db_sql("rls_identity_w0.sql"),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
