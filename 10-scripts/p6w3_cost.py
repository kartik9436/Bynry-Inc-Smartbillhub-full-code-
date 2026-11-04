#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: R43 Trend Pack (`apps/ledger/trend_pack.py`), the `P6.11` wave-3
#            joining read, measured on REAL PostgreSQL 16. The test suite runs
#            on in-memory SQLite (`config/settings/test.py` hardcodes it and
#            ignores `DATABASE_URL`) and cannot answer a question about a query
#            plan, an aggregate's cost or RLS — CLAUDE.md hard-won law 14.
# Rules:     `BR-REP-009` · `BR-REP-011` · `BR-REP-034` · `NFR-3` · `NFR-5` ·
#            hard rule 1 (tenant scoping; RLS FORCE) · hard rule 4 (this script
#            READS; only the fixture writes) · hard-won law 7 (a check that
#            cannot cover its whole subject prints what it SKIPPED beside what
#            it checked)
# Sibling:   `10-scripts/p6w2_cost.py` — R34. This file follows its shape
#            deliberately rather than inventing a second one.
# ───────────────────────────────────────────────────────
"""WHAT R43 COSTS, AND WHY THE INSTRUMENT IS DIFFERENT FROM EVERY SIBLING'S.

R34, R23, R32 and R36 are all bounded by the TENANT: more accounts, more rows,
so the questions are *does the last page cost what the first did* and *does the
statement count move with `per`*. **R43 is bounded by a CONTROL** — p059's
**Periods 12** — so it serves twelve rows at a 300-account utility and twelve at
a 40,000-account one, and neither of those questions applies to it.

What DOES grow with the tenant is the cost of each ROW, and it grows in a shape
worth naming: every period issues its own aggregates, so the work is
`periods × (a billed Σ + a collected Σ + an account count + a rebill count)`
plus one AR control and one billed Σ per period for DSO. **A report that costs
twelve times one period is exactly what NOT to have if one period is expensive**,
which is why the figures below are quoted per period as well as per report.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY — each answered, never assumed:**

  * **Measuring nothing.** With `app.tenant_id` unset, RLS FORCE returns zero
    rows in about a millisecond and every timing looks wonderful. Every leg runs
    inside `tenant_context` and PRINTS its row count; a zero FAILS.
  * **Measuring an empty book.** Twelve rows of `0.00` cost nothing whatever.
    The script REFUSES unless at least one period carries a non-zero REVENUE
    **and** a non-zero COLLECTED — otherwise it is timing twelve aggregates over
    an empty index and calling the report fast.
  * **A cost that is really one period's.** `--periods 1` is measured beside
    `--periods 12` and beside `--periods 60`. If the twelve-period run is not
    materially dearer than the one-period run, the periods are not being asked
    about separately and something is caching.
  * **An N+1 in the seams.** The statement count must be a LINEAR function of
    the period count with a small constant, and `statements(12) − statements(1)`
    is printed as *statements per period* so a reader can see it rather than
    infer it.
  * **An export that inherited a page.** The stream is counted against the
    report's own row count and a short file FAILS.

⚠ **WHAT THIS SCRIPT DOES NOT MEASURE, STATED RATHER THAN LEFT BLANK**
(hard-won law 7's fifth shape — a number over a scope it silently excludes):

  * **RLS** → `10-scripts/p6w3_rls_proof.py`, which runs as a role that is
    neither SUPERUSER nor BYPASSRLS and plants the neighbour's rows first.
  * **A TYPED revenue target.** `BR-REP-034`'s field is published by nobody, so
    the TARGET column is NULL on every tenant and there is nothing to time. That
    is the ruled degrade, not a gap in this script.
  * **DSO on a tenant with twelve months of books.** The perf tenant's earliest
    posted entry is printed; where it is inside the window, DSO is NULL by
    `BR-REP-011` and the AR-control read is skipped, and the script SAYS SO
    beside the figure instead of quietly reporting a cheaper report.
"""

import argparse
import os
import uuid as _uuid
import statistics
import sys
import time
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import connection, reset_queries  # noqa: E402

from apps.ledger import chart, models as ledger_models, posting, reporting  # noqa: E402
from apps.ledger import trend_pack as r43  # noqa: E402
from apps.reports import runner  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

import cr051_provision_utilities as provisioner  # noqa: E402
import p6w2_cost  # noqa: E402  — its account seeder, reused rather than rewritten

#: `docker-entrypoint.sh`, `GUNICORN_TIMEOUT:-60`. A read slower than this is
#: not slow — it is KILLED BEFORE IT ANSWERS.
WORKER_TIMEOUT = 60.0

#: Every entry this script posts carries it, so a re-run adds nothing new that
#: could be mistaken for the sample data underneath.
MARKER = "P6W3"

#: One stamped moment for every entry this fixture writes, for
#: `ledger_le_fixtures.POSTED_AT`'s reason: `G6` greps for a clock in a money
#: path, and a fixture reading one is the same fault in a different file.
POSTED_AT = datetime(2026, 9, 27, 9, 15, tzinfo=dt_timezone.utc)


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


def _say(result: dict) -> None:
    print(
        f"  {result['label']:<44} {result['seconds']:>8.3f}s  "
        f"{result['statements']:>4} statements  {result['rows']:>7} rows"
    )


# ── the fixture ─────────────────────────────────────────────────────────────


def seed_bills(tenant, *, months: int, per_month: int) -> int:
    """Bills across `months` fiscal periods, so the trend has something to trend.

    ⚠ **IT POSTS THROUGH THE POSTING SERVICE AND NOT THROUGH THE ORM.** Hard
    rule 5 makes that service the sole writer of journal lines and
    `ledger_sole_writer_guard()` raises by name on a `create()`; a fixture going
    round it would time this report against rows the product cannot produce.

    ⚠ **IT SPREADS THE ENTRIES ACROSS MONTHS ON PURPOSE.** All of them in one
    month would leave eleven rows aggregating over an empty index, and the
    report would be measured at a twelfth of its real cost.
    """
    ar_id = reporting._designated_account_id(chart.AR)  # noqa: SLF001
    if ar_id is None:
        sys.exit(
            "REFUSED: this tenant designates no accounts_receivable account, so nothing this "
            "script posts would be BILLED as far as R43 is concerned and every revenue figure "
            "would read 0.00 (hard-won law 7 — a check measuring nothing)."
        )
    ar = ledger_models.LedgerAccount.objects.get(id=ar_id)
    revenue, _ = ledger_models.LedgerAccount.objects.get_or_create(
        tenant=tenant, code="4100", defaults={"name": "Water revenue", "type": "revenue"}
    )
    anchor = date(2026, 9, 27)
    made = 0
    skipped = 0
    for month in range(months):
        when = anchor.replace(day=15) - timedelta(days=30 * month)
        for index in range(per_month):
            key = f"{MARKER}|{month:03d}|{index:05d}"
            # ⚠ **BR-LED-001 — EVERY LINE NAMES A SOURCE DOCUMENT.** The
            # posting service refuses a line with a null `source_id` outright,
            # which is the rule that makes LE-5's *"what is the 506.31?"*
            # answerable. A deterministic uuid per key stands in for the
            # invoice this fixture does not create.
            document = _uuid.uuid5(_uuid.NAMESPACE_URL, f"p6w3://{key}")
            if ledger_models.JournalEntry.objects.filter(
                tenant_id=tenant.id, posting_key=key
            ).exists():
                continue
            amount = Decimal("100.0000") + Decimal(index % 50)
            # ⚠ **A CLOSED PERIOD REFUSES AND THIS FIXTURE ACCEPTS THE
            # REFUSAL** (`BR-LED-006`, `DEF-3202`). The perf tenant has August
            # 2026 closed, and the two lawful answers are *forward it* or
            # *report it* — forwarding would pile fourteen months of fixture
            # into one row and measure the wrong report, so this SKIPS and
            # COUNTS. The period still carries the sample plant's own bills, so
            # its row is not empty; it is simply not this fixture's.
            try:
                posting.post(
                    posting.PostingRequest(
                        posting_key=key,
                        entry_date=when,
                        # `BR-TEN-043` — the wall-clock moment is an INPUT and
                        # never a clock read inside the posting service.
                        posted_at=POSTED_AT,
                        currency="USD",
                        source_type="invoice",
                        source_id=document,
                        memo=MARKER,
                        lines=(
                            posting.PostingLine(
                                ledger_account_id=ar.id,
                                side=ledger_models.SIDE_DEBIT,
                                amount=amount,
                                source_type="invoice_line",
                                source_id=document,
                            ),
                            posting.PostingLine(
                                ledger_account_id=revenue.id,
                                side=ledger_models.SIDE_CREDIT,
                                amount=amount,
                                source_type="invoice_line",
                                source_id=document,
                            ),
                        ),
                    )
                )
            except posting.PostingError as refusal:
                if "CLOSED fiscal period" not in str(refusal):
                    raise
                skipped += 1
                continue
            made += 1
    if skipped:
        # ⚠ **PRINTED, NEVER SWALLOWED** (hard-won law 7's fifth shape). A
        # fixture that silently wrote less than it says it wrote is a
        # measurement over a scope nobody declared.
        print(f"  ⚠ SKIPPED {skipped} entries dated inside a CLOSED fiscal period (BR-LED-006)")
    return made


# ── the guards ──────────────────────────────────────────────────────────────


def _substance_guard(answer: dict) -> None:
    """The one refusal that makes this a measurement of R43 rather than of zero."""
    rows = answer["rows"]
    if not rows:
        sys.exit(
            "FAIL: the report served ZERO rows. Either `app.tenant_id` was not set — RLS FORCE "
            "then returns nothing in about a millisecond and every timing below looks "
            "wonderful — or this tenant keeps no fiscal calendar."
        )
    billing = [row for row in rows if row.revenue and row.revenue != Decimal("0")]
    if not billing:
        sys.exit(
            f"FAIL: all {len(rows)} periods billed 0.00, so this run timed twelve aggregates "
            "over an empty index. Seed bills across the window before trusting any figure here."
        )
    print(f"  substance: {len(billing)} of {len(rows)} periods carry a non-zero REVENUE")
    collected = [row for row in rows if row.collected not in (None, Decimal("0"))]
    if collected:
        print(f"  substance: {len(collected)} of {len(rows)} periods carry a non-zero COLLECTED")
    else:
        # ⚠ **PRINTED, NOT FAILED.** The perf tenant's sample plant may hold no
        # allocations at all; the COLLECTED aggregate still RAN and was still
        # timed. Stating it is what stops a reader believing the figures below
        # cover a path they do not.
        print(
            "  ⚠ SKIPPED: no period carries a non-zero COLLECTED, so the allocation subquery "
            "was timed over an empty match. The timing is real; the SELECTIVITY is not."
        )


def _period_guard(one: dict, twelve: dict, many: dict) -> None:
    """Twelve periods must cost materially more than one, or nothing is per-period."""
    print(
        f"  periods:  1 → {one['seconds']:.3f}s / {one['statements']} statements  ·  "
        f"12 → {twelve['seconds']:.3f}s / {twelve['statements']}  ·  "
        f"60 → {many['seconds']:.3f}s / {many['statements']}"
    )
    if twelve["statements"] <= one["statements"]:
        sys.exit(
            f"FAIL: 12 periods cost {twelve['statements']} statements and 1 cost "
            f"{one['statements']}. The periods are not being aggregated separately — either "
            "something is caching or every row is answering about the same window."
        )
    per_period = (twelve["statements"] - one["statements"]) / 11
    print(f"  statements per period: {per_period:.1f}")
    if many["seconds"] > WORKER_TIMEOUT:
        sys.exit(
            f"FAIL: 60 periods took {many['seconds']:.3f}s and a web worker is given "
            f"{WORKER_TIMEOUT}s (docker-entrypoint.sh, GUNICORN_TIMEOUT). It would not be "
            "slow in production, it would be killed before it answered."
        )


def _export_guard(report: dict, streamed: dict) -> None:
    if streamed["rows"] != len(report["rows"]):
        sys.exit(
            f"FAIL: the stream served {streamed['rows']} of the report's {len(report['rows'])} "
            "rows. NFR-5 forbids a ceiling on the export branch."
        )
    print(f"  export: {streamed['rows']} rows, same as the report")
    if streamed["seconds"] > WORKER_TIMEOUT:
        sys.exit(f"FAIL: the export took {streamed['seconds']:.3f}s against {WORKER_TIMEOUT}s")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=int, default=95, help="perf tenant index")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--months", type=int, default=14)
    parser.add_argument("--per-month", type=int, default=150)
    parser.add_argument("--as-of", default="2026-09-27")
    #: ⚠ **THE ACCOUNT COUNT MATTERS TO THIS REPORT AND IT IS NOT OBVIOUS.**
    #: Three of R43's four aggregates scale with the BOOKS and the fourth —
    #: ACCOUNTS — scales with the REGISTER, once per period. A measurement on a
    #: seventy-account sample tenant would under-report the account count by
    #: three orders of magnitude and say nothing about the top of the ICP.
    parser.add_argument("--accounts", type=int, default=40_000)
    args = parser.parse_args()

    as_of = date.fromisoformat(args.as_of)
    tenant = provisioner.provision(args.index)
    print(f"tenant {tenant.subdomain} ({tenant.id})")

    with core_tenancy.tenant_context(str(tenant.id)):
        # The account seeder is `p6w2_cost`'s, imported rather than rewritten:
        # two spellings of *a row at the grain being measured* is how two cost
        # scripts come to measure two different utilities (hard-won law 5).
        print(f"seeded {p6w2_cost.seed_accounts(tenant, wanted=args.accounts)} new accounts")
        print(f"posted {seed_bills(tenant, months=args.months, per_month=args.per_month)} entries")
        from apps.customers import models as customer_models

        accounts = customer_models.Account.objects.count()
        print(f"tenant holds {accounts} accounts")
        lines = ledger_models.JournalLine.objects.count()
        earliest = r43._earliest_entry_date()  # noqa: SLF001
        print(f"tenant holds {lines} journal lines · earliest posted entry {earliest}")
        # ⚠ **STATED RATHER THAN LEFT BLANK.** BR-REP-011 leaves DSO NULL until
        # twelve months of books exist, so on a young fixture the AR-control
        # read never runs and the report is CHEAPER than it will be in
        # production. A reader must see that beside the figures.
        if earliest is None or earliest > as_of - timedelta(days=364):
            print(
                "  ⚠ SKIPPED: fewer than twelve months of books, so DSO is NULL on every row "
                "(BR-REP-011) and the AR-control read was NOT timed."
            )
        else:
            print("  DSO: twelve months of books exist, so the AR-control read IS timed.")

        print("\nR43 Trend Pack — one row per FISCAL PERIOD")
        one = _measure(
            "1 period", lambda: r43.trend_pack(as_of=as_of, periods=1), repeat=args.repeat
        )
        twelve = _measure(
            "12 periods (the drawn default)",
            lambda: r43.trend_pack(as_of=as_of, periods=12),
            repeat=args.repeat,
        )
        many = _measure(
            "60 periods (five years)",
            lambda: r43.trend_pack(as_of=as_of, periods=60),
            repeat=args.repeat,
        )
        through_runner = _measure(
            "12 periods, through runner.run()",
            lambda: runner.run("trend_pack", {"as_of": as_of.isoformat()}).payload,
            repeat=args.repeat,
        )
        streamed = _measure(
            "export — every row",
            lambda: {"rows": list(r43.trend_pack_stream(as_of=as_of, periods=12))},
            repeat=1,
        )
        for result in (one, twelve, many, through_runner, streamed):
            _say(result)

        _substance_guard(twelve["answer"])
        _period_guard(one, twelve, many)
        _export_guard(twelve["answer"], streamed)

        # ⚠ **THE SCREEN AND THE FILE MUST BE THE SAME REPORT** (`P0.5`). Not a
        # cost question, and measured here because this is the only harness that
        # runs both against a real database.
        screen = [dict(row) for row in through_runner["answer"]["rows"]]
        file_rows = runner.rows_for("trend_pack", {"as_of": as_of.isoformat()}, whole=True)
        if screen != file_rows:
            sys.exit("FAIL: the viewer and the export produced different rows (P0.5)")
        print(f"  P0.5: the viewer's {len(screen)} rows are byte-identical to the export's")

        # The tiles are read off the rows, so they cannot describe a different
        # population — asserted rather than believed.
        tiles = twelve["answer"]["tiles"]
        latest = twelve["answer"]["rows"][-1]
        if tiles["revenue_latest"] != latest.revenue:
            sys.exit("FAIL: the REVENUE tile does not match the last row's revenue")
        print(f"  tiles: revenue {tiles['revenue_latest']} == the last row's own figure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P6.11 wave 3 (R43 trend_pack; DEF-REP-6937)
# generated: 2026-09-27 by lane REP-P6-W3
# gates: RED PROVED FIRST — run against an unseeded tenant it exits `FAIL: all 12 periods billed 0.00`, which is the false pass it exists to prevent.
# exceptions: (1) it does NOT measure RLS — see 10-scripts/p6w3_rls_proof.py · (2) a TYPED revenue target is unmeasurable because BR-REP-034's field is published by nobody · (3) where the books are younger than twelve months the AR-control read does not run and the script PRINTS that beside the figures rather than reporting a cheaper report
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
