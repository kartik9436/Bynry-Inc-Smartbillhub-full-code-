# ── Trace ──────────────────────────────────────────────
# Change:   CR-174-BRC10 — US Payments (Prime): a payment agent's three calls
#           to us. This file is the PAYMENTS half: what a landed notification
#           does to money. The door half is apps/integrations/inbound.py.
# Rules:    PO 2026-10-07 D1 (post on arrival) · D2 (an account we cannot
#           find) · D3 (never in the New World feed) · BR-PAY-003 / BR-PAY-028
#           (a payment is recorded once) · BR-PAY-010 (oldest-first; overpay
#           carries as credit) · BR-PAY-013 (a return reverses) · BR-PAY-036
#           (a payment is always accepted) · BR-TEN-081 (a business date is the
#           utility's own day) · CLAUDE.md hard rules 1, 4, 5, 6, 7 · law 14
# Tests:    06-backend/tests/test_cr174_us_payments.py
# Impacts:  apps/integrations/seams/payments.py (the address integrations
#           calls) · apps/payments/services.record_payment ·
#           apps/payments/reversal.reverse_payment · apps/payments/
#           account_balance.account_balance (the one balance read)
# ───────────────────────────────────────────────────────
"""A PAYMENT AGENT TOLD US SOMETHING — what it does to the money. HUMAN-REVIEW-PENDING.

AI-authored 2026-10-07 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human"*): it records payments, reverses them and keys
both against a duplicate, which is three 🔒 paths at once. Row in
`12-governance/09-human-review-ledger.md`.

WHY THIS EXISTS AT ALL — THE RULING THAT MOVED A BOUNDARY
---------------------------------------------------------
Until 2026-10-07 the inbound door landed a kiosk payment and STOPPED
(`BR-INT-058`, `OQ-INT-1729` (a)): *"Runbooks will handle the logic"*. The PO
was shown the cost for US Payments — Rosa pays **$150.00** cash at a kiosk at
2:32 pm; if posting waits for a runbook, a 2:40 pm lookup still shows
**$147.85** owed and she may pay twice — and ruled, verbatim: *"(a). A person
standing at a machine needs the live balance. Runbooks still handle the
exceptions in D2."* So for a connector that DECLARES it (`Operation.applies`,
data on the manifest, never a branch on its key), the door calls this file
inside the call, and the answer the agent gets is the truth about the money.

The kiosk card (`payments_kiosk`) was not ruled and declares nothing, so it
still applies nothing.

THREE FUNCTIONS, ONE PER OPERATION
----------------------------------
* `account_position` — the lookup. **Reads the ONE balance function**
  (`account_balance.account_balance`) the customer portal reads; it adds no
  arithmetic of its own.
* `post_payment` — `record_payment`, cleared on arrival (D1: the money is the
  agent's to collect and the customer is standing there), keyed
  `agent|<provider>:<paymentId>|payment`, allocated by the tenant's own order with no
  bill named, any overpayment carried as credit (BR-PAY-010).
* `post_return` — the EXISTING `reverse_payment`, keyed
  `agent|<provider>:<paymentId>|return`, with the bank's code beside the
  reason.

⚠ **THE TWO GUARDS ARE INDEPENDENT AND BOTH STAND (DEF-058's lesson).** The
door's `uq_payment_webhook_events_event` answers *have I been handed this
message*; `uq_payments_webhook_key` here answers *has this payment been
recorded*. Either one alone refuses the second payment; a test switches each
off in turn.

⚠ **NOTHING HERE OPENS A SAVEPOINT FOR THE HAPPY PATH; THE DOOR'S TRANSACTION
IS THE BOUNDARY.** The landing row, the payment, its allocations, its journal
entry, its audit rows and the stamp on the landing row all commit together or
none of them does — so an internal failure answers 500 with NOTHING kept, and
the agent's retry of the identical body is a first delivery rather than a
`409` over money we never posted. The two savepoints below exist for the two
REFUSALS a clerk must see, and they are law 14's: on PostgreSQL a refused
statement poisons the whole transaction, so a refusal caught without one would
lose the landing row it is trying to keep.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import transaction

from core import tenancy as core_tenancy

from apps.payments import idempotency, models, settings_seam
from apps.payments.exceptions import PaymentRuleError

ZERO = Decimal("0")

#: What a landed notification turned into. CODES, never prose (the door maps
#: each to the manifest's status number; this file holds none).
POSTED = "posted"
PARKED = "parked"
NOT_YET = "not_yet"
INVALID = "invalid"

#: The landing row's `outcome` when a clerk must look (D2's residue). The
#: words are a sentence a person can act on, because S142 and the landed-events
#: list show them as written.
PARKED_ACCOUNT_NOT_FOUND = "account_not_found"
PARKED_RULE_REFUSED = "refused_by_a_payment_rule"
PARKED_ORIGINAL_NOT_POSTED = "original_payment_was_not_posted"

#: Nacha return codes that mean the money was never there (insufficient or
#: uncollected funds). Every other code — an account closed, an authorisation
#: revoked, a card chargeback — is the bank taking money back, which
#: `REVERSAL_REASONS` calls `bank_chargeback`. The two staff reasons
#: (`data_entry_error`, `customer_dispute`) are never chosen by a machine: they
#: carry a window and an approval a clerk gives (`reversal_rules`).
NSF_RETURN_CODES = frozenset({"R01", "R09"})


@dataclass(frozen=True)
class AgentOutcome:
    """What one landed notification did. `code` is one of the four above."""

    code: str
    payment_id: str | None = None
    payment_no: str | None = None
    detail: str | None = None
    replayed: bool = False


# ═══════════════════════════════════════════════════════════════════════════
# Shared reads
# ═══════════════════════════════════════════════════════════════════════════


def business_date(moment: datetime) -> date:
    """The UTILITY's own calendar day for an instant (BR-TEN-081).

    `2026-10-08T03:30:00Z` is **7 October** for a utility on
    `America/New_York` and 8 October for one on UTC. The agent stamps its
    payment in UTC; the customer paid on the day their utility calls it.
    """
    return moment.astimezone(settings_seam.tenant_timezone()).date()


def business_moment(on: date) -> datetime:
    """A business date as this module stores one: midnight in the utility's
    own zone — the ruled anchor (`payments/api._moment`, OQ-153 CLOSED)."""
    return datetime.combine(on, time.min, tzinfo=settings_seam.tenant_timezone())


def find_account(account_ref: Any) -> Any:
    """The account whose number is EXACTLY `account_ref`, in this tenant, or None.

    Exact: `00123` is not `123` and `a-10` is not `A-10` — the agent's
    specification says the id is an exact string with its leading zeros kept,
    and a forgiving match would put money on somebody else's account. Through
    customers' own published queryset (B1), which filters on the tenant itself;
    RLS FORCE is the second guarantee on PostgreSQL (hard rule 1).
    """
    from importlib import import_module

    text = "" if account_ref is None else str(account_ref)
    if not text:
        return None
    read = getattr(import_module("apps.customers.selectors"), "account_queryset", None)
    if read is None:  # pragma: no cover - customers always publishes it
        return None
    return read().filter(account_no=text).first()


def agent_channel(word: Any) -> str | None:
    """`KIOSK` → `kiosk`; a word nobody listed → `other`; nothing sent → None.

    *"unknown → OTHER, never refuse"* — the specification's own rule.
    """
    text = str(word or "").strip().lower()
    if not text:
        return None
    return text if text in models.AGENT_CHANNELS else models.AGENT_CHANNEL_OTHER


def _terminal(value: Any) -> str | None:
    """The agent's machine number as text (`4471`), or None. An identifier is
    never arithmetic, so it is never stored as a number."""
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    return text[:64] or None


def _money(value: Any) -> Decimal | None:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return amount if amount.is_finite() else None


# ═══════════════════════════════════════════════════════════════════════════
# 1 · the account lookup
# ═══════════════════════════════════════════════════════════════════════════


def account_position(account_ref: Any, *, as_of: date) -> dict[str, Any] | None:
    """What the agent may show a customer about ONE account — or None.

    None is *no such account*, and it is the same None for an account of
    another utility (the queryset cannot see it), a blank id and a typo: the
    agent's contract is one answer for all three, and a different answer for
    any of them would tell a stranger which account numbers exist somewhere.

    `allow_*` are TRUE unless the account carries a real restriction, and the
    product has exactly one: `cash_only_no_autopay`, set after repeated bounces
    (BR-PAY-013). A cash-only account may still pay — in cash — so
    `allow_payments` stays true and the three instruments that can bounce say
    no. `residential` is the account's own category code (`account_types`),
    `residential` and nothing else.
    """
    from apps.payments import account_balance

    account = find_account(account_ref)
    if account is None:
        return None
    position = account_balance.account_balance(account.pk, as_of=as_of)
    cash_only = bool(getattr(account, "cash_only_no_autopay", False))
    category = getattr(getattr(account, "account_type", None), "code", None)
    return {
        "account_id": str(account.pk),
        "account_no": account.account_no,
        "balance": Decimal(position["balance"]),
        "past_due": Decimal(position["past_due"] or "0"),
        "currency": position.get("currency"),
        "allow_payments": True,
        "allow_check": not cash_only,
        "allow_credit": not cash_only,
        "allow_debit": not cash_only,
        "display_credit": True,
        "residential": str(category or "").strip().lower() == "residential",
    }


# ═══════════════════════════════════════════════════════════════════════════
# The landing row — payments' own table, stamped with what became of it
# ═══════════════════════════════════════════════════════════════════════════


def _stamp(event_row_id: Any, *, status: str, outcome: str, payment_id: Any = None) -> None:
    """The four columns `payments/0020`'s freeze lets move, and nothing else.

    `processed_at` is the row's own `received_at` — the moment the agent's
    message arrived — never a clock (BR-TEN-043; gate G6).
    """
    row = models.PaymentWebhookEvent.objects.get(
        tenant_id=core_tenancy.current_tenant_id(), pk=event_row_id
    )
    row.status = status
    row.outcome = outcome
    row.payment_id = payment_id
    row.processed_at = row.received_at
    row.save(update_fields=["status", "outcome", "payment_id", "processed_at", "updated_at"])


def landed_event(provider: str, event_id: str) -> Any:
    """A landing row by its door key, in this tenant, or None."""
    return models.PaymentWebhookEvent.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), provider=provider, event_id=event_id
    ).first()


# ═══════════════════════════════════════════════════════════════════════════
# 2 · a payment
# ═══════════════════════════════════════════════════════════════════════════


def post_payment(
    *,
    provider: str,
    door_key: str,
    event_row_id: Any,
    account_ref: Any,
    amount: Any,
    paid_at: datetime,
    method_code: str | None,
    confirmation: str | None,
    channel: Any = None,
    terminal: Any = None,
) -> AgentOutcome:
    """Record one agent payment — or park it for a clerk. Never refuses money.

    ⚠ **THE ACCOUNT IS LOOKED UP BY ITS NUMBER AT PAYMENT TIME, AND A MISS IS
    PARKED, NOT REFUSED (D2).** The PO's reasoning is that the kiosk always asks
    first, so a payment for an unknown account cannot happen. The residue the
    reasoning does not cover — an account closed or renumbered between the
    lookup and the payment — is OUR judgment, recorded: the message is already
    landed, so the agent is told `200` (we have it; do not resend), nothing is
    posted, the landing row says why, and the door alerts the System Admin. A
    refusal would make the agent resend for ever; a guess would put somebody's
    money on somebody else's account.

    ⚠ **CLEARED ON ARRIVAL.** `cleared_at` is the business date, so the
    payment allocates and posts now (D1). `record_payment` leaves a payment
    with no clearing date `processing`, unallocated — which is exactly the
    *"still shows $147.85"* the PO ruled against.
    """
    value = _money(amount)
    if value is None or value <= ZERO:
        # The door validates first; this is the belt to its braces.
        return AgentOutcome(code=INVALID, detail="the amount is not a positive number")
    account = find_account(account_ref)
    if account is None:
        _stamp(event_row_id, status=models.WEBHOOK_REFUSED, outcome=PARKED_ACCOUNT_NOT_FOUND)
        return AgentOutcome(code=PARKED, detail=PARKED_ACCOUNT_NOT_FOUND)
    on = business_moment(business_date(paid_at))
    from apps.payments import services

    try:
        # ← SAVEPOINT. Law 14. A rule refusal must not take the landing row
        # with it on PostgreSQL. Do not remove.
        with transaction.atomic():
            recorded = services.record_payment(
                None,  # BR-AUD-003 — no person stands behind an agent's message.
                account_id=account.pk,
                amount=value,
                posted_at=on,
                cleared_at=on,
                method_code=method_code,
                confirmation=confirmation,
                idempotency_source=idempotency.SOURCE_AGENT,
                # GUARD 2, independent of the door's:
                # `agent|pay_uspayments:900000000123|payment`. The door's own
                # composite key is reused as the reference so the payment and
                # its return can never share one (`uq_payments_webhook_key`).
                idempotency_reference=f"{provider}:{door_key}",
                channel=agent_channel(channel),
                terminal=_terminal(terminal),
            )
    except PaymentRuleError as refusal:
        _stamp(event_row_id, status=models.WEBHOOK_REFUSED, outcome=PARKED_RULE_REFUSED)
        return AgentOutcome(code=PARKED, detail=str(refusal))
    _stamp(
        event_row_id,
        status=models.WEBHOOK_ACCEPTED,
        outcome=f"recorded as {recorded.payment_no or recorded.payment_id}",
        payment_id=recorded.payment_id,
    )
    return AgentOutcome(
        code=POSTED,
        payment_id=str(recorded.payment_id),
        payment_no=recorded.payment_no,
        replayed=not recorded.created,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 3 · a return
# ═══════════════════════════════════════════════════════════════════════════


def nacha_reason(return_code: str | None) -> str:
    """`nsf` for R01/R09; `bank_chargeback` for every other code and for none."""
    code = (return_code or "").strip().upper()
    return (
        models.REVERSAL_REASON_NSF
        if code in NSF_RETURN_CODES
        else models.REVERSAL_REASON_BANK_CHARGEBACK
    )


def post_return(
    *,
    provider: str,
    payment_door_key: str,
    door_key: str,
    event_row_id: Any,
    account_ref: Any,
    amount: Any,
    returned_at: datetime,
    return_code: str | None,
) -> AgentOutcome:
    """Reverse the payment this return names — through the EXISTING reversal.

    The original is found by the agent's own payment id, through the landing
    row its payment notification left (`<id>|payment`) — the same tenant, the
    same provider, nothing typed. Four answers:

    * **NOT_YET** — no such payment has arrived. The door answers a retry
      status and keeps NOTHING, so the identical resend is a first delivery.
      (A return can overtake its payment on the wire.)
    * **PARKED** — the payment arrived and was parked for a clerk (D2), so
      there is no money to take back: this is landed for the same clerk.
    * **INVALID** — the account does not match the payment's, or the amount is
      more than the payment (or than what still stands of it). The door
      answers `400` and keeps nothing.
    * **POSTED** — `reverse_payment` wrote the reversing row, released the
      allocations (the bills are due again from their own due dates) and
      mirrored the journal entry.

    ⚠ **THE ADMIN-ONLY GATE IS PASSED BY `__wrapped__`, AND THAT IS THE
    RULING RATHER THAN A WAY ROUND IT.** `reverse_payment` carries
    `@require_role(SYSTEM_ADMIN)` (`BR-PAY-1070`, CS-5), and its own docstring
    names this exact collision and says the CS-1 rails must decide it: *"a
    gateway returns feed has no user and therefore no role … a decision CS-1
    must make when the rails land"*. The PO made it for this connector on
    2026-10-07 (D1: a return reverses inside the call). The authority here is
    the agent's credential — authenticated, allow-listed and scoped to the
    `returns` operation by `serve.resolve_caller` before this line runs — not a
    person's role, and there is no person. Every staff path still meets the
    gate unchanged.
    """
    from apps.payments import reversal

    landed = landed_event(provider, payment_door_key)
    if landed is None:
        return AgentOutcome(code=NOT_YET, detail="the payment this return names has not arrived")
    if landed.payment_id is None:
        _stamp(event_row_id, status=models.WEBHOOK_REFUSED, outcome=PARKED_ORIGINAL_NOT_POSTED)
        return AgentOutcome(code=PARKED, detail=PARKED_ORIGINAL_NOT_POSTED)
    original = models.Payment.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), pk=landed.payment_id
    ).select_related("account").first()
    if original is None:  # pragma: no cover - the landing row names a real payment
        return AgentOutcome(code=NOT_YET, detail="the payment this return names is not visible")
    if str(account_ref or "") != str(original.account.account_no):
        return AgentOutcome(
            code=INVALID, detail="the account does not match the payment this return names"
        )
    value = _money(amount)
    if value is None or value <= ZERO:
        return AgentOutcome(code=INVALID, detail="the amount is not a positive number")
    if value > original.amount:
        return AgentOutcome(
            code=INVALID, detail="the amount is more than the payment this return names"
        )
    on = business_moment(business_date(returned_at))
    try:
        # ← SAVEPOINT. Law 14 — a refusal must leave the transaction usable so
        # the door can roll the landing back cleanly and answer 400.
        with transaction.atomic():
            reversed_ = reversal.reverse_payment.__wrapped__(
                None,
                payment_id=original.pk,
                returned_on=on,
                reason=nacha_reason(return_code),
                amount=value,
                idempotency_source=idempotency.SOURCE_AGENT,
                idempotency_reference=f"{provider}:{door_key}",
                return_code=return_code,
            )
    except PaymentRuleError as refusal:
        return AgentOutcome(code=INVALID, detail=str(refusal))
    _stamp(
        event_row_id,
        status=models.WEBHOOK_ACCEPTED,
        outcome=f"reversed as {reversed_.reversal_no or reversed_.reversal_id}",
        payment_id=reversed_.reversal_id,
    )
    return AgentOutcome(
        code=POSTED,
        payment_id=str(reversed_.reversal_id),
        payment_no=reversed_.reversal_no,
        replayed=not reversed_.created,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-174-BRC10 · decision log 2026-10-07 (PO D1–D4 + the build's judgments)
# generated: 2026-10-07 by the CR-174-BRC10 US Payments lane
# checklist: A✔ B✔ C✔ D✔(the door: apps/integrations/inbound.py) E✔(the payment's detail shows the channel, the terminal and the return code) F✔ G✔ H=deferred(PO 2026-08-09 — row in 09-human-review-ledger.md)
# gates: pytest tests/test_cr174_us_payments.py (SQLite and PostgreSQL 16) · G6 (no clock under payments/) · G77 (no provider key)
# exceptions: `reverse_payment.__wrapped__` passes the Admin-only role gate for the agent's credential, by the PO's D1 ruling (see `post_return`)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
