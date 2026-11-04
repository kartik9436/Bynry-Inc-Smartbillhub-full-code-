# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 5, lane SRV-4 — P5.3's read (the at-risk list)
#           needs the tenant's warning window (§7.3, `GET /work/at-risk`).
# Rules:    PO answer (1) of 2026-10-04 (every job has a promise) · CLAUDE.md
#           🔒 migration ordering
# Tests:    06-backend/tests/test_cr168_srv4_promise.py
# ───────────────────────────────────────────────────────
"""work 0037 — `work_settings.at_risk_window_hours INT NULL`.

The at-risk list (`GET /work/at-risk`) names open jobs whose promise falls
within the tenant's WARNING WINDOW. No such setting existed, so SRV-1 served
`sla.at_risk` as *past its target* and said the window was SRV-4's. NULL is
the seeded value and keeps exactly that reading: no figure is invented for a
tenant that has not chosen one. Not a tenant TABLE (a column on the existing
RLS-forced `work_settings`), so no policy migration follows.

**Down:** drops the column. A tenant's chosen window is lost with it, which is
stated; nothing else reads it.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md 🔒
sensitive path. AI-authored 2026-10-04 under the PO ruling of 2026-08-09; row in
`12-governance/09-human-review-ledger.md`.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("work", "0036_rls_force_photo_links")]

    operations = [
        migrations.AddField(
            model_name="worksettings",
            name="at_risk_window_hours",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
