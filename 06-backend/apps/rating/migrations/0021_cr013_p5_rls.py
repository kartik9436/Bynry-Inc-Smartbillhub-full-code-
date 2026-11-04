"""rating 0021 — RLS ENABLE+FORCE on `plan_versions`, the table 0020 creates.
HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-21 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"), applying the SIGNED B2 §3
policy template verbatim from 06-backend/db/rls_rating_cr013_p5.sql. Row per
file in 12-governance/09-human-review-ledger.md; not RATIFIED without a human
sign-off.

⚠ It runs in the SAME COMMIT as 0020, which creates the table. A tenant table is
unprotected for exactly as long as its policy is a separate piece of work, and
`plan_versions.snapshot` holds the whole of a plan's pricing for every version —
one unscoped read is a complete price book, not one column.

Postgres only — live proofs run in the G5 isolation suite (NFR-10, zero
tolerance, release blocker).
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL, load_db_sql


class Migration(migrations.Migration):

    dependencies = [
        ("rating", "0020_cr013_p5_plan_versions"),
    ]

    operations = [
        PostgresOnlySQL(
            sql=load_db_sql("rls_rating_cr013_p5.sql"),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
