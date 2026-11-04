"""identity 0006 — `CR-145-BRC08`: the five session and lockout settings.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-28 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md.

Five columns on `security_policies`, and **nothing else**. The table already
exists (`identity/0003`) and its RLS policy is already forced (`identity/0004`)
— a policy is written against the TABLE, so five new columns are covered by it
the moment they exist and this migration adds no policy of its own.

⚠ **EVERY DEFAULT IS TODAY'S FIXED VALUE.** `services.py` carried
`ABSOLUTE_SESSION_HOURS = 12`, `TRUSTED_DEVICE_REFRESH_DAYS = 30`,
`LOCKOUT_MAX_FAILED = 5` and `LOCKOUT_MINUTES = 15` as platform constants, and
*"Keep me signed in"* was always offered. So **no utility's behaviour moves
when this runs** — a backfill of an existing row writes the number that was
already being applied to it.

⚠ **THE ONE VISIBLE CHANGE IS NOT IN THIS FILE.** Withdrawing the 240- and
480-minute inactivity choices moves real utilities to 60, so it is `0007`, on
its own, with an audit row per utility and a printed count — a behaviour change
belongs where somebody can see it run, not folded into an `AddField`.

⚠ **THE LIMITS AN ADMIN MAY CHOOSE ARE NOT DECLARED HERE.** A column default is
what a NEW row gets; the allowed ranges live once in
`apps/identity/services.SETTING_LIMITS` and are served to the front end with
the policy, so no screen keeps a second copy of them.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0005_cr070_f_field_technician"),
    ]

    operations = [
        migrations.AddField(
            model_name="securitypolicy",
            name="absolute_session_hours",
            field=models.IntegerField(default=12),
        ),
        migrations.AddField(
            model_name="securitypolicy",
            name="keep_signed_in_days",
            field=models.IntegerField(default=30),
        ),
        migrations.AddField(
            model_name="securitypolicy",
            name="keep_signed_in_offered",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="securitypolicy",
            name="lockout_max_failed",
            field=models.IntegerField(default=5),
        ),
        migrations.AddField(
            model_name="securitypolicy",
            name="lockout_minutes",
            field=models.IntegerField(default=15),
        ),
    ]
