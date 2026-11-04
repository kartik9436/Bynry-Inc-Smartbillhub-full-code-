# ── Trace ──────────────────────────────────────────────
# Story:   US-WRK-003 (EP-WRK-01) — the three rows `wireframes/Work-009.png`
#          draws, and the address the phase-0 demo raises a job on.
# Rules:   BR-WRK-007 (the queue is a null — this writes NO new table and adds
#          NO migration; it clears `accepted_by` on rows that already exist in
#          the shape the seeder makes them) · hard rule 1 (every write inside
#          one tenant's context)
# Tests:   this is fixture prep for
#          10-scripts/render-checks/cr070-b-fourteen-doors-and-the-queue.mjs
# ───────────────────────────────────────────────────────
"""The three rows of `Work-009`, and `77 Cedar Ct`.

WHY THIS FILE EXISTS, AND WHY IT IS NOT IN THE SEEDER
-----------------------------------------------------
`10-execution-plan.md` task B4 names the drawing's fixture by number —
`WO-4906 · Meter set · Gas · CON-26-0117` (Passed, 6 days), `WO-4903`
(Partially done), `WO-4917 · Container delivery · Trash`. **None of it is in
`load_sample_data`**, and it should not be: the seeder's own work orders are
`WO-0001`–`WO-0039` and every completed one is ALREADY ACCEPTED, which is the
correct demonstration estate for the Orders tab and leaves this queue empty.

So the walkthrough prepares what its demo script names, the way every
render-check in this folder builds its own data, and it does it HERE rather
than inside the `.mjs` because Node cannot reach Django's models and the
alternative — reaching into PostgreSQL from JavaScript with hand-written SQL —
would be a second, drifting description of the same table (hard-won law 5).

WHAT IT DOES NOT DO, DELIBERATELY
---------------------------------
**It does not raise the leak investigation and it does not close it.** Those
are demo script B's steps 4 and 5 and the walkthrough performs them through the
product's own doors — `POST /work-orders` and
`POST /work-orders/{id}/field-result` — because "a clerk can raise a job on an
address with no build" is the phase-0 LAUNCH claim, and a fixture that wrote
that row directly would prove the screen renders and prove nothing about the
claim.

It only creates the premises the demo raises that job ON, because an address is
a thing a utility already has when a leak is reported.

RUN IT
------
    export DATABASE_URL=…                       # from 10-scripts/proof-db.sh
    export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
    (cd 06-backend && python manage.py shell < ../10-scripts/render-checks/cr070-b-fixture.py)

It is IDEMPOTENT: run it twice and the second run reports the same three rows
and writes nothing new. A walkthrough that cannot be re-run is a walkthrough
nobody re-runs.
"""

import datetime as _dt

from django.db import connection as _conn
from django.utils import timezone as _tz

from apps.tenancy.models import Tenant

TENANT_CODE = "brazosbend"
BUILD = "CON-26-0117"

# The drawing's three rows: (order_no, type, service, outcome, days waiting).
ROWS = [
    ("WO-4906", "Meter set", "gas", "passed", 6),
    ("WO-4903", "Meter set", "water", "partially_done", 2),
    ("WO-4917", "Container delivery", "trash", "passed", 1),
]

# The address demo script B raises a leak investigation on. `P-00891` is the
# number `US-WRK-003`'s own test fixture uses, kept so the two agree.
LEAK_PREMISE = ("P-00891", "77 Cedar Ct")

tenant = Tenant.objects.get(subdomain=TENANT_CODE)
now = _tz.now()

with _conn.cursor() as cur:
    cur.execute("set local app.tenant_id = %s", [str(tenant.id)])

    cur.execute("select id from connections where connection_no = %s", [BUILD])
    row = cur.fetchone()
    if row is None:
        raise SystemExit(f"cr070-b-fixture: {BUILD} is not in this database — seed it first.")
    build_id = row[0]

    cur.execute("select id, premises_id from connections where id = %s", [build_id])
    _, build_premises = cur.fetchone()

    # ── the address ────────────────────────────────────────────────────────
    cur.execute("select id from premises where address_line = %s", [LEAK_PREMISE[1]])
    got = cur.fetchone()
    if got is None:
        cur.execute(
            """
            insert into premises (id, tenant_id, premise_no, address_line, status,
                                  created_at, updated_at)
            values (gen_random_uuid(), %s, %s, %s, 'active', now(), now())
            returning id
            """,
            [str(tenant.id), LEAK_PREMISE[0], LEAK_PREMISE[1]],
        )
        leak_premises = cur.fetchone()[0]
        print(f"cr070-b-fixture: created premises {LEAK_PREMISE[0]} · {LEAK_PREMISE[1]}")
    else:
        leak_premises = got[0]
        print(f"cr070-b-fixture: premises {LEAK_PREMISE[1]} already there")

    # ── the three rows ─────────────────────────────────────────────────────
    for order_no, kind, service, outcome, days in ROWS:
        completed = now - _dt.timedelta(days=days, hours=1)
        cur.execute("select code, id from services where code = %s", [service])
        svc = cur.fetchone()
        service_id = svc[1] if svc else None

        cur.execute("select id from work_orders where order_no = %s", [order_no])
        existing = cur.fetchone()
        if existing is None:
            # ⚠ `DEF-WRK-4108` / `DEF-WRK-4109`'s prevention — THROUGH THE MODEL,
            # NOT A RAW INSERT. The raw INSERT named its columns by hand and
            # broke twice as columns arrived (`dispatch_state` in wave G,
            # `held_seconds` in CR-168 P5.2), each NOT NULL with a PYTHON-side
            # default the database never sees. The model supplies every
            # default, so a column added next month cannot break this file.
            from apps.work.connection_models import WorkOrder as _WorkOrder

            _WorkOrder.objects.create(
                tenant_id=tenant.id,
                connection_id=build_id,
                premises_id=build_premises,
                service_id=service_id,
                order_no=order_no,
                type=kind,
                state="completed",
                dispatch_state="complete",
                outcome=outcome,
                mode="our_crew",
                is_gate=False,
                is_sample=True,
                scope="connection",
                completed_at=completed,
                field_data={},
            )
            print(f"cr070-b-fixture: + {order_no} · {kind} · {service} · {outcome} · {days}d")
        else:
            # Idempotent: put it back in the queue rather than making a second one.
            cur.execute(
                """
                update work_orders
                   set state = 'completed', outcome = %s, completed_at = %s,
                       accepted_at = null, accepted_by = null
                 where order_no = %s
                """,
                [outcome, completed, order_no],
            )
            print(f"cr070-b-fixture: = {order_no} put back in the queue ({days}d)")

    # ── the previous run's leak investigations ─────────────────────────────
    # The walkthrough RAISES one on `77 Cedar Ct` every time it runs, through
    # the product's own door, and there is no product door that removes one —
    # rightly: a work order is a record, not a scratch pad. So the FIXTURE
    # clears the ones its own walkthrough left, or the queue grows by one per
    # run and the footer sentence stops matching the drawing. Scoped to that
    # one address and that one type, so nothing a person raised is touched.
    cur.execute(
        """
        delete from work_orders
         where type = 'Leak investigation'
           and premises_id = %s
           and connection_id is null
        """,
        [leak_premises],
    )
    if cur.rowcount:
        print(f"cr070-b-fixture: cleared {cur.rowcount} leak investigation(s) from earlier runs")

    # ── what the queue now holds, printed so the run can be quoted ─────────
    cur.execute(
        """
        select order_no, type, connection_id is null, outcome,
               extract(day from now() - completed_at)::int
          from work_orders
         where state = 'completed' and accepted_by is null
         order by completed_at
        """
    )
    queue = cur.fetchall()
    print(f"cr070-b-fixture: the queue holds {len(queue)} order(s):")
    for order_no, kind, no_build, outcome, days in queue:
        where = "NO BUILD" if no_build else BUILD
        print(f"    {order_no:<9} {kind:<20} {where:<12} {outcome:<15} waiting {days}d")

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-003@ab786097 (EP-WRK-01) · 10-execution-plan.md wave B task B4 · wireframes/Work-009.png
# generated: 2026-09-04 by the CR-070 wave B build lane
# checklist: A=n/a(fixture prep, not product code) B=n/a C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: not a product path — the walkthrough it feeds is the check. Idempotence proved by running it twice and reading the same three rows back.
# exceptions: it writes `work_orders` rows directly, which product code may never do from outside metering — stated here because this is a FIXTURE and not a module; the leak investigation it does NOT write is raised through the real door by the walkthrough, on purpose
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
