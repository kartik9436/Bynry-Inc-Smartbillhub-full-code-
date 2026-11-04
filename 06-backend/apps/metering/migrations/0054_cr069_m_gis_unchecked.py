"""metering 0054 — CR-069 wave M: the mark `OQ-INT-1471` ruled into existence.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-06 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`.

ONE COLUMN ON `premises` — `gis_unchecked boolean NOT NULL DEFAULT false`.

WHY IT EXISTS
-------------
`OQ-INT-1471` asked whether a clerk may create a property while the City's
address service is unreachable. The PO ruled on 2026-09-04, verbatim: *"(b)
type it, marked unchecked"*. So the branch is a **build** — the property IS
created — and the whole of the ruling is the second half of the sentence.

The question said why in its own words: the unsafe option *"writes a property
against a parcel the City may have split since — and it looks identical on
screen to the good case"*. A property created from a picked candidate carries
the City's parcel key in `external_ref`; one typed past an unreachable City
carries nothing, and **without a mark those two are indistinguishable on every
screen this product has**. This column is what makes them different.

WHY A COLUMN AND NOT A KEY IN `custom_data`
--------------------------------------------
`EP-INT-12`'s wave-Q story proposes `premises.custom_data.gis_confirmed_on` for
the *confirmed* half, and that is a fact about a night's run. This is a fact
about how the ROW WAS CREATED, it has to be readable by a list query and by
every screen that draws a premises, and `custom_data` is documented on the
model as *"tenant-defined VALUES for the `custom_field` definitions tenancy
owns"* — a system flag living in the same object a tenant may define keys in is
a collision waiting for the first utility whose custom field is called
`gis_unchecked`. `DB-17` also forbids a money path reading `custom_data`, and a
future jurisdiction check may well want to ask this question.

`NOT NULL DEFAULT false`, NOT NULLABLE
---------------------------------------
Every premises already in the database was created by a path that never claimed
a City check and never bypassed one. `false` is the true answer for all of them:
the flag means *typed past an unreachable City and not yet re-checked*, and a
third state would invite a screen to guess what *unknown* meant. Django writes
the default for existing rows in the same `ALTER TABLE`; there are 44 premises
on the demo plant and a 40,000-account tenant is the ICP's top, so the rewrite
is bounded and one statement.

⚠ NO INDEX. The one query that filters on it is wave Q's night, which walks the
tenant's premises anyway; an index on a boolean whose selectivity is
approximately 1.0 costs writes and buys nothing at any tier in scope.

ORDERING: depends on `metering/0053` (CR-070 wave N), this app's own next
number, re-derived at push time (CLAUDE.md law 11).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0053_cr070_n_minutes_on_site"),
    ]

    operations = [
        migrations.AddField(
            model_name="premises",
            name="gis_unchecked",
            field=models.BooleanField(default=False),
        ),
    ]
