# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-8696 (Sign off's summary read: 250–396 s at 40,008 bills;
#           a web worker is killed at 60 s, so Sign off never showed)
# Story:    US-BIL-039 (Sign off) · J73 S2
# Ruling:   OQ-843 re-ruled 2026-09-30, option C (saved, and rebuilt the moment
#           what it was built from changes)
# Tests:    06-backend/tests/test_d8696_signoff_snapshot_pg.py
# Measured: 04-docs/05-modules/07-billing/19-check-cost-measured.md §12
# ───────────────────────────────────────────────────────
"""billing 0038 — Sign off's whole-run summary can be SAVED on the run.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list. AI-authored 2026-10-01 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`
(*"2026-10-01 · SIGN OFF AT SCALE"*).

Two nullable columns on `bill_runs`: the summary `signoff.build_sign_off_summary`
answered, and the key of every row it was read from. Every existing run reads
NULL, which means *build it now* — nothing is back-filled and no figure moves.
No money column: the summary is a COPY of a read (its money is text at the
stored scale), never a record, and nothing but Sign off reads it.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0037_def_bil_8708_invoice_line_id_index"),
    ]

    operations = [
        migrations.AddField(
            model_name="billrun",
            name="sign_off_snapshot",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="billrun",
            name="sign_off_snapshot_key",
            field=models.TextField(blank=True, null=True),
        ),
    ]
