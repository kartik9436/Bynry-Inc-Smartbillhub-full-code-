"""portal 0019 — one card charge per portal application (DEF-PAY-10554).

Three columns on `portal_application_drafts`: the application fee's
server-made idempotency key, the count of definite declines that moves it on,
and the provider's approval, written before the request is (decision log
2026-10-23, *"one charge per application, even across a reload"*). Nullable or
defaulted (`fee_declines` 0), no backfill: no draft written before today was
ever charged under a server key. The table keeps its RLS policy from
portal/0004 — per TABLE, new columns inherit it (hard rule 1).
Rollback: reverse this migration (the three columns go). Only do so with no
unsent draft holding `fee_charge_approved`, or that approval is lost.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-10-23 under the PO ruling of 2026-08-09; row in
`12-governance/09-human-review-ledger.md`.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0018_def_bil_10531_bill_link_valid_days"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="fee_idempotency_key",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="fee_declines",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="portalapplicationdraft",
            name="fee_charge_approved",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
