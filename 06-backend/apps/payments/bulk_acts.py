# ── Trace ──────────────────────────────────────────────
# Change:   Payments audit Q4 (PO 2026-10-30, decision log *"Q4 settled: bulk
#           Send receipts AND bulk Reapply are built; queued email waits for
#           the provider (PO)"*) · DEF-PAY-10747 · lane PAY-J
# Story:    US-PAY-004 (S33 Record payments — the list's bulk bar) ·
#           US-PAY-025 (the receipt) · US-PAY-006 (the allocation write path)
# Rules:    BR-PAY-024 (the receipt) · BR-PAY-018 (a HELD row is never re-sent)
#           · BR-NOT-005 (queue only; nothing here sends) · BR-PAY-031
#           (reapply = reversing allocation rows + new ones, posting nothing) ·
#           BR-PAY-010 (oldest bill first) · BR-PAY-014 (held credit is the
#           account's position) · BR-TEN-043 (the caller names the day) ·
#           CLAUDE.md hard rules 1, 4, 6, 7 · hard-won law 14 (SAVEPOINTs)
# Tests:    06-backend/tests/test_pay_j_bulk_receipts_reapply.py
# Impacts:  apps/payments/receipt_resend.resend_receipt (the single-payment
#           resend, called as-is) · apps/payments/receipts.
#           queue_receipt_for_recorded_payment (the first-time queue, called
#           as-is) · apps/payments/reapply.reapply_payment (🔒, called as-is,
#           not edited) · apps/payments/bulk_acts_api.py (the two doors)
# ───────────────────────────────────────────────────────
"""The two ONE-PAYMENT acts the Payments list's bulk bar runs once per tick.

╔══════════════════════════════════════════════════════════════════════════╗
║  NEITHER OF THESE IS A NEW MONEY PATH OR A NEW RECEIPT PATH.             ║
╚══════════════════════════════════════════════════════════════════════════╝
The PO ruled the two bulk actions in on 2026-10-30 (*"with bulk option is
good"*), and the ruling says each acts *"per selected payment through the
existing single-payment service"*. So each function below DECIDES what the
existing service should be asked, asks it, and names what happened. Nothing
here composes a receipt, picks a template, writes `outbound_messages`, writes
`allocations` or posts a journal line.

The bulk bar calls these ONE PAYMENT AT A TIME, in order (the bar's own header
in `paymentsBulk.tsx` says why: sequential, never aborting, a verdict per row).
There is deliberately no list endpoint: the per-row verdict IS the product.

════════════════════════════════════════════════════════════════════════════
SEND RECEIPT — AND WHY A RECEIPT STILL WAITING IS NEVER QUEUED AGAIN
════════════════════════════════════════════════════════════════════════════
The PO's statement of how email works (verbatim): *"we write email in table once
email serivce provider is up the all email going out and provider is down the
service will stop"*. So a receipt written during an outage is not lost — it is
`queued` in `outbound_messages` and goes out on the first dispatch after the
provider is back (lane PAY-G measured exactly that in
`tests/test_pay_g_receipts_go_out.py`).

The coordinator's judgment recorded under that ruling: **bulk Send receipts
never re-queues a receipt still waiting.** Queueing a second copy beside a
`queued` one sends TWO receipts the moment the provider returns. So the email
receipt's latest row decides, and the outcome names it:

    no email row at all     → queue the receipt through the FIRST-TIME path
                              (`queue_receipt_for_recorded_payment`, which is
                              idempotent on (payment, channel, copy 0))  → sent
    `queued`, an address    → WAITING for the email service — nothing written
    `queued` / any, no      → NO CONTACT ON FILE — nothing written; a copy of
      address on the row       a row with no address goes nowhere either
    HELD                    → HELD (BR-PAY-018: that address bounced)
    `failed`                → re-queued as the next copy through the existing
                              single-payment resend (`resend_receipt`) → sent
    `sent` / `delivered`    → ALREADY SENT — nothing written
    bounced/complained/     → UNDELIVERABLE — nothing written; sending to the
      unsubscribed             same address again is what those states forbid

"Sent" on the screen means *queued to go out*, which is what the single-payment
Resend says too; the dispatcher does the sending (BR-NOT-005).

⚠ **EMAIL ONLY, AND THAT IS A JUDGMENT RECORDED IN THE DECISION LOG.** The
ruling's case is *"20 receipts not sent during a 29 Oct email outage"* and its
statement is about the email provider. A printed receipt has no vendor and never
leaves on its own (PAY-G); a text has its own channel switch. Widening this to
text is one more channel in `CHANNELS` — not a second design.

⚠ **IDEMPOTENT WITHOUT A TOKEN.** A second press finds the row the first press
wrote — `queued` — and answers WAITING. Two clerks racing compute the same
`copy_no` and the queue's unique key `(source, channel, copy_no)` collides them
into one row (`created: false`).

════════════════════════════════════════════════════════════════════════════
REAPPLY — THE PAYMENT'S HELD PART, ONTO ITS ACCOUNT'S OPEN BILLS, OLDEST FIRST
════════════════════════════════════════════════════════════════════════════
A single reapply names its bills by hand, because it exists to correct a choice
the automatic order made (`reapply.py` E2). A bulk run cannot ask fifty
questions, so the bulk act is the ONE reapply that needs no choice: the money
the payment is still HOLDING as credit goes onto the account's open bills,
oldest first (BR-PAY-010's shipped default — `open_invoices_for_account`
returns them in that order), and NOTHING the payment already meets is taken off
(`release=()`). That is exactly the account screen's *Apply now* (lane PAY-F),
done for every ticked payment. The ruling's worked case — *"5 lockbox cheques
to move to the newer bills"* — is that: cheques that arrived before the bills
they pay were issued, sitting as credit.

The held part is capped by the account's credit POSITION, because a refund
names the account and not a payment (PO 2026-09-01), so a payment's own
leftover can already have gone back to the customer. Applying it again would
put money on a bill that nobody holds.

Refused BY NAME, never skipped silently (the brief: *"a payment the clerk may
not reapply is named"*): still processing · reversed · cancelled · failed · a
reversing row · a deposit or payment-plan down payment (money held for one
purpose). Each raises `PaymentRuleError`, which the door turns into the
catalogue refusal the row's result line shows.

Outcomes when it runs: REAPPLIED (with the amount and the bills) · NOTHING TO
REAPPLY (the payment holds no credit) · NO OPEN BILL. A second press finds
nothing held and answers NOTHING TO REAPPLY — no token needed.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.db import transaction

from apps.payments import billing_seam, models, reapply, receipt_resend, receipts, selectors
from apps.payments.exceptions import PaymentRuleError
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy

ZERO = Decimal("0")

#: The receipt channels a bulk send acts on. Email only — see the docstring.
CHANNELS = (receipt_resend.CHANNEL_EMAIL,)

# ── outcome codes (sentences live in the eleven catalogues, B14 rule 35) ────
RECEIPT_SENT = "sent"
RECEIPT_WAITING = "waiting"
RECEIPT_NO_CONTACT = "no_contact"
RECEIPT_ALREADY_SENT = "already_sent"
RECEIPT_HELD = "held"
RECEIPT_UNDELIVERABLE = "undeliverable"
RECEIPT_NOT_MONEY = "not_money_received"
RECEIPTS_SWITCHED_OFF = "receipts_off"
RECEIPT_NOT_QUEUED = "not_queued"

REAPPLIED = "reapplied"
NOTHING_TO_REAPPLY = "nothing_to_reapply"
NO_OPEN_BILL = "no_open_bill"

AUDIT_BULK_RECEIPT = "payment.bulk_receipt"

#: The audit reason every bulk reapply row carries. The reapply service
#: requires one; a bulk run has no per-row reason to ask for, and this names
#: which act moved the money so the trail reads truthfully months later.
BULK_REAPPLY_REASON = "Bulk reapply from the Payments list: held credit to open bills, oldest first"

_UNDELIVERABLE = {"bounced", "bounced_hard", "bounced_soft", "complained", "unsubscribed"}
_DELIVERED = {"sent", "delivered"}

_NOT_REAPPLIABLE_STATUS = {
    models.PAYMENT_PROCESSING: "still processing — the money has not arrived",
    models.PAYMENT_REVERSED: "reversed — the money came back",
    models.PAYMENT_CANCELLED: "cancelled",
    models.PAYMENT_FAILED: "failed — the money never arrived",
}
_HELD_FOR_A_PURPOSE = {
    models.PURPOSE_DEPOSIT: "a deposit — held, not applied to bills",
    models.PURPOSE_PLAN_DOWN: "a payment-plan down payment — held for the plan",
}


def _tenant_id() -> Any:
    """CLAUDE.md rule 1 — nothing touches a tenant table without `app.tenant_id`."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _payment(payment_id: Any) -> models.Payment:
    tenant_id = _tenant_id()
    payment = models.Payment.objects.filter(tenant_id=tenant_id, pk=payment_id).first()
    if payment is None:
        raise PaymentRuleError(
            f"payment {payment_id} is not this tenant's. Nothing was done.",
            br_ref="BR-TEN-003",
        )
    return payment


def _latest(rows: list[dict[str, Any]], channel: str) -> dict[str, Any] | None:
    mine = [row for row in rows if row.get("channel") == channel]
    if not mine:
        return None
    return max(mine, key=lambda row: int(row.get("copy_no") or 0))


def _receipt_outcome_from_row(row: dict[str, Any]) -> str | None:
    """What an EXISTING latest email row says, or None when it should be re-queued."""
    if not row.get("recipient_address"):
        return RECEIPT_NO_CONTACT
    if row.get("held"):
        return RECEIPT_HELD
    status = str(row.get("status") or "")
    if status == "queued":
        return RECEIPT_WAITING
    if status in _DELIVERED:
        return RECEIPT_ALREADY_SENT
    if status in _UNDELIVERABLE:
        return RECEIPT_UNDELIVERABLE
    if status == "failed":
        return None
    # A status this table may grow later is reported as waiting rather than
    # re-queued: doubling a receipt is the one outcome this function exists to
    # prevent, and a waiting row is the conservative reading.
    return RECEIPT_WAITING


def send_receipt(*, actor: Any, payment_id: Any) -> dict[str, Any]:
    """`POST /payments/{id}/bulk-receipt` — one payment's email receipt, unless it
    is still waiting. Read the module docstring's table before changing a branch.
    """
    payment = _payment(payment_id)
    outcome, detail = _send_receipt(actor=actor, payment=payment)
    # Hard rule 7: a receipt is a statement of money received, and "did we send
    # that twice?" is the question this row answers later — so even a run that
    # wrote nothing records what it found.
    core_audit.money_action(
        actor,
        AUDIT_BULK_RECEIPT,
        "payment",
        str(payment.pk),
        after={
            "outcome": outcome,
            "channels": list(CHANNELS),
            "detail": detail,
            "job": None if actor is not None else "payments.bulk_receipt",
        },
    )
    return {
        "payment_id": str(payment.pk),
        "payment_no": payment.payment_no,
        "outcome": outcome,
    }


def _send_receipt(*, actor: Any, payment: models.Payment) -> tuple[str, str | None]:
    if payment.type in (models.PAYMENT_TYPE_CREDIT, models.PAYMENT_TYPE_ADJUSTMENT) or (
        payment.amount <= ZERO or payment.reverses_payment_id is not None
    ):
        return RECEIPT_NOT_MONEY, None

    channel = receipt_resend.CHANNEL_EMAIL
    latest = _latest(receipt_resend.receipt_deliveries(payment), channel)

    if latest is None:
        # No receipt was ever queued on email (receipts switched off at the
        # time, or the payment predates the email receipt). The FIRST-TIME path
        # is the one receipt path; it is idempotent on copy 0, and it writes
        # print and text rows only where those are missing too.
        with transaction.atomic():  # law 14 — a refused write must not poison the caller
            problems = receipts.queue_receipt_for_recorded_payment(payment=payment, actor=actor)
        codes = {str(problem.get("code")) for problem in problems}
        if receipts.RECEIPT_ELECTION_OFF in codes:
            return RECEIPTS_SWITCHED_OFF, None
        written = _latest(receipt_resend.receipt_deliveries(payment), channel)
        if written is None:
            # The channel switch or the utility's rule left no email row; the
            # queue's own reason is the detail.
            return RECEIPT_NOT_QUEUED, ", ".join(sorted(codes)) or None
        if not written.get("recipient_address"):
            return RECEIPT_NO_CONTACT, None
        return RECEIPT_SENT, None

    found = _receipt_outcome_from_row(latest)
    if found is not None:
        return found, None

    # FAILED — the provider was tried three times and the row rests. The
    # existing single-payment resend copies it as the next copy number.
    copy_no = receipt_resend.next_copy_no(receipt_resend.receipt_deliveries(payment))
    with transaction.atomic():  # law 14
        resent = receipt_resend.resend_receipt(
            actor=actor, payment=payment, channels=list(CHANNELS), copy_no=copy_no
        )
    if any(one.get("channel") == channel for one in resent.queued):
        return RECEIPT_SENT, None
    problems = [p for p in resent.problems if p.get("code") != "resend_touched_no_money"]
    return RECEIPT_NOT_QUEUED, "; ".join(str(p.get("detail") or p.get("code")) for p in problems)


# ── reapply ────────────────────────────────────────────────────────────────


def _refuse_if_not_reappliable(payment: models.Payment) -> None:
    label = payment.payment_no or str(payment.pk)
    why = _NOT_REAPPLIABLE_STATUS.get(payment.status)
    if why is not None:
        raise PaymentRuleError(
            f"{label} is {why}, so there is nothing to reapply.", br_ref="BR-PAY-031"
        )
    if payment.reverses_payment_id is not None or payment.amount <= ZERO:
        raise PaymentRuleError(
            f"{label} is a reversing row; its money is the mirror of another payment's.",
            br_ref="BR-PAY-031",
        )
    held_for = _HELD_FOR_A_PURPOSE.get(payment.purpose)
    if held_for is not None:
        raise PaymentRuleError(f"{label} is {held_for}.", br_ref="BR-PAY-012")


def reapply_held(*, actor: Any, payment_id: Any, on_date: date) -> dict[str, Any]:
    """`POST /payments/{id}/bulk-reapply` — the payment's held part onto its
    account's open bills, oldest first, through `reapply.reapply_payment`.

    Read the module docstring. Refusals RAISE (the row is named, never skipped);
    the three ordinary outcomes RETURN.
    """
    payment = _payment(payment_id)
    _refuse_if_not_reappliable(payment)

    applied = sum((row.amount for row in payment.allocations.all()), ZERO)
    held = payment.amount - applied
    # The account's position, because a refund draws on the ACCOUNT.
    position = selectors.account_credit_position(payment.account_id)
    held = min(held, position)
    base = {"payment_id": str(payment.pk), "payment_no": payment.payment_no}
    if held <= ZERO:
        return {**base, "outcome": NOTHING_TO_REAPPLY, "applied_total": "0", "bills": []}

    open_bills = billing_seam.open_invoices_for_account(payment.account_id).invoices
    targets: list[dict[str, Any]] = []
    left = held
    for bill in open_bills:  # oldest first — the seam's own order (BR-PAY-010)
        if left <= ZERO:
            break
        take = min(left, bill.balance)
        if take > ZERO:
            targets.append({"invoice_id": str(bill.invoice_id), "amount": take})
            left -= take
    if not targets:
        return {**base, "outcome": NO_OPEN_BILL, "applied_total": "0", "bills": []}

    with transaction.atomic():  # law 14
        result = reapply.reapply_payment(
            actor,
            payment_id=payment.pk,
            targets=tuple(targets),
            reason=BULK_REAPPLY_REASON,
            on_date=on_date,
            release=(),
        )
    return {
        **base,
        "outcome": REAPPLIED,
        "applied_total": str(result.applied_total),
        "currency": result.currency,
        "bills": [row.get("invoice_number") for row in result.applied_to],
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: decision log 2026-10-30 "Q4 settled" (PO) + PAY-G judgment 5 (the
#         outbound statuses) · apps/payments/receipt_resend.py ·
#         apps/payments/receipts.py · apps/payments/reapply.py ·
#         07-frontend/src/features/payments/paymentsBulk.tsx (the run)
# generated: 2026-10-30 by lane PAY-J
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions:
#   E1 email only — the ruling's case and statement are the email provider's;
#      recorded in the decision log as a lane judgment.
#   E2 bulk reapply moves HELD credit only (release=()); a payment already on
#      the wrong bill is still corrected from its row's Reapply, where the
#      clerk names the bill. Recorded in the decision log.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
