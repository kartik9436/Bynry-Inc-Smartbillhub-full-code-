"""metering 0002 — RLS ENABLE+FORCE on every W1 metering tenant table.
HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-09 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"), applying the SIGNED B2 §3
policy template verbatim from 06-backend/db/rls_metering_w1.sql. Row per file in
12-governance/09-human-review-ledger.md; not RATIFIED without human sign-off.

Written in the W1 verification pass: the schema lane documented these policies in
metering/models.py but ended before authoring them, so the tables shipped without
isolation. Postgres only — live proofs run in the G5 isolation suite (NFR-10,
zero tolerance, release blocker).
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL, load_db_sql


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0001_initial"),
    ]

    operations = [
        PostgresOnlySQL(
            sql=load_db_sql("rls_metering_w1.sql"),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
