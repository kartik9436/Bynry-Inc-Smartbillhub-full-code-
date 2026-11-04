# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-5814 — `discount_versions`' CHECK constraint still lists the
#          FIVE scopes `rating/0009` baked in, while `discounts.DISCOUNT_SCOPES`
#          has carried SEVEN since `CR-091-BRC01`. The wizard offers all seven,
#          so *All services* and *Specific services* were a guaranteed HTTP 500.
# Rules:   `CR-091-BRC01` / PO ruling 2026-09-10 (*"Add a new choice. - one or
#          more services from drop down; All services or sepecific services;
#          this is correct"*) · CLAUDE.md hard-won law 14 (the suite's database
#          cannot express the production guarantee) · CLAUDE.md 🔒 migration
#          ordering
# Tests:   06-backend/tests/test_def_rat_5814_every_scope_saves_pg.py
# ───────────────────────────────────────────────────────
"""rating 0040 — let the table store the two scopes the product already offers.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-19 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md.

⚠ **THIS IS A CONTENT DIFFERENCE AND IT WAS TWICE READ AS A SPELLING ONE.**
`makemigrations --check` has been red on this constraint since 10 September.
`DEF-RAT-5094` called it *"the signature Django emits when a CheckConstraint's
Python expression no longer serialises to what its migration recorded"*, and
`DEF-GOV-5506` called it *"a permanent false positive"* whose honest fix was
*"one migration that re-creates the constraint under the new spelling"*. Both
rows are corrected in the register by the same commit as this file. **One
`psql` query separates the two readings**, and it was never run:

    CHECK ((applies_to = ANY (ARRAY['whole_bill','one_service','usage_only',
                                    'base_only','named_codes'])))

against `discounts.DISCOUNT_SCOPES`, which carries those five **plus
`all_services` and `specific_services`**.

⚠ **WHAT IT COST A CLERK, MEASURED.** Of the seven choices DIS-02 step 2 draws
in its *Applies to* select, **two could never be saved**: the row reached
PostgreSQL, the check refused it, and the screen rendered *"Something went
wrong on our side."* The pair was the PO's own ask of 2026-09-10 and had been
dead every day since.

⚠ **NOTHING IN THE DEFAULT SUITE COULD SEE IT** (hard-won law 14).
`config/settings/test.py` hardcodes in-memory SQLite, and SQLite does not
enforce this constraint — so every existing discount test passes green on both
the broken and the fixed schema. The proof therefore lives in a PostgreSQL-only
test that **walks `DISCOUNT_SCOPES` itself** and commits one discount per
scope, so the EIGHTH scope cannot ship without its migration either.

⚠ **THE SEVEN VALUES ARE WRITTEN OUT AS A LITERAL, AND THAT IS THE WHOLE
POINT — DO NOT "TIDY" IT INTO `from apps.rating.discounts import
DISCOUNT_SCOPES`.** The autodetector EXECUTES this file to build its picture of
the recorded schema. An imported tuple therefore evaluates to whatever the model
says *today*, the two can never differ, and `makemigrations --check` goes green
for ever — including on the next scope that ships with no migration. That is
hard-won law 7's *structurally incapable of failing*: it would silence the only
check that has ever noticed this drift, on the very defect it failed to stop.
A frozen literal is what makes the next divergence visible.

⚠ **NO DATA MOVES AND NO ROW IS REWRITTEN.** The old check is a strict subset
of the new one, so every stored row already satisfies it; this only widens what
may be written next. `reverse` puts the five-value check back and will refuse
only rows written AFTER this migration on one of the two new scopes.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0039_def_rat_5799_class_backfill_under_rls"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="discountversion",
            name="ck_discount_versions_scope",
        ),
        migrations.AddConstraint(
            model_name="discountversion",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "applies_to__in",
                        (
                            "whole_bill",
                            "one_service",
                            "usage_only",
                            "base_only",
                            "named_codes",
                            # ── `CR-091-BRC01`, the pair that could not be saved
                            "all_services",
                            "specific_services",
                        ),
                    )
                ),
                name="ck_discount_versions_scope",
            ),
        ),
    ]
