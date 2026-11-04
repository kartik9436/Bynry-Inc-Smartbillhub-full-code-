# ── Trace ──────────────────────────────────────────────
# Change:   DEF-CWP-9817 — Start service step 1 asks Street, Town, ZIP and the
#           unit as the Customer Portal blueprint draws them (p31), so the
#           premises match can use town and ZIP (`BR-CUS-1091`, PO 2026-09-22).
#           DEF-CWP-9818 — PO ruling 2026-10-06 (b): the applicant picks the
#           customer Category and Sub-category on step 3.
# Rules:    CLAUDE.md hard rule 8 (premises is the one address — these are
#           what a stranger TYPED, `_as_given`, never the address) · hard rule
#           1 (`portal_application_drafts` keeps its RLS policy from portal/0004
#           — per TABLE, so new columns inherit it; no policy is added here)
# Tests:    06-backend/tests/test_def_cwp_9817_9818_portal_address_and_category.py
# Impacts:  apps/portal/models.py · applications.py · selectors.py · services.py
# ───────────────────────────────────────────────────────
"""portal 0015 — four nullable text columns on `portal_application_drafts`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-06 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*); row in
12-governance/09-human-review-ledger.md, 2026-10-06, lane DEF-CWP-9817/9818.

NULLABLE, NO BACKFILL, NO DEFAULT: an unsent draft written before today typed
its whole address into one box, and splitting a town out of it is a guess — so
it carries NULL and is matched the way it always was. No money figure depends
on any of these columns.

ROLLBACK: reverse drops the four columns. An unsent draft loses the town, ZIP
and category typed into it; a request already sent keeps its own copies.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0014_cr161_w7_draft_custom_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="address_city_as_given",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="address_postal_code_as_given",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="account_type_code",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="account_subtype_code",
            field=models.TextField(blank=True, null=True),
        ),
    ]
