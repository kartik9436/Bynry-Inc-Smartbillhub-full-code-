# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-CWP-9167 — which required document a portal applicant's file
#           is (PO ruling 2026-10-02, option A: *"a separate attach row for
#           each requirement (Photo ID, Proof of address)"*) · DEF-CWP-9163 —
#           the applicant's mailing address, if different (wireframe s17;
#           CR-085 lane-3 finding 17.3; PO 2026-10-02)
# Rules:    CLAUDE.md hard rule 1 (both tables keep their RLS policies,
#           portal/0004 and portal/0011 — this migration adds columns and a
#           CHECK and no policy) · hard rule 8 (the mailing address is the
#           named exception, *where the BILL goes*; it lands on the account as
#           `customers.addresses kind='mailing'` through the customers module,
#           never here) · BR-CWP-026
# Tests:    06-backend/tests/test_def_cwp_9163_9167_start_service.py
# Impacts:  apps/portal/models.py · apps/portal/applications.py ·
#           apps/portal/selectors.py · apps/customers/portal_seam.py
# ───────────────────────────────────────────────────────
"""portal 0013 — one nullable column on `portal_application_documents` and six on
`portal_application_drafts`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-02 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md.

**NO BACKFILL, DELIBERATELY.** A file attached before this column existed keeps
`requirement` NULL and the screen lists it under *Other documents* — the
applicant's own file is never guessed into a requirement it may not meet. Every
existing draft reads `mailing_same_as_service = true`, which is exactly what it
meant before the question was asked: the bill goes to the service address.
Reversing drops the seven columns and the CHECK; a draft loses only a mailing
address typed after this landed.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0012_draft_last_visited_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalapplicationdocument",
            name="requirement",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="mailing_same_as_service",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="mailing_line1",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="mailing_line2",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="mailing_city",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="mailing_state",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="mailing_postal_code",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="portalapplicationdocument",
            constraint=models.CheckConstraint(
                condition=models.Q(requirement__isnull=True)
                | models.Q(requirement__in=("photo_id", "proof_of_address")),
                name="ck_portal_app_docs_requirement",
            ),
        ),
    ]
