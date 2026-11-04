"""assets 0002 — RLS ENABLE+FORCE on every W1 assets tenant table.
HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-09 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"), applying the SIGNED B2 §3
policy template verbatim from 06-backend/db/rls_assets_w1.sql. Row per file in
12-governance/09-human-review-ledger.md; not RATIFIED without human sign-off.

Written in the W1 verification pass: the schema lane documented these policies in
assets/models.py but ended before authoring them, so the tables shipped without
isolation. Postgres only — live proofs run in the G5 isolation suite (NFR-10,
zero tolerance, release blocker).

AMENDED 2026-08-09 (BR-AST-043 gap lane): rls_assets_w1.sql now also carries the
meter_types + read_methods policies, appended below a SECTION MARKER. Those two
tables are created by migration 0003 and DO NOT EXIST at this point in history,
so this migration applies only the text ABOVE the marker. Slicing (rather than
splitting the file) keeps every assets policy in one reviewable place; the
`.index()` call fails loudly if anyone deletes the marker.
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL, load_db_sql

SECTION_MARKER = "-- >>> ASSETS-0003 <<<"
_POLICY_FILE = load_db_sql("rls_assets_w1.sql")
# ValueError here = the marker was removed: fix the SQL file, never the slice.
W1_POLICIES = _POLICY_FILE[: _POLICY_FILE.index(SECTION_MARKER)]


class Migration(migrations.Migration):

    dependencies = [
        ("assets", "0001_initial"),
    ]

    operations = [
        PostgresOnlySQL(
            sql=W1_POLICIES,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
