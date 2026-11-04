# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-024 (the portal's balance) × CR-174-BRC10 (US Payments'
#           account lookup)
# Rules:    BR-CWP-047 (never cached) · BR-PAY-041 (a negative credit is a
#           real debt) · CR-059 CS-38 (held credit comes off the chase) ·
#           CLAUDE.md hard rule 2 (4 decimals stored, strings, never floats)
# Tests:    06-backend/tests/test_us_cwp_024_balance.py ·
#           06-backend/tests/test_cr174_us_payments.py
# Impacts:  apps/portal/seams/payments_seam.account_balance (delegates here) ·
#           apps/payments/agent_door.account_position (the US Payments lookup)
# ───────────────────────────────────────────────────────
"""WHAT ONE ACCOUNT OWES — the one read, for the customer portal AND a payment agent.

⚠ **MOVED HERE FROM `apps/portal/seams/payments_seam.py` ON 2026-10-07
(`CR-174-BRC10`) AND NOT COPIED.** The PO ruled, for US Payments' account
lookup: *"A person standing at a machine needs the live balance"* (D1), and the
coordinator's brief added *"the SAME balance read the customer portal uses …
one function, never a second balance calculation"*. Two callers of one figure
need one function, and the function belongs to the module whose rows it reads:
every input below is a `payments` read, so it lives in `payments` and the
portal's seam now delegates to it — byte-for-byte the same keys it always
served, plus three it did not.

**IT COMPUTES NOTHING THE TWO READS BELOW DO NOT ALREADY STATE**, which is the
portal seam's original promise and is kept:

* `open_bills.open_bill_position(account_id=)` — the open bills, oldest first,
  each with what it still asks for;
* `billing_seam.outstanding_positions(account_ids=)` — the same arithmetic in
  bulk, plus `oldest_due_on` and the credit taken off the chase (CS-38).

THE THREE KEYS ADDED, AND WHY EACH IS A STATEMENT RATHER THAN A NEW SUM
-----------------------------------------------------------------------
* `credit_position` — `selectors.account_credit_position`, SIGNED (BR-PAY-041:
  *"a negative credit is a real debt"*). The portal's `credit_held` is only the
  part of it that came off a bill; a payment agent needs the whole of it.
* `balance` — **the one consolidated, SIGNED account balance**: what the bills
  still ask for, less what the utility holds for the account. Negative means the
  account is in credit. Worked: bills open **$147.85**, credit **$0.00** →
  `147.8500`; after a **$150.00** payment the bills are met and **$2.15** is
  held → bills open **$0.00**, credit **$2.15** → `-2.1500`. The portal's
  `owing` floors that at zero by construction (a debtor list holds no
  creditors); a kiosk shows the customer their credit, so it needs the sign.
* `past_due` — the part of `balance` that is already late on `as_of`: the open
  balance of every bill due BEFORE that day, less any held credit, never below
  zero and never above `balance`. Bills with no due date are never late
  (BR-PAY-032 refuses to age a bill nobody can place in time). `None` when the
  caller names no day, because *late* is a statement about a date and this
  module reads no clock (BR-TEN-043).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from apps.payments import billing_seam as payments_billing_seam
from apps.payments import open_bills

FOUR_DP = Decimal("0.0001")
ZERO = Decimal("0")


def _money(value: Any) -> str:
    """Four decimals, as a string. Never a float, never cents (hard rule 2)."""
    return str(Decimal(value or 0).quantize(FOUR_DP))


def _past_due(bills: list[dict[str, Any]], *, as_of: date, held: Decimal, balance: Decimal) -> Decimal:
    late = ZERO
    for bill in bills:
        due_on = bill.get("due_on")
        if not due_on or date.fromisoformat(str(due_on)) >= as_of:
            continue
        late += Decimal(str(bill.get("open_balance") or "0"))
    late -= held if held > ZERO else ZERO
    if late < ZERO:
        late = ZERO
    if balance < late:
        late = balance if balance > ZERO else ZERO
    return late


def account_balance(account_id: Any, *, as_of: date | None = None) -> dict[str, Any]:
    """What ONE account owes, and the bills behind it.

    ⚠ **`account_id` IS ALWAYS ONE THE CALLER HAS ALREADY RESOLVED IN THIS
    TENANT.** The portal checks it is in the session's set; a payment agent's
    lookup resolves it by exact account number. Neither rule belongs in a read
    of money, and putting either here would make it the second place that rule
    is enforced.
    """
    from apps.payments import selectors as payments_selectors

    position = open_bills.open_bill_position(account_id=account_id)
    positions, seam_problems = payments_billing_seam.outstanding_positions(
        account_ids=[account_id]
    )
    outstanding = positions[0] if positions else None

    gross = Decimal(position.get("total_open") or "0")
    net = Decimal(getattr(outstanding, "balance", gross) if outstanding is not None else ZERO)
    credit = Decimal(getattr(outstanding, "credit_applied", ZERO) if outstanding is not None else ZERO)
    oldest_due = getattr(outstanding, "oldest_due_on", None) if outstanding is not None else None
    credit_position = Decimal(payments_selectors.account_credit_position(account_id))
    balance = gross - credit_position
    bills = list(position.get("bills") or ())

    problems = list(position.get("problems") or ()) + [dict(row) for row in seam_problems]
    return {
        "account_id": str(account_id),
        #: The figure the letter, the next bill and the ladder all state.
        "owing": _money(net),
        #: What the bills alone add up to, before any held credit came off.
        "bills_open": _money(gross),
        "credit_held": _money(credit),
        #: CR-174-BRC10 — signed; see the module docstring.
        "credit_position": _money(credit_position),
        "balance": _money(balance),
        "past_due": (
            None
            if as_of is None
            else _money(_past_due(bills, as_of=as_of, held=credit_position, balance=balance))
        ),
        "currency": position.get("currency"),
        "due_on": oldest_due.isoformat() if oldest_due is not None else None,
        "open_bill_count": len(bills),
        #: ⚠ Carried through so a screen can show the bills behind the number
        #: WITHOUT a second round trip and without adding anything up itself.
        "bills": bills,
        #: Named gaps rather than a silently wrong total.
        "problems": problems,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-174-BRC10 (moved from apps/portal/seams/payments_seam.py, US-CWP-024)
# generated: 2026-10-07 by the CR-174-BRC10 US Payments lane
# checklist: A✔ B✔ C✔ D✔ E=n/a(a read; the portal and the agent lookup are its screens) F✔ G✔ H=n/a
# gates: pytest tests/test_us_cwp_024_balance.py tests/test_cr174_us_payments.py
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
