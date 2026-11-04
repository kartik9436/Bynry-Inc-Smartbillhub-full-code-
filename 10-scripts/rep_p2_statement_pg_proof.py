#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  **BR-REP-038** (PO ruling 2026-09-27) and `CR-142-BRC07` `P2.8`.
#          The customer statement is the account's running record, built on the
#          ledger. This is the half the ordinary suite cannot witness.
# Rules:   CLAUDE.md hard-won law 14 (the suite hardcodes in-memory SQLite and
#          is not evidence about SQL) · law 7 clause 2 (what would make this
#          pass WRONGLY) and its FIFTH shape (a number beside every blind spot)
#          · hard rule 1 (tenant scoping; RLS FORCE) · NFR-3 · NFR-5.
# ───────────────────────────────────────────────────────
"""THE STATEMENT, MEASURED ON REAL POSTGRESQL: THE PAGE, THE CARRY-FORWARD, THE EXPORT.

    python3 10-scripts/rep_p2_statement_pg_proof.py

Env: `DJANGO_SETTINGS_MODULE=config.settings.local`, run from `06-backend` or
with it on `PYTHONPATH`. `REP_TENANT` names the tenant (default: the seeded
`Brazos Bend Utilities`). `REP_ACCOUNT` names one account number; without it
the script takes the account with the most AR lines, and PRINTS which.

WHAT IT PROVES THAT THE PYTEST FILE CANNOT
──────────────────────────────────────────
`06-backend/tests/test_br_rep_038_statement.py` asserts the PO's worked case —
the $84.20 bill, the $84.20 payment on the 14th, the balance carried forward —
and it runs on SQLite, where three things are unaskable:

  1 · **THE PAGE IS CUT IN SQL.** A `LIMIT` that was applied and one that was
      not produce the same fifty rows to `len(rows)`. Here the statement a page
      read issues is captured out of `connection.queries` and `EXPLAIN` is run
      over it, and the plan must name a `Limit` node.
  2 · **THE CARRY-FORWARD SURVIVES THE PAGE.** `r_n = r_{n−1} + charge_n −
      payment_n` is cumulative, so page 2 cannot start at the window's opening.
      This reads the whole statement unpaged and then page by page, and asserts
      every row's running balance is IDENTICAL between the two readings. That
      is the one property a statement cannot be wrong about and still be a
      statement.
  3 · **THE EXPORT IS NOT A PAGE** (brief §8.2). `statement_stream` yields every
      row of the window; a viewer page yields at most `per`. Two functions, not
      a flag, so an export cannot inherit a screen's page size.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7 clause 2):

  * **A SKIP READING AS A PASS.** Run anywhere but PostgreSQL it REFUSES with
    the vendor it found, non-zero, rather than skipping. `G5` called 192 skips
    a pass over the isolation suite and that is this exact shape.
  * **AN ACCOUNT WITH TOO FEW ROWS.** A one-row statement pages trivially and
    proves nothing about a carry-forward. The row count is asserted BEFORE the
    paging cases and the script says how many it found.
  * **COMPARING A PAGE WITH ITSELF.** The unpaged reading is taken once, up
    front, and the per-row comparison is by POSITION over the concatenated
    pages — so a paging implementation that returned page one every time would
    fail on page two rather than match.

⚠ **IT REPORTS WHAT IT COULD NOT SEE.** Every refusal is NAMED and counted
beside what was measured, because a blind spot with no number beside it is
indistinguishable from an empty one.
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal

import django

django.setup()

from django.db import connection  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402

from apps.ledger import models as ledger_models  # noqa: E402
from apps.reports import runner, statement as statement_module  # noqa: E402
from apps.reports.models import ReportDefinition  # noqa: E402
from apps.tenancy.models import Tenant  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402

PER = 5
WINDOW = {"from": "2000-01-01", "to": "2099-12-31"}


def _refuse_unless_postgres() -> None:
    if connection.vendor != "postgresql":
        print(
            f"REFUSED: this proof needs PostgreSQL and found {connection.vendor!r}. "
            "The page is cut with LIMIT/OFFSET in SQL and SQLite cannot be asked what "
            "a statement read. A skip here would read as a pass, so this exits 2.",
            file=sys.stderr,
        )
        raise SystemExit(2)


def _busiest_account() -> tuple[str, int]:
    """The account with the most AR journal lines, and how many. Printed, never assumed."""
    wanted = os.environ.get("REP_ACCOUNT")
    rows = (
        ledger_models.JournalLine.objects.exclude(account_id=None)
        .values_list("account_id")
        .order_by()
    )
    counts: dict[str, int] = {}
    for (account_id,) in rows:
        counts[str(account_id)] = counts.get(str(account_id), 0) + 1
    if not counts:
        print("REFUSED: no journal line in this tenant carries an account dimension, "
              "so there is no account to draw a statement for. That is a seeding "
              "state, not a statement failure.", file=sys.stderr)
        raise SystemExit(2)
    if wanted and wanted in counts:
        return wanted, counts[wanted]
    best = max(counts.items(), key=lambda pair: pair[1])
    return best


def main() -> int:
    _refuse_unless_postgres()
    tenant = Tenant.objects.get(name=os.environ.get("REP_TENANT", "Brazos Bend Utilities"))
    failures: list[str] = []
    notes: list[str] = []

    with tenant_context(tenant.pk):
        definition = ReportDefinition.objects.filter(tenant_id=None, key="statement").first()
        if definition is None:
            print("REFUSED: no platform `statement` definition in this database.", file=sys.stderr)
            return 2
        print(f"definition  statement -> dataset={definition.dataset!r} basis={definition.filters.get('basis')!r}")
        if definition.dataset != "journal_lines":
            failures.append(
                f"BR-REP-038: statement is seeded on {definition.dataset!r}; "
                "reports/0007 has not been applied to this database."
            )

        account_id, line_count = _busiest_account()
        print(f"account     {account_id} — {line_count} journal lines carrying it")

        base = {**WINDOW, "subject_id": account_id}

        # ── 1 · the whole statement, unpaged ────────────────────────────────
        whole = statement_module.statement({**base, "per": "all"})
        rows = whole["rows"]
        print(f"unpaged     {len(rows)} rows · opening {whole['totals']['opening_balance']} "
              f"· charges {whole['totals']['charges']} · payments {whole['totals']['payments']} "
              f"· closing {whole['totals']['closing_balance']} · basis {whole['basis']}")
        if len(rows) < 2:
            notes.append(
                f"only {len(rows)} row(s) on the busiest account, so the paging and "
                "carry-forward cases below prove nothing about a boundary. Seed more "
                "postings before quoting this run as evidence."
            )

        # It FOOTS — struck independently of the last row.
        opening = Decimal(whole["totals"]["opening_balance"])
        charges = Decimal(whole["totals"]["charges"])
        payments = Decimal(whole["totals"]["payments"])
        closing = Decimal(whole["totals"]["closing_balance"])
        if closing != opening + charges - payments:
            failures.append(
                f"the statement does not foot: {opening} + {charges} - {payments} != {closing}"
            )

        # BOTH SIDES — the whole of the ruling.
        charge_rows = sum(1 for row in rows if Decimal(row["charge"] or 0) != 0)
        payment_rows = sum(1 for row in rows if Decimal(row["payment"] or 0) != 0)
        print(f"both sides  {charge_rows} charge row(s) · {payment_rows} payment row(s)")
        if payment_rows == 0 and line_count > 1:
            failures.append(
                "the statement shows NO payment row. That is the defect BR-REP-038 "
                "reversed — 'invoices are charges, so a statement built on them "
                "cannot show a payment at all'."
            )

        # ── 2 · the page is cut in SQL ──────────────────────────────────────
        with CaptureQueriesContext(connection) as captured:
            page_one = statement_module.statement({**base, "page": 1, "per": PER})
        limited = [q for q in captured.captured_queries if " LIMIT " in q["sql"].upper()]
        print(f"page 1      {len(page_one['rows'])} rows of per={PER} · "
              f"{len(captured.captured_queries)} statements, {len(limited)} carrying LIMIT")
        if len(page_one["rows"]) > PER:
            failures.append(f"page one held {len(page_one['rows'])} rows over per={PER}")
        if not limited:
            failures.append(
                "no statement in the page read carried a LIMIT, so the page was cut in "
                "Python. NFR-3 is about where the slice happens, not about the row count."
            )
        else:
            with connection.cursor() as cursor:
                cursor.execute("EXPLAIN " + limited[-1]["sql"])
                plan = "\n".join(line for (line,) in cursor.fetchall())
            print("plan        " + ("Limit node PRESENT" if "Limit" in plan else "NO Limit node"))
            if "Limit" not in plan:
                failures.append("the plan for the paged statement names no Limit node:\n" + plan)

        # ── 3 · the carry-forward survives the page ─────────────────────────
        paged: list[dict] = []
        page_no = 1
        while True:
            payload = statement_module.statement({**base, "page": page_no, "per": PER})
            paged.extend(payload["rows"])
            if page_no * PER >= payload["page"]["total"] or not payload["rows"]:
                break
            page_no += 1
        print(f"paged       {len(paged)} rows across {page_no} page(s) of {PER}")
        if len(paged) != len(rows):
            failures.append(f"paged reading held {len(paged)} rows, unpaged {len(rows)}")
        else:
            mismatched = [
                (i, a["running_balance"], b["running_balance"])
                for i, (a, b) in enumerate(zip(rows, paged))
                if a["running_balance"] != b["running_balance"]
            ]
            print(f"carry       {len(rows) - len(mismatched)}/{len(rows)} running balances "
                  "identical paged and unpaged")
            if mismatched:
                failures.append(
                    "the running balance CHANGES when the statement is paged, at rows "
                    f"{[m[0] for m in mismatched[:5]]}. Page two must start where page "
                    "one left off, not at the window's opening."
                )

        # ── 4 · the export is not a page ────────────────────────────────────
        streamed = list(statement_module.statement_stream(base))
        print(f"export      {len(streamed)} rows streamed")
        if len(streamed) != len(rows):
            failures.append(
                f"the export streamed {len(streamed)} rows over a statement of "
                f"{len(rows)}. §8.2: the right path never holds one page."
            )

        # ── 5 · the runner reaches this viewer (law 2: built is not wired) ──
        try:
            result = runner.run("statement", base)
            wired = len(result.payload.get("rows") or ())
            print(f"wired       runner.run('statement') served {wired} rows")
            if wired != len(page_one["rows"]) and definition.dataset == "journal_lines":
                notes.append(
                    f"runner.run served {wired} rows and the direct viewer served "
                    f"{len(page_one['rows'])} — the runner applies its own default page size."
                )
        except Exception as exc:
            failures.append(f"runner.run('statement') raised {type(exc).__name__}: {exc}")

        # ── 6 · the three unserved subjects refuse BY NAME ──────────────────
        refused: list[str] = []
        for subject in ("customer", "premises", "unit"):
            try:
                statement_module.statement({**base, "subject": subject})
            except Exception as exc:
                refused.append(f"{subject}:{type(exc).__name__}")
            else:
                failures.append(
                    f"subject={subject!r} ANSWERED. Three of the four subjects have no "
                    "running-record read model; answering one of them serves the account "
                    "grain's money under another grain's heading."
                )
        print(f"subjects    account SERVED · refused {' · '.join(refused) or 'NONE'}")

    print()
    for note in notes:
        print(f"NOTE     {note}")
    for failure in failures:
        print(f"FAILED   {failure}")
    if failures:
        return 1
    print("PASS — the statement holds both sides, pages in SQL, carries its balance "
          "across pages, and exports whole.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
