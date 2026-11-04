#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: the `journal_lines` DATASET QUERY
#            (`06-backend/apps/ledger/journal_lines_dataset.py`) measured on
#            REAL PostgreSQL 16, because the test suite runs on in-memory
#            SQLite and cannot answer a question about LIMIT/OFFSET, RLS or an
#            aborted transaction (CLAUDE.md hard-won law 14).
# Rules:     `NFR-3` (universal server pagination — in SQL, never in Python) ·
#            `NFR-5` (no hard caps anywhere) · CLAUDE.md hard rule 1 (tenant
#            scoping; RLS FORCE and the app role is neither superuser nor
#            BYPASSRLS) · hard rule 5 (ONLY the posting service writes journal
#            lines — every fixture row below goes through `posting.post()`) ·
#            hard-won law 7 (a check that cannot cover its whole subject prints
#            what it SKIPPED beside what it checked).
# ───────────────────────────────────────────────────────
"""WHAT ONE PAGE OF THE JOURNAL COSTS — three instruments, because one lies.

`10-scripts/cr138_p4_debtor_cost.py` learned this the expensive way and its
lesson is copied rather than re-learned: **a wall clock alone cannot answer an
`NFR-3` question.** At a small tenant every figure is dominated by fixed
overhead, so the same two milliseconds come back before and after a change that
removed 98% of the work. And **a statement count alone cannot answer it
either**, because a read can hold its statement count flat while the ROWS those
statements build grow with the tenant. So three columns, and a reader needs all
three:

  **statements**   round trips. An N+1 shows here and nowhere else.
  **rows served**  what the caller got back — the PAGE on a paged read.
  **seconds**      median of `--repeat`, after a discarded warm-up.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY — each answered, never assumed:**

  * **Measuring nothing.** RLS FORCE is on and the app role is neither
    superuser nor BYPASSRLS, so with `app.tenant_id` unset every query returns
    zero rows in about a millisecond and every timing here would look
    wonderful. Every measurement runs inside `tenant_context` and **prints the
    row count it served**; a zero is a failure, not a fast answer.
  * **Timing a page that is not the expensive one.** Page 1 of an unpaged read
    is cheap because there is only one page. So the LAST page is measured too,
    which is where an in-Python slice shows: a SQL `OFFSET` walk is flat, a
    Python slice that materialised everything first is not.
  * **Proving the wrong thing green.** The balanced pair is asserted here as
    well as in the suite: Σ debits must equal Σ credits over the unfiltered
    window, and a difference other than zero FAILS this script by name.

⚠ **THE FIXTURE IS POSTED, NOT INSERTED.** Hard rule 5 gives `journal_lines`
one writer. `ledger_sole_writer_guard()` raises by name on anything else, so
every entry below is built as a balanced `PostingRequest` and handed to
`posting.post()`. Its date goes through `close.resolve_entry_date` first —
BR-TEN-038 — so a fixture aimed at a closed period is auto-forwarded to the
earliest open one instead of being refused.

USAGE
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_dsledger \\
      python3 ../10-scripts/ds_ledger_journal_lines_cost.py --entries 4000 --repeat 3
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from datetime import date, datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5
from decimal import Decimal
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "06-backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "true")

import django  # noqa: E402

django.setup()

from django.db import connection, reset_queries  # noqa: E402
from django.conf import settings  # noqa: E402

from apps.ledger import close, journal_lines_dataset, models as ledger_models, posting  # noqa: E402
from apps.ledger import reporting as ledger_reporting  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

import cr051_provision_utilities as provisioner  # noqa: E402

PAGE = 50


def _accounts() -> tuple[object, object]:
    """Two GL accounts to post between — the tenant's own, never invented.

    A code is looked up by DESIGNATION where the chart declares one and by
    TYPE otherwise; never by the literal `"1200"`, which is the latent
    misposting `apps/ledger/chart.py` exists to prevent and `OQ-106` was
    raised over.
    """
    asset = ledger_models.LedgerAccount.objects.filter(type="asset").order_by("code").first()
    revenue = ledger_models.LedgerAccount.objects.filter(type="revenue").order_by("code").first()
    if asset is None or revenue is None:
        sys.exit("REFUSED: this tenant's chart of accounts has no asset/revenue pair to post between")
    return asset, revenue


def seed(*, entries: int) -> int:
    """`entries` balanced two-line entries, POSTED. Returns how many were new."""
    asset, revenue = _accounts()
    made = 0
    day = date.today().replace(day=1) - timedelta(days=1)
    for index in range(entries):
        key = posting.posting_key(
            source_type="ds_ledger_fixture", source_id=f"jl-{index}", event="seeded"
        )
        if ledger_models.JournalEntry.objects.filter(posting_key=key).exists():
            continue
        # ⚠ BR-TEN-038 — a fixture aimed at a closed period is AUTO-FORWARDED
        # to the earliest open one with a note, never refused and never
        # silently landed in a locked month.
        wanted = day - timedelta(days=index % 60)
        entry_date, _note = close.resolve_entry_date(wanted)
        amount = Decimal("10.0000") + Decimal(index % 97)
        # ⚠ **BR-LED-001 — EVERY LINE NAMES A SOURCE DOCUMENT**, and
        # `posting._refuse_unless_postable` refuses a `source_id` of None BY
        # NAME. A fixture is not exempt: the rule is what makes LE-5's auditor
        # question answerable, and a fixture that went round it would be
        # measuring rows the product cannot produce. Derived with `uuid5` so a
        # replay of this script produces the same ids and the posting key's
        # replay guard can do its job.
        document = uuid5(NAMESPACE_URL, f"ds-ledger-fixture/{index}")
        request = posting.PostingRequest(
            posting_key=key,
            entry_date=entry_date,
            posted_at=datetime.now(timezone.utc),
            currency="USD",
            memo=f"DS-LEDGER fixture {index}",
            source_type="ds_ledger_fixture",
            source_id=document,
            lines=(
                posting.PostingLine(
                    ledger_account_id=asset.id,
                    side=ledger_models.SIDE_DEBIT,
                    amount=amount,
                    source_type="ds_ledger_fixture",
                    source_id=document,
                ),
                posting.PostingLine(
                    ledger_account_id=revenue.id,
                    side=ledger_models.SIDE_CREDIT,
                    amount=amount,
                    source_type="ds_ledger_fixture",
                    source_id=document,
                ),
            ),
        )
        result = posting.post(request)
        made += 1 if getattr(result, "created", False) else 0
    return made


def _measure(label: str, call, *, repeat: int) -> dict:
    """(statements, rows, median seconds) for one call, warm-up discarded."""
    previous = settings.DEBUG
    settings.DEBUG = True
    try:
        call()  # discarded warm-up — the first run pays for the connection
        timings: list[float] = []
        statements = 0
        rows = 0
        for _ in range(repeat):
            reset_queries()
            began = time.perf_counter()
            answer = call()
            timings.append(time.perf_counter() - began)
            statements = len(connection.queries)
            rows = len(answer["rows"])
        return {
            "label": label,
            "statements": statements,
            "rows": rows,
            "seconds": statistics.median(timings),
            "answer": answer,
        }
    finally:
        settings.DEBUG = previous


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entries", type=int, default=4000)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--index", type=int, default=90, help="perf tenant index")
    parser.add_argument("--explain", action="store_true")
    args = parser.parse_args()

    tenant = provisioner.provision(args.index)
    print(f"tenant {tenant.subdomain} ({tenant.id})")

    with core_tenancy.tenant_context(str(tenant.id)):
        made = seed(entries=args.entries)
        total_lines = ledger_models.JournalLine.objects.count()
        print(f"posted {made} new entries · {total_lines} journal lines in this tenant")
        if total_lines == 0:
            # hard-won law 7: a query returning nothing reads as "no error".
            sys.exit("REFUSED: zero journal lines — this would measure nothing at all")

        window = {"start": date(2000, 1, 1), "end": date(2100, 1, 1)}
        first = _measure(
            "page 1",
            lambda: journal_lines_dataset.journal_lines(page=1, per=PAGE, **window),
            repeat=args.repeat,
        )
        pages = first["answer"]["pages"]
        last = _measure(
            f"page {pages} (last)",
            lambda: journal_lines_dataset.journal_lines(page=pages, per=PAGE, **window),
            repeat=args.repeat,
        )
        whole = _measure(
            "per=None (the export branch)",
            lambda: journal_lines_dataset.journal_lines(per=None, **window),
            repeat=args.repeat,
        )

        print()
        print(f"{'read':<32}{'statements':>12}{'rows served':>14}{'seconds':>10}")
        for measured in (first, last, whole):
            print(
                f"{measured['label']:<32}{measured['statements']:>12}"
                f"{measured['rows']:>14}{measured['seconds']:>10.3f}"
            )

        totals = first["answer"]["totals"]
        print()
        print(f"Σ debits  {totals['debit']}")
        print(f"Σ credits {totals['credit']}")
        print(f"difference {totals['difference']}  ·  balanced={first['answer']['balanced']}")

        # ⚠ THE BALANCED PAIR, ASSERTED AND NAMED. R15's warning, verbatim:
        # a difference other than zero means the posting service has a defect,
        # not that the report needs tuning.
        if totals["difference"] != Decimal("0"):
            sys.exit(
                "FAIL — the books do not foot: Σ debits "
                f"{totals['debit']} vs Σ credits {totals['credit']}, difference "
                f"{totals['difference']}. BR-LED-007: this is a posting-service defect and a "
                "release blocker, never a figure this report adjusts."
            )
        if first["answer"]["balanced"] is not True:
            sys.exit("FAIL — an unfiltered window must state a verdict, and this one did not")

        # A PAGE MUST NOT BE THE WHOLE SET. The one false pass this measurement
        # has: a query that ignored `per` would time beautifully and serve
        # everything.
        if first["rows"] > PAGE:
            sys.exit(f"FAIL — page 1 served {first['rows']} rows against per={PAGE}")
        if whole["rows"] != total_lines:
            sys.exit(
                f"FAIL — `per=None` served {whole['rows']} of {total_lines} lines. NFR-5 "
                "forbids a ceiling on the export branch."
            )

        # SORTING IS IN SQL. Two directions over the same window must be
        # mirror images at the ends; a Python sort after a SQL page could not
        # be.
        ascending = journal_lines_dataset.journal_lines(
            page=1, per=PAGE, sort="amount", direction="asc", **window
        )
        descending = journal_lines_dataset.journal_lines(
            page=1, per=PAGE, sort="amount", direction="desc", **window
        )
        print(
            f"sort amount asc first={ascending['rows'][0].amount} "
            f"desc first={descending['rows'][0].amount}"
        )
        # ⚠ **THIS COMPARISON WAS WRITTEN BACKWARDS ON ITS FIRST RUN AND FAILED
        # A CORRECT QUERY** (`asc` first 1.21, `desc` first 8240.00 — exactly
        # right, and the guard read `asc > desc`). It is recorded rather than
        # quietly corrected because it is hard-won law 7's own shape: a guard
        # nobody can describe a false pass for is a guard nobody understands.
        # **The false pass this version would give:** a query that ignored
        # `direction` entirely returns the SAME first row both ways, so the
        # equality case has to fail too — which is why `<` and not `<=`.
        low = ascending["rows"][0].amount
        high = descending["rows"][0].amount
        if not low < high:
            sys.exit(
                f"FAIL — ascending opened at {low} and descending at {high}. The two "
                "directions must reverse; equal firsts mean `direction` was ignored and "
                "the order is not being applied in SQL at all."
            )

        if args.explain:
            with connection.cursor() as cursor:
                cursor.execute(
                    "EXPLAIN (ANALYZE, BUFFERS) "
                    "SELECT jl.* FROM journal_lines jl "
                    "JOIN journal_entries je ON je.id = jl.journal_entry_id "
                    "WHERE jl.tenant_id = %s AND je.status = 'posted' "
                    "ORDER BY je.entry_date DESC, je.created_at DESC, jl.id DESC "
                    "LIMIT %s OFFSET %s",
                    [str(tenant.id), PAGE, (pages - 1) * PAGE],
                )
                print()
                for line in cursor.fetchall():
                    print(line[0])

    print()
    print("PASS — the page is cut in SQL, the export branch is uncapped, and the books foot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
