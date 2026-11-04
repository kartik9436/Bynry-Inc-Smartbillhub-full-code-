"""metering 0057 — the City's GIS keys, in columns of their own (2026-09-17).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-17 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`.

TWELVE COLUMNS, THREE FACTS, AND NOT ONE OF THEM IS AN ADDRESS.

──────────────────────────────────────────────────────────────────────────────
1 · THE KEYS — `premises.gis_parcel_id`, `units.gis_point_id`
──────────────────────────────────────────────────────────────────────────────
`BR-MET-1173`, PO rulings of 2026-09-17. The City of Ann Arbor publishes an
ArcGIS Feature Service of qualified addresses; the utility wants it as the
authoritative source of addresses. Their `PIN` is a **parcel** — one lot — and
their `FULLPIN` is an **address point**, one per unit. That is the premises/unit
split this product already has, so the two keys land on the two tables.

⚠ **WHY NOT `external_ref`, WHICH IS WHERE THE PARCEL KEY GOES TODAY.**
`CR-069` wave M writes `"external_ref": candidate.get("parcel")` in
`apps/integrations/seams/metering.py` and reads it back through
`premises_external_ref_taken`. But `premises.external_ref` is `BR-MET-403`'s
**import match key** — the id a migrating utility's previous software printed on
every work order — and `units.external_ref`'s own comment calls it *"the LEGACY
id"* (`BR-MET-404`). Both carry a case-insensitive unique-per-tenant partial
index.

**A utility that migrated already has values in those columns.** The first GIS
run would meet `uq_premises_tenant_external_ref_ci` on every one of them, and
the refusal would reach a clerk as *the parcel is already on another property*
about a property that has no parcel at all. *What our old system called this*
and *what the City calls this* are two different facts, and they take two
different columns. The wave M write is corrected in the same commit as this
migration rather than left for somebody to find.

⚠ **NO UNIQUE INDEX ON EITHER NEW KEY, AND THAT IS DELIBERATE.** *Two premises
on one parcel* is a real thing a City does — a duplex split into two properties
on one lot — and `BR-INT-073` classifies it as a QUEUED DIFFERENCE for a person
to judge. A database refusal would turn a question for a clerk into a crash in a
nightly job.

──────────────────────────────────────────────────────────────────────────────
2 · THE HISTORY — `gis_parcel_id_was` / `gis_point_id_was` / `gis_key_changed_at`
──────────────────────────────────────────────────────────────────────────────
Ruling 7 of 2026-09-17: when a key stops resolving because the City split,
merged, annexed or renumbered a parcel, we re-derive it by ADDRESS matching, and
*"one clean match applies the new key; anything else queues"*.

**A wrong key means faithfully copying the wrong parcel's data forever**,
quietly, on every run, and this pair is the only way anybody finds out why six
months later. It is on the ROW and not only in `audit_log` for the reason
`gis_checked_by` already records one table up: `audit_log` is **pruned on a
retention schedule** (hard rule 4; whether any row is exempt is `OQ-1340` and is
OPEN), and this is a fact about the row's IDENTITY rather than an action
somebody took. Both NULL until a key is actually REPLACED — storing a first key
is not a change.

──────────────────────────────────────────────────────────────────────────────
3 · WHAT THE CITY SAID AND WHEN — `gis_status`, `gis_verified`, `gis_verified_at`
──────────────────────────────────────────────────────────────────────────────
`gis_status` is the City's own `Status`, **stored as given and never filtered**.
We do not know their vocabulary and we are not the ones who decide what
*RETIRED* means to them; a row dropped because we did not recognise its status
is a row nobody can see we dropped.

`gis_verified` / `gis_verified_at` are *the last time a reconciliation run
actually found this row in the City's layer* — which is a different question
from `premises.gis_unchecked`, added by `CR-069` wave M, which is about how the
row was CREATED (a clerk typed past an unreachable City). Both are kept.

⚠ **A `preview` RUN STAMPS NEITHER** (`BR-INT-074`). A preview does everything
and writes nothing — not the keys, not the fields, not the stamp. A preview that
left a trail would be a write with a reassuring name.

──────────────────────────────────────────────────────────────────────────────
WHAT `G85` SAYS ABOUT ALL TWELVE, AND WHY THE ANSWER IS *NOTHING*
──────────────────────────────────────────────────────────────────────────────
`G85` enforces hard rule 8 by matching column NAMES against `ADDRESS_SHAPED`.
None of these twelve names is on that list, so the gate never collects them and
cannot fail on them. **That is the right answer and the dangerous kind of right
answer** — `DEF-CUS-5400` is this exact shape, where the gate reported a clean
zero over three columns it could not see.

So `BR-MET-1174`: `HOME_FIELDS` is **deliberately NOT widened**, because that
dict exists to permit `lat`/`lng` on a unit **and nothing else**, and a lane
that widens it for a parcel id has opened it for the next lane that wants a unit
to print its own street. Instead `G85` now COUNTS the `gis_*` columns it walked
past and prints the count beside its verdict, so the silence has a number on it.

**A parcel id needs no permission from an address gate, because it is not an
address.** It identifies a record in somebody else's register, and nothing in
this product derives an address from one.

──────────────────────────────────────────────────────────────────────────────
NULLABLE THROUGHOUT, NO BACKFILL, NO DEFAULT BUT `False`
──────────────────────────────────────────────────────────────────────────────
Every text column is NULL on every existing row and stays that way until a run
or a clerk's pick puts something there. NULL means *the City has not been asked
about this one*, which is the truth on all 673 existing properties and all 1,109
existing units. `gis_verified` defaults to `False` for hard-won law 3's reason:
the unsafe reading — *this address is confirmed* — must be the one somebody
types, never the one a default hands out.
"""

# Generated by Django 5.2.17 on 2026-09-17 06:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0056_reads_work_order_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="premises",
            name="gis_key_changed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="premises",
            name="gis_parcel_id",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="premises",
            name="gis_parcel_id_was",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="premises",
            name="gis_status",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="premises",
            name="gis_verified",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="premises",
            name="gis_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="unit",
            name="gis_key_changed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="unit",
            name="gis_point_id",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="unit",
            name="gis_point_id_was",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="unit",
            name="gis_status",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="unit",
            name="gis_verified",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="unit",
            name="gis_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
