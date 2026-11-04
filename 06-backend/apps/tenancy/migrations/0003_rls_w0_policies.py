"""tenancy 0003 — RLS ENABLE+FORCE on every W0 tenancy-hosted tenant table.
HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 sensitive path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-09 under PO ruling 2026-08-09
("AI will do it; we will review it later as human"), applying the SIGNED B2
§3 policy template verbatim from 06-backend/db/rls_tenancy_w0.sql (the policy
text lives there, reviewable in one place). Row per file in
12-governance/09-human-review-ledger.md; not RATIFIED without human sign-off.

Postgres only: the sqlite test DB cannot exercise RLS — skipped honestly; the
live cross-tenant probes are the G5 isolation suite's job (NFR-10 zero
tolerance, release blocker).

Depends on 0002 so the LAST W0 tenancy table (user_preferences) exists before
its policy applies — B2 §7: RLS after each table.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL, load_db_sql


class Migration(migrations.Migration):

    dependencies = [
        ("tenancy", "0002_user_preferences"),
    ]

    operations = [
        PostgresOnlySQL(
            sql=load_db_sql("rls_tenancy_w0.sql"),
            reverse_sql=migrations.RunSQL.noop,  # policies are never rolled back silently
        ),
    ]
