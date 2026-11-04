# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 §30, lane BOARDS — a technician's DAILY JOB LIMIT,
#           read by the Schedule board (*over their limit*) and the assign
#           advice.
# Rules:    PO answer (2) of 2026-10-05, verbatim: *"(b) Add a daily limit per
#           technician (default 6), editable on the technician's page."* ·
#           ruling 2 (2026-09-23, the match advises and never blocks) · NFR-5
#           (no hard caps) · CLAUDE.md 🔒 migration ordering
# Tests:    06-backend/tests/test_cr168_boards_lane.py
# ───────────────────────────────────────────────────────
"""work 0038 — `technicians.daily_job_limit INT NOT NULL DEFAULT 6`.

The PO's figure is the DEFAULT, so every existing technician reads 6 the moment
this lands and a supervisor changes it on the technician's page. **It is advice,
never a cap**: nothing refuses an assignment past it (ruling 2 — the match
advises and never blocks — and NFR-5). The Schedule board marks a person whose
jobs that day exceed it: limit 6, D. Ortiz holding 7, red.

A column on the existing RLS-forced `technicians` table, so no policy migration
follows.

**Down:** drops the column. Every technician's chosen limit is lost with it,
which is stated; the boards fall back to the off-day marking alone.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md 🔒
sensitive path. AI-authored 2026-10-05 under the PO ruling of 2026-08-09; row in
`12-governance/09-human-review-ledger.md`.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("work", "0037_cr168_at_risk_window")]

    operations = [
        migrations.AddField(
            model_name="technician",
            name="daily_job_limit",
            field=models.PositiveIntegerField(default=6),
        ),
    ]
