# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-8223 (Not in this run has no Leave for next cycle)
# Rule:     BR-BIL-1054 (PO 2026-09-30) · BR-BIL-1039 (the next run opens at
#           the last billed read) · BR-BIL-034 (hold ≠ forget)
# Plan:     04-docs/05-modules/07-billing/15-bulk-bill-run-build-plan.md B20 · A9
# Tests:    06-backend/tests/test_bbr_not_in_run.py
# ───────────────────────────────────────────────────────
"""billing 0036 — a Pending-billing row can be LEFT FOR THE NEXT CYCLE.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list. Row in `12-governance/09-human-review-ledger.md`
(*"2026-09-30 · BULK RUN REST"*).

Two nullable columns on `bill_run_exclusions`: WHEN a clerk chose *Leave for
next cycle* and WHO. The row stays OPEN — it is still owed — and is closed by
the first LATER run that bills the account (`pending.resolve_for_run`),
because that run bills from the last billed read (BR-BIL-1039), so the held
usage is on it and nothing is lost or counted twice. A row with no mark is a
catch-up row exactly as before; every existing row reads NULL.

`next_cycle_by_id` is a plain uuid, not a foreign key: the reviewed
cross-module FK set (B2 §2) is not widened for a marker. No money column.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0035_bbr_finding_check_step"),
    ]

    operations = [
        migrations.AddField(
            model_name="billrunexclusion",
            name="next_cycle_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="billrunexclusion",
            name="next_cycle_by_id",
            field=models.UUIDField(blank=True, null=True),
        ),
    ]
