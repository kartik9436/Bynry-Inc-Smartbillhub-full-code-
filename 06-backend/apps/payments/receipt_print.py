# ── Trace ──────────────────────────────────────────────
# Ruling:   PO 2026-10-30, decision log *"Payments audit by level: answers to
#           Q1, Q3, Q5, Q6, Q7"* — Q3 = A: a **Print receipt** button opens a
#           one-page receipt in the browser to print now (Rosa pays $68.00 cash
#           → prints). Not a PDF; no attachments on a payment.
# Defect:   DEF-PAY-10743 (not built: no way to hand a customer a receipt now) ·
#           DEF-PAY-10770 (W4 = A: an account in credit prints its credit)
# Rules:    CLAUDE.md hard rules 1 (tenant scoping — `_payment_or_404` reads
#           under the request's tenant) and 2 (money as decimal strings) ·
#           B14 rule 31 (numbers, never ids, are what a person reads) ·
#           BR-NOT-005 (this SENDS nothing — it is a read)
# Tests:    tests/test_pay_g_print_receipt.py
# ───────────────────────────────────────────────────────
"""`GET /payments/{id}/receipt/print` — the facts on a one-page counter receipt.

**A READ, NOT A SEND AND NOT A SECOND RECEIPT PATH.** The queued receipt rows
(`receipts.queue_receipt_for_recorded_payment`) are untouched; this serves the
payment's own facts so the browser can lay out one page and print it. The
utility's name and mark are the SHELL's (`GET /settings/display`, the same
response the sidebar draws from), so they are not repeated here.

What the PO listed (Q3 = A) and where each comes from:

  receipt #        `payment_no` — the PY- number, never the id (B14 rule 31)
  date             `posted_at`
  account          `account_no`
  payer/customer   `customer_name` (the account holder, `selectors.payment_row`)
  amount           `amount` + `currency`, a decimal string (hard rule 2)
  method           `method_name` (and `confirmation`, the cheque/reference)
  bill(s) paid     `bills` — the allocation rows, number and amount each
  remaining        `balance` — the account's NET position from the books NOW,
                   signed: positive is still owed, NEGATIVE is credit on the
                   account (`receipts._ar_balance(with_held_credit=True)`, the
                   account header's own figure — `DEF-PAY-10770`, PO W4 = A:
                   Hugo's $68.00 that met no bill prints *"Credit on account
                   $68.00"*). `null` when the books cannot answer, never `0.00`
  clerk/counter    `taken_by` + `counter` — the till's owner and its code when
                   the payment was taken at a counter; a payment agent's name
                   for a kiosk payment; `null` otherwise (nothing is guessed)
"""

from __future__ import annotations

from typing import Any

from apps.payments import models, selectors


def _counter(payment: models.Payment) -> tuple[str | None, str | None]:
    """`(owner name, till code)` of the counter this payment was taken at."""
    session_id = getattr(payment, "counter_session_id", None)
    if session_id is None:
        return None, None
    from apps.payments import counters
    from apps.payments.counter_session_models import CounterSession

    session = (
        CounterSession.objects.filter(pk=session_id, tenant_id=payment.tenant_id)
        .select_related("owner")
        .first()
    )
    if session is None:
        return None, None
    return counters._person(session.owner), counters.counter_code(session)


def print_receipt(payment: models.Payment) -> dict[str, Any]:
    """The one-page receipt's facts for ONE payment."""
    from apps.payments import payment_detail, receipts

    row = selectors.payment_row(payment)
    clerk, counter = _counter(payment)
    if clerk is None:
        clerk = payment_detail._agent_name(payment)
    balance = receipts._ar_balance(payment.account_id, with_held_credit=True)
    return {
        "payment_id": str(payment.pk),
        "payment_no": row.get("payment_no"),
        "posted_at": row.get("posted_at"),
        "account_no": row.get("account_no"),
        "customer_name": row.get("customer_name"),
        "amount": row.get("amount"),
        "currency": row.get("currency"),
        "method_name": row.get("method_name"),
        "confirmation": row.get("confirmation") or None,
        "status": row.get("status"),
        "bills": [
            {"number": entry.get("invoice_number"), "amount": entry.get("amount")}
            for entry in row.get("applied_to") or ()
        ],
        "balance": None if balance is None else selectors._decimal_str(balance),
        "taken_by": clerk,
        "counter": counter,
    }
