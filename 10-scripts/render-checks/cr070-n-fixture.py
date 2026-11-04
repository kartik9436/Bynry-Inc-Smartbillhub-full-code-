#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:   US-WRK-051 (the rate stamped at close) · US-WRK-053 (the worked
#          figure, 52 minutes → 0.87 h → $42.20)
# Rules:   BR-WRK-020 · BR-WRK-051 · hard rule 1 (every write inside one
#          tenant's context)
# Tests:   fixture prep for
#          10-scripts/render-checks/cr070-n-what-it-cost.mjs
# ───────────────────────────────────────────────────────
"""**FIFTY-TWO MINUTES AGO**, which a browser cannot wait for.

⚠ **IT APPENDS AN ARRIVAL; IT DOES NOT MOVE ONE.** The first draft did an
`UPDATE` and the database refused it, correctly and by name::

    BR-WRK-025: the assignment history is append-only; row … cannot be update.
    To change who has a job, add an unassign row and an assign row.

That refusal is a guarantee worth more than this fixture, so the fixture
changed rather than the rule. `work_order_assignments` accepts INSERTs — it is
append-only, not immutable — so this appends the row that WOULD exist if the
crew had pressed *Arrived* fifty-two minutes ago, which is the state the demo
describes. It is written with raw SQL for one reason: `at` is `auto_now_add`,
so the ORM would overwrite any value handed to it with `now`.

WHY THIS FILE EXISTS
--------------------
`snapshot_labour_rate_at_close` prices labour from the LAST `arrive` row to
`completed_at`. Both of those moments are the server's own clock:
`WorkOrderAssignment.at` is `auto_now_add`, and
`POST /work-orders/{id}/field-result` takes no `completed_at` from its body —
the staff door always stamps `now`.

That is right for the product. A dispatcher presses *Arrived* at 15:15 and
*Complete* at 16:07 and the span is 52 minutes because 52 minutes went by. It
is simply not something a walkthrough can perform in a fraction of a second,
and the alternative — asserting whatever tiny span the run happens to produce —
would be a check that cannot fail on the one figure the wave exists for.

So this moves ONE row's timestamp backwards, and nothing else. It invents no
rate, no cost line and no report: the walkthrough closes the job through the
product's own door afterwards, and every figure it then asserts is one the
product computed.

⚠ **IT REFUSES TO TOUCH A JOB THAT HAS ALREADY CLOSED.** Backdating an arrival
under a finished job would move a figure on a report that is frozen, which is
the one thing `BR-WRK-050` exists to prevent.

USAGE
-----
    DATABASE_URL=… DJANGO_SETTINGS_MODULE=config.settings.local \\
      python3 10-scripts/render-checks/cr070-n-fixture.py <tenant-subdomain> \\
        <work-order-id> <minutes>
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2] / "06-backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.utils import timezone  # noqa: E402

from apps.work import connection_models as work_tables
from apps.tenancy.models import Tenant  # noqa: E402
from apps.work import models as work_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    subdomain, order_id, minutes = sys.argv[1], sys.argv[2], int(sys.argv[3])

    tenant = Tenant.objects.get(subdomain=subdomain)
    # Hard rule 1 — never a tenant table without the context set.
    with core_tenancy.tenant_context(tenant.id):
        order = work_tables.WorkOrder.objects.get(pk=order_id)
        if order.completed_at is not None:
            print(f"REFUSED: {order.order_no} has already closed — its report is frozen")
            return 3
        # `at` is `auto_now_add`, so the ORM cannot be asked for a past time,
        # and the append-only trigger refuses an UPDATE. Both of those are
        # right. So: APPEND, in raw SQL, the arrival the demo describes.
        from django.db import connection
        from core.dbfields import uuid7

        technician_id = getattr(order, "assignee_technician_id", None)
        at = timezone.now() - timezone.timedelta(minutes=minutes)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                insert into work_order_assignments
                    (id, tenant_id, work_order_id, act, technician_id, actor_id, at)
                values (%s, %s, %s, 'arrive', %s, %s, %s)
                """,
                [str(uuid7()), str(tenant.id), str(order.id), technician_id, None, at],
            )
        latest = (
            work_models.WorkOrderAssignment.objects.filter(
                work_order_id=order.id,
                act=work_models.WorkOrderAssignment.ACT_ARRIVE,
            )
            .order_by("-at")
            .first()
        )
        print(
            f"{order.order_no}: an arrival appended at {latest.at.isoformat()} "
            f"({minutes} minutes before now)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
