#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defects:  DEF-MET-8106 (a 480-reading post runs in the request and is killed
#           at 60 s after the readings are saved) · DEF-MET-8107 (~52 SQL
#           statements per posted reading) · DEF-MET-8108 (the monthly-usage
#           rebuild in the request, cut part-way with no record)
# Ruling:   PO 2026-09-30, decision log "READS UPLOAD 500 ON 480 READINGS" —
#           all four fixes (A-D) go; the bar for the background post is set
#           from a measurement, as the asset lane did in DEF-AST-8103.
# Rules:    BR-MET-055 (the post as a background job with progress) · CLAUDE.md
#           law 14 (measure on PostgreSQL, never SQLite) · law 7 (a check that
#           reports zero over a scope it excludes is no check — statements are
#           counted with an execute wrapper, never CaptureQueriesContext)
# ───────────────────────────────────────────────────────
"""Read-batch POST cost on PostgreSQL — seconds and statements per reading.

Modelled on `def_ast_8103_upload_cost.py` (the asset lane's), which answers the
same question for asset uploads.

TWO MODES
---------
``--seed N`` writes a PERSISTENT fixture of N occupied units, each with one
electric meter and one active account, through the product's own services
(the same helpers the reads tests use). Meter numbers are ``RP-00001`` … so a
re-run tops the fixture up rather than doubling it. It is the only mode that
writes, and it writes nothing a clerk would mistake for a real customer.

``--rows 100 480 1000`` (the default) MEASURES. Each pass stages a file of that
many readings against the fixture's meters, validates it, and posts it — all
inside ONE transaction that is rolled back, so nothing is left behind and the
next pass starts from the same database. The post's async bar is raised for the
pass so the POST BODY is timed in-process rather than a deferral, and the
monthly-usage rebuild is timed as a separate column (``usage s``) whichever
way the code under test runs it.

WHAT WOULD MAKE THIS PASS WRONGLY — each answered rather than assumed:
  * **Posting nothing.** A post that holds every row is fast and means nothing,
    so a pass whose ``posted_reads`` differs from its row count EXITS by name.
  * **Counting a truncated log.** ``CaptureQueriesContext`` keeps the last
    9,000 queries only; the asset lane's first run reported 0 statements per
    row that way. Statements are counted with ``connection.execute_wrapper``.
  * **Measuring on SQLite.** ``DATABASE_URL`` must name PostgreSQL, and the
    script refuses anything else.

USAGE (a throwaway cluster, migrated and ``seed_demo``'d):
    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL=postgres://postgres@127.0.0.1:55517/sbh_dev \\
    python3 10-scripts/def_met_8106_read_post_cost.py --seed 1000
    python3 10-scripts/def_met_8106_read_post_cost.py --rows 100 480 1000
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import connection, transaction  # noqa: E402

settings.IMPORT_PROGRESS_ISOLATED = False

from apps.assets import models as asset_models  # noqa: E402
from apps.identity import models as identity_models  # noqa: E402
from apps.metering import services  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

GUNICORN_TIMEOUT_S = 60.0
PREFIX = "RP-"
HEADER = "meter_id,read_date,reading,channel,service,flags\n"


class _Rollback(Exception):
    def __init__(self, figures: dict[str, float]) -> None:
        super().__init__("measured — rolling back")
        self.figures = figures


def _meter_numbers(limit: int | None = None) -> list[str]:
    qs = (
        asset_models.Asset.objects.filter(asset_no__startswith=PREFIX)
        .order_by("asset_no")
        .values_list("asset_no", flat=True)
    )
    return list(qs[:limit] if limit else qs)


def seed(actor, tenant, wanted: int) -> None:
    """Top the fixture up to `wanted` occupied, metered units."""
    from apps.customers import services as customers_services
    from apps.metering import services as metering_services
    from apps.rating import models as rating_models

    from tests import identity_fixtures
    from tests.test_us_met_reads_helpers import a_meter, make_premises, make_unit, seed_config

    seed_config()
    have = len(_meter_numbers())
    if have >= wanted:
        print(f"fixture already holds {have} meters")
        return
    service = tenancy_models.Service.objects.get(code="electric")
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name="Read post bench",
        defaults={"code": "read-post-bench", "status": "published"},
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name="Read post bench — electric", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    premises = make_premises(actor, address_line="900 Bench Row", services_available=["electric"])
    started = time.perf_counter()
    for n in range(have + 1, wanted + 1):
        with transaction.atomic():
            unit = make_unit(actor, premises["id"], label=f"Bench {n:05d}", services=["electric"])
            metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(plan.id)})
            metering_services.ensure_service_point(unit["id"], "electric")
            account = customers_services.create_account(
                actor,
                {
                    "unit_id": unit["id"],
                    "account_type": "residential",
                    "opened_at": "2024-01-05",
                    "contact": {"full_name": f"Bench {n}", "email": f"bench{n}@example.test"},
                    "customer": identity_fixtures.customer_block(
                        f"Bench Customer {n}", account_type="residential"
                    ),
                },
            )
            customers_services.activate_account(actor, account["id"])
            a_meter(actor, f"{PREFIX}{n:05d}", unit_id=unit["id"])
        if n % 50 == 0:
            print(f"  {n} / {wanted} seeded ({time.perf_counter() - started:.0f}s)", flush=True)


#: `--profile`: the post's statements grouped by their SQL shape, so a per-row
#: lookup shows as one line with a count of N rather than as a total.
PROFILE: Counter[str] | None = None
#: True while the monthly-usage rebuild runs, so the profile is the POST's own
#: statements whichever side of the change is being measured.
_IN_USAGE = [False]


def _shape(sql: str) -> str:
    head = " ".join(sql.split())
    if head.upper().startswith(("SAVEPOINT", "RELEASE SAVEPOINT", "ROLLBACK TO SAVEPOINT")):
        return head.split(' "', 1)[0]  # one line per verb, not one per savepoint name
    table = re.search(r'(?:FROM|INTO|UPDATE)\s+"?(\w+)"?', head)
    verb = head.split(" ", 1)[0]
    return f"{verb:<9} {table.group(1) if table else '?':<34} {head[:90]}"


def _counted(fn, *, profile: bool = False):
    count = [0]

    def _count(execute, sql, params, many, context):
        count[0] += 1
        if profile and PROFILE is not None and not _IN_USAGE[0]:
            PROFILE[_shape(sql)] += 1
        return execute(sql, params, many, context)

    with connection.execute_wrapper(_count):
        started = time.perf_counter()
        result = fn()
        elapsed = time.perf_counter() - started
    return result, elapsed, count[0]


def one_pass(actor, rows: int) -> dict[str, float]:
    meters = _meter_numbers(rows)
    if len(meters) < rows:
        sys.exit(f"fixture holds {len(meters)} meters; run --seed {rows} first")
    body = HEADER + "".join(f"{m},2026-08-03,{1000 + i},total,E,\n" for i, m in enumerate(meters))
    bar_name = "READ_POST_ASYNC_ROW_BAR"
    original_bar = getattr(services, bar_name, None)
    usage_timer: dict[str, float] = {"s": 0.0, "q": 0}
    original_refresh = services._refresh_monthly_usage

    def _timed_refresh(*args, **kwargs):
        # The rebuild's own cost, measured whichever way the code under test
        # runs it — inside the post (base) or as its own job (the fix).
        _IN_USAGE[0] = True
        try:
            report, elapsed, count = _counted(lambda: original_refresh(*args, **kwargs))
        finally:
            _IN_USAGE[0] = False
        usage_timer["s"] += elapsed
        usage_timer["q"] += count
        return report

    figures: dict[str, float] = {}
    # A job enqueued by the post is RECORDED here rather than handed to a
    # broker: a box with no Redis spends seconds retrying the connection, and
    # that is not the post's cost. The rebuild job is then run below, in-process.
    from core import jobs as core_jobs

    from apps.tenancy import services as tenancy_services

    captured: list[dict] = []
    core_jobs.set_job_dispatcher(captured.append)
    try:
        with transaction.atomic():
            if original_bar is not None:
                setattr(services, bar_name, rows + 1)
            services._refresh_monthly_usage = _timed_refresh
            staged, figures["stage_s"], _ = _counted(
                lambda: services.stage_read_batch(
                    actor,
                    {
                        "source_kind": "csv",
                        "source_detail": "walk_by",
                        "period_month": "2026-08-01",
                        "file_name": f"bench_{rows}.csv",
                        "file_content": body,
                    },
                )
            )
            _, figures["validate_s"], _ = _counted(
                lambda: services.validate_read_batch(actor, staged["id"])
            )
            result, figures["post_s"], figures["post_q"] = _counted(
                lambda: services.commit_read_batch(actor, staged["id"], {"certified": True}),
                profile=True,
            )
            # What the rebuild cost INSIDE the request (the base runs it there;
            # the fix does not), so the per-reading figure is the post's own.
            figures["usage_in_request_q"] = usage_timer["q"]
            # A deferred rebuild (the fix) is run here, inside the pass, so the
            # rebuild is timed on both sides of the change.
            usage_job = result.get("usage_refresh_job_id")
            if usage_job:
                tenant_id = core_tenancy.current_tenant_id()
                core_jobs.run_pending(usage_job)
                # `run_job` clears the tenant it entered; the pass goes on.
                core_tenancy.set_current_tenant(tenant_id)
            figures["usage_s"] = usage_timer["s"]
            figures["usage_q"] = usage_timer["q"]
            if result.get("posted_reads") != rows:
                sys.exit(
                    f"expected {rows} posted, got {result.get('posted_reads')} "
                    f"(held {result.get('held_reads')}: {result.get('held_rows', [])[:2]}) — "
                    "a post that holds its rows measures nothing"
                )
            raise _Rollback(figures)
    except _Rollback as done:
        figures = done.figures
    finally:
        core_jobs.set_job_dispatcher(tenancy_services.dispatch_job)
        services._refresh_monthly_usage = original_refresh
        if original_bar is not None:
            setattr(services, bar_name, original_bar)
    return figures


def progress_proof(actor, rows: int, day: str = "2026-09-03") -> int:
    """⚠ WRITES. Post `rows` readings as a REAL deferred job and watch the
    job's progress from a THIRD connection while the post's one transaction is
    still open — the thing `import_progress.write_job_progress` exists for, and
    the one thing the suite cannot show (its job row is uncommitted, so no
    second connection can see it). Readings are left posted on `day` (one day per proof run: a second run on the same day meets its own readings as duplicates).

    What would make this pass wrongly: a gauge that only jumps 0 → N at the
    end. So the proof is an INTERMEDIATE value seen while the job still says
    `running`; `0 < done < total` or it fails by name."""
    import threading

    from django.db import connections

    from core import jobs as core_jobs

    from apps.tenancy import services as tenancy_services

    settings.IMPORT_PROGRESS_ISOLATED = True
    meters = _meter_numbers(rows)
    body = HEADER + "".join(f"{m},{day},{9000 + i},total,E,\n" for i, m in enumerate(meters))
    staged = services.stage_read_batch(
        actor,
        {"source_kind": "csv", "source_detail": "walk_by", "period_month": "2026-09-01",
         "file_name": f"proof_{rows}.csv", "file_content": body},
    )  # fmt: skip
    services.validate_read_batch(actor, staged["id"])
    tenant_id = str(core_tenancy.current_tenant_id())
    captured: list[dict] = []
    core_jobs.set_job_dispatcher(captured.append)
    # THIS PROCESS is the worker (it runs the job below), so the "is anything
    # listening?" probe — which rightly refuses on a box with no broker — is
    # answered for it.
    core_jobs.dispatch_is_ready = lambda *a, **k: (True, "this script runs the job")
    try:
        answer = services.commit_read_batch(actor, staged["id"], {"certified": True})
    finally:
        core_jobs.set_job_dispatcher(tenancy_services.dispatch_job)
    if not answer.get("deferred"):
        sys.exit(f"{rows} rows did not defer — the bar is {services.READ_POST_ASYNC_ROW_BAR}")
    seen: list[tuple[str, object]] = []
    stop = threading.Event()

    def _watch() -> None:
        watcher = connections.create_connection("default")
        with watcher.cursor() as cursor:
            cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [tenant_id])
            while not stop.is_set():
                cursor.execute(
                    "SELECT status, progress FROM jobs WHERE id = %s", [answer["job_id"]]
                )
                row = cursor.fetchone()
                if row and (not seen or seen[-1] != (row[0], row[1])):
                    seen.append((row[0], row[1]))
                time.sleep(0.2)
        watcher.close()

    thread = threading.Thread(target=_watch)
    thread.start()
    started = time.perf_counter()
    core_jobs.set_job_dispatcher(captured.append)  # the rebuild job it queues
    try:
        core_jobs.run_pending(answer["job_id"])
    finally:
        core_jobs.set_job_dispatcher(tenancy_services.dispatch_job)
        stop.set()
        thread.join()
    print(f"deferred post of {rows} readings ran in {time.perf_counter() - started:.2f}s")
    for status, progress in seen:
        print(f"  seen from a third connection: {status:9} {progress}")
    import json

    def _done(progress: object) -> int:
        # A raw cursor may hand `jsonb` back as text; read both.
        value = json.loads(progress) if isinstance(progress, str) else progress
        return int((value or {}).get("done") or 0) if isinstance(value, dict) else 0

    middle = [p for s, p in seen if s == "running" and 0 < _done(p) < rows]
    if not middle:
        print("FAIL: no intermediate progress was visible while the post ran")
        return 1
    print(f"PASS: {len(middle)} intermediate reading(s) of the gauge while the post ran")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, nargs="+", default=[100, 480, 1000])
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--progress-proof",
        type=int,
        default=0,
        help="WRITES: post this many readings as a real job and watch its gauge",
    )
    parser.add_argument(
        "--proof-day", default="2026-09-03", help="the read date the progress proof posts on"
    )
    parser.add_argument(
        "--profile", action="store_true", help="print the post's statements grouped by shape"
    )
    args = parser.parse_args()
    global PROFILE
    if args.profile:
        PROFILE = Counter()
    if connection.vendor != "postgresql":
        sys.exit(f"this measures PostgreSQL; DATABASE_URL points at {connection.vendor}")
    tenant = tenancy_models.Tenant.objects.order_by("created_at").first()
    if tenant is None:
        sys.exit("no tenant — run `manage.py seed_demo` first")
    user = identity_models.User.objects.filter(tenant_id=tenant.id).order_by("created_at").first()
    actor = SimpleNamespace(id=user.id, pk=user.id, role="system_admin", user=user)
    with core_tenancy.tenant_context(tenant.id):
        if args.seed:
            seed(actor, tenant, args.seed)
            return 0
        if args.progress_proof:
            return progress_proof(actor, args.progress_proof, args.proof_day)
        results = {rows: one_pass(actor, rows) for rows in args.rows}
    print(
        "\n  rows | stage s | validate s | post request s | post stmt/read | "
        "usage s (where) | usage stmt | request vs 60 s"
    )
    for rows, f in results.items():
        own_q = f["post_q"] - f["usage_in_request_q"]
        where = "request" if f["usage_in_request_q"] else "job"
        print(
            f"  {rows:>4} | {f['stage_s']:7.2f} | {f['validate_s']:10.2f} | "
            f"{f['post_s']:14.2f} | {own_q / rows:14.1f} | "
            f"{f['usage_s']:7.2f} ({where:7}) | {f['usage_q']:10.0f} | "
            f"{'inside' if f['post_s'] < GUNICORN_TIMEOUT_S else 'OVER'}"
        )
    if PROFILE is not None:
        total_rows = sum(args.rows)
        print(f"\n  post statements by shape (all passes, {total_rows} readings):")
        for shape, count in PROFILE.most_common(30):
            print(f"  {count:>7}  {count / total_rows:6.2f}/read  {shape}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
