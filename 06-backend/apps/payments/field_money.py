# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 · Phase 13 T-33 / T-34 — what the field app may READ
#           about an account's money, published by the module that owns it.
# Rules:    R16 (PO ruled: *"The field app reads money and never writes it"*) ·
#           R111 (a reconnect fee is its own question, asked beside the
#           arrears) · CR-186-BRC10 (posted then cleared; `balance_rule` is the
#           one statement of which payments count) · CLAUDE.md hard rule 1
#           (tenant scope) · hard rule 2 (4dp strings, never a float)
# Tests:    06-backend/tests/test_cr187_money_freshness.py ·
#           tests/test_cr187_money_push.py · tests/test_cr187_money_pg.py
# Impacts:  apps/work/seams/payments_seam.py (the only caller)
# ───────────────────────────────────────────────────────
"""Three READS for the field app — the balance, a charge's bill, what changed.

WHY THIS FILE EXISTS RATHER THAN A QUERY IN WORK'S SEAM
-------------------------------------------------------
Work may read payments only through `apps/work/seams/payments_seam.py`
(`BR-WRK-002`, `G78`). The three questions the handset asks — *what is owed*,
*is this charge's bill paid*, *whose money moved since* — are each answered
somewhere in payments already, by three different functions with three
different shapes. Writing them again in Work's seam would be a second balance
calculation, which `apps/payments/account_balance.py` was created to stop
(*"one function, never a second balance calculation"*, CR-174-BRC10). So this
file COMPOSES what payments already states and computes nothing of its own:

  * the balance is `account_balance.account_balance` — the portal's and the
    payment agent's read, byte for byte;
  * which payments count is `balance_rule` — never cancelled, failed or
    processing (CR-186-BRC10, `DEF-PAY-10340`);
  * *what changed since* is `bill_run_checks.accounts_changed_since` — the
    poll seam billing's bulk Check already uses, because this repository has no
    signal, outbox or event bus between modules (`apps/billing/
    check_staleness.py`, grepped 2026-09-30 and again 2026-10-21).

**IT WRITES NOTHING** (R16). Every function returns plain dicts of strings, so a
caller in another module cannot call `.save()` on a payments row.

THE TWO MONEY SHAPES
--------------------
Every amount travels as `{"amount": "241.3800", "display": "241.38",
"currency": "USD"}` — four decimals as stored and two for the screen, half-up
(`core.money.finalize`, hard rule 2). The handset never rounds and never does
arithmetic on money; a screen that needs a figure reads `display`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from core import money as core_money

FOUR_DP = Decimal("0.0001")


def _tenant_id() -> Any:
    from apps.payments import selectors

    # Refuses, never defaults — the module's one statement of hard rule 1.
    return selectors._tenant_id()


def money(value: Any, currency: Any) -> dict[str, Any] | None:
    """`{amount (4dp), display (2dp), currency}` — or None for no figure.

    None is never `0.00`: *we could not read it* and *nothing is owed* are two
    different facts and only one of them is a zero (`DEF-127`).
    """
    if value is None:
        return None
    figure = Decimal(str(value))
    return {
        "amount": str(figure.quantize(FOUR_DP)),
        "display": str(core_money.finalize(figure)),
        "currency": currency,
    }


def _latest_receipt(account_id: Any) -> Any:
    """The most recent payment that STANDS — `posted` or `cleared` — or None.

    `balance_rule.RECEIPT_STATUSES`: a cancelled, failed or processing row is
    not money the customer was given credit for, and showing it as *their last
    payment* would tell a technician a debt was met when the balance did not
    move. A deposit is HELD, never credit (US-PAY-002 TC-1), so it is not a
    payment toward what is owed either.
    """
    from apps.payments import balance_rule, models

    return (
        models.Payment.objects.filter(
            tenant_id=_tenant_id(),
            account_id=account_id,
            status__in=balance_rule.RECEIPT_STATUSES,
        )
        .exclude(purpose=models.PURPOSE_DEPOSIT)
        .select_related("method")
        .order_by("-posted_at", "-created_at")
        .first()
    )


def money_position(account_id: Any) -> dict[str, Any]:
    """What one account owes now, and the latest payment that stands.

    ⚠ **`account_id` IS ONE THE CALLER HAS ALREADY RESOLVED IN THIS TENANT** —
    Work resolves it from the technician's own job. The read is tenant-filtered
    in every query anyway (hard rule 1), so a foreign id answers an empty
    position rather than another utility's money.

    `owing` is the figure the letter, the next bill and the ladder state (never
    below zero); `balance` is signed (negative = in credit, BR-PAY-041).
    """
    from apps.payments import account_balance

    position = account_balance.account_balance(account_id)
    currency = position.get("currency")
    latest = _latest_receipt(account_id)
    payment = None
    if latest is not None:
        payment = {
            **money(latest.amount, latest.currency or currency),
            #: `posted` or `cleared` — the PO's two words of CR-186-BRC10:
            #: posted when taken, cleared when the bank statement agrees.
            "state": latest.status,
            "posted_at": latest.posted_at.isoformat() if latest.posted_at else None,
            "cleared_at": latest.cleared_at.isoformat() if latest.cleared_at else None,
            #: The tenant's own word for the tender (*Card*), never a code.
            "method": getattr(getattr(latest, "method", None), "name", None),
        }
    return {
        "owing": money(position.get("owing"), currency),
        "balance": money(position.get("balance"), currency),
        "currency": currency,
        "latest_payment": payment,
        # Named gaps from the reads behind the figure, carried rather than hidden.
        "problems": [
            {"code": row.get("code"), "br_ref": row.get("br_ref")}
            for row in position.get("problems") or ()
        ],
    }


def charge_position(account_id: Any, charge_code: str) -> dict[str, Any] | None:
    """The latest issued bill carrying `charge_code`, and whether it is paid.

    R111, the PO's case on FF-61: *"They cleared the arrears and did not pay the
    fee."* A single balance would read $0.00 there and say nothing, so the fee
    is asked as its OWN question — **the bill that charged it**, measured the
    way every open-bill read measures a bill: what it ASKS (`_amount_due`,
    BR-BIL-072) less what this module allocated to it.

    `charge_code` is the TENANT'S code (BR-BIL-007: fees are tenant-configured
    charge codes, never hardcoded) and arrives from data — a template step —
    never from a constant in Work.

    None when no issued bill carries the code: nothing was charged, which is a
    different answer from *charged and paid* and is never drawn as one.
    """
    from apps.payments import billing_seam

    if not charge_code:
        return None
    _tenant_id()
    queryset = billing_seam._resolve(billing_seam.BILLING_MODULE, billing_seam.INVOICE_QUERYSET_READ)
    if queryset is None:  # pragma: no cover - defensive; billing always publishes it
        return None
    invoice = (
        queryset()
        .filter(
            account_id=account_id,
            status__in=billing_seam.OPEN_INVOICE_STATUSES,
            lines__charge__code=str(charge_code),
        )
        .order_by("-issued_at", "-id")
        .distinct()
        .first()
    )
    if invoice is None:
        return None
    asked, _answered = billing_seam._amount_due(invoice, total=invoice.total)
    allocated = billing_seam.allocated_so_far(invoice.pk)
    still_open = asked - allocated
    if still_open < Decimal("0"):
        still_open = Decimal("0")
    return {
        "charge_code": str(charge_code),
        "bill_no": invoice.invoice_no,
        "charged_on": invoice.issued_at.date().isoformat() if invoice.issued_at else None,
        "charged": money(asked, invoice.currency),
        "still_open": money(still_open, invoice.currency),
        "paid": still_open <= Decimal("0"),
    }


def accounts_with_money_change_since(account_ids: Any, since: Any) -> dict[str, Any]:
    """`{account_id: latest change}` for accounts whose payments moved after `since`.

    Delegates to `bill_run_checks.accounts_changed_since` — ONE statement of
    *a payment changed*: a row posted, cleared, cancelled or reversed bumps
    `updated_at` on every writer (`reconciliation`, `cancel`, `reversal` all
    name it in `update_fields`). Read-only; one query.
    """
    from apps.payments import bill_run_checks

    return bill_run_checks.accounts_changed_since(account_ids, since)


#: FB-023 F5 — the two words a technician is shown about a payment plan.
PLAN_ON_TRACK = "on_track"
PLAN_BEHIND = "behind"


def plan_status(account_id: Any, *, as_of: Any) -> dict[str, Any] | None:
    """Is the account on a payment plan, and is it keeping to it? — FB-023 F5.

    `{"status": "on_track" | "behind", "missed": n}` for an ACTIVE plan, None
    for no plan (a proposed or unsigned plan is not in force, so it is none).
    *Behind* is `plans.outstanding_installments` — instalments due before
    `as_of` that no payment met by their due date, judged on the POSTING date
    (BR-PAY-021) — the same facts the dunning pause reads, never a second count.
    """
    from apps.payments import plans
    from apps.payments.collections_models import PLAN_ACTIVE

    plan = plans.live_plan_for(account_id)
    if plan is None or plan.status != PLAN_ACTIVE:
        return None
    missed = len(plans.outstanding_installments(plan, as_of=as_of))
    return {"status": PLAN_BEHIND if missed else PLAN_ON_TRACK, "missed": missed}


__all__ = [
    "accounts_with_money_change_since",
    "charge_position",
    "money",
    "money_position",
    "plan_status",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-042@3e02d12e (CR-187-BRC10 Phase 13 T-33/T-34 — the job on the phone; R16/R111; sha1[:8] of Rules.txt R16–R19 + WorkToDo.txt T-33..T-35, the design canvas of 2026-10-21)
# generated: 2026-10-21 by the CR-187 Phase 13 lane S-MONEY
# checklist: A✔ B✔ C✔ D=deferred(n/a — no route of its own — Work's seam calls it) E=deferred(n/a — no screen) F✔ G✔ H=deferred(n/a — composes reads; computes no money)
# gates: pytest tests/test_cr187_money_freshness.py tests/test_cr187_money_push.py · G78
# exceptions: none — every figure is an existing payments read; nothing is written
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────
