# ── Trace ──────────────────────────────────────────────
# Story:    CR-048 wave E task E9 — one Templates screen and one draft→publish
#           service over BOTH template stores
#           Screens: S8 (Settings → Configure → Templates)
# Rules:    BR-NOT-025 (a version any sent document points at is ARCHIVED,
#           never deleted — and archiving has to work on BOTH sides of the one
#           screen) · BR-NOT-026 (PO 2026-08-30: one screen and one service,
#           TWO STORES — no row moves) · BR-BIL-026 (append-only versions;
#           publishing affects FUTURE bills only) · BR-BIL-027 (a pinned
#           version can never be deleted) · CLAUDE.md hard rule 4 · rule 1
# Change:   CR-048 task E9
# ───────────────────────────────────────────────────────
"""billing 0024 — `bill_template_versions.archived_at`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-30 under the PO ruling of 2026-08-09.

WHAT THIS ADDS, in one sentence a System Admin would recognise: the bill-layout
version list can now say *when* a layout stopped being offered, the same way the
notification template list already does.

WHY IT IS OWED RATHER THAN NICE
────────────────────────────────────────────────────────────────────────────
`BR-NOT-025` requires that a template version any sent document points at is
ARCHIVED and never deleted, on BOTH sides of the unified Templates screen. The
notification side has carried `archived_at` since it was written. The bill side
carried an archived STATUS and no timestamp — so `templates_service.archive()`
flipped a status, wrote an audit row naming the date, and left the table itself
unable to answer *when*. One screen showing two lifecycles, one of which cannot
say when a version was retired, is the unified screen failing at its first
question.

ONE NULLABLE COLUMN, AND NOTHING ALREADY WRITTEN CHANGED
────────────────────────────────────────────────────────────────────────────
Every existing row carries NULL, including rows already in `archived` status.
That is deliberate and it is the honest value: we do not know when those were
archived, and back-filling `created_at` or `updated_at` would manufacture a date
that reads like evidence. NULL means *retired before this column existed*, and
the version list says so rather than printing a date nobody recorded.

WHAT THIS MIGRATION IS NOT
────────────────────────────────────────────────────────────────────────────
⛔ **It is not the merge.** `BR-NOT-026` (PO 2026-08-30, *"Yes, Go with option B;
I agree"*) ruled that the two template systems become ONE SCREEN and ONE SERVICE
and **not one schema**. No row moves, no table is dropped, and
`bill_template_versions` stays billing's. A later migration that folded these
rows into `notification_template_versions` would be the change that ruling
declined — `06-backend/tests/test_cr048_e9_two_stores_one_screen.py` is the guard
that goes red for it.

⛔ **It is not a delete path.** `archived_at` records a retirement; nothing here
removes a version, and `templates_service.delete_version` still refuses any
version an issued bill is pinned to (BR-BIL-027).

REVERSIBILITY
────────────────────────────────────────────────────────────────────────────
Dropping a nullable column that no other object references is safe, so this
migration reverses cleanly. Reversing it loses the archive timestamps and
nothing else — the archived STATUS is a separate column and is untouched.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0023_cr029_bill_run_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="billtemplateversion",
            name="archived_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
