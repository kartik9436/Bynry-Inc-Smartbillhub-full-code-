"""metering 0081 — a LATE position, kept as its own fact (`DEF-MET-10633`,
FB-003, PO ruling 2026-10-27).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-27 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`.

ONE NULLABLE COLUMN, ONE PARTIAL UNIQUE INDEX, NO BACKFILL, NO RLS CHANGE.

  * `field_reads.position_for_id` — on a row of kind `position` only: the
    reading or route photo whose late position it is. Every existing row reads
    NULL, which is exactly right: no late position was ever received before
    this (the kind was refused `unknown_kind`).
  * `uq_field_reads_one_late_position` — `(tenant_id, position_for_id)` WHERE
    `position_for_id IS NOT NULL`: the FIRST fix within 5 minutes is the one
    kept (*"the first fix within 5 minutes of saving is sent automatically as
    a SEPARATE fact"*). A second one trips it inside the item's savepoint and
    is answered as a duplicate (hard-won law 14 — proved on PostgreSQL in
    `tests/test_def_met_10633_late_position_pg.py`).

`field_reads` already carries `ENABLE` + `FORCE` row-level security from the
migration that created it; a new column on it is covered by the same policy.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metering", "0080_mq033_read_formats"),
    ]

    operations = [
        migrations.AddField(
            model_name="fieldread",
            name="position_for",
            field=models.ForeignKey(
                blank=True,
                db_column="position_for_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="late_positions",
                to="metering.fieldread",
            ),
        ),
        migrations.AddConstraint(
            model_name="fieldread",
            constraint=models.UniqueConstraint(
                condition=models.Q(position_for__isnull=False),
                fields=("tenant", "position_for"),
                name="uq_field_reads_one_late_position",
            ),
        ),
    ]
