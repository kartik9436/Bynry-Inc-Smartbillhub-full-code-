#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · lane DS-METER — the PostgreSQL half of the
#           `meter_reads` dataset's proof.
# Rules:    CLAUDE.md hard-won law 14 (`config/settings/test.py` hardcodes
#           in-memory SQLite and ignores `DATABASE_URL`, so RLS, `jsonb` and an
#           aborted transaction cannot be proved by the suite at all) ·
#           hard-won law 7 (prove a guard RED first; say what would make it pass
#           wrongly; a check's OUTPUT must distinguish pass from fail to a
#           READER, not merely to an exit code) · hard rule 1 (tenant scoping) ·
#           hard rule 3 (every quantity carries its unit) · NFR-3 · NFR-5
# Tests:    it IS the test — 06-backend/tests/test_rep_meter_reads_dataset.py is
#           the SQLite half and proves the arithmetic; this proves the things
#           SQLite structurally cannot hold.
# ───────────────────────────────────────────────────────
"""THE `meter_reads` DATASET ON REAL PostgreSQL — cost, isolation, savepoint.

`meter_reads` is the LARGEST dataset in the product. Brief §7.6 (p087, read as
an image): at T5 the biggest report is *"~480,000 rows — a year of read
history"*, against ~40,000 rows for the three Receivables datasets. So paging
matters more here than anywhere else, and a figure taken on 516 seeded reads
would say nothing.

WHAT EACH COLUMN MEANS
  **statements**   round trips. An N+1 shows here and nowhere else.
  **rows served**  what the caller got back — the PAGE on a paged read.
  **seconds**      median of `--repeat`, after a discarded warm-up.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY — each answered, never assumed:**

  * **Measuring nothing.** RLS `FORCE` is on and the app role is neither
    superuser nor `BYPASSRLS`, so with `app.tenant_id` unset every query returns
    zero rows in about a millisecond and every timing would look wonderful. A
    query returning nothing reads as *"no error"*. So every measurement runs
    inside `tenant_context` and **prints the row count it served**, and a zero
    is a FAILURE by name rather than a fast answer.
  * **Timing a page that is not the expensive one.** Page 1 of an unpaged read
    is cheap because there is only one page. The LAST page is measured too,
    which is where an in-Python slice shows: a SQL `OFFSET` walk is flat, a
    Python slice that materialised 480,000 rows first is not. **The property is
    that the last page is not slower than the first** — not the wall clock.
  * **A query that ignores `per`.** It would time beautifully and serve
    everything, so page 1 serving more than `PAGE` rows FAILS by name.
  * **A sort applied in Python after the page.** Two directions over the same
    window must reverse at the ends; equal firsts mean `direction` was ignored.
  * **An export that inherited a page.** The stream is counted against the
    tenant's whole filtered set and a short file FAILS.
  * **A unit refusal that never fires.** The mixed-unit branch is only
    interesting if the fixture really holds two units, so the seed writes BOTH
    `gal` and `kWh` and the script prints the distinct count it found. A
    one-unit fixture would take the lawful branch and prove nothing.

⚠ **AND THE TWO THINGS SQLITE CANNOT HOLD AT ALL:**

  **`--isolation`** — a SECOND tenant's reads in the same window, then the
  dataset run under the first tenant's `app.tenant_id`. A cross-tenant row in
  the answer, or in the FOOTER TOTAL, is a hard rule 1 failure. The footer is
  checked separately from the rows because **a total struck over the wrong set
  leaks the figure without leaking a row**, which is the R45 portal hazard in
  its staff-facing form.

  **`--savepoint-audit`** — p065's warning, verbatim: *"A rejected row is
  skipped inside its own savepoint — hard-won law 14. Without the nested
  transaction the first rejection aborts the whole import on PostgreSQL and
  every row is lost at commit, while the test suite on SQLite passes."* That is
  a rule for the IMPORT WRITER, not for this read. This audit reports what the
  writer actually does, so the claim is a command a reader can run rather than a
  sentence in a docstring (hard-won law 1).

USAGE
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_ds_meter \\
      python3 ../10-scripts/ds_meter_reads_cost.py --reads 40000 --repeat 3
"""

from __future__ import annotations

import argparse
import os
import re
import statistics
import sys
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "06-backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "true")

import django

django.setup()

import cr051_provision_utilities as provisioner
from apps.assets import models as asset_models
from apps.customers import models as customer_models
from apps.metering import meter_reads_dataset as dataset
from apps.metering import models as metering_models
from core import tenancy as core_tenancy
from django.conf import settings
from django.db import connection, reset_queries

PAGE = 50
WINDOW = {"start": date(2000, 1, 1), "end": date(2100, 1, 1)}
UTC = timezone.utc

#: ⚠ **TWO UNITS ON PURPOSE.** Hard rule 3's refusal is the thing this dataset
#: most exists to enforce, and a fixture holding one unit would take the lawful
#: branch every time and prove nothing about the branch that matters.
UNITS = ("gal", "kWh")


def _partition_span() -> tuple[datetime, datetime]:
    """The declared monthly partitions of `meter_reads`, as one window.

    Measured from `pg_inherits` rather than assumed, because the set moves: the
    clone this was written against carries 28 months (2024-09 → 2026-12) and a
    figure quoted in a docstring would be wrong by the next migration.
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            select min(c.relname), max(c.relname)
            from pg_class c
            join pg_inherits i on i.inhrelid = c.oid
            join pg_class p on p.oid = i.inhparent
            where p.relname = 'meter_reads'
            """)
        low, high = cursor.fetchone()
    if low is None:
        sys.exit(
            "REFUSED: `meter_reads` has no partitions — this is not a PostgreSQL clone"
        )
    first_year, first_month = int(low[-7:-3]), int(low[-2:])
    last_year, last_month = int(high[-7:-3]), int(high[-2:])
    begins = datetime(first_year, first_month, 1, tzinfo=UTC)
    ends = datetime(
        last_year + (last_month // 12), (last_month % 12) + 1, 1, tzinfo=UTC
    )
    print(f"  partitions: {low} .. {high}  ({begins:%Y-%m-%d} to {ends:%Y-%m-%d})")
    return begins, ends


def seed(tenant, *, reads: int) -> int:
    """`reads` committed lineage heads spread over meters, days and both units.

    ⚠ **WRITTEN THROUGH THE ORM RATHER THAN THE IMPORT PIPELINE, DELIBERATELY.**
    `commit_read_batch` runs validation, the plan-register resolver and the
    per-row savepoint — the right door for a real read, and the wrong one here:
    a validation refusal inside a benchmark would be indistinguishable from a
    reporting one. This script measures a READ MODEL over `meter_reads`. The
    same choice, for the same stated reason, that the sibling dataset scripts
    record.

    ⚠ **EVERY ROW CARRIES A UNIT** (hard rule 3, and the model's `unit` is NOT
    NULL anyway), and roughly one in four is `kWh` so the mixed-unit refusal has
    something to refuse.
    """
    accounts = list(customer_models.Account.objects.order_by("account_no")[:200])
    if not accounts:
        sys.exit(
            "REFUSED: this tenant has no accounts — there is nothing to read a meter for"
        )
    meters = list(asset_models.Asset.objects.order_by("asset_no")[:200])
    if not meters:
        sys.exit("REFUSED: this tenant has no assets — there is no meter to read")

    # ⚠ **`meter_reads` IS PARTITIONED MONTHLY ON `read_at` (DB-7/NFR-24,
    # BR-MET-055) AND THE PARTITIONS ARE FINITE.** A row outside every declared
    # range is refused by PostgreSQL with *"no partition of relation
    # meter_reads found for row"* — which is not a bug in the read model and
    # must not be mistaken for one. A naive seed stepping one hour per row runs
    # 40,000 rows across four and a half years and falls off the end.
    #
    # So the span is read FROM THE DATABASE and the step is derived to fit it,
    # and the script REFUSES BY NAME rather than crashing when it cannot.
    span_start, span_end = _partition_span()
    # ⚠ **AND THE CLOCK CONTINUES FROM WHAT IS ALREADY THERE.** `meter_reads`
    # is keyed (tenant, asset, read_at, channel) — BR-MET-059's
    # one-record-per-register-per-date law, enforced by a real unique index on
    # each partition. Restarting at a fixed date makes a SECOND run of this
    # script collide on every row it already wrote, which is how its first
    # 40,000-read run died.
    latest = (
        metering_models.MeterRead.objects.order_by("-read_at")
        .values_list("read_at", flat=True)
        .first()
    )
    start = (
        span_start if latest is None else max(span_start, latest + timedelta(minutes=1))
    )
    room = (span_end - start).total_seconds() / 60.0
    if room < reads:
        sys.exit(
            f"REFUSED: {reads} reads need {reads} minutes of room and the partitioned "
            f"span ends {span_end:%Y-%m-%d} with {int(room)} minutes left after "
            f"{start:%Y-%m-%d %H:%M}. Seed a fresh tenant (--index) or extend the "
            f"partitions; a short seed would quietly measure a smaller report."
        )
    step = timedelta(minutes=max(1, int(room // max(reads, 1))))
    batch: list = []
    made = 0
    for index in range(reads):
        meter = meters[index % len(meters)]
        account = accounts[index % len(accounts)]
        unit = UNITS[0] if index % 4 else UNITS[1]
        moment = start + step * index
        prior = Decimal(100_000 + index)
        batch.append(
            metering_models.MeterRead(
                tenant=tenant,
                asset=meter,
                account=account,
                read_at=moment,
                channel=metering_models.CHANNEL_TOTAL,
                prior_value=prior,
                current_value=prior + Decimal(10),
                consumption=Decimal(10),
                unit=unit,
                source="manual",
                status="ok",
                lifecycle="committed",
            )
        )
        if len(batch) >= 2_000:
            metering_models.MeterRead.objects.bulk_create(batch)
            made += len(batch)
            batch = []
    if batch:
        metering_models.MeterRead.objects.bulk_create(batch)
        made += len(batch)
    return made


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


def _line(result: dict) -> None:
    print(
        f"  {result['label']:<44} {result['statements']:>4} stmts  "
        f"{result['rows']:>7} rows  {result['seconds']:.3f}s"
    )


def savepoint_audit() -> int:
    """p065's warning, CHECKED rather than repeated.

    Greps the import writer for a nested `transaction.atomic()` wrapping the
    per-row post. Prints what it found either way — **a check's output must
    distinguish pass from fail to a reader** (hard-won law 7 habit 3).
    """
    path = BACKEND / "apps" / "metering" / "services.py"
    body = path.read_text()
    print(
        "savepoint audit — p065: 'a rejected row is skipped inside its own savepoint'"
    )
    found = re.search(
        r"try:\s*\n\s*with transaction\.atomic\(\):\s*\n\s*read = _post_row\(",
        body,
    )
    if found is None:
        print(
            "  ✘ NO per-row savepoint around `_post_row` in apps/metering/services.py."
        )
        print("    On PostgreSQL the first refused row aborts the transaction and the")
        print(
            "    whole import is lost at COMMIT, while this repo's SQLite suite passes"
        )
        print("    green (hard-won law 14).")
        return 1
    line_no = body[: found.start()].count("\n") + 1
    print(
        f"  ✔ per-row savepoint present — apps/metering/services.py, `_post_row` call at line {line_no}"
    )
    print(
        "    `with transaction.atomic():` nested inside the batch transaction, and the"
    )
    print(
        "    module header at line 70 states the reason in full. The warning is OBEYED"
    )
    print("    by the write path; this dataset is a read and writes nothing.")
    return 0


def isolation(tenant, other, *, reads: int) -> int:
    """Hard rule 1, on real PostgreSQL with RLS FORCE — rows AND footer.

    ⚠ **THE BASELINE IS LINEAGE HEADS, NOT EVERY ROW, AND GETTING THAT WRONG IS
    WHAT THIS COMMENT IS FOR.** The first version of this check compared the
    dataset's count against `MeterRead.objects.count()` and reported
    `40201 against 40202` — a FAILURE that named a leak and was really one
    superseded read being correctly excluded (BR-MET-016/053). A check whose
    failure message points at the wrong thing is worse than no check, so the
    baseline is spelled the same way `_base()` spells it.

    ⚠ **AND THE COUNT IS THE WEAK HALF.** Two tenants can hold the same number
    of reads, so equal counts prove nothing on their own. The strong question is
    whether any of the OTHER tenant's specific row ids came back, and that is
    asked directly below.
    """
    print("isolation — a second tenant's reads in the same window")
    with core_tenancy.tenant_context(str(other.id)):
        made = seed(other, reads=reads)
        theirs = metering_models.MeterRead.objects.filter(
            superseded_by_id__isnull=True
        ).count()
        their_ids = set(
            metering_models.MeterRead.objects.values_list("id", flat=True)[:5_000]
        )
    print(f"  tenant {other.subdomain}: seeded {made}, holds {theirs} heads")
    if theirs == 0 or not their_ids:
        sys.exit("REFUSED: the second tenant has no reads — this would prove nothing")

    with core_tenancy.tenant_context(str(tenant.id)):
        mine = metering_models.MeterRead.objects.filter(
            superseded_by_id__isnull=True
        ).count()
        page = dataset.meter_reads_dataset(per=PAGE, **WINDOW)
        streamed = sum(1 for _ in dataset.meter_reads_dataset_stream(**WINDOW))
        # The DIRECT question: can this tenant's context see a single one of the
        # other tenant's rows, by id, at all?
        reachable = metering_models.MeterRead.objects.filter(id__in=their_ids).count()
    print(f"  tenant {tenant.subdomain}: holds {mine} heads")
    if mine == 0:
        sys.exit("REFUSED: the measured tenant has no reads — this would prove nothing")

    failures = 0
    if reachable:
        print(
            f"  \u2718 CROSS-TENANT: {reachable} of the other tenant's {len(their_ids)} "
            "row ids are visible under this tenant's app.tenant_id — hard rule 1"
        )
        failures += 1
    else:
        print(
            f"  \u2714 CROSS-TENANT: none of the other tenant's {len(their_ids)} row ids "
            "is reachable under this tenant's app.tenant_id"
        )
    if page["total"] != mine:
        print(
            f"  \u2718 ROWS: the dataset counted {page['total']} against {mine} heads"
        )
        failures += 1
    else:
        print(
            f"  \u2714 ROWS: {page['total']} == this tenant's {mine} heads; none of the other's {theirs}"
        )
    if streamed != mine:
        print(f"  \u2718 STREAM: served {streamed} against {mine}")
        failures += 1
    else:
        print(f"  \u2714 STREAM: {streamed} == this tenant's {mine} heads")
    # ⚠ The FOOTER separately — a total over the wrong set leaks the figure
    # without leaking a row.
    footer = page["totals"]["consumption"]
    if footer["reads"] != mine:
        print(f"  \u2718 FOOTER: struck over {footer['reads']} rows against {mine}")
        failures += 1
    else:
        print(
            f"  \u2714 FOOTER: struck over {footer['reads']} rows — this tenant's heads exactly"
        )
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reads", type=int, default=40_000)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--index", type=int, default=93, help="perf tenant index")
    parser.add_argument("--other-index", type=int, default=94)
    parser.add_argument("--isolation", action="store_true")
    parser.add_argument("--savepoint-audit", action="store_true")
    args = parser.parse_args()

    if args.savepoint_audit:
        return savepoint_audit()

    tenant = provisioner.provision(args.index)
    print(f"tenant {tenant.subdomain} ({tenant.id})")
    failures = 0

    with core_tenancy.tenant_context(str(tenant.id)):
        made = seed(tenant, reads=args.reads)
        total = metering_models.MeterRead.objects.count()
        units = (
            metering_models.MeterRead.objects.values_list("unit", flat=True)
            .distinct()
            .order_by("unit")
        )
        units = list(units)
        print(f"seeded {made} new reads · {total} committed heads in this tenant")
        print(f"  distinct units present: {units}  (hard rule 3's refusal needs > 1)")
        if total == 0:
            sys.exit("REFUSED: zero reads — this would measure nothing at all")

        first = _measure(
            "dataset · page 1",
            lambda: dataset.meter_reads_dataset(page=1, per=PAGE, **WINDOW),
            repeat=args.repeat,
        )
        pages = (first["answer"]["total"] + PAGE - 1) // PAGE
        last = _measure(
            f"dataset · page {pages} (last)",
            lambda: dataset.meter_reads_dataset(page=pages, per=PAGE, **WINDOW),
            repeat=args.repeat,
        )
        sorted_page = _measure(
            "dataset · page 1 sorted by consumption",
            lambda: dataset.meter_reads_dataset(
                page=1, per=PAGE, sort="consumption", direction="asc", **WINDOW
            ),
            repeat=args.repeat,
        )
        ranked = _measure(
            "ranking · group by account (R30)",
            lambda: dataset.account_usage_ranking(service="water", limit=25, **WINDOW),
            repeat=args.repeat,
        )
        one_account = customer_models.Account.objects.order_by("account_no").first()
        portal = _measure(
            "portal · R45 My Usage, one account",
            lambda: dataset.portal_usage(
                account_ids=[one_account.id], page=1, per=PAGE, **WINDOW
            ),
            repeat=args.repeat,
        )
        stream = _measure(
            "export · whole set, streamed",
            lambda: sum(1 for _ in dataset.meter_reads_dataset_stream(**WINDOW)),
            repeat=1,
            rows_of=lambda answer: answer,
        )

        print()
        for result in (first, last, sorted_page, ranked, portal, stream):
            _line(result)
        print()

        # ── the properties, each named so a reader can tell pass from fail ──
        if first["rows"] > PAGE:
            print(
                f"  ✘ PAGE IGNORED: page 1 served {first['rows']} rows against per={PAGE}"
            )
            failures += 1
        else:
            print(
                f"  ✔ PAGE HONOURED: page 1 served {first['rows']} rows at per={PAGE}"
            )

        if last["seconds"] > first["seconds"] * 3:
            print(
                f"  ✘ LAST PAGE {last['seconds']:.3f}s against first {first['seconds']:.3f}s — "
                "an OFFSET walk is flat; this is a Python slice over the whole set"
            )
            failures += 1
        else:
            print(
                f"  ✔ LAST PAGE {last['seconds']:.3f}s vs first {first['seconds']:.3f}s — "
                "the page is cut in SQL"
            )

        if stream["rows"] != first["answer"]["total"]:
            print(
                f"  ✘ EXPORT INHERITED A PAGE: {stream['rows']} rows against "
                f"{first['answer']['total']} in the filtered set"
            )
            failures += 1
        else:
            print(
                f"  ✔ EXPORT served the whole set — {stream['rows']} rows, no cap (NFR-5)"
            )

        # Hard rule 3 — the refusal, on a set that really does span two units.
        footer = first["answer"]["totals"]["consumption"]
        if len(units) > 1 and footer["total"] is not None:
            print(
                f"  ✘ HARD RULE 3: a total of {footer['total']} was served over "
                f"{footer['unit_count']} units — gallons plus kilowatt-hours is not a number"
            )
            failures += 1
        elif len(units) > 1:
            print(
                f"  ✔ HARD RULE 3: total REFUSED over {footer['unit_count']} units — "
                f"reason '{footer['reason']['code']}'"
            )
        else:
            print(
                "  ✘ FIXTURE: only one unit present — the refusal branch was never reached"
            )
            failures += 1

        # ⚠ **AND THE LAWFUL BRANCH BESIDE IT, OVER THE SAME ROWS.** Without it
        # the refusal above proves only that the total is "always None" — law 7's
        # *"ask what would make this check pass wrongly"*. Narrowing the SAME
        # filtered set to ONE unit must produce a real number and name it.
        gal_only = metering_models.MeterRead.objects.filter(
            tenant_id=tenant.id, superseded_by_id__isnull=True, unit=UNITS[0]
        )
        lawful = dataset.consumption_total(gal_only)
        if lawful["total"] is None or lawful["unit"] != UNITS[0]:
            print(
                f"  \u2718 HARD RULE 3 (lawful branch): one unit still refused — "
                f"{lawful}. The refusal above is 'always None', not a refusal."
            )
            failures += 1
        else:
            print(
                f"  \u2714 HARD RULE 3 (lawful branch): {lawful['reads']} rows in one unit "
                f"total {lawful['total']} {lawful['unit']} — the refusal is real, not blanket"
            )

        # The two sort directions must reverse at the ends.
        down = dataset.meter_reads_dataset(
            page=1, per=PAGE, sort="reading", direction="desc", **WINDOW
        )
        up = dataset.meter_reads_dataset(
            page=1, per=PAGE, sort="reading", direction="asc", **WINDOW
        )
        if (
            down["rows"]
            and up["rows"]
            and down["rows"][0].reading == up["rows"][0].reading
        ):
            print("  ✘ SORT IGNORED: both directions start on the same reading")
            failures += 1
        else:
            print(
                f"  ✔ SORT applied in SQL: desc starts {down['rows'][0].reading}, "
                f"asc starts {up['rows'][0].reading}"
            )

        # R45 — the portal scope, and its footer.
        with_scope = portal["answer"]
        if with_scope["total"] >= first["answer"]["total"]:
            print(
                f"  ✘ PORTAL SCOPE: {with_scope['total']} rows against the whole set's "
                f"{first['answer']['total']} — the scope did nothing"
            )
            failures += 1
        else:
            print(
                f"  ✔ PORTAL SCOPE: {with_scope['total']} rows of {first['answer']['total']} — "
                f"footer struck over {with_scope['totals']['consumption']['reads']}"
            )
        if with_scope["totals"]["consumption"]["reads"] != with_scope["total"]:
            print("  ✘ PORTAL FOOTER: struck over a different set from the rows")
            failures += 1

    if args.isolation:
        print()
        other = provisioner.provision(args.other_index)
        failures += isolation(tenant, other, reads=min(args.reads, 2_000))

    print()
    print("FAIL" if failures else "PASS", f"— {failures} property failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
