"""portal 0018 — `portal_settings.bill_link_valid_days` (DEF-BIL-10531).

How long the bill email's direct PDF link stays valid, in days: a utility
SETTING seeded at 30 (decision log 2026-10-22, *"The bill email's link opens the
bill PDF directly, with no sign-in"* — our judgment, the PO named no number),
never a constant. It sits beside `agreement_link_valid_days` (`0017`) and is
built the same way. Additive with a default, so every existing utility reads 30
the moment it is applied.
Rollback: reverse this migration (the column goes; the reader then reads the
model default, which is the same 30).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-10-22 under the PO ruling of 2026-08-09; row in
`12-governance/09-human-review-ledger.md`.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0017_cr190_agreement_link_valid_days"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalsettings",
            name="bill_link_valid_days",
            field=models.IntegerField(default=30),
        ),
    ]
