"""work 0052 — a job reading's *Unable to read* carries an optional note
(DEF-MET-10609; decision log 2026-10-26, PO *"yes do it"*: the technician picks
one reason from the shared can't-read list, plus an optional note).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-26 under the PO ruling of
2026-08-09; the review-ledger row is written in the same commit.

ONE NULL-SAFE COLUMN ON `work_order_readings`, NOTHING ELSE.
`unable_note` text NULL — every existing row reads NULL, which is what it was
(no row could carry a note before). No row changes, no constraint, no RLS
change: the table's `ENABLE` + `FORCE` policy (`work/0013`) covers new columns
as it covers the old ones. The reverse drops the column; nothing reads it but
the reading services and their serialisers.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("work", "0051_def_wrk_10601_reading_unable"),
    ]

    operations = [
        migrations.AddField(
            model_name="workorderreading",
            name="unable_note",
            field=models.TextField(blank=True, null=True),
        ),
    ]
