"""metering 0053 — CR-070 wave N: the minutes the labour line is priced from.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-09-06 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`.

ONE COLUMN ON `work_orders` — `minutes_on_site integer NULL`.

WHY IT IS BEING ADDED AFTER THE WAVE SHIPPED (`DEF-WRK-4124`)
------------------------------------------------------------
`apps/work/costing.py` has read this attribute since the day it was written::

    def minutes_on_site(order):
        return getattr(order, "minutes_on_site", None)

and `work_orders` never had the column. `getattr` with a default cannot fail,
so `_labour_input` returned `None` on every real order and **no report has ever
carried a labour line**. `WO-4822` reports `96.00 + 0.22 = 96.22`; the wave's
own signed figure is `138.42`, and `42.20` of it was unreachable.

Nothing said so. Every case in `tests/test_us_wrk_053_costing.py` calls
`compute()` with hand-built inputs or a `_Order` class that declares
`minutes_on_site = 52` itself — the arithmetic is pinned perfectly and the
INPUT is pinned nowhere, so the suite proves a figure the product cannot
produce.

WHY AN INTEGER COLUMN AND NOT A DERIVATION AT READ TIME
------------------------------------------------------
The same argument `0051` makes for `labour_rate_snapshot`, and `costing.py`'s
own docstring already asks for it in as many words — *"this reads an explicit
`minutes_on_site` when the order carries one and returns None otherwise, never
a guess from `created_at`, which would price a job at however long it sat in a
queue"*. **A report must be reproducible from the ORDER.** So the minutes are
stamped at close beside the rate, and the report reads what was stamped.

NULL means the job has not closed, or closed with no recorded arrival. It does
NOT mean zero: a labour line of `0.00 h` states that nobody was there, which is
a worse answer than not stating it (the posture `costing.py` already takes for
a missing rate snapshot).

⚠ NO DATA MIGRATION AND NO BACKFILL, for `0051`'s reason exactly. A job that
closed before this column existed has no recorded arrival to subtract from, and
inventing one would put a duration nobody measured into a money column.

ORDERING: depends on `metering/0052` (wave I), this app's own next number,
re-derived at push time (CLAUDE.md law 11).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0052_cr070_i_edit_and_followup"),
    ]

    operations = [
        migrations.AddField(
            model_name="workorder",
            name="minutes_on_site",
            field=models.IntegerField(null=True, blank=True),
        ),
    ]
