#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: N utilities' bill runs at the SAME TIME on ONE database — the
#            measurement behind CR-051 task 27.
# Change:   CR-051 task 27 (PO 2026-08-31), verbatim: *"what if we get 10
#           utilities firing billing at the same time, will it hamper live
#           system performance"*.
# Rules:    BR-BIL-052 (each account is its own transaction — so the runs here
#           COMMIT as they go, exactly as production does) · CLAUDE.md rule 1
#           (every process enters its own tenant context, and the role must be
#           SUBJECT to RLS — DEF-2717)
# ───────────────────────────────────────────────────────
"""Fire 2, 5 and 10 utilities' bill runs at once and watch the database.

TWO DIFFERENT NUMBERS, AND THE CR IS EXPLICIT THAT THEY MUST NOT BE CONFLATED
-----------------------------------------------------------------------------
* **`--mode all`** — every utility's run starts at once, N processes against
  one PostgreSQL. This answers *what does contention cost each run*, and it is
  the database question.
* **`--mode queue`** — the same N runs through **two slots**, because
  `docker-compose.yml` runs the worker at `--concurrency 2`. Ten utilities
  firing at once do not run ten at once: **two run and eight queue.** This
  answers *how long before the last utility's bills exist*, which is the
  question a utility actually asks, and it is a different number.

Running both is the point. A per-run cost that barely moves and a drain time of
an hour and a half are both true at once, and quoting either alone misleads.

⚠ **AND A THIRD NUMBER IS PRINTED BESIDE THEM BECAUSE IT DECIDES WHAT THE
FIRST TWO MEAN: THE CORE COUNT.** Ten bill runs on a four-core box are ten
processes competing for four CPUs, and a slowdown there says nothing about
PostgreSQL. `pg_stat_activity`'s wait events and the ungranted-lock count are
the database's own answer; the cores and the load average are the other half,
and every wave prints all of it together so a reader cannot take one for the
other.

WHY THE RUNS COMMIT
-------------------
`cr051_run_benchmark.py` rolls its transaction back, which is right for a
single-run timing and WRONG here: one transaction open for the whole run holds
its locks for the whole run, which is not what production does and would
manufacture contention that does not exist. `runs.calculate_run` gives every
account its own transaction (BR-BIL-052) and this lets it. The drafts are
deleted afterwards, in a `finally`; `--keep` leaves them.

WHAT THE DATABASE IS ASKED, WHILE IT HAPPENS
--------------------------------------------
The parent samples `pg_stat_activity` and `pg_locks` every 250 ms on a
connection of its own and reports: peak connections, the wait events seen and
their share of samples, how many ungranted locks were ever observed, and the
longest single wait. Sampling is honest about what it is — a lock held for
100 ms between two samples is invisible — and that is stated with the figures
rather than left for a reader to assume.

SETUP
    python3 10-scripts/cr051_provision_utilities.py --count 10 --accounts 200

USAGE
    python3 10-scripts/cr051_concurrency_benchmark.py --tenants 2 5 10
    python3 10-scripts/cr051_concurrency_benchmark.py --tenants 10 --mode queue
    python3 10-scripts/cr051_concurrency_benchmark.py --tenants 1   # the baseline
"""

from __future__ import annotations

import argparse
import datetime
import json
import multiprocessing
import os
import shutil
import sys
import tempfile
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
from apps.billing import runs as billing_runs  # noqa: E402
from apps.metering import models as metering_models  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402
from core.dbfields import uuid7  # noqa: E402

from cr051_provision_utilities import PREFIX  # noqa: E402

WINDOW = (
    datetime.date(2026, 7, 1),
    datetime.date(2026, 7, 31),
    datetime.date(2026, 8, 5),
)

#: `docker-compose.yml` runs the celery service at `--concurrency 2`. Read out
#: of the file rather than assumed, and named here so a reader can see what the
#: queue mode is modelling.
WORKER_SLOTS = 2

#: Printed beside every wave. See the note in `one_wave`: on a four-core box,
#: ten concurrent runs are a CPU measurement wearing a database measurement's
#: clothes, and the only defence is stating the machine with the figure.
_CORES = os.cpu_count() or 0


def _load_average() -> float:
    try:
        return os.getloadavg()[0]
    except OSError:  # not available on every platform
        return float("nan")


# ── one utility's run, in its own process ───────────────────────────────────
def _one_run(subdomain: str, out_dir: str) -> None:
    """Prepare + calculate for ONE tenant, committing as production does.

    ⚠ The inherited connection is DISCARDED, not closed: closing it would close
    the file descriptor the PARENT is still using and the parent dies with
    *ssl/tls alert bad record mac*, which reads like a database fault and is a
    fork bug.
    """
    from django.db import connections

    for conn in connections.all():
        conn.connection = None

    started = time.perf_counter()
    outcome = {"subdomain": subdomain}
    try:
        tenant = tenancy_models.Tenant.objects.get(subdomain=subdomain)
        with core_tenancy.tenant_context(str(tenant.id)):
            from apps.metering import derivation

            cycle, unit_ids = None, []
            for candidate in metering_models.Cycle.objects.all():
                found = derivation.units_in_cycle(candidate.id)
                if len(found) > len(unit_ids):
                    cycle, unit_ids = candidate, found
            run = billing_models.BillRun.objects.create(
                tenant_id=tenant.id,
                cycle_id=cycle.id,
                period_start=WINDOW[0],
                period_end=WINDOW[1],
                bill_date=WINDOW[2],
                idempotency_key=f"concurrency-{uuid7()}",
                status="draft",
            )
            outcome["run_id"] = str(run.pk)
            prepare_started = time.perf_counter()
            prepared = billing_runs.prepare_run(
                cycle_id=cycle.id,
                period_start=WINDOW[0],
                period_end=WINDOW[1],
                service_date=WINDOW[2],
            )
            outcome["prepare"] = time.perf_counter() - prepare_started
            outcome["ready"] = len(prepared.ready)
            calculate_started = time.perf_counter()
            calculated = billing_runs.calculate_run(prepared, bill_run=run)
            outcome["calculate"] = time.perf_counter() - calculate_started
            outcome["drafted"] = len(calculated.drafted)
            outcome["breaks"] = len(calculated.breaks)
    except Exception as problem:  # noqa: BLE001 — reported, never swallowed
        outcome["error"] = f"{type(problem).__name__}: {problem}"
    outcome["wall"] = time.perf_counter() - started
    # ONE json file per child rather than a `multiprocessing.Queue`: a child
    # that fills a pipe and exits before the parent drains it is the classic
    # join-before-drain deadlock, and a benchmark that hangs at ten processes
    # would be discovered at ten processes. A file also survives a child that
    # dies badly, which is the case this measurement must not lose.
    Path(out_dir, f"{subdomain}.json").write_text(json.dumps(outcome), encoding="utf-8")


# ── what the database was doing while that happened ─────────────────────────
class _DatabaseWatch:
    """Samples `pg_stat_activity` and `pg_locks` on a connection of its own.

    ⚠ **SAMPLING IS HONEST ABOUT WHAT IT MISSES, AND THE REPORT SAYS SO.** A
    lock taken and released between two samples is invisible here. What this
    can state is what was TRUE at 250 ms intervals — peak connections, which
    wait events appeared and how often, whether an ungranted lock was ever
    observed, and the longest wait seen. That is enough to answer *did they get
    in each other's way*; it is not a lock trace.
    """

    def __init__(self, interval: float = 0.25) -> None:
        self.interval = interval
        self.samples = 0
        self.peak_connections = 0
        self.peak_active = 0
        self.waits: dict[str, int] = {}
        self.ungranted_seen = 0
        self.longest_wait = 0.0
        self.longest_wait_event = ""

    def sample(self, cursor) -> None:
        self.samples += 1
        cursor.execute(
            "SELECT count(*) FILTER (WHERE true), "
            "       count(*) FILTER (WHERE state = 'active') "
            "FROM pg_stat_activity WHERE datname = current_database()"
        )
        total, active = cursor.fetchone()
        self.peak_connections = max(self.peak_connections, total or 0)
        self.peak_active = max(self.peak_active, active or 0)

        cursor.execute(
            "SELECT coalesce(wait_event_type, '') || '/' || coalesce(wait_event, ''), "
            "       count(*), "
            "       max(extract(epoch FROM (now() - state_change))) "
            "FROM pg_stat_activity "
            "WHERE datname = current_database() AND state = 'active' "
            "  AND wait_event_type IS NOT NULL "
            "GROUP BY 1"
        )
        for name, count, waited in cursor.fetchall():
            self.waits[name] = self.waits.get(name, 0) + int(count)
            if name.startswith("Lock/") and waited and waited > self.longest_wait:
                self.longest_wait = float(waited)
                self.longest_wait_event = name

        cursor.execute("SELECT count(*) FROM pg_locks WHERE NOT granted")
        (ungranted,) = cursor.fetchone()
        self.ungranted_seen = max(self.ungranted_seen, int(ungranted or 0))

    def report(self) -> None:
        print(f"  samples                {self.samples} at {self.interval:.2f}s")
        print(
            f"  peak connections       {self.peak_connections} (active {self.peak_active})"
        )
        print(f"  ungranted locks seen   {self.ungranted_seen}")
        if self.longest_wait:
            print(
                f"  longest LOCK wait      {self.longest_wait:.2f}s "
                f"({self.longest_wait_event})"
            )
        else:
            print("  longest LOCK wait      none observed")
        if self.waits:
            print("  wait events (sample count):")
            for name, count in sorted(self.waits.items(), key=lambda pair: -pair[1])[
                :8
            ]:
                print(f"    {name:<34} {count:>6}")
        else:
            print("  wait events            none observed")


def _clean_up(subdomains: list[str], run_ids: dict[str, str]) -> None:
    """Delete the drafts these runs wrote. Only DRAFTS — an issued invoice can
    never be deleted (hard rule 4) and these runs never issue one."""
    removed = 0
    for subdomain in subdomains:
        run_id = run_ids.get(subdomain)
        if run_id is None:
            continue
        tenant = tenancy_models.Tenant.objects.get(subdomain=subdomain)
        with core_tenancy.tenant_context(str(tenant.id)):
            issued = billing_models.Invoice.objects.filter(bill_run_id=run_id).exclude(
                status=billing_models.INVOICE_DRAFT
            )
            if issued.exists():
                print(
                    f"  REFUSING to clean {subdomain}: {issued.count()} issued — hard rule 4"
                )
                continue
            billing_models.InvoiceLine.objects.filter(
                invoice__bill_run_id=run_id
            ).delete()
            removed += billing_models.Invoice.objects.filter(bill_run_id=run_id).count()
            billing_models.Invoice.objects.filter(bill_run_id=run_id).delete()
            billing_models.BillRunBreak.objects.filter(bill_run_id=run_id).delete()
            billing_models.BillRunExclusion.objects.filter(bill_run_id=run_id).delete()
            billing_models.BillRun.objects.filter(pk=run_id).delete()
    print(f"cleaned up {removed} draft(s) across {len(subdomains)} utilities")


def one_wave(subdomains: list[str], *, slots: int, keep: bool) -> dict:
    """Run these utilities, `slots` at a time, and watch the database."""
    label = (
        "all at once"
        if slots >= len(subdomains)
        else f"{slots} slot(s), the rest queued"
    )
    print(f"\n── {len(subdomains)} utilities · {label} ──")

    from django.db import connection

    context = multiprocessing.get_context("fork")
    out_dir = tempfile.mkdtemp(prefix="cr051-concurrency-")
    watch = _DatabaseWatch()
    pending = list(subdomains)
    running: list = []
    outcomes: list[dict] = []
    started = time.perf_counter()

    # The parent's own connection, opened BEFORE the first fork so no child
    # ever inherits a mid-statement socket.
    with connection.cursor() as cursor:
        while pending or running:
            while pending and len(running) < slots:
                child = context.Process(target=_one_run, args=(pending.pop(0), out_dir))
                child.start()
                running.append(child)
            time.sleep(watch.interval)
            try:
                watch.sample(cursor)
            except (
                Exception
            ) as problem:  # noqa: BLE001 — a watcher never fails the work
                print(f"  (watch: {type(problem).__name__}: {problem})")
            for child in list(running):
                if not child.is_alive():
                    child.join()
                    running.remove(child)
    drain = time.perf_counter() - started

    for subdomain in subdomains:
        path = Path(out_dir, f"{subdomain}.json")
        if path.exists():
            outcomes.append(json.loads(path.read_text(encoding="utf-8")))
        else:
            # A child that wrote no file died before it could — reported, never
            # dropped, because a missing run is the interesting result here.
            outcomes.append(
                {
                    "subdomain": subdomain,
                    "error": "the process wrote no result",
                    "wall": 0.0,
                }
            )
    shutil.rmtree(out_dir, ignore_errors=True)
    outcomes.sort(key=lambda one: one["subdomain"])

    print(
        f"  {'utility':<20} {'ready':>7} {'prepare':>9} {'calculate':>10} {'wall':>9} {'ms/acct':>9}"
    )
    for one in outcomes:
        if "error" in one:
            print(f"  {one['subdomain']:<20} ERROR {one['error'][:70]}")
            continue
        ready = one.get("ready", 0) or 1
        print(
            f"  {one['subdomain']:<20} {one.get('ready', 0):>7,} "
            f"{one.get('prepare', 0):>8.1f}s {one.get('calculate', 0):>9.1f}s "
            f"{one['wall']:>8.1f}s {one['wall'] * 1000 / ready:>9.0f}"
        )
    good = [one for one in outcomes if "error" not in one]
    if good:
        walls = sorted(one["wall"] for one in good)
        per = [one["wall"] * 1000 / (one.get("ready", 0) or 1) for one in good]
        print(
            f"  {'—':<20} {'':>7} {'':>9} {'':>10} "
            f"slowest {walls[-1]:.1f}s · median {walls[len(walls) // 2]:.1f}s · "
            f"per-account median {sorted(per)[len(per) // 2]:.0f} ms"
        )
    print(f"  DRAIN (first start to last finish): {drain:.1f}s")
    watch.report()
    # ⚠ **THE MACHINE IS PART OF THE RESULT AND MUST BE PRINTED BESIDE IT.**
    # Ten bill runs on FOUR cores are not ten runs contending for a database;
    # they are ten runs contending for four CPUs, and a reader who cannot see
    # the core count will read the first as the second. `pg_stat_activity`
    # answers the database half (wait events, ungranted locks) and this answers
    # the other half.
    print(
        f"  machine                {_CORES} cores · load {_load_average():.1f} "
        f"· {len(subdomains)} run(s) wanted {slots} slot(s)"
    )

    if not keep:
        _clean_up(
            [one["subdomain"] for one in good],
            {one["subdomain"]: one.get("run_id") for one in good},
        )
    return {
        "count": len(subdomains),
        "slots": slots,
        "drain": drain,
        "outcomes": outcomes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenants", type=int, nargs="+", default=[1, 2, 5, 10])
    parser.add_argument(
        "--mode",
        choices=("all", "queue", "both"),
        default="both",
        help="all = N processes at once · queue = N through WORKER_SLOTS slots",
    )
    parser.add_argument("--keep", action="store_true", help="leave the drafts behind")
    args = parser.parse_args()

    from django.db import connection

    if connection.vendor != "postgresql":
        sys.exit("this measurement needs PostgreSQL (CLAUDE.md rule 1)")
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
        )
        superuser, bypass = cursor.fetchone()
    if superuser or bypass:
        sys.exit(
            "REFUSING: this connection's role bypasses row-level security, so every "
            "tenant would read every other tenant's rows and the figures would be of "
            "a system that does not exist (DEF-2717, CLAUDE.md hard rule 1)."
        )

    available = [
        tenant.subdomain
        for tenant in tenancy_models.Tenant.objects.filter(
            subdomain__startswith=PREFIX
        ).order_by("subdomain")
    ]
    if not available:
        sys.exit(
            "no perf utilities exist — run:\n"
            "  python3 10-scripts/cr051_provision_utilities.py --count 10 --accounts 200"
        )
    print(f"utilities available: {len(available)} ({', '.join(available[:4])}…)")

    for count in sorted(args.tenants):
        if count > len(available):
            print(f"\n(skipping {count}: only {len(available)} utilities exist)")
            continue
        chosen = available[:count]
        if args.mode in ("all", "both"):
            one_wave(chosen, slots=count, keep=args.keep)
        if args.mode in ("queue", "both") and count > WORKER_SLOTS:
            one_wave(chosen, slots=WORKER_SLOTS, keep=args.keep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
