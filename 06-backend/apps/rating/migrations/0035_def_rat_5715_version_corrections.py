# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-RAT-5715 — BR-RAT-104's SHARED rule was built for taxes only,
#           so a typo in a live rate schedule had no correction path at all.
#           PO, beta, verbatim: *"if user make an error while creating the rate
#           schedule and they want to rectify that error using edit - how are
#           they going to do it; it is not a new rate or it is not a change in
#           rate - it is just an error handling"*.
# Rules:    BR-RAT-1016 (CONFIRMED 2026-09-17 — the three verbs are the same for
#           EVERY priced object; this is the fifth and last of them) ·
#           BR-RAT-104 (a correction restates the SAME window; the corrected row
#           keeps its rate, its dates and its trail for ever) · BR-RAT-037 (a
#           CHANGE is a new row with a NEW window — untouched by this) ·
#           BR-RAT-007 / BR-RAT-017 (a June bill re-prices on June's terms, for
#           seven years) · CLAUDE.md hard rule 4
# Tests:    06-backend/tests/test_def_rat_5715_correct_a_version.py
# ───────────────────────────────────────────────────────
"""rating 0035 — `corrects` · `superseded_by` · `correction_reason` ·
`corrected_by` on `tariff_versions`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-17 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md.

⚠ **THE FOUR COLUMNS ARE `taxes`' FOUR AND `discount_versions`' FOUR, VERBATIM,
AND THE SAMENESS IS THE POINT — IT IS WHAT `BR-RAT-1016` RULES.** `rating/0031` and `rating/0032` put exactly these on `taxes` for
exactly this rule. CR-013 part 4's words are generic — *"in-place edits of an
ACTIVE VERSION are refused outright, even for Owner/Admin, because rate history
is an audit artefact; a historic typo is fixed by a documented correction
version with a reason"* — and the 2026-08-21 build satisfied them on one of the
two objects in this module that HAVE rate history. Inventing a second shape for
the second object is how one signed rule starts being answered two ways.

⚠ **ADDITIVE AND NULLABLE, SO IT BACKFILLS NOTHING AND RE-PRICES NOTHING.**
Every version written before today reads `corrects = NULL` and
`superseded_by = NULL`, which is exactly true of them: none was a correction and
none has been corrected. **No existing row is touched, so no bill changes**, and
a rollback is this migration reversed — the columns drop and every version goes
on pricing precisely as it does now.

⚠ **`PROTECT`, NOT `CASCADE`, ON BOTH SELF-FKs.** A rate history outlives the
reason anybody had for deleting a row in it: deleting a corrected version would
take the correction's own explanation with it, and `tariff_versions` is the
table `BR-RAT-017`'s seven-year reproducibility is read out of. Nothing in this
module deletes an ACTIVATED version today; `PROTECT` is what keeps that true
after somebody adds a path that does.

⚠ **NO DATABASE CONSTRAINT FORBIDS A CORRECTION OF A CORRECTION, AND THAT IS
DELIBERATE RATHER THAN AN OMISSION.** `correct_rate_schedule_version` refuses a
row that is already superseded, by name (`rating.schedules.already_corrected`),
which is the same place and the same shape `correct_tax` refuses it. Writing it
as a check constraint would need a recursive read the column does not have, and
two half-expressions of one rule is worse than one whole one — B2 §2's EXCLUDE
on this very table is the precedent, and it was never materialised for the same
kind of reason (`models.py`'s own exceptions line says so).
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0034_br_rat_1016_discount_corrections"),
        # `corrected_by` points at identity's User, the same reviewed cross-module
        # FK `submitted_by` already uses on this table (B2 §2, DEF-367).
        ("identity", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="tariffversion",
            name="corrects",
            field=models.ForeignKey(
                blank=True,
                db_column="corrects_version_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="corrections",
                to="rating.tariffversion",
            ),
        ),
        migrations.AddField(
            model_name="tariffversion",
            name="superseded_by",
            field=models.ForeignKey(
                blank=True,
                db_column="superseded_by_version_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="supersedes",
                to="rating.tariffversion",
            ),
        ),
        migrations.AddField(
            model_name="tariffversion",
            name="correction_reason",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tariffversion",
            name="corrected_by",
            field=models.ForeignKey(
                blank=True,
                db_column="corrected_by",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="corrected_tariff_versions",
                to="identity.user",
            ),
        ),
    ]
