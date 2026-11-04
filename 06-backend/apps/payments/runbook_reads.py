# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-027 · US-RBS-029 · US-RBS-035 · US-RBS-036 (EP-RBS-05) —
#           CR-075 wave R′, the payments half: the four reads runbooks 15, 17,
#           25 and 26 make, added by the module that OWNS the tables.
# Rules:    BR-RBS-039 (a runbook READS through a seam this module owns; the
#           OWNING module publishes the selector and the seam never reaches
#           past it) · 13-selector-inventory.md S-11 and S-12 · BR-PAY-016
#           (plan notices: reminder 3 days before, missed-notice day+1, 2nd
#           miss VOIDS the plan) · BR-PAY-013 (N NSFs → cash-only/no-autopay) ·
#           BR-PAY-015 (autopay v1 is capture-INTENT: nothing drafts money) ·
#           BR-PAY-021 (on time is `posted_at ≤ due date`) · BR-CUS-050 (the
#           deposit interest rate lives in Settings) · BR-TEN-043 (a business
#           date is an argument, never a clock read — gate G6) · CLAUDE.md hard
#           rule 1 (tenant scoping) · hard rule 2 (money 4 decimals, never a
#           float, always with its currency)
# Tests:    06-backend/tests/test_us_rbs_027_deposit_review.py ·
#           06-backend/tests/test_us_rbs_029_autopay_prenotice.py ·
#           06-backend/tests/test_us_rbs_035_payment_plans.py ·
#           06-backend/tests/test_us_rbs_036_returned_payments.py
# Impacts:  apps/runbooks/seams/payments_seam.py (the five wrappers) ·
#           04-docs/05-modules/17-runbooks/13-selector-inventory.md S-11 · S-12
# ───────────────────────────────────────────────────────
"""READ ONLY — the five questions wave R′'s payments runbooks ask of this module.

⚠ **THIS FILE IS `payments`', NOT `runbooks`', AND THAT IS THE WHOLE POINT.**
`BR-RBS-039` and `13-selector-inventory.md` say the same thing twice: a runbook
reads through a seam, and **the owning module adds the selector**. A version of
these five living inside `apps/runbooks/` would be payments' law — what *in
flight* means, what *on time* means, what *held past the period* means —
re-derived in a file payments' reviewers never open, and `G115` refuses it
besides.

⚠ **A THIRD KIND OF MODULE, DELIBERATELY, EXACTLY AS `collections_read.py` AND
`bankrec_read.py` ARE.** It is not `selectors.py` because `selectors.py` is 1,787
lines that four lanes edit in a week, and a whole-file collision on it costs more
than a new name (CLAUDE.md hard-won law 11). `runbooks/seams/payments_seam.py`
imports this module BY NAME, the way it already imports `collections_read`.

WHAT EACH ANSWER CANNOT SAY, STATED IN THE ANSWER ITSELF
---------------------------------------------------------
Every function below returns its findings **and a statement of what it could not
look at**, because a count of zero and a count nobody could take read identically
on a screen and mean opposite things (hard-won law 7: *a declared blind spot with
no NUMBER attached is indistinguishable from an empty one*). Three of them are
structural on this product and are named here once:

1. **NOTHING DRAFTS AN AUTOPAY DEBIT, SO NO DEBIT EVER FAILS.** `BR-PAY-015`:
   autopay v1 is a capture INTENT — *"enrollment + method stored; bill issue
   records intent dated the due date … staff record the actual money; real
   charging = rails (W7)"*. `AutopayCaptureIntent.status` has exactly ONE value
   (`awaiting_rails`) and nothing consumes an intent. So *"11 failed debits
   yesterday"* — runbook 17's own second half — has **no row it could ever come
   from**, and `autopay_debits_due` reports that as an absence rather than as 0.
2. **NO COLUMN ANYWHERE HOLDS A BANK RETURN CODE OR ITS REASON.** `BankLine`
   carries `posted_on`, `reference` and `amount` and nothing else; there is no
   returns feed, no return-code column and no link from a returned item back to
   the payment it reverses. Runbook 26's promise — *each failed debit reading the
   bank's reason in words* — has nowhere to read from, which is why
   `returned_items_landed` answers with a reasoned absence and never with an
   empty list that would read as *"a clean morning"*.
3. **DEPOSIT INTEREST IS `customers`' ARITHMETIC AND IS NOT RE-DERIVED HERE.**
   ❄️ **`GT-61` IS FROZEN AND FINANCE-SIGNED** — *$150 @ 2.0%, 89 months →
   **$22.25*** — and `apps/customers/deposit_interest.py` implements it, is
   published as `apps.customers.selectors.deposit_interest_accrued`, and is
   asserted against that figure. **This file computes no interest**, because a
   second implementation of a frozen money rule is exactly the thing hard rule 2
   and B4's freeze exist to prevent. Runbook 15 reads it through
   `customers_seam`. ⚠ The first draft of this module was about to report the
   figure as *not worked out* on the grounds that nothing implemented it — which
   would have been the mistake `CR-075`'s own dependency table already records
   once: *"the capability was reported absent because this lane looked for it in
   the shape it expected"*.
4. **A REVERSAL IS A PERSON'S ACT AND HAS NO PORT.** `reverse_payment` is
   `@require_role` Admin-only (`BR-PAY-1070`) and is bound to NO port on
   purpose — `runbook_ports.py` says so in its own closing line, and the
   fourteenth port added on 2026-09-07 (`step_ladder`) is not it either. So even with a feed, a runbook could not reverse; it can only plan.

WHAT WOULD MAKE THESE READS WRONG QUIETLY (hard-won law 7, habit 2)
--------------------------------------------------------------------
* **Reading a clock.** Every one of these takes `as_of` as an argument. A
  deposit review re-taken for the 1st must give the 1st's answer, and `G6` greps
  for the clock read none of them makes.
* **Counting outside the tenant context.** Every queryset filters `tenant_id`
  explicitly as well as relying on RLS `FORCE`, because the unit tier is SQLite
  where the policy does not exist (`invoice_queryset` takes the same posture and
  says so).
* **Money as a float.** Every amount travels as a `Decimal` or as its stored
  four-place STRING, never as a float — hard rule 2, and these values pass
  through `jsonb` on their way to a runbook's report where no column type would
  catch one.
* **Treating a plan `closed` as *in flight*.** `LIVE_PLAN_STATUSES` is the
  module's own tuple and is read rather than restated; a second list here would
  eventually disagree with the unique index that enforces it.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from importlib import import_module
from typing import Any

from django.db.models import Count, Max, Sum

from apps.payments import models
from apps.payments.collections_models import (
    LIVE_PLAN_STATUSES,
    PaymentPlan,
    PaymentPlanInstallment,
)
from core import tenancy as core_tenancy

ZERO = Decimal("0")

#: `Invoice.status` when a bill has been issued. Read from billing's own module
#: rather than typed, so a fifth status cannot silently drop out of the window.
BILLING_MODULE = "billing"
INVOICE_QUERYSET_READ = "invoice_queryset"

#: The behaviour class that means CLOSED (`BR-CUS-055`). A status LABEL is the
#: tenant's to rename; the class is the product's, which is why every predicate
#: in this product keys off the class and never off the word.
ACCOUNT_CLASS_TERMINAL = "terminal"


def _tenant_id() -> Any:
    """The tenant this read is for, or a refusal — never a silent whole-estate read.

    `open_bills._tenant_id`'s posture, for its reason: on PostgreSQL RLS `FORCE`
    would return nothing at all, and on the SQLite unit tier it would return
    EVERY tenant's rows. The two failure modes are opposite and both are worse
    than a refusal.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise RuntimeError(
            "a runbook read was taken with no tenant set. CLAUDE.md hard rule 1: never touch a "
            "tenant table without `app.tenant_id`. On PostgreSQL this would read nothing and on "
            "the SQLite test tier it would read everything, so it refuses instead."
        )
    return tenant_id


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """The owning module's callable, or `None` while it has not published one.

    The shape `apps.payments.billing_seam._resolve` already uses. `None` means
    *this module cannot answer*, never *there is nothing* — `DEF-075` is what it
    costs to read those two as the same sentence, and every caller below states
    which one it got.
    """
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _money(value: Any) -> Decimal:
    """A stored amount as a `Decimal`. **Never `float(...)`** (hard rule 2)."""
    if value is None or value == "":
        return ZERO
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        raise TypeError(
            "money arrived as a float. Hard rule 2: stored to 4 decimals, displayed to 2, and "
            "never a binary fraction — `0.1 + 0.2` is not `0.3` and no column type catches one "
            "that has been through jsonb."
        )
    return Decimal(str(value))


def _stored(value: Decimal) -> str:
    """The four-place string a runbook carries. Display rounds; storage does not."""
    return f"{value.quantize(Decimal('0.0001')):f}"


def _account_no(account: Any) -> str | None:
    """The account's human-facing number — never the id (B14 rule 31)."""
    number = getattr(account, "account_no", None)
    return str(number) if number else None


def _is_closed(account: Any) -> bool:
    """Has this account been closed? Read off the status's CLASS, never its label."""
    status = getattr(account, "status", None)
    return str(getattr(status, "behavior_class", "") or "") == ACCOUNT_CLASS_TERMINAL


def _accounts_by_id(account_ids) -> dict[str, Any]:
    """Account rows through `customers`' OWN published queryset (B1 / `BR-TEN-013`).

    `apps.customers.selectors.account_queryset`. Never `Account.objects` — the
    owning module's queryset is what applies its own tenant scope and its own
    `select_related`, and a second one here would drift from it.
    """
    read = _resolve("customers", "account_queryset")
    if read is None:  # pragma: no cover - customers always publishes it
        return {}
    wanted = [one for one in account_ids if one]
    if not wanted:
        return {}
    return {str(row.id): row for row in read().filter(id__in=wanted)}


# ══════════════════════════════════════════════════════════════════════════
# S-11 · DEPOSITS HELD PAST THE PERIOD — runbook 15 steps 1, 2, 3 and 5
# ══════════════════════════════════════════════════════════════════════════


def deposits_held(*, as_of: dt.date, months: int = 12) -> dict[str, Any]:
    """Every deposit this utility has held longer than the policy period.

    `13-selector-inventory.md` **S-11**, and it answers three of runbook 15's
    steps in one read for the same reason the ladder board answers runbook 8's:
    the count on the setup screen (*"Matches 70 deposits · $17,890.00 held"*) and
    the set the run walks must be ONE function, or they can disagree.

    ⚠ **A DEPOSIT LIVES ON `accounts`, WHICH IS WHY THIS READS AN ACCOUNT AND
    RETURNS A DEPOSIT.** `accounts.deposit_on_file` and
    `accounts.deposit_received_on` (B2 r9 #5, `BR-CUS-050`) are the only place
    this product records one — there is no `deposits` table — so the subject a
    runbook walks is the DEPOSIT and the row it is read from is the account's.
    `BR-CUS-057`'s accrual column (`deposit_interest_accrued`) is **not written by
    anything on this deployment**, which is `customers`' own recorded absence
    (`deposit_interest_not_accrued`); this read reports the figure it finds and
    never treats an unwritten accrual as zero interest already paid.

    `held_days` is measured from `deposit_received_on`, which is the only date
    the product holds for it. An account holding money with **no** receipt date
    is returned with `received_on=None` and `eligible=False`: it cannot be aged,
    and guessing a date would be inventing the fact the whole runbook turns on.
    """
    tenant_id = _tenant_id()
    read = _resolve("customers", "account_queryset")
    if read is None:  # pragma: no cover - customers always publishes it
        return {
            "rows": [],
            "readable": False,
            "why_not": (
                "this deployment cannot read accounts, so no deposit can be found or aged."
            ),
        }
    cutoff = _months_before(as_of, months)
    rows: list[dict[str, Any]] = []
    undated = 0
    for account in read().filter(deposit_on_file__gt=0).order_by("account_no", "id"):
        held = _money(account.deposit_on_file)
        received = account.deposit_received_on
        if received is None:
            undated += 1
        eligible = received is not None and received <= cutoff
        rows.append(
            {
                "account_id": str(account.id),
                "account_no": _account_no(account),
                "label": _account_no(account) or "",
                "held": _stored(held),
                "currency": getattr(account, "currency", None) or _tenant_currency(),
                "received_on": received.isoformat() if received else None,
                "held_days": (as_of - received).days if received else None,
                "eligible": eligible,
                "closed": _is_closed(account),
                "interest_accrued_so_far": _stored(
                    _money(getattr(account, "deposit_interest_accrued", None))
                ),
            }
        )
    return {
        "rows": rows,
        "readable": True,
        "tenant_id": str(tenant_id),
        "cutoff": cutoff.isoformat(),
        "months": int(months),
        # Both numbers, never one: *5 held* beside *2 past the period* is a
        # different sentence from *2 found*, and only the pair can be checked.
        "held_count": len(rows),
        "eligible_count": len([one for one in rows if one["eligible"]]),
        "undated_count": undated,
        "held_value": _stored(sum((_money(one["held"]) for one in rows), ZERO)),
    }


def _tenant_currency() -> str:
    """The tenant's ONE currency code (`BR-TEN-042`), as `CHAR(3)`."""
    from apps.payments import settings_seam

    try:
        return str(settings_seam.tenant_currency())
    except Exception:  # noqa: BLE001 — a refusal here is not this read's to raise
        return "USD"


def _months_before(as_of: dt.date, months: int) -> dt.date:
    """`as_of` less N whole months, without a calendar library.

    Clamped to the last day of the target month so *twelve months before 31
    March* is 31 March a year earlier and *before 29 February* in a leap year is
    28 February — never a `ValueError` on a day the month does not have.
    """
    total = (as_of.year * 12 + as_of.month - 1) - int(months)
    year, month = divmod(total, 12)
    month += 1
    day = min(as_of.day, _days_in_month(year, month))
    return dt.date(year, month, day)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (dt.date(year, month + 1, 1) - dt.timedelta(days=1)).day


def payment_history_verdict(account_ids, *, as_of: dt.date, months: int = 12) -> dict[str, Any]:
    """Twelve months of ON-TIME payment, per account — `BR-PAY-021`'s reading.

    Runbook 15 step 2 (*"Every bill paid by its due date"*) and step 3
    (*"nothing past due today — the morning of, not the month of"*), in ONE read
    over the whole pinned set rather than two per account.

    **On time is `posted_at ≤ due date`** — `BR-PAY-021`, and the rule's own
    example is the one that matters: *a cheque posted on the due date and cleared
    three days later is ON TIME*. So this compares the ALLOCATION's payment
    `posted_at` against the invoice's `due_date` and never a clearing date.

    ⚠ **AN INVOICE WITH NO DUE DATE IS NOT EVIDENCE OF ANYTHING** and is counted
    separately rather than treated as met: `invoices.due_date` is nullable
    (`BR-BIL-024`, derived), and reading NULL as *paid on time* would hand a
    deposit back on the strength of bills nobody could age.

    ⚠ **A REVERSED PAYMENT IS NOT A PAYMENT.** A bounce writes a NEGATIVE
    reversing row (`BR-PAY-002`), so the allocation total for an invoice a
    customer's cheque bounced on nets back down and the bill reads unmet — which
    is the answer a deposit review needs and the reason the sum is taken over
    allocations rather than over payment rows.

    ⚠ **`on_time` IS THREE-VALUED, AND THE THIRD VALUE IS WHY THIS FUNCTION WAS
    REWRITTEN BEFORE IT SHIPPED.** The first draft started every account at
    `True` and set it `False` on evidence — so an account with **no bills at
    all** came back *twelve months of on-time payment*, which is the exact shape
    hard-won law 7's second habit asks about: *what would make this check pass
    wrongly?* It is not academic on this deployment. Two of the five accounts
    holding a deposit on the seeded tenant (`A-10432`, `A-10650`) have **zero**
    issued bills, so a review would have released both on the strength of a
    history nobody has. `None` now means **unproven** — no bill was looked at —
    and money going out is held on unproven, never released.
    """
    tenant_id = _tenant_id()
    wanted = [one for one in account_ids if one]
    empty: dict[str, Any] = {
        "verdicts": {},
        "readable": True,
        "from": _months_before(as_of, months).isoformat(),
        "to": as_of.isoformat(),
    }
    if not wanted:
        return empty
    invoices_read = _resolve(BILLING_MODULE, INVOICE_QUERYSET_READ)
    if invoices_read is None:
        return {
            **empty,
            "readable": False,
            "why_not": (
                "this deployment cannot read bills, so no payment history can be checked. "
                "Nothing is treated as on time on the strength of an unreadable book."
            ),
        }
    from apps.billing import models as billing_models

    since = _months_before(as_of, months)
    invoices = list(
        invoices_read()
        .filter(
            account_id__in=wanted,
            status__in=(billing_models.INVOICE_ISSUED,),
        )
        .values("id", "account_id", "due_date", "total")
    )
    settled = {
        row["invoice_id"]: (_money(row["paid"]), row["latest"])
        for row in models.Allocation.objects.filter(
            tenant_id=tenant_id, invoice_id__in=[one["id"] for one in invoices]
        )
        .values("invoice_id")
        .annotate(paid=Sum("amount"), latest=Max("payment__posted_at"))
    }
    verdicts: dict[str, dict[str, Any]] = {
        str(one): {
            # ⚠ `None` = UNPROVEN, and it is the value an account with no bills
            # keeps. See the docstring: starting at True releases a deposit on
            # evidence nobody has.
            "on_time": None,
            "bills_looked_at": 0,
            "bills_late": 0,
            "bills_open_now": 0,
            "bills_with_no_due_date": 0,
            "past_due_today": False,
        }
        for one in wanted
    }
    for invoice in invoices:
        verdict = verdicts.get(str(invoice["account_id"]))
        if verdict is None:  # pragma: no cover - the filter already bounds it
            continue
        due = invoice["due_date"]
        if due is None:
            verdict["bills_with_no_due_date"] += 1
            verdict["on_time"] = False
            continue
        if due < since:
            continue
        verdict["bills_looked_at"] += 1
        if verdict["on_time"] is None:
            # The first bill in the window is what turns *unproven* into a
            # verdict. Every later bill can only take it away.
            verdict["on_time"] = True
        paid, latest = settled.get(invoice["id"], (ZERO, None))
        total = _money(invoice["total"])
        if paid < total:
            if due <= as_of:
                verdict["bills_open_now"] += 1
                verdict["past_due_today"] = True
                verdict["on_time"] = False
            continue
        if latest is not None and latest.date() > due:
            verdict["bills_late"] += 1
            verdict["on_time"] = False
    return {**empty, "verdicts": verdicts}


# ══════════════════════════════════════════════════════════════════════════
# S-12 · PRIOR RETURNED PAYMENTS, AND THE FEED THAT DOES NOT EXIST — runbook 26
# ══════════════════════════════════════════════════════════════════════════


def returned_payment_counts(account_ids) -> dict[str, int]:
    """How many payments have come BACK on each account — `13-selector-inventory` **S-12**.

    Counted from the reversing ROWS rather than from `accounts.nsf_count`, and
    the difference is not academic: `BR-PAY-013`'s `nsf_count++` is CUSTOMERS'
    write and **`apps/payments/reversal.py` records that it does not happen** —
    every reversal carries `nsf_count_not_incremented` because there is no
    service on the far side to perform it (`DEF-069`). A privilege limit read off
    a counter nothing increments would never be reached, on any account, ever.

    A reversing row is one whose `reverses_payment_id` is set and whose
    `reversal_reason` is `nsf` — the bank returned the item. The other three
    reasons (`bank_chargeback`, `data_entry_error`, `customer_dispute`) are staff
    corrections under `BR-PAY-011` and are **not** returns, so they are not
    counted towards a privilege a customer loses.
    """
    tenant_id = _tenant_id()
    wanted = [one for one in account_ids if one]
    if not wanted:
        return {}
    counts = {str(one): 0 for one in wanted}
    rows = (
        models.Payment.objects.filter(
            tenant_id=tenant_id,
            account_id__in=wanted,
            reverses_payment__isnull=False,
            reversal_reason=models.REVERSAL_REASON_NSF,
        )
        .values("account_id")
        .annotate(returns=Count("id"))
    )
    for row in rows:
        counts[str(row["account_id"])] = int(row["returns"] or 0)
    return counts


#: CR-175-BRC10 — the bank's reason in WORDS for the codes a utility meets most
#: (`RB-126`: *"the bank's reason in words"*; B14 rule 32 keeps a code off a
#: clerk's table). A code not listed reads as *Returned by the bank (Rxx)* —
#: the code is kept, never guessed into a sentence.
NACHA_RETURN_WORDS: dict[str, str] = {
    "R01": "Insufficient funds",
    "R02": "Account closed",
    "R03": "No account found",
    "R04": "Invalid account number",
    "R05": "Unauthorized debit",
    "R06": "Returned at the bank's request",
    "R07": "Authorization revoked",
    "R08": "Payment stopped",
    "R09": "Uncollected funds",
    "R10": "Customer says not authorized",
    "R16": "Account frozen",
    "R20": "Not a transaction account",
    "R29": "Business says not authorized",
}


def bank_said(return_code: str | None) -> str:
    """The bank's return code, in words."""
    code = (return_code or "").strip().upper()
    return NACHA_RETURN_WORDS.get(code) or (
        f"Returned by the bank ({code})" if code else "Returned by the bank"
    )


def returned_items_landed(*, as_of: dt.date, window_days: int = 1) -> dict[str, Any]:
    """Every payment the bank sent back in the window — **read off the reversing rows.**

    ⚠ **THIS ANSWERED `feed_available: False` WITH AN EMPTY LIST UNTIL 2026-10-07
    (`DEF-PAY-10010`), AND THE ABSENCE IT NAMED HAD STOPPED BEING TRUE THAT
    MORNING.** Its second reason was *"no column holds a bank return code"*;
    `CR-174-BRC10` added `payments.return_code` the same day, and nothing asked
    this read again. So a return US Payments sent us reached the returned-payments
    runbook only as a count of things *"reversed by hand"*, the run stopped at
    step 1, and no fee was drafted and no notice handled for it.

    **WHAT A RETURNED ITEM IS NOW:** a reversing row (`reverses_payment_id` set)
    that carries the bank's `return_code`, dated in the window by the day the
    bank returned it (`posted_at`, which `reversal.py` writes as the return
    date). Two writers put that row there and they are read the same way:

      * US Payments' return notification (`agent_door.post_return`, `CR-174`);
      * a billing clerk or System Admin marking an ACH payment returned
        (`reversal.mark_ach_returned`, `CR-175-BRC10`, PO 2026-10-07: *"The same
        effect follows: balance restored, fee and notice."*).

    The reversal has ALREADY happened — the PO's reading (A) reverses on
    arrival — so every row says so (`reversal_no`), and the runbook's job is the
    fee and the notice. `letter_queued_by_reversal` is true for an `nsf` return,
    because `reversal.py` queues the customer's *payment failed* letter itself
    for that reason and the runbook must not send a second.

    ⚠ **A REVERSAL WITH NO CODE IS NOT A RETURNED ITEM HERE** — an Admin's
    Reverse on S35 carries none — and it is still COUNTED beside the list
    (`already_reversed_by_hand`), because a blind spot with no figure beside it
    cannot be told from an empty one (hard-won law 7).
    """
    tenant_id = _tenant_id()
    since = as_of - dt.timedelta(days=max(int(window_days), 0))
    in_window = models.Payment.objects.filter(
        tenant_id=tenant_id,
        reverses_payment__isnull=False,
        posted_at__date__gte=since,
        posted_at__date__lte=as_of,
    )
    reversed_by_hand = in_window.filter(
        return_code__isnull=True, reversal_reason=models.REVERSAL_REASON_NSF
    ).count()
    returned = (
        in_window.filter(return_code__isnull=False)
        .select_related("reverses_payment", "account")
        .order_by("posted_at", "id")
    )
    rows = []
    for reversing in returned:
        original = reversing.reverses_payment
        rows.append(
            {
                "item_id": str(reversing.pk),
                # B14 rule 31 — the payment's own NUMBER is the label.
                "label": original.payment_no or "",
                "reference": original.confirmation or "",
                "account_id": str(reversing.account_id),
                "account_no": getattr(reversing.account, "account_no", "") or "",
                "payment_id": str(original.pk),
                "amount": str(-reversing.amount),
                "currency": reversing.currency,
                "return_code": reversing.return_code,
                "bank_said": bank_said(reversing.return_code),
                "reversal_reason": reversing.reversal_reason,
                "reversal_no": reversing.payment_no or "",
                "returned_on": reversing.posted_at.date().isoformat(),
                "origin": reversing.origin,
                "already_reversed": True,
                "letter_queued_by_reversal": (
                    reversing.reversal_reason == models.REVERSAL_REASON_NSF
                ),
            }
        )
    return {
        "rows": rows,
        "feed_available": True,
        "why_not": "",
        "from": since.isoformat(),
        "to": as_of.isoformat(),
        # ⚠ THE NUMBER BESIDE THE LIST. A reversal nobody gave a bank code is not
        # picked up, and saying how many there were is what keeps that visible.
        "already_reversed_by_hand": int(reversed_by_hand),
        "missing": (),
    }


# ══════════════════════════════════════════════════════════════════════════
# AUTOPAY DEBITS DUE — runbook 17 steps 2, 3 and 4
# ══════════════════════════════════════════════════════════════════════════


def autopay_debits_due(*, as_of: dt.date, within_days: int = 10) -> dict[str, Any]:
    """Every debit this product has PROMISED inside the notice window.

    ⚠ **THE PROMISE IS THE `AutopayCaptureIntent` ROW AND NOTHING ELSE**
    (`BR-PAY-015`). *"Bill issue records intent dated the due date"*, `amount` and
    `scheduled_on` are STORED rather than recomputed *"because what the customer
    was told would be drafted, and when, must survive a later change to the
    bill"* — which is precisely what a pre-notification is. An open bill on an
    autopay account with **no** intent is not a debit due: nothing will draft it,
    and telling a customer otherwise is a promise this product cannot keep.

    ⚠ **BOTH NUMBERS TRAVEL.** `autopay_accounts` is how many accounts are on
    autopay at all and `rows` is how many have a debit scheduled in the window.
    *6 on autopay · 0 scheduled* is a different sentence from *0 on autopay*, and
    a screen that could only say the second would report a working morning over a
    feature nobody has switched on.

    `previous_amount` is the amount this account's PREVIOUS intent promised — the
    only thing this product holds that can answer runbook 17's *"only when the
    amount changed"*. A first-ever debit has none, and an account whose amount is
    unchanged needs no notice under the bank rule the card cites.
    """
    tenant_id = _tenant_id()
    until = as_of + dt.timedelta(days=max(int(within_days), 0))
    accounts_read = _resolve("customers", "account_queryset")
    autopay_accounts = (
        accounts_read().filter(autopay=True).count() if accounts_read is not None else None
    )
    intents = list(
        models.AutopayCaptureIntent.objects.filter(tenant_id=tenant_id).order_by(
            "account_id", "scheduled_on", "created_at"
        )
    )
    previous: dict[str, Decimal] = {}
    rows: list[dict[str, Any]] = []
    accounts = _accounts_by_id({str(one.account_id) for one in intents})
    for intent in intents:
        key = str(intent.account_id)
        amount = _money(intent.amount)
        was = previous.get(key)
        previous[key] = amount
        if not (as_of <= intent.scheduled_on <= until):
            continue
        account = accounts.get(key)
        rows.append(
            {
                "intent_id": str(intent.pk),
                "account_id": key,
                "account_no": _account_no(account) if account is not None else None,
                "label": (_account_no(account) if account is not None else None) or "",
                "invoice_id": str(intent.invoice_id),
                "amount": _stored(amount),
                "currency": intent.currency,
                "scheduled_on": intent.scheduled_on.isoformat(),
                "previous_amount": None if was is None else _stored(was),
                "amount_changed": was is None or was != amount,
                "autopay_on": bool(getattr(account, "autopay", False)) if account else False,
                "cash_only": bool(getattr(account, "cash_only_no_autopay", False))
                if account
                else False,
            }
        )
    return {
        "rows": rows,
        "from": as_of.isoformat(),
        "to": until.isoformat(),
        "autopay_accounts": autopay_accounts,
        "intents_in_total": len(intents),
        "scheduled_in_window": len(rows),
    }


def failed_debits(*, as_of: dt.date) -> dict[str, Any]:
    """Yesterday's failed debits — **and no debit is ever attempted here.**

    ⚠ **NOT REPORTED, NEVER ZERO.** `AutopayCaptureIntent.status` has exactly ONE
    value — `awaiting_rails` — and **nothing in this product consumes an
    intent**: `apps/payments/autopay.py` says so in its own words, *"no function
    here takes a method, an amount or a date to capture"*, and the customer
    portal's refusal code was renamed `no_automatic_charge` on 2026-09-05 for the
    same reason. A debit that is never attempted cannot fail.

    So `RB-117`'s second half — *11 failed debits, $1,480.20 — 9 retrying, 2 need
    a person* — has no row it could come from on any deployment today, and a
    tile reading **0** over it would be indistinguishable from a morning when
    every debit went through. `reported` is `False` and the reason travels with
    it.
    """
    _tenant_id()
    statuses = tuple(models.INTENT_STATUSES)
    return {
        "rows": [],
        "reported": False,
        "why_not": (
            "nothing in this product drafts an autopay payment yet, so no debit can fail. "
            "Until a payment provider drafts them, this is not a count of zero."
        ),
        "as_of": as_of.isoformat(),
        # The evidence for the sentence above, as a VALUE rather than only in
        # prose (hard-won law 1): one status, and it is not a failure state.
        "intent_statuses": statuses,
    }


# ══════════════════════════════════════════════════════════════════════════
# PLANS IN FLIGHT AND THE INSTALMENTS THEY MISSED — runbook 25
# ══════════════════════════════════════════════════════════════════════════


def plans_in_flight(*, as_of: dt.date, grace_days: int = 0) -> dict[str, Any]:
    """Every payment plan still running, with the instalments it has missed.

    ⚠ **`LIVE_PLAN_STATUSES` IS READ, NEVER RESTATED.** It is the same tuple the
    `uq_one_live_plan_per_account` index is built on, so *in flight* means
    exactly one thing across the wizard, the ladder's pause and this runbook. A
    second list here would eventually disagree with the constraint that enforces
    it, and the disagreement would show up as one debt carrying two schedules.

    **A MISS IS A DUE DATE PASSED WITH NO PAYMENT INSIDE THE GRACE DAYS.**
    `PaymentPlanInstallment.paid_posted_on` records WHEN the payment that met an
    instalment POSTED — `BR-PAY-021` again, *on time is `posted_at ≤ due date`* —
    so an instalment is met when that column is set and missed when it is not and
    `due_date + grace_days` has passed. Nothing here re-derives the schedule:
    `apps.customers.payment_plan.build_schedule` owns the arithmetic (frozen as
    `GT-47`) and this reads what it wrote.

    ⚠ **THE GRACE DAYS AND THE MISS LIMIT ARE THE TENANT'S** (`BR-PAY-016`,
    settings `plan_missed_notice_days_after` and `plan_void_after_misses`). This
    takes the grace as an ARGUMENT so the caller reads Settings once, and it
    returns the miss COUNT rather than a verdict — deciding *voided* is the
    runbook's step, against a limit it read from the same Settings.
    """
    tenant_id = _tenant_id()
    plans = list(
        PaymentPlan.objects.filter(
            tenant_id=tenant_id, status__in=LIVE_PLAN_STATUSES
        ).order_by("account_id", "proposed_on", "id")
    )
    if not plans:
        return {"rows": [], "plans_in_total": 0, "grace_days": int(grace_days)}
    instalments: dict[str, list[Any]] = {}
    for row in PaymentPlanInstallment.objects.filter(
        tenant_id=tenant_id, plan_id__in=[one.pk for one in plans]
    ).order_by("seq"):
        instalments.setdefault(str(row.plan_id), []).append(row)
    accounts = _accounts_by_id({str(one.account_id) for one in plans})
    grace = dt.timedelta(days=max(int(grace_days), 0))
    rows: list[dict[str, Any]] = []
    for plan in plans:
        schedule = instalments.get(str(plan.pk), [])
        missed = [
            one
            for one in schedule
            if one.paid_posted_on is None and (one.due_date + grace) < as_of
        ]
        met = [one for one in schedule if one.paid_posted_on is not None]
        outstanding = sum((_money(one.amount) for one in missed), ZERO)
        account = accounts.get(str(plan.account_id))
        rows.append(
            {
                "plan_id": str(plan.pk),
                "account_id": str(plan.account_id),
                "account_no": _account_no(account) if account is not None else None,
                "label": (_account_no(account) if account is not None else None) or "",
                "status": plan.status,
                "currency": plan.currency,
                "total_amount": _stored(_money(plan.total_amount)),
                "installment_count": int(plan.installment_count),
                "instalments_met": len(met),
                "misses": len(missed),
                "missed_value": _stored(outstanding),
                "earliest_missed_on": (
                    min(one.due_date for one in missed).isoformat() if missed else None
                ),
                "next_due_on": _next_due(schedule, as_of),
                "suspend_disconnect": bool(plan.suspend_disconnect),
            }
        )
    return {
        "rows": rows,
        "plans_in_total": len(plans),
        "grace_days": int(grace_days),
        "as_of": as_of.isoformat(),
    }


def _next_due(schedule, as_of: dt.date) -> str | None:
    """The next instalment that has not been met, or `None` when none is left."""
    upcoming = [
        one.due_date
        for one in schedule
        if one.paid_posted_on is None and one.due_date >= as_of
    ]
    return min(upcoming).isoformat() if upcoming else None


def plan_notice_settings() -> dict[str, Any]:
    """`BR-PAY-016`'s three plan figures, from Settings — read, never duplicated.

    `plan_reminder_days_before` (3) · `plan_missed_notice_days_after` (1) ·
    `plan_void_after_misses` (2). `RBR-03`: policy lives in Settings and a card
    never carries a second copy, because a duplicated threshold is how a utility
    ends up with two answers and no way to tell which one voided the plan.

    ⚠ **AN UNREADABLE SETTING IS NOT A DEFAULT.** `settings_seam.collections`
    already refuses rather than falling back to the `BR-PAY-017` figures, and its
    reason applies here word for word: *"every step it takes reaches a real
    customer"*. So a refusal travels as `readable=False` and the runbook reports
    *not set up* rather than voiding a plan against a number nobody chose.
    """
    from apps.payments import settings_seam

    try:
        values = settings_seam.collections()
    except Exception as refusal:  # noqa: BLE001 — the owning module's own words
        return {"readable": False, "why_not": str(refusal)}
    return {
        "readable": True,
        "reminder_days_before": _whole(values.get("plan_reminder_days_before")),
        "missed_notice_days_after": _whole(values.get("plan_missed_notice_days_after")),
        "void_after_misses": _whole(values.get("plan_void_after_misses")),
        "returns_before_privilege_lost": _whole(values.get("nsf_privilege_n")),
    }


def _whole(raw: Any) -> int | None:
    """An integer setting, or `None` where the tenant has no value for it."""
    if raw in (None, ""):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):  # pragma: no cover - the family validates it
        return None


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-027 · US-RBS-029 · US-RBS-035 · US-RBS-036 (EP-RBS-05; CR-075 wave R′, the payments half)
# generated: 2026-09-07 by the CR-075 wave R′ payments build lane
# checklist: A✔ B✔ C✔ D=n/a(no endpoint — a seam reads this in process, never over HTTP) E=n/a(no screen) F✔ G✔ H=n/a(no 🔒 path: no money is written, no idempotency key is composed and no rounding is decided here — every figure is read at its stored precision and carried as a string)
# gates: pytest tests/test_us_rbs_027_deposit_review.py tests/test_us_rbs_029_autopay_prenotice.py tests/test_us_rbs_035_payment_plans.py tests/test_us_rbs_036_returned_payments.py · G20 (every seam name resolves) · G6 (no clock read — as_of is an argument on every function)
# exceptions: `failed_debits` and `returned_items_landed` report NOT REPORTED rather than zero, because nothing in this product drafts a debit or records a bank return code — both absences are structural and are named in the module docstring · `returned_payment_counts` counts reversing ROWS rather than `accounts.nsf_count`, which nothing increments (DEF-069) · no deposits table exists: a deposit is two columns on `accounts` (B2 r9 #5)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
