"""work 0051 — a job reading may be answered *Unable to read* (DEF-WRK-10601).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-24 under the PO ruling of
2026-08-09; the review-ledger row is written in the same commit.

TWO NULL-SAFE COLUMNS ON `work_order_readings`, NOTHING ELSE.
`unable_to_read` boolean NOT NULL DEFAULT false — every existing row reads
false, which is what it was (no row could record the answer before) — and
`unable_reason` text NULL. No row changes, no constraint, no RLS change: the
table's `ENABLE` + `FORCE` policy (`work/0013`) covers new columns as it covers
the old ones. The reverse drops both columns; nothing reads them but the
reading services and their serialisers.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("work", "0050_mq033_read_answer_findings"),
    ]

    operations = [
        migrations.AddField(
            model_name="workorderreading",
            name="unable_to_read",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="workorderreading",
            name="unable_reason",
            field=models.TextField(blank=True, null=True),
        ),
    ]
