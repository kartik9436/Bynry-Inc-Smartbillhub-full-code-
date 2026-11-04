# ── Trace ──────────────────────────────────────────────
# Change:   the uniform correction verbs. PO ruling 2026-09-17, verbatim, shown
#           a table of what each of the five priced objects in Plans & Rates
#           does today: *"please fix all these"*.
# Defects:  DEF-RAT-5709 — a discount cannot be edited at all, not even a draft
#           nobody has submitted; the only route out of a typo is a second
#           version through submit, approve and activate.
# Rules:    BR-RAT-1016 (the three verbs, the same for every priced object) ·
#           BR-RAT-104 (the shape it generalises — same window, a correction
#           row, the two linked) · CR-013 part 4 SHARED RULES · DEF-367 (an
#           actor on the object's OWN version row, never from `audit_log`) ·
#           CLAUDE.md hard rule 4
# Tests:    06-backend/tests/test_br_rat_1016_discount_verbs.py
# ───────────────────────────────────────────────────────
"""rating 0034 — a discount version can be CORRECTED over the same window.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-17 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human."*). Row in
12-governance/09-human-review-ledger.md.

⚠ **WHY FOUR COLUMNS AND NOT A SECOND TABLE.** `discount_versions` is already
one row per dated state with its own window, exactly as `taxes` is — so a
correction needs no new table: it is a NEW VERSION ROW that restates **the same
`effective_from`/`effective_to`** and points back at the row it corrects, while
the corrected row goes to `superseded` and stops pricing. That is `Tax.corrects`
/ `Tax.superseded_by`'s shape verbatim (`rating 0032` and the model's own
docstring), and copying it rather than inventing a second one is the whole point
of `BR-RAT-1016`: two objects answering the same question must not answer it two
ways.

⚠ **THE WINDOW IS WHAT THE COLUMNS ARE FOR.** A discount whose value CHANGES is
already a new version with NEW dates (`create_discount_version`). A CORRECTION
says the figure recorded for a period that has already run was wrong. Without
`corrects`, the two are indistinguishable in the version table — and a
correction that took its window from the payload would be a backdated change
wearing a correction's clothes, silently rewriting which bills the old figure
was ever right for.

⚠ **ADDITIVE AND NULLABLE, SO IT BACKFILLS NOTHING.** Every version written
before today has no correction chain and no corrector, and the screen says
*"—"* rather than inventing one. Same disposition `taxes.corrected_by` took, for
the reason `DEF-367` records: history is never filled in backwards.

⚠ **THE CHECK CONSTRAINT IS CHEAP AND IS THE ONE SHAPE THAT BREAKS THE CHAIN.**
A row that corrects itself makes `corrects`/`superseded_by` a cycle of length
one, and every reader that walks the chain then loops. Stated verbatim from
`ck_taxes_corrects_not_self`.

**REVERSIBLE, AND THE REVERSE COSTS DATA NOTHING ELSE HOLDS.** Dropping these
columns loses which version corrected which and who filed it. `audit_log` holds
the acts, is pruned on a retention schedule (hard rule 4's 2026-09-02
narrowing), and is not a source this product reads for a version's own history.
Reverting the CODE alone is the documented rollback
(`22-product-maintenance-process.md` §7) and leaves the columns in place,
unread and empty.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0033_cr091_discount_applies_to_services"),
        ("identity", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="discountversion",
            name="corrects",
            field=models.ForeignKey(
                blank=True,
                db_column="corrects_version_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="corrections",
                to="rating.discountversion",
            ),
        ),
        migrations.AddField(
            model_name="discountversion",
            name="superseded_by",
            field=models.ForeignKey(
                blank=True,
                db_column="superseded_by_version_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="supersedes",
                to="rating.discountversion",
            ),
        ),
        migrations.AddField(
            model_name="discountversion",
            name="correction_reason",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="discountversion",
            name="corrected_by",
            field=models.ForeignKey(
                blank=True,
                db_column="corrected_by_user_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="corrected_discount_versions",
                to="identity.user",
            ),
        ),
        migrations.AddConstraint(
            model_name="discountversion",
            constraint=models.CheckConstraint(
                condition=models.Q(("corrects__isnull", True))
                | ~models.Q(("corrects", models.F("id"))),
                name="ck_discount_versions_corrects_not_self",
            ),
        ),
    ]
