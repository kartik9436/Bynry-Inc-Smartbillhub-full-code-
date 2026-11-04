"""metering 0075 — the seventeenth `work_orders.source` token: `disconnect`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path; `human_owned.txt` guards
every numbered migration under `apps/*/migrations/0*.py`).

HUMAN-REVIEW-PENDING — AI-authored 2026-10-05 (`CR-168-BRC10` round 8, lane
FIX-8A) under the PO ruling of 2026-08-09 (*"AI will do it; we will review it
later as human"*). Its row is in `12-governance/09-human-review-ledger.md`; not
RATIFIED without a recorded sign-off.

`DEF-CUS-9631` — the disconnect wizard's step 3 asks *Who goes: Work order* per
service point (`BR-CUS-1098`) and its confirm step said *1 work orders will be
raised*; the commit raised none. The cut visit is now raised through Work's
seventh flow door (`from_flows.FLOW_DISCONNECT`), stamped `source =
disconnect`. Why a new token and not `dunning_auto` or `reconnect` is written
beside `metering.connections.SOURCE_DISCONNECT`, where a lane choosing a source
reads.

WHY A MIGRATION AND NOT JUST A PYTHON EDIT
------------------------------------------
`0056`'s reasoning, unchanged: `0049` builds `ck_work_orders_source` from a live
import of `connections.WORK_ORDER_SOURCES`, so appending a token changes what
that migration WOULD create while every database that already ran it keeps the
sixteen-token CHECK — Python accepts the raise and PostgreSQL refuses the
INSERT. `RemoveConstraint` + `AddConstraint` under the SAME NAME makes the
database agree with the tuple.

⚠ **A WIDENING, NOT THE NARROWING `DEF-WRK-3726` FORBIDS.** Every row already
in the table satisfies the new CHECK; there is no data migration and nothing to
back-fill. RLS is untouched: a policy is on the table, and this adds no column.

**Rollback:** redeploying the previous build is enough. `0056`/`0049` import
the tuple live, so `migrate metering 0074` re-states the CHECK from whatever
tuple the deployed code holds; on `2.520.1` code that is the sixteen, and it
REFUSES while any row carries `disconnect` — re-source those rows first.
"""

from __future__ import annotations

from django.db import migrations, models

from apps.metering.connections import WORK_ORDER_SOURCES


class Migration(migrations.Migration):

    dependencies = [
        ("metering", "0074_def_wrk_9642_same_day_readings"),
    ]

    operations = [
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
