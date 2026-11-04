# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-024 (EP-CWP-04) — the balance read. Screens: CWP-018's
#           consequence panel · CWP-022 Home's lead tile · CWP-023 All my
#           accounts
# Rules:    BR-CWP-015 (balances across the set are shown SEPARATELY and
#           totalled for information; NEVER merged into one invoice) ·
#           BR-CWP-041 (the portal sees NOTHING above the issued bill) ·
#           BR-CWP-047 (re-read on every load; no portal screen caches a
#           balance or a credit) · BR-CWP-012 (read through a seam, no second
#           copy) · CLAUDE.md hard rule 2 (4 decimals stored, display 2; never
#           float, never cents) · CR-068 §2d (no arithmetic of its own)
# Tests:    06-backend/tests/test_us_cwp_024_balance.py (TC-2 $872.82 ·
#           TC-3 $102.18 · TC-6 the corrected pair counted once)
# Impacts:  apps/portal/api.py (`GET accounts/{id}/balance`,
#           `GET balance/summary`)
# ───────────────────────────────────────────────────────
"""THE BALANCE READ — *"the single most-requested number in the whole product"*.

⚠ **IT COMPUTES NOTHING.** Every figure below comes out of `payments`' own
published reads and is carried, not recomputed. `CR-068` §2d says so and the
reason is one line: a second implementation of *what do I owe* is a second
answer, and the customer would be looking at the one the letter does not say.

WHAT IS COMPOSED, AND THE ONE THING THAT WAS NOT
------------------------------------------------
* `apps.payments.open_bills.open_bill_position(account_id=)` — the OPEN BILLS
  of one account, oldest first, each with what it charged, what it asks for,
  what has been allocated to it and what is still open.
* `apps.payments.billing_seam.outstanding_positions(account_ids=)` — the same
  arithmetic in bulk, plus `oldest_due_on` and — since `CR-059` CS-38 — the
  account's credit taken off the chase.

⚠ **`outstandings()` WAS NAMED BY THE EXECUTION PLAN AND IS DELIBERATELY NOT
USED, AND THAT IS A JUDGMENT WITH A REASON RATHER THAN A SHORTCUT** (recorded
in `12-governance/02-decision-log.md`, 2026-09-04). `outstandings()` is the
COLLECTIONS view: it joins `AccountCollectionState`, the live payment plan, the
notice counts and `DeliveryReturnEvent`'s bad-address flag onto every row. Every
one of those is on `BR-CWP-052`'s held-back list or above the issued bill
(`BR-CWP-041`). Composing it would mean assembling the four things the customer
must not see and then remembering to drop them — one serialiser away from a
customer reading their own collection ladder. `outstanding_positions` is the
arithmetic **without** them, and it is what `outstandings()` itself composes.

TWO FIGURES, BOTH NAMED, BECAUSE THEY ARE DIFFERENT FACTS
---------------------------------------------------------
`owing` is the NET figure — bills less allocations less the credit the utility
is already holding. It is the number the collection letter, the next bill and
the ladder all state (`CR-059` CS-38: *"the balance, the next bill and the
collection ladder all agree with the letter"*), so it is the number the portal
states too; a fourth disagreeing figure is the whole defect CS-38 closed.
`bills_open` is what the bills alone add up to, and `credit_held` is the
difference. On an account holding no credit — nearly all of them — the two are
equal, and `US-CWP-024` TC-2's `$872.82` is that case.

WHAT MAKES THE HARD CASES COME OUT RIGHT WITHOUT A LINE OF CODE HERE
--------------------------------------------------------------------
* **Part-paid** (`$142.18` with `$40.00` against it → **`$102.18`**): the seam
  measures a bill at `amount_due − allocated` and drops it only when that is
  ≤ 0, so a part-paid bill is neither absent nor whole. `BR-CWP-043`'s third
  state falls out of the arithmetic rather than being a case here.
* **Void and draft** are excluded because the seam's `OPEN_INVOICE_STATUSES` is
  `("issued", "paid")` — which is also `BR-CWP-041` (*"the portal sees nothing
  above the issued bill"*) enforced one module down, in the query.
* **A corrected pair counts once** for the same reason: a corrected original
  carries `status = "corrected"` and is therefore not in that tuple, while its
  replacement is `issued`. The customer sees `$129.02` once and not
  `$154.90 + $129.02` (`BR-CWP-042` keeps BOTH ROWS on the bills LIST — that is
  wave G's screen — and this read counts what is owed, which is one of them).
* **Never cached** (`BR-CWP-047`): there is no cache in this file, no
  `cache_page` on the endpoints that call it, and `US-CWP-024`'s test asserts a
  second read after a payment lands returns the new figure.

MONEY
-----
Every figure leaves here as a **string quantised to four decimals** — hard rule
2's stored precision, carried rather than rounded, because rounding happens at
DISPLAY and this is not display. `Decimal` throughout; no float touches a
number in this file.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from apps.payments import models as payments_models
from core import tenancy as core_tenancy

FOUR_DP = Decimal("0.0001")
ZERO = Decimal("0")


def _money(value: Any) -> str:
    """Four decimals, as a string. Never a float, never cents (hard rule 2)."""
    return str(Decimal(value or 0).quantize(FOUR_DP))


def account_balance(account_id: Any) -> dict[str, Any]:
    """What ONE account owes, and the bills behind it.

    ⚠ **THE BODY MOVED TO `apps/payments/account_balance.py` ON 2026-10-07
    (`CR-174-BRC10`) AND THIS DELEGATES TO IT.** US Payments' account lookup has
    to answer the same live balance a customer reads here (PO D1, *"A person
    standing at a machine needs the live balance"*), and two callers of one
    figure need one function rather than two that agree today. Every key this
    returned before it still returns, from the same two payments reads; three
    were added there (`credit_position`, `balance`, `past_due`) and the portal
    ignores them.

    ⚠ **`account_id` IS ALWAYS ONE THE CALLER HAS ALREADY CHECKED IS IN THE
    SESSION'S SET.** This seam does not know about sessions and must not: the
    filter is `BR-CWP-010`'s and belongs in the query the endpoint makes, which
    is where `api.py` puts it.
    """
    from apps.payments import account_balance as payments_account_balance

    return payments_account_balance.account_balance(account_id)


def balance_summary(account_ids: list[Any], *, as_of: date | None = None) -> dict[str, Any]:
    """Every account in the set, **separately**, and a total for information.

    ⚠ **`BR-CWP-015`: NEVER MERGED INTO ONE INVOICE.** The rows below are the
    product; `total_owing` is a sum for a person's convenience and there is no
    field anywhere in this response that could be mistaken for a single amount
    payable. `US-CWP-024` TC-2's `$872.82` is four rows and a total, and the
    landlord's `$0.00` row is one of the four rather than an absence.

    ⚠ **AN ACCOUNT OWING NOTHING IS LISTED** — `customer_open_bill_position`'s
    own reasoning, quoted because a lane will reach for the other one: *"an
    account that owes nothing is a property the customer still holds"*, and
    hiding it would make the total disagree with the switcher.

    `as_of` is a PARAMETER and never a clock read inside this module
    (`BR-TEN-043`): the caller holds the request's own date.
    """
    ids = [str(account_id) for account_id in account_ids]
    rows = [account_balance(account_id) for account_id in ids]

    currencies = {row["currency"] for row in rows if row.get("currency")}
    total = sum((Decimal(row["owing"]) for row in rows), ZERO)
    problems: list[dict[str, Any]] = []
    for row in rows:
        problems.extend(row.get("problems") or ())
    if len(currencies) > 1:
        # Hard rule 2's other half — the sum only means something when the
        # parts share a code. BR-TEN-042 locks a utility to one currency, so
        # this is a data fact somebody must see, never a conversion.
        problems.append(
            {
                "code": "accounts_in_several_currencies",
                "br_ref": "BR-TEN-042",
                "detail": f"this login's accounts carry {sorted(currencies)}; the total is not "
                "stated, because adding them would invent a rate. Each account is listed with "
                "its OWN code.",
            }
        )
    return {
        "as_of": as_of.isoformat() if as_of is not None else None,
        "accounts": rows,
        "account_count": len(rows),
        "total_owing": _money(total) if len(currencies) <= 1 else None,
        "currency": next(iter(currencies)) if len(currencies) == 1 else None,
        "problems": problems,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-024@c05e4dd4 (EP-CWP-04 story + BR-CWP-015/041/047 verbatim)
# generated: 2026-09-04 by the CR-068 wave E build lane
# checklist: A✔ B✔ C✔ D✔(api.py) E✔(CWP-018 consequence panel · CWP-022 tile) F✔ G✔ H=n/a(no 🔒 path — it composes, it computes nothing)
# gates: G81 (a seam performs no ORM write) · pytest tests/test_us_cwp_024_balance.py
# exceptions: `outstandings()` was named by the plan and is NOT composed — it joins four held-back facts onto every row (BR-CWP-041/052); `outstanding_positions` is the same arithmetic without them. Decision logged 2026-09-04.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


# ── CR-068 wave F · CWP-022's *last payment* tile (US-CWP-025) ──────────────


def last_payment(account_ids: list[Any]) -> dict[str, Any] | None:
    """The most recent payment across this login's accounts, or None.

    ⚠ **POSTED OR CLEARED PAYMENTS ONLY (amended 2026-10-21, CR-186-BRC10).**
    This read *"cleared payments only"* while `cleared` meant *money taken*.
    Since the PO's ruling of 2026-10-21 a payment is `posted` and applied the
    moment it is taken and `cleared` only when the bank statement is
    reconciled — so the balance moves at `posted`, and this tile follows the
    balance. A payment still processing (or cancelled, or failed) is not money
    the customer has been given credit for, and showing it as *your last
    payment* would have somebody ring up when their balance did not move. A
    reversing row is not shown for the same reason from the other direction.

    ⚠ **`None` IS A NORMAL ANSWER** (`BR-CWP-093`) — a new customer has paid
    nothing yet, and the tile closes up rather than reading `$0.00`, which would
    say *you paid nothing* instead of *you have not paid yet*.

    ⚠ **NO `confirmation`, NO `memo`.** A cheque number and a clerk's note are
    the utility's record of the payment, not the customer's view of it — and
    `confirmation` is one of the three columns the PO opened to correction on
    2026-09-02, so it is a value that CHANGES. A customer reading yesterday's
    cheque number off a cached page is a support call nobody needs.
    """
    from apps.payments import balance_rule
    from apps.payments import models as payment_models

    row = (
        payment_models.Payment.objects.filter(
            # `BR-CWP-010` — the tenant is IN THE QUERY, not left to RLS alone
            # (`G96`, `DEF-CWP-3775`). The suite runs on in-memory SQLite,
            # which has no row-level security, so the database's guarantee is
            # invisible to every test here and a regression would be silent.
            tenant_id=core_tenancy.current_tenant_id(),
            account_id__in=[str(one) for one in account_ids],
            # CR-186-BRC10: a receipt that stands is `posted` from the moment
            # it is taken and `cleared` only once the bank statement is
            # reconciled, so `cleared` alone would hide every new payment
            # here for days. `balance_rule.RECEIPT_STATUSES` is both.
            status__in=balance_rule.RECEIPT_STATUSES,
        )
        .select_related("method")
        .order_by("-posted_at")
        .first()
    )
    if row is None:
        return None
    return {
        "amount": _money(row.amount),
        "currency": row.currency,
        "paid_on": row.posted_at.date().isoformat() if getattr(row, "posted_at", None) else None,
        #: The tenant's OWN word for the tender — `method` is the tenant-
        #: extensible lookup, so *Bank transfer* is whatever they call it.
        "method": getattr(getattr(row, "method", None), "name", None),
    }


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 · `CWP-031` — THE NUMBER ON THE RECEIPT, FOR A DOCUMENT ROW (US-CWP-036)
# ═══════════════════════════════════════════════════════════════════════════


def payment_numbers(payment_ids: list[Any]) -> dict[str, str]:
    """`{payment id: PMT-2608-0042}` for the ids that HAVE a number.

    The `payment_no` series (r12 #13) is what a customer can quote back on the
    telephone. An id with no number is ABSENT from this map rather than
    defaulted to the id: B14 rule 31 forbids a database id as a visible value,
    and the caller says so in words instead (`DEF-3158`).
    """
    ids = [str(one) for one in payment_ids]
    if not ids:
        return {}
    rows = payments_models.Payment.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), id__in=ids  # G96 — see above
    ).values_list("id", "payment_no")
    return {str(key): number for key, number in rows if number}


def payment_amounts(payment_ids: list[Any]) -> dict[str, dict[str, Any]]:
    """`{payment id: {"amount": "38.4400", "currency": "USD"}}` — HOW MUCH a
    receipt was for, so `CWP-031` can name the document rather than its class.

    ⚠ **THIS IS WHAT MAKES A LIST OF RECEIPTS USABLE** (`DEF-CWP-3969`). Every
    receipt a customer had been sent read the same six words, so the only thing
    distinguishing one row from another was a payment number — which asks
    somebody to know their own reference numbers to find the receipt for the
    $38.44 they paid in June.

    ⚠ **THE FIGURE IS THE STORED 4dp ONE AND IT IS ROUNDED WHERE MONEY IS
    ALWAYS ROUNDED** — at display, by the screen's own `formatMoney` (hard rule
    2). Rounding here would put a second money formatter in a seam.

    A payment with no amount is ABSENT from the map and the caller falls back
    to the kind word, rather than naming a document after a blank.
    """
    ids = [str(one) for one in payment_ids]
    if not ids:
        return {}
    rows = payments_models.Payment.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), id__in=ids
    ).values_list("id", "amount", "currency")
    return {
        str(key): {"amount": f"{amount:.4f}", "currency": currency}
        for key, amount, currency in rows
        if amount is not None
    }


def settled_guest_charge(*, idempotency_key: str) -> dict[str, Any] | None:
    """The receipt a PREVIOUS attempt under this key already earned, or `None`.

    ⚠ **THIS EXISTS BECAUSE THE WORST ANSWER ON A MONEY PATH IS *there is
    nothing to pay*** (`DEF-CWP-3950`). A guest pays `$142.18` against
    `BL-2608-0141`, the payment commits, the RESPONSE is lost on the way back,
    and the browser resends. Hard rule 6 is genuinely satisfied — the rails
    collapse the two onto one payment — but the retry never reaches the rails:
    it stops at the payability re-read (`BR-CWP-058`), because the bill is now
    settled, and the person is told *"There is nothing to pay"*. They cannot
    tell whether their money was taken, and the obvious thing to do about it is
    to pay again.

    ⚠ **A READ AND NOTHING ELSE.** `payment_webhook_events` is written by
    `payments`' own settlement door and this only looks at it; the portal writes
    no payment row anywhere (`G81` fails this package for an ORM write of its
    own). Nor does it re-price, re-allocate or re-decide anything — every figure
    comes off the payment that already exists.

    ⚠ **THE KEY IS THE DELIVERY'S `event_id`, WHICH IS WHERE THE ATTEMPT KEY
    LANDS.** `webhooks.settle_charge` is called with `key=` and stores it as
    `event_id` — its own docstring: *"`event_id` here is the idempotency key we
    presented to the provider"* — so the row this finds is the one that recorded
    THIS attempt.

    ⚠ **`payment_id__isnull=False` IS LOAD-BEARING.** A delivery that produced
    NO payment is a row that exists and is not a receipt: `BR-PAY-003`'s case is
    exactly *the provider approved the debit and we could not record it*, and
    the delivery row is kept precisely so the money can be found. Replaying one
    would tell somebody they had paid when nothing was recorded — the same
    class of lie as the defect this function fixes, pointing the other way.

    ⚠ **NOT FILTERED BY PROVIDER, DELIBERATELY.** The caller is an edge that has
    not resolved one, and resolving it would mean asking `active_provider`
    before the guards have run. The key is already unique per tenant, bill and
    visit; the tenant filter is hard rule 1's and `BR-CWP-010`'s.
    """
    key = str(idempotency_key or "").strip()
    if not key:
        return None
    tenant_id = core_tenancy.current_tenant_id()
    delivery = (
        payments_models.PaymentWebhookEvent.objects.filter(
            tenant_id=tenant_id, event_id=key, payment_id__isnull=False
        )
        .order_by("received_at")
        .first()
    )
    if delivery is None:
        return None
    payment = payments_models.Payment.objects.filter(
        tenant_id=tenant_id, pk=delivery.payment_id
    ).first()
    if payment is None or not payment.payment_no:
        #: A payment with no HUMAN number would put a row id on a receipt
        #: (B14 rule 31), so this answers `None` and the edge falls through to
        #: the ordinary refusal rather than inventing a reference.
        return None
    return {
        "reference": payment.payment_no,
        "amount": payment.amount,
        "currency": payment.currency,
        #: WHEN THE MONEY WAS TAKEN, never when the retry arrived. A replayed
        #: receipt stamped with today's clock is how a customer concludes they
        #: have paid twice.
        "paid_at": payment.posted_at or payment.created_at,
    }


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 · `CWP-063` — A PLAN THE UTILITY HAS OFFERED YOU (US-CWP-053)
#
# ⚠ **THE READ IS THE S24 WIZARD'S OWN AND IS REACHED, NEVER REBUILT.**
# `apps.payments.plans.payment_plans_for_account` has served
# `GET accounts/{id}/payment-plans` since 2026-08-16 and is the read the portal
# reuse map names for this screen. `US-CWP-053` §7 is emphatic about why that
# matters here more than anywhere: *"the figures on the offer must be
# byte-identical to the plan that activates — a customer who accepts one
# schedule and receives another is the worst outcome on this screen"*. One
# implementation is what makes that true by construction.
# ═══════════════════════════════════════════════════════════════════════════

#: `collections_models.PLAN_AGREEMENT_SENT` — the ONE state this screen exists
#: for. `BR-CWP-065`: a plan activates on the CUSTOMER's signature alone, so
#: `agreement_sent` means *offered, waiting on you*, and it is the only state
#: where the customer has something to do.
PLAN_AGREEMENT_SENT = "agreement_sent"


def plan_offer_for(account_ids: list[Any], *, as_of: date) -> dict[str, Any] | None:
    """The one plan waiting on this customer's signature, or `None`.

    `None` means there is no offer — a real and ordinary answer, and the screen
    says so rather than drawing an empty offer.

    ⚠ **`BR-CWP-010` IS IN THE LOOP AND NOT AFTER IT.** The published read is
    per account, so it is asked once per account in the session's OWN set;
    there is no path here that could be handed an account the session does not
    hold.

    ⚠ **AT MOST ONE.** `BR-CUS-043` holds one live plan per account in the
    DATABASE (a partial unique index), so a customer with four accounts can be
    offered at most one plan per account; the newest `agreement_sent` is the
    offer, and a second would be a defect upstream rather than a choice here.
    """
    from apps.payments import plans as payments_plans

    for account_id in account_ids:
        rows = payments_plans.payment_plans_for_account(account_id, as_of=as_of)
        for row in rows:
            if row["status"] == PLAN_AGREEMENT_SENT:
                return dict(row)
    return None


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave G · `CWP-041` — the money list (US-CWP-048)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **EVERY FIGURE BELOW COMES OUT OF A READ SOMEBODY ELSE ALREADY PUBLISHES.**
# The PO's ruling of 2026-09-04 — *"all the services that are required for
# Consumer portal - you will find it same set of services, endpoints are
# already available for Accounts - account details view"* — and
# `12-reuse-map.md`, which names this screen's read: **payments' S33 list**.
# So the payments half is `apps.payments.selectors.payment_queryset()` +
# `payment_row()`, the pair the staff Payments tab is built on, and the credit
# half is `apps.billing.selectors.account_credit_notes`, the read `CR-059`
# CS-37 added. This module composes and NARROWS; it computes nothing.
#
# ⚠ **WHAT IS NEW HERE, NAMED SO IT CAN BE CHECKED (reuse map step 5).** There
# is **no per-account write-off read anywhere in this product** —
# `writeoffs.write_off_queue` is the whole tenant's approval queue and carries
# `reason` and `note`, and `bad_debt` is a period report. Searched:
# `apps/payments/{selectors,writeoffs,bad_debt,customer_position,open_bills,
# outstandings}.py`, `apps/billing/selectors.py`, every
# `apps/*/[a-z]*_reads.py`, and both `apps/customers/api.py` and
# `apps/payments/api.py` url tables. So `_write_off_rows` below reads
# `WriteOff` directly, in the posture `billing_seam.bills_for` already takes.
#
# ⚠ **AND `billing.Adjustment` HAS NO WRITER AT ALL** — the execution plan
# names it for this screen, and `grep "Adjustment.objects.create"` over
# `06-backend/apps/` returns the model definition and nothing else. A
# goodwill concession is a `CreditNote` (`billing/credit_notes_api.py`,
# CS-37), which is what `BR-CWP-050`'s *"adjustment … with a plain-English
# reason"* actually resolves to: the reason is a COLUMN there. On a `payments`
# row typed `credit` or `adjustment` it is not — CS-35, verbatim, *"Data: none
# on payments"* — so such a row states its TYPE and its date and never
# pretends to a reason it does not hold.
#
# ⚠ **THE SIGN IS THE SERVER'S, EVERYWHERE.** A reversal is `−129.02` and a
# credit note is negative by database constraint (`credit_notes.amount <= 0`,
# added after two writers stored opposite signs and a sign-off panel read
# `$272.30` on an account owing `$222.30` — DEF-085). Nothing here takes an
# absolute value and nothing flips a sign.

#: What a row IS. A key, never a sentence: eleven catalogues write the words
#: (B14 rule 35).
MONEY_PAYMENT = "payment"
MONEY_REVERSAL = "reversal"
MONEY_CREDIT = "credit"
MONEY_WRITE_OFF = "write_off"

#: What STATE the customer reads on the row.
#:
#: ⚠ **`received` REPLACED `cleared` ON 2026-10-21 (`DEF-CWP-10341`).** Since
#: `CR-186-BRC10` every payment is `posted` at entry and `cleared` only when
#: its deposit batch is reconciled with the bank. That is the utility's
#: bookkeeping and not the customer's question, so BOTH read *received* here —
#: and the old word *cleared* would have been a claim about the bank that a
#: `posted` row cannot make.
STATE_RECEIVED = "received"
STATE_PROCESSING = "processing"
STATE_FAILED = "failed"
#: A payment taken by mistake and undone (`payments/0036`; since `CR-186`,
#: only from `posted`). ⚠ **BOTH ROWS OF A CANCEL READ THIS** — the original and
#: the reversing row `cancel.py` writes beside it. Without it the pair read
#: *reversed* + *bounced*, *returned by the bank*, about money no bank touched.
STATE_CANCELLED = "cancelled"
#: ⚠ **THE EXPLICIT FALLBACK.** A status `payments` does not define reads as
#: *status unavailable* — never a borrowed real word, which would be a guess.
STATE_UNKNOWN = "unknown"
#: The reversing row itself — the money the bank took back.
STATE_BOUNCED = "bounced"
#: ⚠ **DERIVED, NEVER STORED.** The original payment's own `status` column is
#: still `cleared` — `reversal.py` writes no `original.save()` anywhere, because
#: hard rule 4 forbids an UPDATE on a payment. This word means *"a reversing row
#: exists that points at me"* and is computed on every read.
STATE_REVERSED = "reversed"
STATE_CREDITED = "credited"
STATE_WRITTEN_OFF = "written_off"
STATE_WRITE_OFF_REVERSED = "write_off_reversed"

#: `US-PAY-012` — only an APPROVED write-off has left the books. A request
#: awaiting a Finance approver has no effect on what the customer owes and does
#: not belong on their money list; a REJECTED one never will.
WRITE_OFF_VISIBLE = ("approved", "reversed")


def money_list(account_ids: list[Any], *, year: int | None = None) -> list[dict[str, Any]]:
    """`CWP-041` — everything that moved money on this login's accounts.

    ⚠ **A BOUNCE IS TWO ROWS AND NEITHER OF THEM IS AN EDIT** (`BR-CWP-061`,
    hard rule 4). The reversing row reads *returned by the bank* at `−$129.02`
    and sits DIRECTLY ABOVE the `$129.02` it undoes. Both rows are real rows in
    `payments`; the word *reversed* on the second is this module's reading of
    *"something points at me"*, not a status anybody wrote over `cleared`.

    ⚠ **THE PAIR IS ANCHORED AT THE REVERSAL'S DATE, AND THAT IS A CHOICE WITH
    A REASON.** Sorting the two rows independently would separate them the day
    a June cheque bounces in July, and the story's whole promise is that they
    are adjacent. Anchoring at the LATER date also puts the pair where the
    customer's bank statement shows the trouble, which is what this screen is
    for. On the fixture both are 2 Jul and the order is exactly TC-2's.

    ⚠ **`BR-CWP-010`, BOTH HALVES IN THE QUERY.** `payment_queryset()` filters
    the tenant; `account_id__in` is added here, and the caller has already
    intersected the ids with the session's set.

    ⚠ **NO ROW ID LEAVES THIS FUNCTION** (B14 rule 31 — and eight characters of
    one is the same breach as thirty-six). The visible reference is the cheque
    number in `confirmation`, or the `PMT-` number, or the credit note's own
    number. `customer_name` and `memo` stay behind too (`BR-CWP-052`).
    """
    from apps.billing import selectors as billing_selectors
    from apps.payments import selectors as payment_selectors

    ids = [str(one) for one in account_ids]
    if not ids:
        return []

    rows = list(
        payment_selectors.payment_queryset()
        .filter(account_id__in=ids)
        .prefetch_related("reversals")
        .order_by("-posted_at", "-id")
    )
    by_id = {str(row.pk): row for row in rows}
    # ⚠ **THE BATCH LOOKUP IS TAKEN ONCE FOR THE WHOLE TIMELINE.** `payment_row`
    # will do it per row when nothing is passed, which is correct and is two
    # queries — and this loop is UNPAGED over every payment of up to four
    # accounts, so per-row would be an N+1 on a customer-facing screen. The map
    # is built here and handed to every call below.
    batch_labels = payment_selectors.payment_batch_labels(rows)
    #: original id → its reversing rows.
    reversals: dict[str, list[Any]] = {}
    for row in rows:
        if row.reverses_payment_id is not None:
            reversals.setdefault(str(row.reverses_payment_id), []).append(row)

    out: list[tuple[Any, dict[str, Any]]] = []
    for row in rows:
        if row.reverses_payment_id is not None and str(row.reverses_payment_id) in by_id:
            # Emitted with its original, immediately above it — see the
            # docstring. A reversal whose original is on ANOTHER account (which
            # `BR-CWP-010` can produce for a landlord reading one of four) falls
            # through to the orphan pass rather than disappearing.
            continue
        undone = reversals.get(str(row.pk), [])
        anchor = max([row.posted_at] + [one.posted_at for one in undone])
        for one in sorted(undone, key=lambda r: (r.posted_at, str(r.pk)), reverse=True):
            out.append((anchor, _payment_view(payment_selectors.payment_row(one, batch_labels=batch_labels), one)))
        out.append((anchor, _payment_view(payment_selectors.payment_row(row, batch_labels=batch_labels), row)))

    for row in rows:
        if row.reverses_payment_id is not None and str(row.reverses_payment_id) not in by_id:
            out.append((row.posted_at, _payment_view(payment_selectors.payment_row(row, batch_labels=batch_labels), row)))

    #: ⚠ **THE ANCHOR TRAVELS WITH THE ROW, AND IT HAS TO.** A first draft
    #: sorted the pairs correctly and then re-sorted the merged list by
    #: `view["date"]`, which SPLIT every bounce whose return date was not its
    #: payment date: a cheque paid on 13 June and returned on 2 July came back
    #: `bounced · cleared · reversed`, with an unrelated payment standing between
    #: a reversal and the row it undoes. Caught by
    #: `test_us_cwp_048_a_bounce_a_month_later_…`, which is the case the fixture's
    #: same-day figures cannot reach.
    for anchor, view in out:
        view["_anchor"] = anchor.date().isoformat()
    money = [view for _anchor, view in out]

    for account_id in ids:
        money.extend(_credit_rows(billing_selectors, account_id))
    money.extend(_write_off_rows(ids))
    for view in money:
        view.setdefault("_anchor", view["date"] or "")

    #: ⚠ **STABLE, SO THE PAIR IS NEVER SPLIT.** Sorting on the anchor keeps a
    #: reversal and its original adjacent whatever else shares the day, because
    #: Python's sort is stable and they carry the same key.
    money.sort(key=lambda view: view["_anchor"] or "", reverse=True)
    if year is not None:
        #: ⚠ **FILTERED ON THE ROW'S OWN DATE, NEVER THE ANCHOR.** *This year*
        #: means *this year's money*, and a June payment returned in July is a
        #: June payment.
        money = [view for view in money if (view["date"] or "").startswith(f"{year:04d}-")]
    for view in money:
        view.pop("_anchor", None)
    return money


def _payment_view(staff_row: dict[str, Any], row: Any) -> dict[str, Any]:
    """One S33 row as a CUSTOMER reads it — a projection, never a second read.

    ⚠ **WHAT IS DROPPED IS THE POINT.** `id`, `account_id`, `customer_name` and
    `memo` are in the staff row and in none of the fields below: a database id
    is never a visible value (B14 rule 31) and a clerk's note is not the
    customer's view of their payment (`BR-CWP-052`).
    """
    is_reversal = row.reverses_payment_id is not None
    was_reversed = False if is_reversal else bool(list(row.reversals.all()))
    applied = [
        entry["invoice_number"]
        for entry in staff_row.get("applied_to") or ()
        if entry.get("invoice_number")
    ]
    return {
        "kind": MONEY_REVERSAL if is_reversal else MONEY_PAYMENT,
        "date": staff_row["posted_at"][:10] if staff_row.get("posted_at") else None,
        #: The tenant's OWN word for the tender (`BR-PAY-026`), so *Bank
        #: transfer* is whatever this utility calls it. `None` on a credit or an
        #: adjustment row, which carry no instrument — a stated absence.
        "how": staff_row.get("method_name"),
        #: ⚠ **A HUMAN REFERENCE OR NOTHING** — the cheque number the customer
        #: wrote (TC-10), else the `PMT-` number. Never a row id, never eight
        #: characters of one.
        "reference": _customer_reference(staff_row),
        #: ⚠ **THE `PMT-` NUMBER, WHICH IS NOT ALWAYS WHAT `reference` HOLDS**
        #: (`CR-085` `CPB-20`). `_customer_reference` prefers the CHEQUE number
        #: the customer wrote, because that is what they can look up in their
        #: own bank statement — and the receipt DOCUMENT is filed under the
        #: payment's own number. Serving the receipt off `reference` would work
        #: on card and bank-transfer rows and answer *not found* on every
        #: cheque, which is exactly the row a person most often wants a receipt
        #: for. Two facts, two fields; neither is an id (B14 rule 31 — both are
        #: numbers printed on paper).
        #: `None` on a reversal, a credit and a write-off. A reversal IS a
        #: `payments` row and may well carry a number of its own, and it is
        #: still not a receipt: nothing posts a receipt for a cheque that
        #: BOUNCED, and offering one would hand a customer a document saying we
        #: had their money.
        "receipt_reference": None if is_reversal else (row.payment_no or None),
        #: ⚠ A reversal's *applied to* cell reads **returned by the bank**; the
        #: negative allocations behind it are the ledger's business, not a
        #: sentence for a customer (TC-2).
        "applied_to": [] if is_reversal else applied,
        #: ⚠ **NOT ON A CANCEL'S REVERSING ROW** (`DEF-CWP-10341`). `cancel.py`
        #: writes a negative self-FK row exactly as a bounce does, and that row
        #: read *Returned by the bank*, in red — about money the utility undid
        #: itself and no bank ever touched.
        "returned_by_the_bank": is_reversal and not _is_cancelled(row),
        #: The sign the server holds. `−129.02` on a reversal, and no absolute
        #: value is taken anywhere.
        "amount": _money(staff_row["amount"]),
        "currency": staff_row.get("currency"),
        "state": _payment_state(row, is_reversal=is_reversal, was_reversed=was_reversed),
        #: A `credit` or `adjustment` row is not a receipt and says so. The
        #: reason for one has NO column (`CR-059` CS-35) and is not invented.
        "money_type": row.type,
    }


def _customer_reference(staff_row: dict[str, Any]) -> str | None:
    """`#10188` · `Chase ••••4021` · `PMT-26-09014` — **what a CUSTOMER would
    recognise**, which is not always the same string a clerk typed.

    ⚠ **`DEF-CWP-3974` — THIS COLUMN PRINTED OUR INTERNAL VALUE VERBATIM.**
    Every row of `CWP-041` read `SAMPLE-BL-2608-000077`, and the fixture was
    only half the fault: a cheque number stored bare as `10188` still reads on
    screen as a quantity rather than as a cheque, and `CWP-041.png` writes it
    `#10188`. So the tender decides the shape, once, HERE — a second answer in
    the browser would be a second definition of *what is my reference*.

    ⚠ **THE `#` IS ADDED ONLY TO A BARE RUN OF DIGITS ON A CHEQUE.** A clerk
    who already typed `#10188`, or who typed a bank's own alphanumeric
    reference, is left exactly as they typed it: this formats a value, it never
    corrects one.
    """
    confirmation = (staff_row.get("confirmation") or "").strip()
    if not confirmation:
        #: A cash payment has no reference at all. The `PMT-` number is what a
        #: customer reads out on the telephone (B14 rule 31 — never a row id).
        return staff_row.get("payment_no")
    if _is_cheque(staff_row.get("method")) and confirmation.isdigit():
        return f"#{confirmation}"
    return confirmation


#: The tender codes this product seeds and imports for a cheque. A tenant may
#: name the tender whatever it likes (`BR-PAY-026`), so this matches the CODE
#: and never `method_name`.
_CHEQUE_CODES = frozenset({"check", "cheque"})


def _is_cheque(method_code: Any) -> bool:
    return str(method_code or "").strip().lower() in _CHEQUE_CODES


def _is_cancelled(row: Any) -> bool:
    from apps.payments import models as payment_models

    return row.status == payment_models.PAYMENT_CANCELLED


def _payment_state(row: Any, *, is_reversal: bool, was_reversed: bool) -> str:
    """The word on the chip. ⚠ **`reversed` IS DERIVED** — see `STATE_REVERSED`.

    ⚠ **`cancelled` IS ASKED FIRST** (`DEF-CWP-10341`). A cancel writes a
    reversing row too, so asked any later both halves of the pair fell into the
    bounce branches — *bounced* over *reversed* — about money no bank returned.

    ⚠ **EVERY STATUS IS NAMED; NOTHING FALLS THROUGH TO A REAL WORD.** The last
    line used to return *cleared* for anything unrecognised, which is how a
    `cancelled` row came to read as money received.
    """
    from apps.payments import models as payment_models

    if _is_cancelled(row):
        return STATE_CANCELLED
    if is_reversal:
        return STATE_BOUNCED
    if was_reversed:
        return STATE_REVERSED
    if row.status == payment_models.PAYMENT_PROCESSING:
        return STATE_PROCESSING
    if row.status == payment_models.PAYMENT_FAILED:
        return STATE_FAILED
    if row.type in (payment_models.PAYMENT_TYPE_CREDIT, payment_models.PAYMENT_TYPE_ADJUSTMENT):
        return STATE_CREDITED
    if row.status in (payment_models.PAYMENT_POSTED, payment_models.PAYMENT_CLEARED):
        return STATE_RECEIVED
    return STATE_UNKNOWN


def _credit_rows(billing_selectors: Any, account_id: str) -> list[dict[str, Any]]:
    """The goodwill credit — `BR-CWP-050`, through the read that already exists.

    `account_credit_notes` is `GET /accounts/{id}/credit-notes` (`CR-059` CS-37)
    and its `reason` is a COLUMN, which is what makes *"with a plain-English
    reason"* answerable here and not on a `payments` row.

    ⚠ **THE AMOUNT ARRIVES NEGATIVE AND LEAVES NEGATIVE.**
    `credit_notes.amount <= 0` is a database CHECK added after two writers
    stored opposite signs (DEF-085). Nothing here re-signs it.
    """
    answer = billing_selectors.account_credit_notes(account_id)
    return [
        {
            "kind": MONEY_CREDIT,
            "date": (note.get("issued_at") or "")[:10] or None,
            "how": None,
            #: The credit note's own number, or the bill it was raised
            #: against — both are on the paper. A historic row carries
            #: neither and states that rather than printing an id.
            "reference": note.get("credit_note_no") or note.get("invoice_no"),
            #: A credit note is not a payment and posts no receipt (`CPB-20`).
            "receipt_reference": None,
            "applied_to": [note["invoice_no"]] if note.get("invoice_no") else [],
            "returned_by_the_bank": False,
            "amount": _money(note["amount"]),
            "currency": note.get("currency"),
            "state": STATE_CREDITED,
            "money_type": MONEY_CREDIT,
            #: ⚠ **SHOWN — and it is the one reason on this screen that is.**
            #: `BR-CWP-050` asks for it; `BR-CWP-051` forbids the write-off's.
            #: Two different rules about two different rows.
            "reason": note.get("reason"),
        }
        for note in answer.get("credit_notes") or ()
    ]


def _write_off_rows(account_ids: list[str]) -> list[dict[str, Any]]:
    """`BR-CWP-051` — the amount, the date and the status, **and never the reason**.

    ⚠ **`reason` AND `note` ARE NOT SELECTED, NOT SERIALISED AND NOT NEAR THIS
    FUNCTION'S RETURN VALUE.** *Bankruptcy* and *deceased, no estate* are the
    utility's judgment about a person; the amount is the person's own money. A
    test asserts `customer_bankruptcy` appears nowhere in the response body.

    ⚠ **A REVERSAL IS ITS OWN ROW** (TC-6) — never a deletion of the first,
    which is hard rule 4 in the shape `write_offs` answers it: a self-FK,
    `uq_write_offs_reverses`, and both rows standing.

    ⚠ **THE AMOUNT IS THE MAGNITUDE THE APPROVER APPROVED**, positive by the
    table's own `ck_write_offs_amount_positive`; `status` says which way it
    went. That is the model's stated reading and nothing here inverts it.
    """
    from apps.payments import collections_models

    rows = collections_models.WriteOff.objects.filter(
        account_id__in=account_ids, status__in=WRITE_OFF_VISIBLE
    ).only(
        "id",
        "amount",
        "currency",
        "status",
        "approved_on",
        "requested_on",
        "reverses_write_off",
    )
    return [
        {
            "kind": MONEY_WRITE_OFF,
            "date": (row.approved_on or row.requested_on).isoformat(),
            "how": None,
            #: ⚠ **NO REFERENCE, AND THAT IS NOT AN OVERSIGHT.** `write_offs`
            #: mints no customer-facing number, and the only other candidate is
            #: the row's uuid — which rule 31 forbids outright. A stated
            #: absence beats an id.
            "reference": None,
            #: Nor is a write-off (`CPB-20`).
            "receipt_reference": None,
            "applied_to": [],
            "returned_by_the_bank": False,
            "amount": _money(row.amount),
            "currency": row.currency,
            "state": (
                STATE_WRITE_OFF_REVERSED
                if row.reverses_write_off_id is not None
                else STATE_WRITTEN_OFF
            ),
            "money_type": MONEY_WRITE_OFF,
        }
        for row in rows
    ]


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave M · `CWP-042` and `CWP-043` — payment plans (US-CWP-051/052)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **NOT ONE LINE OF INSTALMENT ARITHMETIC LIVES IN THIS MODULE, AND THAT IS
# THE WHOLE POINT OF THE SECTION.** `US-CWP-051` §7: *"Existing, tested
# instalment arithmetic — this screen **previews** it and must not recompute it
# independently."* `12-reuse-map.md` names the read: `GET
# accounts/{id}/payment-plans/preview`, served by
# `apps.customers.payment_plan_service.preview`, which calls
# `apps.customers.payment_plan.build_schedule` — ❄️ **GT-47**, `BR-CUS-043`.
# So `plan_preview` below calls **the same function the clerk's S24 wizard
# calls**, and a clerk and a customer cannot be handed different instalments.
#
# **Worked, and it is the story's own figure:** `172.20 − 40.00 = 132.20`;
# `132.20 ÷ 6 = 22.0333…` → `22.03`; `22.03 × 5 = 110.15`; the final instalment
# is what is LEFT, `132.20 − 110.15 = ` **`22.05`**; Σ = `132.20` **exactly**.
#
# ⚠ **THE STORY'S PROSE SAYS *truncate* AND THE ENGINE ROUNDS HALF-UP.** On
# these figures they agree; on ❄️ GT-47's they do not (`36.2166…` is `36.22`
# half-up and `36.21` truncated, and `36.22` is the frozen figure). §7's
# sentence DESCRIBES the engine, it does not re-specify it — which is exactly
# why the same section forbids recomputing. Decision log, 2026-09-04.
#
# ⚠ **WHAT THE PORTAL DOES ADD IS AN INPUT CONSTRAINT, NEVER A FIGURE.** The
# blueprint's *"between two and twelve months"* (`P28`, `US-CWP-051` TC-4) has
# no home in the engine — `validate_proposal` refuses only `installments < 1` —
# so thirteen months is refused HERE, by name, and never reaches the engine.

#: Blueprint `P28` · `US-CWP-051` TC-4. The portal's own range, refused at the
#: edge because the engine does not hold it.
PLAN_MIN_MONTHS = 2
PLAN_MAX_MONTHS = 12

#: Where an instalment stands, as a KEY — eleven catalogues write the words
#: (B14 rule 35). ⚠ **DERIVED FROM THE ENGINE'S OWN FACTS**, never stored:
#: `paid_posted_on` and `on_time` come straight out of
#: `payment_plans_for_account`, which reads `BR-PAY-021` (*on time* is
#: `posted_at ≤ due_date`, whatever the clearing date).
INSTALMENT_PAID_ON_TIME = "paid_on_time"
INSTALMENT_PAID_LATE = "paid_late"
#: The EARLIEST unpaid instalment still to fall due. It carries `days_until`,
#: which is what makes the fixture's *due in 9 days* on 5 December a fact rather
#: than a sentence assembled on the server (B14 rule 35 again).
INSTALMENT_DUE_NEXT = "due_next"
INSTALMENT_TO_COME = "to_come"
#: Past its date and unmet. ⚠ **IT ENDS NOTHING** — PO 2026-08-11, *"nodrop we
#: chase for payments until write off"*. See `OQ-CWP-1720` (this cited
#: `OQ-CWP-1569` until 2026-09-05 — that id is the bill-comparison question,
#: `DEF-CWP-3800`).
INSTALMENT_MISSED = "missed"


def _carries_rounding(installments: list[dict[str, Any]], row: dict[str, Any]) -> bool:
    """Is THIS the row the remainder landed on — or merely the last one?

    `DEF-CWP-4140`. `build_schedule` marks the final instalment `final=True`
    unconditionally, because that is what *final* means. The remainder is a
    different fact: it exists only when `(total − down) ÷ n` does not divide
    exactly, and then it shows up as a final amount unequal to the base one.
    A one-instalment plan has no base row to differ from, so nothing carries a
    remainder there either.
    """
    if not row.get("final"):
        return False
    if len(installments) < 2:
        return False
    return _money(row["amount"]) != _money(installments[0]["amount"])


def plan_preview(
    account_id: Any,
    *,
    months: int,
    first_due_on: date,
    down_payment: Any,
    as_of: date,
) -> dict[str, Any]:
    """`CWP-042` — what the plan WOULD be. **Writes nothing.**

    ⚠ **THE BALANCE IS THE LEDGER'S AND IS NEVER TAKEN FROM THE BODY**
    (`US-CUS-018` TC-6's reasoning, which applies twice over to a customer): a
    caller that named the amount to spread could widen the ceiling their own
    proposal is checked against. `wizard_context` reads it, and where the books
    cannot be asked it answers `null` with its reason and this refuses rather
    than opening on `0.00` — DEF-127, *a zero that means "I don't know"*.

    ⚠ **`suspend_late_fees` IS READ FROM `wizard_context()["defaults"]`, NEVER
    ASSUMED** (`BR-CWP-064`). It is a per-PLAN election a clerk makes, and the
    product's default is **off**, so today the consequence box says *fees still
    apply* — which is `US-CWP-051` TC-11, the case the blueprint singles out as
    *worse than a blank space*. A screen that hard-coded *late fees stop* would
    be promising something only a clerk can grant.
    """
    from apps.customers import payment_plan, payment_plan_service
    from apps.customers import selectors as customers_selectors
    from core import errors

    if not PLAN_MIN_MONTHS <= int(months) <= PLAN_MAX_MONTHS:
        # ⚠ The refusal NAMES THE RANGE (TC-4). A bare *"not allowed"* leaves a
        # customer guessing at a number the screen already knows.
        raise errors.ValidationError(
            errors.VAL_RANGE,
            br_ref="BR-CWP-062",
            message_key="portal.plan.termOutOfRange",
            params={"min": PLAN_MIN_MONTHS, "max": PLAN_MAX_MONTHS},
        )

    account = customers_selectors.account_detail(account_id)
    context = payment_plan_service.wizard_context(account=account, as_of=as_of)
    if not context["can_propose"]:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CWP-062",
            message_key="portal.plan.cannotAsk",
            params={"detail": context["cannot_propose_reason"] or ""},
        )

    balance = Decimal(str(context["balance"]))
    down = Decimal(str(down_payment or "0"))
    try:
        preview = payment_plan_service.preview(
            # The WHOLE balance is what a customer spreads; a clerk may spread
            # part of it, and that choice is not offered here.
            balance_to_spread=balance,
            account_balance=balance,
            down_payment=down,
            installments=int(months),
            cadence=payment_plan.CADENCE_MONTHLY,
            first_due_date=first_due_on,
            as_of=as_of,
            currency=str(context["currency"] or ""),
            live_plan_exists=context["live_plan"] is not None,
            suspend_late_fees=bool(context["defaults"]["suspend_late_fees"]),
            suspend_disconnect=bool(context["defaults"]["suspend_disconnect"]),
        )
    except payment_plan.PaymentPlanRuleError as refusal:
        # The engine's own refusals — a down payment that settles the whole
        # balance (TC-6), one larger than it (TC-5), a first date already past.
        # Carried through as the SERVER's sentence rather than re-worded here,
        # so the customer and the clerk are refused for the same stated reason.
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CUS-043",
            message_key="portal.plan.refused",
            params={"detail": str(refusal)},
        ) from refusal

    schedule = preview.as_dict()
    return {
        #: ⚠ **WHICH ACCOUNT THIS PLAN IS FOR, BY ITS NUMBER AND ITS ADDRESS.**
        #: A landlord holding four accounts is the reason: a plan screen that
        #: named neither would ask somebody to spread `$172.20` without saying
        #: whose `$172.20`. Both are human references (B14 rule 31), and the
        #: address is DERIVED BY WALKING TO THE PREMISES — `account_detail`'s own
        #: `premise` cell — never stored on the account (hard rule 8).
        "account_no": account.get("account_no"),
        "service_address": account.get("premise"),
        "balance": _money(balance),
        "down_payment": _money(schedule["down_payment"]),
        #: What the instalments cover — balance less what is paid up front.
        "spread": _money(schedule["spread"]),
        "currency": schedule["currency"],
        "cadence": schedule["cadence"],
        "term_months": schedule["installment_count"],
        "first_due_on": first_due_on.isoformat(),
        "instalments": [
            {
                "seq": row["seq"],
                "due_on": row["due_date"],
                "amount": _money(row["amount"]),
                #: ⚠ **THE ROUNDING ROW — AND *ROUNDING* IS A DIFFERENT FACT
                #: FROM *LAST* (`DEF-CWP-4140`).** This read `bool(row["final"])`
                #: until 2026-09-06, and `build_schedule` sets `final` on the
                #: last instalment whether or not a remainder exists. So a
                #: spread that divides exactly — `$120.00` over six is six of
                #: `$20.00`, which the wave M demo script names in as many
                #: words — flagged its sixth row anyway and `CWP-042` printed
                #: *"the last instalment carries the rounding"* over six
                #: identical figures. `US-CWP-051` §1 asks for *"the uneven last
                #: instalment"* to be shown; when it is not uneven there is
                #: nothing to show.
                "carries_the_rounding": _carries_rounding(schedule["installments"], row),
            }
            for row in schedule["installments"]
        ],
        #: The count the CONSEQUENCE BOX must use — `US-CWP-051` TC-3 asserts the
        #: copy says **five** then one, not six then one, and the blueprint's own
        #: figure was wrong about exactly this. Served so the screen cannot
        #: compute a different one.
        "base_instalment_count": max(schedule["installment_count"] - 1, 0),
        "base_amount": _money(schedule["installments"][0]["amount"]),
        "final_amount": _money(schedule["installments"][-1]["amount"]),
        #: `BR-CWP-064` — per plan, read, never assumed.
        "suspend_late_fees": schedule["suspend_late_fees"],
        "suspend_disconnect": schedule["suspend_disconnect"],
        #: `BR-CWP-063` / `BR-BIL-073`, carried on the payload rather than left
        #: for a screen to remember — believing the plan replaces the bill is
        #: DEF-061.
        "current_bill_still_due": True,
        #: ⚠ **NOTHING WAS WRITTEN.** The staff preview says so on the wire and
        #: this says it the same way, so a caller reading the body can tell a
        #: preview from a commit without knowing which route it called.
        "writes": [],
    }


def current_plans(account_id: Any, *, as_of: date) -> dict[str, Any]:
    """`CWP-043` — the WHOLE plan, closed ones included.

    Composed from `apps.payments.plans.payment_plans_for_account`, the read
    `apps/customers/seams.payment_plans_for` already resolves for the staff
    wizard. Every money figure and every date below is that read's.

    ⚠ **A CLOSED PLAN STAYS VISIBLE** (`US-CWP-052` TC-8) — *"a finished plan
    disappears from the portal today. It must not."* Nothing is filtered by
    status here, and the row carries `closed_on`.

    ⚠ **WHICH PAYMENT PAID WHICH INSTALMENT REACHES NO SCREEN TODAY** (the
    story's §1, in those words), and the published read does not carry it — it
    serves `paid_posted_on` and `on_time` and stops there. So this seam reads
    the `PMT-` NUMBER off `PaymentPlanInstallment.paid_payment` in one extra
    query, the same posture `last_payment` above already takes. **A number, never
    an id** (B14 rule 31): without it a customer cannot match an instalment to a
    line on their bank statement, which is the entire reason this screen exists.

    ⚠ **THE CADENCE IS READ, NEVER ASSUMED MONTHLY** (TC-4) — it is a column and
    a plan may be weekly or fortnightly.
    """
    from apps.payments import collections_models
    from apps.payments import plans as payment_plans

    rows = payment_plans.payment_plans_for_account(account_id, as_of=as_of)
    if not rows:
        return {"plans": []}

    paid_by: dict[tuple[str, int], str | None] = {}
    for row in (
        collections_models.PaymentPlanInstallment.objects.filter(
            plan_id__in=[plan["id"] for plan in rows], paid_payment__isnull=False
        )
        .select_related("paid_payment")
        .only("plan_id", "seq", "paid_payment__payment_no")
    ):
        paid_by[(str(row.plan_id), row.seq)] = row.paid_payment.payment_no

    return {
        "plans": [
            {
                #: ⚠ **NO PLAN ID ON THE WIRE** (B14 rule 31, and eight
                #: characters of one is the same breach). A customer holds at
                #: most one live plan and a handful of closed ones; the screen
                #: keys on the date it started.
                "status": plan["status"],
                "live": plan["live"],
                "cadence": plan["cadence"],
                "currency": plan["currency"],
                "total": _money(plan["total_amount"]),
                #: ⚠ Shown, and not only at creation (TC-3) — otherwise the
                #: instalments look as though they came from nowhere.
                "down_payment": _money(plan["down_payment"]),
                "spread": _money(plan["spread"]),
                "paid_to_date": _money(plan["paid_to_date"]),
                "term_months": plan["installment_count"],
                "started_on": plan["signed_on"] or plan["agreement_sent_on"] or plan["proposed_on"],
                "closed_on": plan["closed_on"],
                #: `BR-CWP-064` — the per-plan elections, as the clerk left them.
                "suspend_late_fees": plan["suspend_late_fees"],
                "suspend_disconnect": plan["suspend_disconnect"],
                #: TC-10 — on the plan row, and reaching no screen until now.
                "autopay_enabled": plan["autopay_enabled"],
                "current_bill_still_due": True,
                "instalments": _instalment_views(plan, paid_by=paid_by, as_of=as_of),
                #: ⚠ **`US-CWP-052` §7's INVARIANT, SERVED SO A TEST CAN ASSERT
                #: IT:** down payment + Σ instalments must equal the arrears the
                #: plan was raised against — `40.00 + 5 × 22.03 + 22.05 =`
                #: **`172.20`**. A plan silently covering the wrong figure is the
                #: defect this catches.
                "instalments_total": _money(
                    sum((Decimal(row["amount"]) for row in plan["installments"]), ZERO)
                ),
                #: ⚠ **WHETHER THE SIGNED AGREEMENT CAN ACTUALLY BE HANDED
                #: OVER** (`CR-085` `CPB-14`). `CWP-043`'s *↓ Agreement* read
                #: *"Downloads arrive later this year"* — the same rotted
                #: `unwatched` hold `CPB-03` found on the OFFER screen, over a
                #: document the store may well be holding. It is a FACT about
                #: this plan, not a promise about the future, so the control
                #: cannot rot: the day a copy is filed the button is live in the
                #: same render, and the day there is none it says so.
                #: ⚠ **NO PLAN ID TRAVELS WITH IT** (B14 rule 31). The screen
                #: asks for *this account's live plan's agreement* by address,
                #: because a customer holds at most one live plan.
                "agreement_available": _agreement_kept(plan["id"]),
            }
            for plan in rows
        ]
    }


def live_plan_id(account_id: Any, *, as_of: date) -> Any | None:
    """The id of this account's LIVE plan, for a caller that must serve its
    document — or `None`.

    ⚠ **IT NEVER LEAVES THE SERVER** (B14 rule 31). `current_plans` above
    deliberately publishes no plan id, and this exists so the agreement route
    can resolve the plan the screen is showing without one travelling to the
    browser. The newest live plan wins; two live plans on one account is a data
    fault, not a shape this has to carry.
    """
    from apps.payments import plans as payment_plans

    rows = [
        plan
        for plan in payment_plans.payment_plans_for_account(account_id, as_of=as_of)
        if plan.get("live")
    ]
    if not rows:
        return None
    return rows[0]["id"]


def _agreement_kept(plan_id: Any) -> bool:
    """Is there a frozen agreement for this plan that we could serve?

    ⚠ **IT ASKS THE SERVING PATH'S OWN QUESTION** (`CR-085` `CPB-14`/`CPB-19`).
    A screen flag decided any other way is a promise the file route can refuse,
    which is the disagreement this whole wave exists to remove — measured twice
    in one afternoon on the bill and on the receipt.

    A handful of plans per account, so it is a handful of lookups on a screen
    that draws one plan.
    """
    from apps.portal.seams import notifications_seam

    verdict, payload, _ctype, _name = notifications_seam.stored_document_service(
        source_type="plan", source_id=plan_id
    )
    return verdict == notifications_seam.DOCUMENT_OK and payload is not None


def _instalment_views(
    plan: dict[str, Any], *, paid_by: dict[tuple[str, int], str | None], as_of: date
) -> list[dict[str, Any]]:
    """Each instalment, with where it stands and what cleared it.

    ⚠ **ONLY THE EARLIEST UNPAID INSTALMENT STILL TO FALL DUE IS *due next*.**
    The rest are *to come*. That is what makes the fixture read *4 of 6 · 14 Dec
    · DUE IN 9 DAYS* on 5 December while 14 January and 14 February read *TO
    COME* — one payment is being asked for, and a screen that said *due in 40
    days* four times would be asking for four.

    ⚠ **A MISSED INSTALMENT ENDS NOTHING** (PO 2026-08-11, *"nodrop we chase for
    payments until write off"*). It is a FACT on the row and no status anywhere
    moves because of it. Whether the blueprint's *"miss two and the plan ends"*
    survives that ruling is `OQ-CWP-1720` and is OPEN — **until it is answered no
    screen, document or docstring here may say a plan ends on a missed
    instalment.**
    """
    rows = plan.get("installments") or ()
    due_next_seq: int | None = None
    for row in rows:
        if row["paid_posted_on"] is None and date.fromisoformat(row["due_date"]) >= as_of:
            due_next_seq = row["seq"]
            break

    views: list[dict[str, Any]] = []
    for row in rows:
        due_on = date.fromisoformat(row["due_date"])
        if row["paid_posted_on"] is not None:
            state = INSTALMENT_PAID_ON_TIME if row["on_time"] else INSTALMENT_PAID_LATE
        elif due_on < as_of:
            state = INSTALMENT_MISSED
        elif row["seq"] == due_next_seq:
            state = INSTALMENT_DUE_NEXT
        else:
            state = INSTALMENT_TO_COME
        views.append(
            {
                "seq": row["seq"],
                "due_on": row["due_date"],
                "amount": _money(row["amount"]),
                "currency": row["currency"],
                "state": state,
                #: A FACT, so eleven catalogues can write *due in 9 days* in
                #: their own words (B14 rule 35). `None` on every other state.
                "days_until": (due_on - as_of).days if state == INSTALMENT_DUE_NEXT else None,
                "paid_on": row["paid_posted_on"],
                #: ⚠ **THE `PMT-` NUMBER — TC-2.** Without it a customer cannot
                #: match an instalment to their bank statement, which the story
                #: names as the reason a plan cannot be reconciled today.
                "paid_reference": paid_by.get((str(plan["id"]), row["seq"])),
                #: The row that carries the remainder — `BR-CWP-062`. Derived
                #: here because the STORED schedule has no `final` column, and
                #: derived from the AMOUNT rather than from the position
                #: (`DEF-CWP-4140`): being last is not the same fact as
                #: carrying a remainder, and a plan whose spread divided
                #: exactly has no row that carries one.
                "carries_the_rounding": (
                    row["seq"] == plan["installment_count"]
                    and plan["installment_count"] > 1
                    and _money(row["amount"]) != _money(rows[0]["amount"])
                ),
            }
        )
    return views


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave L1 · `CWP-045` and `CWP-057` — money coming BACK, and the
# write-off on the ladder (US-CWP-056 · US-CWP-057)
# ═══════════════════════════════════════════════════════════════════════════


#: The refund lifecycle, in `payments`' own spelling. Re-exported so the portal
#: and the screen name one set of five words; `models.REFUND_STATUSES` is the
#: closed set and nothing here adds a sixth.
REFUND_STEPS: tuple[str, ...] = ("requested", "approved", "issued", "cleared")


def refunds_for(account_id: Any) -> list[dict[str, Any]]:
    """`CWP-045`'s left half — every refund on THIS account, **voided included**.

    ⚠ **TENANT AND ACCOUNT ARE BOTH IN THE QUERY** (`BR-CWP-010`, `G96`), and
    `refunds.account_id` is `NOT NULL` since `payments/0018` — CR-059 CS-7, the
    PO's ruling of 2026-09-01 — so the account is the row's own column and never
    a walk through the payment it came from. A refund built from several
    payments carries `payment_id: None` and still has an address.

    ⚠ **A VOIDED REFUND IS SHOWN AS VOIDED AND NOT REMOVED** (`US-CWP-056`
    TC-4). A customer who was told money was coming and then sees the row gone
    has no way to ask what happened to it; the row with its date is the answer.

    ⚠ **THE SERIALISATION IS `payments`' OWN `refund_row` AND THE FIVE
    TIMESTAMPS COME OFF IT UNCHANGED.** A second money serialisation is
    `DEF-014`'s exact shape. What is dropped on the way to a customer is the
    ids, the two journal-entry ids and `void_reason` — `void_reason` is the
    utility's judgment written for the utility, the same distinction
    `BR-CWP-051` draws on a write-off.

    ⚠ **AND NOTHING HERE TAKES AN ABSOLUTE VALUE.** `refunds.amount` is stored
    positive (money going OUT is the row's whole meaning) and it leaves
    positive; the sign the server sent is the sign the screen renders.
    """
    from apps.payments import refunds as payments_refunds
    from apps.payments import selectors as payments_selectors

    rows = payments_models.Refund.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), account_id=account_id
    ).order_by("-requested_at", "-created_at", "-id")
    #: ⚠ **THE ADDRESS IS READ ONCE FOR THE WHOLE LIST, NOT PER REFUND.** It is
    #: the same envelope for every cheque on one account, and `contact_details`
    #: is a two-table read.
    posted_to = _mailing_address_for(account_id)
    out: list[dict[str, Any]] = []
    for row in rows:
        view = payments_selectors.refund_row(row)
        out.append(
            {
                "amount": view["amount"],
                "currency": view["currency"],
                "status": view["status"],
                #: `BR-CWP-060` — *the refund names the method it is going back
                #: to*. `check` or `ach`, or `None` where none is recorded yet.
                "method": view["method"],
                #: The cheque number, which is on the paper the customer will
                #: receive. Not an id (B14 rule 31) — `refunds.reference` is the
                #: clerk's own typed reference.
                "reference": view["reference"],
                "reason": view["reason"],
                "requested_at": view["requested_at"],
                "approved_at": view["approved_at"],
                "issued_at": view["issued_at"],
                "cleared_at": view["cleared_at"],
                "voided_at": view["voided_at"],
                #: ⚠ **DERIVED FROM THE TIMESTAMPS, NEVER A SECOND STATUS.** A
                #: refund's status IS its furthest step; a boolean per step
                #: computed anywhere else would be a second lifecycle.
                "steps": [
                    {"step": step, "on": view[f"{stamp}"]}
                    for step, stamp in (
                        ("requested", "requested_at"),
                        ("approved", "approved_at"),
                        ("issued", "issued_at"),
                        ("cleared", "cleared_at"),
                    )
                ],
                #: ── CR-068 `CWP-045` · WHERE IT IS GOING BACK TO (US-CWP-049)
                #: `BR-CWP-060`, and `payments` owns the whole judgment —
                #: `refunds.destination_of` decides it and this composes the ONE
                #: fact payments does not own: the ADDRESS a cheque goes to,
                #: which is `customers.addresses kind='mailing'` (CLAUDE.md hard
                #: rule 8's first exception — where the BILL goes, which for a
                #: landlord is another building).
                "destination": {
                    **payments_refunds.destination_of(row),
                    "posted_to": (
                        posted_to if view["method"] == payments_models.REFUND_METHOD_CHECK else None
                    ),
                },
            }
        )
    return out


def _mailing_address_for(account_id: Any) -> str | None:
    """Where a cheque goes — one line, as a person would write it on an envelope.

    ⚠ **`customers_seam` IS ASKED FOR IT RATHER THAN THE TABLE BEING READ HERE**
    (`BR-CWP-012` — read through the owning module, no second copy). It is also
    the only address a refund may name: `premises` is where SERVICE is taken and
    a cheque does not go there when the customer has moved out, which is the
    whole reason `kind='mailing'` survived the retirement of `kind='service'`.
    """
    from apps.portal.seams import customers_seam

    details = customers_seam.contact_details(core_tenancy.current_tenant_id(), [str(account_id)])
    postal = details.get("postal") or {}
    parts = [
        postal.get("line1"),
        postal.get("line2"),
        postal.get("city"),
        " ".join(part for part in (postal.get("state"), postal.get("postal_code")) if part) or None,
    ]
    line = ", ".join(part for part in parts if part)
    return line or None


def write_offs_for(account_ids: list[Any]) -> list[dict[str, Any]]:
    """`BR-CWP-051` on `CWP-057` — the amount and the date, and NEVER the reason.

    A thin public door onto `_write_off_rows`, which `CWP-041` already serves
    from. `US-CWP-057` TC-9 asserts the amount and the date show and that no
    reason code is anywhere in the response; that guarantee lives in the one
    function rather than being re-made here.
    """
    return _write_off_rows([str(one) for one in account_ids])


# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave R (the ending lane) — ONE PAYMENT BY THE REFERENCE SOMEBODY KEPT
#
# `US-CWP-010` TC-7 and `US-CWP-005` TC-3. This is the read the `TRACKABLE_
# SERIES` comment in `apps/portal/selectors.py` said wave P owed the tracker,
# written out here rather than left standing as a sentence.
# ═══════════════════════════════════════════════════════════════════════════


def payment_by_number(tenant_id: Any, *, number: Any) -> dict[str, Any] | None:
    """One payment by the reference a person is holding, or `None`.

    ⚠ **THIS FUNCTION ON ITS OWN IS A REFERENCE ORACLE AND MUST NEVER BE CALLED
    FROM ANYWHERE BUT `selectors.track`**, which matches `BR-CWP-025`'s second
    fact before it discloses anything. `billing_seam.bill_by_number` carries the
    identical warning for the identical reason: a guest has no session and no
    account set, so the second fact is the whole guard.

    ⚠ **WHAT COMES BACK IS NOT A GUEST RESPONSE.** `account_id` is here because
    the caller needs it to walk to the premises for the postcode — it is the
    INPUT to the second-fact check and it never reaches a payload.
    `guest_fields.NEVER_ON_A_GUEST_RESPONSE` names `account_id` by name, and
    `selectors.payment_progress_view` is where the narrowing happens.

    ⚠ **THE TENANT IS IN THE QUERY** (`BR-CWP-010`, `G96`, `DEF-CWP-3775`), as
    this function's own argument rather than `app.tenant_id` alone: the suite
    runs on SQLite, which has no row-level security, so a read that left the
    tenant to the database would have no test that could ever see it go wrong
    (hard-won law 14 in its second costume). `US-CWP-005` TC-5 — `PAY-26-08841`
    submitted on `/oak-ridge` — is what asserts it.

    ⚠ **`type = payment` AND NOT THE OTHER TWO.** `payments` holds credits and
    adjustments in the same table under the same numbering, and nothing in this
    product ever hands a stranger the number of one. Restricting here keeps the
    boundary NARROWER than the story asks and never wider, which is the posture
    `TRACKABLE_SERIES` took when it refused the series outright.

    **BOTH DATES TRAVEL** (`BR-PAY-021` — *"POSTING date ≠ CLEARING date —
    always both"*). `posted_at` is when the record entered the system and
    `cleared_at` is when the money actually arrived; the second is NULL while a
    payment is still processing, which is a real answer rather than a gap.
    """
    typed = str(number or "").strip()
    if not typed:
        return None
    if tenant_id is None:
        # Hard rule 1 — never touch a tenant table without a tenant.
        raise RuntimeError("payment_by_number called with no tenant (hard rule 1)")
    row = (
        payments_models.Payment.objects.filter(
            tenant_id=tenant_id,  # G96 — in the query, never left to RLS alone
            payment_no=typed,
            type=payments_models.PAYMENT_TYPE_PAYMENT,
        )
        .only("id", "account_id", "payment_no", "status", "posted_at", "cleared_at")
        .first()
    )
    if row is None:
        return None
    return {
        "account_id": row.account_id,
        "reference": row.payment_no,
        "status": row.status,
        "posted_at": row.posted_at,
        "cleared_at": row.cleared_at,
    }


# ═══════════════════════════════════════════════════════════════════════════
# CR-191-BRC10 (PO 2026-10-23) — THE APPLICATION FEE, PAID ONLINE AT SUBMISSION
#
# ⚠ **THE RAILS ARE REACHED, NEVER REBUILT.** Both functions resolve
# `apps.payments.gateway` through `sys.modules` at the call, for the reason
# `guest_api._rails` records (a stand-in installed by a test is otherwise
# silently bypassed), and call the gateway's own `charge_guest_fee` — which is
# `active_provider` + `held_reason` + `charge()`, the guest bill path minus its
# account-settlement step. Nothing here writes a row.
# ═══════════════════════════════════════════════════════════════════════════


def _gateway() -> Any:
    from importlib import import_module

    return import_module("apps.payments.gateway")


def card_payments_available(tenant_id: Any) -> bool:
    """Can this utility take a card at all? (`BR-CWP-056` — the last step holds
    its Pay button WITH its reason rather than offering a commit that can only
    be refused.)"""
    return bool(_gateway().card_payments_available(tenant_id))


def charge_application_fee(
    tenant_id: Any,
    *,
    amount: Any,
    currency: str | None,
    instrument: dict[str, Any],
    idempotency_key: str,
) -> dict[str, Any]:
    """One card debit for an application fee; raises `GuestChargeRefused` on
    any outcome but an approval, and writes nothing in either case."""
    return _gateway().charge_guest_fee(
        tenant_id,
        amount=amount,
        currency=currency,
        instrument=instrument,
        idempotency_key=idempotency_key,
    )


def fee_not_recorded(key: str | None, failure: BaseException) -> Exception:
    """⛔ The card was approved and the application could not be written.

    The gateway's own `NOT_RECORDED` refusal, so the edge answers it through
    `_refusal_for` with the quick-pay sentence *"We could not record that
    payment."* — never a reference. The same key on a retry is one debit at the
    provider (decision log 2026-10-23, "how it is built" 3–4)."""
    rails = _gateway()
    return rails.GuestChargeRefused(
        "the provider approved the application fee and the application could not be "
        f"recorded: {type(failure).__name__}.",
        outcome=rails.NOT_RECORDED,
        key=key,
        br_ref="BR-PAY-003",
    )


def charge_was_declined(failure: BaseException) -> bool:
    """`DEF-PAY-10554` — did the provider definitely say NO? True only for the
    gateway's `DECLINED`; a silence (`NO_ANSWER`) or a held card is not a
    decline, because after a silence the money may have moved and the same key
    must be presented again."""
    rails = _gateway()
    return isinstance(failure, rails.GuestChargeRefused) and failure.outcome == rails.DECLINED
