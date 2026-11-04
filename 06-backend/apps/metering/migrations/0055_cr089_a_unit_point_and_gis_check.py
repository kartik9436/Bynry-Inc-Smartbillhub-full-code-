"""metering 0055 — CR-089 wave A: a unit's own point, and who checked a property.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-08 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`.

FOUR COLUMNS, TWO FACTS, AND NEITHER OF THEM IS AN ADDRESS.

──────────────────────────────────────────────────────────────────────────────
1 · `units.lat` / `units.lng` — `BR-MET-1162`, PO ruling 2026-09-08
──────────────────────────────────────────────────────────────────────────────
PO verbatim: *"youa re correct address is on premsies/property - but GIS data
for unit might change and hence we have to have parcel ID and GIs details on
Unit also"*, confirming the reading put back to them: *"The address half
stands. The coordinate half narrows: a unit may carry its own point and parcel,
and where it does, that is the truth for that unit. Where it does not, it uses
its building's."*

⚠ **THIS NARROWS `BR-MET-1161` — CLAUDE.md HARD RULE 8 — AND ONLY ITS
COORDINATE CLAUSE.** The address half is untouched: an address is stored on
`premises` and nowhere else, and this table still declares **no address
column**. What is allowed to differ is a point on a map, for the case the rule
was never written for — a cabin in a park, a pad, a wing of a campus, where the
site office is somewhere the unit is not.

**THE FALLBACK IS PART OF THE RULE.** NULL means *read the building's*, and
every screen that draws a point says which of the two it is showing
(`selectors.unit_point`).

**NOTHING IS BACKFILLED, AND THAT IS THE RULED STATE, NOT AN OMISSION.** All
1,109 units carry no point today and stay that way: a unit's own point is
opt-in by design, and the decision log of 2026-09-08 records the opposite
reading as deliberately NOT taken — *"making it required would mark all 1,109
existing units incomplete overnight for no gain"*.

`NUMERIC(9,6)` NULLABLE, the same declaration and the same WGS 84
decimal-degree frame as `premises.lat`/`lng`, so a pin read from a unit and a
pin read from its building are comparable numbers. No default: `0,0` would draw
a cabin park in the Gulf of Guinea, which is the argument `premises.lat`
already carries in its own docstring.

⚠ **NO INDEX.** The only query that filters on these is the equipment map's
`unit_premises_geo_index`, which walks the tenant's units anyway; an index on a
column NULL on 100% of rows costs writes and buys nothing at any tier in scope.

⚠ **`G85` WENT RED ON THE COMMIT THAT ADDED THESE TWO COLUMNS — that is the
guard working, and it was proved red through `run_gates`' own entry point
(`module.run()`), never by running the gate file (`DEF-GOV-3733`):**

    G85 FAIL: apps/metering/models.py::Unit declares ['lat', 'lng']. An address
    is stored on `premises` (BR-MET-1161, PO ruling 2026-09-04) …

Its allow list moves in this same commit, with the ruling quoted in the lines
directly above the entry — and **field-scoped**, because the ruling is: a unit
is a home for `lat`/`lng` and for nothing else, so `G85` still refuses a `city`
on a unit BY NAME. Putting the whole class on the list would have opened the
door the ruling deliberately kept shut. CLAUDE.md hard rule 8 is stamped in
this same commit, never before the code (hard-won law 1).

──────────────────────────────────────────────────────────────────────────────
2 · `premises.gis_checked_by` / `premises.gis_checked_at`
──────────────────────────────────────────────────────────────────────────────
PO ruling 2026-09-08 (*"We will need GIS verfieid Flag or field"*), recorded in
the decision log as: the flag *"becomes **Checked against GIS**, with who and
when"*.

`premises.gis_unchecked` already existed and answered only *has the City
confirmed this address*. **It is set on NONE of the 673 properties** — a column
that means something and has never been used — and it cannot say who looked or
when.

⚠ **WHY TWO COLUMNS AND NOT A READ OF `audit_log`.** The audit trail does hold
the row that flips the flag, and `audit_log` is **pruned on a retention
schedule** — CLAUDE.md hard rule 4 states that in terms, and whether any row is
exempt from the sweep is `OQ-1340`, still OPEN. A screen sourcing a person's
name from a table that will be swept prints *Checked · D. Whitfield, 8 Sep
2026* today and *Checked · —* afterwards, with nothing anywhere saying a fact
decayed. A fact a screen must state is a fact the row must hold.

⚠ **CR-089 §5 SAYS *"the only new columns in the whole CR are two on a unit"*
AND THAT SENTENCE IS NOW ONE WAVE OUT OF DATE.** It is a SIZING paragraph
written before anybody asked where *who and when* would live; the RULING it
sizes asks for both. The judgment is recorded in the decision log of
2026-09-08 rather than left for the next reader to reconcile, and §5 is stamped
in the same commit (r11 step W).

**BOTH NULLABLE, AND THE PAIR IS READ TOGETHER.** `gis_unchecked=false` is the
column's DEFAULT, so on all 673 rows it means *nobody has ever looked*, not
*checked*. A screen therefore reads `gis_checked_at IS NULL` as **Not checked
yet** whichever way the boolean sits, and draws **Checked** only where a person
actually pressed the control. Reading the default as an answer is the shape
hard-won law 3 is about.

`gis_checked_by` is `on_delete=PROTECT` like every other actor FK on this model
(`uploaded_by`, `disposed_by`, `fixed_by`): a person who checked a property is
part of the record and deleting them is a decision, never a cascade.

⚠ NEITHER IS AN ADDRESS-SHAPED NAME AND `G85` IS UNMOVED BY THEM. They say who
looked and when, not where anything is.

ORDERING: depends on `metering/0054` (CR-069 wave M, the flag these two
qualify), this app's own next number, re-derived at push time (CLAUDE.md law
11).

Tests: 06-backend/tests/test_cr089_a_where_a_property_is.py
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0054_cr069_m_gis_unchecked"),
        ("identity", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="unit",
            name="lat",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name="unit",
            name="lng",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name="premises",
            name="gis_checked_by",
            field=models.ForeignKey(
                blank=True,
                db_column="gis_checked_by",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="identity.user",
            ),
        ),
        migrations.AddField(
            model_name="premises",
            name="gis_checked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
