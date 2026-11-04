"""metering 0049 — a work order says WHY it exists, and which flow asked.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path; `human_owned.txt`
guards every numbered migration under `apps/*/migrations/0*.py`).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-05 under the PO ruling of
2026-08-09. ⚠ It changes NO policy and writes NO data: two ADD COLUMNs on one
existing metering table, both nullable, plus one CHECK. RLS `FORCE` on
`work_orders` (`metering/0027`) is untouched — a policy is on the TABLE, not on
its columns — and no existing row moves. Its row is in
`12-governance/09-human-review-ledger.md`.

`CR-070` wave P task P1 · `US-WRK-039` · `BR-WRK-024` · `BR-WRK-055` ·
hard rule 1 · `10-execution-plan.md` judgment 4.

WHY A METERING MIGRATION IN A WORK WAVE
---------------------------------------
`work_orders` is METERING's table today. Work owns it by the ruling of
2026-09-03 and `03-field-map.md` §4 records the choice of HOW to move it as
PENDING the blueprint's §16. So a column added to `work_orders` is a metering
migration, exactly as `metering/0044` and `metering/0045` were.

⚠ **THE PLAN ROW SAYS `work/000N` AND THAT IS NOT BUILDABLE.** Task `P1` reads
*"`work/000N` carries the two columns"*. Django resolves a migration's
`model_name` inside its own app: `workorder` is declared in
`apps/metering/connections.py`, so an `AddField` on it in `apps/work/migrations`
raises before it can run. The plan is amended in the same commit as this file,
and the correction is recorded rather than silently made.

WHAT IT ADDS
------------
* **`work_orders.source`** — `BR-WRK-024`: *"Every order carries its SOURCE —
  why it was raised."* NULLABLE, because 100% of the orders that exist at this
  migration were raised before any door stamped one, and inventing a value for
  them would put a false reason on a real record. `Work-007` draws the column as
  RAISED BY and an unstamped order renders a dash.
* **`work_orders.source_ref`** — the flow record's own number, as a clerk quotes
  it (`SR-…`, `MVO-…`, `MVI-…`, `TRF-…`, `DSC-…`). Text.
* **`ck_work_orders_source`** — NULL, or one of the fourteen tokens in
  `connections.WORK_ORDER_SOURCES`.

WHY THE CHECK IS HERE AND NOT LEFT TO PYTHON
--------------------------------------------
`DEF-WRK-3726`. Wave `G` declares this same column with ELEVEN values and lands
BEFORE the waves that write into it, so a lane building `G` to its own row would
narrow the vocabulary and the flow doors would start refusing at raise time —
three waves downstream of the cause, in a different sprint. With the CHECK
already in the database, that narrowing is a migration that fails on the way in.

WHY TWO COLUMNS AND NOT FIVE FOREIGN KEYS
-----------------------------------------
Judgment 4 of the 2026-09-04 plan, worked: one nullable FK per flow takes this
table from **4 anchor columns to 9** and `ck_work_orders_has_anchor` from a
four-way CHECK to a nine-way one, and adds **four** cross-module FKs to B2 §2's
reviewed interface set — for a link that is only ever read to print a reference.
**`ck_work_orders_has_anchor` DOES NOT MOVE.** A flow-raised job stands on the
anchor it already has: the account a move-out closes, the premises a request
resolved to.
"""

from django.db import migrations, models

from apps.metering.connections import WORK_ORDER_SOURCES


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0048_cr070_d_template_bundle"),
    ]

    operations = [
        migrations.AddField(
            model_name="workorder",
            name="source",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workorder",
            name="source_ref",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="workorder",
            constraint=models.CheckConstraint(
                condition=models.Q(source__isnull=True)
                | models.Q(source__in=WORK_ORDER_SOURCES),
                name="ck_work_orders_source",
            ),
        ),
    ]
