"""metering 0045 — the templates table gets its NUMBER and its TYPE.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path; `human_owned.txt`
guards every numbered migration under `apps/*/migrations/0*.py`).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-04 under the PO ruling of
2026-08-09. ⚠ It changes NO policy and writes NO data: three ADD COLUMNs on
two existing metering tables, all nullable, so the RLS already forced on
`work_order_templates` and `work_orders` is untouched and no existing row
moves. Its row is in `12-governance/09-human-review-ledger.md`.

`CR-070` wave C task C1 · `US-WRK-007` · `US-WRK-012` · `BR-WRK-017` ·
`BR-WRK-021` · `03-field-map.md` §3 rows 5, 21 and 26.

WHY A METERING MIGRATION IN A WORK WAVE
---------------------------------------
`work_orders` and `work_order_templates` are METERING's tables today. Work owns
them by the ruling of 2026-09-03 and `03-field-map.md` §4 records the choice of
HOW to move them as PENDING the blueprint's §16, which this repo has never been
able to read — so the tables have not moved, and a column added to a metering
table is a metering migration. `work/0001` creates the six NEW tables; this one
adds three columns to two OLD ones.

WHAT IT ADDS, AND WHAT EACH ONE UNBLOCKS
----------------------------------------
* **`work_order_templates.template_no`** — the `service_template` number series
  (`ST-{0000}`) has been on Settings → Numbering since 2026-08-16 with nowhere
  to write. This is the place. NULLABLE, because the number is allocated ON
  PUBLISH (wave D) inside the publish transaction, so the 24 seeded starters and
  every draft carry a blank until then. Unique per tenant when present: an
  issued number is never reused and never renumbered (`BR-TEN-035`), and NULLs
  do not collide in PostgreSQL, so unpublished templates do not fight over the
  blank.
* **`work_order_templates.type_id`** and **`work_orders.type_id`** — the job-type
  catalogue (`work_order_types`, `work/0001`). Both **beside** the free-text
  `type`/`skill` columns rather than replacing them: `US-WRK-007` TC-6 is
  explicit that an existing order's typed words are never guessed at, and when
  the free text retires is §16's to say.

⚠ **A CROSS-MODULE FK, DECLARED AS ONE.** `work_orders.type_id` and
`work_order_templates.type_id` point at `work.work_order_types` — metering →
work, both new, both in B2 §2's reviewed interface set. They are POINTERS:
nothing in metering writes a `work_order_types` row and nothing in `apps/work`
writes a metering row outside the one named door (`BR-WRK-002`, enforced by
G78). `on_delete=PROTECT` on both, so a type a live order names cannot be
deleted out from under it — which is `BR-TEN-034` expressed in the schema as
well as in the handler.

**No data is backfilled and nothing is guessed.** Every existing order keeps its
free-text `type` and gets a NULL `type_id`; matching the eight seeded names to
existing text is `US-WRK-007` TC-6's *"matched only on an exact seeded name;
unmatched text stays and is reported, never guessed"* and belongs to the wave
that has a screen to report it on.

RLS: both tables already carry ENABLE + FORCE from `metering/0026`/`0027`. A
column added to a table under a policy is under the policy — the policy is on
the TABLE, not on its columns — so there is nothing to add here, and
`test_us_wrk_rls_pg.py` re-reads `pg_class` for the six NEW tables rather than
assuming any of this.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0044_cr070_a_work_order_anchors"),
        ("tenancy", "0036_def3422_drop_bell_events"),
        ("work", "0002_rls_force"),
    ]

    operations = [
        migrations.AddField(
            model_name="workorder",
            name="type_ref",
            field=models.ForeignKey(
                blank=True,
                db_column="type_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="work_orders",
                to="work.workordertype",
            ),
        ),
        migrations.AddField(
            model_name="workordertemplate",
            name="template_no",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="workordertemplate",
            name="type",
            field=models.ForeignKey(
                blank=True,
                db_column="type_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="templates",
                to="work.workordertype",
            ),
        ),
        migrations.AddConstraint(
            model_name="workordertemplate",
            constraint=models.UniqueConstraint(
                fields=("tenant", "template_no"), name="uq_work_order_templates_tenant_no"
            ),
        ),
    ]
