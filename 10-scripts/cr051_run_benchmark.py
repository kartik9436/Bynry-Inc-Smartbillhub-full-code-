#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: the bill run at 100, 1,000 and 10,000 accounts — THE MEASUREMENT,
#            run against real PostgreSQL with the real prepare and calculate
#            passes and rolled back after.
# Change:   CR-051 task 21 (PO 2026-08-30) — *"Measure the run at 100, 1,000
#           and 10,000 accounts on a real database; publish the figures."* The
#           CR states the gap in as many words: *"There is no timing figure for
#           a bill run of any size anywhere in this repo."* Its sibling, the
#           premises import, set its 5,000-row worker bar from
#           10-scripts/cr026_import_benchmark.py rather than from an opinion;
#           this is that script's shape, pointed at billing.
# Rules:    BR-BIL-039 (stages 1-5 are pure; `gather` is the only reader) ·
#           BR-BIL-051/052 (phase 2 is a background, resumable batch) ·
#           BR-BIL-023 (stage 6 REPLACES a draft) · CLAUDE.md rule 1 (tenant
#           scoping — every pass runs inside `tenant_context`)
# Tests:    none, deliberately — see "WHY THIS IS A SCRIPT AND NOT A TEST".
#           The ratified figure this produces is asserted by
#           06-backend/tests/test_cr051_run_scale.py.
# Impacts:  12-governance/02-decision-log.md (the published figures) ·
#           CR-051 tasks 22 and 23, which are sized against them
# ───────────────────────────────────────────────────────
"""How long does a bill run actually take at 100, 1,000 and 10,000 accounts?

WHY THIS IS A SCRIPT AND NOT A TEST. Its figures are the input to a DESIGN
DECISION — whether the plural seams of CR-051 task 22 and the bulk write of
task 23 are worth building, and by how much — not an assertion about behaviour.
A twenty-minute case in a suite that runs on every commit would be paid for by
every lane, for ever, to re-learn a number that changes only when the engine
does. This is verbatim the reasoning `cr026_import_benchmark.py` records, and
it applies here for the same reason.

IT WRITES NOTHING. Every pass runs inside one transaction that is rolled back
at the end, so a 10,000-account run can be measured against a live database
without leaving 10,000 accounts behind. Nothing is committed, so nothing needs
cleaning up, and the script may be run as often as it is useful.

── WHAT IS MEASURED, AND WHAT THE THREE NUMBERS MEAN ────────────────────────

Three passes, because a clerk waits on three different things:

* **prepare** — `runs.prepare_run` — phase 1. It is what
  `GET /billing/runs/{id}/findings` re-runs on every refresh and what
  `POST .../calculate` runs before it drafts anything. This is the pass that
  opens the 23 named cross-module reads through 8 seams that CR-051 counts,
  once per account.
* **calculate** — `runs.calculate_run` over the prepared set — phase 2. One
  transaction per account (BR-BIL-052), the stages, and stage 6's writes:
  one invoice and its lines per account.
* **total** — the two together, which is what `POST .../calculate` costs and
  therefore what a clerk was held at the screen for before CR-051 task 8.

The write half is reported separately as invoice LINES per second, because
that is the figure CR-051 task 23 (bulk-write invoice lines) is sized against.

── HOW THE POPULATION IS BUILT, AND WHY IT IS A CLONE ───────────────────────

The demo tenant has 48 units in its largest cycle. 10,000 accounts do not
exist anywhere and seeding them through the real service layer would take
longer than the measurement.

So this CLONES the accounts the run already finds ready — unit, service
points, meters, meter reads, account, service agreements — round-robin, until
the cycle holds N. That keeps the priced world entirely real: the plans, the
rate schedules, the tax rules, the charge codes and the jurisdiction are the
seeded tenant's own, resolved through the same seams, and the mix of readings
per account is the seeded mix repeated. What is synthetic is the POPULATION
COUNT, which is the one variable being measured.

⚠ **A CLONE IS NOT A FIXTURE.** The demo-fixture rule — *"seed through the
services a clerk's click uses, never by writing rows directly"* — exists so a
fixture proves the product works. This proves nothing about the product and
must never be used as one: it writes rows directly, it is rolled back, and it
would be wrong to reach for it to populate anything.

── FINDING THE EIGHT SEAMS (CR-051 task 22 · `--seams`) ─────────────────────

`--seams` runs one prepare pass and prints, per named cross-module read, how
many times the pass ASKED the owning module and how many times one answer
served another account. That table is the evidence for which seams have a
plural form worth building — CR-051 says *"Find the eight; do not guess at
them"*, and a list assembled by reading imports would be a guess.

USAGE
    python3 10-scripts/cr051_run_benchmark.py                 # 100, 1000, 10000
    python3 10-scripts/cr051_run_benchmark.py --sizes 100 1000
    python3 10-scripts/cr051_run_benchmark.py --no-calculate  # prepare only
    python3 10-scripts/cr051_run_benchmark.py --seams --sizes 1000

    DATABASE_URL must point at a migrated database holding a seeded tenant:
      DJANGO_SETTINGS_MODULE=config.settings.local
      DATABASE_URL=postgres://…  python3 10-scripts/cr051_run_benchmark.py
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
# The measurement runs the bodies in-process; a broker would time a queue.
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import connection, transaction  # noqa: E402

# ⚠ **DEBUG OFF, AND IT IS A MEASUREMENT DECISION.** `config.settings.local`
# sets DEBUG=True, and Django then keeps every SQL statement and its formatted
# parameters in `connection.queries`. At 10,000 accounts that is hundreds of
# thousands of strings: it warns at 9,000 (`Limit for query logging exceeded`),
# truncates the count this script would print, and charges the run for memory
# no deployment pays. Queries are counted through `execute_wrapper` below
# instead, which is exact at any size and costs one function call per statement.
settings.DEBUG = False

from apps.assets import models as asset_models  # noqa: E402
from apps.billing import models as billing_models  # noqa: E402
from apps.billing import gather, runs, seam_batch, selectors  # noqa: E402
from apps.customers import models as customer_models  # noqa: E402
from apps.metering import models as metering_models  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402
from core.dbfields import uuid7  # noqa: E402


class _Rollback(Exception):
    """Carries the figures out of the transaction that is being thrown away."""

    def __init__(self, figures: dict[str, object]) -> None:
        super().__init__("benchmark complete — rolling back")
        self.figures = figures


# ── cloning ─────────────────────────────────────────────────────────────────
def _clone(row, **overrides):
    """A new row with the same concrete field values, a fresh id and no pk.

    Field-by-field rather than `copy.copy`, so a column added tomorrow is
    carried without this script being edited — a benchmark that silently stops
    copying a column would measure a different world from the one it names.
    """
    fresh = row.__class__()
    for field in row._meta.concrete_fields:
        # ⚠ `meter_reads` has a COMPOSITE primary key `(tenant_id, read_at, id)`
        # — the table is partitioned on `read_at`. Assigning `fresh.pk = None`
        # on such a model nulls all three components, and PostgreSQL answers
        # `no partition of relation "meter_reads" found for row`. So the pk is
        # skipped rather than nulled, and `id` is set explicitly below.
        if field.primary_key:
            continue
        if getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False):
            continue
        setattr(fresh, field.attname, getattr(row, field.attname))
    fresh.id = uuid7()
    for name, value in overrides.items():
        setattr(fresh, name, value)
    fresh._state.adding = True
    return fresh


def clone_account(account, index: int) -> None:
    """One account's whole billable subtree, written directly. See the module
    docstring on why this is a clone and never a fixture."""
    tenant_id = account.tenant_id
    source_unit = metering_models.Unit.objects.get(pk=account.unit_id)
    unit = _clone(
        source_unit,
        unit_no=f"BM{index:06d}",
        label=f"BM {index}",
        external_ref=None,
    )
    unit.save(force_insert=True)

    # ⚠ THE CLONE MUST JOIN THE ROUTE, OR IT IS NOT IN THE CYCLE AT ALL.
    # `derivation.units_in_cycle` derives the population from route membership
    # and area coverage (CR-029 D4), NOT from the `service_points.cycle_id`
    # stamp. Without this the clones exist, are billable, and the run reports
    # the original 47 — which is how the first draft of this script measured
    # 100 accounts and timed 47.
    for membership in metering_models.RouteMembership.objects.filter(
        tenant_id=tenant_id, unit_id=source_unit.id
    ):
        _clone(membership, unit_id=unit.id).save(force_insert=True)

    point_map: dict[str, object] = {}
    for point in metering_models.ServicePoint.objects.filter(
        tenant_id=tenant_id, unit_id=source_unit.id, deleted_at__isnull=True
    ):
        fresh = _clone(point, unit_id=unit.id)
        fresh.save(force_insert=True)
        point_map[str(point.id)] = fresh

    # The meters on the source unit, and their current assignment, so
    # `billing_reads_for_unit` finds the same shape on the clone.
    asset_map: dict[str, object] = {}
    for assignment in asset_models.AssetAssignment.objects.filter(
        tenant_id=tenant_id, unit_id=source_unit.id, to_date__isnull=True
    ).select_related("asset"):
        asset = _clone(
            assignment.asset,
            asset_no=f"BM{index:06d}-{len(asset_map)}",
            serial_no=f"BM{index:06d}-{len(asset_map)}",
        )
        if getattr(asset, "service_point_id", None) is not None:
            replacement = point_map.get(str(assignment.asset.service_point_id))
            asset.service_point_id = None if replacement is None else replacement.id
        asset.save(force_insert=True)
        asset_map[str(assignment.asset_id)] = asset
        _clone(assignment, unit_id=unit.id, asset_id=asset.id).save(force_insert=True)

    new_account = _clone(
        account,
        unit_id=unit.id,
        account_no=f"BM-{index:06d}",
    )
    new_account.save(force_insert=True)

    for agreement in customer_models.ServiceAgreement.objects.filter(
        tenant_id=tenant_id, account_id=account.id
    ):
        replacement = point_map.get(str(agreement.service_point_id))
        if replacement is None:
            continue
        _clone(
            agreement, account_id=new_account.id, service_point_id=replacement.id
        ).save(force_insert=True)

    # The reads, last: they carry both the asset and the account.
    for read in metering_models.MeterRead.objects.filter(
        tenant_id=tenant_id, asset_id__in=list(asset_map)
    ):
        fresh = _clone(
            read,
            asset_id=asset_map[str(read.asset_id)].id,
            account_id=new_account.id,
        )
        fresh.save(force_insert=True)


# ── the passes ──────────────────────────────────────────────────────────────
#: The statement verbs CR-051 task 26 asks to be separated. The PO's question
#: was literally *"how many read and writes ahppens"*, and a TOTAL cannot
#: answer it: a SELECT is work a read replica could one day take and an INSERT
#: is work that must reach the primary, which is the engineering difference the
#: question is about.
VERBS = ("SELECT", "INSERT", "UPDATE", "DELETE", "SAVEPOINT", "RELEASE", "OTHER")


class _Counter:
    """One increment per SQL statement, classified by verb, with rows written.

    ⚠ **THIS IS THE APPLICATION'S VIEW, AND THE SCRIPT SAYS SO WHERE IT PRINTS
    THE TABLE.** `connection.execute_wrapper` sees exactly the statements
    Django SENT, which is the right denominator for *"how many reads and
    writes does one bill cost"*. `pg_stat_statements` is the other route and
    answers a different question — what the SERVER executed, planning included,
    across every connection — and this script reports it alongside rather than
    instead (`--pg-stat`), because the two disagreeing is itself information.

    `written` is `cursor.rowcount` after an INSERT, UPDATE or DELETE, so a
    `bulk_create` of eight invoice lines counts as ONE statement and EIGHT
    rows. Counting statements alone would say the run writes one row per
    account, which is the opposite of true.
    """

    __slots__ = ("count", "by_verb", "written")

    def __init__(self) -> None:
        self.count = 0
        self.by_verb = dict.fromkeys(VERBS, 0)
        self.written = 0

    @staticmethod
    def _verb(sql: str) -> str:
        head = sql.lstrip()[:9].upper()
        for verb in VERBS[:-1]:
            if head.startswith(verb):
                return verb
        return "OTHER"

    def __call__(self, execute, sql, params, many, context):
        self.count += 1
        verb = self._verb(sql if isinstance(sql, str) else str(sql))
        self.by_verb[verb] += 1
        answer = execute(sql, params, many, context)
        if verb in ("INSERT", "UPDATE", "DELETE"):
            cursor = context.get("cursor")
            rows = getattr(cursor, "rowcount", -1) if cursor is not None else -1
            # -1 is "the driver did not say", never a silent zero.
            if rows and rows > 0:
                self.written += rows
        return answer


def _timed(label: str, call):
    counter = _Counter()
    with connection.execute_wrapper(counter):
        started = time.perf_counter()
        answer = call()
        elapsed = time.perf_counter() - started
    reads = counter.by_verb["SELECT"]
    writes = (
        counter.by_verb["INSERT"]
        + counter.by_verb["UPDATE"]
        + counter.by_verb["DELETE"]
    )
    print(
        f"  {label:<12} {elapsed:9.1f}s   {counter.count:>9} SQL "
        f"({reads:,} read · {writes:,} write · {counter.written:,} rows)"
    )
    return answer, elapsed, counter


def _every_seam(cycle, window) -> dict[str, int]:
    """EVERY named cross-module read one prepare pass makes, batchable or not.

    The pre-task-22 world, measured rather than reasoned about: the allowlist
    is emptied so nothing is memoised, and `gather._resolve`'s RESULT is
    wrapped so each call is counted where it is made. CR-051 says *"Find the
    eight; do not guess at them"*, and this table is what the finding is made
    of — it names the seams the cache cannot help with as plainly as the ones
    it can, which is the half a lane would otherwise quietly leave out.

    WARNING: it wraps the RESULT of `_resolve`, never `_resolve` itself.
    Replacing `_resolve` takes `seam_batch.wrap` out of the path, so the
    "with cache" and "without cache" passes come out identical and the report
    says the cache saved nothing — which is exactly what the first draft of
    this function did, and what a first draft of its test did too.
    """
    counts: dict[str, int] = {}
    original_resolve = gather._resolve  # noqa: SLF001 - the seam resolution point
    original_list = dict(seam_batch.BATCHABLE)
    seam_batch.BATCHABLE.clear()

    def counting(module: str, attribute: str, kind: str = "selectors"):
        found = original_resolve(module, attribute, kind)
        if found is None:
            return None
        name = f"{module}.{attribute}"

        def watched(*args, **kwargs):
            counts[name] = counts.get(name, 0) + 1
            return found(*args, **kwargs)

        return watched

    gather._resolve = counting  # noqa: SLF001
    runs._resolve = counting  # noqa: SLF001
    try:
        runs.prepare_run(
            cycle_id=cycle.id,
            period_start=window[0],
            period_end=window[1],
            service_date=window[2],
        )
    finally:
        gather._resolve = original_resolve  # noqa: SLF001
        runs._resolve = original_resolve  # noqa: SLF001
        seam_batch.BATCHABLE.update(original_list)
    return counts


def _report_seams(cache, ready: int, before: dict[str, int]) -> None:
    """Which named cross-module reads a prepare pass repeats, and how badly.

    `asked` is what reached the owning module; `served` is what one answer
    covered for another account. A seam with a high `served` is one the run was
    asking the same question of, over and over — which is CR-051 task 22's
    whole subject and the reason this table exists rather than a list somebody
    assembled by reading imports.
    """
    print(f"\n  ── every named cross-module read, over {ready:,} ready accounts ──")
    print(f"  {'seam':<40} {'before':>9} {'after':>9} {'per acct':>9}")
    names = sorted(set(before) | set(cache.asked), key=lambda n: -before.get(n, 0))
    for name in names:
        was = before.get(name, 0)
        now = cache.asked.get(name, was)
        print(f"  {name:<40} {was:>9,} {now:>9,} {was / max(ready, 1):>9.1f}")
    total_before = sum(before.values())
    total_after = total_before - cache.saved()
    print(f"  {'TOTAL':<40} {total_before:>9,} {total_after:>9,}")
    print(
        f"  {'':<40} {'':>9} {'':>9}   "
        f"{cache.saved():,} calls not made "
        f"({cache.saved() * 100 / max(total_before, 1):.0f}%)"
    )


def _load_average() -> float:
    """The machine's 1-minute load average, or 0.0 where it cannot be read.

    ⚠ **IT IS PRINTED WITH EVERY FIGURE BECAUSE A WALL CLOCK IS MEANINGLESS
    WITHOUT IT.** This lane published a 10,000-account run that read SLOWER
    after an optimisation which removed a quarter of its queries; the cause was
    four other processes on the same four cores, and the only reason it was
    caught is that the query count fell exactly as predicted while the clock
    did not. A figure that carries the load it was taken under can be told from
    a regression by someone who was not in the room.

    A load average AT OR BELOW the core count means this measurement had the
    machine to itself; well above it means the number is a lower bound on how
    fast the code is and nothing more.
    """
    try:
        return os.getloadavg()[0]
    except (OSError, AttributeError):  # pragma: no cover — not Linux
        return 0.0


def one_size(
    tenant,
    cycle,
    templates,
    size: int,
    *,
    window,
    calculate: bool,
    seams: bool = False,
    findings: bool = False,
) -> dict[str, object]:
    print(f"\n── {size:,} accounts ──")
    figures: dict[str, object] = {"accounts": size}
    try:
        with transaction.atomic():
            existing = customer_models.Account.objects.filter(
                tenant_id=tenant.id, unit_id__in=[str(one.unit_id) for one in templates]
            ).count()
            started = time.perf_counter()
            for index in range(existing, size):
                clone_account(templates[index % len(templates)], index)
            print(
                f"  {'seed':<12} {time.perf_counter() - started:9.1f}s   {size - existing:>9} cloned"
            )

            run = billing_models.BillRun(
                tenant_id=tenant.id,
                cycle_id=cycle.id,
                period_start=window[0],
                period_end=window[1],
                bill_date=window[2],
                idempotency_key=f"benchmark-{size}-{uuid7()}",
                status="draft",
            )
            run.save(force_insert=True)

            # `seam_batch.pass_cache` is re-entrant, so opening one here hands
            # `prepare_run` this very object and the counters come back out —
            # which is how `--seams` reports the per-seam figures without
            # instrumenting the ORM or changing the pass being measured.
            with seam_batch.pass_cache() as cache:
                prepared, figures["prepare"], prepare_counter = _timed(
                    "prepare",
                    lambda: runs.prepare_run(
                        cycle_id=cycle.id,
                        period_start=window[0],
                        period_end=window[1],
                        service_date=window[2],
                    ),
                )
            if seams:
                _report_seams(cache, len(prepared.ready), _every_seam(cycle, window))
            figures["ready"] = len(prepared.ready)
            figures["blocked"] = len(prepared.blocked)
            if findings:
                # ⚠ THE FINDINGS SCREEN IS THE PREPARE PASS PLUS A DICT, AND
                # THAT IS THE FINDING. `selectors.findings_dict` calls
                # `prepared_for(run)` and then builds the body — so it pays the
                # WHOLE pass again, which is why it is timed here rather than
                # reasoned about. A sibling lane measured the endpoint at 20.6s
                # for 47 accounts (438 ms an account) through a real browser;
                # what this measures is the server-side half of that, so the
                # difference between the two figures IS the HTTP stack.
                _, figures["findings"], findings_counter = _timed(
                    "findings", lambda: selectors.findings_dict(run)
                )
                figures["findings_queries"] = findings_counter.count
            figures["prepare_queries"] = prepare_counter.count
            figures["prepare_by_verb"] = dict(prepare_counter.by_verb)
            figures["prepare_rows"] = prepare_counter.written
            figures["calculate_queries"] = 0
            figures["calculate_by_verb"] = dict.fromkeys(VERBS, 0)
            figures["calculate_rows"] = 0
            if calculate:
                calculated, figures["calculate"], calculate_counter = _timed(
                    "calculate",
                    lambda: runs.calculate_run(prepared, bill_run=run),
                )
                figures["calculate_queries"] = calculate_counter.count
                figures["calculate_by_verb"] = dict(calculate_counter.by_verb)
                figures["calculate_rows"] = calculate_counter.written
                figures["drafted"] = len(calculated.drafted)
                figures["breaks"] = len(calculated.breaks)
                figures["lines"] = billing_models.InvoiceLine.objects.filter(
                    tenant_id=tenant.id, invoice__bill_run_id=run.id
                ).count()
            raise _Rollback(figures)
    except _Rollback as done:
        figures = done.figures

    total = float(figures.get("prepare", 0.0)) + float(figures.get("calculate", 0.0))
    figures["total"] = total
    figures["load"] = _load_average()
    ready = int(figures.get("ready", 0)) or 1
    print(
        f"  {'TOTAL':<12} {total:9.1f}s   ({total * 1000 / ready:.0f} ms/account, "
        f"load {figures['load']:.1f} on {os.cpu_count()} cores)"
    )
    if figures.get("lines"):
        lines = int(figures["lines"])
        print(
            f"  {'lines':<12} {lines:>9}   "
            f"({lines / max(float(figures.get('calculate', 0.0)), 1e-9):.0f} lines/s written)"
        )
    return figures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    # 5,000 is in the DEFAULTS because the PO named it first and the first
    # measurement skipped it (CR-051 task 26).
    parser.add_argument(
        "--sizes", type=int, nargs="+", default=[100, 1_000, 5_000, 10_000]
    )
    parser.add_argument(
        "--no-cache",
        dest="cache",
        action="store_false",
        help="empty seam_batch.BATCHABLE for the whole run — the pre-task-22 world",
    )
    parser.add_argument("--no-calculate", dest="calculate", action="store_false")
    parser.add_argument(
        "--findings",
        action="store_true",
        help="also time GET /billing/runs/{id}/findings — the screen a clerk waits on",
    )
    parser.add_argument(
        "--seams",
        action="store_true",
        help="print the per-seam ask/serve table — CR-051 task 22's evidence",
    )
    parser.add_argument(
        "--tenant", default=None, help="subdomain; default is the oldest tenant"
    )
    args = parser.parse_args()

    if connection.vendor != "postgresql":
        sys.exit(
            "this measurement needs PostgreSQL — tenant context is a Postgres GUC "
            "and the figures would be a different database's (CLAUDE.md rule 1)."
        )

    # ⚠ **DEF-2717 — A SUPERUSER BYPASSES ROW-LEVEL SECURITY, `FORCE` INCLUDED,
    # AND NOTHING SAYS SO.** The tables still report `relrowsecurity` and
    # `relforcerowsecurity` true, the policies still exist, every query still
    # returns the right rows, and the only difference is that a predicate
    # nobody can see is not evaluated. The first run of this benchmark was
    # taken that way — the role had been made superuser twenty minutes earlier
    # to create a database — so every figure was of a bill run that never paid
    # for tenant scoping. It refuses now rather than caveating later.
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolsuper, rolbypassrls, current_user FROM pg_roles "
            "WHERE rolname = current_user"
        )
        row = cursor.fetchone()
    if row is None:
        sys.exit(
            "could not read the connection role's RLS posture — refusing to measure"
        )
    superuser, bypass, role = row
    if superuser or bypass:
        sys.exit(
            f"REFUSING: the role {role!r} is "
            f"{'a SUPERUSER' if superuser else 'BYPASSRLS'}, so row-level security is "
            "not evaluated on any query and every figure would describe a bill run "
            "that never paid for tenant scoping (DEF-2717, CLAUDE.md hard rule 1). "
            f"Fix it with: ALTER ROLE {role} NOSUPERUSER NOBYPASSRLS;"
        )
    print(
        f"role: {role} · rolsuper={superuser} · rolbypassrls={bypass} — RLS IS enforced"
    )
    tenants = tenancy_models.Tenant.objects.order_by("created_at")
    tenant = (
        tenants.filter(subdomain=args.tenant).first()
        if args.tenant
        else tenants.first()
    )
    if tenant is None:
        sys.exit("no tenant in this database — run `manage.py seed_demo` first")

    with core_tenancy.tenant_context(str(tenant.id)):
        from apps.metering import derivation

        cycle, unit_ids = None, []
        for candidate in metering_models.Cycle.objects.all():
            found = derivation.units_in_cycle(candidate.id)
            if len(found) > len(unit_ids):
                cycle, unit_ids = candidate, found
        if cycle is None or not unit_ids:
            sys.exit(f"tenant {tenant.subdomain!r} has no cycle with units in it")

        window = (
            datetime.date(2026, 7, 1),
            datetime.date(2026, 7, 31),
            datetime.date(2026, 8, 5),
        )
        templates = list(
            customer_models.Account.objects.filter(
                tenant_id=tenant.id, unit_id__in=unit_ids
            ).order_by("account_no")
        )
        print(
            f"tenant: {tenant.subdomain} · cycle {cycle.code} · "
            f"{len(unit_ids)} units · {len(templates)} template accounts · "
            f"period {window[0]}→{window[1]} priced at {window[2]}"
        )
        if not args.cache:
            # The pre-task-22 world: the same code path with nothing on the
            # memo's named list. This is the honest "before", not a missing
            # cache — `prepare_run` always opens one now.
            seam_batch.BATCHABLE.clear()
            print("--no-cache: seam_batch.BATCHABLE emptied for this whole run")
        results = [
            one_size(
                tenant,
                cycle,
                templates,
                size,
                window=window,
                calculate=args.calculate,
                seams=args.seams,
                findings=args.findings,
            )
            for size in sorted(args.sizes)
        ]

    print("\n── the figures ──")
    print(
        f"  {'accounts':>9} {'ready':>7} {'prepare':>10} {'calculate':>10} "
        f"{'total':>10} {'ms/acct':>9} {'findings':>10} {'lines':>8} "
        f"{'SQL':>10} {'load':>6}"
    )
    for row in results:
        queries = int(row.get("prepare_queries", 0)) + int(
            row.get("calculate_queries", 0)
        )
        ready = int(row.get("ready", 0)) or 1
        print(
            f"  {int(row['accounts']):>9,} {ready:>7,} "
            f"{float(row.get('prepare', 0)):9.1f}s {float(row.get('calculate', 0)):9.1f}s "
            f"{float(row['total']):9.1f}s {float(row['total']) * 1000 / ready:9.0f} "
            f"{float(row.get('findings', 0)):9.1f}s "
            f"{int(row.get('lines', 0)):>8,} {queries:>10,} "
            f"{float(row.get('load', 0)):>6.1f}"
        )

    # ── CR-051 task 26: the PO asked "how many read and writes ahppens", and a
    # TOTAL cannot answer it. Per ACCOUNT, because that is the unit a utility
    # grows in.
    print("\n── reads and writes, PER ACCOUNT (task 26) ──")
    print(
        f"  {'accounts':>9} {'SELECT':>8} {'INSERT':>8} {'UPDATE':>8} {'DELETE':>8} "
        f"{'other':>8} {'SQL':>8} {'rows written':>13}"
    )
    for row in results:
        ready = int(row.get("ready", 0)) or 1
        merged = {
            verb: int(row.get("prepare_by_verb", {}).get(verb, 0))
            + int(row.get("calculate_by_verb", {}).get(verb, 0))
            for verb in VERBS
        }
        other = merged["SAVEPOINT"] + merged["RELEASE"] + merged["OTHER"]
        total = sum(merged.values())
        rows_written = int(row.get("prepare_rows", 0)) + int(
            row.get("calculate_rows", 0)
        )
        print(
            f"  {int(row['accounts']):>9,} {merged['SELECT'] / ready:>8.1f} "
            f"{merged['INSERT'] / ready:>8.1f} {merged['UPDATE'] / ready:>8.1f} "
            f"{merged['DELETE'] / ready:>8.1f} {other / ready:>8.1f} "
            f"{total / ready:>8.1f} {rows_written / ready:>13.1f}"
        )
    print("\n── the same, as TOTALS ──")
    print(
        f"  {'accounts':>9} {'SELECT':>10} {'INSERT':>10} {'UPDATE':>10} {'DELETE':>10} "
        f"{'other':>10} {'rows written':>13}"
    )
    for row in results:
        merged = {
            verb: int(row.get("prepare_by_verb", {}).get(verb, 0))
            + int(row.get("calculate_by_verb", {}).get(verb, 0))
            for verb in VERBS
        }
        other = merged["SAVEPOINT"] + merged["RELEASE"] + merged["OTHER"]
        rows_written = int(row.get("prepare_rows", 0)) + int(
            row.get("calculate_rows", 0)
        )
        print(
            f"  {int(row['accounts']):>9,} {merged['SELECT']:>10,} {merged['INSERT']:>10,} "
            f"{merged['UPDATE']:>10,} {merged['DELETE']:>10,} {other:>10,} {rows_written:>13,}"
        )
    print(
        f"\n  `load` is the 1-minute average on {os.cpu_count()} cores AT THE END of "
        "that size.\n  At or below the core count the measurement had the machine; "
        "well above it, the\n  wall clock is a lower bound and the SQL counts are the "
        "figure to compare."
    )
    print(
        "\n  counted at the APPLICATION boundary (django's connection.execute_wrapper),\n"
        "  which is what the run SENT. `rows written` is the driver's own rowcount, so a\n"
        "  bulk_create of eight lines is ONE statement and EIGHT rows."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
