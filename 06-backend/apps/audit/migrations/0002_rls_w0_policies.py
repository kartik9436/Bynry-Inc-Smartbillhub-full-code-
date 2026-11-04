"""audit 0002 — RLS ENABLE+FORCE on the audit_log partitioned parent
(BR-AUD-007). HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-09 under PO ruling 2026-08-09
("AI will do it; we will review it later as human"), applying the SIGNED B2
§3 policy template verbatim from 06-backend/db/rls_audit_w0.sql. Row per file
in 12-governance/09-human-review-ledger.md; not RATIFIED without human
sign-off.

Postgres only — sqlite cannot exercise RLS; US-AUD-001 TC-5/TC-6 live in the
G5 isolation suite (NFR-10 zero tolerance, release blocker).
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL, load_db_sql


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0001_initial"),
    ]

    operations = [
        PostgresOnlySQL(
            sql=load_db_sql("rls_audit_w0.sql"),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
