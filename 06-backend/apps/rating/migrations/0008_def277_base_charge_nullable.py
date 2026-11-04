"""rating 0008 — a base charge may now be BLANK, and a blank means "not served".

HUMAN-OWNED 🔒 · HUMAN-REVIEW-PENDING — migration ordering and money rounding are
CLAUDE.md sensitive paths, AI-authored under the PO ruling of 2026-08-09 ("AI will do it;
we will review it later as human"). Row in 12-governance/09-human-review-ledger.md; not
RATIFIED without a recorded human sign-off.

WHAT THIS COLUMN CHANGE ENDS — DEF-277
--------------------------------------
CR-013 part 1, verbatim: *"Blank base = size not served"*. Both of these columns were
NOT NULL with `default=0`, so a blank could not be stored and three different facts
arrived at one row as `0.000000`:

    "I did not type a base"          -> 0.000000
    "this size is not served"        -> 0.000000     <- CR-013 part 1's meaning
    "this size is served, and free"  -> 0.000000

Downstream nothing could tell them apart, so a bill printed **$0.00 for a size the
utility refuses to serve** — a silent wrong answer rather than a partial one. After this
migration NULL is "no base was stated" and `apps.billing.gather._base_charge_for` refuses
to bill it by name; `0` still means "stated, and free".

⚠ THIS MIGRATION CONVERTS NO DATA, AND THAT IS A PO RULING, NOT AN OMISSION
--------------------------------------------------------------------------
PO ruling 2026-08-19 (decision log, CR-013 ruling 3), verbatim: **"print $0.00"**.

Every `0.00` already stored is either *"not served"* or *"free"* and the data does not
say which. A data migration would have to guess, and either guess writes a decision the
utility never made onto a customer's bill — a refusal on a service that is genuinely
free, or a $0.00 line on a size that has no price. So the rows already in the database
keep their zero and keep billing $0.00, and the distinction begins with the next write.

The change is therefore widening only (NOT NULL -> NULL): it cannot fail on existing
data and it has no backfill to get wrong. The reverse direction is what would need care,
which is why nothing here writes one.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rating", "0007_tax_conditions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="planservice",
            name="base_charge",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
        ),
        migrations.AlterField(
            model_name="tariffversion",
            name="base_charge",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
        ),
    ]
