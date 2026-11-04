# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-8286 (the Check's categories behind an ordered registry;
#           a Fix / Re-check re-runs only the category a fix touched)
# Plan:     04-docs/05-modules/07-billing/15-bulk-bill-run-build-plan.md B15
# Tests:    06-backend/tests/test_bbr_check_categories.py
# ───────────────────────────────────────────────────────
"""billing 0035 — which CATEGORY of the Check recorded each saved finding.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is on CLAUDE.md's
sensitive-paths list. Row in `12-governance/09-human-review-ledger.md`
(*"2026-09-30 · BULK RUN REST — registry, fixes, leave out, sign-off"*).

ONE nullable column on `bill_run_findings` and nothing else. A partial
re-check (`check_engine.check_account(categories=…)`) replaces exactly the
saved rows of the categories it re-ran and keeps the rest, so each row has to
say which category wrote it. Rows saved before this migration carry NULL, and
`check_store.check_run` re-checks such an account IN FULL rather than guess
which category a row belongs to.

No money column moves; `bill_run_findings` is a derived, rewritable table
(`check_models.py`). The lock-at-Send trigger (`0034`) is row-level and is
untouched by an added column.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0034_bbr_check_record_locked_at_send"),
    ]

    operations = [
        migrations.AddField(
            model_name="billrunfinding",
            name="check_step",
            field=models.TextField(blank=True, null=True),
        ),
    ]
