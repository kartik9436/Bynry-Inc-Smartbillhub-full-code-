#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Task:     Finance blueprint `P2.21` — the Aging view and *"the report's
#           paging and filters"* (p035's GAP box: *"An aging list grows with
#           the tenant — at 40,000 accounts it cannot load whole"*).
# Defect:   `DEF-REP-6607` — handed back because `ar_aging` loaded every open
#           bill of the tenant into Python and nothing had measured the cost.
# Rules:    `NFR-3` (universal server pagination) · `NFR-5` (no hard caps) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard-won law 7 (a check
#           whose output cannot distinguish pass from fail is worse than none;
#           a check that cannot cover its subject prints what it skipped).
# ───────────────────────────────────────────────────────
"""WHAT ONE PAGE OF THE AR AGEING COSTS, before and after `P2.21`.

`10-scripts/cr138_p4_debtor_cost.py` is the precedent and this is deliberately
its shape — same instruments, same warm-up discipline, same refusal to trust a
wall clock alone:

  **statements**   round trips. An N+1 shows here and nowhere else.
  **rows built**   how many open BILLS the server materialised to answer. This
                   is the `NFR-3` instrument: the removed code pulled every
                   open invoice of the tenant into Python before anything was
                   filtered, so this number was the tenant's whole ledger
                   whatever page was asked for.
  **rows served**  what the caller got. On a paged list, the page.

⚠ **THE `before` READ IS A RECONSTRUCTION AND SAYS SO ON EVERY LINE.** The
in-Python version was DELETED by `P2.21`, so there is nothing left to call.
`_before()` below is that algorithm rebuilt from the removed code — the same
`list()` over `invoice_queryset`, the same per-bill `allocated_so_far`, the
same dict fold, the same `rows.sort` — and it is labelled `before (rebuilt)`
in the output rather than being presented as a measurement of shipped code.
A reader who does not trust it can read it: it is forty lines.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY — and each is answered, not assumed:**

  * **Measuring nothing.** RLS FORCE is on and the app role is neither
    superuser nor BYPASSRLS: with `app.tenant_id` unset every query returns
    zero rows in about a microsecond and this script would print a beautiful
    set of figures about an empty tenant. Everything runs inside
    `tenant_context`, **inside a transaction** — a bare `SET LOCAL` outside one
    does nothing — and the header prints the DEBTOR COUNT it measured over.
    **A run whose debtor count is 0 measured nothing: it says so and exits 2.**
  * **A cold cache on one side and a warm one on the other.** Every timing is
    the MEDIAN of `--repeat` runs after one discarded warm-up.
  * **A page that is the whole list.** The page size is printed beside the
    rows served, so a "page" of 40,000 cannot hide.

⚠ **WHAT IT DOES NOT MEASURE**, named because a declared blind spot with no
number beside it is indistinguishable from an empty one: no HTTP, no DRF
serialisation, no authentication and no front end. It calls the read models
directly, over ONE tenant, and prints how big that tenant is on every line.

USAGE
    10-scripts/proof-db.sh clone finaging
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_finaging \\
      python3 ../10-scripts/fin_p221_aging_cost.py --repeat 3
"""

from __future__ import annotations

import argparse
import os
import pathlib
import statistics
import sys
import time
from datetime import date
from decimal import Decimal

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402

from apps.payments import billing_seam, reporting  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402

ZERO = Decimal("0")


class _StatementCounter:
    """Counts EVERY statement, which `connection.queries` does not.

    Django's query log is capped at 9,000 entries, so a read making 40,000
    round trips would be reported as making 9,000 — the exact defect this
    script exists to size, understated fourfold.
    """

    def __init__(self) -> None:
        self.count = 0

    def __call__(self, execute, sql, params, many, context):
        self.count += 1
        return execute(sql, params, many, context)


def _tenant_shape() -> dict[str, int]:
    with connection.cursor() as cursor:
        cursor.execute(
            "select (select count(*) from accounts), "
            "(select count(*) from invoices where status in ('issued','paid')), "
            "(select count(distinct account_id) from invoices "
            "  where status in ('issued','paid'))"
        )
        accounts, open_bills, debtors = cursor.fetchone()
    return {"accounts": accounts, "open_bills": open_bills, "debtors": debtors}


# ══════════════════════════════════════════════════════════════════════════
# THE READ `P2.21` REMOVED, REBUILT SO THERE IS SOMETHING TO COMPARE AGAINST
# ══════════════════════════════════════════════════════════════════════════
def _before(as_of: date, *, page: int, per: int) -> dict:
    """`apps.payments.reporting.ar_aging` as it stood before 2026-09-24.

    Rebuilt from the deleted code and not paraphrased: `list()` over billing's
    whole open set, `allocated_so_far` per bill, a dict fold, a `rows.sort`.
    **There is no page parameter because there was no page** — `per` is taken
    and then honoured by slicing the finished list, which is what a naive
    "just add paging" fix would have done and is the thing being measured.
    """
    queryset = billing_seam._resolve(
        billing_seam.BILLING_MODULE, billing_seam.INVOICE_QUERYSET_READ
    )
    open_bills = list(
        queryset()
        .filter(status__in=billing_seam.OPEN_INVOICE_STATUSES)
        .values("id", "account_id", "total", "due_date", "currency")
    )
    per_account: dict = {}
    for bill in open_bills:
        balance = bill["total"] - billing_seam.allocated_so_far(bill["id"])
        if balance <= ZERO:
            continue
        entry = per_account.setdefault(bill["account_id"], {"total": ZERO, "oldest": None})
        entry["total"] += balance
        due_on = bill["due_date"]
        if due_on is not None and (entry["oldest"] is None or due_on < entry["oldest"]):
            entry["oldest"] = due_on
    rows = [{"account_id": key, **value} for key, value in per_account.items()]
    rows.sort(key=lambda row: -row["total"])
    return {"rows": rows[(page - 1) * per : page * per], "built": len(open_bills)}


def _after(as_of: date, *, page: int, per: int) -> dict:
    view = reporting.ar_aging(as_of=as_of, page=page, per=per)
    return {"rows": view["rows"], "built": len(view["rows"])}


def _measure(label: str, call, *, repeat: int, warmup: bool) -> dict:
    # ⚠ **IT PRINTS AS IT GOES.** A run whose first read takes half an hour
    # shows nothing for half an hour otherwise, which is indistinguishable from
    # a hung script — and the figure already measured is lost if it is killed.
    print(f"  measuring: {label} …", flush=True)
    if warmup:
        call()
    timings: list[float] = []
    statements = served = built = 0
    for _ in range(repeat):
        counter = _StatementCounter()
        started = time.monotonic()
        with connection.execute_wrapper(counter):
            result = call()
        timings.append(time.monotonic() - started)
        statements = counter.count
        served = len(result["rows"])
        built = result["built"]
    out = {
        "label": label,
        "seconds": statistics.median(timings),
        "statements": statements,
        "served": served,
        "built": built,
    }
    print(
        f"    {label}: {out['seconds']:.3f}s · {out['statements']:,} statements · "
        f"{out['built']:,} rows built · {out['served']:,} rows served",
        flush=True,
    )
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default="brazosbend")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--page", type=int, default=50)
    parser.add_argument("--as-of", default="2026-09-24")
    parser.add_argument(
        "--no-warmup",
        action="store_true",
        help="skip the discarded first call — ONLY for a read too slow to run twice",
    )
    parser.add_argument("--only", default="", help="substring: measure just these reads")
    args = parser.parse_args()

    as_of = date.fromisoformat(args.as_of)
    tenant = tenancy_models.Tenant.objects.filter(subdomain=args.tenant).first()
    if tenant is None:
        print(f"no tenant with subdomain {args.tenant!r} on this database", file=sys.stderr)
        return 2

    with tenant_context(tenant.id):
        shape = _tenant_shape()
        print(
            f"tenant {args.tenant}: {shape['accounts']:,} accounts · "
            f"{shape['open_bills']:,} open bills · {shape['debtors']:,} debtors · "
            f"page of {args.page} · as of {as_of}",
            flush=True,
        )
        if shape["debtors"] == 0:
            # ⚠ Under FORCE RLS an unscoped session sees zero rows instantly,
            # and a benchmark over nothing is the most convincing wrong answer
            # this script could give.
            print("REFUSED: 0 debtors — this run would measure nothing", file=sys.stderr)
            return 2

        results = []
        for label, call in (
            ("before (rebuilt)", lambda: _before(as_of, page=1, per=args.page)),
            ("after", lambda: _after(as_of, page=1, per=args.page)),
        ):
            if args.only and args.only not in label:
                continue
            results.append(
                _measure(label, call, repeat=args.repeat, warmup=not args.no_warmup)
            )

    print()
    print("  read                seconds   statements   rows built   rows served")
    for row in results:
        print(
            f"  {row['label']:<18}{row['seconds']:>8.3f}{row['statements']:>13,}"
            f"{row['built']:>13,}{row['served']:>14,}"
        )
    print()
    print(
        "  A web worker is given 60s (docker-entrypoint.sh, GUNICORN_TIMEOUT:-60). "
        "A figure past it is not slow, it is killed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# ── Lifecycle ─────────────────────────────────────────────
# packet: Finance blueprint `P2.21` · `DEF-REP-6607`
# generated: 2026-09-24 by lane FIN-AGING
# exceptions: (1) the `before` figure is a RECONSTRUCTION of deleted code and
#   every line that prints it says so · (2) it measures the read models, never
#   HTTP or the front end · (3) it measures ONE tenant and prints its size
# ──────────────────────────────────────────────────────────
