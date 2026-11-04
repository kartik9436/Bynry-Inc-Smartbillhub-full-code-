# ── Trace ──────────────────────────────────────────────
# Change:   CR-120-BRC06 — the rate schedule NAMES its base charge code. PO
#           ruling 2026-09-19, verbatim: *"no this is not correct ; So: plan →
#           rate schedule -> charge code → base charges - this is correct"*, and
#           on why it reverses nothing: *"we are not bindng base charges in rate
#           schedule - you were taking it default; now we are making it explicit
#           it is a same rule - change is default -> expliciate"*.
# Rules:    BR-RAT-1025 (NEW — the schedule names the code; named first, the
#           `is_base` lookup second) · BR-RAT-088 CONFIRMED-AS-AMENDED (the
#           CHARGE CODE still owns the base AMOUNT; only the ROUTE gains a step)
#           · BR-RAT-1011 / CR-078 (the named-then-inferred precedent) ·
#           CLAUDE.md hard rule 2, hard rule 4
# Tests:    06-backend/tests/test_cr120_schedule_names_base_charge_code.py
# ───────────────────────────────────────────────────────
"""rating 0037 — `tariff_versions.base_charge_code_id`, a NULLABLE FK to
`charges`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-19 under the PO ruling of
2026-08-09. Row in 12-governance/09-human-review-ledger.md.

⚠ **IT IS A POINTER AND THE COLUMN BESIDE IT IS A RETIRED FIGURE. THEY ARE
OPPOSITES AND THEY SIT NEXT TO EACH OTHER, SO READ BOTH BEFORE TOUCHING
EITHER.** `tariff_versions.base_charge` is the decimal `BR-RAT-088` RETIRED on
2026-08-20; it is NULL on every schedule this product can create, it is read at
exactly one place (R4's legacy fallback for a tenant provisioned before that
ruling), and **this migration does not repurpose it, backfill it, read it or
drop it.** The new column says WHICH CODE owns the base. The code goes on
saying what the base is WORTH.

── WHY NO BILL MOVES, AS ARITHMETIC RATHER THAN AS A PROMISE ────────────────

The column is added NULL and **nothing backfills it**. `resolution
.resolve_base_charge` asks for the named code FIRST and falls through to the
`is_base` + service lookup when there is none, so on every row that exists the
second arm answers — which is the only arm that exists today.

Measured on the shipped sample utility, before and after (the suite's
`test_forty_seven_of_forty_seven_resolve_the_same_base`):

    tariff_versions rows before 0037                        12
    rows with base_charge_code_id IS NULL after 0037        12   (100%)
    accounts ready to bill on the fixture                   47
    accounts resolving a base BEFORE                        47
    accounts resolving the SAME base, same code, same
      amount, AFTER                                         47   (47 of 47)
    bills whose total moves                                  0

⚠ **ADDITIVE, NULLABLE, NO BACKFILL, NO RE-PRICE — AND THAT IS WHAT MAKES THE
ROLLBACK ONE STATEMENT.** Reversing this migration drops one column. Every
schedule goes on resolving its base exactly as it does now, because every
schedule is already doing so.

⚠ **`PROTECT`, NOT `CASCADE`.** Deleting a charge code that a schedule has
NAMED as its base would silently take the binding with it and put that
schedule back on the inferred route — the same figure today and a different
figure the moment a second `is_base` code exists. `PROTECT` turns that into a
refusal a person reads. It is also the posture every other cross-object FK in
this module already takes, so this is the existing rule applied rather than a
new one invented.

⚠ **NO DATABASE CONSTRAINT REQUIRES THE BOUND CODE TO BE `is_base`, OR TO MATCH
THE SCHEDULE'S SERVICE, AND THAT IS DELIBERATE.** `charges.is_base`, the code's
service and its customer-class scope are all MUTABLE after the binding is
written, so a check constraint here would refuse an ordinary edit to a charge
code somewhere else in the catalogue — a refusal on the wrong screen, naming
the wrong object. The coherence gate lives at ACTIVATION instead
(`services._guard_bound_base_charge_code`), which is `DEF-2923`'s own reasoning
one column across: the refusal belongs on a settings screen with the cure in
its sentence, not on the day the money is due.

⚠ **NO INDEX.** The column is read one row at a time, by a version the chain
has already resolved; it is never a filter and never a join driver. Django
creates no index for a nullable FK it is not asked to, and adding one would be
a write cost on every version save for a query nobody issues.

⚠ **NOT TENANT-SCOPED BY A CONSTRAINT, BECAUSE NOTHING IN THIS SCHEMA IS.**
`tariff_versions` and `charges` both carry `tenant_id` and RLS FORCE is on
(CLAUDE.md hard rule 1), so a cross-tenant binding cannot be read even if it
could be written. The write path narrows by `tenant_id` explicitly as well —
`services._validate_base_charge_code` — so the refusal names the field rather
than returning an empty row.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0036_oq_rat_12409_plan_version_corrections"),
    ]

    operations = [
        migrations.AddField(
            model_name="tariffversion",
            name="base_charge_code",
            field=models.ForeignKey(
                blank=True,
                db_column="base_charge_code_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="base_for_tariff_versions",
                to="rating.charge",
            ),
        ),
    ]
