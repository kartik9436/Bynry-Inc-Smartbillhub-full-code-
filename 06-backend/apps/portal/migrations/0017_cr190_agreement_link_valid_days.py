"""portal 0017 — `portal_settings.agreement_link_valid_days` (CR-190-BRC10).

How long an emailed agreement link stays valid, in days: a utility SETTING
seeded at 7 (PO 2026-10-22, answer 1: *"7 Days"*), never a constant. Additive
with a default, so every existing utility reads 7 the moment it is applied.
Rollback: reverse this migration (the column goes; the reader falls back to
nothing — `agreements.link_valid_days` then refuses rather than guesses).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-10-22 under the PO ruling of 2026-08-09; row in
`12-governance/09-human-review-ledger.md`.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0016_def_cus_10250_draft_movein_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalsettings",
            name="agreement_link_valid_days",
            field=models.IntegerField(default=7),
        ),
    ]
