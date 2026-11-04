# ── Trace ──────────────────────────────────────────────
# Change:  CR-161-BRC10 wave W6 — the utility's own fields on the staff New
#          Request. PO ruling 2026-10-02 (decision log *"TENANT CUSTOM FIELDS
#          BECOME A COMPLETE PLATFORM CAPABILITY …"*), Part 1 row 15: *"Service
#          request (staff New Request) … ✅ Copied to the real records on
#          approval"*.
# Rules:   BR-TEN-046 (tenant DATA, never DDL — this is the one column that
#          holds it) · BR-TEN-048 (never read by a money path) · CLAUDE.md
#          hard rule 1 (RLS on `service_requests` is per TABLE and already
#          FORCEd — `customers/0018`; a new column inherits it)
# Tests:   06-backend/tests/test_cr161_w6_request_custom_fields.py
# ───────────────────────────────────────────────────────
"""`service_requests.custom_data jsonb NOT NULL DEFAULT '{}'`.

HUMAN-REVIEW-PENDING — AI-authored 2026-10-02 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Migration ordering is a
CLAUDE.md 🔒 path; the row is `12-governance/09-human-review-ledger.md`,
2026-10-02, lane CF-W6.

ONE column, holding the request's own copy of every answer typed on Staff New
Request, keyed by record type: ``{"customers": {…}, "accounts": {…},
"premises": {…}}``. It is never overwritten by approval — approval COPIES out of
it — so the Request detail can always show what was asked for.

WHY THE DATABASE DEFAULT IS SET BY HAND
---------------------------------------
`JSONField(default=dict)` is a PYTHON default. The portal door, the sample
seeder and any `INSERT … SELECT` would meet NOT NULL instead of `{}`. A constant
default is a catalogue change on PostgreSQL 11+, so no row is rewritten.

RLS: none needed — `service_requests` carries its policy (per TABLE).

ROLLBACK
--------
Reverse drops the default and the column. Answers typed on a request are lost
with it; answers already COPIED onto a customer, account or premises stay
there. No money figure depends on any of them.

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path (`DEF-GOV-8547`).
"""

from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0075_req03_american_english_check"),
    ]

    operations = [
        migrations.AddField(
            model_name="servicerequest",
            name="custom_data",
            field=models.JSONField(blank=True, default=dict),
        ),
        PostgresOnlySQL(
            sql="ALTER TABLE service_requests ALTER COLUMN custom_data SET DEFAULT '{}'::jsonb;",
            reverse_sql="ALTER TABLE service_requests ALTER COLUMN custom_data DROP DEFAULT;",
        ),
    ]
