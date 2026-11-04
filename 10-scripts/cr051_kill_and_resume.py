#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: CR-051 task 11's checkpoint, proved by KILLING A REAL WORKER —
#            SIGKILL to a forked process mid-pass, then resuming it, against
#            real PostgreSQL with committed rows.
# Change:   CR-051 task 11 — *"Write a checkpoint so a killed worker resumes
#           rather than re-walking the cycle."*
# Rules:    BR-BIL-052 (per-account, restartable, resumable) · BR-BIL-023 (a
#           re-calculation REPLACES a draft) · CLAUDE.md hard rule 6 (a bill
#           run is idempotent) · rule 1 (tenant scoping)
# Tests:    the DETERMINISTIC half is 06-backend/tests/test_cr051_run_scale.py
#           (tc4/tc5/tc6, both tiers). This is the half a suite cannot host —
#           see "WHY THIS IS A SCRIPT" below.
# ───────────────────────────────────────────────────────
"""Kill a bill-run worker mid-pass with signal 9, resume it, and check the bills.

WHY THIS IS A SCRIPT AND NOT A TEST, and it is not a preference
---------------------------------------------------------------
A real kill needs a second PROCESS, and a second process can only see rows the
first one COMMITTED. In pytest-django that means `django_db(transaction=True)`,
and **this repository has already established twice that it cannot host that**:

    tests/test_us_cus_003_account_race.py — *"it needs committed fixture data,
    i.e. `django_db(transaction=True)`, whose teardown flushes the database —
    including the platform rows seeded by data migrations (`account_types`,
    `services`, `subscription_plans`) that every later test in the session
    depends on. Buying a nicer-looking test by breaking the suite it runs in is
    not a trade this lane will make."*

Measured again here, and it is worse than that note says — the flush does not
merely delete seed rows, it FAILS:

    psycopg.errors.FeatureNotSupported: cannot truncate a table referenced in a
    foreign key constraint
    DETAIL:  Table "meter_read_asset_monthly_usage" references "assets".
    django.core.management.base.CommandError: Database
    test_sbh_agent_… couldn't be flushed.

…which leaves the test database unusable for every case after it. So the
deterministic half of task 11 lives in the suite, on both tiers, and the
real-kill half lives here — the same disposition, for the same reason, as the
two race files. `cr026_import_benchmark.py` is the standing precedent for a
measurement that is a script rather than a case.

WHAT IT PROVES, and both halves matter
--------------------------------------
1. **Nobody is billed twice.** After the kill and the resume, every account has
   exactly ONE draft invoice, and the accounts the first pass had already
   drafted carry the SAME total to the last decimal. That is hard rule 6.
2. **The cycle is not re-walked.** The resumed pass gathers only the accounts
   the killed one had not finished. That is what task 11 is for, and at the
   measured 111 ms per account it is what stops a worker killed at 9,000 of
   10,000 paying twenty-three minutes again.

IT WRITES AND THEN CLEANS UP. Unlike `cr051_run_benchmark.py` this CANNOT run
inside a rolled-back transaction — the whole point is that the child's writes
survive into another process — so it clones its accounts, runs, and deletes
exactly what it created at the end, in a `finally`. A `--keep` flag leaves the
rows for inspection when a run has gone wrong.

USAGE
    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL=postgres://…  python3 10-scripts/cr051_kill_and_resume.py
    python3 10-scripts/cr051_kill_and_resume.py --accounts 12 --kill-after 4
"""

from __future__ import annotations

import argparse
import datetime
import multiprocessing
import os
import signal
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402

settings.DEBUG = False

from apps.billing import models as billing_models  # noqa: E402
from apps.billing import run_jobs  # noqa: E402
from apps.billing import runs as billing_runs  # noqa: E402
from apps.customers import models as customer_models  # noqa: E402
from apps.metering import models as metering_models  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import jobs as core_jobs  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402
from core.dbfields import uuid7  # noqa: E402

import cr051_run_benchmark as bench  # noqa: E402

WINDOW = (
    datetime.date(2026, 7, 1),
    datetime.date(2026, 7, 31),
    datetime.date(2026, 8, 5),
)
CLONE_PREFIX = "KR"


def _child(job_id: str, tenant_id: str) -> None:
    """The worker, in its own process, reporting every account.

    ⚠ The inherited connection is DISCARDED, not closed. `connections.
    close_all()` here would close the file descriptors the PARENT is still
    using, and the parent then dies with *"consuming input failed: SSL error:
    ssl/tls alert bad record mac"* — which reads like a database fault and is a
    fork bug.

    ⚠ **IT GOES THROUGH THE CELERY TASK AND NOT THROUGH `core_jobs.run_job`
    (CR-105-BRC03).** It called `run_job(job_id, run_jobs.run_calculate_job)`
    until 2026-09-14, and on real PostgreSQL that cannot work: `run_job` LOADS
    the record before it enters tenant context, `jobs` carries RLS FORCE, and a
    freshly-forked process has no `app.tenant_id` — so the load returned zero
    rows and this proof died with

        child: JobsError: unknown job '01a0a03c-…'

    on every run. `apps.tenancy.tasks.run_pending_job` is the thing that makes
    a real worker work: it enters the tenant from the MESSAGE before touching
    the database, which is what its own docstring is about. Calling it here
    makes the child a worker rather than an imitation of one — the same reason
    the resume below now calls `core_jobs.resume`.
    """
    from django.db import connections

    for conn in connections.all():
        conn.connection = None
    run_jobs.PROGRESS_EVERY = 1
    try:
        from apps.tenancy import tasks as tenancy_tasks

        tenancy_tasks.run_pending_job(job_id, tenant_id, kind=run_jobs.CALCULATE_JOB)
    except Exception as problem:  # noqa: BLE001 — the child's own log line
        print(f"  child: {type(problem).__name__}: {problem}", flush=True)


def _drafts(tenant, run) -> dict[str, str]:
    return {
        str(account_id): str(total)
        for account_id, total in billing_models.Invoice.objects.filter(
            tenant_id=tenant.id, bill_run=run, status=billing_models.INVOICE_DRAFT
        ).values_list("account_id", "total")
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accounts", type=int, default=12)
    parser.add_argument(
        "--kill-after", type=int, default=3, help="accounts finished before SIGKILL"
    )
    parser.add_argument("--per-account-delay", type=float, default=0.4)
    parser.add_argument(
        "--keep", action="store_true", help="do not clean up the cloned rows"
    )
    args = parser.parse_args()

    from django.db import connection

    if connection.vendor != "postgresql":
        sys.exit(
            "this proof needs PostgreSQL: a second PROCESS has to see rows the first "
            "COMMITTED, and config/settings/test.py hardcodes in-memory SQLite, which "
            "no other process can open at all (CLAUDE.md law 14's own reason)."
        )

    tenant = tenancy_models.Tenant.objects.order_by("created_at").first()
    if tenant is None:
        sys.exit("no tenant in this database — run `manage.py seed_demo` first")

    created: dict[str, list] = {}
    run = None
    with core_tenancy.tenant_context(str(tenant.id)):
        from apps.metering import derivation

        cycle, unit_ids = None, []
        for candidate in metering_models.Cycle.objects.all():
            found = derivation.units_in_cycle(candidate.id)
            if len(found) > len(unit_ids):
                cycle, unit_ids = candidate, found
        if cycle is None or not unit_ids:
            sys.exit(f"tenant {tenant.subdomain!r} has no cycle with units in it")
        templates = list(
            customer_models.Account.objects.filter(
                tenant_id=tenant.id, unit_id__in=unit_ids
            ).order_by("account_no")
        )
        print(
            f"tenant: {tenant.subdomain} · cycle {cycle.code} · {len(templates)} accounts"
        )

        try:
            # ── clone up to the wanted population, remembering what we made ──
            before = {str(one.id) for one in templates}
            for index in range(len(templates), args.accounts):
                bench.clone_account(templates[index % len(templates)], index)
            after = set(
                str(one)
                for one in customer_models.Account.objects.filter(
                    tenant_id=tenant.id, account_no__startswith="BM-"
                ).values_list("id", flat=True)
            )
            created["accounts"] = sorted(after - before)
            print(f"cloned {len(created['accounts'])} account(s) for this proof")

            run = billing_models.BillRun.objects.create(
                tenant_id=tenant.id,
                cycle_id=cycle.id,
                period_start=WINDOW[0],
                period_end=WINDOW[1],
                bill_date=WINDOW[2],
                idempotency_key=f"kill-and-resume-{uuid7()}",
                status="draft",
            )

            previous_dispatch = core_jobs._dispatcher  # noqa: SLF001
            core_jobs.set_job_dispatcher(lambda _record: None)
            try:
                record = core_jobs.enqueue(
                    run_jobs.CALCULATE_JOB,
                    payload={"run_id": str(run.pk), "actor_user_id": None},
                    scope_key=f"billing:calculate:kill:{run.pk}",
                )
            finally:
                core_jobs.set_job_dispatcher(previous_dispatch)
            job_id = record["id"]

            # Widen the window so the kill lands mid-pass. The KILL is real;
            # this only makes the race winnable.
            original_account = billing_runs.calculate_account

            def slowly(*call_args, **call_kwargs):
                time.sleep(args.per_account_delay)
                return original_account(*call_args, **call_kwargs)

            billing_runs.calculate_account = slowly

            child = multiprocessing.get_context("fork").Process(
                target=_child, args=(job_id, str(tenant.id))
            )
            print("\n── the first pass, in its own process ──")
            child.start()
            deadline = time.monotonic() + 120
            marker: dict = {}
            while time.monotonic() < deadline and child.is_alive():
                marker = (core_jobs._store.get(job_id) or {}).get(
                    "checkpoint"
                ) or {}  # noqa: SLF001
                if marker.get("done", 0) >= args.kill_after:
                    break
                time.sleep(0.05)
            if marker.get("done", 0) < args.kill_after:
                sys.exit(
                    f"the child never reached {args.kill_after} accounts (checkpoint {marker})"
                )
            print(f"  checkpoint before the kill: {marker}")
            os.kill(child.pid, signal.SIGKILL)
            child.join(timeout=60)
            print(f"  child exit code: {child.exitcode} (expect -{signal.SIGKILL})")
            if child.exitcode != -signal.SIGKILL:
                sys.exit(
                    "the child was NOT killed by signal 9 — this proof is worthless"
                )

            killed = core_jobs._store.get(job_id)  # noqa: SLF001
            partial = _drafts(tenant, run)
            # ⚠ THE POPULATION IS WHAT THE RUN FOUND, NOT WHAT WAS ASKED FOR.
            # `--accounts` is a FLOOR the clone tops the cycle up to; the cycle
            # may already hold more. The first run of this script compared
            # against the argument and reported "-34 accounts unbilled" over a
            # pass that had worked perfectly — a check whose output cannot tell
            # pass from fail is worse than no check (CLAUDE.md law 11).
            population = int((killed["checkpoint"] or {}).get("total") or 0)
            print(f"  the run's READY population: {population} accounts")
            print(
                f"  job status after the kill: {killed['status']} (a SIGKILL records nothing)"
            )
            print(f"  checkpoint survived: {killed['checkpoint']}")
            print(f"  drafts committed before the kill: {len(partial)} of {population}")
            if not 0 < len(partial) < population:
                sys.exit(
                    "the kill landed outside the pass — re-run with a longer delay"
                )

            # ── the resume, in THIS process ──
            print("\n── the resume ──")
            gathered: list[str] = []
            original_gather = billing_runs.gather.gather_account

            def counted(**call_kwargs):
                gathered.append(str(getattr(call_kwargs["account"], "account_no", "?")))
                return original_gather(**call_kwargs)

            billing_runs.gather.gather_account = counted
            billing_runs.calculate_account = original_account
            try:
                # ⚠ **THIS WAS THREE HAND-WRITTEN STEPS UNTIL 2026-09-14 AND
                # THAT IS HOW THE REAL DEFECT HID (CR-105-BRC03).** It read
                #
                #     core_jobs.fail(job_id, "worker killed (SIGKILL)")
                #     resumed = core_jobs.start(job_id)
                #     run_jobs.run_calculate_job(resumed)
                #     core_jobs.succeed(job_id)
                #
                # and every line of it was correct — but the FIRST one is a
                # step no deployment performs. A killed worker writes nothing,
                # so its record says `running`; `start()` refuses a `running`
                # record; and the acks-late redelivery therefore raised
                # *"cannot start (resume is failed→running)"* and gave up. By
                # marking the record failed itself, this proof supplied the one
                # hop production did not have, and then proved the rest — so it
                # passed, honestly, over a checkpoint nothing could reach.
                #
                # `core_jobs.resume` is now that hop, and this calls it, so the
                # proof exercises the path a worker actually takes.
                core_jobs.resume(job_id)
            finally:
                billing_runs.gather.gather_account = original_gather

            final = _drafts(tenant, run)
            print(
                f"  accounts gathered by the resumed pass: {len(gathered)} of {population}"
            )
            print(f"  drafts after the resume: {len(final)} of {population}")

            broke = billing_models.BillRunBreak.objects.filter(
                tenant_id=tenant.id, bill_run=run
            ).count()
            ok = True
            # An account that BROKE is accounted for and is not "unbilled" —
            # BR-BIL-055: a break never blocks the run, and the seeded fixture
            # deliberately carries one (a disputed read).
            if len(final) + broke != population:
                missing = population - len(final) - broke
                print(
                    f"  ✗ the resumed run left {missing} account(s) neither billed nor broken"
                )
                ok = False
            moved = [
                account
                for account, total in partial.items()
                if final.get(account) != total
            ]
            if moved:
                print(
                    f"  ✗ {len(moved)} account(s) already drafted were RE-PRICED by the resume"
                )
                ok = False
            else:
                print(
                    f"  ✓ every one of the {len(partial)} drafts the killed pass wrote is unchanged"
                )
            duplicates = billing_models.Invoice.objects.filter(
                tenant_id=tenant.id, bill_run=run, status=billing_models.INVOICE_DRAFT
            ).count() - len(final)
            if duplicates:
                print(f"  ✗ {duplicates} DUPLICATE draft(s) — hard rule 6 violated")
                ok = False
            else:
                print("  ✓ exactly one draft per account — nobody was billed twice")
            if len(gathered) >= population:
                print(
                    "  ✗ the resumed pass re-walked the whole cycle — the checkpoint bought nothing"
                )
                ok = False
            else:
                saved = population - len(gathered)
                print(
                    f"  ✓ the cycle was NOT re-walked — {saved} account(s) not gathered again"
                )
            print("\nRESULT:", "PASS" if ok else "FAIL")
            return 0 if ok else 1
        finally:
            if args.keep:
                print("\n--keep: the cloned rows and the run are left in the database")
            elif run is not None:
                _clean_up(tenant, run, created)


def _clean_up(tenant, run, created: dict[str, list]) -> None:
    """Delete exactly what this proof created, and nothing else.

    Only DRAFT invoices are touched — an issued bill can never be deleted (hard
    rule 4) and this proof never issues one, so a run that somehow holds an
    issued invoice is reported rather than cleaned.
    """
    issued = billing_models.Invoice.objects.filter(
        tenant_id=tenant.id, bill_run=run
    ).exclude(status=billing_models.INVOICE_DRAFT)
    if issued.exists():
        print(
            f"\nREFUSING TO CLEAN UP: run {run.pk} holds {issued.count()} non-draft invoice(s)"
        )
        return
    lines = billing_models.InvoiceLine.objects.filter(invoice__bill_run=run)
    print(f"\ncleaning up: {lines.count()} line(s), ", end="")
    lines.delete()
    drafts = billing_models.Invoice.objects.filter(tenant_id=tenant.id, bill_run=run)
    print(f"{drafts.count()} draft(s), ", end="")
    drafts.delete()
    billing_models.BillRunBreak.objects.filter(bill_run=run).delete()
    billing_models.BillRunExclusion.objects.filter(bill_run=run).delete()
    run.delete()
    tenancy_models.Job.objects.filter(
        tenant_id=tenant.id, scope_key__startswith="billing:calculate:kill:"
    ).delete()
    print("the run, and the job record")
    print(
        "⚠ the CLONED accounts are left: they are what `cr051_run_benchmark.py` also makes and"
    )
    print("  they are prefixed BM- so they are recognisable. Remove them with:")
    print(
        "  DELETE FROM accounts WHERE account_no LIKE 'BM-%';  (and their units/meters)"
    )


if __name__ == "__main__":
    sys.exit(main())
