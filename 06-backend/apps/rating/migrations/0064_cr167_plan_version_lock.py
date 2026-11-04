"""rating 0064 — every binding row MUST name its version, and two versions of one
plan that can price never share a date (`BR-RAT-1066`; `CR-167-BRC10` §9).

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING (migration ordering, a money path). Row in
`12-governance/09-human-review-ledger.md`, 2026-10-03, CR-167-BRC10 r2 t3.

1. `plan_version_id` NOT NULL on the five binding tables (0063 filled every row).
2. **`ex_plan_versions_no_overlap`** — `EXCLUDE USING gist` over
   `(tenant_id, rate_plan_id, daterange(effective_from, effective_to + 1))` for
   every `published`, un-superseded version with a start date. It is the second
   guard behind `plan_writes` (which refuses an overlap by name,
   `rating.plans.versions_overlap`), the copy of `ex_discount_versions_no_overlap`
   (`rating/0049`, `0061`), and `DEFERRABLE INITIALLY DEFERRED` for the same
   reason: publishing v2 ENDS v1 the day before in the same transaction, and a
   correction marks the row it replaces superseded after inserting its own — the
   lock is checked at COMMIT, when both are true. Proved RED on PostgreSQL
   (`tests/test_cr167_plan_versions_pg.py`).

PostgreSQL only (`btree_gist` exists since `rating/0045`); SQLite has no
exclusion constraints and the service-layer refusal is what the default suite
exercises.

DOWN PATH: drop the constraint; the columns become NULLable again.
"""

import django.db.models.deletion
from django.db import migrations, models

from core.migrationtools import PostgresOnlySQL

FORWARD = """
ALTER TABLE plan_versions
  ADD CONSTRAINT ex_plan_versions_no_overlap
  EXCLUDE USING gist (
    tenant_id WITH =,
    rate_plan_id WITH =,
    daterange(effective_from, COALESCE(effective_to + 1, 'infinity'::date)) WITH &&
  )
  WHERE (status = 'published' AND superseded_by_version_id IS NULL AND effective_from IS NOT NULL)
  DEFERRABLE INITIALLY DEFERRED;
"""

REVERSE = "ALTER TABLE plan_versions DROP CONSTRAINT IF EXISTS ex_plan_versions_no_overlap;"


def _version_fk() -> models.ForeignKey:
    return models.ForeignKey(
        db_column="plan_version_id",
        on_delete=django.db.models.deletion.PROTECT,
        related_name="+",
        to="rating.planversion",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("rating", "0063_cr167_plan_version_backfill"),
    ]

    operations = [
        migrations.AlterField(model_name=name, name="plan_version", field=_version_fk())
        for name in (
            "planservice",
            "planrateschedule",
            "planchargerule",
            "plantaxrule",
            "plandiscountrule",
        )
    ] + [PostgresOnlySQL(FORWARD, reverse_sql=REVERSE)]
