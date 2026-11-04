#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: what a CLERK feels while bill runs are in flight — the measurement
#            behind CR-051 task 28.
# Change:   CR-051 task 28 (PO 2026-08-31), verbatim: *"will it hamper live
#           system performance"*. This is the only one of the PO's three
#           questions a customer actually feels.
# Rules:    CLAUDE.md rule 1 (every read inside tenant_context, on a connection
#           SUBJECT to RLS — DEF-2717) · A11 pagination (a list is a PAGE, and
#           the page is taken in the database)
# ───────────────────────────────────────────────────────
"""Time three screens a clerk waits on, idle and while the runs are going.

WHY THESE THREE SCREENS
-----------------------
The CR asks for *three interactive screens a clerk really waits on*, so they
are chosen for what a person does with them and not for what is quick to time:

* **the accounts list with a filter** (`GET /accounts?f.status=active`) — the
  screen a clerk opens first every morning, and the one that reads the same
  `accounts` table the run is walking;
* **one account's detail** (`GET /accounts/{id}`) — the single-row read behind
  every customer call, and the one where a lock wait would be felt as a stall;
* **one bill** (`GET /invoices/{id}`) — a read of `invoices` and
  `invoice_lines`, which are the two tables a bill run is WRITING while this
  is happening. If anything is going to contend, it is this one;
* **the bill run's own findings screen** (`GET /billing/runs/{id}/findings`) —
  added because a sibling lane measured it at **20.6 seconds for 47 accounts,
  438 ms an account**, on an IDLE system. A screen that already takes twenty
  seconds with nothing else running does not need concurrent load to be a
  problem, and measuring a screen that is already at the edge of a person's
  patience says more than measuring three fast ones. It is timed at the same
  account counts as everything else so the two sets can be read together.

  ⚠ **IT IS THE PREPARE PASS, WHOLE, ON A GET.** `selectors.findings_dict`
  calls `prepared_for(run)` and then builds a body, so it pays for the entire
  pass every time a clerk refreshes — and CR-051's own measured note says so:
  *"re-runs the whole prepare pass over every account in the cycle, on a GET a
  clerk can refresh"*. That also answers whether task 22's memo helps it: it is
  the same pass, so it already does. It is timed LAST because it is by far the
  slowest and a fixed sample count on it would dominate the run.

WHAT IS REPORTED, AND WHY p95 AND NOT AN AVERAGE
------------------------------------------------
p50 and p95 over N samples, idle and under load and **idle again**, with the
ratio. The third set is not a formality: five other lanes share these four
cores, and an idle-then-loaded pair taken twenty minutes apart on a machine
whose own load moved is a measurement of the machine. Two idle sets bracketing
the loaded one settle it — agree and the middle figure is attributable, disagree
and it is not. An average
hides the case that matters: a clerk does not notice a screen that is 8 ms
slower on average, they notice the one click in twenty that takes four seconds.
p95 is where that lives. The MAXIMUM is printed beside it because with a few
hundred samples p95 is an estimate and the worst case is a fact.

⚠ **THIS TIMES THE SERVER'S WORK, NOT A BROWSER.** It calls the API view
functions in-process with a request factory, so what it measures is the query
and serialization time a gunicorn worker would spend — not network, not React,
not the round trip. That is the right half to measure for *"does a bill run
hamper the live system"*, because the bill run cannot affect the other half.
Stated here rather than left for a reader to assume.

USAGE
    # in one shell, start the load:
    python3 10-scripts/cr051_concurrency_benchmark.py --tenants 10 --mode all --keep
    # in another, while it runs:
    python3 10-scripts/cr051_screen_latency.py --samples 200 --label "under load"

    # or let this script do both:
    python3 10-scripts/cr051_screen_latency.py --with-load 10
"""

from __future__ import annotations

import argparse
import multiprocessing
import os
import statistics
import sys
import threading
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
from apps.customers import models as customer_models  # noqa: E402
from apps.customers import selectors as customer_selectors  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

from cr051_provision_utilities import PREFIX  # noqa: E402


def _screens(tenant):
    """`{name: callable}` — the three reads, resolved for THIS tenant.

    They call the SELECTORS the API views call rather than the views
    themselves: a view needs an authenticated request, a role and a paginator,
    and wiring those up here would time the test harness. The database work —
    which is the only half a bill run can affect — is identical.
    """
    from apps.billing import selectors as billing_selectors
    from core.pagination import parse_list_params

    account = customer_models.Account.objects.order_by("account_no").first()
    invoice = (
        billing_models.Invoice.objects.order_by("-created_at").first()
        if billing_models.Invoice.objects.exists()
        else None
    )

    def accounts_list():
        params = parse_list_params(
            {"f.status": "active", "page_size": "50"},
            allowed_sorts=customer_selectors.ACCOUNT_SORTS,
            default_sort=customer_selectors.ACCOUNT_DEFAULT_SORT,
            allowed_filters=customer_selectors.ACCOUNT_FILTERS,
        )
        rows = customer_selectors.account_list(params)
        return len(rows[:50]) if hasattr(rows, "__getitem__") else 0

    def account_detail():
        return customer_selectors.account_detail(str(account.id)) if account else None

    def bill_detail():
        return billing_selectors.invoice_detail(str(invoice.id)) if invoice else None

    run = (
        billing_models.BillRun.objects.filter(cycle__isnull=False)
        .order_by("-created_at")
        .first()
    )

    def findings():
        return billing_selectors.findings_dict(run) if run else None

    screens = {"accounts list (filtered)": accounts_list}
    if account is not None:
        screens["one account's detail"] = account_detail
    if invoice is not None:
        screens["one bill"] = bill_detail
    if run is not None:
        # LAST, and with its own smaller sample count — see the module
        # docstring. At 438 ms an account a hundred samples of this is an hour.
        screens["the run's findings screen"] = findings
    return screens


def measure(tenant, samples: int) -> dict[str, list[float]]:
    timings: dict[str, list[float]] = {}
    with core_tenancy.tenant_context(str(tenant.id)):
        screens = _screens(tenant)
        for name, call in screens.items():
            values: list[float] = []
            # The findings screen is ~400x the others. A fixed sample count
            # would spend the whole measurement on one screen and report the
            # other three from a sample so small its p95 means nothing.
            wanted = max(3, samples // 40) if "findings" in name else samples
            for _ in range(wanted):
                started = time.perf_counter()
                try:
                    call()
                except Exception as problem:  # noqa: BLE001 — a failure is a result
                    values.append(float("nan"))
                    print(f"  {name}: {type(problem).__name__}: {problem}")
                    break
                values.append((time.perf_counter() - started) * 1000)
            timings[name] = values
    return timings


def _percentile(values: list[float], share: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(share * (len(ordered) - 1))))
    return ordered[index]


def report(
    label: str, timings: dict[str, list[float]], baseline: dict | None = None
) -> None:
    print(f"\n── {label} ──")
    print(f"  {'screen':<28} {'n':>5} {'p50':>9} {'p95':>9} {'max':>9}", end="")
    print(f" {'p50 x':>7} {'p95 x':>7}" if baseline else "")
    for name, values in timings.items():
        clean = [one for one in values if one == one]  # drop NaN
        p50, p95 = _percentile(clean, 0.50), _percentile(clean, 0.95)
        worst = max(clean) if clean else 0.0
        line = (
            f"  {name:<28} {len(clean):>5} {p50:>8.1f}ms {p95:>8.1f}ms {worst:>8.1f}ms"
        )
        if baseline and name in baseline:
            base = [one for one in baseline[name] if one == one]
            base50, base95 = _percentile(base, 0.50), _percentile(base, 0.95)
            line += (
                f" {p50 / base50 if base50 else 0:>6.2f}x"
                f" {p95 / base95 if base95 else 0:>6.2f}x"
            )
        print(line)
    if timings:
        every = [one for values in timings.values() for one in values if one == one]
        if every:
            print(
                f"  all screens together: mean {statistics.fmean(every):.1f}ms, n={len(every)}"
            )


class _SustainedLoad:
    """N bill runs in flight for as long as the measurement lasts.

    ⚠ **THIS CLASS EXISTS BECAUSE THE FIRST VERSION OF THIS HARNESS MEASURED
    THREE OF ITS FOUR SCREENS AGAINST A MACHINE THAT HAD GONE QUIET.** Ten runs
    fired at once drain in about 167 seconds; the accounts list alone, at 200
    samples and ~600 ms each, takes longer than that. The screens timed later in
    the pass were therefore timed with no load at all, and **nothing in the
    output said so** — the table still said UNDER LOAD. A measurement whose
    conditions end half way through is worse than no measurement, because it is
    reported with the same confidence.

    So a supervisor thread relaunches any run that finishes. The load is a
    STATE, not an event, and it is torn down explicitly when the timing stops.
    """

    def __init__(self, subdomains: list[str]) -> None:
        self.subdomains = subdomains
        self.children: dict = {}
        self.launched = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _spawn(self, subdomain: str):
        import cr051_concurrency_benchmark as concurrency

        context = multiprocessing.get_context("fork")
        child = context.Process(target=concurrency._one_run, args=(subdomain, "/tmp"))
        child.start()
        self.launched += 1
        return child

    def start(self) -> None:
        for subdomain in self.subdomains:
            self.children[subdomain] = self._spawn(subdomain)

        def supervise() -> None:
            while not self._stop.is_set():
                for subdomain, child in list(self.children.items()):
                    if not child.is_alive():
                        child.join()
                        if not self._stop.is_set():
                            self.children[subdomain] = self._spawn(subdomain)
                self._stop.wait(1.0)

        self._thread = threading.Thread(target=supervise, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop relaunching, then let the runs in flight finish normally.

        They are NOT killed: a bill run halfway through its accounts has
        committed some of them, and killing it would leave the benchmark
        database in a state the next measurement would have to reason about.
        """
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        for child in self.children.values():
            child.join()


def _load(subdomains: list[str]) -> list:
    """One burst of bill runs — the un-sustained form, kept for `--sustain 0`."""
    import cr051_concurrency_benchmark as concurrency

    context = multiprocessing.get_context("fork")
    out_dir = "/tmp"
    children = []
    for subdomain in subdomains:
        child = context.Process(target=concurrency._one_run, args=(subdomain, out_dir))
        child.start()
        children.append(child)
    return children


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=200)
    parser.add_argument("--label", default=None)
    parser.add_argument(
        "--with-load",
        type=int,
        default=0,
        metavar="N",
        help="start N utilities' bill runs first, then time the screens against them",
    )
    parser.add_argument(
        "--tenant", default=None, help="subdomain to time; default is the oldest"
    )
    parser.add_argument(
        "--sustain",
        type=int,
        default=1,
        help="1 (default): keep N runs in flight for the WHOLE measurement, "
        "relaunching any that finish. 0: one burst, which measures the later "
        "screens against a machine that has already gone quiet.",
    )
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
            "REFUSING: this role bypasses row-level security, so the screens would be "
            "timed without the tenant predicate every real request pays for "
            "(DEF-2717, CLAUDE.md hard rule 1)."
        )

    tenants = tenancy_models.Tenant.objects.order_by("created_at")
    tenant = (
        tenants.filter(subdomain=args.tenant).first()
        if args.tenant
        else tenants.first()
    )
    if tenant is None:
        sys.exit("no tenant in this database")
    print(f"timing {tenant.subdomain}'s screens · {args.samples} samples each")

    if not args.with_load:
        report(args.label or "as measured", measure(tenant, args.samples))
        return 0

    idle = measure(tenant, args.samples)
    report("IDLE — nothing else running", idle)

    available = [
        one.subdomain
        for one in tenancy_models.Tenant.objects.filter(
            subdomain__startswith=PREFIX
        ).order_by("subdomain")
    ][: args.with_load]
    if len(available) < args.with_load:
        sys.exit(
            f"only {len(available)} perf utilities exist — run "
            "10-scripts/cr051_provision_utilities.py first"
        )
    print(f"\nstarting {len(available)} bill runs…")
    sustained = None
    children: list = []
    if args.sustain:
        sustained = _SustainedLoad(available)
        sustained.start()
    else:
        children = _load(available)
    time.sleep(3)  # let them get past their own setup and into the walk
    under = measure(tenant, args.samples)
    if sustained is not None:
        print(
            f"  the load was SUSTAINED: {sustained.launched} run(s) were started to keep "
            f"{len(available)} in flight for the whole measurement"
        )
        sustained.stop()
        children = []
    report(f"UNDER LOAD — {len(available)} bill runs in flight", under, baseline=idle)

    # ⚠ **THE SECOND IDLE SET IS WHAT MAKES THE FIRST COMPARISON READABLE.**
    # Five other lanes share these four cores. If the machine's own background
    # load moved between the idle run and the loaded one, the ratio above is a
    # measurement of the machine and not of the bill run — and NOTHING in the
    # numbers would say so. Bracketing the loaded set with two idle sets does
    # say so: when the two idle sets agree, the middle figure is attributable;
    # when they disagree, it is not, and the report must say which.
    still = [child for child in children if child.is_alive()]
    if still:
        print(
            f"\nwaiting for {len(still)} bill run(s) to finish before re-measuring idle…"
        )
        for child in children:
            child.join()
    after = measure(tenant, args.samples)
    report("IDLE AGAIN — the load has drained", after, baseline=idle)
    print(
        "\n  READ THE TWO IDLE SETS AGAINST EACH OTHER FIRST. They bracket the loaded\n"
        "  one; if they disagree, this machine moved underneath the measurement and the\n"
        "  middle figure cannot be attributed to the bill runs."
    )
    print(
        "\n  the load processes' drafts are NOT cleaned up by this script. Run\n"
        "  cr051_concurrency_benchmark.py without --keep to sweep, or drop the\n"
        "  benchmark database."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
