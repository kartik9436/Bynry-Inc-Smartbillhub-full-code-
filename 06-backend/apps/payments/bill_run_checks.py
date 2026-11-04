# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-037 TC-10 (bulk run · Check — Payments & balances)
# Rules:    BR-BIL-1053 (payment checks at Check, read through the payments
#           seam) · BR-PAY-021 (posted_at is the date billing judges by) ·
#           BR-PAY-016 (an instalment is met by a payment posted by its due
#           date) · BR-CUS-059 / BR-PAY-013 (autopay election and its sanction)
# Plan:     15-bulk-bill-run-build-plan.md B12 · DEF-BIL-8211
# Tests:    06-backend/tests/test_bbr_check_engine.py (payment cases) ·
#           06-backend/tests/test_bbr_payment_checks.py (DEF-BIL-8240)
# ───────────────────────────────────────────────────────
"""What the payments module can tell a bill run's CHECK about an account.

READ-ONLY, AND OWNED HERE. Billing may not read `payments` tables (B1, and the
cross-module-write gate's reading twin), so the facts the Check's *Payments &
balances* category needs are answered by this module, about its own rows, in
one call per CHUNK of accounts rather than one per account per fact — a
40,000-account run (the top of T5) asks four questions per 500 accounts, not
360,000.

WHAT IT ANSWERS, AND WHAT IT DELIBERATELY DOES NOT
--------------------------------------------------
Every fact below is a row this module already stores. Where a tag the PO ruled
(BR-BIL-1053) has NO stored fact behind it today, it is listed in
`UNAVAILABLE` with the reason and is **never raised** — a count shown against
a fact nobody records would be a guess on a screen about money (plan, *Open*:
*"where a fact has no source today it is built as a deliberate absence and
filed, not guessed"*).

  * `paid_after_cutoff` — a payment POSTED after the period ended and on or
    before the bill date (BR-PAY-021: `posted_at` is billing's date). The
    story's own case: $120.00 posted Oct 1 on a Sep 1–30 period billed Oct 1.
  * `plan_instalment_due` — the account's live payment plan has an instalment
    due on or before this bill's due date that no payment has met.
  * `in_collections` — the account stands on the collection ladder (a tier has
    been sent).
  * `autopay_card_expiring` — the account is autopay-enrolled and not under the
    cash-only sanction, and every card its customer holds for autopay expires
    before this bill's due date.

  * `unmatched_payment` — a payment the utility RECEIVED that could not be
    matched to an account, tied to this account by the payer's details or by a
    clerk, and not yet posted (DEF-BIL-8240; PO ruling 2026-09-30, option B:
    *"b"*). **Never a credit balance.** Read from `payment_import_rows`, the
    one place received-but-unassigned money is stored. Worked: a $120.00 bank
    transfer with no account number whose payer name ties it to Maria's
    account → tagged; Maria's $80.00 June credit → NOT tagged.

  ABSENT (see `UNAVAILABLE`): `bounced_payment_not_reversed`, `credit_covers_bill`.
  `level_pay_off_track` is BILLING's fact (its own `account_budget_status` and
  issued bills, BR-BIL-017) and is read by `apps.billing.level_pay_check`, never
  from here. `deposit_not_paid` is a CUSTOMERS fact (`accounts.deposit_assessed`
  vs `deposit_on_file`) and is read by billing from the account row it already
  holds, never from here.

Nothing here writes, and nothing here decides anything: each fact is handed to
the Check as a code with its figures, and the Check's taxonomy says whether it
is a decision or a warning.
"""

from __future__ import annotations

import calendar
from collections.abc import Iterable
from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import Any


from apps.payments import models
from apps.payments.collections_models import (
    LIVE_PLAN_STATUSES,
    AccountCollectionState,
    PaymentPlan,
    PaymentPlanInstallment,
)
from core import tenancy as core_tenancy

FACT_PAID_AFTER_CUTOFF = "paid_after_cutoff"
FACT_INSTALMENT_DUE = "plan_instalment_due"
FACT_IN_COLLECTIONS = "in_collections"
FACT_CARD_EXPIRING = "autopay_card_expiring"
FACT_UNMATCHED = "unmatched_payment"

#: The ruled tags with no stored fact behind them today, and why. Served on the
#: Check's findings so the screen can say the tag is not checked rather than
#: showing a zero that reads as *checked and clear*.
UNAVAILABLE: tuple[dict[str, str], ...] = (
    {
        # ⚠ SEARCHED FOR AND NOT FOUND (DEF-BIL-8240, 2026-09-30). The ruling
        # asked for *"a bank return advice recorded against the account's
        # payment with no reversal yet"*; every place a return reaches this
        # product was read:
        #   * `reversal.reverse_payment` — a clerk's or a bank's return IS the
        #     reversing row: the advice reference is that row's `webhook_key`
        #     (`_by_advice`), so an advice and its reversal are ONE write and
        #     neither exists without the other;
        #   * `runbook_reads.returned_items_landed` — *"there is no such
        #     feed"*: no connection declares a returns operation, and
        #     `BankLine` holds no return code and no link to a payment;
        #   * `bank_rec_resolutions.reason_code = 'returned_item'` hangs off a
        #     deposit BATCH or a bank LINE (`ck_bank_rec_resolutions_one_parent`),
        #     never off a payment or an account;
        #   * the integrations door lands a kiosk `…|return` envelope RAW in
        #     `payment_webhook_events` and stops (`BR-INT-058`). Which of our
        #     payments it names is Runbooks' apply half, which is not built
        #     (`integrations.inbound.runbooks_apply` returns None), and reading
        #     a partner's own field names here would be that ETL (`BR-INT-054`).
        #     The door never records the kiosk's payment either, so there is no
        #     payment of ours for the return to name.
        # So the tag stays absent rather than guessed; DEF-BIL-8500 holds it.
        "code": "bounced_payment_not_reversed",
        "reason": "no_return_advice_without_reversal",
        "detail": (
            "a bank return reaches this product only as the reversal a clerk or the bank "
            "records, in one write; a return advice held against one of our payments with "
            "no reversal yet is not stored anywhere"
        ),
    },
    {
        "code": "credit_covers_bill",
        "reason": "bill_not_calculated_at_check",
        "detail": (
            "whether a credit covers the bill needs the bill's amount, which does not "
            "exist until Calculate; it belongs to Sign off, not to Check"
        ),
    },
)

#: Payment statuses whose money never arrived or was taken back. A payment in
#: one of these is not a payment the customer made for this bill.
_NOT_MONEY = (models.PAYMENT_FAILED, models.PAYMENT_CANCELLED, models.PAYMENT_REVERSED)


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _card_expires_before(month: int | None, year: int | None, day: date) -> bool:
    """A card is good to the LAST day of its expiry month."""
    if not month or not year:
        return False
    last = calendar.monthrange(int(year), int(month))[1]
    return date(int(year), int(month), last) < day


#: One fact the Check reads: `(account_id, code, params)`.
Fact = tuple[str, str, dict[str, Any]]


# ── ONE READER PER FACT (DEF-BIL-8286, 2026-09-30) ──────────────────────────
# `payment_facts_for_accounts` was one 135-line function, so the one fact the
# rest of the run needs AGAIN — the payments posted after the cut-off, which
# *"Apply to this bill"* counts on the bill and Sign off counts under
# *payments applied* — could only be had by asking all four. Each reader below
# is one query (two for the cards) over the chunk, owns its own dates, and is
# callable on its own; `FACT_READERS` runs them in the order the old body did.


def paid_after_cutoff(
    account_ids: Iterable[Any], *, period_end: date, bill_date: date | None
) -> list[Fact]:
    """Payments POSTED after the period ended and on or before the bill date
    (BR-PAY-021: `posted_at` is billing's date). The story's own case: $120.00
    posted Oct 1 on a Sep 1–30 period billed Oct 1. None bill date → none."""
    ids = [str(one) for one in account_ids if one]
    if not ids or bill_date is None or bill_date <= period_end:
        return []
    rows = (
        models.Payment.objects.filter(
            tenant_id=_tenant_id(),
            account_id__in=ids,
            type=models.PAYMENT_TYPE_PAYMENT,
            reverses_payment__isnull=True,
            posted_at__date__gt=period_end,
            posted_at__date__lte=bill_date,
        )
        .exclude(status__in=_NOT_MONEY)
        .order_by("posted_at", "id")
        .values("id", "account_id", "payment_no", "amount", "currency", "posted_at")
    )
    return [
        (
            str(row["account_id"]),
            FACT_PAID_AFTER_CUTOFF,
            {
                "payment_no": row["payment_no"],
                "amount": str(row["amount"]),
                "currency": row["currency"],
                "posted_on": row["posted_at"].date().isoformat(),
            },
        )
        for row in rows
    ]


def instalments_due(account_ids: Iterable[Any], *, due_date: date | None) -> list[Fact]:
    """The account's live payment plan has an instalment due on or before this
    bill's due date that no payment has met (BR-PAY-016). One per account —
    the earliest. `account_ids` may be a queryset of ids, read as a subquery —
    Sign off asks this for a whole bill run (`DEF-BIL-8696`)."""
    if due_date is None:
        return []
    ids: Any = (
        account_ids if hasattr(account_ids, "query") else [str(one) for one in account_ids if one]
    )
    if not hasattr(ids, "query") and not ids:
        return []
    tenant_id = _tenant_id()
    live = PaymentPlan.objects.filter(
        tenant_id=tenant_id, account_id__in=ids, status__in=LIVE_PLAN_STATUSES
    ).values_list("id", "account_id")
    account_by_plan = {str(plan_id): str(account_id) for plan_id, account_id in live}
    if not account_by_plan:
        return []
    due = (
        PaymentPlanInstallment.objects.filter(
            tenant_id=tenant_id,
            plan_id__in=list(account_by_plan),
            due_date__lte=due_date,
            paid_posted_on__isnull=True,
        )
        .order_by("due_date", "seq")
        .values("plan_id", "seq", "due_date", "amount", "currency")
    )
    out: list[Fact] = []
    seen: set[str] = set()
    for row in due:
        account_id = account_by_plan[str(row["plan_id"])]
        if account_id in seen:
            continue
        seen.add(account_id)
        out.append(
            (
                account_id,
                FACT_INSTALMENT_DUE,
                {
                    "seq": row["seq"],
                    "due_on": row["due_date"].isoformat(),
                    "amount": str(row["amount"]),
                    "currency": row["currency"],
                },
            )
        )
    return out


def in_collections(account_ids: Iterable[Any]) -> list[Fact]:
    """The account stands on the collection ladder (a tier has been sent)."""
    ids = [str(one) for one in account_ids if one]
    if not ids:
        return []
    return [
        (str(account_id), FACT_IN_COLLECTIONS, {"tier": tier})
        for account_id, tier in AccountCollectionState.objects.filter(
            tenant_id=_tenant_id(), account_id__in=ids, tier__isnull=False
        )
        .exclude(tier="")
        .values_list("account_id", "tier")
    ]


def autopay_cards_expiring(account_ids: Iterable[Any], *, due_date: date | None) -> list[Fact]:
    """Autopay-enrolled (not under the cash-only sanction), and every card the
    customer holds for autopay expires before this bill's due date."""
    ids = [str(one) for one in account_ids if one]
    if not ids or due_date is None:
        return []
    accounts = _resolve("customers", "account_queryset")
    customer_for = _resolve("customers", "primary_customer_id_for_account")
    if accounts is None or customer_for is None:
        return []
    enrolled = [
        str(pk)
        for pk in accounts()
        .filter(pk__in=ids, autopay=True, cash_only_no_autopay=False)
        .values_list("pk", flat=True)
    ]
    customer_by_account = {account_id: customer_for(account_id) for account_id in enrolled}
    customers = {c for c in customer_by_account.values() if c}
    cards: dict[str, list[tuple[int | None, int | None, str]]] = {}
    if customers:
        for row in (
            models.StoredPaymentInstrument.objects.filter(
                tenant_id=_tenant_id(),
                customer_id__in=list(customers),
                kind=models.INSTRUMENT_CARD,
                deleted_at__isnull=True,
            )
            .exclude(status=models.INSTRUMENT_EXPIRED)
            .values("customer_id", "expires_month", "expires_year", "last_four", "used_for")
        ):
            if models.INSTRUMENT_USE_AUTOPAY not in (row["used_for"] or []):
                continue
            cards.setdefault(str(row["customer_id"]), []).append(
                (row["expires_month"], row["expires_year"], row["last_four"])
            )
    out: list[Fact] = []
    for account_id, customer_id in customer_by_account.items():
        held = cards.get(str(customer_id or ""), [])
        if held and all(_card_expires_before(m, y, due_date) for m, y, _ in held):
            month, year, last_four = held[0]
            out.append(
                (
                    account_id,
                    FACT_CARD_EXPIRING,
                    {
                        "last_four": last_four,
                        "expires": f"{int(month):02d}/{int(year)}",
                        "due_on": due_date.isoformat(),
                    },
                )
            )
    return out


def unmatched_payments(account_ids: Iterable[Any], *, period_end: date) -> list[Fact]:
    """WHAT *UNMATCHED PAYMENT* MEANS — THE ONE PLACE IT IS DEFINED (DEF-BIL-8240).

    **PO ruling 2026-09-30, option B, verbatim *"b"*** (decision log, the row
    *"UNMATCHED PAYMENT … MEANS A PAYMENT RECEIVED THAT COULD NOT BE MATCHED TO
    ANY ACCOUNT"*): money the utility RECEIVED that could not be matched to an
    account, linked to this account by the payer's details or by a clerk. It is
    **never a credit balance** — normal credit comes off the next bill and is
    no Check question. (Option A, *any credit held on the account*, was this
    lane's first build and is superseded; it lived in this same function.)

    **WHERE THAT MONEY IS STORED.** `payments.account_id` is NOT NULL, so no
    recorded payment is ever unassigned; received-but-unassigned money exists
    only BEFORE it becomes a payment, as a row of a remittance or lockbox file
    in `payment_import_rows` (CS-2: *"a row that cannot be matched to an account
    with certainty is left unmatched for a person"*). A row counts when:
      * it names an account — the payer's details suggested one
        (`name_amount`, left in `review`: *"A name is not an identifier"*), or a
        clerk placed it (`manual`, `assign_row_account`);
      * it has NOT become a payment (`payment_id` NULL) — once posted it is an
        ordinary payment on the account, allocated like any other;
      * its file was not discarded, and it carries a readable amount above 0.
    A row with NO account (nothing matched, or several candidates) names no
    account a Check row could carry, so it cannot reach this tag; it is the
    import screen's review queue, not a per-account fact.

    `period_end` is part of the reader's signature for the Check's window and
    is not used: an unposted receipt is unposted whenever it arrived.

    One fact per account: the total received, how many rows, and the oldest
    row's reference. One query per chunk. Tenant-scoped on `tenant_id`
    (CLAUDE.md rule 1), RLS FORCE the second guarantee.
    """
    ids = [str(one) for one in account_ids if one]
    if not ids:
        return []
    rows = (
        models.PaymentImportRow.objects.filter(
            tenant_id=_tenant_id(),
            account_id__in=ids,
            match_method__in=(models.MATCH_NAME_AMOUNT, models.MATCH_MANUAL),
            payment_id__isnull=True,
            amount__gt=0,
        )
        .exclude(batch__status=models.IMPORT_DISCARDED)
        .order_by("account_id", "paid_on", "row_no", "id")
        .values("account_id", "amount", "reference", "paid_on", "match_method")
    )
    held: dict[str, dict[str, Any]] = {}
    for row in rows:
        slot = held.setdefault(
            str(row["account_id"]),
            {
                "received": Decimal("0"),
                "receipts": 0,
                "reference": row["reference"],
                "received_on": row["paid_on"].isoformat() if row["paid_on"] else None,
                "linked_by": row["match_method"],
            },
        )
        slot["received"] += row["amount"]
        slot["receipts"] += 1
    return [
        (account_id, FACT_UNMATCHED, {**slot, "received": str(slot["received"])})
        for account_id, slot in held.items()
    ]


#: THE ORDER IS THE BEHAVIOUR: an account's facts are listed in this order,
#: the order the single function used to raise them in.
FACT_READERS: tuple[tuple[str, Any], ...] = (
    (
        FACT_PAID_AFTER_CUTOFF,
        lambda ids, w: paid_after_cutoff(ids, period_end=w["period_end"], bill_date=w["bill_date"]),
    ),
    (FACT_INSTALMENT_DUE, lambda ids, w: instalments_due(ids, due_date=w["due_date"])),
    (FACT_IN_COLLECTIONS, lambda ids, w: in_collections(ids)),
    (FACT_CARD_EXPIRING, lambda ids, w: autopay_cards_expiring(ids, due_date=w["due_date"])),
    (FACT_UNMATCHED, lambda ids, w: unmatched_payments(ids, period_end=w["period_end"])),
)


def payment_facts_for_accounts(
    account_ids: Iterable[Any],
    *,
    period_end: date,
    bill_date: date | None,
    due_date: date | None,
) -> dict[str, list[dict[str, Any]]]:
    """`{account_id: [ {code, params}, … ]}` for the accounts that HAVE a fact.

    An account with nothing to say is absent from the answer. Five queries per
    call whatever the number of accounts (more when an autopay account holds a
    card or a receipt is held), which is why the Check asks per chunk.

    `bill_date` / `due_date` are the RUN's (the typed bill date and the due
    date it implies); None skips the facts that need them rather than guessing
    a date (BR-TEN-043 — there is no clock here).
    """
    ids = [str(one) for one in account_ids if one]
    out: dict[str, list[dict[str, Any]]] = {}
    if not ids:
        return out
    window = {"period_end": period_end, "bill_date": bill_date, "due_date": due_date}
    for _code, reader in FACT_READERS:
        for account_id, code, params in reader(ids, window):
            out.setdefault(str(account_id), []).append({"code": code, "params": params})
    return out


def accounts_changed_since(account_ids: Iterable[Any], since: Any) -> dict[str, Any]:
    """`{account_id: latest change}` for accounts with a payment posted or
    changed (a reversal is a new row) after `since` — so billing's bulk Check
    re-checks exactly those accounts (OQ-843 re-ruled 2026-09-30, option C:
    *"… or payment changes"*). Read-only; one query. `account_ids=None`
    (`DEF-BIL-8694`) asks about every account of the utility; the caller keeps
    the ones it saved — what changed, never the run's 40,000 ids as parameters."""
    from django.db.models import Max

    every = account_ids is None
    ids = [] if every else [str(one) for one in account_ids if one]
    if (not every and not ids) or since is None:
        return {}
    scope = {} if every else {"account_id__in": ids}
    return {
        str(account_id): last
        for account_id, last in models.Payment.objects.filter(
            tenant_id=_tenant_id(), updated_at__gt=since, **scope
        )
        .values("account_id")
        .annotate(last=Max("updated_at"))
        .values_list("account_id", "last")
    }


__all__ = [
    "FACT_READERS",
    "UNAVAILABLE",
    "accounts_changed_since",
    "autopay_cards_expiring",
    "in_collections",
    "instalments_due",
    "paid_after_cutoff",
    "payment_facts_for_accounts",
    "unmatched_payments",
]
