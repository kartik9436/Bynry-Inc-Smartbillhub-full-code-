# ── Trace ──────────────────────────────────────────────
# Change:   CR-087 — the tax detail's `Audit` tab, PO ruling 2026-09-10
#           (*"build"*, decision log, THE FOUR EMPTY TAB BODIES GET BUILT).
#           The ruling's own sizing for this tab: *"three of four columns are
#           stored per row; a chain read and the actor are missing — and the
#           actor must NOT come from `audit_log`."* This is the actor.
# Rules:    BR-RAT-104 (a live tax is corrected with a new dated row, never
#           edited) · DEF-367 (an actor on the object's OWN version row, the
#           `TariffVersion.submitted_by` precedent) · hard rule 4
# Tests:    06-backend/tests/test_cr087_tax_audit_and_plans.py
# ───────────────────────────────────────────────────────
"""rating 0032 — `taxes.corrected_by`, the `BY` column of the tax Audit tab.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-10 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md.

⚠ **WHY A COLUMN AND NOT AN `audit_log` QUERY, WHICH IS THE CHEAPER-LOOKING
ANSWER.** `correct_tax` already writes two `audit_log` rows naming the acting
user, so the `BY` column looks like it is already stored. It is not stored
*where it can be read*: `DefinitionDetailPage.tsx`'s §10 note and the
source-as-text guard in `DefinitionDetail.test.tsx` both refuse a filtered audit
query behind this tab, because an audit row and a version row answer different
questions — and CLAUDE.md hard rule 4's own 2026-09-02 narrowing states the
sharper reason: **`audit_log` is pruned on a retention schedule**. A rate
history whose `BY` column is an audit lookup loses its authors on the pruning
run, silently, on the one screen whose entire job is to say who changed a
statutory rate.

⚠ **ADDITIVE AND NULLABLE, SO IT BACKFILLS NOTHING.** Every correction written
before today has no actor on the row, and the screen says *"—"* for it rather
than reaching into `audit_log` to fill history in backwards. That is the drawn
behaviour (`CR-087-p036-tax-audit.md` §5, state *One version*: *"a dash where
nobody was recorded. History is never filled in backwards."*) and it is the same
disposition `TariffVersion.submitted_by` took for the same reason.

**REVERSIBLE, AND THE REVERSE COSTS DATA THAT NOTHING ELSE HOLDS.** Dropping the
column loses who filed each correction — `audit_log` may still hold it, may have
been pruned, and is not a source this product reads for that fact. Reverting the
CODE alone is the documented rollback (`22-product-maintenance-process.md` §7)
and leaves the column in place, unread.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0031_plan_service_minimum_removed"),
        ("identity", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="tax",
            name="corrected_by",
            field=models.ForeignKey(
                blank=True,
                db_column="corrected_by",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="corrected_taxes",
                to="identity.user",
            ),
        ),
    ]
