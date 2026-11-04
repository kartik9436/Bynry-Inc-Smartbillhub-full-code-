# BR-RAT-082 (PO ruling 2026-08-20) — the regulator signs OUTSIDE the product and
# we capture the sign-off as DATA. Four nullable columns, no gate, no default:
# `regulator_ref` already held the filing reference, and these are the authority,
# the submitted date, the approved date and the approver's name.
#
# Every column is NULL-able with no default because every existing version was
# written before the fields existed and none of them has an answer. NULL here is
# "not recorded", which is a true statement about every row this migration
# touches; a default would have invented an answer for all of them.
"""rating 0014 - CR-013 P1: what a tariff version was FILED as - the filing authority, `filed_on`, `regulator_approved_on` and who approved it.

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
        ("rating", "0013_cr013_amount_four_places"),
    ]

    operations = [
        migrations.AddField(
            model_name="tariffversion",
            name="filing_authority",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tariffversion",
            name="filed_on",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tariffversion",
            name="regulator_approved_on",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tariffversion",
            name="regulator_approver",
            field=models.TextField(blank=True, null=True),
        ),
    ]
