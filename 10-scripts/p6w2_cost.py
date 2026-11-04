#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Component: R34 Disconnect & Reconnect (`apps/customers/disconnect_reconnect.py`),
#            the `P6.11` wave-2 joining read, measured on REAL PostgreSQL 16.
#            The test suite runs on in-memory SQLite (`config/settings/test.py`
#            hardcodes it and ignores `DATABASE_URL`) and cannot answer a
#            question about LIMIT/OFFSET, a query plan or RLS — CLAUDE.md
#            hard-won law 14.
# Rules:     `BR-REP-039` (one row per ACCOUNT, latest case) · `NFR-3` (server
#            pagination, in SQL) · `NFR-5` (no hard caps) · hard rule 1 (tenant
#            scoping; RLS FORCE, and the app role is neither superuser nor
#            BYPASSRLS) · hard rule 4 (this script READS; only the fixture
#            writes) · hard-won law 7 (a check that cannot cover its whole
#            subject prints what it SKIPPED beside what it checked).
# Sibling:   `10-scripts/p6_join_cost.py` — wave 1's three reads. This file
#            follows its shape deliberately rather than inventing a second one.
# ───────────────────────────────────────────────────────
"""WHAT ONE PAGE OF R34 COSTS — three instruments, never one.

  **statements**   round trips. An N+1 shows here and nowhere else.
  **rows served**  what the caller got back — the PAGE on a paged read.
  **seconds**      median of `--repeat`, after a discarded warm-up.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY — each answered, never assumed:**

  * **Measuring nothing.** With `app.tenant_id` unset, RLS FORCE returns zero
    rows in about a millisecond and every timing looks wonderful. Every leg
    runs inside `tenant_context` and PRINTS its row count; a zero FAILS.
  * **Timing a page that is not the expensive one.** The LAST page is measured,
    which is where a Python slice over a materialised set shows.
  * **A query that ignores `per`.** Page 1 serving more than `per` FAILS.
  * **A sort applied in Python after the page.** Two directions over one window
    must reverse at the ends, so the comparison is `!=` and never `<=`.
  * **An export that inherited a page.** The stream is counted against its own
    filtered set and a short file FAILS.
  * **An N+1 hiding behind a small page.** The customer and premises labels are
    batched per page, so the statement count must NOT move with `per`.
  * **A fixture that cannot tell this grain from the case grain.** `BR-REP-039`
    is ONLY about accounts with MORE THAN ONE case: a fixture of one case each
    would pass every assertion against a per-CASE query. The fixture gives a
    third of the accounts two cases and the script REFUSES if `cases > accounts`
    is not true.

⚠ **WHAT THIS SCRIPT DOES NOT MEASURE, STATED RATHER THAN LEFT BLANK**
(hard-won law 7's fifth shape — a number over a scope it silently excludes):

  * **RLS** → `10-scripts/p6w2_rls_proof.py`, which runs as a role that is
    neither superuser nor BYPASSRLS and plants the neighbour's rows first.
  * **`ELIGIBLE` and `PAID`.** Both are NULL with named reasons and there is
    nothing to time. See the read model's two `GAP_` constants.
"""

import argparse
import os
import statistics
import sys
import time
from datetime import date, timedelta
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

from apps.customers import disconnect_reconnect as r34  # noqa: E402
from apps.customers import disconnects  # noqa: E402
from apps.customers import models as customer_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

import cr051_provision_utilities as provisioner  # noqa: E402

PAGE = 50
BIG_PAGE = 200
#: `docker-entrypoint.sh`, `GUNICORN_TIMEOUT:-60`. A read slower than this is
#: not slow — it is KILLED BEFORE IT ANSWERS.
WORKER_TIMEOUT = 60.0
#: What a cut row must carry beside the cut
#: (`ck_cut_records_the_price_of_coming_back`, customers/0024). The amount is
#: arbitrary: R34 does not read it and pinning a figure no rule fixes would be
#: a fixture asserting a price nobody signed.
RECONNECTION_FEE = Decimal("35.0000")


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


#: Every row this script writes carries it, so a re-run ADDS NOTHING and the
#: pre-existing sample rows are never mistaken for the fixture.
MARKER = "P6W2"


def seed_accounts(tenant, *, wanted: int) -> int:
    """Grow the tenant to `wanted` accounts.

    ⚠ **R34's GRAIN IS THE ACCOUNT, SO THE ACCOUNT TABLE IS THE FIXTURE.**
    `p6_join_cost.py` could grow `move_records` alone because R23's grain is the
    EVENT; here the row count is bounded by accounts, and the provisioner seeds
    a sample utility of about seventy. A measurement over seventy rows says
    nothing whatever about `NFR-3`.

    Only the columns R34 reads are populated — the account number, and the
    status and type every account must carry. It is not a realistic customer;
    it is a row at the grain being measured, which is what a cost fixture is.
    """
    have = customer_models.Account.objects.count()
    if have >= wanted:
        return 0
    status = customer_models.AccountStatus.objects.order_by("created_at").first()
    kind = customer_models.AccountType.objects.order_by("created_at").first()
    if status is None or kind is None:
        sys.exit(
            "REFUSED: this tenant has no account status or type lookup rows, so an account "
            "cannot be written. Provision it before running this."
        )
    # ⚠ **EVERY SEEDED ACCOUNT IS ANCHORED TO A UNIT, AND A PREMISES IS NOT
    # ENOUGH.** Two constraints bite in sequence and the second is the strict
    # one: `ck_accounts_anchored` wants a unit OR a premises, and
    # `ck_accounts_regular_has_unit` then demands a UNIT of every account whose
    # `kind` is `regular` — which is the default. Hard rule 8 is why either
    # exists: an account declares no address of its own and DERIVES one by
    # walking, so an unanchored row has nowhere to walk to and this report's
    # CUSTOMER and premises columns would have nothing to resolve.
    anchor = (
        customer_models.Account.objects.filter(unit_id__isnull=False)
        .values_list("unit_id", "premises_id")
        .first()
    )
    if anchor is None:
        sys.exit(
            "REFUSED: no existing account is anchored to a unit, so a seeded one has nothing "
            "to anchor to (ck_accounts_regular_has_unit, hard rule 8)."
        )
    unit_anchor, premises_anchor = anchor
    batch: list[customer_models.Account] = []
    made = 0
    for index in range(have, wanted):
        batch.append(
            customer_models.Account(
                tenant=tenant,
                account_no=f"{MARKER}-{index:07d}",
                status=status,
                account_type=kind,
                unit_id=unit_anchor,
                premises_id=premises_anchor,
            )
        )
        if len(batch) >= 2_000:
            customer_models.Account.objects.bulk_create(batch)
            made += len(batch)
            batch = []
    if batch:
        customer_models.Account.objects.bulk_create(batch)
        made += len(batch)
    return made


def seed_cases(tenant, *, accounts_wanted: int) -> tuple[int, int]:
    """One case on every account, and a SECOND, EARLIER one on every third.

    ⚠ **THE SECOND CASE IS THE WHOLE POINT OF THE FIXTURE.** `BR-REP-039` is a
    ruling about accounts with more than one case; a fixture of one case each
    would let a per-CASE query pass every assertion in this script, and the
    balance column would read `$395` on a real tenant while every number here
    said PASS. `main` refuses when cases do not exceed accounts.

    ⚠ **THE EARLIER CASE IS `restored` AND THE LATEST IS OPEN.**
    `uq_one_open_disconnect_case_per_account` permits exactly one open case per
    account, so two open cases would be refused by the database and this script
    would fail for a reason that is not about cost.
    """
    # ⚠ **ONLY THE ACCOUNTS THAT HAVE NO CASE YET.** A first draft returned
    # early whenever the table held ANY row, and the provisioner's own four
    # sample cases were enough to skip the seeding entirely — so the script
    # measured 4 rows and its own guard caught it. Re-runnable now: an account
    # that already has a case is skipped, so running twice adds nothing.
    spoken_for = set(
        disconnects.DisconnectCase.objects.values_list("account_id", flat=True).distinct()
    )
    account_ids = [
        one
        for one in customer_models.Account.objects.order_by("account_no").values_list(
            "id", flat=True
        )[: max(1, accounts_wanted)]
        if one not in spoken_for
    ]
    if not account_ids and not spoken_for:
        sys.exit("REFUSED: this tenant has no accounts — a disconnect case would have no anchor")

    anchor = date(2026, 9, 27)
    rows: list[disconnects.DisconnectCase] = []
    for index, account_id in enumerate(account_ids):
        # THE EARLIER, CLOSED CASE — every third account.
        if index % 3 == 0:
            opened = anchor - timedelta(days=200 + (index % 90))
            rows.append(
                disconnects.DisconnectCase(
                    tenant=tenant,
                    account_id=account_id,
                    sequence=disconnects.SEQ_SERVICE,
                    state=disconnects.STATE_RESTORED,
                    amount_owed_at_open=Decimal("210.0000"),
                    currency="USD",
                    opened_on=opened,
                    cut_on=opened + timedelta(days=3),
                    reconnected_on=opened + timedelta(days=11),
                    reconnection_fee_amount=RECONNECTION_FEE,
                    reconnection_fee_code=disconnects.RECONNECT_CHARGE_CODE,
                    deposit_disposition=disconnects.DEPOSIT_HELD,
                )
            )
        # THE LATEST CASE — one on every account, spread over 180 days.
        opened = anchor - timedelta(days=index % 180)
        cut = index % 4 != 0
        rows.append(
            disconnects.DisconnectCase(
                tenant=tenant,
                account_id=account_id,
                sequence=disconnects.SEQ_SERVICE,
                state=(
                    disconnects.STATE_CUT if cut else disconnects.STATE_NOTICE_SENT
                ),
                amount_owed_at_open=Decimal("185.0000") + Decimal(index % 40),
                currency="USD",
                opened_on=opened,
                cut_on=(opened + timedelta(days=5)) if cut else None,
                reconnection_fee_amount=RECONNECTION_FEE if cut else None,
                reconnection_fee_code=(
                    disconnects.RECONNECT_CHARGE_CODE if cut else None
                ),
                deposit_disposition=disconnects.DEPOSIT_HELD if cut else None,
            )
        )
        if len(rows) >= 2_000:
            disconnects.DisconnectCase.objects.bulk_create(rows)
            rows = []
    if rows:
        disconnects.DisconnectCase.objects.bulk_create(rows)
    return (
        disconnects.DisconnectCase.objects.count(),
        disconnects.DisconnectCase.objects.values("account_id").distinct().count(),
    )


# ── the guards ──────────────────────────────────────────────────────────────


def _page_guards(name, first, last, streamed, *, page_size=PAGE, floor=1) -> None:
    if first["rows"] == 0:
        sys.exit(
            f"FAIL — {name}: page 1 served ZERO rows. A read that answers nothing reads as "
            "'no error' and this script would have measured a tenant context that was never "
            "set (hard rule 1, RLS FORCE)."
        )
    if first["rows"] > page_size:
        sys.exit(f"FAIL — {name}: page 1 served {first['rows']} rows against per={page_size}")
    filtered = first["answer"]["total"]
    if filtered < floor:
        sys.exit(
            f"FAIL — {name}: the filtered set holds {filtered} rows and this measurement "
            f"needs at least {floor} to distinguish a SQL page from a Python slice."
        )
    ratio = last["seconds"] / first["seconds"] if first["seconds"] else 0
    print(
        f"  {name}: last page / first page = {ratio:.2f}×  "
        f"({last['seconds']:.3f}s vs {first['seconds']:.3f}s)"
    )
    # ⚠ **THE RATIO IS REPORTED AND IS NOT THE GUARD** — a deep OFFSET is a walk
    # however good the index is, so a ratio threshold goes red when the read
    # IMPROVES. What matters is whether the last page answers at all.
    if last["seconds"] > WORKER_TIMEOUT:
        sys.exit(
            f"FAIL — {name}: the last page took {last['seconds']:.3f}s and a web worker is "
            f"given {WORKER_TIMEOUT}s (docker-entrypoint.sh, GUNICORN_TIMEOUT). It would not "
            "be slow in production, it would be killed before it answered."
        )
    print(f"  {name}: stream {streamed['rows']} · filtered set {filtered}")
    if streamed["rows"] != filtered:
        sys.exit(
            f"FAIL — {name}: the stream served {streamed['rows']} of the {filtered} rows in "
            "its own filtered set. NFR-5 forbids a ceiling on the export branch."
        )


def _statement_guard(name, small, big) -> None:
    if small["statements"] != big["statements"]:
        sys.exit(
            f"FAIL — {name}: page 1 cost {small['statements']} statements at per={PAGE} and "
            f"{big['statements']} at per={BIG_PAGE}. A count that scales with the page is an "
            "N+1 in the label read, which is the one defect a wall clock hides at this size."
        )
    print(f"  {name}: {small['statements']} statements at per={PAGE} AND at per={BIG_PAGE}")


def _direction_guard(name, ascending, descending, key) -> None:
    low = key(ascending["answer"]["rows"][0])
    high = key(descending["answer"]["rows"][0])
    if low == high:
        sys.exit(
            f"FAIL — {name}: both directions opened at {low!r}. They must reverse; equal "
            "firsts mean the sort was applied in Python after the page, or not at all."
        )
    print(f"  {name}: asc opens at {low!r} · desc opens at {high!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--accounts", type=int, default=40_000)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--index", type=int, default=95, help="perf tenant index")
    args = parser.parse_args()

    tenant = provisioner.provision(args.index)
    print(f"tenant {tenant.subdomain} ({tenant.id})")

    with core_tenancy.tenant_context(str(tenant.id)):
        print(f"seeded {seed_accounts(tenant, wanted=args.accounts)} new accounts")
        cases, with_cases = seed_cases(tenant, accounts_wanted=args.accounts)
        accounts = customer_models.Account.objects.count()
        print(
            f"tenant holds {accounts} accounts · {cases} disconnect cases over "
            f"{with_cases} of them"
        )
        # ⚠ **THE ONE REFUSAL THAT MAKES THIS A MEASUREMENT OF `BR-REP-039`.**
        if cases <= with_cases:
            sys.exit(
                "FAIL — every account has exactly one case, so a per-CASE query would pass "
                "every figure below. BR-REP-039 is a ruling about accounts with MORE THAN "
                "ONE case and this fixture cannot tell the two grains apart."
            )

        print("\nR34 Disconnect & Reconnect — one row per ACCOUNT, latest case")
        pages = max(1, -(-with_cases // PAGE))
        first = _measure(
            "page 1 of 50", lambda: r34.disconnect_reconnect(per=PAGE, page=1), repeat=args.repeat
        )
        last = _measure(
            f"page {pages} (the last) of 50",
            lambda: r34.disconnect_reconnect(per=PAGE, page=pages),
            repeat=args.repeat,
        )
        big = _measure(
            "page 1 of 200",
            lambda: r34.disconnect_reconnect(per=BIG_PAGE, page=1),
            repeat=args.repeat,
        )
        ascending = _measure(
            "sort=account_no asc",
            lambda: r34.disconnect_reconnect(per=PAGE, sort="account_no", direction="asc"),
            repeat=args.repeat,
        )
        descending = _measure(
            "sort=account_no desc",
            lambda: r34.disconnect_reconnect(per=PAGE, sort="account_no", direction="desc"),
            repeat=args.repeat,
        )
        streamed = _measure(
            "export — the WHOLE filtered set",
            lambda: {"rows": list(r34.disconnect_reconnect_stream())},
            repeat=1,
        )
        for result in (first, last, big, ascending, descending, streamed):
            _say(result)
        _page_guards("R34", first, last, streamed, floor=1_000)
        _statement_guard("R34", first, big)
        # ⚠ **A ROW IS A `DisconnectReconnectRow`, NOT A DICT** — the read model
        # yields its own dataclass and `_fact_rows` in `queries.py` is what
        # turns one into the wire's mapping. A first draft subscripted it and
        # crashed here, AFTER every timing had been taken, which is the right
        # way round: the guard failed loudly rather than skipping.
        _direction_guard("R34", ascending, descending, lambda row: row.account_no)

        # ⚠ **THE TILES FOOT TO THE WHOLE FILTERED SET AND NOT TO THE PAGE.**
        # A tile computed over the page is the defect `US-PAY-013` TC-1 names,
        # and it is invisible on page 1 where the two agree by accident.
        page_one = first["answer"]
        page_two = r34.disconnect_reconnect(per=PAGE, page=2)
        if page_one["totals"] != page_two["totals"]:
            sys.exit(
                "FAIL — R34: the totals moved between page 1 and page 2, so they are computed "
                "over the PAGE. BR-REP-039's balance column would then describe a page."
            )
        print(f"  R34: totals identical on page 1 and page 2 — {page_one['totals']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
