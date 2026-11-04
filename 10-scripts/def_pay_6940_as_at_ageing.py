#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:   `DEF-PAY-6940` — the AR Ageing answers the same figures for every
#           `as_of` it is asked for. `DEF-PAY-7020` — what a past-date read
#           still cannot restore, and its count.
# Story:    US-REP-005 (AR ageing) · Finance blueprint `P2.21`, p035
# Rules:    `BR-TEN-043` (`as_of` is an argument, never a clock) ·
#           `BR-REP-001` (POSTING basis) · `BR-PAY-021` (posting ≠ clearing) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2 (money 4dp) ·
#           hard-won law 7 (a check whose output cannot distinguish pass from
#           fail is worse than no check; print the blind spot's NUMBER).
# ───────────────────────────────────────────────────────
"""CAN THE AR AGEING LOOK BACK? — one ladder of dates, and the SQL to check it.

Run it against a seeded PostgreSQL 16 clone and read the ladder DOWN. On the
broken read every row is identical below `total` and `accounts`; on the fixed
read the position moves as bills are issued and cash is posted.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY, and each is answered rather than
assumed:**

  * **Measuring an empty tenant.** RLS FORCE is on and the app role is neither
    SUPERUSER nor BYPASSRLS, so with `app.tenant_id` unset every query returns
    zero rows very fast and this script would print a beautiful ladder of
    zeroes. Everything runs inside `tenant_context`, the header prints the
    role's `rolsuper`/`rolbypassrls`, and **a run whose open-bill count is 0
    prints that it measured nothing and exits 2.**
  * **A ladder that cannot move.** A date range outside the tenant's own
    history answers `0` at every step and would look like a fix. The header
    prints the tenant's FIRST and LAST `issued_at` and `posted_at`, and the
    ladder is built from those dates, so a reader can see that the dates
    asked for are dates the data has something to say about.
  * **Trusting the code to check the code.** The last section re-derives one
    figure in **hand-written SQL that shares no line with the read** —
    `invoices` joined to `allocations` joined to `payments`, with the two
    clocks written out — and prints both numbers side by side. They must
    match; if they do not, the script says so and exits 2.

⚠ **WHAT IT DOES NOT MEASURE**, named because a blind spot with no number is
indistinguishable from an empty one: it calls the read model directly, so no
HTTP, no serialisation, no front end. It measures ONE tenant and says which.
And it cannot see bills that are `void` or `corrected` today — nothing records
the day a live bill stopped being live (`DEF-PAY-7020`) — so it prints the
COUNT of those instead.

USAGE
    10-scripts/proof-db.sh clone ageing
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_ageing \\
      python3 ../10-scripts/def_pay_6940_as_at_ageing.py
"""

from __future__ import annotations

import os
import pathlib
import sys
from datetime import date
from decimal import Decimal

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402

from apps.payments import reporting  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402

BANDS = ("current", "1-30", "31-60", "61-90", "90+")

#: The three dates `DEF-PAY-6940` was reported against, kept verbatim so the
#: register row can be re-run exactly as it was written.
REPORTED = (date(2026, 9, 30), date(2025, 9, 30), date(2024, 1, 31))


def _shape() -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            "select (select count(*) from invoices where status in ('issued','paid')),"
            " (select min(issued_at)::date from invoices where status in ('issued','paid')),"
            " (select max(issued_at)::date from invoices where status in ('issued','paid')),"
            " (select count(*) from payments),"
            " (select min(posted_at)::date from payments),"
            " (select max(posted_at)::date from payments),"
            " (select count(*) from invoices where status in ('void','corrected'))"
        )
        row = cursor.fetchone()
    keys = (
        "open_bills",
        "first_issue",
        "last_issue",
        "payments",
        "first_posting",
        "last_posting",
        "retired_bills",
    )
    return dict(zip(keys, row))


def _by_hand(as_of: date) -> tuple[Decimal, int]:
    """The same position, in SQL that shares no line with the read.

    `amount_due` is `BR-BIL-072`'s ❄️ *"Level is due"* — the budget payload's
    figure when there is one, the bill's total otherwise. Money never leaves
    `numeric` (hard rule 2).
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            with due as (
              select i.id, i.account_id,
                     coalesce((i.bill_payload->'budget'->>'amount_due')::numeric,
                              i.total) as amount_due
                from invoices i
               where i.status in ('issued','paid')
                 and (i.issued_at at time zone 'UTC')::date <= %s
            ), paid as (
              select a.invoice_id, sum(a.amount) as amt
                from allocations a
                join payments p on p.id = a.payment_id
               where (p.posted_at at time zone 'UTC')::date <= %s
               group by a.invoice_id
            ), open_bills as (
              select due.account_id,
                     due.amount_due - coalesce(paid.amt, 0) as balance
                from due left join paid on paid.invoice_id = due.id
            )
            select coalesce(sum(balance), 0), count(distinct account_id)
              from open_bills where balance > 0
            """,
            [as_of, as_of],
        )
        total, debtors = cursor.fetchone()
    return Decimal(total), int(debtors)


def main() -> int:
    with connection.cursor() as cursor:
        cursor.execute(
            "select rolname, rolsuper, rolbypassrls from pg_roles where rolname = current_user"
        )
        role, superuser, bypass = cursor.fetchone()
    print(f"role {role}  rolsuper={superuser}  rolbypassrls={bypass}")
    if superuser or bypass:
        print("  ⚠ this role BYPASSES row-level security; hard rule 1 is not")
        print("    being exercised by this run, only the arithmetic is.")

    tenant = tenancy_models.Tenant.objects.order_by("created_at").first()
    if tenant is None:
        print("MEASURED NOTHING: this database holds no tenant.")
        return 2
    print(f"tenant {tenant.id}  {getattr(tenant, 'name', '')}")

    with tenant_context(str(tenant.id)):
        shape = _shape()
        print(
            f"  open bills {shape['open_bills']} issued "
            f"{shape['first_issue']} → {shape['last_issue']}"
        )
        print(
            f"  payments   {shape['payments']} posted "
            f"{shape['first_posting']} → {shape['last_posting']}"
        )
        print(f"  retired bills today (void/corrected) {shape['retired_bills']}")
        if not shape["open_bills"]:
            print("MEASURED NOTHING: no open bills in this tenant.")
            return 2

        first, last = shape["first_issue"], shape["last_issue"]
        ladder = sorted(
            {
                first.replace(day=1),
                first,
                date(first.year, first.month, 15) if first.day <= 15 else first,
                last,
                *REPORTED,
            }
        )

        print()
        header = "  as_of      " + "".join(f"{band:>14}" for band in BANDS)
        print(header + f"{'total':>14}{'accts':>7}  problems")
        print("  " + "─" * (len(header) + 19))
        for as_of in ladder:
            body = reporting.ar_aging(as_of=as_of, per=None)
            totals = body["totals"]
            codes = [
                problem["code"]
                for problem in body["problems"]
                if problem["code"] != "imported_opening_buckets_are_not_built"
            ]
            cells = "".join(f"{str(totals[band]):>14}" for band in BANDS)
            print(
                f"  {as_of}"
                + cells
                + f"{str(totals['total']):>14}{totals['accounts']:>7}  "
                + (",".join(codes) or "—")
            )

        print()
        print("  the same position, re-derived in hand-written SQL:")
        failures = 0
        for as_of in ladder:
            body = reporting.ar_aging(as_of=as_of, per=None)
            hand_total, hand_debtors = _by_hand(as_of)
            read_total = Decimal(body["totals"]["total"])
            read_debtors = body["totals"]["accounts"]
            agree = hand_total == read_total and hand_debtors == read_debtors
            failures += 0 if agree else 1
            print(
                f"  {as_of}  read {read_total}/{read_debtors}"
                f"   by hand {hand_total}/{hand_debtors}   "
                + ("agree" if agree else "⚠ DISAGREE")
            )

        print()
        if failures:
            print(f"FAIL: {failures} date(s) where the read and the hand SQL disagree.")
            return 2
        distinct = {
            reporting.ar_aging(as_of=as_of, per=None)["totals"]["total"]
            for as_of in ladder
        }
        print(
            f"PASS: {len(ladder)} dates agree with hand SQL; {len(distinct)} distinct totals."
        )
        if len(distinct) == 1 and len(ladder) > 1:
            print("  ⚠ ONE distinct total over every date — that is `DEF-PAY-6940`'s")
            print("    signature. Either the read does not look back, or this tenant")
            print("    genuinely never moved. The header above says which.")
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
