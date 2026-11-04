# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 lane RULINGS (2026-10-05) — `OQ-CUS-12790` CLOSED (a).
# Rules:    PO ruling, decision log *"FOUR PO RULINGS IN ONE REPLY"* (4),
#           verbatim: *"Release the deposit and refund the full $175.00 as one
#           refund, approved by Finance as usual."* · BR-PAY-012 (a deposit is a
#           LIABILITY, never revenue) · US-PAY-002 TC-1 (a HELD deposit is not
#           credit) · BR-PAY-014 (a refund only out of a real credit) ·
#           BR-LED-025 (the posting service refuses more than two decimals) ·
#           CLAUDE.md hard rules 1, 2, 4, 5, 6, 7
# Tests:    06-backend/tests/test_cr171_oq_cus_12790_cancel_refund.py
# ───────────────────────────────────────────────────────
"""🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — release a HELD deposit to the
account's CREDIT, with its books entry. The ONE writer of `deposit_releases`.

AI-authored 2026-10-05 (lane RULINGS, `CR-171-BRC10`) under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`.

THE PO's CASE, AND WHAT THIS FUNCTION DOES WITH IT
---------------------------------------------------
Nilesh pays **$175.00 by check 1043** — a **$150.00** deposit and a **$25.00**
connection fee — and his move-in is cancelled before any bill. The $25.00 is
already credit; the $150.00 is HELD and the refund path cannot reach it, on
purpose (US-PAY-002 TC-1). The ruling: *"Release the deposit and refund the full
$175.00 as one refund, approved by Finance as usual."* This function is the
*release* half, and it does three things in ONE transaction:

  1. writes a `deposit_releases` row for **$150.00** — which
     `selectors.account_credit_position` counts, so the account's credit goes
     **$25.00 → $175.00**;
  2. posts **DR 2300 customer deposit liability $150.00 / CR 2400 customer
     credit balances $150.00** through the ledger's own `post_deposit_applied`
     with a closing position of $0.00 — the entry a move-out's leftover
     deposit already uses (OQ-248, CLOSED 2026-09-30) — so the books and the
     credit move together (hard rule 5: only the posting service writes);
  3. writes the `audit_log` row (hard rule 7).

The *refund* half is NOT here: the caller raises ONE refund request for the
whole credit through `refunds.request_refund`, which Finance approves and issues
on the chain that already exists. Nothing in this file pays anything out.

The customer register (`accounts.deposit_on_file`) is CUSTOMERS' table and is
moved by customers (`services.record_deposit_movement(released=True)`), in the
same transaction, by the caller — payments never writes another module's table.

WHAT IS REFUSED, BY NAME, AND NOTHING WRITTEN
---------------------------------------------
* an amount that is not a positive Decimal of at most two decimals (the
  posting service would refuse it anyway — refused first, before any row);
* more than this account still HOLDS in deposit payments (paid deposits minus
  earlier releases) — a release cannot create money;
* an account that is not this tenant's;
* a ledger that cannot post it (no published writer, or a refusal from it) —
  the release and its entry are one fact or neither.

An `idempotency_key` seen before returns the first release unchanged (hard
rule 6): a retried cancel never releases a deposit twice.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from importlib import import_module
from typing import Any

from django.db import transaction
from django.db.models import Sum

from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy
from core.dbfields import uuid7

from apps.payments import models as payment_models
from apps.payments.deposit_release_models import DepositRelease
from apps.payments.exceptions import PaymentRuleError

ZERO = Decimal("0")
CENT = Decimal("0.01")

#: The audit action written with every release.
AUDIT_RELEASED = "deposit.released_to_credit"
#: The journal entry's `source_type` — the release row is the source document.
SOURCE_TYPE = "deposit_release"


@dataclass(frozen=True)
class ReleaseResult:
    release_id: str
    account_id: str
    amount: Decimal
    currency: str
    journal_entry_id: str | None
    created: bool

    def serialize(self) -> dict[str, Any]:
        return {
            "release_id": self.release_id,
            "account_id": self.account_id,
            "amount": f"{self.amount:.4f}",
            "currency": self.currency,
            "journal_entry_id": self.journal_entry_id,
            "created": self.created,
        }


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def released_total(account_id: Any) -> Decimal:
    """Every deposit this account has had released to credit."""
    total = DepositRelease.objects.filter(tenant_id=_tenant_id(), account_id=account_id).aggregate(
        total=Sum("amount")
    )["total"]
    return total or ZERO


def _deposit_paid_in(account_id: Any, *, uncleared_counts: bool) -> Decimal:
    """Deposit-purpose money paid in, net of every return and every release.

    The population, and how each existing return path takes money back OUT of
    it — no path is added here (PO 2026-10-06, `DEF-BIL-9751` (a): *"bounced
    payments are already handled by a process that exists today"*):

      * a cheque VOIDED at the counter (`cheques.void_cheque`) moves
        `processing → failed` and writes no reversing row, so `failed` is
        excluded by status — it never was money (`DEF-PAY-9782`: until
        2026-10-06 it was counted, and a release could have refunded it);
      * a payment CANCELLED while processing (`cancel.cancel_payment`) keeps
        its +amount and gains a −amount row, both `cancelled`: they net to 0;
      * a cleared payment that BOUNCES (`reversal.reverse_payment`) gains a
        −amount row, `reversed`, same purpose: it nets to 0 (or to what stood,
        for a partial return).

    `uncleared_counts` is the one difference between the two readers below.
    """
    rows = payment_models.Payment.objects.filter(
        tenant_id=_tenant_id(),
        account_id=account_id,
        purpose=payment_models.PURPOSE_DEPOSIT,
    ).exclude(status=payment_models.PAYMENT_FAILED)
    if not uncleared_counts:
        rows = rows.exclude(status=payment_models.PAYMENT_PROCESSING)
    paid = rows.aggregate(total=Sum("amount"))["total"] or ZERO
    return paid - released_total(account_id)


def deposit_still_held(account_id: Any) -> Decimal:
    """Deposit-purpose money CLEARED and not yet released — what a release may
    draw on, and therefore what may be paid OUT.

    ⚖️ **A PROCESSING DEPOSIT IS NOT HERE, AND `DEF-BIL-9751` DID NOT MOVE
    THAT.** The PO's ruling of 2026-10-06 makes a deposit taken at move-in
    count as PAID for the first bill's deposit line (`deposit_counted_paid`
    below). A release turns a deposit into credit that a refund pays out, and
    money a cheque has not yet delivered must not leave the utility — so the
    release still draws only on cleared money (decision log 2026-10-06,
    *"WHICH READ COUNTS A PROCESSING DEPOSIT"*)."""
    return _deposit_paid_in(account_id, uncleared_counts=False)


def deposit_counted_paid(account_id: Any) -> Decimal:
    """Deposit-purpose money that SATISFIES the first bill's deposit line
    (BR-PAY-012) — cleared OR still processing, net of returns and releases.

    PO ruling 2026-10-06 (`DEF-BIL-9751`, option (a)), verbatim: *"this is
    correct - I recommend (a). It matches what the customer actually did at
    the counter, and bounced payments are already handled by a process that
    exists today."* Worked: the church pays **$325.00** by cheque at move-in
    ($300.00 deposit + $25.00 connection); its first bill carries no $300.00
    deposit line. If the cheque is voided, cancelled or bounces, the existing
    path takes it back out of this figure and the $300.00 is owed again.

    Billing's only reader (`payments_seam.deposit_paid_for_account` via
    `credit.deposit_payments_for_account`). It pays nothing out."""
    return _deposit_paid_in(account_id, uncleared_counts=True)


def _post_to_books() -> Any:
    """The ledger's `post_deposit_applied`, resolved BY NAME (B1)."""
    try:
        module = import_module("apps.ledger.deposit_legs")
    except ImportError:  # pragma: no cover - the ledger app always imports
        return None
    found = getattr(module, "post_deposit_applied", None)
    return found if callable(found) else None


def _amount(value: Any) -> Decimal:
    if not isinstance(value, Decimal) or value <= ZERO:
        raise PaymentRuleError(
            f"a deposit release of {value!r} was asked for; it must be a positive Decimal "
            "(CLAUDE.md rule 2 — money is never a float, and a release of nothing is no release).",
            br_ref="BR-PAY-012",
        )
    if value != value.quantize(CENT):
        raise PaymentRuleError(
            f"a deposit release of {value} carries more than two decimals; the books take money "
            "rounded at finalisation (BR-LED-025: refuse and make the caller round).",
            br_ref="BR-LED-025",
        )
    return value.quantize(CENT)


def release_to_credit(
    actor: Any,
    *,
    account_id: Any,
    amount: Decimal,
    reason: str,
    source_type: str,
    source_id: Any,
    released_on: date,
    posted_at: datetime,
    idempotency_key: str,
) -> ReleaseResult:
    """Release `amount` of the account's HELD deposit to its credit, with the
    books entry. See the module docstring for the worked case."""
    from apps.payments import refunds  # the account and currency reads live there

    tenant_id = _tenant_id()
    amount = _amount(amount)
    key = str(idempotency_key or "").strip()
    if not key:
        raise PaymentRuleError(
            "a deposit release needs an idempotency key — a retried cancel must never release "
            "the same deposit twice (CLAUDE.md rule 6).",
            br_ref="BR-PAY-012",
        )
    with transaction.atomic():
        already = DepositRelease.objects.filter(tenant_id=tenant_id, idempotency_key=key).first()
        if already is not None:
            return _result(already, created=False)
        if not refunds._account_exists(tenant_id, account_id):
            raise errors.NotFoundError()
        held = deposit_still_held(account_id)
        if amount > held:
            raise PaymentRuleError(
                f"a release of {amount} was asked for and this account holds {held} in deposit "
                "payments. A release moves money the utility HOLDS for the customer to their "
                "credit; it cannot create money (BR-PAY-012).",
                br_ref="BR-PAY-012",
            )
        post = _post_to_books()
        if post is None:
            raise PaymentRuleError(
                "the ledger's deposit writer (`apps.ledger.deposit_legs.post_deposit_applied`) "
                "is not published, so this release would leave the books holding a deposit the "
                "credit no longer does. Refused: the release and its entry are one fact.",
                br_ref="BR-LED-007",
            )
        currency = refunds._currency_of(tenant_id, account_id, None)
        release_id = uuid7()
        reason_text = str(reason or "").strip() or "unspecified"
        # DR 2300 / CR 2400 FIRST, keyed on the release's own id, so the row is
        # written ONCE with its entry and never updated (hard rule 4). A closing
        # position of 0.00 means nothing is owed: the whole release lands in
        # customer credit (OQ-248's shape).
        posted = post(
            account_id=account_id,
            source_type=SOURCE_TYPE,
            source_id=release_id,
            credit=amount,
            closing_position=ZERO,
            entry_date=released_on,
            posted_at=posted_at,
            currency=currency,
            actor=actor,
            memo=f"Deposit released to customer credit — {reason_text}",
        )
        entry_id = getattr(posted, "entry_id", None)
        release = DepositRelease.objects.create(
            id=release_id,
            tenant_id=tenant_id,
            account_id=account_id,
            amount=amount,
            currency=currency,
            reason=reason_text,
            source_type=str(source_type),
            source_id=str(source_id),
            released_on=released_on,
            released_by_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
            journal_entry_id=entry_id,
            idempotency_key=key,
        )
        core_audit.money_action(
            actor,
            AUDIT_RELEASED,
            "deposit_release",
            str(release.id),
            after={
                "account_id": str(account_id),
                "amount": f"{amount:.4f}",
                "currency": currency,
                "held_before": f"{held:.4f}",
                "reason": release.reason,
                "source_type": release.source_type,
                "source_id": release.source_id,
                "released_on": released_on.isoformat(),
                "journal_entry_id": None if entry_id is None else str(entry_id),
                "idempotency_key": key,
            },
        )
    return _result(release, created=True)


def _result(release: DepositRelease, *, created: bool) -> ReleaseResult:
    return ReleaseResult(
        release_id=str(release.id),
        account_id=str(release.account_id),
        amount=release.amount,
        currency=release.currency,
        journal_entry_id=(
            None if release.journal_entry_id is None else str(release.journal_entry_id)
        ),
        created=created,
    )
