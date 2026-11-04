#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-LED-6640 — the demo fixture's calendar is a set of fixed 2026
#          dates (`core/sample_fixture.py` `PERIODS`: June and July billed,
#          August read-and-unbilled), so once the real clock passes August
#          EVERY period-scoped Finance screen reads $0.00 on a database that
#          holds 80 invoices, 66 payments and 167 journal entries.
#          DEF-GOV-6641 — the zero that was reported instead was a psql count
#          taken with no `app.tenant_id` set.
# Rules:   CLAUDE.md hard rule 1 (tenant scoping — every write inside
#          `tenancy.tenant_context`) · hard rule 2 (money stored to 4 decimals,
#          never float — every amount here is a `Decimal`) · hard rule 4 (money
#          rows are append-only — this script never UPDATEs or DELETEs one) ·
#          hard rule 5 (only the ledger posting service writes journal lines —
#          this script writes none; it calls the payments services, which post)
#          · hard rule 6 (idempotency — every payment carries an
#          `idempotency_reference`, so a replay writes nothing) · hard rule 7
#          (every money action writes `audit_log` — via those services) ·
#          BR-PAY-020 (a write-off is a request, then an approval) ·
#          BR-TEN-022 (the accounting period is COMPUTED, never stored).
# Tests:   there is no automated test for this script and it does not pretend
#          otherwise — it is a DEMO tool, and its proof is `--report`, which
#          reads the figures back out of the database it just wrote to and
#          foots the trial balance. Run `--report` before and after.
# Impacts: the database named by `--database` and NOTHING else. It refuses the
#          shared `smartbillhub` by name unless told twice.
# ───────────────────────────────────────────────────────
"""Put money in the **open accounting period** of a demo tenant, so the Finance
screens have something true to show today.

WHY THIS EXISTS, AND WHY IT IS NOT A SECOND SEEDER
====================================================
`apps/tenancy/management/commands/load_sample_data.py` already owns seeding a
tenant, and its own docstring says the thing that matters here: *"It is not a
second seeder."* This script does not seed a tenant, does not create accounts,
premises, plans or bills, and shares no code path with a fixture. It does one
thing the fixture **cannot** do, and the reason is in `DEF-LED-6640`:

⚠⚠ **THE PARAGRAPH BELOW WAS OVERTAKEN ON 2026-09-25, AND THIS SCRIPT STILL
HAS A JOB — READ WHICH ONE BEFORE REACHING FOR IT.** `DEF-LED-6640` is fixed at
the source: `core/sample_fixture.py` no longer holds its calendar as constants,
it SHIFTS the whole table by whole months so that today always falls inside the
open, unbilled period. **So a tenant seeded FROM NOW ON does not need this
script at all** — its two billed cycles and its cash are already in months a
clerk can see.

**What this script is still the only tool for: a tenant that ALREADY EXISTS.**
Hard rule 4 makes issued invoices, payments and journal entries append-only, so
an old tenant's money **cannot be re-dated** — not by this script, not by any
script, not by a migration. The fixture's fix reaches new tenants only. An
existing demo is brought back to life either by re-seeding a FRESH tenant (the
clean answer) or by this script, which adds NEW cash-side rows in the open
period without touching a single row that is already there.

⚠ **AND IT IS STILL NOT A SECOND SEEDER, for the same reason as before.** It
creates no account, premises, plan or bill. It does not bill the open month and
must not: see the note at the foot of this docstring.

**THE SUPERSEDED DIAGNOSIS IS KEPT BELOW**, because a reader who meets this
script in a year is entitled to see what it was written against.

`core/sample_fixture.py` holds its calendar as `date()` CONSTANTS — June 2026
billed, July 2026 billed, August 2026 read-and-unbilled. That was correct the
day it was written. **The Finance screens show the CURRENT accounting period**
(`useFinancePeriod` → `GET /shell/display`, computed per `BR-TEN-022`), and
there is no period picker to move off it. So on any day after 31 August 2026 a
clerk opening Finance sees:

    BILLED THIS MONTH  $0.00        COLLECTED  $0.00
    "No revenue was posted to the books in this period."

…on a database holding 80 invoices and 66 payments. Nothing is broken and
nothing is lying; the money is simply in a month the screen cannot show.

WHAT IT WRITES, AND WHAT IT DELIBERATELY DOES NOT
===================================================
**It writes CASH-SIDE activity dated inside the open period**, through the same
service functions the S22 *Record a payment* form and the S34/S35 *Write off*
act call:

  1. **Payments** against accounts that genuinely owe, `record_payment`, spread
     over several days of the open period with mixed tenders, so deposit
     batches form for a cash/cheque day and the journal gains entries.
  2. **A write-off awaiting approval** — `request_write_off`. It moves no money
     (that is `BR-PAY-020`'s whole point) and it is what makes the *Write-offs*
     view and its pending badge visible instead of rendering nothing.
  3. **One approved write-off** — `approve_write_off`, which is where the money
     moves, so *Written off YTD* stops reading *Not available*.

**It does NOT run a bill run and does NOT issue an invoice.** That is not
timidity, it is the fixture's own instruction: August is left
read-and-unbilled ON PURPOSE — *"everything done leaves nothing to evaluate"* —
because the PO's own acceptance test is to run that cycle themselves. Billing
it here would delete their acceptance test. So **BILLED THIS MONTH stays
$0.00**, correctly, and the gallery README says so in words rather than letting
a reader assume the screen is broken.

RE-RUNNABLE, AND HOW
=====================
**Idempotent.** Every payment carries an `idempotency_reference` of the form
`finseed:cp:<period>:<n>`, so `record_payment`'s own replay read answers a
second run with `created=False` and writes nothing (hard rule 6). Each
write-off is looked up by the marker in its note before being requested. A
second run therefore reports the same figures and changes no count — which is
also the only honest way to re-run it, because hard rule 4 means nothing it
writes can ever be removed.

USAGE
======
    # look, write nothing
    10-scripts/seed_finance_current_period.py --database sbh_clone_mine --report

    # write
    10-scripts/seed_finance_current_period.py --database sbh_clone_mine

It **refuses to run with no `--database`**, and refuses the shared
`smartbillhub` by name unless `--yes-the-shared-demo` is also given — six lanes
read that database and several assert on its current contents.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "06-backend"

#: The shared demo database. Refused by name unless the caller says so twice.
SHARED_DEMO = "smartbillhub"

#: How the money is spread across the open period. Each entry is
#: (days before today, tender, how many accounts, share of what they owe).
#: Cash and cheques bank in a counter drawer, so they form deposit batches;
#: card and ACH deliberately do not (`counters.HAND_TENDERS`).
#:
#: ⚠ **THE SHARES ARE MOSTLY PARTIAL AND THE LIST IS SHORTER THAN THE QUEUE OF
#: ACCOUNTS THAT OWE, ON PURPOSE.** Collecting everything in full would empty
#: the ageing buckets, which are the thing the Aging view and the Dashboard
#: exist to show — a demo where nobody is behind is not a demo of a utility.
#: So a mix of full and part payments is taken, and the accounts furthest
#: behind are deliberately LEFT ALONE, exactly as `core/sample_fixture.py`
#: leaves its 70-day case unpaid rather than stamping an age on it.
#: ⚠ **THE LAST FOUR WAVES TAKE A TENTH OR SO FROM A LOT OF ACCOUNTS, AND THAT
#: IS WHAT MAKES THE JOURNAL PAGE.** The journal's rows-per-page chooser starts
#: at **50** (`components/tableTypes.ts PAGE_SIZES`), so its arrows cannot come
#: alive until the open period holds more than fifty entries — and paging that
#: list was the whole of `P1.8`. Adding more FULL payments would have bought
#: those rows by emptying the ageing buckets. A small part payment buys the
#: same row and leaves the account still owing, so the two can both be true.
CASH_DAYS: tuple[tuple[int, str, int, str], ...] = (
    (18, "check", 3, "1.00"),
    (18, "cash", 2, "0.60"),
    (12, "card", 3, "1.00"),
    (9, "ach", 2, "0.45"),
    (5, "check", 2, "0.50"),
    (5, "money_order", 1, "1.00"),
    (2, "cash", 2, "0.75"),
    (2, "card", 1, "0.40"),
)

#: The second pass, run against a FRESHLY READ list of who still owes — so a
#: small payment is always a slice of a balance that is really there, never of
#: a figure the first pass has already collected.
SMALL_DAYS: tuple[tuple[int, str, int, str], ...] = (
    (16, "card", 6, "0.08"),
    (11, "ach", 6, "0.07"),
    (7, "check", 5, "0.10"),
    (3, "card", 5, "0.06"),
)

#: How many accounts overpay, and by how much. An overpayment is the ONLY way
#: to put a refund in the queue honestly: `request_refund` refuses an account
#: that owes money — *"the credit is offset against it FIRST"* (PO ruling
#: 2026-08-12) — so a refund needs a real credit balance behind it, and a
#: credit balance comes from somebody paying too much. `core/sample_fixture.py`
#: already names this case 11, *"one account overpays"*; this is three more of
#: the same thing, so the Refunds queue has something waiting.
OVERPAYMENTS: tuple[tuple[int, str], ...] = (
    (14, "40.00"),
    (8, "25.00"),
    (4, "60.00"),
)

#: The two write-offs. `approve=False` is the one that makes the pending badge
#: and the queue visible; `approve=True` is the one that moves money.
WRITE_OFFS: tuple[dict[str, Any], ...] = (
    {
        "marker": "finseed-wo-pending-1",
        "reason": "uncollectible_120_days",
        "note": "Mail returned twice and the telephone is disconnected. No forwarding address.",
        "approve": False,
    },
    {
        "marker": "finseed-wo-pending-2",
        "reason": "deceased_no_estate",
        "note": "Death certificate on file. The estate was closed with no assets.",
        "approve": False,
    },
    {
        "marker": "finseed-wo-approved-1",
        "reason": "below_write_off_threshold",
        "note": "A residual cent balance left after the final bill was settled. Not worth billing.",
        "approve": True,
    },
)


def _bootstrap(database: str) -> None:
    """Point Django at exactly the database named, and nothing else."""
    os.environ["DATABASE_URL"] = (
        f"postgres://smartbillhub:smartbillhub@127.0.0.1:5432/{database}"
    )
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    os.environ.setdefault("JOBS_EAGER", "false")
    sys.path.insert(0, str(BACKEND))
    import django

    django.setup()


def _money(value: Any) -> Decimal:
    """Every amount in this file is a Decimal (hard rule 2 — never float)."""
    return Decimal(str(value)).quantize(Decimal("0.0001"))


def _display(value: Any) -> str:
    return f"${_money(value).quantize(Decimal('0.01')):,}"


def _report(tenant_id: str) -> dict[str, Any]:
    """Read the figures back OUT of the database. This is the proof."""
    from django.db import connection

    rows: dict[str, Any] = {}
    with connection.cursor() as cur:
        cur.execute("select set_config('app.tenant_id', %s, false)", [tenant_id])
        for label, sql in (
            ("invoices", "select count(*) from invoices"),
            ("invoice_lines", "select count(*) from invoice_lines"),
            ("payments", "select count(*) from payments"),
            ("journal_entries", "select count(*) from journal_entries"),
            ("journal_lines", "select count(*) from journal_lines"),
            ("deposit_batches", "select count(*) from deposit_batches"),
            ("refunds", "select count(*) from refunds"),
            ("write_offs", "select count(*) from write_offs"),
            ("fiscal_period_closes", "select count(*) from fiscal_period_closes"),
        ):
            cur.execute(sql)
            rows[label] = cur.fetchone()[0]
        cur.execute(
            """
            select coalesce(sum(case when side='debit'  then amount else 0 end), 0),
                   coalesce(sum(case when side='credit' then amount else 0 end), 0)
            from journal_lines
            """
        )
        debit, credit = cur.fetchone()
        rows["trial_balance_debit"] = _money(debit)
        rows["trial_balance_credit"] = _money(credit)
        rows["trial_balance_difference"] = _money(debit) - _money(credit)
        cur.execute(
            """
            select count(*) from (
              select journal_entry_id from journal_lines group by journal_entry_id
              having sum(case when side='debit' then amount else -amount end) <> 0
            ) unbalanced
            """
        )
        rows["unbalanced_entries"] = cur.fetchone()[0]
        cur.execute("select status, count(*) from write_offs group by status")
        rows["write_offs_by_status"] = dict(cur.fetchall())
    return rows


def _print_report(title: str, rows: dict[str, Any]) -> None:
    print(f"\n── {title} " + "─" * max(0, 58 - len(title)))
    for key in (
        "invoices",
        "invoice_lines",
        "payments",
        "journal_entries",
        "journal_lines",
        "deposit_batches",
        "refunds",
        "write_offs",
        "fiscal_period_closes",
    ):
        print(f"   {key:<22} {rows[key]}")
    if rows["write_offs_by_status"]:
        print(f"   {'write_offs by status':<22} {rows['write_offs_by_status']}")
    print(
        f"   {'TRIAL BALANCE':<22} debit {_display(rows['trial_balance_debit'])}"
        f"  ·  credit {_display(rows['trial_balance_credit'])}"
    )
    footed = rows["trial_balance_difference"] == 0 and rows["unbalanced_entries"] == 0
    print(
        f"   {'':<22} difference {_display(rows['trial_balance_difference'])}"
        f"  ·  unbalanced entries {rows['unbalanced_entries']}"
        f"  ·  {'FOOTS' if footed else '*** DOES NOT FOOT ***'}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Put cash-side money in a demo tenant's OPEN accounting period, "
            "through the real payment and write-off services."
        )
    )
    parser.add_argument(
        "--database",
        required=True,
        help=(
            "the database to write to. REQUIRED — there is no default, because "
            "a default would be the shared demo."
        ),
    )
    parser.add_argument("--tenant", default="brazosbend", help="the tenant's subdomain")
    parser.add_argument(
        "--yes-the-shared-demo",
        action="store_true",
        help=(
            f"permit --database {SHARED_DEMO}. Six lanes read that database and "
            "several assert on its current contents."
        ),
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="read the figures out and write NOTHING",
    )
    args = parser.parse_args()

    if args.database == SHARED_DEMO and not args.yes_the_shared_demo:
        print(
            f"REFUSED: --database {SHARED_DEMO} is the shared demo database that "
            "six lanes are reading, and several of them assert on its current "
            "contents. Clone it first (10-scripts/proof-db.sh clone <label>, or "
            "CREATE DATABASE <yours> TEMPLATE smartbillhub) and point this at the "
            "clone. If you really mean the shared one, pass --yes-the-shared-demo.",
            file=sys.stderr,
        )
        return 2

    _bootstrap(args.database)

    from django.db import connection

    if connection.vendor != "postgresql":
        print(
            "REFUSED: tenant context is a Postgres GUC (core/tenancy.py) and "
            "sqlite cannot run it, so every write would be unscoped "
            "(CLAUDE.md hard rule 1). Nothing was written.",
            file=sys.stderr,
        )
        return 2

    from apps.identity import models as ident
    from apps.payments import billing_seam, refunds, services as pay_services, writeoffs
    from apps.payments import collections_models as pay_collections
    from apps.tenancy import models as ten, selectors as ten_selectors
    from core import tenancy as core_tenancy

    tenant = ten.Tenant.objects.filter(subdomain=args.tenant).first()
    if tenant is None:
        print(
            f"REFUSED: no tenant with subdomain {args.tenant!r} in database "
            f"{args.database!r}. Nothing was written.",
            file=sys.stderr,
        )
        return 2

    print(f"database : {args.database}")
    print(f"tenant   : {tenant.name} ({tenant.subdomain}) {tenant.id}")

    before = _report(str(tenant.id))
    _print_report("BEFORE", before)

    if args.report:
        print("\n--report was given: nothing was written.")
        return 0

    with core_tenancy.tenant_context(str(tenant.id)):
        period = ten_selectors.current_period()
        if period is None:
            print(
                "REFUSED: this tenant has no fiscal year start, so it has no "
                "current period (BR-TEN-022) and there is no open window to put "
                "money in. Nothing was written.",
                file=sys.stderr,
            )
            return 2
        period_start = date.fromisoformat(period["start"])
        period_end = date.fromisoformat(period["end"])
        print(
            f"period   : {period['fy_label']} period {period['period']} "
            f"{period_start} – {period_end} ({period['status']})"
        )

        user = (
            ident.User.objects.filter(tenant=tenant).order_by("created_at").first()
        )
        if user is None:
            print("REFUSED: this tenant has no user to act as.", file=sys.stderr)
            return 2
        actor = SimpleNamespace(
            id=user.id, pk=user.id, role="system_admin", roles=("system_admin",),
            user=user, is_authenticated=True,
        )

        # ── who owes, and how much ─────────────────────────────────────────
        positions, _ = billing_seam.outstanding_positions()
        owing = [p for p in positions if _money(p.balance) > 0]
        owing.sort(key=lambda p: _money(p.balance), reverse=True)
        print(f"accounts owing before: {len(owing)}")
        if not owing:
            print("nothing is owed, so there is nothing to collect. Stopping.")
            return 0

        # ── 1 · cash in the open period ────────────────────────────────────
        today = date.today()
        taken = 0
        replayed = 0
        collected = Decimal("0")
        seq = 0

        def collect(waves, queue):
            """One pass of payments over `queue`. Returns nothing; the counters
            above are updated in place."""
            nonlocal taken, replayed, collected, seq
            cursor = 0
            for days_back, tender, how_many, share in waves:
                when = today - timedelta(days=days_back)
                if when < period_start:
                    when = period_start
                if when > period_end:
                    when = period_end
                posted_at = datetime.combine(when, time(hour=10, minute=30))
                posted_at = posted_at.replace(tzinfo=_utc())
                for _ in range(how_many):
                    if cursor >= len(queue):
                        break
                    position = queue[cursor]
                    cursor += 1
                    seq += 1
                    amount = (_money(position.balance) * Decimal(share)).quantize(
                        Decimal("0.01")
                    )
                    if amount <= 0:
                        continue
                    reference = f"finseed:cp:{period_start.isoformat()}:{seq:03d}"
                    try:
                        result = pay_services.record_payment(
                            actor,
                            account_id=position.account_id,
                            amount=_money(amount),
                            posted_at=posted_at,
                            cleared_at=posted_at,
                            currency="USD",
                            method_code=tender,
                            confirmation=(
                                f"{seq:06d}"
                                if tender in ("check", "money_order")
                                else None
                            ),
                            memo="Payment taken in the current period",
                            idempotency_source=(
                                "entry"
                                if tender in ("cash", "check", "money_order")
                                else "webhook"
                            ),
                            idempotency_reference=reference,
                        )
                    except Exception as exc:  # surfaced, never swallowed
                        print(
                            f"   ! {tender} {amount} on {when}: "
                            f"{type(exc).__name__}: {exc}"
                        )
                        continue
                    if getattr(result, "created", True):
                        taken += 1
                        collected += amount
                    else:
                        replayed += 1

        collect(CASH_DAYS, owing)
        # Re-read who still owes before the small-payment pass — a slice of a
        # balance the first pass already collected is not a real payment.
        positions, _ = billing_seam.outstanding_positions()
        still = [p for p in positions if _money(p.balance) > 0]
        still.sort(key=lambda p: _money(p.balance), reverse=True)
        collect(SMALL_DAYS, still)
        print(
            f"payments : {taken} recorded, {replayed} already there (replayed), "
            f"{_display(collected)} collected"
        )

        # ── 2 · a few overpayments, and the refunds they make possible ─────
        positions, _ = billing_seam.outstanding_positions()
        payers = [p for p in positions if _money(p.balance) > 0]
        payers.sort(key=lambda p: _money(p.balance))
        overpaid = 0
        refunds_asked = 0
        refunds_replayed = 0
        for index, (days_back, extra) in enumerate(OVERPAYMENTS):
            if index >= len(payers):
                break
            position = payers[index]
            when = min(max(today - timedelta(days=days_back), period_start), period_end)
            posted_at = datetime.combine(when, time(hour=11)).replace(tzinfo=_utc())
            surplus = _money(extra)
            amount = _money(position.balance) + surplus
            reference = f"finseed:over:{period_start.isoformat()}:{index + 1:02d}"
            try:
                result = pay_services.record_payment(
                    actor,
                    account_id=position.account_id,
                    amount=amount,
                    posted_at=posted_at,
                    cleared_at=posted_at,
                    currency="USD",
                    method_code="check",
                    confirmation=f"9{index + 1:05d}",
                    memo="Paid more than the bill",
                    idempotency_source="entry",
                    idempotency_reference=reference,
                )
                if getattr(result, "created", True):
                    overpaid += 1
            except Exception as exc:
                print(f"   ! overpayment {index + 1}: {type(exc).__name__}: {exc}")
                continue
            # …and ask for it back. The refund is REQUESTED and left that way:
            # approving it is a person's act, and an empty queue is the thing
            # this whole script exists to fix.
            try:
                asked = refunds.request_refund(
                    actor,
                    account_id=position.account_id,
                    amount=surplus,
                    method="check",
                    requested_at=datetime.combine(
                        min(today, period_end), time(hour=15)
                    ).replace(tzinfo=_utc()),
                    reason="overpayment",
                    memo="Customer paid twice and asked for the difference back.",
                    idempotency_key=f"finseed:refund:{period_start.isoformat()}:{index + 1:02d}",
                )
                # `created=False` is the idempotent replay of a request that
                # already exists under the same key. Counting it as a new one
                # would make a replay REPORT work it did not do — which is the
                # shape of check this repo files defects about.
                if getattr(asked, "created", True):
                    refunds_asked += 1
                else:
                    refunds_replayed += 1
            except Exception as exc:
                print(f"   ! refund {index + 1}: {type(exc).__name__}: {exc}")
        print(
            f"overpayments: {overpaid} taken, {refunds_asked} refunds asked for, "
            f"{refunds_replayed} already there (replayed)"
        )

        # ── 3 · the write-off queue ────────────────────────────────────────
        positions, _ = billing_seam.outstanding_positions()
        still_owing = [p for p in positions if _money(p.balance) > 0]
        still_owing.sort(key=lambda p: _money(p.balance))
        requested = 0
        approved = 0
        skipped = 0
        for index, plan in enumerate(WRITE_OFFS):
            existing = pay_collections.WriteOff.objects.filter(
                tenant_id=tenant.id, note__contains=plan["marker"]
            ).first()
            if existing is not None:
                skipped += 1
                # ⚠ A REPLAY MUST STILL FINISH A HALF-DRIVEN ROW. The first
                # version of this block `continue`d here, so a run that
                # requested a write-off and then failed to approve it left the
                # row `requested` for good and every later run skipped it —
                # an idempotency check that also skips the step that never
                # happened. The marker says the REQUEST is done; the status
                # says whether the APPROVAL is.
                if plan["approve"] and existing.status == "requested":
                    posted_at = datetime.combine(
                        min(today, period_end), time(hour=14)
                    ).replace(tzinfo=_utc())
                    try:
                        writeoffs.approve_write_off(
                            actor,
                            write_off_id=existing.id,
                            approved_on=min(today, period_end),
                            posted_at=posted_at,
                        )
                        approved += 1
                    except Exception as exc:
                        print(f"   ! approve {plan['marker']}: {type(exc).__name__}: {exc}")
                continue
            if index >= len(still_owing):
                print(f"   ! no account left to write off for {plan['marker']}")
                continue
            # smallest balances first, so a write-off gives up a small sum
            position = still_owing[index]
            amount = _money(position.balance)
            if amount <= 0:
                continue
            try:
                result = writeoffs.request_write_off(
                    actor,
                    account_id=position.account_id,
                    amount=amount,
                    reason=plan["reason"],
                    note=f"{plan['note']} [{plan['marker']}]",
                    requested_on=min(today, period_end),
                    currency="USD",
                )
                requested += 1
            except Exception as exc:
                print(f"   ! request {plan['marker']}: {type(exc).__name__}: {exc}")
                continue
            if plan["approve"]:
                posted_at = datetime.combine(
                    min(today, period_end), time(hour=14)
                ).replace(tzinfo=_utc())
                try:
                    writeoffs.approve_write_off(
                        actor,
                        write_off_id=result.write_off_id,
                        approved_on=min(today, period_end),
                        posted_at=posted_at,
                    )
                    approved += 1
                except Exception as exc:
                    print(f"   ! approve {plan['marker']}: {type(exc).__name__}: {exc}")
        print(
            f"write-offs: {requested} requested, {approved} of them approved, "
            f"{skipped} already there"
        )

    after = _report(str(tenant.id))
    _print_report("AFTER", after)

    footed = (
        after["trial_balance_difference"] == 0 and after["unbalanced_entries"] == 0
    )
    if not footed:
        print(
            "\n*** THE TRIAL BALANCE DOES NOT FOOT AFTER THIS RUN. ***\n"
            "The seed is wrong, not the books. Do not photograph these screens.",
            file=sys.stderr,
        )
        return 1
    print("\nthe trial balance foots.")
    return 0


def _utc():
    from datetime import timezone

    return timezone.utc


if __name__ == "__main__":
    raise SystemExit(main())
