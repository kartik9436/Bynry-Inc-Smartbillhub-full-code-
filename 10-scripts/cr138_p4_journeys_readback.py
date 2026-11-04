#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:   `CR-138-BRC07` `P4.22` (`J-PAY-chase-the-morning`) and `P4.23`
#           (`J-PAY-credit-or-cheque`) — the two phase-4 e2e journeys.
# Rules:    CLAUDE.md hard rule 1 (tenant scoping — every read runs inside
#           `tenant_context`) · hard rule 2 (money 4dp, display 2, never
#           float) · BR-TEN-043 (the business day is an ARGUMENT, never a
#           clock) · BR-PAY-029 (AR high → low) · BR-PAY-032 (the oldest
#           unpaid bill is the ageing anchor) · BR-PAY-014 (a refund is
#           offset-first and Admin-approved) · `NFR-3`
# ───────────────────────────────────────────────────────
"""WALK BOTH PHASE-4 JOURNEYS AND PRINT WHAT EACH STEP LEAVES.

    10-scripts/proof-db.sh clone p4walk          (or reuse a seeded clone)
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \\
      DATABASE_URL=postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_p4walk \\
      python3 ../10-scripts/cr138_p4_journeys_readback.py

⚠ **THIS IS A READBACK, NOT A TEST.** It asserts nothing about what OUGHT to
happen; it performs each walk and prints what it found, **including where the
walk runs out of built product**. `J19` is in the catalogue as the warning: it
was written from a plan and on 2026-08-15 it went red at step 1 — *not on a
wrong figure, on the absence of anything to click* (`DEF-112`). Every figure in
`JPAYCHASEMORNING-…md` and `JPAYCREDITORCHEQUE-…md` came out of this file.

⚠ **IT RUNS ON PostgreSQL, AND THAT IS NOT A PREFERENCE.**
`config/settings/test.py` hardcodes in-memory SQLite and ignores
`DATABASE_URL`, and SQLite has no RLS, no aborted-transaction state and a
different query planner — CLAUDE.md hard-won law 14. A collections walk taken
there proves the arithmetic and nothing about the read.

⚠ **EVERY READ RUNS INSIDE `tenant_context`, AND THE HEADER PRINTS THE DEBTOR
COUNT.** With `app.tenant_id` unset, RLS FORCE matches zero rows, every query
is instant and a walk over an empty tenant looks like a clean run. A run whose
debtor count is 0 measured nothing and says so.

⚠ **WHAT IT DOES NOT DO: it writes nothing.** Both walks are READS plus, for
the part payment, a DRY DESCRIPTION of the write rather than the write itself —
because a clone is shared and a journey readback that leaves rows behind makes
the next run's figures different from this one's. Where a step writes, the
script says what it would write and what the read shows before it.
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "06-backend"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
os.environ.setdefault("JOBS_EAGER", "false")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402

from apps.payments import (  # noqa: E402
    billing_seam,
    collections_read,
    credit,
    debtor_read,
    outstandings as outstandings_read,
)
from apps.tenancy import models as tenancy_models  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402

#: The business day both walks are taken on. `BR-TEN-043`: NAMED, never read
#: off a clock, so re-running this on any date prints the same figures.
AS_OF = date(2026, 9, 23)

#: The band 7·1's *OVER 60 DAYS* tile and its filter chip mean. `bucket_for`
#: puts an account in `61-90` or `90+`; the tile is those two added.
OVER_SIXTY = ("61-90", "90+")


def _line(title: str) -> None:
    print(f"\n── {title} " + "─" * max(0, 72 - len(title)))


def _shape() -> dict[str, int]:
    with connection.cursor() as cursor:
        cursor.execute(
            "select (select count(*) from accounts), "
            "(select count(distinct account_id) from invoices "
            "  where status in ('issued','paid'))"
        )
        accounts, debtors = cursor.fetchone()
    return {"accounts": accounts, "debtors": debtors}


# ══════════════════════════════════════════════════════════════════════════
# J-PAY-chase-the-morning — filter to over sixty · open one · see what was
# tried · take a part payment
# ══════════════════════════════════════════════════════════════════════════
def chase_the_morning() -> int:
    print("\n" + "=" * 78)
    print("J-PAY-chase-the-morning  ·  P4.22")
    print("=" * 78)

    _line("step 1 · the clerk filters the debtor list to OVER SIXTY DAYS")
    # ⚠ TWO CALLS, NOT ONE, AND THE DIFFERENCE IS THE STEP. 7·1's tile is the
    # two tail bands added; the filter chip asks the server for one band at a
    # time, which is what `GET /outstandings?f.bucket=` takes.
    whole = outstandings_read.outstandings(as_of=AS_OF, page=1, per=50)
    print(f"  unfiltered page 1: {len(whole.rows)} rows · {whole.total_accounts:,} debtors in all")
    over_sixty: list = []
    for band in OVER_SIXTY:
        view = outstandings_read.outstandings(as_of=AS_OF, bucket=band, page=1, per=50)
        print(f"  f.bucket={band:<6} → {view.total_accounts:,} accounts, page 1 holds {len(view.rows)}")
        over_sixty.extend(view.rows)
    if not over_sixty:
        print(
            "  ⚠ NOBODY IS OVER SIXTY DAYS ON THIS CLONE. The walk stops here rather than "
            "printing a journey about an empty list."
        )
        return 2
    # BR-PAY-029 — worst first. The read sorts in SQL; this only shows it.
    over_sixty.sort(key=lambda row: Decimal(row.balance), reverse=True)
    worst = over_sixty[0]
    print(f"  worst of them: {worst.account_no} · {worst.balance} · {worst.days_late} days late")

    _line("step 2 · she opens that debtor (7·2)")
    body = debtor_read.debtor(account_id=worst.account_id, as_of=AS_OF)
    position = body.get("position") or {}
    print(f"  account_no on screen : {body.get('account_no')}   (B14 rule 31 — never the id)")
    print(f"  balance              : {position.get('balance')}")
    print(f"  oldest unpaid bill   : {position.get('oldest_due_on')}   (BR-PAY-032's anchor)")
    print(f"  open bills           : {len(body.get('bills') or [])}")

    _line("step 3 · she sees WHAT WAS TRIED — the notice trail")
    history = body.get("history") or []
    print(f"  trail rows on this page: {len(history)}  ·  COUNT(*) over the whole trail: "
          f"{body.get('history_count')}")
    for row in history[:5]:
        print(
            f"    {row.get('occurred_on')}  {row.get('notice_type'):<12} "
            f"{row.get('outcome'):<8} {row.get('skip_reason') or ''}"
        )
    if not history:
        print("    (nothing recorded — this account has never been chased)")
    ladder = body.get("collections") or {}
    print(f"  rung already sent    : {ladder.get('current_tier')}  sent {ladder.get('tier_sent_on')}")
    print(f"  would a step run today: {ladder.get('runs')}  "
          f"{'(' + str(ladder.get('skip_reason')) + ')' if ladder.get('skip_reason') else ''}")

    _line("step 4 · she takes a PART payment — described, not written")
    balance = Decimal(str(position.get("balance") or "0"))
    # A quarter of what is owed, on the 2dp grid the LEDGER insists on
    # (`BR-LED-025`, PO 2026-08-12 verbatim *"Refuse and make the caller
    # round"*): a posting carrying more than two decimals is refused, and it
    # refuses the whole payment with it.
    part = (balance / 4).quantize(Decimal("0.01"))
    print(f"  owed {balance}  →  a part payment of {part}  (2dp; BR-LED-025 refuses more)")
    print(f"  after it the balance would read {balance - part}")
    print(
        "  ⚠ NOT WRITTEN BY THIS SCRIPT. `services.record_payment` posts a journal pair and "
        "an audit row; a readback that left them behind would change the next run's figures. "
        "The journey file records the write as the step it is."
    )
    return 0


# ══════════════════════════════════════════════════════════════════════════
# J-PAY-credit-or-cheque — an account closes in credit and the clerk is
# offered BOTH ways out
# ══════════════════════════════════════════════════════════════════════════
def credit_or_cheque() -> int:
    print("\n" + "=" * 78)
    print("J-PAY-credit-or-cheque  ·  P4.23")
    print("=" * 78)

    _line("step 1 · find an account holding credit")
    # `_credit_positions(None)` is the tenant-wide read `outstanding_positions`
    # already makes — asking it rather than scanning is the same statement of
    # the rule the debtor list uses (`BR-PAY-1125`).
    positions = billing_seam._credit_positions(None)  # noqa: SLF001 — the read, not a copy
    holders = {a: amount for a, amount in positions.items() if amount > 0}
    negatives = {a: amount for a, amount in positions.items() if amount < 0}
    print(f"  accounts in POSITIVE credit : {len(holders)}")
    print(f"  accounts in NEGATIVE credit : {len(negatives)}   "
          "(BR-PAY-041 — a real debt, never floored, never added to a bill chase)")
    if not holders:
        print(
            "  ⚠ NOBODY ON THIS CLONE HOLDS CREDIT. The walk stops rather than printing a "
            "journey about an account that does not exist."
        )
        return 2
    # ⚠ **PREFER A HOLDER THAT ALSO HAS AN OPEN BILL, AND SAY WHEN THERE IS
    # NONE.** The credit door is refused on an account with no open bill — a
    # goodwill credit is raised AGAINST a bill — so a walk that picked the
    # largest holder blind would report *"one door, one refusal"* and read as a
    # broken screen rather than as a correct one. Both cases are walked below.
    with_a_bill: list = []
    for candidate in holders:
        if billing_seam.credit_path_for_account(candidate).get("available"):
            with_a_bill.append(candidate)
    account_id = with_a_bill[0] if with_a_bill else max(holders, key=lambda a: holders[a])
    held = holders[account_id]
    print(f"  holders that ALSO have an open bill (both doors open): {len(with_a_bill)}")
    print(f"  walking: {account_id} holding {held}")

    _line("step 2 · WAY OUT ONE — a cheque back (the refund path)")
    refundable = credit.refundable_position(account_id)
    print(f"  refundable balance  : {refundable.balance}")
    for problem in refundable.problems:
        print(f"  ⚠ {problem.get('code')}: {str(problem.get('detail'))[:110]}")
    contributing = credit.contributing_payments(account_id)
    print(f"  payments behind it  : {len(contributing)}  (CR-059 CS-7 — the evidence half)")
    for row in contributing[:4]:
        print(f"    {row.get('posted_at') or row.get('posted_on')}  {row.get('amount')}  "
              f"{row.get('method_name') or row.get('method_code') or ''}")
    print("  ⚠ BR-PAY-014 — offset FIRST and an Admin approves. The read above offers the "
          "figure; `refunds.py` owns the chain and this script raises nothing.")

    _line("step 3 · WAY OUT TWO — leave it ON the account (the credit path)")
    door = billing_seam.credit_path_for_account(account_id)
    print(f"  credit path available : {door.get('available')}")
    print(f"  bills it could be raised against : {len(door.get('bills') or [])}")
    for bill in (door.get("bills") or [])[:4]:
        print(f"    {bill.get('number')}  total {bill.get('total')}  open {bill.get('balance')}")
    for problem in door.get("problems") or []:
        print(f"  ⚠ {problem.get('code')}: {str(problem.get('detail'))[:120]}")

    _line("step 4 · BOTH are offered, which is the whole point of P4.12")
    print(
        "  A clerk standing on payments sees the refund AND the credit. Before `P4.12` the "
        "credit was invisible from here — one capability with one path, reachable from two "
        "places (PO 2026-09-22: *\"we can not have two path for 1 capabilities wew will "
        "confuse user\"*)."
    )
    print(
        f"  refund: OFFERED, {refundable.balance} refundable   ·   "
        f"credit: {'OFFERED against ' + str(len(door.get('bills') or [])) + ' bill(s)' if door.get('available') else 'REFUSED WITH ITS REASON'}"
    )
    if not door.get("available"):
        print(
            "  ⚠ **ONE DOOR OPEN AND ONE REFUSED IS THE CORRECT ANSWER HERE, NOT A GAP.** "
            "`available: false` means THIS ACCOUNT has nothing to credit today, and "
            "`BR-SHL-025` requires the reason on the control rather than a greyed-out "
            "button — *\"why can I not give them a credit?\"* is the question a shrug "
            "leaves a clerk holding."
        )
    return 0


def main() -> int:
    tenant = tenancy_models.Tenant.objects.get(subdomain="brazosbend")
    with tenant_context(str(tenant.id)):
        shape = _shape()
        print(f"tenant brazosbend: {shape['accounts']:,} accounts · {shape['debtors']:,} debtors")
        print(f"business day (BR-TEN-043, an ARGUMENT): {AS_OF.isoformat()}")
        if not shape["debtors"]:
            print(
                "REFUSED: this tenant has no debtors, so both walks below would be walks "
                "over an empty list. Check `app.tenant_id` is set — RLS FORCE makes an "
                "unscoped session look exactly like an empty tenant (hard rule 1)."
            )
            return 2
        first = chase_the_morning()
        second = credit_or_cheque()
    return max(first, second)


if __name__ == "__main__":
    raise SystemExit(main())

# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-138-BRC07 `P4.22` · `P4.23` · blueprint p023 (both task rows)
# generated: 2026-09-23 by LANE P4-TESTS
# checklist: A=n/a B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
# gates: run on real PostgreSQL 16 against the two seeded clones left by
#        `P4.1`/`P4.2` — `sbh_clone_p4perf` (2,046 debtors) and
#        `sbh_clone_p4perf40` (40,046). Every figure in the two journey files
#        is one this script printed.
# exceptions: (1) IT WRITES NOTHING. The part payment and the refund are
#        DESCRIBED. A readback that left rows on a shared clone would make the
#        next run's figures differ from the ones in the journey files, which is
#        the one thing a measured journey may not do.
#        (2) IT REACHES `billing_seam._credit_positions`, a private name, on
#        purpose: it is the read `outstanding_positions` itself uses, and
#        scanning for credit some other way would be a second implementation
#        of the rule `BR-PAY-1125` states once.
# status: VERIFIED-UNRATIFIED
