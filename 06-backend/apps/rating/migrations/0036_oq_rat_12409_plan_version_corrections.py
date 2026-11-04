# ── Trace ──────────────────────────────────────────────
# Question: OQ-RAT-12409 — CLOSED by PO ruling 2026-09-18, verbatim: *"The plan
#           correction — A, B or C - option A pls"*. Option A as it was put to
#           them: `plan_versions` gains `corrects`, `superseded_by`,
#           `correction_reason`, `corrected_by`, and the unique key becomes
#           PARTIAL (`WHERE corrects IS NULL`), so a correction is a NEW ROW
#           carrying the same `version_no`, the corrected row keeps its snapshot
#           for ever, and `rate_plans.version` never moves.
# Defect:   DEF-RAT-5710 — a typo in a published plan mints a new version, so
#           the record says the price changed when it did not.
# Rules:    BR-RAT-1016 (CONFIRMED 2026-09-17 — the three verbs are the same for
#           EVERY priced object; the plan is the last of the five) ·
#           BR-RAT-104 (a correction restates, it never re-files) ·
#           BR-RAT-037 (a CHANGE bumps the counter — untouched by this) ·
#           BR-RAT-111 (`plan_versions` is the filing record, append-only) ·
#           BR-CUS-013 (`unit_plan_assignments.plan_version` snapshots the
#           counter at assignment and outlives the plan) ·
#           CLAUDE.md hard rule 4
# Tests:    06-backend/tests/test_oq_rat_12409_plan_corrections.py
# ───────────────────────────────────────────────────────
"""rating 0036 — `corrects` · `superseded_by` · `correction_reason` ·
`corrected_by` on `plan_versions`, and `uq_plan_versions_plan_version_no` made
PARTIAL on `corrects IS NULL`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-18 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md.

⚠ **THE FOUR COLUMNS ARE `taxes`' FOUR, `discount_versions`' FOUR AND
`tariff_versions`' FOUR, VERBATIM, AND THE SAMENESS IS THE POINT.** `rating/0018`
and `rating/0032` put them on `taxes`; `rating/0034` on `discount_versions`;
`rating/0035` on `tariff_versions`. `BR-RAT-1016` rules that the three verbs are
the same for every priced object, so inventing a fourth spelling for the fourth
table is how one signed rule starts being answered four ways.

⚠ **THE ONE THING THAT IS NOT COPIED IS WHAT THE CORRECTION HOLDS FIXED.** For a
tax and for a schedule version it is the effective WINDOW, copied from the row
being corrected and never read from the payload. A plan version has no window —
`OQ-324` records that omission as deliberate — so the equivalent invariant here
is the COUNTER: `version_no` is copied from the row being corrected, and
`rate_plans.version` does not move. That is what `OQ-RAT-12409`'s option A buys
and it is why the unique key has to change.

── THE CONSTRAINT CHANGE, AND THE ARITHMETIC THAT SAYS NO DATA MOVES ─────────

`uq_plan_versions_plan_version_no` was UNIQUE `(rate_plan_id, version_no)`. It
becomes UNIQUE `(rate_plan_id, version_no) WHERE corrects_version_id IS NULL`.

**A PARTIAL UNIQUE IS STRICTLY WEAKER THAN THE ONE IT REPLACES, SO NO EXISTING
ROW CAN FAIL IT.** `corrects` is added NULL and is backfilled by nothing, so
every row on disk reads `corrects IS NULL` and is therefore INSIDE the new
predicate — the new key constrains exactly the set the old one did, over exactly
the same columns. The measurement on the seeded estate, run before and after
(`tests/test_oq_rat_12409_plan_corrections.py::test_partial_key_covers_every_
existing_row`, and the walkthrough's own before/after count):

    plan_versions rows before 0036            6
    rows with corrects IS NULL after 0036      6      (100%, none backfilled)
    distinct (rate_plan_id, version_no)        6      (still unique — 6 of 6)
    rows whose (plan, version_no) moved        0

⚠ **AND THE NAME IS DELIBERATELY REUSED RATHER THAN RETIRED.** A new name would
leave `uq_plan_versions_plan_version_no` in every docstring and register row
pointing at a constraint that no longer exists, and would make a rollback read
as an unrelated change. `RemoveConstraint` + `AddConstraint` under one name is
one DDL statement each way and the rollback is this migration reversed.

⚠ **ADDITIVE, NULLABLE, NO BACKFILL, NO RE-PRICE.** Nothing reads these columns
to price a bill: `plan_versions` is inert by `BR-RAT-111`'s own docstring —
`resolution` and `billing/gather` do not touch it — so this migration cannot
change one figure on one bill. Reversing it drops four columns and restores the
total unique, and every version goes on reading exactly as it does now.

⚠ **`PROTECT`, NOT `CASCADE`, ON BOTH SELF-FKs.** Deleting a corrected version
would take the correction's own explanation with it. `delete_plan` is the one
path in this module that removes `plan_versions` rows and it only ever reaches a
plan with zero accounts that was never billed; `PROTECT` is what keeps that true
after somebody adds a path that does not check.

⚠ **NO DATABASE CONSTRAINT FORBIDS A CORRECTION OF A CORRECTION**, deliberately
and for `rating/0035`'s recorded reason: `correct_plan_version` refuses a row
that is already superseded, BY NAME (`rating.plans.already_corrected`), which is
the same place and the same shape `correct_tax` and `correct_rate_schedule_
version` refuse it. Writing it as a check constraint needs a recursive read the
column does not have, and two half-expressions of one rule is worse than one
whole one.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0035_def_rat_5715_version_corrections"),
        # `corrected_by` points at identity's User — the same reviewed
        # cross-module FK `submitted_by` already uses on this table (B2 §2,
        # DEF-367).
        ("identity", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="planversion",
            name="corrects",
            field=models.ForeignKey(
                blank=True,
                db_column="corrects_version_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="corrections",
                to="rating.planversion",
            ),
        ),
        migrations.AddField(
            model_name="planversion",
            name="superseded_by",
            field=models.ForeignKey(
                blank=True,
                db_column="superseded_by_version_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="supersedes",
                to="rating.planversion",
            ),
        ),
        migrations.AddField(
            model_name="planversion",
            name="correction_reason",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="planversion",
            name="corrected_by",
            field=models.ForeignKey(
                blank=True,
                db_column="corrected_by",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="corrected_plan_versions",
                to="identity.user",
            ),
        ),
        # ── THE KEY BECOMES PARTIAL ──────────────────────────────────────────
        # Removed and re-added under the SAME NAME, so every citation of
        # `uq_plan_versions_plan_version_no` in the registers, the model
        # docstring and `_record_plan_version` goes on naming a constraint that
        # exists. The columns do not move; only the predicate is new, and the
        # predicate admits every row already on disk.
        migrations.RemoveConstraint(
            model_name="planversion",
            name="uq_plan_versions_plan_version_no",
        ),
        migrations.AddConstraint(
            model_name="planversion",
            constraint=models.UniqueConstraint(
                condition=models.Q(("corrects__isnull", True)),
                fields=("rate_plan", "version_no"),
                name="uq_plan_versions_plan_version_no",
            ),
        ),
        migrations.AddConstraint(
            model_name="planversion",
            constraint=models.CheckConstraint(
                condition=models.Q(("corrects__isnull", True))
                | ~models.Q(("corrects", models.F("id"))),
                name="ck_plan_versions_corrects_not_self",
            ),
        ),
    ]
