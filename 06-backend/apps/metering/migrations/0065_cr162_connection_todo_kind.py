"""metering 0065 — a New Connection's To-do tab holds NOTES too (`CR-162-BRC10`).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-02 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`.

PO 2026-10-02, verbatim: *"in to do also keep notes - allow user to add notes"*.

ONE COLUMN: `connection_todos.kind TEXT NOT NULL DEFAULT 'todo'` — `todo` or
`note`. Every row that exists today is a to-do (`BR-MET-114`'s outstanding
work), which is exactly what the default writes, so there is NO backfill and no
existing row changes meaning. A note is a row with `kind = 'note'`: free text,
who wrote it and when (`marked_by`, `marked_at`), never closed, never blocking.

WHY NOT `account_notes`: a single-family build has no account (Q1, the same
day), so the account's notes table cannot hold a note about it — decision log
2026-10-02, CR-162-BRC10 row, judgment (e).

ROLLBACK: `manage.py migrate metering 0064` drops the column; notes written in
the meantime would then read as to-dos, so export them first.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0064_def_met_8106_read_post_receipt"),
    ]

    operations = [
        migrations.AddField(
            model_name="connectiontodo",
            name="kind",
            field=models.TextField(default="todo"),
        ),
    ]
