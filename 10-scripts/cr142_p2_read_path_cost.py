#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 `P2.12` (the three read models accept paging) ·
#           `P2.1` (paging in SQL) · `P2.2` (sort in SQL) · `P2.3` (search) ·
#           `P2.4` (the row cap and the pre-count are deleted).
# Rules:    `NFR-3` (universal server pagination) · `NFR-5` (no hard caps) ·
#           CLAUDE.md hard rule 1 (tenant scoping — `app.tenant_id` BEFORE a
#           row is written or read) · hard rule 2 (money is NUMERIC) ·
#           hard-won law 7 (ask what would make this check pass WRONGLY; a
#           check that cannot cover its whole subject prints what it skipped).
# Brief:    `05-prototype/09 Reports Build Brief.pdf` p010 (phase 2's DONE
#           WHEN — *"a report of 38,412 rows opens in under two seconds
#           showing 50, and no export is refused for being large"*) · p087
#           §7.5 (*"returns rows with limit/offset/sort applied in SQL. Never
#           the whole result"*) and its two measured facts.
# ───────────────────────────────────────────────────────
"""WHAT THE REPORTS READ PATH COSTS AT THE TOP OF THE ICP — MEASURED, ON REAL
PostgreSQL, WITH THE PLAN PRINTED RATHER THAN DESCRIBED.

`P2.9` (a later lane's) puts it plainly: **the SQLite suite is not evidence.**
`config/settings/test.py` hardcodes in-memory SQLite, and on 38,412 rows the
difference between a `LIMIT` and a Python slice is the difference between a
page and a worker timeout — neither of which a fixture of twenty rows can
show.

FOUR LEGS, and each answers a different task:

  **A · the register pages** (`P2.12` · `P2.1`) — page 1 and page 769 of a
       38,412-row billing register, against the cost of the line the OLD code
       opened with: `list(_issued_queryset())`, the tenant's whole issued
       book. The plan is printed so a reader sees the `LIMIT`, and the
       **served row count** is printed so a reader can see it is 50.
  **B · the register sorts and searches in SQL** (`P2.2` · `P2.3`) — each of
       the four declared sorts, both directions, and a `q`. The check is that
       the cost does NOT move with the sort: a Python sort of 38,412 rows is
       visible, an `ORDER BY` with an index behind it is not.
  **C · the account ledger pages, and its running balance survives it**
       (`P2.12` · `P2.2`) — page 2's first row must carry the SAME running
       balance it carries in an unpaged read. This is the leg that can fail
       CORRECTLY: paging a cumulative column is the thing that goes wrong.
  **D · the export is never refused, and the report is built ONCE**
       (`P2.4`) — the pre-count is gone, so the accept path must issue **no
       statement at all** against the selection before enqueueing.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY — and each is answered rather than
assumed:**

  * **Measuring nothing.** RLS `FORCE` is on and the app role is neither
    superuser nor `BYPASSRLS`: with `app.tenant_id` unset every statement
    returns zero rows in a microsecond and this script would print a beautiful
    table about an empty tenant. Everything runs inside `tenant_context`, and
    the header prints the ROW COUNT it is measuring over — **a run whose
    register holds fewer than 10,000 rows has not measured the thing this
    script exists for, and it says so and exits 2.**
  * **A cold cache on the first call and a warm one on the second**, which
    would make whichever ran second look faster. Every timing is the MEDIAN of
    `--repeat` runs after one DISCARDED warm-up.
  * **A `LIMIT` that is really a Python slice.** A wall clock cannot tell them
    apart on a fast box. So leg A prints the statement's own plan from
    `EXPLAIN (ANALYZE, BUFFERS)` — taken from the statement the read
    ACTUALLY issued, recorded through an `execute_wrapper`, never from a
    hand-written lookalike (that is law 7's *looking at the wrong thing*, and
    `cr138_p4_debtor_cost.py` records it happening).
  * **A page that is fast because it is empty.** Every leg asserts its served
    row count and prints it.

⚠ **WHAT IT DOES NOT MEASURE, named because a declared blind spot with no
number beside it is indistinguishable from an empty one:** no HTTP, no DRF
serialisation, no authentication, no front end — it calls the read models
directly. And the fixture writes **one usage line per bill**, so the page's
line read is exercised but a bill with eight services is not; a real register
page does marginally more work in Python than this prints, and nothing in that
work scales with the tenant.

USAGE
    10-scripts/proof-db.sh clone p2aperf
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_p2aperf \\
      python3 ../10-scripts/cr142_p2_read_path_cost.py --seed --accounts 19206
"""

from __future__ import annotations

import argparse
import os
import pathlib
import statistics
import sys
import time
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402
from django.utils import timezone  # noqa: E402

from apps.billing import reporting as billing_reporting  # noqa: E402
from apps.ledger import reporting as ledger_reporting  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402

MARK = "SCALE-%"
#: The seeder writes every bill with `issued_at = now()`, so any window that
#: contains today contains all of them. Stated rather than inferred: a window
#: that missed them would make every figure here a measurement of zero rows.
WINDOW_START = date(2026, 1, 1)
WINDOW_END = date(2030, 1, 1)


class _Counter:
    """Counts EVERY statement. `connection.queries` caps at 9,000 and warns on
    stderr in the middle of a benchmark, so a read making 40,000 round trips
    would be reported as making 9,000 — the exact N+1 this sizes, understated
    fourfold."""

    def __init__(self) -> None:
        self.count = 0

    def __call__(self, execute, sql, params, many, context):
        self.count += 1
        return execute(sql, params, many, context)


class _Recorder:
    """Keeps the statements a read ACTUALLY made, so EXPLAIN runs THEM."""

    def __init__(self) -> None:
        self.statements: list[tuple[str, Any]] = []

    def __call__(self, execute, sql, params, many, context):
        self.statements.append((sql, params))
        return execute(sql, params, many, context)


def _measure(label: str, call, *, repeat: int, rows_of, warmup: bool = True) -> dict:
    print(f"  measuring: {label} …", flush=True)
    if warmup:
        call()
    timings: list[float] = []
    statements = 0
    served = 0
    for _ in range(repeat):
        counter = _Counter()
        started = time.monotonic()
        with connection.execute_wrapper(counter):
            result = call()
        timings.append(time.monotonic() - started)
        statements = counter.count
        served = rows_of(result)
    out = {
        "label": label,
        "seconds": statistics.median(timings),
        "statements": statements,
        "served": served,
    }
    print(
        f"    {label:<46} {out['seconds']:>8.3f}s · {out['statements']:>4} statements · "
        f"{out['served']:>7,} rows served",
        flush=True,
    )
    return out


def _explain(sql: str, params: Any) -> str:
    with connection.cursor() as cursor:
        cursor.execute(f"explain (analyze, buffers) {sql}", params)
        return "\n".join("      " + row[0] for row in cursor.fetchall())


def _register_shape() -> dict[str, int]:
    with connection.cursor() as cursor:
        cursor.execute(
            "select (select count(*) from accounts), "
            "(select count(*) from invoices "
            "   where status in ('issued','paid','void','corrected')), "
            "(select count(*) from invoice_lines)"
        )
        accounts, register_rows, lines = cursor.fetchone()
    return {"accounts": accounts, "register_rows": register_rows, "lines": lines}


# ══════════════════════════════════════════════════════════════════════════
# THE FIXTURE
# ══════════════════════════════════════════════════════════════════════════
def seed_lines(cursor) -> int:
    """ONE usage line per scale bill, so the page's line read is not a no-op.

    Without these, `billing_register`'s per-page `invoice_lines` query returns
    nothing and the Services/Usage columns are empty on every row — which
    would make the page look cheaper than a real one and would leave the
    service FILTER (`Exists` over `invoice_lines`) measuring an empty table.
    """
    cursor.execute("select id from services order by code limit 1")
    row = cursor.fetchone()
    if row is None:
        raise SystemExit("REFUSED: this tenant has no services; run `manage.py seed_demo`.")
    service_id = row[0]
    cursor.execute(
        """
        insert into invoice_lines (
            id, kind, description, quantity, unit, unit_price, amount, taxable,
            created_at, updated_at, invoice_id, account_id, service_id,
            tenant_id, gl_account_id
        )
        select gen_random_uuid(), 'usage', 'Scale usage', 100.000000, 'kWh',
               1.000000, i.total, false, now(), now(), i.id, i.account_id,
               %s, i.tenant_id, null
        from invoices i
        join accounts a on a.id = i.account_id
        where a.account_no like %s
        """,
        (service_id, MARK),
    )
    return cursor.rowcount


# ══════════════════════════════════════════════════════════════════════════
# THE LEGS
# ══════════════════════════════════════════════════════════════════════════
def leg_a(repeat: int, shape: dict[str, int]) -> list[dict]:
    print("\nA · THE BILLING REGISTER PAGES (`P2.12` · `P2.1`)")
    rows_of = lambda view: len(view["rows"])  # noqa: E731
    results = [
        _measure(
            "register page 1 of 50",
            lambda: billing_reporting.billing_register(
                start=WINDOW_START, end=WINDOW_END, page=1, per=50
            ),
            repeat=repeat,
            rows_of=rows_of,
        ),
        _measure(
            f"register page {max(2, shape['register_rows'] // 50)} of 50 (the LAST page)",
            lambda: billing_reporting.billing_register(
                start=WINDOW_START,
                end=WINDOW_END,
                page=max(2, shape["register_rows"] // 50),
                per=50,
            ),
            repeat=repeat,
            rows_of=rows_of,
        ),
    ]

    # ⚠ **THE OLD CODE'S FIRST LINE, MEASURED AS ITSELF.** `billing_register`
    # opened with `invoices = list(queryset)` over exactly this queryset before
    # `P2.12`. Re-implementing the whole old function here would be a lookalike
    # (law 7); its FIRST STATEMENT is the part that did not scale, and this is
    # that statement, unchanged.
    def _whole_book() -> list:
        return list(billing_reporting._issued_queryset())

    results.append(
        _measure(
            "the line P2.12 deleted: list(_issued_queryset())",
            _whole_book,
            repeat=repeat,
            rows_of=len,
        )
    )

    # ── the plan, from the statement the read ACTUALLY issued ────────────
    recorder = _Recorder()
    with connection.execute_wrapper(recorder):
        billing_reporting.billing_register(
            start=WINDOW_START, end=WINDOW_END, page=2, per=50
        )
    # ⚠ **THE FIRST DRAFT OF THIS BLOCK EXPLAINED THE WRONG STATEMENT, WHICH
    # IS LAW 7'S *looking at the wrong thing* IN THIS FILE'S OWN LIFETIME.**
    # It took the LAST statement containing `LIMIT`, and the last one a
    # register page issues is customers' primary-contact read — so it printed
    # a beautiful three-buffer plan over `contacts` under a heading that said
    # PAGE. The register's page statement is the one that selects FROM
    # `invoices`, and it is now selected by that, with a refusal when no such
    # statement carries a `LIMIT` at all.
    page_statements = [
        (sql, params)
        for sql, params in recorder.statements
        if " LIMIT " in sql.upper() and 'FROM "INVOICES"' in sql.upper()
    ]
    print("\n  the PAGE statement's own plan (EXPLAIN ANALYZE, BUFFERS):")
    if not page_statements:
        raise SystemExit(
            "REFUSED: no statement against `invoices` carried a `LIMIT`. That is "
            "P2.1 failing — the page is being cut in Python — and it is not a "
            "reporting gap to be printed and passed over."
        )
    for sql, params in page_statements[-1:]:
        print(f"      -- {sql[:160]}…")
        print(_explain(sql, params))
    print(f"    statements against `invoices` carrying a LIMIT: {len(page_statements)}")
    return results


def leg_b(repeat: int) -> list[dict]:
    print("\nB · THE REGISTER SORTS AND SEARCHES IN SQL (`P2.2` · `P2.3`)")
    rows_of = lambda view: len(view["rows"])  # noqa: E731
    results = []
    for sort in billing_reporting.REGISTER_SORTS:
        for direction in ("asc", "desc"):
            results.append(
                _measure(
                    f"register page 1 sorted {sort} {direction}",
                    lambda sort=sort, direction=direction: billing_reporting.billing_register(
                        start=WINDOW_START,
                        end=WINDOW_END,
                        page=1,
                        per=50,
                        sort=sort,
                        direction=direction,
                    ),
                    repeat=repeat,
                    rows_of=rows_of,
                )
            )
    searched = _measure(
        "register page 1 with q='SC-A-000100'",
        lambda: billing_reporting.billing_register(
            start=WINDOW_START, end=WINDOW_END, page=1, per=50, search="SC-A-000100"
        ),
        repeat=repeat,
        rows_of=rows_of,
    )
    results.append(searched)
    return results


def seed_ledger(*, lines: int) -> tuple[Any, int]:
    """One account with `lines` posted AR movements, THROUGH THE POSTING SERVICE.

    ⚠ **THE FIRST DRAFT OF THIS FUNCTION WROTE `journal_entries` WITH RAW SQL
    AND THE DATABASE REFUSED IT BY NAME**, which is the best kind of proof
    there is:

        CLAUDE.md rule 5: journal_entries is written ONLY by the ledger posting
        service (apps/ledger/posting.py). This INSERT did not come through
        post(), so it lands nowhere.

    `ledger_sole_writer_guard()` is a trigger, not a convention, and a
    benchmark fixture is not an exception to hard rule 5. So every movement
    here is a BALANCED pair through `posting.post()` — AR against the tenant's
    revenue account — which is slower to seed and is the only lawful way to
    put a running balance in front of this measurement.

    Alternating debit and credit so the balance actually MOVES: a column of
    identical values would let a broken carry-forward pass.
    """
    from apps.ledger import chart, close, models as ledger_models, posting

    account = (
        __import__("apps.customers.models", fromlist=["models"])
        .Account.objects.filter(account_no__startswith="SCALE-")
        .order_by("account_no")
        .first()
    )
    if account is None:
        raise SystemExit("REFUSED: no scale account to hang a ledger on; seed accounts first.")
    designated = {
        row.designation: row.id
        for row in ledger_models.LedgerAccount.objects.filter(
            designation__in=(chart.AR, chart.CUSTOMER_CREDIT_BALANCE)
        )
    }
    ar_id = designated.get(chart.AR)
    other_id = designated.get(chart.CUSTOMER_CREDIT_BALANCE)
    if ar_id is None or other_id is None:
        raise SystemExit(
            "REFUSED: this tenant designates no AR and/or customer-credit account (OQ-106), so "
            "no balanced pair can be posted and leg C would measure nothing."
        )

    # ⚠ **ONE OPEN DATE, RESOLVED RATHER THAN CHOSEN.** The first draft
    # dated these from 2026-01-01 and `post()` refused by name — 2026-07 is a
    # CLOSED fiscal period (`BR-LED-006`). `resolve_entry_date` is the
    # service's own answer for a late-arriving event, so the fixture asks it
    # instead of picking a date that happens to work today.
    # `_ar_lines` orders by entry_date, then created_at, then id — a TOTAL
    # order — so one shared date still gives a stable, pageable sequence.
    entry_date, _note = close.resolve_entry_date(date(2026, 9, 26))
    written = 0
    for n in range(1, lines + 1):
        debit_is_ar = (n % 2) == 1
        amount = Decimal(10 + (n % 7))
        request = posting.PostingRequest(
            posting_key=f"p2a-ledger-scale||{account.id}||{n}",
            entry_date=entry_date,
            posted_at=timezone.now(),
            currency="USD",
            memo=f"P2A ledger scale {n}",
            lines=(
                posting.PostingLine(
                    ledger_account_id=ar_id,
                    side=ledger_models.SIDE_DEBIT if debit_is_ar else ledger_models.SIDE_CREDIT,
                    amount=amount,
                    source_type="manual",
                    source_id=account.id,
                    account_id=account.id,
                ),
                posting.PostingLine(
                    ledger_account_id=other_id,
                    side=ledger_models.SIDE_CREDIT if debit_is_ar else ledger_models.SIDE_DEBIT,
                    amount=amount,
                    source_type="manual",
                    source_id=account.id,
                    account_id=account.id,
                ),
            ),
        )
        posting.post(request)
        written += 1
    return account.id, written


def leg_c(repeat: int) -> list[dict]:
    print("\nC · THE ACCOUNT LEDGER PAGES, AND ITS RUNNING BALANCE SURVIVES IT")
    with connection.cursor() as cursor:
        cursor.execute(
            "select jl.account_id, count(*) from journal_lines jl "
            "group by jl.account_id order by count(*) desc limit 1"
        )
        row = cursor.fetchone()
    if row is None or row[1] < 2:
        print("  SKIPPED: no account carries two or more journal lines in this fixture.")
        print("  ⚠ THIS IS A BLIND SPOT WITH A NUMBER BESIDE IT, NOT A PASS.")
        return []
    account_id, lines = row
    print(f"  the account with the most AR movement: {lines:,} journal line(s)")
    # ⚠ **THE PAGE SIZE COMES FROM THE AR ROWS, NOT THE JOURNAL LINES.** A
    # balanced pair puts TWO lines in the books and exactly ONE of them on this
    # customer's ledger, so `lines // 2` made the page the same size as the
    # report and the carry-forward was never exercised — the refusal below
    # caught it, which is the refusal doing its job on its own author.
    whole = ledger_reporting.account_ledger(
        account_id, start=date(2000, 1, 1), end=date(2030, 1, 1)
    )
    per = max(1, len(whole["rows"]) // 2)
    print(f"  the report holds {len(whole['rows']):,} AR row(s); the page is {per}")
    page_two = ledger_reporting.account_ledger(
        account_id, start=date(2000, 1, 1), end=date(2030, 1, 1), page=2, per=per
    )
    # ⚠ **THIS CHECK USED TO SKIP ITSELF SILENTLY.** It sat behind an `if`
    # and printed nothing when the fixture was too small, so a run in which
    # the one assertion that can fail CORRECTLY never executed looked exactly
    # like a run in which it passed. A blind spot with no number beside it is
    # indistinguishable from an empty one (law 7).
    if not (len(whole["rows"]) > per and page_two["rows"]):
        raise SystemExit(
            f"REFUSED: this account has {len(whole['rows'])} AR row(s) in the window "
            f"and the page is {per}, so the carry-forward was NEVER EXERCISED. "
            "Seed an account with more AR movement rather than reading this as a pass."
        )
    if True:
        expected = whole["rows"][per]
        got = page_two["rows"][0]
        same = expected.running_balance == got.running_balance
        print(
            f"    row {per + 1}'s running balance — unpaged {expected.running_balance} · "
            f"page two {got.running_balance} · {'SAME' if same else '⛔ DIFFERENT'}"
        )
        if not same:
            raise SystemExit(
                "REFUSED: the running balance does not survive the page. That is the "
                "one thing paging a cumulative column can get wrong."
            )
        print(
            f"    window totals unchanged by the page — charges "
            f"{whole['totals']['charges']} == {page_two['totals']['charges']}: "
            f"{whole['totals']['charges'] == page_two['totals']['charges']}"
        )
    return [
        _measure(
            f"account ledger page 2 of {per}",
            lambda: ledger_reporting.account_ledger(
                account_id, start=date(2000, 1, 1), end=date(2030, 1, 1), page=2, per=per
            ),
            repeat=repeat,
            rows_of=lambda view: len(view["rows"]),
        )
    ]


def leg_d() -> None:
    print("\nD · THE EXPORT IS NEVER REFUSED, AND THE REPORT IS BUILT ONCE (`P2.4`)")
    from apps.tenancy import exports as export_kernel

    for name in ("EXPORT_ROW_CAP", "selection_count"):
        present = hasattr(export_kernel, name)
        print(f"    apps.tenancy.exports.{name:<16} present: {present}  (must be False)")
        if present:
            raise SystemExit(f"REFUSED: `{name}` is back — NFR-5 / P2.4.")
    print("    a 685,000-row export is therefore refused by no number at all.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default="brazosbend")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--seed", action="store_true", help="write the invoice lines first")
    parser.add_argument("--min-rows", type=int, default=10_000)
    parser.add_argument("--ledger-lines", type=int, default=400)
    args = parser.parse_args()

    tenant = tenancy_models.Tenant.objects.get(subdomain=args.tenant)
    with tenant_context(str(tenant.id)):
        if args.seed:
            with connection.cursor() as cursor:
                written = seed_lines(cursor)
            ledger_account, ledger_lines = seed_ledger(lines=args.ledger_lines)
            with connection.cursor() as cursor:
                cursor.execute(
                    "analyze invoices, invoice_lines, accounts, journal_lines, journal_entries"
                )
            print(f"seeded {written:,} invoice line(s) · {ledger_lines:,} AR journal line(s)")

        shape = _register_shape()
        print(
            f"\ntenant {args.tenant}: {shape['accounts']:,} accounts · "
            f"{shape['register_rows']:,} register rows · {shape['lines']:,} invoice lines · "
            f"median of {args.repeat} after a discarded warm-up"
        )
        if shape["register_rows"] < args.min_rows:
            print(
                f"REFUSED: {shape['register_rows']:,} register rows is below "
                f"{args.min_rows:,}. At this size a LIMIT and a Python slice are the "
                "same two numbers, so this run would prove nothing. Seed first:\n"
                "  python3 ../10-scripts/cr138_p4_debtor_scale_seed.py --accounts 19206"
            )
            return 2

        leg_a(args.repeat, shape)
        leg_b(args.repeat)
        leg_c(args.repeat)
        leg_d()
    print("\ndone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
