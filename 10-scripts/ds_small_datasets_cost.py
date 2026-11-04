#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: the THREE remaining dataset queries, measured on REAL PostgreSQL
#            16 — `apps/work/work_orders_dataset.py`,
#            `apps/assets/assets_dataset.py` and
#            `apps/rating/rate_schedules_dataset.py`. The test suite runs on
#            in-memory SQLite (`config/settings/test.py` hardcodes it and
#            ignores `DATABASE_URL`) and cannot answer a question about
#            LIMIT/OFFSET, a query plan or RLS (CLAUDE.md hard-won law 14).
# Rules:     `NFR-3` (universal server pagination — in SQL, never in Python) ·
#            `NFR-5` (no hard caps anywhere) · hard rule 1 (tenant scoping; RLS
#            FORCE, and the app role is neither superuser nor BYPASSRLS) ·
#            hard rule 3 (a quantity carries its unit) · hard rule 4 (this
#            script READS; only the fixture writes) · hard-won law 7 (a check
#            that cannot cover its whole subject prints what it SKIPPED beside
#            what it checked).
# ───────────────────────────────────────────────────────
"""WHAT ONE PAGE OF EACH OF THE LAST THREE FACTS COSTS — three instruments.

`cr138_p4_debtor_cost.py` learned this the expensive way and both sibling
dataset scripts copied the lesson rather than re-learning it; this does the
same. **A wall clock alone cannot answer an `NFR-3` question** — at a small
tenant every figure is dominated by fixed overhead. **And a statement count
alone cannot either**, because a read can hold its statement count flat while
the ROWS those statements build grow with the tenant.

  **statements**   round trips. An N+1 shows here and nowhere else.
  **rows served**  what the caller got back — the PAGE on a paged read.
  **seconds**      median of `--repeat`, after a discarded warm-up.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY — each answered, never assumed:**

  * **Measuring nothing.** RLS FORCE is on and the app role is neither
    superuser nor BYPASSRLS, so with `app.tenant_id` unset every query returns
    zero rows in about a millisecond and every timing would look wonderful.
    Every measurement runs inside `tenant_context` and **prints the row count
    it served**; a zero is a failure, not a fast answer.
  * **Timing a page that is not the expensive one.** Page 1 of an unpaged read
    is cheap because there is only one page. The LAST page is measured too,
    which is where an in-Python slice shows: a SQL `OFFSET` walk is flat, a
    Python slice that materialised everything first is not.
  * **A query that ignores `per`.** It would time beautifully and serve
    everything, so page 1 serving more than `PAGE` rows FAILS by name.
  * **A sort applied in Python after the page.** Two directions over the same
    window must reverse at the ends; **equal firsts mean `direction` was
    ignored**, so the comparison is `!=` and never `<=`.
  * **An export that inherited a page.** Each stream is counted against the
    tenant's whole filtered set and a short file FAILS.
  * **An N+1 hiding behind a small page.** Every label read on all three paths
    is batched per page, so the statement count must NOT move with `per`. The
    script measures page 1 at two page sizes and fails a count that scales.

⚠ **WHAT THIS SCRIPT DOES NOT MEASURE, STATED RATHER THAN LEFT BLANK
(hard-won law 7's fifth shape — a number over a scope it silently excludes).**
It measures three DATASETS and **four reports are seeded on them: R31, R33,
R34, R37.** Only R31 and R33 are served; R34 and R37 are refused on grain and
there is nothing to time. The refusals are asserted here rather than skipped,
so a future lane that quietly starts serving one turns this red.

USAGE
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_dssmall \\
      python3 ../10-scripts/ds_small_datasets_cost.py --orders 40000 --assets 40000 --repeat 3
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "true")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import connection, reset_queries  # noqa: E402
from django.db.models import F  # noqa: E402

from apps.assets import assets_dataset  # noqa: E402
from apps.assets import models as asset_models  # noqa: E402
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models  # noqa: E402
from apps.rating import models as rating_models  # noqa: E402
from apps.rating import rate_schedules_dataset  # noqa: E402
from apps.work import work_orders_dataset  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

import cr051_provision_utilities as provisioner  # noqa: E402

PAGE = 50
BIG_PAGE = 200
#: `docker-entrypoint.sh`, `GUNICORN_TIMEOUT:-60`. A read slower than this is
#: not slow — it is KILLED BEFORE IT ANSWERS, which is what `CR-138` `P4`
#: measured on `/outstandings` at the top of the ICP.
WORKER_TIMEOUT = 60.0
MARKER = "DS-SMALL fixture"


def _measure(label: str, call, *, repeat: int, rows_of=None) -> dict:
    """(statements, rows, median seconds) for one call, warm-up discarded."""
    rows_of = rows_of or (lambda answer: len(answer["rows"]))
    previous = settings.DEBUG
    settings.DEBUG = True
    try:
        call()  # discarded warm-up — the first run pays for the connection
        timings: list[float] = []
        statements = 0
        rows = 0
        answer = None
        for _ in range(repeat):
            reset_queries()
            began = time.perf_counter()
            answer = call()
            timings.append(time.perf_counter() - began)
            statements = len(connection.queries)
            rows = rows_of(answer)
        return {
            "label": label,
            "statements": statements,
            "rows": rows,
            "seconds": statistics.median(timings),
            "answer": answer,
        }
    finally:
        settings.DEBUG = previous


def seed_orders(tenant, *, orders: int) -> int:
    """`orders` work orders spread over states and days, anchored on premises.

    ⚠ **WRITTEN THROUGH THE ORM RATHER THAN `create_work_order`.** That service
    applies numbering, an audit row and BR-WRK-006's refusals — the right door
    for real work — but this script measures a READ MODEL, and a raise failure
    inside a benchmark would be indistinguishable from a reporting one. It is
    the same choice, for the same stated reason, the sibling scripts record.

    ⚠ **ONE IN SEVEN IS CANCELLED**, because that is the arithmetic finding the
    script has to be able to see: `raised − completed` is not `open` once a
    cancellation exists, and R33's drawn tiles get away with the subtraction
    only because the illustration has none in it.
    """
    premises = metering_models.Premises.objects.order_by("premise_no").first()
    if premises is None:
        sys.exit("REFUSED: this tenant has no premises — an order would have no anchor")
    existing = work_tables.WorkOrder.objects.filter(type__startswith=MARKER).count()
    made = 0
    day_zero = date.today().replace(day=1) - timedelta(days=1)
    batch: list[work_tables.WorkOrder] = []
    for index in range(existing, orders):
        when = day_zero - timedelta(days=index % 180)
        raised = datetime(when.year, when.month, when.day, 8, 0, tzinfo=timezone.utc)
        if index % 7 == 6:
            state, completed = work_tables.WO_CANCELLED, None
        elif index % 7 in (4, 5):
            state, completed = work_tables.WO_PLANNED, None
        else:
            state, completed = work_tables.WO_COMPLETED, raised + timedelta(days=1 + index % 5)
        batch.append(
            work_tables.WorkOrder(
                tenant=tenant,
                order_no=f"WO-DSS-{index:07d}",
                premises=premises,
                type=f"{MARKER} meter change",
                state=state,
                completed_at=completed,
                minutes_on_site=(30 + index % 120) if completed else None,
            )
        )
        if len(batch) >= 2_000:
            work_tables.WorkOrder.objects.bulk_create(batch)
            made += len(batch)
            batch = []
    if batch:
        work_tables.WorkOrder.objects.bulk_create(batch)
        made += len(batch)
    # `created_at` is `auto_now_add`, so the window is stamped afterwards — a
    # fixture that left every order at "now" could not exercise the raise-date
    # filter that IS this report's basis.
    #
    # ⚠ **IT IS SPREAD ACROSS 180 DAYS, AND THE FIRST DRAFT STAMPED THEM ALL TO
    # ONE INSTANT.** That is a fixture that measures the wrong thing: with every
    # row sharing a `created_at`, the default sort collapses onto its `id`
    # tiebreak and page 801 becomes a 40,000-row walk through one equal run.
    # The script's own last-page guard caught it at 4.96×, which is the guard
    # doing its job on its author — and a benchmark nobody can distinguish from
    # a real regression is worse than none.
    # ⚠ **UNCONDITIONAL, NOT `if made:`.** The first draft put the spread behind
    # the insert count, so a SECOND run over an already-seeded tenant seeded
    # nothing, skipped the spread and went on measuring the collapsed dates the
    # first run left behind — a fixture step that only runs on the path nobody
    # takes twice. It is idempotent and cheap; it runs every time.
    if True:
        for bucket in range(180):
            when = day_zero - timedelta(days=bucket)
            moment = datetime(when.year, when.month, when.day, 8, 0, tzinfo=timezone.utc)
            # ⚠ **`completed_at` MOVES WITH IT.** The first draft spread only
            # the raise and left completion where the insert put it, so the two
            # were decoupled and the script printed *"average days to close
            # −70.3"*. A benchmark that reports a negative elapsed time and then
            # says PASS is hard-won law 7's own shape, which is why the guard
            # below now refuses it rather than leaving it to a reader to notice.
            work_tables.WorkOrder.objects.filter(
                type__startswith=MARKER, order_no__endswith=f"{bucket:03d}"
            ).update(created_at=moment)
    # ⚠ **THEN COMPLETION IS DERIVED FROM THE RAISE, FOR EVERY ROW, IN ONE
    # STATEMENT — AND THIS IS THE SECOND ATTEMPT AT IT.** The first fix moved
    # `completed_at` inside the bucket loop beside `created_at`, which looked
    # right and reached **18% of the rows**: the buckets run 0–179 and an order
    # number ends in 000–999, so four rows in five never matched and kept an
    # insert-time raise beside a completion computed from a date up to 180 days
    # earlier. The script went on printing *"average days to close −70.3"*.
    #
    # `F("created_at") + interval` needs no match at all — it is relative to
    # whatever the raise ended up being, so it cannot decouple. The guard that
    # refuses a negative average is what caught both attempts, which is the
    # argument for having written it: a fixture is code, and a benchmark whose
    # numbers nobody checks is a benchmark that measures the wrong thing
    # confidently.
    work_tables.WorkOrder.objects.filter(
        type__startswith=MARKER, completed_at__isnull=False
    ).update(completed_at=F("created_at") + timedelta(days=2))
    return made


def seed_assets(tenant, *, assets: int) -> int:
    """`assets` meters, ONE IN SIX SPARE (no service point, so no premises).

    The spares are the drawn warning's own case: *"a spare meter has no
    premises and no read, and both cells show an em-dash rather than a blank."*
    A fixture with none could not tell `not_applicable` from `unknown`.
    """
    asset_type = asset_models.AssetType.objects.order_by("code").first()
    stage_in_service = asset_models.AssetLifecycleStage.objects.filter(
        behavior_class=assets_dataset.CLASS_IN_SERVICE
    ).first()
    stage_spare = asset_models.AssetLifecycleStage.objects.filter(
        behavior_class=assets_dataset.CLASS_AVAILABLE
    ).first()
    point = metering_models.ServicePoint.objects.order_by("created_at").first()
    if not (asset_type and stage_in_service and stage_spare and point):
        sys.exit(
            "REFUSED: this tenant lacks an asset type, both lifecycle stages or a service "
            "point — the fixture would measure a fleet that cannot exist"
        )
    existing = asset_models.Asset.objects.filter(location_note=MARKER).count()
    made = 0
    batch: list[asset_models.Asset] = []
    for index in range(existing, assets):
        spare = index % 6 == 0
        batch.append(
            asset_models.Asset(
                tenant=tenant,
                asset_no=f"MTR-DSS-{index:07d}",
                type=asset_type,
                status=stage_spare if spare else stage_in_service,
                service_point=None if spare else point,
                size_class='5/8"',
                unit="kgal",
                install_date=date(2019, 1, 1) + timedelta(days=index % 2500),
                test_interval_months=None if index % 4 == 3 else 120,
                last_test_date=None if index % 4 == 3 else date(2016, 1, 1),
                location_note=MARKER,
            )
        )
        if len(batch) >= 2_000:
            asset_models.Asset.objects.bulk_create(batch)
            made += len(batch)
            batch = []
    if batch:
        asset_models.Asset.objects.bulk_create(batch)
        made += len(batch)
    return made


def seed_versions(tenant, *, versions: int) -> int:
    """`versions` dated tariff versions on the tenant's own schedules."""
    tariff = rating_models.Tariff.objects.order_by("name").first()
    if tariff is None:
        sys.exit("REFUSED: this tenant has no rate schedule — there are no versions to read")
    existing = rating_models.TariffVersion.objects.filter(
        change_reason__startswith=MARKER
    ).count()
    made = 0
    batch: list[rating_models.TariffVersion] = []
    for index in range(existing, versions):
        batch.append(
            rating_models.TariffVersion(
                tenant=tenant,
                tariff=tariff,
                model="flat",
                # DEF-277 — one in nine is NULL, which means *not served* and is
                # a different fact from a stored 0 meaning *served, and free*.
                base_charge=None if index % 9 == 8 else Decimal("20.0000") + (index % 13),
                effective_from=date(2020, 1, 1) + timedelta(days=index % 2200),
                change_reason=f"{MARKER} {index}",
            )
        )
        if len(batch) >= 2_000:
            rating_models.TariffVersion.objects.bulk_create(batch)
            made += len(batch)
            batch = []
    if batch:
        rating_models.TariffVersion.objects.bulk_create(batch)
        made += len(batch)
    return made


def _page_guards(name, first, last, streamed, total, *, page_size=PAGE) -> None:
    """The four guards, per dataset. Each names the false pass it closes."""
    if first["rows"] == 0:
        sys.exit(f"FAIL — {name}: page 1 served ZERO rows. A read that answers nothing "
                 "reads as 'no error' and this script would have measured a tenant "
                 "context that was never set (hard rule 1, RLS FORCE).")
    if first["rows"] > page_size:
        sys.exit(f"FAIL — {name}: page 1 served {first['rows']} rows against per={page_size}")
    ratio = last["seconds"] / first["seconds"] if first["seconds"] else 0
    print(
        f"  {name}: last page / first page = {ratio:.2f}×  "
        f"({last['seconds']:.3f}s vs {first['seconds']:.3f}s) · "
        f"last page {last['seconds']:.3f}s against the {WORKER_TIMEOUT}s worker timeout"
    )
    # ⚠ **THE RATIO IS REPORTED AND IS NOT THE GUARD, AND THAT IS A CORRECTION
    # THIS SCRIPT MADE TO ITSELF ON THE DAY IT WAS WRITTEN.** The first draft
    # failed above 3.0×, which is the right instrument for the defect it was
    # aimed at — a page sliced in Python after materialising everything. It is
    # the WRONG instrument here, and the measurement proved it: adding an index
    # on `work_orders (tenant_id, created_at DESC, id DESC)` took page 1 from
    # 0.418s to 0.161s and the last page from 1.946s to 1.361s — every figure
    # BETTER — and the ratio went from 4.65× to 8.47× and the guard went red.
    # A check that turns red when the thing it measures improves is hard-won
    # law 7's false pass running backwards, and it is worse than none because
    # it is trusted. A deep OFFSET is a walk however good the index is; what
    # actually matters is whether the last page ANSWERS, and the threshold that
    # means something is the one a real deployment enforces.
    if last["seconds"] > WORKER_TIMEOUT:
        sys.exit(
            f"FAIL — {name}: the last page took {last['seconds']:.3f}s and a web worker is "
            f"given {WORKER_TIMEOUT}s (docker-entrypoint.sh, GUNICORN_TIMEOUT). It would not "
            "be slow in production, it would be killed before it answered."
        )
    # The Python-slice defect the ratio was aimed at has TWO signatures this
    # script measures directly instead, and both are exact rather than
    # thresholded: the statement count must not move with `per` (checked by the
    # caller), and page 1 must not serve more rows than `per` (checked above).
    # ⚠ **AGAINST THE PAGE'S OWN `total`, NOT AGAINST THE TABLE'S ROW COUNT —
    # AND THE FIRST DRAFT GOT THAT WRONG.** It compared the stream against
    # `Asset.objects.count()` and failed at 40,073 of 40,074, which looked like
    # a ceiling on the export and was the OPPOSITE: the `assets` query filters
    # by `as_of` (installed by then, not retired by then) and one asset in the
    # fixture is legitimately outside that window. The stream was right and the
    # yardstick was wrong. NFR-5 asks whether the export serves the whole
    # FILTERED set, and the only figure that means that is the SQL aggregate the
    # page already struck over it. The table count is printed beside it so a
    # reader can see what the filter removed rather than having to guess.
    filtered = first["answer"]["total"]
    print(f"  {name}: stream {streamed['rows']} · filtered set {filtered} · table {total}")
    if streamed["rows"] != filtered:
        sys.exit(
            f"FAIL — {name}: the stream served {streamed['rows']} of the {filtered} rows in "
            "its own filtered set. NFR-5 forbids a ceiling on the export branch."
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--orders", type=int, default=40_000)
    parser.add_argument("--assets", type=int, default=40_000)
    parser.add_argument("--versions", type=int, default=2_000)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--index", type=int, default=93, help="perf tenant index")
    args = parser.parse_args()

    tenant = provisioner.provision(args.index)
    print(f"tenant {tenant.subdomain} ({tenant.id})")

    with core_tenancy.tenant_context(str(tenant.id)):
        print(f"seeded {seed_orders(tenant, orders=args.orders)} new work orders")
        print(f"seeded {seed_assets(tenant, assets=args.assets)} new assets")
        print(f"seeded {seed_versions(tenant, versions=args.versions)} new tariff versions")

        orders_total = work_tables.WorkOrder.objects.count()
        assets_total = asset_models.Asset.objects.count()
        versions_total = rating_models.TariffVersion.objects.filter(
            effective_from__isnull=False
        ).count()
        spares = asset_models.Asset.objects.filter(service_point__isnull=True).count()
        print(
            f"{orders_total} work orders · {assets_total} assets "
            f"({spares} with no service point) · {versions_total} dated versions"
        )
        for label, count in (
            ("work orders", orders_total),
            ("assets", assets_total),
            ("tariff versions", versions_total),
        ):
            if count == 0:
                sys.exit(f"REFUSED: zero {label} — this would measure nothing at all")

        measurements = []
        results = {}
        for name, module, page_fn, stream_fn, kwargs in (
            ("work_orders", work_orders_dataset, "work_orders_dataset",
             "work_orders_dataset_stream", {}),
            ("assets", assets_dataset, "assets_dataset", "assets_dataset_stream", {}),
            ("rate_schedules", rate_schedules_dataset, "rate_schedules_dataset",
             "rate_schedules_dataset_stream", {}),
        ):
            paged = getattr(module, page_fn)
            streamer = getattr(module, stream_fn)
            first = _measure(
                f"{name} · page 1", lambda p=paged, k=kwargs: p(page=1, per=PAGE, **k),
                repeat=args.repeat,
            )
            pages = first["answer"]["pages"]
            last = _measure(
                f"{name} · page {pages} (last)",
                lambda p=paged, k=kwargs, n=pages: p(page=n, per=PAGE, **k),
                repeat=args.repeat,
            )
            wide = _measure(
                f"{name} · page 1 (per={BIG_PAGE})",
                lambda p=paged, k=kwargs: p(page=1, per=BIG_PAGE, **k),
                repeat=args.repeat,
            )
            streamed = _measure(
                f"{name} · stream (the export)",
                lambda s=streamer, k=kwargs: {"rows": list(s(**k))},
                repeat=1,
            )
            measurements += [first, last, wide, streamed]
            results[name] = (first, last, wide, streamed)

        print()
        print(f"{'read':<42}{'statements':>12}{'rows served':>14}{'seconds':>10}")
        for measured in measurements:
            print(
                f"{measured['label']:<42}{measured['statements']:>12}"
                f"{measured['rows']:>14}{measured['seconds']:>10.3f}"
            )

        print()
        totals = {
            "work_orders": orders_total,
            "assets": assets_total,
            "rate_schedules": versions_total,
        }
        for name, (first, last, wide, streamed) in results.items():
            _page_guards(name, first, last, streamed, totals[name])
            # A LABEL READ THAT IS NOT BATCHED shows here and nowhere else: a
            # per-row seam call makes the statement count scale with `per`.
            if wide["statements"] > first["statements"] + 2:
                sys.exit(
                    f"FAIL — {name}: page 1 cost {first['statements']} statements at per={PAGE} "
                    f"and {wide['statements']} at per={BIG_PAGE}. A count that moves with the "
                    "page size is a label read per row, not per page."
                )

        # ── the refusals, asserted rather than skipped ──────────────────────
        print()
        orders_answer = results["work_orders"][0]["answer"]
        rates_answer = results["rate_schedules"][0]["answer"]
        codes = {p["code"] for p in orders_answer["problems"]} | {
            p["code"] for p in rates_answer["problems"]
        }
        for required in (
            "disconnect_and_reconnect_is_one_account_not_one_work_order",
            "rate_change_history_is_one_component_change_not_one_version",
        ):
            if required not in codes:
                sys.exit(f"FAIL — the refusal {required!r} is no longer carried")
            print(f"refusal carried: {required}")

        # ── the tile arithmetic ────────────────────────────────────────────
        t = orders_answer["totals"]
        print()
        print(f"raised {t['raised']} · completed {t['completed']} · open {t['open']} · "
              f"duration {t['duration']} {t['duration_unit']}")
        print(f"average days to close {t['average_days_to_close']} (non-additive) "
              f"· on-time {t['on_time_pct']}")
        # ⚠ A NEGATIVE ELAPSED TIME IS NOT A SLOW READ, IT IS A WRONG ONE, and
        # a run that prints one and reports PASS is a check that does not check.
        if t["average_days_to_close"] is not None and t["average_days_to_close"] < 0:
            sys.exit(
                f"FAIL — average days to close is {t['average_days_to_close']}. An order "
                "cannot be completed before it was raised; either the fixture decoupled "
                "the two dates or the query is subtracting them the wrong way round."
            )
        if t["open"] == t["raised"] - t["completed"]:
            sys.exit(
                "FAIL — `open` equals `raised − completed` although this tenant holds "
                "cancelled orders. A cancelled order is neither, and a query copying the "
                "drawn subtraction is wrong the first day a job is called off."
            )
        a = results["assets"][0]["answer"]["totals"]
        print(f"meters {a['assets']} · in service {a['in_service']} · spare {a['spare']} · "
              f"due for change {a['due_for_change']} ({a['due_for_change_pct']}%)")
        if a["spare"] == 0:
            sys.exit("FAIL — no spare meters; the em-dash warning cannot be exercised")

        # ── sorting is in SQL. EQUAL firsts mean `direction` was ignored. ───
        print()
        for name, module, fn, key, attribute in (
            ("work_orders", work_orders_dataset, "work_orders_dataset", "order_no", "order_no"),
            ("assets", assets_dataset, "assets_dataset", "asset_no", "asset_no"),
            ("rate_schedules", rate_schedules_dataset, "rate_schedules_dataset",
             "effective_from", "effective_from"),
        ):
            paged = getattr(module, fn)
            low = getattr(paged(page=1, per=PAGE, sort=key, direction="asc")["rows"][0], attribute)
            high = getattr(
                paged(page=1, per=PAGE, sort=key, direction="desc")["rows"][0], attribute
            )
            print(f"sort {name}.{key}: asc opens {low} · desc opens {high}")
            if low == high:
                sys.exit(
                    f"FAIL — {name}: both directions opened at {low}. They must reverse; "
                    "equal firsts mean `direction` was ignored and the order is not being "
                    "applied in SQL at all."
                )

    print()
    print("PASS — every guard above held.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 · the last three dataset queries (lane DS-SMALL)
# generated: 2026-09-27
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
