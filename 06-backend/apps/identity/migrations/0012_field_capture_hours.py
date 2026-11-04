"""identity 0012 — the field app's capture life becomes the utility's setting.

PO 2026-10-21, decision log *"Field app: the PO corrects four of the ten
answers"* item 2, verbatim: *"this should come from settings"* — how long a
phone may keep capturing (and renewing its sign-in) without a password is held
per utility, seeded at **7 days** (`BR-WRK-060`'s signed figure) and editable
by a System Admin on Settings → Security.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path; credentials are 🔒
identity). HUMAN-REVIEW-PENDING — AI-authored 2026-10-21 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*). The
review-ledger row is owed by the coordinator; not RATIFIED without a sign-off.

ONE column on `security_policies` and nothing else — the table's RLS policy is
written against the TABLE (`identity/0004`), so it covers the column the moment
it exists. **The default is 168 hours, which is the 7 days every handset was
already given** (`WORK_CAPTURE_TOKEN_MAX_AGE_S`'s default), so no utility's
behaviour moves when this runs. Stored in HOURS because the design's own figure
(36 hours, `OQ-FLD-12798`) is not a whole number of days. The choices an admin
may pick are `apps/identity/services.SETTING_LIMITS`, never this file.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0011_cr187_native_tokens_activation"),
    ]

    operations = [
        migrations.AddField(
            model_name="securitypolicy",
            name="field_capture_hours",
            field=models.IntegerField(default=168),
        ),
    ]
