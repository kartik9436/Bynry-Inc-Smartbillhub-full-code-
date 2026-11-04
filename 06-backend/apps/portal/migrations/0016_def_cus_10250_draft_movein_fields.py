# ── Trace ──────────────────────────────────────────────
# Change:   DEF-CUS-10225 / DEF-CUS-10250 — the portal's About-you step asks
#           Move-in's fields in Move-in's order (PO 2026-10-18; image
#           04-portal.png): contact by, SSN last four, the co-applicant card,
#           and Preferences (paperless, text reminders, language).
# Rules:    hard rule 1 (`portal_application_drafts` keeps its RLS policy from
#           portal/0004 — per TABLE, new columns inherit it)
# Tests:    06-backend/tests/test_def_cus_10250_portal_apply_carry_forward.py
# ───────────────────────────────────────────────────────
"""portal 0016 — eleven columns on `portal_application_drafts`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-18 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md (lane CF-2).

Nullable or defaulted (`co_applicant` False), no backfill: an unsent draft
written before today was never asked these. `ssn_last4` is encrypted
(`core.crypto`, its own AAD) and blanked at Send.

ROLLBACK: reverse drops the eleven columns; an unsent draft loses what was
typed into them, a sent request keeps its own copies.
"""


import core.crypto
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0015_def_cwp_9817_9818_address_parts_and_category"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="co_applicant",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="co_applicant_date_of_birth",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="co_applicant_email",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="co_applicant_name",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="co_applicant_phone",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="co_applicant_relationship",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="contact_by",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="paperless",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="preferred_language",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="ssn_last4",
            field=core.crypto.EncryptedTextField(
                blank=True, crypto_context="portal_application_drafts.ssn_last4", null=True
            ),
        ),
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="text_reminders",
            field=models.BooleanField(blank=True, null=True),
        ),
    ]
