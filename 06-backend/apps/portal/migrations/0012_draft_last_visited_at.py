# ── Trace ──────────────────────────────────────────────
# Change:   CR-158-BRC10 — its "not done" item, ruled by the PO on 2026-10-02:
#           an unsent portal application and its files are deleted 30 days
#           after the applicant's last visit; a return restarts the 30 days.
# Rules:    PO ruling 2026-10-02 (decision log, "AN UNSENT PORTAL APPLICATION
#           AND ITS UPLOADED FILES ARE DELETED 30 DAYS AFTER THE APPLICANT'S
#           LAST VISIT") · CLAUDE.md hard rule 1 (the table keeps its RLS
#           policy, portal/0004 — this migration adds a column and no policy)
# Tests:    06-backend/tests/test_cr158_draft_cleanup_pg.py
# Impacts:  apps/portal/models.py PortalApplicationDraft.last_visited_at ·
#           apps/portal/applications.py (stamps it) · apps/portal/draft_cleanup.py
#           (reads it)
# ───────────────────────────────────────────────────────
"""portal 0012 — ONE nullable column: `portal_application_drafts.last_visited_at`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-02 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md.

**NO BACKFILL, DELIBERATELY.** The table is under RLS `FORCE`, so an UPDATE
here would see no row without a tenant context and would report success over
nothing (law 7's *reporting zero over a scope it silently excludes*). A draft
written before this column existed keeps NULL, and the nightly job reads
`COALESCE(last_visited_at, updated_at)` — its last SAVE, which is the latest
visit anybody can prove. Reversing drops the column and loses nothing a person
typed.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0011_rls_application_documents"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="last_visited_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
