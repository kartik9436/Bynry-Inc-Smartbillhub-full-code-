# ── Trace ──────────────────────────────────────────────
# Change:   CR-161-BRC10 wave W7 — the utility's own fields on the customer
#           portal's new-service form. PO ruling 2026-10-02 (decision log
#           *"TENANT CUSTOM FIELDS BECOME A COMPLETE PLATFORM CAPABILITY …"*),
#           Part 2 row 16: *"Portal new-service form (applicant) · Staff
#           Request detail · Customer → clerk · Off by default per field; a
#           utility turns each one on"*.
# Rules:    CLAUDE.md hard rule 1 (`portal_application_drafts` keeps its RLS
#           policy from portal/0004 — per TABLE, so a new column inherits it;
#           this migration adds a column and no policy) · BR-TEN-046 (tenant
#           DATA, never DDL — this is the one column that holds the answers) ·
#           BR-TEN-048 (never read by a money path)
# Tests:    06-backend/tests/test_cr161_w7_portal_custom_fields.py
# Impacts:  apps/portal/models.py · apps/portal/applications.py ·
#           apps/portal/selectors.py · apps/portal/services.py
# ───────────────────────────────────────────────────────
"""portal 0014 — `portal_application_drafts.custom_data jsonb NOT NULL DEFAULT '{}'`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-02 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*); row in
12-governance/09-human-review-ledger.md, 2026-10-02, lane CF-W7.

ONE column: the applicant's answers to the utility's own questions, keyed by
record type exactly as the request's copy is (`customers/0076`):
``{"customers": {…}, "accounts": {…}, "premises": {…}}``. It is the DRAFT's,
like every other column here — an unsent form holding nothing the utility has
agreed to. At Send the answers still asked are handed to the CUSTOMERS module's
own door (`create_from_portal(custom_data=…)`), which stores them on the
service request; the draft keeps its copy, frozen with the rest of the sent
form (`BR-CWP-028`).

WHY THE DATABASE DEFAULT IS SET BY HAND
---------------------------------------
`JSONField(default=dict)` is a PYTHON default. Any insert that does not go
through the model would meet NOT NULL instead of `{}`. A constant default is a
catalogue change on PostgreSQL 11+, so no existing draft row is rewritten.

ROLLBACK
--------
Reverse drops the default and the column. An unsent draft loses the answers
typed into the utility's questions; a request already sent keeps its own copy
in `service_requests.custom_data`. No money figure depends on any of them.
"""

from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0013_def_cwp_9163_9167_mailing_and_requirement"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="custom_data",
            field=models.JSONField(blank=True, default=dict),
        ),
        PostgresOnlySQL(
            sql=(
                "ALTER TABLE portal_application_drafts "
                "ALTER COLUMN custom_data SET DEFAULT '{}'::jsonb;"
            ),
            reverse_sql=(
                "ALTER TABLE portal_application_drafts ALTER COLUMN custom_data DROP DEFAULT;"
            ),
        ),
    ]
