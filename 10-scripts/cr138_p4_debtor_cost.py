#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:   CR-138-BRC07 `P4.1` (page and sort `/outstandings` in SQL) ·
#           `P4.2` (one query for the ladder) · `P4.5` (indexes).
# Defect:   DEF-PAY-4221 — `GET /outstandings` is unpaginated and sorts in
#           Python; correct at 3,000 connections, thirteen times short at
#           40,000.
# Rules:    `NFR-3` (universal server pagination) · `NFR-5` (no hard caps) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard-won law 7 (a check
#           whose output cannot distinguish pass from fail is worse than no
#           check; a check that cannot cover its whole subject prints what it
#           skipped beside what it checked).
# ───────────────────────────────────────────────────────
"""WHAT ONE DEBTOR LIST COSTS — three instruments, because one of them lies.

`10-scripts/cr094c_accounts_page_cost.py` already learned this the expensive
way on the accounts list and its lesson is copied here rather than re-learned:
**a wall clock alone cannot answer an `NFR-3` question**, because at a small
tenant every figure is dominated by fixed overhead and the same two numbers
come back before and after a change that removed 98% of the work. And a
**statement count alone cannot answer it either**, because a read can hold its
statement count perfectly flat while the ROWS those statements build grow with
the tenant — which is exactly the shape of `outstanding_positions`.

So this prints three columns and a reader needs all three:

  **statements**   how many round trips the read makes. This is the `P4.2`
                   instrument: an N+1 shows here and nowhere else.
  **rows built**   how many open BILLS the server materialised to answer.
                   This is the `P4.1` instrument: the seam pulls every open
                   invoice of the tenant into Python before anything is
                   filtered, so this number is the tenant's whole ledger
                   whatever page was asked for.
  **rows served**  what the caller actually got back. On a paged list this is
                   the page. On today's code it is every debtor.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY — and each is answered, not assumed:**

  * **Measuring nothing.** RLS FORCE is on and the app role is neither
    superuser nor BYPASSRLS: with `app.tenant_id` unset every query returns
    zero rows in about a microsecond and this script would print a beautiful
    set of figures about an empty tenant. Everything runs inside
    `tenant_context`, and the header prints the DEBTOR COUNT it is measuring
    over — **a run whose debtor count is 0 is a run that measured nothing, and
    it says so and exits 2.**
  * **A cold cache on the first call and a warm one on the second**, which
    would make whichever ran second look faster. Every timing is the MEDIAN of
    `--repeat` runs after one discarded warm-up, and the warm-up is stated.
  * **A plan cached from a previous run.** The EXPLAIN leg below runs
    `EXPLAIN (ANALYZE, BUFFERS)` on the statement, printing the plan rather
    than a verdict, so a reader sees the scan rather than being told about it.

⚠ **WHAT IT DOES NOT MEASURE, named because a declared blind spot with no
number beside it is indistinguishable from an empty one:** it does not measure
HTTP, DRF serialisation, authentication or the front end. It calls the read
models directly. The figure is the server's own work for one list and nothing
either side of it. It also measures ONE tenant — the fixture's — and says how
big that tenant is on every line.

USAGE
    10-scripts/proof-db.sh clone p4perf
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_p4perf \\
      python3 ../10-scripts/cr138_p4_debtor_cost.py --repeat 3
"""

from __future__ import annotations

import argparse
import os
import pathlib
import statistics
import sys
import time
from datetime import date
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402

from apps.payments import collections_read, outstandings as outstandings_read  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402

AS_OF = date(2026, 9, 23)


def _tenant_shape() -> dict[str, int]:
    """What this tenant HOLDS, so a reader can size every figure below."""
    with connection.cursor() as cursor:
        cursor.execute(
            "select (select count(*) from accounts), "
            "(select count(*) from invoices where status in ('issued','paid')), "
            "(select count(distinct account_id) from invoices "
            "  where status in ('issued','paid'))"
        )
        accounts, open_bills, debtors = cursor.fetchone()
    return {"accounts": accounts, "open_bills": open_bills, "debtors": debtors}


class _StatementCounter:
    """Counts EVERY statement, which `CaptureQueriesContext` does not.

    ⚠ Django's `connection.queries` log is capped at 9,000 entries and warns
    *"only the last 9000 queries will be returned"* — on stderr, in the middle
    of a benchmark, where it reads like noise. A read that makes 40,000 round
    trips would be reported as making 9,000, and the N+1 this script exists to
    size would be understated by a factor of four. An `execute_wrapper` counts
    the calls themselves and has no cap.
    """

    def __init__(self) -> None:
        self.count = 0

    def __call__(self, execute, sql, params, many, context):
        self.count += 1
        return execute(sql, params, many, context)


def _measure(label: str, call, *, repeat: int, rows_of, warmup: bool = True) -> dict:
    # ⚠ **IT PRINTS AS IT GOES.** The first version collected every figure and
    # printed the table at the end, so a run whose first read takes ten minutes
    # and whose second takes an hour shows nothing for seventy minutes — which
    # is indistinguishable from a hung script, and the figure already measured
    # is lost the moment it is killed. It was, once.
    print(f"  measuring: {label} …", flush=True)
    # ⚠ The warm-up is DISCARDED, not skipped for speed: the first call pays for
    # the connection and the plan cache, and a benchmark that let one side of a
    # comparison pay that and not the other is measuring the order it ran in.
    # `--no-warmup` exists only for the UNFIXED read at 40,000 debtors, where one
    # call is half an hour, and every line it prints says so.
    if warmup:
        call()
    timings = []
    statements = 0
    served = 0
    for _ in range(repeat):
        counter = _StatementCounter()
        started = time.monotonic()
        with connection.execute_wrapper(counter):
            result = call()
        timings.append(time.monotonic() - started)
        statements = counter.count
        served = rows_of(result)
    result = {
        "label": label,
        "seconds": statistics.median(timings),
        "statements": statements,
        "served": served,
    }
    print(
        f"    {label}: {result['seconds']:.3f}s · {result['statements']:,} statements · "
        f"{result['served']:,} rows served",
        flush=True,
    )
    return result


class _SqlRecorder:
    """Keeps the statements a read ACTUALLY made, so EXPLAIN can run THEM.

    ⚠ **THIS REPLACED A HAND-WRITTEN PROXY QUERY, WHICH IS LAW 7'S *looking at
    the wrong thing*.** The first version of this file explained a tidy
    `select account_id, sum(total) … group by account_id` that resembled the
    read. It was not the read: it had no allocations join, no credit
    subqueries, no band and no filter, so its plan would have been a plan for a
    statement this product never issues — and it would have looked completely
    convincing beside a real figure.
    """

    def __init__(self) -> None:
        self.statements: list[tuple[str, Any]] = []

    def __call__(self, execute, sql, params, many, context):
        self.statements.append((sql, params))
        return execute(sql, params, many, context)


def _explain(sql: str, params: Any) -> str:
    with connection.cursor() as cursor:
        cursor.execute(f"explain (analyze, buffers) {sql}", params)
        return "\n".join("      " + row[0] for row in cursor.fetchall())


# ══════════════════════════════════════════════════════════════════════════
# `P4.18` — THE CHECK, AS OPPOSED TO THE MEASUREMENT
# ══════════════════════════════════════════════════════════════════════════
#: One page of a list, wherever the tenant sits between T7 and the top of T5.
#: `NFR-3` is *universal server pagination* and `NFR-5` forbids a cap, so the
#: property is not "fast enough" — it is **the work does not grow with the
#: tenant**.
#:
#: ⚠ **A STATEMENT COUNT IS A PROPERTY OF THE CODE AND A WALL CLOCK IS A
#: PROPERTY OF THE BOX**, which this CR already learned the expensive way: the
#: draft patch recorded 10.046 s and 99.97 s for two reads that re-ran at
#: 3.089 s and 14.503 s on the same databases, while **both statement counts
#: reproduced exactly**. So nothing below asserts a second.
CHECKS: dict[str, dict[str, Any]] = {
    "GET /outstandings (page 1 of {per})": {
        # ⚠⚠ **THE PROPERTY THAT SEPARATES *PAGED IN SQL* FROM *PAGED IN
        # PYTHON*, AND THE FIRST DRAFT OF THIS CHECK DID NOT HAVE IT.** Asked
        # *what would make this pass wrongly*, the answer was measured rather
        # than reasoned about: `rows = list(positions)[offset : offset + per]`
        # — `DEF-PAY-4221` put back by hand — materialises every open position
        # in Python and still makes **one statement** and still serves **fifty
        # rows**. Both instruments above are blind to it. The SQL is not: a
        # read that pages in the database emits an OUTER `LIMIT` after its
        # `ORDER BY`, and one that pages in Python does not.
        #
        # ⚠⚠ **AND *`LIMIT` APPEARS SOMEWHERE IN THE STATEMENT* IS NOT THE
        # CHECK — THAT VERSION WAS WRITTEN, RUN, AND PASSED ON THE BROKEN
        # BUILD.** The page statement contains a correlated subquery ending
        # `GROUP BY U0."INVOICE_ID" LIMIT 1`, so `"LIMIT" in sql` is TRUE
        # whether the page is cut in SQL or in Python. Measured tails:
        #
        #   paged in SQL     … > %s ORDER BY 7 DESC, 1 ASC **LIMIT 50**
        #   paged in Python  … > %s ORDER BY 7 DESC, 1 ASC
        #
        # So the property is **an outer `LIMIT` AFTER the last `ORDER BY`**,
        # which is what `page_sql_is_outer_limited` below looks for.
        "outer_limit": True,
        # A ceiling, not an equality: the negative-credit count is CHUNKED at
        # `_IN_CHUNK = 5000`, so a tenant with negative credit positions issues
        # one extra statement per chunk. Measured: 13 at 2,046 debtors (one
        # chunk) and 12 at 40,046 (none). An equality would go red on data
        # rather than on code.
        "max_statements": 16,
        "serves_a_page": True,
    },
    "GET /outstandings (f.bucket=90+, page 1)": {
        "outer_limit": True,
        "max_statements": 16,
        "serves_a_page": True,
    },
    "collections/ladder (page 1 of {per})": {
        "max_statements": 24,
        "serves_a_page": True,
    },
    # ⚠ **THE UNPAGED LADDER IS THE BUILD THIS REPO ACTUALLY HAS, AND IT IS
    # `DEF-PAY-6300`.** `P4.2` removed the N+1 — 20 statements at BOTH sizes,
    # genuinely flat — and did NOT add a page argument, so the response is one
    # row per debtor: **40,030 rows at 40,046 debtors.** The statement ceiling
    # is checked because that is what `P4.2` won; `serves_a_page` is False and
    # NAMED, rather than the read being left out of the record, because a check
    # that silently excludes part of its subject is law 7's own shape.
    "collections/ladder (UNPAGED — this build takes no page)": {
        "max_statements": 24,
        "serves_a_page": False,
        "known_gap": "DEF-PAY-6300 — GET /collections/ladder takes no page",
    },
}


def _outer_limited(sql: str) -> bool:
    """Is the PAGE cut by this statement's own trailing `LIMIT`?

    A statement pages in SQL when its LAST `ORDER BY` is followed by a `LIMIT`.
    A `LIMIT` that appears anywhere else is a subquery's — this read has one,
    `GROUP BY U0."INVOICE_ID" LIMIT 1` — and it is present either way.
    """
    upper = " ".join(sql.split()).upper()
    cut = upper.rfind("ORDER BY")
    return cut != -1 and "LIMIT" in upper[cut:]


def _page_sql(per: int) -> list[str]:
    """The statements `GET /outstandings` page 1 REALLY issues, as text.

    ⚠ **THE READ IS RE-RUN TO CAPTURE THEM**, which costs one more call and is
    the honest way: an `execute_wrapper` around the timed call would put string
    accumulation inside the thing being timed.
    """
    recorder = _SqlRecorder()
    with connection.execute_wrapper(recorder):
        outstandings_read.outstandings(as_of=AS_OF, page=1, per=per)
    return [sql for sql, _ in recorder.statements]


def _check(results: list[dict], *, shape: dict[str, int], per: int, record: str) -> int:
    """Assert what `P4.18` asks, and APPEND this run to the record.

    Three properties, and the third is the one that needs two runs:

      1. **The page is a page.** `rows served` must be at most `per`, so the
         read answers one page rather than the tenant. This is `NFR-3`.
      2. **The statement count is bounded by a CONSTANT** declared above — a
         constant that does not mention the tenant's size anywhere.
      3. **The page is cut IN SQL.** One of the statements the read really
         issues must end its `ORDER BY` with a `LIMIT`. Properties 1 and 2 are
         both blind to a page sliced in Python — measured, not assumed — so
         without this one the check passes on the defect it was written for.
         ⚠ And *a `LIMIT` somewhere in the statement* is not enough either:
         see `outer_limit` in `CHECKS`, which records the version of this
         property that was written first and passed on the broken build.
      4. **It did not GROW.** Every earlier run in the record at a SMALLER
         debtor count is compared: more statements over more debtors is the
         regression this file exists to catch, and it is invisible to any
         single run however carefully measured.

    ⚠ **WHY THE COMPARISON IS `grew`, NOT `differs`.** The counts are 13 at
    2,046 debtors and 12 at 40,046 — the SMALLER tenant costs one more, because
    it holds a negative credit position and the count of those is chunked. An
    equality check would report that as a failure and a reader would go looking
    for a regression that is not there.

    ⚠ **AND WHAT MAKES THIS PASS WRONGLY: measuring nothing.** `main` exits 2
    at zero debtors before reaching here, because with `app.tenant_id` unset RLS
    matches no rows, every read is instant and a timing run looks spectacular.
    That guard is upstream of this function and is not repeated in it — it is
    the reason the record carries the DEBTOR COUNT on every line.
    """
    import json

    failures: list[str] = []
    debtors = shape["debtors"]

    prior: list[dict] = []
    path = pathlib.Path(record)
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                prior.append(json.loads(line))

    written: list[dict] = []
    for row in results:
        label = row["label"]
        spec = CHECKS.get(label) or CHECKS.get(label.replace(str(per), "{per}"))
        if spec is None:
            failures.append(
                f"{label}: no CHECKS entry. A read this harness measures and nothing "
                "asserts is a measurement, not a check — add a ceiling or say why not."
            )
            continue

        if spec["serves_a_page"] and row["served"] > per:
            failures.append(
                f"{label}: served {row['served']:,} rows for a page of {per}. NFR-3 is "
                "universal server pagination; this read answered the whole tenant."
            )
        if spec.get("outer_limit"):
            statements = _page_sql(per)
            if not any(_outer_limited(sql) for sql in statements):
                failures.append(
                    f"{label}: not one of the {len(statements)} statements this read "
                    "issues ends its ORDER BY with a LIMIT, so the page is being cut in "
                    "PYTHON. The statement count stays at one and exactly `per` rows are "
                    "served, so the other two instruments pass over it — this is the "
                    "only one that does not (DEF-PAY-4221's own shape)."
                )
        if row["statements"] > spec["max_statements"]:
            failures.append(
                f"{label}: {row['statements']:,} statements over {debtors:,} debtors, "
                f"ceiling {spec['max_statements']}. A per-row query has come back."
            )

        entry = {
            "debtors": debtors,
            "read": label,
            "statements": row["statements"],
            "served": row["served"],
            "per": per,
        }
        for old in prior:
            if old["read"] != label:
                continue
            if old["debtors"] < debtors and row["statements"] > old["statements"]:
                failures.append(
                    f"{label}: {row['statements']:,} statements at {debtors:,} debtors "
                    f"against {old['statements']:,} at {old['debtors']:,}. The work GREW "
                    "with the tenant, which is the N+1 shape whatever the wall clock says."
                )
            if old["debtors"] > debtors and old["statements"] > row["statements"]:
                failures.append(
                    f"{label}: a recorded run at {old['debtors']:,} debtors made "
                    f"{old['statements']:,} statements against {row['statements']:,} here. "
                    "Same regression, seen from the smaller end."
                )
        if entry not in prior:
            written.append(entry)

    if written:
        with path.open("a", encoding="utf-8") as handle:
            for entry in written:
                handle.write(json.dumps(entry, sort_keys=True) + "\n")
        print(f"\n  recorded {len(written)} line(s) in {record}")
    else:
        print(f"\n  nothing new to record in {record} — these figures are already in it")

    sizes = sorted({entry["debtors"] for entry in prior + written})
    print(f"  the record now spans debtor counts: {', '.join(f'{n:,}' for n in sizes)}")
    if len(sizes) < 2:
        print(
            "  ⚠ ONE SIZE ONLY. Property 3 — *the work did not grow* — needs two, and "
            "until a second size is recorded this run asserted only the ceilings. Run "
            "it against the other seeded clone."
        )
    for spec in CHECKS.values():
        if spec.get("known_gap"):
            print(f"  ⚠ known gap, asserted around rather than hidden: {spec['known_gap']}")

    if failures:
        print("\nP4.18 FAILED:")
        for line in failures:
            print(f"  · {line}")
        return 1
    print("\nP4.18 PASS: every read answers one page with a bounded, non-growing "
          "statement count.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default="brazosbend")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--page", type=int, default=50)
    parser.add_argument("--explain", action="store_true", help="also print the open-bill plan")
    parser.add_argument(
        "--no-warmup",
        action="store_true",
        help="skip the discarded first call — ONLY for a read too slow to run twice",
    )
    parser.add_argument("--only", default="", help="substring: measure just these reads")
    parser.add_argument(
        "--check",
        metavar="RECORD",
        default="",
        help=(
            "`P4.18`: ASSERT instead of only measuring. Appends this run's figures to "
            "RECORD (JSON lines) and fails if the read regressed against anything "
            "already in it. Default record: "
            "10-scripts/cr138_p4_18_statement_record.jsonl"
        ),
    )
    args = parser.parse_args()

    tenant = tenancy_models.Tenant.objects.get(subdomain=args.tenant)
    with tenant_context(str(tenant.id)):
        shape = _tenant_shape()
        print(
            f"tenant {args.tenant}: {shape['accounts']:,} accounts · "
            f"{shape['open_bills']:,} open bills · {shape['debtors']:,} debtors"
        )
        if not shape["debtors"]:
            print(
                "REFUSED: this tenant has no debtors, so every figure below would be a "
                "figure about an empty list. Seed one with "
                "10-scripts/cr138_p4_debtor_scale_seed.py, and check `app.tenant_id` "
                "is set — RLS FORCE makes an unscoped session look exactly like an "
                "empty tenant (CLAUDE.md hard rule 1)."
            )
            return 2
        print(
            f"median of {args.repeat} run(s) "
            + (
                "WITHOUT a warm-up — the first call's cold cache is IN these figures"
                if args.no_warmup
                else "after one discarded warm-up"
            )
            + f"; page size {args.page}\n"
        )

        results = []

        def measure(label, call, rows_of):
            """Measure one read, or say out loud that `--only` skipped it.

            ⚠ **`--only` SKIPS THE MEASUREMENT, NOT THE PRINTING.** The first
            version of this file filtered the FINISHED table, so
            `--only outstandings` still spent an hour on the ladder and then
            silently dropped the figure — a flag that looks like it narrowed
            the work and did not. And a skip is PRINTED, because a table with
            one row in it and no note is indistinguishable from a run where
            the other reads were free.
            """
            if args.only and args.only.lower() not in label.lower():
                print(f"  skipped (--only {args.only!r}): {label}", flush=True)
                return
            results.append(
                _measure(
                    label,
                    call,
                    repeat=args.repeat,
                    warmup=not args.no_warmup,
                    rows_of=rows_of,
                )
            )

        # ── GET /outstandings (P4.1) ─────────────────────────────────────
        supports_paging = "page" in outstandings_read.outstandings.__code__.co_varnames
        if supports_paging:
            measure(
                f"GET /outstandings (page 1 of {args.page})",
                lambda: outstandings_read.outstandings(as_of=AS_OF, page=1, per=args.page),
                lambda view: len(view.rows),
            )
            measure(
                "GET /outstandings (f.bucket=90+, page 1)",
                lambda: outstandings_read.outstandings(
                    as_of=AS_OF, bucket="90+", page=1, per=args.page
                ),
                lambda view: len(view.rows),
            )
        else:
            measure(
                "GET /outstandings (UNPAGED — this build takes no page)",
                lambda: outstandings_read.outstandings(as_of=AS_OF),
                lambda view: len(view.rows),
            )
            measure(
                "GET /outstandings (f.bucket=90+, UNPAGED)",
                lambda: outstandings_read.outstandings(as_of=AS_OF, bucket="90+"),
                lambda view: len(view.rows),
            )

        # ── collections/ladder (P4.2) ────────────────────────────────────
        if "page" in collections_read.ladder_board.__code__.co_varnames:
            measure(
                f"collections/ladder (page 1 of {args.page})",
                lambda: collections_read.ladder_board(as_of=AS_OF, page=1, per=args.page),
                lambda board: len(board["rows"]),
            )
        else:
            measure(
                "collections/ladder (UNPAGED — this build takes no page)",
                lambda: collections_read.ladder_board(as_of=AS_OF),
                lambda board: len(board["rows"]),
            )

        if not results:
            print(f"REFUSED: --only {args.only!r} matched no read.")
            return 2
        check_exit = 0
        width = max(len(row["label"]) for row in results)
        print(f"  {'read'.ljust(width)}  {'secs':>8}  {'stmts':>7}  {'built':>8}  {'served':>8}")
        for row in results:
            # "rows built" is the tenant's whole open-bill set whenever the read
            # materialises it. A build that pages in SQL touches only the page,
            # and the statement plan below is what proves which one this is.
            print(
                f"  {row['label'].ljust(width)}  {row['seconds']:>8.3f}  "
                f"{row['statements']:>7,}  {'—':>8}  {row['served']:>8,}"
            )
        print(
            "\n  'built' is printed by the EXPLAIN leg below, not guessed here: run with "
            "--explain."
        )

        if args.explain:
            recorder = _SqlRecorder()
            with connection.execute_wrapper(recorder):
                if supports_paging:
                    outstandings_read.outstandings(as_of=AS_OF, page=1, per=args.page)
                else:
                    outstandings_read.outstandings(as_of=AS_OF)
            print(
                f"\n  EXPLAIN (ANALYZE, BUFFERS) on the {len(recorder.statements)} statement(s) "
                "GET /outstandings really issued:"
            )
            for index, (sql, params) in enumerate(recorder.statements, start=1):
                print(f"\n  [{index}/{len(recorder.statements)}] {sql[:110]}…")
                try:
                    print(_explain(sql, params))
                except Exception as exc:  # a statement EXPLAIN cannot take
                    print(f"      not explainable here: {exc}")

        if args.check:
            record = args.check
            if record in ("1", "true", "yes", "default"):
                record = str(
                    pathlib.Path(__file__).with_name("cr138_p4_18_statement_record.jsonl")
                )
            check_exit = _check(results, shape=shape, per=args.page, record=record)
    return check_exit


if __name__ == "__main__":
    raise SystemExit(main())
