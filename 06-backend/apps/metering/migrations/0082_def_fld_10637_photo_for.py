"""metering 0082 — a route photo added AFTER its reading was saved names that
reading (`DEF-FLD-10637`, FB-019, PO report 2026-10-28; ruling *"start FB-019
… go with recommendation"* the same day).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-28 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`.

ONE NULLABLE COLUMN (with the foreign key's own index), NO BACKFILL, NO RLS
CHANGE.

  * `field_reads.photo_for_id` — on a row of kind `photo` only: the reading
    the photograph was added to after saving. Every existing row reads NULL,
    which is exactly right: until this no declaration named its reading (the
    handset's 2.606.0 and earlier sent no `reading_key`), so there is nothing
    to back-fill and nothing could be inferred without guessing.

`field_reads` already carries `ENABLE` + `FORCE` row-level security from the
migration that created it; a new column on it is covered by the same policy.
On PostgreSQL, `ADD COLUMN … NULL` with no default is a catalogue-only change
(no table rewrite); the index is built in the same transaction.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("metering", "0081_def_met_10633_late_position"),
    ]

    operations = [
        migrations.AddField(
            model_name="fieldread",
            name="photo_for",
            field=models.ForeignKey(
                blank=True,
                db_column="photo_for_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="added_photos",
                to="metering.fieldread",
            ),
        ),
    ]
