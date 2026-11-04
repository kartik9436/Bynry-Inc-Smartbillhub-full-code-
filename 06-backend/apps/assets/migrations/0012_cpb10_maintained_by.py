"""assets 0012 — `asset_types.maintained_by`: whose the kit is.

CR-085 blueprint `CPB-10`. Screen 52 asks *"what is installed at my address,
whose is it, and what am I paying for it?"* and the drawing's table is
`Equipment · Reference · Installed · Whose · Monthly`. **Nothing in this product
records whose a meter, cart or backflow device is** — the blueprint says so in
its own words: *"The equipment data has no owner and no monthly charge — two of
the three facts that screen exists to answer."*

HUMAN-OWNED (CLAUDE.md 🔒 "migration ordering"). HUMAN-REVIEW-PENDING —
AI-authored under the PO ruling of 2026-08-09 (*"AI will do it; we will review
it later as human"*). Row in 12-governance/09-human-review-ledger.md.

⚠ **ON THE TYPE, NOT ON THE ASSET, AND THAT IS THE WHOLE DESIGN DECISION.**
Whose a thing is is a property of the KIND of thing in almost every utility: all
the meters are the utility's, all the private sprinkler heads are the customer's.
A column on `assets` would ask a clerk the same question 40,000 times and get it
wrong once; a column on `asset_types` is answered once per type on Settings and
inherited. `BR-AST-031` already works exactly this way for lifecycle stages —
the CLASS is the fact and the tenant owns the label — and `BR-AST-004`'s
`category` works this way for the S49 tabs.

⚠ **THE SEEDED VALUE IS DERIVED FROM `category` ONCE, HERE, AND NEVER READ LIVE.**
`behind_the_meter` is by its own name kit on the customer's side of the meter, so
it seeds `customer`; `meters` and `sub_meters` seed `utility`. That is the honest
use of a taxonomy — a STARTING value a tenant may change. Reading it live on
every render would be `DEF-CWP-3765`'s *"a shape that implies it is a rule in
disguise, and rules move"*: a utility that owns the battery it installed would be
told on the customer's own screen that it is the customer's, with no way to say
otherwise.

⚠ **NOT NULLABLE, AND THE DEFAULT IS `utility`.** A NULL would mean *nobody has
said*, and this screen's whole job is to settle the repair-bill question — the
drawing's callout reads *"Equipment marked Ours is maintained by us at no cost to
you. Anything marked Yours is your responsibility to repair."* A screen that has
to render *we do not know whose this is* beside a leaking meter is worse than one
that states the ordinary case and lets a tenant correct it. `utility` is the
ordinary case for every seeded type but one.

⚠ **THIS COLUMN CARRIES NO MONEY AND NEVER WILL.** `BR-MET-067` is explicit that
a price on an equipment or size-class lookup would be *"a second, unsigned rating
input beside the signed one"* and that size-based base charges are *"a Plans &
Rates change with a finance re-sign, never a column added here"*. The `Monthly`
column of the drawing is read from the customer's own latest BILL — the bill's
line for that service, at the rate the bill charged — and not from anything
stored here. See `portal.seams.billing_seam.per_item_monthly`.
"""

from django.db import migrations, models

#: `category` → the value seeded ONCE. Mirrored in
#: `apps.assets.equipment_reads.SEEDED_MAINTAINED_BY`, which is what the tests
#: assert against; the duplication is deliberate — a migration must not import
#: application code that a later refactor could move under it.
SEEDED = {"meters": "utility", "sub_meters": "utility", "behind_the_meter": "customer"}


def seed_from_category(apps, schema_editor):
    AssetType = apps.get_model("assets", "AssetType")
    for category, who in SEEDED.items():
        if who != "utility":
            AssetType.objects.filter(category=category).update(maintained_by=who)


def back(apps, schema_editor):
    """Nothing to undo — the column goes with the reverse of the AddField."""


class Migration(migrations.Migration):
    dependencies = [("assets", "0011_po_2026_09_07_stage_names")]

    operations = [
        migrations.AddField(
            model_name="assettype",
            name="maintained_by",
            field=models.TextField(default="utility"),
        ),
        migrations.RunPython(seed_from_category, back),
    ]
