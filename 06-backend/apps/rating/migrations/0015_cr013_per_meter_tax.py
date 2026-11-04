"""CR-013 part 4 · the FOURTH tax computation form (BR-RAT-036 amended).

PO ruling 2026-08-21, option C, verbatim: *"Per-meter now (it's a small
change), stacking later — because that one needs care to avoid a tax that
taxes itself in a circle."*

BR-RAT-036 ratified three forms — percent, flat-per-bill, per-unit — and
CR-013 part 4 names four. The missing one is the shape a state regulatory
fee usually takes: **a rate charged per METER**. A `$1.25` per-meter fee on
a duplex with two meters is `$2.50`, and with no column it billed `$0.00`
(DEF-386).

ADDITIVE and NULLABLE: every existing tax row keeps its form and its
figures, and a NULL here simply means "this tax is not a per-meter tax".
Nothing is backfilled, because no existing row was ever a per-meter tax
pretending to be something else.

The tax-on-tax half of the same defect (DEF-381) is NOT here and is
deliberately deferred — compounding needs a cycle guard, since A taxing B
while B taxes A is a non-terminating bill.

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path, and this file
declares schema that money is priced, posted or scoped against.

HUMAN-REVIEW-PENDING — AI-authored under the PO ruling of 2026-08-09 (*"AI will
do it; we will review it later as human."*). The standing record of that deferred
review is 12-governance/09-human-review-ledger.md; no 🔒 file reaches lifecycle
RATIFIED without a human sign-off recorded there.

⚠ **BOTH MARKERS WERE MISSING UNTIL 2026-09-02 AND G7 HAD BEEN RED ON THIS FILE
EVER SINCE IT LANDED (DEF-3229).** 198 of this repository's 218 migrations carry
them and 20 did not — so the gate that enforces the 🔒 protocol could not go green
for anybody, and every lane that ran it truthfully reported the failure as
"pre-existing, not mine". Nothing about the migration itself changed here.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("rating", "0014_cr013_p1_filing_capture"),
    ]

    operations = [
        migrations.AddField(
            model_name="tax",
            name="per_meter_amount",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
        ),
    ]
