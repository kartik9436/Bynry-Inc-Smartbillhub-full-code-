#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: the PROOF CR-051 task 29 owes — does giving billing its own named
#            worker with a CPU share give the clerk their screens back?
# Change:   PO ruling 2026-08-31, verbatim: *"we will ahve to create named worker
#           for billing - eventually we should able to scale these works on the
#           fly itf required; but billing will need its own named workers -
#           otherwise it will slow down the system"*
# Rules:    CLAUDE.md rule 1 (every read inside tenant_context, on a connection
#           SUBJECT to RLS — DEF-2717) · hard-won law 7 (a measurement, like a
#           guard, is only worth what its failing case is worth)
# ───────────────────────────────────────────────────────
"""Time a clerk's screens with billing's CPU share CAPPED and UNCAPPED.

WHAT THE RULING ASKS FOR, AND WHY A PASSING TEST WOULD NOT ANSWER IT
--------------------------------------------------------------------
The decision log is explicit: *"Re-run task 28's screen timings with the split in
place and a CPU limit on the billing worker: the accounts list p95 under two
concurrent runs must come back toward its idle 605.8 ms rather than 2,868.9 ms.
A split that separates the queues and leaves the clerk's screens exactly as slow
has not done the thing the PO asked for, and saying so is the point of measuring
it."*

So this script measures FIVE sets in one run, in this order:

    idle · loaded UNCAPPED · idle · loaded CAPPED · idle

The uncapped set reproduces task 28. The capped set is the same load with the
same code under the CPU share `docker-compose.yml` now gives `celery-billing`.
Three idle sets bracket the two loaded ones, because five other lanes share these
four cores and an idle-then-loaded pair taken minutes apart can be a measurement
of the machine rather than of the bill run. Task 28's own second idle set moved
by 1.55× and changed how its figures had to be read; that is the reason the
bracketing is not optional.

⚠ **HOW THE CAP IS APPLIED, AND WHY IT IS THE SAME THING DOCKER DOES.**
`deploy.resources.limits.cpus: "1.0"` is implemented by Docker as Linux CFS
bandwidth control: `cpu.cfs_quota_us = 1.0 × cpu.cfs_period_us` on the
container's cgroup. This script creates a cgroup and sets exactly those two
files, then puts every bill-run process into it. **It is the same kernel
mechanism, set to the same numbers** — not a proxy, not `nice`, not an affinity
mask. What it deliberately does NOT do is start containers: the screens are timed
in-process the way task 28 timed them, so the two runs are comparable line for
line, and the only thing that changes between them is the quota.

Verified before it was trusted: with the quota at `0.5` a fixed workload's
`cpu.stat` showed **18 throttled periods**; with the quota off, **0**.

⚠ **THE LOAD IS SUSTAINED, AND THAT IS THE WHOLE REASON THE FIRST TASK-28 RUN WAS
WRONG.** Ten runs fired at once drain in ~167 s and the accounts-list measurement
alone takes ~116 s, so a burst run times its later screens against a machine that
has gone quiet — and reports it as "under load". A supervisor thread relaunches
any run that finishes, so every screen in a loaded set is timed under the same
conditions. This reuses `cr051_screen_latency._SustainedLoad` for that rather
than reimplementing it.

USAGE
    DATABASE_URL=postgres://…/sbh_cr051perf \\
      python3 10-scripts/cr051_billing_worker_cap.py --runs 2 --samples 100

    --runs 2      how many bill runs are kept in flight. TWO is the number that
                  matters: `--concurrency 2` is what this deployment can execute
                  at once, so it is what a clerk actually works alongside.
    --cpus 1.0    the quota to test, matching docker-compose.yml's `cpus:`.
    --tenant      whose screens to time. Default: the OLDEST tenant, which in
                  the perf database is `brazosbend` — a bystander that fires no
                  run, which is the question a shared deployment actually poses.
"""

from __future__ import annotations

import argparse
import multiprocessing
import os
import pathlib
import sys
import time

BACKEND = pathlib.Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402

settings.DEBUG = False

from apps.tenancy import models as tenancy_models  # noqa: E402

import cr051_screen_latency as latency  # noqa: E402
from cr051_provision_utilities import PREFIX  # noqa: E402

#: Docker's own default CFS period, in microseconds. `--cpus N` sets
#: `cpu.cfs_quota_us = N × this`. Kept as a named constant so the arithmetic
#: below reads as the docker flag it is imitating.
CFS_PERIOD_US = 100_000


class CpuQuota:
    """A cgroup with the CPU bandwidth `deploy.resources.limits.cpus` would set.

    ⚠ Every process put in here SHARES the quota, exactly as the processes inside
    one container share the container's. That is why `--concurrency 2` under
    `cpus: "1.0"` means two bill runs at half speed each, and not one core each —
    the trap the compose comment warns about in the other direction for
    `replicas`.
    """

    def __init__(self, cpus: float | None, name: str = "sbh-billing-worker") -> None:
        self.cpus = cpus
        self.path = pathlib.Path("/sys/fs/cgroup/cpu") / name if cpus else None

    def __enter__(self) -> "CpuQuota":
        if self.path is None:
            return self
        self.path.mkdir(exist_ok=True)
        (self.path / "cpu.cfs_period_us").write_text(str(CFS_PERIOD_US))
        (self.path / "cpu.cfs_quota_us").write_text(str(int(self.cpus * CFS_PERIOD_US)))
        return self

    def __exit__(self, *_exc) -> None:
        if self.path is None:
            return
        # Release the quota rather than removing the directory: a cgroup with a
        # process still exiting inside it cannot be rmdir'd, and a leftover
        # directory with no quota throttles nothing.
        try:
            (self.path / "cpu.cfs_quota_us").write_text("-1")
        except OSError:
            pass

    def throttled_periods(self) -> int | None:
        """How many periods the kernel actually throttled. **This is the check
        that says the cap was really applied** — a quota written to a cgroup that
        no process joined would look identical from the outside, and would be a
        measurement of nothing (DEF-182)."""
        if self.path is None:
            return None
        for line in (self.path / "cpu.stat").read_text().splitlines():
            if line.startswith("nr_throttled"):
                return int(line.split()[1])
        return None


def _capped_run(cgroup: str | None, subdomain: str, out_dir: str) -> None:
    """One bill run, inside the quota if there is one.

    It joins the cgroup as its FIRST act, before any work — moving the pid from
    the parent after `start()` would leave a short uncapped window, and a
    measurement with a hole in it is the thing this whole file is arguing
    against.
    """
    if cgroup:
        (pathlib.Path(cgroup) / "cgroup.procs").write_text(str(os.getpid()))
    import cr051_concurrency_benchmark as concurrency

    concurrency._one_run(subdomain, out_dir)


class CappedLoad(latency._SustainedLoad):
    """`_SustainedLoad`, with every run it launches inside the quota.

    Subclassed rather than copied so the SUSTAIN behaviour — relaunching any run
    that finishes, for the whole measurement — is literally the same code that
    task 28 finally used, and cannot drift from it.
    """

    def __init__(self, subdomains: list[str], cgroup: str | None) -> None:
        super().__init__(subdomains)
        self.cgroup = cgroup

    def _spawn(self, subdomain: str):
        context = multiprocessing.get_context("fork")
        child = context.Process(target=_capped_run, args=(self.cgroup, subdomain, "/tmp"))
        child.start()
        self.launched += 1
        return child


def _p(values: list[float], share: float) -> float:
    return latency._percentile([one for one in values if one == one], share)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--cpus", type=float, default=1.0)
    parser.add_argument("--tenant", default=None)
    args = parser.parse_args()

    from django.db import connection

    if connection.vendor != "postgresql":
        sys.exit("this measurement needs PostgreSQL (CLAUDE.md rule 1)")
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        superuser, bypass = cursor.fetchone()
    if superuser or bypass:
        sys.exit(
            "REFUSING: this role bypasses row-level security, so the screens would "
            "be timed without the tenant predicate every real request pays for "
            "(DEF-2717, CLAUDE.md hard rule 1)."
        )

    tenants = tenancy_models.Tenant.objects.order_by("created_at")
    tenant = tenants.filter(subdomain=args.tenant).first() if args.tenant else tenants.first()
    if tenant is None:
        sys.exit("no tenant in this database")
    available = [
        one.subdomain
        for one in tenancy_models.Tenant.objects.filter(subdomain__startswith=PREFIX).order_by(
            "subdomain"
        )
    ][: args.runs]
    if len(available) < args.runs:
        sys.exit(
            f"only {len(available)} perf utilities exist — run "
            "10-scripts/cr051_provision_utilities.py first"
        )

    print(
        f"timing {tenant.subdomain}'s screens · {args.samples} samples each · "
        f"{args.runs} bill run(s) in flight · cap {args.cpus} CPU\n"
        f"load average now: {', '.join(f'{one:.2f}' for one in os.getloadavg())} "
        f"on {os.cpu_count()} cores"
    )

    sets: dict[str, dict[str, list[float]]] = {}

    def take(label: str) -> None:
        sets[label] = latency.measure(tenant, args.samples)
        latency.report(label, sets[label])

    def loaded(label: str, cpus: float | None) -> None:
        with CpuQuota(cpus) as quota:
            before = quota.throttled_periods()
            load = CappedLoad(available, str(quota.path) if quota.path else None)
            load.start()
            time.sleep(3)  # let them get past their own setup and into the walk
            sets[label] = latency.measure(tenant, args.samples)
            launched, after = load.launched, quota.throttled_periods()
            load.stop()
        latency.report(label, sets[label])
        print(
            f"  SUSTAINED: {launched} run(s) started to keep {len(available)} in "
            "flight for the whole measurement"
        )
        if cpus is not None:
            print(
                f"  the cap was REALLY APPLIED: the kernel throttled the billing "
                f"cgroup {(after or 0) - (before or 0)} times during this set "
                "(0 would mean the quota was written and nothing joined it)"
            )

    take("IDLE ①  — nothing else running")
    loaded(f"UNDER LOAD — {args.runs} run(s), NO CPU LIMIT (today's deployment)", None)
    take("IDLE ②  — between the two loaded sets")
    loaded(f"UNDER LOAD — {args.runs} run(s), CAPPED AT {args.cpus} CPU", args.cpus)
    take("IDLE ③  — after everything drained")

    idle_labels = [one for one in sets if one.startswith("IDLE")]
    uncapped = next(one for one in sets if "NO CPU LIMIT" in one)
    capped = next(one for one in sets if "CAPPED" in one)
    screens = list(sets[uncapped])

    print("\n" + "=" * 104)
    print("THE ANSWER THE RULING ASKS FOR — p95 in milliseconds")
    print("=" * 104)
    header = (
        f"{'screen':<28}{'idle ①':>10}{'idle ②':>10}{'idle ③':>10}"
        f"{'uncapped':>11}{'x bracket':>11}{'capped':>10}{'x bracket':>11}"
    )
    print(header)
    for name in screens:
        idle = [_p(sets[label].get(name, []), 0.95) for label in idle_labels]
        # ⚠ EACH LOADED SET IS DIVIDED BY THE MEAN OF THE TWO IDLE SETS TAKEN
        # EITHER SIDE OF IT, AND NOT BY A SINGLE SHARED BASELINE. The first
        # draft of this table used idle ① for both columns and printed the
        # CAPPED set at 0.86x — "faster than idle", which is nonsense and reads
        # like a triumph. It was not a lie about the cap; it was the machine's
        # own foreign load falling by 1.37x between the two loaded sets, and a
        # shared baseline silently credits that drift to whichever column comes
        # later. A ratio whose value depends on measurement ORDER is the shape
        # DEF-182 describes: an output that cannot distinguish the thing being
        # measured from the conditions it was measured in.
        hot, cool = (
            _p(sets[uncapped].get(name, []), 0.95),
            _p(sets[capped].get(name, []), 0.95),
        )
        hot_base = sum(idle[0:2]) / 2 if len(idle) >= 2 else (idle[0] if idle else 0)
        cool_base = sum(idle[1:3]) / 2 if len(idle) >= 3 else hot_base
        row = f"  {name:<26}" + "".join(f"{one:>10.1f}" for one in idle)
        row += f"{hot:>11.1f}{hot / hot_base if hot_base else 0:>10.2f}x"
        row += f"{cool:>10.1f}{cool / cool_base if cool_base else 0:>10.2f}x"
        print(row)
    print(
        "\n'x bracket' is each loaded set divided by the MEAN of the two idle sets "
        "taken either side of it — uncapped against idle ①+②, capped against idle "
        "②+③. Read the three idle columns first: if they disagree, the machine "
        "moved during the run, and the size of that disagreement is the size of "
        "the doubt in everything else. Task 28's realistic case had a second idle "
        "set 1.55x the first, which is why it reported a range and not a point."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
