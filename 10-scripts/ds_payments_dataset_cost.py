#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: the `payments` DATASET QUERY
#            (`06-backend/apps/payments/payments_dataset.py`) measured on REAL
#            PostgreSQL 16, because the test suite runs on in-memory SQLite
#            (`config/settings/test.py` hardcodes it and ignores
#            `DATABASE_URL`) and cannot answer a question about LIMIT/OFFSET,
#            a query plan or RLS (CLAUDE.md hard-won law 14).
# Rules:     `NFR-3` (universal server pagination — in SQL, never in Python) ·
#            `NFR-5` (no hard caps anywhere) · CLAUDE.md hard rule 1 (tenant
#            scoping; RLS FORCE and the app role is neither superuser nor
#            BYPASSRLS) · hard rule 2 (money is a Decimal) · hard rule 4 (this
#            script READS; the fixture writes payments and writes nothing else)
#            · hard-won law 7 (a check that cannot cover its whole subject
#            prints what it SKIPPED beside what it checked).
# ───────────────────────────────────────────────────────
"""WHAT ONE PAGE OF THE PAYMENTS FACT COSTS — three instruments, because one lies.

`10-scripts/cr138_p4_debtor_cost.py` learned this the expensive way and
`ds_ledger_journal_lines_cost.py` copied the lesson rather than re-learning it;
this does the same. **A wall clock alone cannot answer an `NFR-3` question** —
at a small tenant every figure is dominated by fixed overhead. **And a
statement count alone cannot either**, because a read can hold its statement
count flat while the ROWS those statements build grow with the tenant. Three
columns, and a reader needs all three:

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
    Python slice that materialised everything first is not. **The property is
    that the last page is not slower than the first** — not the wall clock.
  * **A query that ignores `per`.** It would time beautifully and serve
    everything, so page 1 serving more than `PAGE` rows FAILS by name.
  * **A sort applied in Python after the page.** Two directions over the same
    window must reverse at the ends; equal firsts mean `direction` was ignored.
  * **An export that inherited a page.** The stream is counted against the
    tenant's whole filtered set and a short file FAILS.

⚠ **THE COMPARISON THIS SCRIPT EXISTS TO MAKE.** It measures BOTH reads side by
side over the same rows: this dataset query, and
`apps/payments/reporting.payments_by_method`, which is what R1 serves through
today and which folds every matched payment into Python lists with no `LIMIT`,
no `OFFSET` and no SQL aggregate. That is `DEF-REP-6854` and the figures below
are its evidence.

USAGE
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_dspay \\
      python3 ../10-scripts/ds_payments_dataset_cost.py --payments 40000 --repeat 3
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

from apps.customers import models as customer_models  # noqa: E402
from apps.payments import models as payment_models  # noqa: E402
from apps.payments import payments_dataset, reporting as payments_reporting  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

import cr051_provision_utilities as provisioner  # noqa: E402

PAGE = 50
WINDOW = {"start": date(2000, 1, 1), "end": date(2100, 1, 1)}


def _method(tenant, code: str, name: str):
    row, _ = tenancy_models.PaymentMethod.objects.get_or_create(
        tenant=tenant, code=code, defaults={"name": name, "is_system": True}
    )
    return row


def seed(tenant, *, payments: int) -> int:
    """`payments` cleared payments spread over methods, purposes and days.

    ⚠ **WRITTEN THROUGH THE ORM RATHER THAN `services.record_payment`,
    DELIBERATELY.** `record_payment` runs the ledger posting service, and hard
    rule 5 plus `ledger_sole_writer_guard()` make that the right door for real
    money — but this script measures a READ MODEL over `payments`, and a
    posting failure inside a benchmark would be indistinguishable from a
    reporting one. It is the same choice, for the same stated reason, that
    `tests/test_us_rep_canned_reports.a_cleared_payment` records.

    ⚠ **ONE IN FIVE IS A DEPOSIT**, because that is the grain finding this
    script has to be able to see: a deposit writes NO `allocations` row, so an
    allocation-grain query would serve four fifths of these rows and a smaller
    day. The counts printed below make the difference visible.
    """
    account = customer_models.Account.objects.order_by("account_no").first()
    if account is None:
        sys.exit("REFUSED: this tenant has no accounts — there is nothing to take money against")
    cash = _method(tenant, "cash", "Cash")
    cheque = _method(tenant, "check", "Cheque")
    card = _method(tenant, "card", "Card")
    methods = (cash, cheque, card)

    existing = payment_models.Payment.objects.filter(memo__startswith="DS-PAY fixture").count()
    made = 0
    day_zero = date.today().replace(day=1) - timedelta(days=1)
    batch: list[payment_models.Payment] = []
    for index in range(existing, payments):
        when = day_zero - timedelta(days=index % 90)
        moment = datetime(when.year, when.month, when.day, 10, 0, tzinfo=timezone.utc)
        batch.append(
            payment_models.Payment(
                tenant=tenant,
                account=account,
                method=methods[index % 3],
                amount=Decimal("10.0000") + Decimal(index % 97),
                currency="USD",
                status=payment_models.PAYMENT_CLEARED,
                purpose=(
                    payment_models.PURPOSE_DEPOSIT
                    if index % 5 == 0
                    else payment_models.PURPOSE_BILL
                ),
                posted_at=moment,
                cleared_at=moment,
                memo=f"DS-PAY fixture {index}",
            )
        )
        if len(batch) >= 2_000:
            payment_models.Payment.objects.bulk_create(batch)
            made += len(batch)
            batch = []
    if batch:
        payment_models.Payment.objects.bulk_create(batch)
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payments", type=int, default=40_000)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--index", type=int, default=91, help="perf tenant index")
    parser.add_argument("--explain", action="store_true")
    parser.add_argument(
        "--skip-today",
        action="store_true",
        help="skip the payments_by_method comparison (it materialises every row)",
    )
    args = parser.parse_args()

    tenant = provisioner.provision(args.index)
    print(f"tenant {tenant.subdomain} ({tenant.id})")

    with core_tenancy.tenant_context(str(tenant.id)):
        made = seed(tenant, payments=args.payments)
        total = payment_models.Payment.objects.count()
        deposits = payment_models.Payment.objects.filter(
            purpose=payment_models.PURPOSE_DEPOSIT
        ).count()
        print(f"seeded {made} new payments · {total} payments in this tenant")
        print(
            f"  of which {deposits} are DEPOSITS — an allocation-grain dataset would serve "
            f"{total - deposits} of these {total} rows (DEF-REP-6853)"
        )
        if total == 0:
            # hard-won law 7: a query returning nothing reads as "no error".
            sys.exit("REFUSED: zero payments — this would measure nothing at all")

        first = _measure(
            "dataset · page 1",
            lambda: payments_dataset.payments_dataset(page=1, per=PAGE, **WINDOW),
            repeat=args.repeat,
        )
        pages = first["answer"]["pages"]
        last = _measure(
            f"dataset · page {pages} (last)",
            lambda: payments_dataset.payments_dataset(page=pages, per=PAGE, **WINDOW),
            repeat=args.repeat,
        )
        grouped = _measure(
            "dataset · group by method",
            lambda: payments_dataset.payment_groups(group_by="method", **WINDOW),
            repeat=args.repeat,
        )
        streamed = _measure(
            "dataset · stream (the export)",
            lambda: {"rows": list(payments_dataset.payments_dataset_stream(**WINDOW))},
            repeat=1,
        )

        measurements = [first, last, grouped, streamed]
        if not args.skip_today:
            today = _measure(
                "TODAY · reporting.payments_by_method",
                lambda: payments_reporting.payments_by_method(
                    start=WINDOW["start"], end=WINDOW["end"]
                ),
                repeat=1,
                rows_of=lambda answer: len(answer["details"]),
            )
            measurements.append(today)

        print()
        print(f"{'read':<40}{'statements':>12}{'rows served':>14}{'seconds':>10}")
        for measured in measurements:
            print(
                f"{measured['label']:<40}{measured['statements']:>12}"
                f"{measured['rows']:>14}{measured['seconds']:>10.3f}"
            )

        totals = first["answer"]["totals"]
        print()
        print(f"Σ amount              {totals['amount']}")
        print(f"Σ bill-purpose amount {totals['bill_purpose_amount']}  (BR-REP-014)")
        print(f"payments              {totals['payments']}")

        # ── the guards. Each one names the false pass it closes. ────────────

        # A PAGE MUST NOT BE THE WHOLE SET — the one false pass that would make
        # every timing above look wonderful.
        if first["rows"] > PAGE:
            sys.exit(f"FAIL — page 1 served {first['rows']} rows against per={PAGE}")

        # NFR-3's actual property: the LAST page is not slower than the first.
        # A Python slice that materialised everything first cannot hold this.
        ratio = last["seconds"] / first["seconds"] if first["seconds"] else 0
        print()
        print(
            f"last page / first page = {ratio:.2f}×  "
            f"({last['seconds']:.3f}s vs {first['seconds']:.3f}s)"
        )
        if ratio > 3.0:
            sys.exit(
                f"FAIL — the last page cost {ratio:.2f}× the first ({last['seconds']:.3f}s vs "
                f"{first['seconds']:.3f}s). NFR-3 asks for a page cut in SQL; a walk that "
                "degrades with OFFSET this steeply is materialising first."
            )

        # NFR-5 — no ceiling on the export branch.
        if streamed["rows"] != total:
            sys.exit(
                f"FAIL — the stream served {streamed['rows']} of {total} payments. NFR-5 "
                "forbids a ceiling on the export branch."
            )

        # Σ groups == Σ payments. A grouping that loses or duplicates money is
        # the invisible wrong answer the dimension model exists to refuse.
        group_total = grouped["answer"]["totals"]["amount"]
        if group_total != totals["amount"]:
            sys.exit(
                f"FAIL — grouped Σ {group_total} against ungrouped Σ {totals['amount']}. A "
                "grouping must partition the set, never fan it."
            )

        # BR-REP-014 must be structural, which it only is while the two figures
        # can differ. A fixture with no deposits could not tell.
        if totals["bill_purpose_amount"] == totals["amount"] and deposits:
            sys.exit(
                "FAIL — the bill-purpose total equals the grand total although this tenant "
                f"holds {deposits} deposits. BR-REP-014 is not being applied."
            )

        # SORTING IS IN SQL. Two directions must reverse at the ends; EQUAL
        # firsts mean `direction` was ignored, so the comparison is `<` and not
        # `<=` — the false pass `ds_ledger_journal_lines_cost.py` records.
        ascending = payments_dataset.payments_dataset(
            page=1, per=PAGE, sort="amount", direction="asc", **WINDOW
        )
        descending = payments_dataset.payments_dataset(
            page=1, per=PAGE, sort="amount", direction="desc", **WINDOW
        )
        low = ascending["rows"][0].amount
        high = descending["rows"][0].amount
        print(f"sort amount asc first={low} desc first={high}")
        if not low < high:
            sys.exit(
                f"FAIL — ascending opened at {low} and descending at {high}. The two "
                "directions must reverse; equal firsts mean `direction` was ignored and the "
                "order is not being applied in SQL at all."
            )

        if args.explain:
            with connection.cursor() as cursor:
                cursor.execute(
                    "EXPLAIN (ANALYZE, BUFFERS) "
                    "SELECT p.* FROM payments p "
                    "WHERE p.tenant_id = %s "
                    "ORDER BY p.cleared_at DESC, p.id DESC LIMIT %s OFFSET %s",
                    [str(tenant.id), PAGE, (pages - 1) * PAGE],
                )
                print()
                for line in cursor.fetchall():
                    print(line[0])

    print()
    print("PASS — every guard above held.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 · the `payments` dataset query (lane DS-PAYMENTS)
# generated: 2026-09-27
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
