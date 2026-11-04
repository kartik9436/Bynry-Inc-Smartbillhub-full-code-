"""metering 0056 — the sixteenth `work_orders.source` token: `meter_read`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path; `human_owned.txt` guards
every numbered migration under `apps/*/migrations/0*.py`).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-14 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Its row is in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a recorded
sign-off.

`BR-WRK-024` (every order carries its source) · `BR-MET-023` / `BR-MET-027` /
`BR-MET-062` (a missing reading's answer is a field visit, and for a demand peak
it is the ONLY answer) · decision log 2026-09-14 (*"please build this"*, which
reversed that morning's `Q2` deferral of the Reads→Work door) · hard rule 1.

WHY A MIGRATION AND NOT JUST A PYTHON EDIT — THE WHOLE POINT
------------------------------------------------------------
`metering/0049` builds `ck_work_orders_source` from a **live import** of
`connections.WORK_ORDER_SOURCES`. So appending a token silently changes what
that migration *would* create, while **every database that already ran it keeps
the fifteen-token constraint.** The result is the one failure nobody can debug
from the symptom: **Python accepts the raise and PostgreSQL refuses the INSERT**,
inside the transaction, naming a constraint rather than a cause. `0052` recorded
that in full when it added the fifteenth; this is the same act for the sixteenth
and is deliberately written the same way.

`RemoveConstraint` + `AddConstraint` under the SAME NAME is what makes the
database agree with the tuple.

⚠ **THIS IS A WIDENING, THE OPPOSITE DIRECTION FROM THE ONE `DEF-WRK-3726`
FORBIDS, AND THE TWO LOOK ALIKE IN A DIFF.** That defect is about a wave
DECLARING a shorter list and thereby refusing writes other waves make, three
sprints downstream of the cause. **Adding a token refuses nothing that worked
yesterday**: every row already in the table still satisfies the new CHECK,
because the old vocabulary is a subset of the new one. There is no data
migration and there is nothing to back-fill.

WHY `meter_read` AND NOT AN EXISTING TOKEN
-------------------------------------------
The reasoning is written out beside the constant in
`apps/metering/connections.py`, where a lane choosing a source will actually be
reading, rather than only here. The short form: `high_usage_alert` names a flag
on a reading that ARRIVED; this door is dominated by a reading that did NOT.
`dispatcher` is refused by name in that same comment block, because a visit
filed that way **vanishes from `EP-WRK-10`'s first-time-fix report** — the one
report that measures failures.

RLS IS UNTOUCHED, AND WHY THAT IS SAFE
---------------------------------------
`work_orders` has had `ENABLE` + `FORCE` row-level security since
`metering/0027`, and **a policy is on the TABLE, not on its columns** — this
migration adds no column at all, only re-states a CHECK. `tests/test_us_wrk_
rls_pg.py` reads `pg_class` for `work_orders` already.

⚠ **AND THE CHECK ITSELF IS PROVED, NOT ASSERTED (hard-won law 1).**
`06-backend/tests/test_reads_field_work_pg.py` writes a `work_orders` row with a
source the tuple does not hold and asserts PostgreSQL refuses it by the
constraint's own name, then writes `meter_read` and asserts it is accepted —
run against a real PostgreSQL, because the default suite is in-memory SQLite
where a CHECK over a text column proves nothing about the deployed database.
"""

from __future__ import annotations

from django.db import migrations, models

from apps.metering.connections import WORK_ORDER_SOURCES


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0055_cr089_a_unit_point_and_gis_check"),
    ]

    operations = [
        # ── the sixteenth source token, in the database ────────────────────
        # Dropped and rebuilt under the SAME NAME. `0049` imports the tuple
        # live, so its own definition already reads sixteen after this commit;
        # what it cannot do is change a database that has already run it.
        migrations.RemoveConstraint(
            model_name="workorder",
            name="ck_work_orders_source",
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
