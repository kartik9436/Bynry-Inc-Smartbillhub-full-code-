"""work 0055 — an End shift records when it stopped holding the status
(DEF-WRK-10615; decision log 2026-10-26, PO *"yes reset each morning, and use
web words — start"*: a technician set *off today* by End shift returns to *on
shift* at the start of their next working day).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-26 under the PO ruling of
2026-08-09; the review-ledger row is written in the same commit.

ONE NULL-SAFE COLUMN ON `work_technician_shift_ends`, NOTHING ELSE.
`settled_at` timestamptz NULL — set once, by the morning return or by the
office setting a status by hand after the End shift. Every existing row reads
NULL (*still holds*), which is what each one is: nothing has ever returned a
technician. No constraint, no RLS change: `work/0054`'s `ENABLE` + `FORCE`
covers the table and its new column. The reverse drops the column.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("work", "0054_rls_force_cr193_shifts"),
    ]

    operations = [
        migrations.AddField(
            model_name="technicianshiftend",
            name="settled_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
