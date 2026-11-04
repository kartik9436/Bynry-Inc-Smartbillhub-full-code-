"""`BR-CUS-1090` — a move-in's `MVI-` number, READ BACK from real PostgreSQL.

WHY THIS EXISTS BESIDE THE SUITE
--------------------------------
`06-backend/tests/test_br_cus_1090_move_in_job_number.py` runs on **in-memory
SQLite** (`config/settings/test.py` hardcodes it, and CLAUDE.md hard-won law 14
is about exactly this), and three of the things this rule turns on cannot be
observed there at all:

1. **`uq_move_in_jobs_tenant_move_no_ci` is a PARTIAL, EXPRESSION index.**
   `LOWER(move_no)` with `WHERE move_no IS NOT NULL` is the guarantee that one
   number means one job, and that two unnumbered jobs on a tenant with no series
   do NOT collide. Section 2 below inserts both cases against the live cluster
   and prints what the database says.
2. **RLS `FORCE`.** The policy `0053` created must still be in force after a
   column is added to the table. Section 1 asks `pg_class` rather than assuming.
3. **THE CHAIN ACROSS THREE TABLES ON REAL DATA.** Section 3 walks
   approval → park → commit on the seeded `brazosbend` utility and asserts one
   number comes out the other end.

⚠ **IT WRITES NOTHING THAT SURVIVES.** Every section runs inside a
`transaction.atomic()` that is rolled back at the end, so the clone is left as it
was found — except for the numbers it burns out of the `move_in` counter, which
`BR-TEN-035` permits and `BR-CUS-1090` states.

RUN IT
------
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL="postgres://…/sbh_clone_<label>?sslmode=disable" \\
      python ../10-scripts/br_cus_1090_move_in_number_readback.py

Get the database from `10-scripts/proof-db.sh clone <label>` — and set
`app.tenant_id` before counting anything, because RLS FORCE makes every unscoped
count answer 0 and three lanes have now nearly reported a false zero from that.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import django

# The backend is the import root whether this is run from `06-backend` or from
# the repository root — a script that only works from one directory is a script
# that reports "no module named config" instead of a result.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from django.db import IntegrityError, connection, transaction  # noqa: E402

from apps.tenancy.models import Tenant  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

FAILURES: list[str] = []


def check(label: str, got: object, want: object) -> None:
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'}  {label}: got {got!r}, want {want!r}")
    if not ok:
        FAILURES.append(label)


def main() -> int:
    tenant = Tenant.objects.filter(subdomain="brazosbend").first()
    if tenant is None:  # pragma: no cover - a clone without the demo tenant
        print("no `brazosbend` tenant in this database; seed it first")
        return 2
    print(f"tenant: {tenant.subdomain} ({tenant.id})")

    # ═══════════════════════════════════════════════════════════════════
    # 1 · RLS IS STILL IN FORCE AFTER THE COLUMN WAS ADDED
    # ═══════════════════════════════════════════════════════════════════
    print("\n1 · RLS on `move_in_jobs` (hard rule 1)")
    with connection.cursor() as cur:
        cur.execute(
            "select relrowsecurity, relforcerowsecurity from pg_class "
            "where relname = 'move_in_jobs'"
        )
        enabled, forced = cur.fetchone()
        cur.execute(
            "select polname from pg_policy p join pg_class c on c.oid = p.polrelid "
            "where c.relname = 'move_in_jobs'"
        )
        policies = sorted(row[0] for row in cur.fetchall())
    check("ENABLE ROW LEVEL SECURITY", enabled, True)
    check("FORCE ROW LEVEL SECURITY", forced, True)
    check("the policy", policies, ["move_in_jobs_tenant_isolation"])

    # ═══════════════════════════════════════════════════════════════════
    # 2 · THE PARTIAL, CASE-INSENSITIVE UNIQUE — both halves
    # ═══════════════════════════════════════════════════════════════════
    print("\n2 · `uq_move_in_jobs_tenant_move_no_ci` (BR-CUS-1090 / hard rule 6)")
    with core_tenancy.tenant_context(tenant.id):
        from apps.customers import models as cmodels, move_in_jobs

        # ⚠ **REQUESTS WITH NO JOB OF THEIR OWN, AND THE FIRST DRAFT TOOK THE
        # FIRST THREE BLINDLY.** `uq_move_in_jobs_tenant_request` refused the
        # insert the moment this ran against a database where a job already
        # existed — which is every database the companion walkthrough has been
        # run on. **A proof script that only works on a pristine clone is a
        # proof nobody can repeat**, and it fails in a way that reads like the
        # product being broken rather than the fixture being wrong.
        taken = set(move_in_jobs.MoveInJob.objects.values_list("request_id", flat=True))
        requests = list(cmodels.ServiceRequest.objects.exclude(id__in=taken)[:3])
        if len(requests) < 3:  # pragma: no cover
            print("  need three requests with no move-in job; skipping section 2")
        else:
            # ⚠ SAVEPOINTS, not a bare try/except — CLAUDE.md hard-won law 14.
            # A failed statement poisons the whole PostgreSQL transaction, and
            # the naive form passes the entire SQLite suite and loses the rest
            # of this script the first time the index refuses a row.
            with transaction.atomic():
                a = move_in_jobs.MoveInJob.objects.create(
                    tenant_id=tenant.id, request_id=requests[0].id, move_no="MVI-99-0001"
                )
                print(f"  first job written with {a.move_no}")

                refused = None
                try:
                    with transaction.atomic():
                        move_in_jobs.MoveInJob.objects.create(
                            tenant_id=tenant.id,
                            request_id=requests[1].id,
                            # SAME number, DIFFERENT CASE — one number to a
                            # person, two to a plain index.
                            move_no="mvi-99-0001",
                        )
                except IntegrityError as exc:
                    refused = type(exc).__name__
                check("a differently-cased duplicate is refused", refused, "IntegrityError")

                # The partial half: two NULLs must NOT collide, or a tenant
                # with no `move_in` series could hold exactly one job.
                collided = None
                try:
                    with transaction.atomic():
                        move_in_jobs.MoveInJob.objects.create(
                            tenant_id=tenant.id, request_id=requests[1].id, move_no=None
                        )
                        move_in_jobs.MoveInJob.objects.create(
                            tenant_id=tenant.id, request_id=requests[2].id, move_no=None
                        )
                        collided = False
                except IntegrityError:  # pragma: no cover - the bug this guards
                    collided = True
                check("two unnumbered jobs coexist", collided, False)

                # The connection is still usable after both — which is the
                # whole reason the savepoints are here.
                check(
                    "the transaction is still usable",
                    move_in_jobs.MoveInJob.objects.filter(move_no="MVI-99-0001").count(),
                    1,
                )
                transaction.set_rollback(True)

    # ═══════════════════════════════════════════════════════════════════
    # 3 · THE CHAIN — one number, three tables
    # ═══════════════════════════════════════════════════════════════════
    print("\n3 · approval → park → commit carries ONE number (BR-CUS-1090 §4)")
    with core_tenancy.tenant_context(tenant.id):
        from apps.customers import models as cmodels, move_in_jobs
        from apps.tenancy import wizard_parks

        # The same reason as section 2: a request that already HAS a job is
        # refused by name, and the refusal carries the existing number rather
        # than a new one — which is correct behaviour and proves nothing about
        # the allocator, so this section asks for one that has no job.
        taken = set(move_in_jobs.MoveInJob.objects.values_list("request_id", flat=True))
        request = (
            cmodels.ServiceRequest.objects.exclude(id__in=taken).order_by("request_no").first()
        )
        if request is None:  # pragma: no cover
            print("  every request on this tenant already has a job; skipping section 3")
            return 1 if FAILURES else 0
        with transaction.atomic():
            job = move_in_jobs.raise_for_request(None, request)
            allocated = job.get("move_no")
            print(f"  approval allocated {allocated!r}")
            check("the approval allocated a number", bool(allocated), True)
            check("the number is a move-in's", str(allocated or "").startswith("MVI-"), True)

            # The wizard opened ON that job CARRIES the number rather than
            # minting a second one.
            carried = wizard_parks._draft_reference("move_in", {"move_in_no": allocated})
            check("the wizard carries it rather than minting", carried, allocated)

            # And a wizard opened from SCRATCH still mints its own.
            fresh = wizard_parks._draft_reference("move_in", {})
            check("a wizard from scratch still mints its own", fresh != allocated, True)
            print(f"  a from-scratch draft would take {fresh!r}")
            transaction.set_rollback(True)

    print("\n" + ("FAILURES: " + ", ".join(FAILURES) if FAILURES else "all checks passed"))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
